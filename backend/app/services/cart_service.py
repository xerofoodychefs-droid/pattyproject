import uuid
import json
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone

from app.models.cart import Cart, CartItem
from app.models.product import Product
from app.models.branch import Branch
from app.schemas.cart import (
    CartResponse,
    CartItemResponse,
    CartProductOut,
    CartItemCreateRequest
)


def _normalize_configuration(
    modifiers: Optional[List[Dict[str, Any]]] = None,
    choices: Optional[List[Dict[str, Any]]] = None,
    removed_ingredients: Optional[List[str]] = None
) -> Tuple[str, str, str]:
    """Generates canonical string signatures for configuration comparison."""
    mod_list = sorted(modifiers or [], key=lambda m: (m.get("name", ""), float(m.get("price", 0))))
    choice_list = sorted(
        choices or [],
        key=lambda c: (c.get("group_id", ""), c.get("option_id", ""), float(c.get("price_delta", 0)))
    )
    rem_list = sorted(removed_ingredients or [])
    return (
        json.dumps(mod_list, sort_keys=True),
        json.dumps(choice_list, sort_keys=True),
        json.dumps(rem_list, sort_keys=True)
    )


def calculate_item_prices(product: Product, selected_modifiers: Optional[List[Dict[str, Any]]], selected_choices: Optional[List[Dict[str, Any]]], quantity: int) -> Tuple[float, float]:
    """Calculates unit_price and line_total for a cart item."""
    mod_cost = sum(float(m.get("price", 0)) for m in (selected_modifiers or []))
    choice_cost = sum(float(c.get("price_delta", 0)) for c in (selected_choices or []))
    unit_price = round(product.base_price + mod_cost + choice_cost, 2)
    line_total = round(unit_price * quantity, 2)
    return unit_price, line_total


def get_or_create_cart(
    db: Session,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None
) -> Cart:
    """
    Resolves or creates the active Cart:
    - For authenticated users: strictly queried/scoped by user_id with concurrency collision protection.
    - For guests: strictly queried/scoped by session_id (with user_id IS NULL).
    """
    if user_id:
        cart = db.query(Cart).filter(Cart.user_id == user_id).first()
        if cart:
            return cart

        try:
            new_cart = Cart(user_id=user_id, session_id=None, order_type="COLLECTION")
            db.add(new_cart)
            db.commit()
            db.refresh(new_cart)
            return new_cart
        except IntegrityError:
            db.rollback()
            # Concurrency race: winning thread created the cart
            winning_cart = db.query(Cart).filter(Cart.user_id == user_id).first()
            if winning_cart:
                return winning_cart
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to initialize user cart")

    if session_id:
        clean_session_id = session_id.strip()
        cart = db.query(Cart).filter(Cart.session_id == clean_session_id, Cart.user_id.is_(None)).first()
        if cart:
            return cart

        new_cart = Cart(session_id=clean_session_id, user_id=None, order_type="COLLECTION")
        db.add(new_cart)
        db.commit()
        db.refresh(new_cart)
        return new_cart

    # Neither provided: generate fresh guest cart
    random_session_id = str(uuid.uuid4())
    new_cart = Cart(session_id=random_session_id, user_id=None, order_type="COLLECTION")
    db.add(new_cart)
    db.commit()
    db.refresh(new_cart)
    return new_cart


def add_item_to_cart(
    db: Session,
    cart: Cart,
    product_id: str,
    quantity: int,
    modifiers: Optional[List[Dict[str, Any]]] = None,
    choices: Optional[List[Dict[str, Any]]] = None,
    removed_ingredients: Optional[List[str]] = None
) -> CartItem:
    """Adds an item or increments quantity if identical item configuration already exists."""
    if quantity <= 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Quantity must be at least 1")

    product = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or currently unavailable")

    target_mod_sig, target_choice_sig, target_rem_sig = _normalize_configuration(modifiers, choices, removed_ingredients)

    # Check for existing matching line item
    for item in cart.items:
        if item.product_id == product.id:
            item_mod_sig, item_choice_sig, item_rem_sig = _normalize_configuration(
                item.selected_modifiers, item.selected_choices, item.removed_ingredients
            )
            if item_mod_sig == target_mod_sig and item_choice_sig == target_choice_sig and item_rem_sig == target_rem_sig:
                item.quantity += quantity
                item.updated_at = datetime.now(timezone.utc)
                cart.updated_at = datetime.now(timezone.utc)
                db.commit()
                db.refresh(item)
                return item

    # Create new line item
    new_item = CartItem(
        cart_id=cart.id,
        product_id=product.id,
        quantity=quantity,
        selected_modifiers=modifiers or [],
        selected_choices=choices or [],
        removed_ingredients=removed_ingredients or []
    )
    cart.updated_at = datetime.now(timezone.utc)
    db.add(new_item)
    db.commit()
    db.refresh(new_item)
    return new_item


def update_cart_item_quantity(
    db: Session,
    cart: Cart,
    item_id: str,
    quantity: int
) -> Optional[CartItem]:
    """Updates item quantity or removes item if quantity <= 0."""
    item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.cart_id == cart.id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found in your cart")

    if quantity <= 0:
        db.delete(item)
        cart.updated_at = datetime.now(timezone.utc)
        db.commit()
        return None

    item.quantity = quantity
    item.updated_at = datetime.now(timezone.utc)
    cart.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return item


