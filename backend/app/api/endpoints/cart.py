from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.models.cart import Cart
from app.api.endpoints.auth import get_optional_current_user, get_current_user
from app.schemas.cart import (
    CartResponse,
    CartItemResponse,
    CartItemCreateRequest,
    CartItemUpdateRequest,
    CartSettingsUpdateRequest,
    CartMergeRequest
)
from app.services.cart_service import (
    get_or_create_cart,
    add_item_to_cart,
    update_cart_item_quantity,
    remove_cart_item,
    clear_cart,
    set_cart_settings,
    merge_guest_cart_into_user_cart,
    serialize_cart
)

router = APIRouter()


def _resolve_cart(
    db: Session,
    current_user: Optional[User],
    x_guest_session_id: Optional[str]
) -> Cart:
    """
    Authoritative Cart Resolver:
    - If user is authenticated: derived STRICTLY from JWT current_user.id.
    - If user is guest: derived from X-Guest-Session-ID header.
    - Frontend cannot spoof or supply user_id in request bodies.
    """
    if current_user:
        return get_or_create_cart(db, user_id=current_user.id)
    return get_or_create_cart(db, session_id=x_guest_session_id)


@router.get("", response_model=CartResponse)
@router.get("/", response_model=CartResponse)
def get_cart(
    response: Response,
    current_user: Optional[User] = Depends(get_optional_current_user),
    x_guest_session_id: Optional[str] = Header(None, alias="X-Guest-Session-ID"),
    db: Session = Depends(get_db)
):
    """
    Retrieves the authoritative active cart for the authenticated user or guest session.
    Sets X-Guest-Session-ID in response header for guest sessions.
    """
    cart = _resolve_cart(db, current_user, x_guest_session_id)
    if not current_user and cart.session_id:
        response.headers["X-Guest-Session-ID"] = cart.session_id
    return serialize_cart(cart)


@router.post("/items", response_model=CartResponse)
def add_cart_item(
    item_in: CartItemCreateRequest,
    response: Response,
    current_user: Optional[User] = Depends(get_optional_current_user),
    x_guest_session_id: Optional[str] = Header(None, alias="X-Guest-Session-ID"),
    db: Session = Depends(get_db)
):
    """
    Adds a product with modifiers/choices to the active cart.
    Merges quantities if identical item configuration already exists.
    """
    cart = _resolve_cart(db, current_user, x_guest_session_id)
    add_item_to_cart(
        db=db,
        cart=cart,
        product_id=item_in.product_id,
        quantity=item_in.quantity,
        modifiers=item_in.selected_modifiers,
        choices=item_in.selected_choices,
        removed_ingredients=item_in.removed_ingredients
    )
    if not current_user and cart.session_id:
        response.headers["X-Guest-Session-ID"] = cart.session_id
    db.refresh(cart)
    return serialize_cart(cart)


@router.patch("/items/{item_id}", response_model=CartResponse)
def update_cart_item(
    item_id: str,
    item_in: CartItemUpdateRequest,
    response: Response,
    current_user: Optional[User] = Depends(get_optional_current_user),
    x_guest_session_id: Optional[str] = Header(None, alias="X-Guest-Session-ID"),
    db: Session = Depends(get_db)
):
    """
    Updates the quantity of a specific cart item.
    Removes the item if quantity is set to 0.
    Enforces that item_id belongs to the resolved cart.
    """
    cart = _resolve_cart(db, current_user, x_guest_session_id)
    update_cart_item_quantity(
        db=db,
        cart=cart,
        item_id=item_id,
        quantity=item_in.quantity
    )
    if not current_user and cart.session_id:
        response.headers["X-Guest-Session-ID"] = cart.session_id
    db.refresh(cart)
    return serialize_cart(cart)


@router.delete("/items/{item_id}", response_model=CartResponse)
def delete_cart_item(
    item_id: str,
    response: Response,
    current_user: Optional[User] = Depends(get_optional_current_user),
    x_guest_session_id: Optional[str] = Header(None, alias="X-Guest-Session-ID"),
    db: Session = Depends(get_db)
):
    """
    Removes a specific item from the cart.
    Enforces that item_id belongs to the resolved cart.
    """
    cart = _resolve_cart(db, current_user, x_guest_session_id)
    remove_cart_item(db=db, cart=cart, item_id=item_id)
    if not current_user and cart.session_id:
        response.headers["X-Guest-Session-ID"] = cart.session_id
    db.refresh(cart)
    return serialize_cart(cart)


@router.delete("", response_model=CartResponse)
@router.post("/clear", response_model=CartResponse)
def clear_active_cart(
    response: Response,
    current_user: Optional[User] = Depends(get_optional_current_user),
    x_guest_session_id: Optional[str] = Header(None, alias="X-Guest-Session-ID"),
    db: Session = Depends(get_db)
):
    """
    Clears all items from the active cart.
    """
    cart = _resolve_cart(db, current_user, x_guest_session_id)
    clear_cart(db=db, cart=cart)
    if not current_user and cart.session_id:
        response.headers["X-Guest-Session-ID"] = cart.session_id
    return serialize_cart(cart)


@router.patch("/settings", response_model=CartResponse)
def update_cart_settings(
    settings_in: CartSettingsUpdateRequest,
    response: Response,
    current_user: Optional[User] = Depends(get_optional_current_user),
    x_guest_session_id: Optional[str] = Header(None, alias="X-Guest-Session-ID"),
    db: Session = Depends(get_db)
):
    """
    Updates branch, order type, or applied coupon for the active cart.
    """
    cart = _resolve_cart(db, current_user, x_guest_session_id)
    set_cart_settings(
        db=db,
        cart=cart,
        branch_id=settings_in.branch_id,
        order_type=settings_in.order_type,
        coupon_code=settings_in.coupon_code
    )
    if not current_user and cart.session_id:
        response.headers["X-Guest-Session-ID"] = cart.session_id
    return serialize_cart(cart)


@router.post("/merge", response_model=CartResponse)
def merge_cart(
    merge_in: CartMergeRequest,
    current_user: User = Depends(get_current_user),
    x_guest_session_id: Optional[str] = Header(None, alias="X-Guest-Session-ID"),
    db: Session = Depends(get_db)
):
    """
    Merges guest cart into the authenticated customer's account cart upon login:
    - Destination user is STRICTLY derived from JWT current_user.id.
    - Guest cart is resolved via header or request body.
    - Atomically transfers items and deletes the guest cart.
    """
    guest_session = merge_in.guest_session_id or x_guest_session_id
    merged_cart = merge_guest_cart_into_user_cart(
        db=db,
        user_id=current_user.id,
        guest_session_id=guest_session,
        guest_items=merge_in.items
    )
    return serialize_cart(merged_cart)
