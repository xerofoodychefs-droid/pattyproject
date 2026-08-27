from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, Header, Query
from sqlalchemy.orm import Session
from app.core.config import settings
from app.core.database import get_db
from app.models.order import Order, OrderStatus, OrderType, PaymentStatus as OrderPaymentStatus
from app.models.payment import Payment, PaymentStatus, PaymentProvider
from app.models.branch import Branch
from app.schemas.payment import (
    PaymentResponse,
    PaymentSessionCreateRequest,
    PaymentSessionResponse,
    PaymentRefundRequest,
    PaymentWebhookPayload,
    PaymentConfigResponse,
    PaymentProcessRequest
)
from app.services.payment_service import (
    get_payment_provider,
    get_or_create_payment_for_order,
    transition_payment_status,
    process_payment_refund,
    process_payment_event,
    award_order_loyalty_points,
    NormalizedPaymentEvent,
    InvalidPaymentTransitionError,
    MockPaymentProvider
)
from app.services.square_service import SquarePaymentError
from app.services.branch_service import calculate_haversine_miles, MAX_DELIVERY_RADIUS_MILES
from app.api.endpoints.auth import require_role, get_current_user
from app.models.user import UserRole, User

router = APIRouter()


def check_mock_gateway_allowed():
    """Refuses execution if mock gateway is called in production environment."""
    if settings.is_production:
        raise HTTPException(
            status_code=403,
            detail="Mock payment gateway is strictly disabled in production environments."
        )


@router.get("/config", response_model=PaymentConfigResponse)
def get_payment_configuration():
    """
    Returns public client gateway configuration (Application ID, Location ID, Environment).
    Strictly excludes server-side secrets and access tokens.
    """
    provider_name = (settings.PAYMENT_PROVIDER or "").lower()
    is_square = provider_name == "square" or bool(settings.SQUARE_ACCESS_TOKEN and settings.SQUARE_APPLICATION_ID)
    return PaymentConfigResponse(
        provider="square" if is_square else "mock",
        application_id=settings.SQUARE_APPLICATION_ID if is_square else None,
        location_id=settings.SQUARE_LOCATION_ID if is_square else None,
        environment="sandbox" if settings.is_square_sandbox else "production"
    )