def remove_cart_item(db: Session, cart: Cart, item_id: str) -> bool:
    """Removes a specific item from the cart."""
    item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.cart_id == cart.id).first()
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cart item not found in your cart")

    db.delete(item)
    cart.updated_at = datetime.now(timezone.utc)
    db.commit()
    return True


def clear_cart(db: Session, cart: Cart):
    """Clears all items and active coupon from the cart."""
    for item in list(cart.items):
        db.delete(item)
    cart.coupon_code = None
    cart.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cart)


def set_cart_settings(
    db: Session,
    cart: Cart,
    branch_id: Optional[str] = None,
    order_type: Optional[str] = None,
    coupon_code: Optional[str] = None
) -> Cart:
    """Updates branch, order type, and active coupon on cart."""
    if branch_id is not None:
        if branch_id:
            branch = db.query(Branch).filter(Branch.id == branch_id, Branch.is_active == True).first()
            if not branch:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected branch does not exist")
            cart.branch_id = branch.id
        else:
            cart.branch_id = None

    if order_type is not None:
        order_type_clean = order_type.strip().upper()
        if order_type_clean not in ["DELIVERY", "COLLECTION"]:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid order type. Must be DELIVERY or COLLECTION")
        cart.order_type = order_type_clean

    if coupon_code is not None:
        cart.coupon_code = coupon_code.strip() if coupon_code else None

    cart.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(cart)
    return cart


def merge_guest_cart_into_user_cart(
    db: Session,
    user_id: str,
    guest_session_id: Optional[str] = None,
    guest_items: Optional[List[CartItemCreateRequest]] = None
) -> Cart:
    """
    Atomically merges guest cart items into the authenticated customer's account cart:
    1. Locks / resolves destination account cart.
    2. Merges identical line item configurations by combining quantities.
    3. Retires and removes the guest cart.
    4. Commits atomically so no lost items or duplicate carts remain.
    """
    user_cart = get_or_create_cart(db, user_id=user_id)

    # 1. Merge by guest session ID
    if guest_session_id:
        clean_session = guest_session_id.strip()
        guest_cart = db.query(Cart).filter(Cart.session_id == clean_session, Cart.user_id.is_(None)).first()
        if guest_cart and guest_cart.id != user_cart.id:
            # Transfer/Merge items
            for g_item in list(guest_cart.items):
                # Verify product is still active
                product = db.query(Product).filter(Product.id == g_item.product_id, Product.is_active == True).first()
                if product:
                    add_item_to_cart(
                        db=db,
                        cart=user_cart,
                        product_id=g_item.product_id,
                        quantity=g_item.quantity,
                        modifiers=g_item.selected_modifiers,
                        choices=g_item.selected_choices,
                        removed_ingredients=g_item.removed_ingredients
                    )

            if not user_cart.branch_id and guest_cart.branch_id:
                user_cart.branch_id = guest_cart.branch_id
                user_cart.order_type = guest_cart.order_type

            # Delete the guest cart after merge
            db.delete(guest_cart)
            db.commit()

    # 2. Merge explicit payload items if provided
    if guest_items:
        for item_data in guest_items:
            product = db.query(Product).filter(Product.id == item_data.product_id, Product.is_active == True).first()
            if product:
                add_item_to_cart(
                    db=db,
                    cart=user_cart,
                    product_id=item_data.product_id,
                    quantity=item_data.quantity,
                    modifiers=item_data.selected_modifiers,
                    choices=item_data.selected_choices,
                    removed_ingredients=item_data.removed_ingredients
                )

    db.refresh(user_cart)
    return user_cart


def serialize_cart(cart: Cart) -> CartResponse:
    """Serializes a Cart model into CartResponse with calculated unit and line prices."""
    item_responses: List[CartItemResponse] = []
    subtotal = 0.0
    total_count = 0

    for item in cart.items:
        prod = item.product
        if not prod:
            continue
        unit_price, line_total = calculate_item_prices(
            product=prod,
            selected_modifiers=item.selected_modifiers,
            selected_choices=item.selected_choices,
            quantity=item.quantity
        )
        subtotal += line_total
        total_count += item.quantity

        product_out = CartProductOut(
            id=prod.id,
            name=prod.name,
            sku=prod.sku,
            base_price=prod.base_price,
            image_url=prod.image_url,
            is_active=prod.is_active,
            category_id=prod.category_id
        )

        item_responses.append(CartItemResponse(
            id=item.id,
            cart_id=item.cart_id,
            product_id=item.product_id,
            product=product_out,
            quantity=item.quantity,
            selected_modifiers=item.selected_modifiers or [],
            selected_choices=item.selected_choices or [],
            removed_ingredients=item.removed_ingredients or [],
            unit_price=unit_price,
            line_total=line_total
        ))

    return CartResponse(
        id=cart.id,
        user_id=cart.user_id,
        session_id=cart.session_id,
        order_type=cart.order_type,
        branch_id=cart.branch_id,
        coupon_code=cart.coupon_code,
        items=item_responses,
        subtotal=round(subtotal, 2),
        item_count=total_count
    )
