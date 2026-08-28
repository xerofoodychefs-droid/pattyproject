import uuid
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Set
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from dataclasses import dataclass
from app.core.config import settings
from app.models.payment import Payment, PaymentStatus, PaymentProvider, PaymentEvent
from app.models.order import Order, OrderStatus, OrderStatusHistory
from app.models.loyalty import LoyaltyAccount, LoyaltyTransaction
from app.models.user import User
from app.services.loyalty_service import (
    award_order_loyalty_points as svc_award_loyalty,
    reverse_order_loyalty_points,
    restore_redeemed_loyalty_points
)

logger = logging.getLogger("pattyproject.payment")


@dataclass
class NormalizedPaymentEvent:
    event_id: str
    provider: str
    event_type: str  # SUCCESS, FAILED, CANCELLED, PENDING, REFUNDED
    order_id: Optional[str] = None
    transaction_id: Optional[str] = None
    amount: Optional[float] = None
    currency: str = "GBP"
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None


# Canonical Payment State Machine Definitions
VALID_PAYMENT_TRANSITIONS: Dict[str, Set[str]] = {
    PaymentStatus.PENDING: {
        PaymentStatus.AUTHORIZED,
        PaymentStatus.CAPTURED,
        PaymentStatus.PAID,
        PaymentStatus.FAILED,
        PaymentStatus.CANCELLED
    },
    PaymentStatus.AUTHORIZED: {
        PaymentStatus.CAPTURED,
        PaymentStatus.PAID,
        PaymentStatus.CANCELLED,
        PaymentStatus.FAILED
    },
    PaymentStatus.CAPTURED: {
        PaymentStatus.PARTIALLY_REFUNDED,
        PaymentStatus.REFUNDED
    },
    PaymentStatus.PAID: {
        PaymentStatus.PARTIALLY_REFUNDED,
        PaymentStatus.REFUNDED
    },
    PaymentStatus.PARTIALLY_REFUNDED: {
        PaymentStatus.PARTIALLY_REFUNDED,
        PaymentStatus.REFUNDED
    },
    PaymentStatus.FAILED: set(),       # Terminal state
    PaymentStatus.CANCELLED: set(),    # Terminal state
    PaymentStatus.REFUNDED: set(),     # Terminal state
}


class InvalidPaymentTransitionError(Exception):
    def __init__(self, current_status: str, target_status: str):
        super().__init__(
            f"Illegal payment status transition from '{current_status}' to '{target_status}'."
        )
        self.current_status = current_status
        self.target_status = target_status


def validate_payment_transition(current_status: str, target_status: str) -> bool:
    """Validates if status change is valid according to canonical lifecycle."""
    if current_status == target_status:
        return True  # Idempotent re-affirmation is allowed
    allowed = VALID_PAYMENT_TRANSITIONS.get(current_status, set())
    return target_status in allowed