@router.post("/create-session", response_model=PaymentSessionResponse)
async def create_payment_session(
    request_data: PaymentSessionCreateRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db)
):
    """
    Initializes payment session or executes direct Square payment when source_id is provided.
    Canonical contract:
    POST /api/v1/payments/create-session
    Headers:
      Idempotency-Key: <key>
    JSON Body:
      {
        "order_id": "<ORDER_ID>",
        "payment_method_type": "CARD",
        "source_id": "cnon:..." (optional Square nonce)
      }
    """
    provider = get_payment_provider()
    target_provider_name = PaymentProvider.SQUARE if (settings.PAYMENT_PROVIDER == "square" or settings.SQUARE_ACCESS_TOKEN) else PaymentProvider.MOCK

    if target_provider_name == PaymentProvider.MOCK:
        check_mock_gateway_allowed()

    target_order_id = request_data.order_id
    effective_idempotency_key = idempotency_key or request_data.idempotency_key

    order = db.query(Order).filter(Order.id == target_order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Protection: Cancelled order payment rejection
    if order.status == OrderStatus.CANCELLED:
        raise HTTPException(status_code=400, detail="Cannot initiate payment for a cancelled order.")

    # Protection: Delivery radius validation
    if order.order_type == OrderType.DELIVERY and order.delivery_address:
        addr = order.delivery_address
        lat = addr.get("latitude") if isinstance(addr, dict) else getattr(addr, "latitude", None)
        lng = addr.get("longitude") if isinstance(addr, dict) else getattr(addr, "longitude", None)

        if lat is not None and lng is not None:
            branch = db.query(Branch).filter(Branch.id == order.branch_id).first()
            if branch and branch.latitude is not None and branch.longitude is not None:
                dist = calculate_haversine_miles(lat, lng, branch.latitude, branch.longitude)
                if dist > (branch.delivery_radius_miles or MAX_DELIVERY_RADIUS_MILES):
                    raise HTTPException(
                        status_code=400,
                        detail={
                            "code": "DELIVERY_OUTSIDE_RADIUS",
                            "message": "WE PROVIDE DELIVERY UP TO 2 MILES ONLY",
                            "distance_miles": round(dist, 2),
                            "max_radius_miles": branch.delivery_radius_miles or MAX_DELIVERY_RADIUS_MILES
                        }
                    )

    # Protection: Already paid protection
    if order.payment_status == OrderPaymentStatus.PAID:
        existing_paid = db.query(Payment).filter(
            Payment.order_id == order.id,
            Payment.status == PaymentStatus.PAID
        ).first()
        if existing_paid:
            return PaymentSessionResponse(
                provider=existing_paid.provider,
                order_id=order.id,
                payment_id=existing_paid.id,
                transaction_id=existing_paid.transaction_id or "ALREADY_PAID",
                amount=existing_paid.amount,
                currency=existing_paid.currency,
                status=PaymentStatus.PAID,
                client_secret=None,
                payment_url=None,
                order_number=order.order_number
            )

    method_type = request_data.payment_method_type if request_data and request_data.payment_method_type else "CARD"

    # Fetch or initialize the provider-independent payment ledger entry
    payment = get_or_create_payment_for_order(
        db=db,
        order=order,
        provider=target_provider_name,
        idempotency_key=effective_idempotency_key,
        payment_method_type=method_type
    )

    # Idempotent re-request check for existing uncharged mock session
    if payment.transaction_id and not request_data.source_id and target_provider_name == PaymentProvider.MOCK:
        final_tx_id = payment.transaction_id
        return PaymentSessionResponse(
            provider=payment.provider,
            order_id=order.id,
            payment_id=payment.id,
            transaction_id=final_tx_id,
            amount=payment.amount,
            currency=payment.currency,
            status=payment.status,
            client_secret=f"sec_mock_{final_tx_id}",
            payment_url=f"/mock-checkout/{final_tx_id}",
            order_number=order.order_number
        )

    try:
        session_data = await provider.create_payment_session(
            order_id=order.id,
            amount=payment.amount,
            currency=payment.currency,
            customer_info={"name": order.customer_name, "email": order.customer_email},
            idempotency_key=effective_idempotency_key,
            source_id=request_data.source_id,
            order_number=order.order_number
        )
    except SquarePaymentError as exc:
        payment.status = PaymentStatus.FAILED
        payment.error_code = exc.error_code
        payment.error_message = exc.message
        db.commit()
        raise HTTPException(
            status_code=400,
            detail={"code": exc.error_code, "message": exc.message}
        )

    # Update payment transaction ID and status if charged directly
    if session_data.get("transaction_id"):
        payment.transaction_id = session_data.get("transaction_id")
        order.payment_transaction_id = session_data.get("transaction_id")

    if session_data.get("status") == PaymentStatus.PAID:
        payment.status = PaymentStatus.PAID
        payment.raw_response = session_data.get("raw_response")
        order.payment_status = PaymentStatus.PAID
        if order.status == OrderStatus.PENDING_PAYMENT:
            order.status = OrderStatus.INCOMING
        award_order_loyalty_points(db, order)

    db.commit()
    db.refresh(payment)

    final_tx_id = payment.transaction_id or session_data.get("transaction_id", "")
    client_sec = session_data.get("client_secret") or (f"sec_mock_{final_tx_id}" if target_provider_name == PaymentProvider.MOCK else None)
    pay_url = session_data.get("payment_url") or (f"/mock-checkout/{final_tx_id}" if target_provider_name == PaymentProvider.MOCK else None)

    return PaymentSessionResponse(
        provider=payment.provider,
        order_id=order.id,
        payment_id=payment.id,
        transaction_id=final_tx_id,
        amount=payment.amount,
        currency=payment.currency,
        status=payment.status,
        client_secret=client_sec,
        payment_url=pay_url,
        order_number=order.order_number,
        receipt_url=session_data.get("receipt_url")
    )


@router.post("/webhook")
async def payment_gateway_webhook(request: Request, db: Session = Depends(get_db)):
    """
    Inbound provider webhook endpoint for server-to-server gateway callbacks.
    Verifies gateway signature, normalizes event, and processes state lifecycle atomically.
    """
    provider = get_payment_provider()
    raw_body = await request.body()
    headers = dict(request.headers)

    # Signature / authenticity validation
    is_valid = await provider.verify_webhook_signature(headers, raw_body)
    if not is_valid:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Normalize incoming gateway event
    event = provider.normalize_webhook_payload(headers=headers, payload=payload)

    if event.provider == PaymentProvider.MOCK:
        check_mock_gateway_allowed()

    try:
        result = process_payment_event(db=db, event=event)
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except InvalidPaymentTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/mock-simulate")
async def mock_simulate_payment(request: Request, db: Session = Depends(get_db)):
    """
    Development-only simulation endpoint used exclusively by MockCheckoutPage.
    Strictly blocked in production environments. Passes directly through process_payment_event.
    """
    check_mock_gateway_allowed()

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    headers = dict(request.headers)
    event = MockPaymentProvider().normalize_webhook_payload(headers=headers, payload=payload)

    try:
        result = process_payment_event(db=db, event=event)
        return result
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except InvalidPaymentTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))



