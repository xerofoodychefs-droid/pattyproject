import random, uuid, logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.order import Order, OrderItem, OrderStatusHistory, OrderStatus, OrderType, PaymentStatus
from app.models.branch import Branch
from app.models.product import Product, Inventory
from app.schemas.order import OrderCreateRequest, OrderResponse, StatusUpdateRequest
from app.services.pricing_service import calculate_order_totals
from app.services.payment_service import payment_provider
from app.api.endpoints.auth import require_role, get_current_user, get_optional_current_user
from app.models.user import UserRole, User
from app.models.loyalty import LoyaltyAccount, LoyaltyTransaction

from app.services.branch_service import (
    find_nearest_eligible_branch,
    calculate_haversine_miles,
    resolve_postcode_lat_lng,
    MAX_DELIVERY_RADIUS_MILES
)

from app.services.loyalty_service import (
    award_order_loyalty_points,
    reverse_order_loyalty_points,
    restore_redeemed_loyalty_points,
    validate_and_redeem_points
)

logger = logging.getLogger("pattyproject.orders")
router = APIRouter()

@router.post("", response_model=OrderResponse)
@router.post("/", response_model=OrderResponse)
def create_order(
    request: OrderCreateRequest,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Creates a new order with server-side pricing recalculation, inventory check, and initial PENDING_PAYMENT status.
    Mandatory backend enforcement of 2-mile delivery radius rule (<= 2.0 miles).
    Authoritatively validates loyalty points redemptions and eligible spend calculations.
    """
    order_type_clean = request.order_type.strip().upper()
    if order_type_clean not in ["DELIVERY", "COLLECTION"]:
        raise HTTPException(status_code=400, detail="Invalid order type. Must be DELIVERY or COLLECTION.")

    branch = db.query(Branch).filter(Branch.id == request.branch_id, Branch.is_active == True).first()
    if not branch:
        raise HTTPException(status_code=400, detail="Invalid branch selected")

    if not branch.ordering_enabled:
        raise HTTPException(status_code=400, detail=f"Ordering is currently disabled at {branch.name}.")

    if order_type_clean == "COLLECTION":
        if not branch.collection_enabled:
            raise HTTPException(status_code=400, detail=f"Collection is not currently available at {branch.name}.")

    # NON-NEGOTIABLE BACKEND ENFORCEMENT: 2-Mile Delivery Radius Validation
    branch_to_use = branch
    if order_type_clean == "DELIVERY":
        if not branch.delivery_enabled:
            raise HTTPException(status_code=400, detail=f"Delivery is not currently available from {branch.name}.")
        lat = request.latitude
        lng = request.longitude
        pc = request.delivery_postcode

        if (lat is None or lng is None) and isinstance(request.delivery_address, dict):
            lat = request.delivery_address.get("latitude")
            lng = request.delivery_address.get("longitude")
            if not pc:
                pc = request.delivery_address.get("postcode")

        if (lat is None or lng is None) and pc:
            resolved = resolve_postcode_lat_lng(pc)
            if resolved:
                lat, lng = resolved

        dist_result = find_nearest_eligible_branch(db, lat=lat, lng=lng, postcode=pc)

        if not dist_result.get("is_delivery_eligible") or dist_result.get("status") != "SUCCESS":
            nearest_b = dist_result.get("nearest_branch") or branch
            dist_val = dist_result.get("distance_miles")
            logger.warning(
                f"[SECURITY] Delivery order rejected. Distance: {dist_val} mi (Threshold: {MAX_DELIVERY_RADIUS_MILES} mi). Status: {dist_result.get('status')}."
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "code": "DELIVERY_OUTSIDE_RADIUS",
                    "message": "WE PROVIDE DELIVERY UP TO 2 MILES ONLY",
                    "suggestion": "Please collect your food from the nearest store.",
                    "nearest_branch": {
                        "id": nearest_b.id if nearest_b else branch.id,
                        "name": nearest_b.name if nearest_b else branch.name,
                        "distance_miles": dist_val
                    }
                }
            )

        # Check that the specific requested branch is within delivery radius
        if lat is not None and lng is not None and branch.latitude is not None and branch.longitude is not None:
            requested_branch_distance = calculate_haversine_miles(lat, lng, branch.latitude, branch.longitude)
            branch_max_radius = branch.delivery_radius_miles or MAX_DELIVERY_RADIUS_MILES
            if requested_branch_distance > branch_max_radius:
                nearest_b = dist_result.get("nearest_branch") or dist_result.get("assigned_branch") or branch
                logger.warning(
                    f"[SECURITY] Delivery order for {branch.name} rejected: customer is {requested_branch_distance:.2f} mi away (max {branch_max_radius} mi)."
                )
                raise HTTPException(
                    status_code=400,
                    detail={
                        "success": False,
                        "code": "DELIVERY_OUTSIDE_RADIUS",
                        "message": "WE PROVIDE DELIVERY UP TO 2 MILES ONLY",
                        "suggestion": "Please collect your food from the nearest store.",
                        "nearest_branch": {
                            "id": nearest_b.id,
                            "name": nearest_b.name,
                            "distance_miles": round(requested_branch_distance, 2)
                        }
                    }
                )

        branch_to_use = branch

    # 1. Authoritative Identity & Redemption Pre-Validation
    if request.redeem_points and request.redeem_points > 0:
        # SEC-LOYALTY-01: Points redemption strictly requires authenticated session
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to redeem loyalty points."
            )
        
        # Authenticated user cannot redeem on behalf of another user's email
        normalized_req_email = request.customer_email.strip().lower() if request.customer_email else ""
        normalized_curr_email = current_user.email.strip().lower() if current_user.email else ""
        if normalized_req_email and normalized_req_email != normalized_curr_email:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only redeem loyalty points for your own account."
            )

        resolved_user = current_user
        
        if request.redeem_points < 4000:
            raise HTTPException(
                status_code=400,
                detail="Minimum 4,000 Patty Points required for reward redemption."
            )
        if request.redeem_points % 1000 != 0:
            raise HTTPException(
                status_code=400,
                detail="Loyalty points can only be redeemed in whole 1,000-point increments (£1 per 1,000 points)."
            )
        
        # Authoritative loyalty account resolved strictly via current_user.id
        loyalty_acc = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == current_user.id).first()
        if not loyalty_acc or loyalty_acc.available_points < request.redeem_points:
            avail = loyalty_acc.available_points if loyalty_acc else 0
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient loyalty points. You have {avail:,} points but requested {request.redeem_points:,}."
            )
    else:
        # Normal guest or authenticated order without points redemption
        resolved_user = current_user
        if not resolved_user and request.customer_email:
            resolved_user = db.query(User).filter(User.email == request.customer_email.strip().lower()).first()

    # Calculate authoritative server totals
    items_input = [{"product_id": item.product_id, "quantity": item.quantity, "selected_modifiers": item.selected_modifiers} for item in request.items]
    totals = calculate_order_totals(
        db=db,
        items=items_input,
        order_type=request.order_type,
        coupon_code=request.coupon_code,
        redeem_reward_id=request.redeem_reward_id,
        redeem_points=request.redeem_points
    )

    if not totals["items"]:
        raise HTTPException(status_code=400, detail="Cart contains no valid items")

    # NON-NEGOTIABLE BACKEND ENFORCEMENT: €15.00 Minimum Delivery Subtotal Rule + Offer/Coupon Exception
    if order_type_clean == "DELIVERY":
        if not totals.get("is_delivery_subtotal_eligible", True):
            shortfall = totals.get("delivery_shortfall", 0.0)
            current_sub = totals.get("subtotal", 0.0)
            logger.warning(
                f"[BUSINESS_RULE] Delivery order rejected: subtotal €{current_sub:.2f} < €15.00 without valid promotion."
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "success": False,
                    "code": "MINIMUM_DELIVERY_ORDER_REQUIRED",
                    "message": f"Minimum order value of €15.00 required for delivery. Add €{shortfall:.2f} more to qualify.",
                    "min_threshold": 15.00,
                    "current_subtotal": current_sub,
                    "amount_needed": shortfall
                }
            )

    # Check branch stock availability
    for item in request.items:
        inv = db.query(Inventory).filter(
            Inventory.branch_id == branch_to_use.id,
            Inventory.product_id == item.product_id
        ).first()
        if inv and (not inv.is_available or inv.stock_quantity <= 0):
            prod = db.query(Product).filter(Product.id == item.product_id).first()
            prod_name = prod.name if prod else "Item"
            raise HTTPException(
                status_code=400,
                detail=f"'{prod_name}' is currently out of stock at {branch_to_use.name}."
            )

    order_num = f"#PP{random.randint(1000, 9999)}"

    slot_time = None
    if isinstance(request.collection_slot_time, str) and request.collection_slot_time.strip():
        try:
            from datetime import datetime as dt
            slot_time = dt.fromisoformat(request.collection_slot_time.strip())
        except Exception:
            slot_time = None
    elif hasattr(request.collection_slot_time, "isoformat"):
        slot_time = request.collection_slot_time

    if resolved_user and not resolved_user.phone and request.customer_phone:
        resolved_user.phone = request.customer_phone

    order = Order(
        order_number=order_num,
        customer_id=resolved_user.id if resolved_user else None,
        customer_name=request.customer_name,
        customer_email=request.customer_email.strip().lower(),
        customer_phone=request.customer_phone,
        branch_id=branch_to_use.id,
        order_type=request.order_type,
        status=OrderStatus.PENDING_PAYMENT,
        delivery_address=request.delivery_address,
        collection_slot_time=slot_time,
        delivery_instructions=request.delivery_instructions,

        subtotal=totals["subtotal"],
        delivery_fee=totals["delivery_fee"],
        service_fee=totals["service_fee"],
        discount_amount=totals["discount_amount"],
        vat_amount=totals["vat_amount"],
        total_amount=totals["total_amount"],
        payment_method="Client Payment Gateway",
        payment_status=PaymentStatus.PENDING,
        coupon_code=request.coupon_code,
        points_earned=totals["points_earned"],
        points_redeemed=totals.get("points_redeemed", 0)
    )
    db.add(order)
    db.flush()

    # Process points deduction if points were redeemed
    if order.points_redeemed > 0 and current_user:
        ok, msg, tx = validate_and_redeem_points(
            db=db,
            user_id=current_user.id,
            points_to_redeem=order.points_redeemed,
            order_id=order.id
        )
        if not ok:
            db.rollback()
            raise HTTPException(status_code=400, detail=msg)

    for item_data in totals["items"]:
        oi = OrderItem(
            order_id=order.id,
            product_id=item_data["product_id"],
            product_name=item_data["product_name"],
            quantity=item_data["quantity"],
            unit_price=item_data["unit_price"],
            total_price=item_data["total_price"],
            selected_modifiers=item_data["selected_modifiers"]
        )
        db.add(oi)

    history = OrderStatusHistory(
        order_id=order.id,
        from_status=None,
        to_status=OrderStatus.PENDING_PAYMENT,
        notes="Order created, awaiting payment gateway confirmation"
    )
    db.add(history)

    db.commit()
    db.refresh(order)
    logger.info(f"Order {order.order_number} ({order.id}) created successfully. Type: {order.order_type}, Branch: {order.branch_id}, Amount: £{order.total_amount:.2f}")
    return order

@router.get("/my-orders", response_model=List[OrderResponse])
def get_my_orders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns order history for the logged-in customer."""
    user_email = current_user.email.strip().lower()
    orders = db.query(Order).filter(
        (Order.customer_id == current_user.id) | (Order.customer_email == user_email)
    ).order_by(Order.created_at.desc()).all()
    return orders

@router.get("/{order_number}", response_model=OrderResponse)
def get_order_by_number(
    order_number: str,
    email: Optional[str] = Query(None),
    guest_email: Optional[str] = Query(None),
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Customer order inspection / status tracking or admin inspection.
    Enforces strict ownership & role authorization to prevent IDOR / PII enumeration.
    """
    order = db.query(Order).filter(
        (Order.order_number == order_number) | (Order.id == order_number)
    ).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # 1. Super Admin -> Full Access
    if current_user and current_user.role == UserRole.SUPER_ADMIN:
        return order

    # 2. Branch Admin -> Assigned Branch Isolation Check
    if current_user and current_user.role == UserRole.BRANCH_ADMIN:
        assigned_ids = [bu.branch_id for bu in current_user.branch_assignments]
        if order.branch_id not in assigned_ids:
            raise HTTPException(status_code=403, detail="Access denied to order outside assigned branch")
        return order

    # 3. Authenticated Customer -> Must own the order
    if current_user and current_user.role == UserRole.CUSTOMER:
        is_owner = (
            (order.customer_id and order.customer_id == current_user.id) or
            (order.customer_email and order.customer_email.strip().lower() == current_user.email.strip().lower())
        )
        if not is_owner:
            raise HTTPException(status_code=403, detail="Access denied: You do not have permission to view this order")
        return order

    # 4. Unauthenticated Guest Tracking -> Requires verification with customer email
    check_email = (email or guest_email or "").strip().lower()
    if check_email and order.customer_email and check_email == order.customer_email.strip().lower():
        return order

    # 5. Unauthenticated Caller without proof of ownership -> Denied
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication or customer email verification required to access order details",
        headers={"WWW-Authenticate": "Bearer"}
    )


@router.get("", response_model=List[OrderResponse])
@router.get("/", response_model=List[OrderResponse])
def list_admin_orders(
    response: Response,
    branch_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.BRANCH_ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Branch-Isolated Admin Orders list.
    Super Admin can view orders from all branches or a specific branch.
    Branch Admins view orders ONLY for their assigned branch.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    query = db.query(Order)

    if current_user.role == UserRole.BRANCH_ADMIN:
        assigned_ids = [bu.branch_id for bu in current_user.branch_assignments]
        if branch_id and branch_id not in assigned_ids:
            raise HTTPException(status_code=403, detail="Access denied to this branch's orders")
        query = query.filter(Order.branch_id.in_(assigned_ids))
    elif branch_id and branch_id != "ALL":
        query = query.filter(Order.branch_id == branch_id)

    if status and status != "ALL":
        query = query.filter(Order.status == status)

    return query.order_by(Order.created_at.desc()).all()

@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: str,
    request: StatusUpdateRequest,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN, UserRole.BRANCH_ADMIN])),
    db: Session = Depends(get_db)
):
    """Trigger order status transition with audit log and branch isolation."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Branch Admin Isolation check
    if current_user.role == UserRole.BRANCH_ADMIN:
        assigned_ids = [bu.branch_id for bu in current_user.branch_assignments]
        if order.branch_id not in assigned_ids:
            raise HTTPException(status_code=403, detail="Cannot manage order outside assigned branch")

    old_status = order.status
    new_status = request.status.upper()

    # Concurrency / Idempotency protection: if status is already at the target state, return early
    if new_status == old_status:
        return order

    # Terminal state transition protection: terminal orders cannot be reopened
    terminal_statuses = [
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
        OrderStatus.REFUNDED,
        OrderStatus.DELIVERED,
        OrderStatus.COLLECTED
    ]
    if old_status in terminal_statuses and new_status not in terminal_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition order from terminal status '{old_status}' to '{new_status}'."
        )

    order.status = new_status
    if new_status in [OrderStatus.ACCEPTED, OrderStatus.PREPARING, OrderStatus.READY, OrderStatus.OUT_FOR_DELIVERY, OrderStatus.DELIVERED, OrderStatus.COLLECTED, OrderStatus.PAID]:
        order.payment_status = PaymentStatus.PAID
        try:
            award_order_loyalty_points(db, order)
        except Exception as e:
            logger.warning(f"Loyalty award note for order {order.order_number}: {e}")
    elif new_status in [OrderStatus.CANCELLED, OrderStatus.REFUNDED, OrderStatus.REJECTED]:
        if new_status == OrderStatus.REFUNDED:
            order.payment_status = PaymentStatus.REFUNDED
        try:
            restore_redeemed_loyalty_points(db, order, reason=request.notes or f"Order status transitioned to {new_status}")
            reverse_order_loyalty_points(db, order, reason=request.notes or f"Order status transitioned to {new_status}")
        except Exception as e:
            logger.warning(f"Loyalty reversal note for order {order.order_number}: {e}")

    history = OrderStatusHistory(
        order_id=order.id,
        user_id=current_user.id if current_user else None,
        from_status=old_status,
        to_status=new_status,
        notes=request.notes or f"Status updated to {new_status}" + (f" by {current_user.full_name}" if current_user else "")
    )
    db.add(history)

    db.commit()
    db.refresh(order)

    # Real-time WebSocket broadcast to all authorized admin connections
    try:
        from app.core.websocket_manager import manager, format_order_payload
        manager.sync_broadcast_order_event(
            event_type="ORDER_STATUS_CHANGED",
            order_data=format_order_payload(order),
            branch_id=str(order.branch_id)
        )
    except Exception as e:
        logger.warning(f"[WS_BROADCAST_FAILED] Failed to broadcast ORDER_STATUS_CHANGED for order {order.order_number}: {e}")

    return order