class BasePaymentProvider(ABC):
    @abstractmethod
    async def create_payment_session(
        self,
        order_id: str,
        amount: float,
        currency: str = "GBP",
        customer_info: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        source_id: Optional[str] = None,
        order_number: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Initializes payment session & returns checkout token or redirect URL."""
        pass

    @abstractmethod
    async def verify_webhook_signature(self, headers: Dict[str, str], body: bytes, url: Optional[str] = None, **kwargs) -> bool:
        """Validates incoming webhook authenticity."""
        pass

    @abstractmethod
    def normalize_webhook_payload(self, headers: Dict[str, str], payload: Dict[str, Any]) -> NormalizedPaymentEvent:
        """Normalizes provider-specific webhook payload into unified NormalizedPaymentEvent."""
        pass

    @abstractmethod
    async def process_refund(self, transaction_id: str, amount: float) -> Dict[str, Any]:
        """Processes a refund via gateway."""
        pass


class MockPaymentProvider(BasePaymentProvider):
    """
    Built-in pluggable Mock Payment Provider for local development & testing.
    Hardened for provider-neutral event boundaries and development verification.
    """
    async def create_payment_session(
        self,
        order_id: str,
        amount: float,
        currency: str = "GBP",
        customer_info: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        source_id: Optional[str] = None,
        order_number: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        tx_id = f"TXN_{uuid.uuid4().hex[:10].upper()}"
        return {
            "provider": PaymentProvider.MOCK,
            "order_id": order_id,
            "transaction_id": tx_id,
            "idempotency_key": idempotency_key,
            "amount": amount,
            "currency": currency,
            "status": PaymentStatus.PENDING,
            "client_secret": f"sec_mock_{tx_id}",
            "payment_url": f"/mock-checkout/{tx_id}"
        }

    async def verify_webhook_signature(self, headers: Dict[str, str], body: bytes, url: Optional[str] = None, **kwargs) -> bool:
        # Development Mock signature verification check
        sig = headers.get("x-mock-signature") or headers.get("X-Mock-Signature")
        if sig == "invalid_signature":
            return False
        return True

    def normalize_webhook_payload(self, headers: Dict[str, str], payload: Dict[str, Any]) -> NormalizedPaymentEvent:
        event_id = payload.get("event_id") or headers.get("x-event-id") or headers.get("X-Event-Id")
        if not event_id:
            tx = payload.get("transaction_id") or uuid.uuid4().hex[:8]
            event_id = f"evt_mock_{tx}"

        status_raw = str(payload.get("status", "PAID")).upper()
        if status_raw in ["SUCCESS", "PAID", "CAPTURED"]:
            event_type = "SUCCESS"
        elif status_raw in ["FAILED", "DECLINED"]:
            event_type = "FAILED"
        elif status_raw in ["CANCELLED", "EXPIRED"]:
            event_type = "CANCELLED"
        elif status_raw in ["REFUNDED"]:
            event_type = "REFUNDED"
        else:
            event_type = status_raw

        return NormalizedPaymentEvent(
            event_id=event_id,
            provider=PaymentProvider.MOCK,
            event_type=event_type,
            order_id=payload.get("order_id"),
            transaction_id=payload.get("transaction_id"),
            amount=float(payload["amount"]) if payload.get("amount") is not None else None,
            currency=str(payload.get("currency", "GBP")).upper(),
            error_code=payload.get("error_code"),
            error_message=payload.get("error_message"),
            raw_payload=payload
        )

    async def process_refund(self, transaction_id: str, amount: float) -> Dict[str, Any]:
        return {
            "status": "SUCCESS",
            "refund_id": f"ref_{uuid.uuid4().hex[:8]}",
            "amount": amount,
            "transaction_id": transaction_id
        }


def get_payment_provider() -> BasePaymentProvider:
    """Dynamically resolves and returns the configured payment provider."""
    provider_name = (settings.PAYMENT_PROVIDER or "").lower()
    if provider_name == "square" or (settings.is_production and settings.SQUARE_ACCESS_TOKEN):
        try:
            from app.services.square_service import SquarePaymentProvider
            return SquarePaymentProvider()
        except Exception as e:
            logger.error(f"Failed to initialize SquarePaymentProvider: {e}")
    return MockPaymentProvider()


# Active Provider instance
payment_provider: BasePaymentProvider = get_payment_provider()


# Payment Ledger & Service Operations
def get_or_create_payment_for_order(
    db: Session,
    order: Order,
    provider: str = PaymentProvider.MOCK,
    idempotency_key: Optional[str] = None,
    payment_method_type: str = "CARD"
) -> Payment:
    """
    Idempotently returns an existing active payment or creates a new Payment record.
    """
    if order.status == OrderStatus.CANCELLED:
        raise ValueError("Cannot create or retrieve payment for a cancelled order.")

    if idempotency_key:
        existing = db.query(Payment).filter(Payment.idempotency_key == idempotency_key).first()
        if existing:
            return existing

    # Look for an existing pending payment for this order
    existing_pending = db.query(Payment).filter(
        Payment.order_id == order.id,
        Payment.status.in_([PaymentStatus.PENDING, PaymentStatus.AUTHORIZED])
    ).first()

    if existing_pending:
        if idempotency_key and not existing_pending.idempotency_key:
            existing_pending.idempotency_key = idempotency_key
            db.commit()
            db.refresh(existing_pending)
        return existing_pending

    stable_key = idempotency_key or f"sq_idemp_{order.id}"
    existing_key = db.query(Payment).filter(Payment.idempotency_key == stable_key).first()
    if existing_key:
        return existing_key

    payment = Payment(
        order_id=order.id,
        provider=provider,
        idempotency_key=stable_key,
        amount=order.total_amount,
        currency="GBP",
        status=PaymentStatus.PENDING,
        payment_method_type=payment_method_type,
        refunded_amount=0.0
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


def process_payment_event(db: Session, event: NormalizedPaymentEvent) -> Dict[str, Any]:
    """
    Hardened, atomic payment event verification and lifecycle processor.
    Guarantees event-level idempotency, exact minor-unit matching, strict GBP currency enforcement,
    and safe atomic state transitions.
    """
    # 1. Event Identity & Event-Level Idempotency Check
    existing_event = db.query(PaymentEvent).filter(
        PaymentEvent.gateway_event_id == event.event_id
    ).first()

    if existing_event and existing_event.processing_status == "PROCESSED":
        logger.info(
            f"[PAYMENT_IDEMPOTENT] Duplicate event received: event_id={event.event_id}, payment_id={existing_event.payment_id}"
        )
        existing_pm = db.query(Payment).filter(Payment.id == existing_event.payment_id).first() if existing_event.payment_id else None
        existing_ord = db.query(Order).filter(Order.id == existing_event.order_id).first() if existing_event.order_id else None
        return {
            "status": "SUCCESS",
            "message": "Duplicate event ignored (idempotent)",
            "event_id": event.event_id,
            "payment_id": existing_event.payment_id,
            "payment_status": existing_pm.status if existing_pm else PaymentStatus.PAID,
            "order_id": existing_event.order_id,
            "order_status": existing_ord.status if existing_ord else OrderStatus.INCOMING,
            "idempotent": True
        }


    # 2. Payment & Order Lookup
    payment = None
    if event.transaction_id:
        payment = db.query(Payment).filter(Payment.transaction_id == event.transaction_id).first()
    if not payment and event.order_id:
        payment = db.query(Payment).filter(
            Payment.order_id == event.order_id
        ).order_by(Payment.created_at.desc()).first()

    if not payment and event.order_id:
        order_record = db.query(Order).filter(Order.id == event.order_id).first()
        if order_record:
            payment = get_or_create_payment_for_order(db=db, order=order_record, provider=event.provider)

    if not payment:
        raise ValueError(f"No matching payment record found for event_id={event.event_id}")

    order = db.query(Order).filter(Order.id == payment.order_id).first()
    if not order:
        raise ValueError(f"Associated order not found for payment {payment.id}")

    # 3. Order Ownership & Association Verification
    if event.order_id and payment.order_id != event.order_id:
        raise PermissionError("Payment does not belong to the specified order.")

    # 4. Cancelled Order Protection
    if order.status == OrderStatus.CANCELLED:
        failed_event = PaymentEvent(
            gateway_event_id=event.event_id,
            payment_id=payment.id,
            order_id=order.id,
            provider=event.provider,
            provider_reference=payment.transaction_id,
            event_type=event.event_type,
            payload=event.raw_payload,
            processing_status="REJECTED_CANCELLED",
            error_message="Payment rejected: Order is cancelled"
        )
        db.add(failed_event)
        db.commit()
        raise ValueError("Cannot process payment for a cancelled order.")

    # 5. Currency Verification (Strictly GBP)
    if event.currency and event.currency.upper() != "GBP":
        raise ValueError(f"Invalid currency '{event.currency}'. Only GBP is accepted.")
    if payment.currency and payment.currency.upper() != "GBP":
        raise ValueError(f"Invalid payment currency '{payment.currency}'. Only GBP is accepted.")

    # 6. Exact Minor-Unit (Pence) Amount Verification
    if event.amount is not None:
        event_pence = int(round(float(event.amount) * 100))
        payment_pence = int(round(float(payment.amount) * 100))
        order_pence = int(round(float(order.total_amount) * 100))

        if event_pence != payment_pence or event_pence != order_pence:
            raise ValueError(
                f"Amount mismatch. Provider amount £{event.amount:.2f} does not match authoritative order amount £{order.total_amount:.2f}."
            )

    # 7. Map Target Status
    target_status = PaymentStatus.PAID
    if event.event_type in ["SUCCESS", "PAID", "CAPTURED"]:
        target_status = PaymentStatus.PAID
    elif event.event_type in ["FAILED", "DECLINED"]:
        target_status = PaymentStatus.FAILED
    elif event.event_type in ["CANCELLED", "EXPIRED"]:
        target_status = PaymentStatus.CANCELLED
    elif event.event_type in ["PENDING"]:
        target_status = PaymentStatus.PENDING
    elif event.event_type in ["REFUNDED"]:
        target_status = PaymentStatus.REFUNDED

    # 8. Idempotent Target Status Verification
    if payment.status == target_status:
        # Record processed event to protect subsequent identical deliveries
        evt_record = PaymentEvent(
            gateway_event_id=event.event_id,
            payment_id=payment.id,
            order_id=order.id,
            provider=event.provider,
            provider_reference=payment.transaction_id,
            event_type=event.event_type,
            payload=event.raw_payload,
            processing_status="PROCESSED"
        )
        db.add(evt_record)
        db.commit()
        return {
            "status": "SUCCESS",
            "message": "Payment state already synchronized (idempotent)",
            "payment_id": payment.id,
            "payment_status": payment.status,
            "order_status": order.status,
            "event_id": event.event_id
        }

    # 9. State Machine Transition Validation
    if not validate_payment_transition(payment.status, target_status):
        raise InvalidPaymentTransitionError(payment.status, target_status)

    # 10. Atomic Execution of State Transition, Order Sync, Loyalty Award & Event Record
    payment.status = target_status
    if event.transaction_id:
        payment.transaction_id = event.transaction_id
    if event.raw_payload:
        payment.raw_response = event.raw_payload
    if event.error_code:
        payment.error_code = event.error_code
    if event.error_message:
        payment.error_message = event.error_message

    became_incoming = False
    if target_status in [PaymentStatus.PAID, PaymentStatus.CAPTURED]:
        order.payment_status = PaymentStatus.PAID
        if payment.transaction_id:
            order.payment_transaction_id = payment.transaction_id

        if order.status in [OrderStatus.PENDING_PAYMENT]:
            order.status = OrderStatus.INCOMING
            became_incoming = True
            history = OrderStatusHistory(
                order_id=order.id,
                from_status=OrderStatus.PENDING_PAYMENT,
                to_status=OrderStatus.INCOMING,
                notes=f"Payment {payment.transaction_id or payment.id} confirmed via {payment.provider}"
            )
            db.add(history)

        award_order_loyalty_points(db, order)

    elif target_status == PaymentStatus.FAILED:
        order.payment_status = PaymentStatus.FAILED
        history = OrderStatusHistory(
            order_id=order.id,
            from_status=order.status,
            to_status=order.status,
            notes=f"Payment failed: {event.error_message or event.error_code or 'Unknown error'}"
        )
        db.add(history)

    elif target_status == PaymentStatus.CANCELLED:
        order.payment_status = PaymentStatus.CANCELLED
        history = OrderStatusHistory(
            order_id=order.id,
            from_status=order.status,
            to_status=order.status,
            notes="Payment cancelled by user/gateway"
        )
        db.add(history)

    # Record PaymentEvent
    event_entry = PaymentEvent(
        gateway_event_id=event.event_id,
        payment_id=payment.id,
        order_id=order.id,
        provider=event.provider,
        provider_reference=payment.transaction_id,
        event_type=event.event_type,
        payload=event.raw_payload,
        processing_status="PROCESSED"
    )
    db.add(event_entry)

    db.commit()
    db.refresh(payment)
    db.refresh(order)

    if became_incoming:
        try:
            from app.core.websocket_manager import manager, format_order_payload
            manager.sync_broadcast_order_event(
                event_type="ORDER_INCOMING",
                order_data=format_order_payload(order),
                branch_id=str(order.branch_id)
            )
        except Exception as e:
            logger.warning(f"[WS_BROADCAST_FAILED] Webhook failed to broadcast ORDER_INCOMING: {e}")

    # Sanitized Security Logging (Zero Secrets/Tokens)
    logger.info(
        f"[PAYMENT_PROCESSED] order_id={order.id}, payment_id={payment.id}, event_id={event.event_id}, status={payment.status}, amount=£{payment.amount:.2f}"
    )

    return {
        "status": "SUCCESS",
        "message": f"Payment successfully transitioned to {payment.status}",
        "payment_id": payment.id,
        "payment_status": payment.status,
        "order_id": order.id,
        "order_number": order.order_number,
        "order_status": order.status,
        "event_id": event.event_id
    }


def transition_payment_status(
    db: Session,
    payment: Payment,
    target_status: str,
    transaction_id: Optional[str] = None,
    raw_response: Optional[Dict[str, Any]] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None
) -> Payment:
    """
    Enforces valid state transition on Payment, updates Order state & awards loyalty idempotently.
    """
    target_status = target_status.upper()
    current_status = payment.status.upper()

    if target_status == "SUCCESS":
        target_status = PaymentStatus.PAID

    order = db.query(Order).filter(Order.id == payment.order_id).first()
    if order and order.status == OrderStatus.CANCELLED:
        raise ValueError("Cannot process or transition payment for a cancelled order.")

    if not validate_payment_transition(current_status, target_status):
        raise InvalidPaymentTransitionError(current_status, target_status)

    payment.status = target_status
    if transaction_id:
        payment.transaction_id = transaction_id
    if raw_response:
        payment.raw_response = raw_response
    if error_code:
        payment.error_code = error_code
    if error_message:
        payment.error_message = error_message

    if order:
        if target_status in [PaymentStatus.PAID, PaymentStatus.CAPTURED]:
            order.payment_status = PaymentStatus.PAID
            if payment.transaction_id:
                order.payment_transaction_id = payment.transaction_id

            if order.status in [OrderStatus.PENDING_PAYMENT]:
                order.status = OrderStatus.INCOMING
                history = OrderStatusHistory(
                    order_id=order.id,
                    from_status=OrderStatus.PENDING_PAYMENT,
                    to_status=OrderStatus.INCOMING,
                    notes=f"Payment {payment.transaction_id or payment.id} confirmed via {payment.provider}"
                )
                db.add(history)

            award_order_loyalty_points(db, order)

        elif target_status == PaymentStatus.FAILED:
            order.payment_status = PaymentStatus.FAILED
            history = OrderStatusHistory(
                order_id=order.id,
                from_status=order.status,
                to_status=order.status,
                notes=f"Payment failed: {error_message or error_code or 'Unknown error'}"
            )
            db.add(history)

        elif target_status in [PaymentStatus.REFUNDED, PaymentStatus.PARTIALLY_REFUNDED]:
            if target_status == PaymentStatus.REFUNDED:
                order.payment_status = PaymentStatus.REFUNDED
                order.status = OrderStatus.REFUNDED
                history = OrderStatusHistory(
                    order_id=order.id,
                    from_status=order.status,
                    to_status=OrderStatus.REFUNDED,
                    notes=f"Payment fully refunded: {raw_response.get('reason') if raw_response else 'Refund processed'}"
                )
                db.add(history)
            
            # Loyalty Refund / Cancellation Reversals
            ref_amt = raw_response.get("refund_amount") if raw_response else None
            reason_txt = raw_response.get("reason") if raw_response else "Payment refund"
            reverse_order_loyalty_points(db=db, order=order, refund_amount=ref_amt, reason=reason_txt)
            if target_status == PaymentStatus.REFUNDED:
                restore_redeemed_loyalty_points(db=db, order=order, reason=reason_txt)

    db.commit()
    db.refresh(payment)
    return payment


def process_payment_refund(
    db: Session,
    payment: Payment,
    refund_amount: Optional[float] = None,
    reason: Optional[str] = None
) -> Payment:
    """
    Executes refund validation and updates payment ledger.
    """
    if payment.status not in [PaymentStatus.PAID, PaymentStatus.CAPTURED, PaymentStatus.PARTIALLY_REFUNDED]:
        raise InvalidPaymentTransitionError(payment.status, PaymentStatus.REFUNDED)

    target_refund = refund_amount if refund_amount is not None else (payment.amount - payment.refunded_amount)
    if target_refund <= 0:
        raise ValueError("Refund amount must be greater than zero.")

    new_total_refunded = round(payment.refunded_amount + target_refund, 2)
    if new_total_refunded > round(payment.amount, 2):
        raise ValueError(
            f"Cannot refund £{target_refund:.2f}. Total refunded would exceed original payment amount of £{payment.amount:.2f}."
        )

    payment.refunded_amount = new_total_refunded
    new_status = PaymentStatus.REFUNDED if new_total_refunded >= round(payment.amount, 2) else PaymentStatus.PARTIALLY_REFUNDED

    return transition_payment_status(
        db=db,
        payment=payment,
        target_status=new_status,
        raw_response={"refund_amount": target_refund, "reason": reason or "Customer requested refund"}
    )


def award_order_loyalty_points(db: Session, order: Order) -> None:
    """Awards loyalty points for paid order using authoritative loyalty service."""
    from app.services.loyalty_service import award_order_loyalty_points as svc_award
    svc_award(db=db, order=order)