@router.get("/verify/{transaction_id}")
def verify_transaction_status(transaction_id: str, db: Session = Depends(get_db)):
    """
    Retrieves authoritative status for mock checkout polling and confirmation.
    Supports flexible lookup by transaction ID, payment UUID, order ID, or order number.
    """
    check_mock_gateway_allowed()

    # 1. Direct transaction_id lookup
    payment = db.query(Payment).filter(Payment.transaction_id == transaction_id).first()

    # 2. Fallback: Payment UUID lookup
    if not payment:
        payment = db.query(Payment).filter(Payment.id == transaction_id).first()

    # 3. Fallback: Order ID lookup
    if not payment:
        payment = db.query(Payment).filter(Payment.order_id == transaction_id).order_by(Payment.created_at.desc()).first()

    # 4. Fallback: Order Number lookup (e.g. #PP1234)
    if not payment:
        order_match = db.query(Order).filter(
            (Order.order_number == transaction_id) | (Order.id == transaction_id)
        ).first()
        if order_match:
            payment = db.query(Payment).filter(Payment.order_id == order_match.id).order_by(Payment.created_at.desc()).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Transaction or order payment record not found")

    order = db.query(Order).filter(Order.id == payment.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Associated order not found")

    return {
        "payment_id": payment.id,
        "transaction_id": payment.transaction_id or payment.id,
        "order_id": order.id,
        "order_number": order.order_number,
        "customer_name": order.customer_name,
        "order_type": order.order_type,
        "amount": payment.amount,
        "currency": payment.currency,
        "payment_status": payment.status,
        "order_status": order.status,
        "created_at": payment.created_at.isoformat() if hasattr(payment.created_at, "isoformat") else str(payment.created_at) if payment.created_at else None
    }


@router.get("/order/{order_id}", response_model=List[PaymentResponse])
def get_order_payments(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves all payment transactions and audit ledger for an order."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Super Admin -> Full Access
    if current_user.role == UserRole.SUPER_ADMIN:
        return order.payments

    # Branch Admin -> Assigned branch isolation
    if current_user.role == UserRole.BRANCH_ADMIN:
        assigned_ids = [bu.branch_id for bu in current_user.branch_assignments]
        if order.branch_id not in assigned_ids:
            raise HTTPException(status_code=403, detail="Access denied to payment records outside assigned branch")
        return order.payments

    # Customer -> Must own the order
    is_owner = (
        (order.customer_id and order.customer_id == current_user.id) or
        (order.customer_email and order.customer_email.strip().lower() == current_user.email.strip().lower())
    )
    if not is_owner:
        raise HTTPException(status_code=403, detail="Access denied to payment records for this order")

    return order.payments


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment_details(
    payment_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Fetches details of a specific payment transaction."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")

    order = payment.order

    # Super Admin -> Full Access
    if current_user.role == UserRole.SUPER_ADMIN:
        return payment

    # Branch Admin -> Assigned branch isolation
    if current_user.role == UserRole.BRANCH_ADMIN:
        if order:
            assigned_ids = [bu.branch_id for bu in current_user.branch_assignments]
            if order.branch_id not in assigned_ids:
                raise HTTPException(status_code=403, detail="Access denied to payment outside assigned branch")
        return payment

    # Customer -> Must own the associated order
    if order:
        is_owner = (
            (order.customer_id and order.customer_id == current_user.id) or
            (order.customer_email and order.customer_email.strip().lower() == current_user.email.strip().lower())
        )
        if not is_owner:
            raise HTTPException(status_code=403, detail="Access denied to this payment record")

    return payment


@router.post("/{payment_id}/refund", response_model=PaymentResponse)
def refund_payment(
    payment_id: str,
    request: PaymentRefundRequest,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Processes a full or partial refund for a completed payment (Super Admin only)."""
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")

    try:
        updated = process_payment_refund(
            db=db,
            payment=payment,
            refund_amount=request.amount,
            reason=request.reason
        )
        return updated
    except InvalidPaymentTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

