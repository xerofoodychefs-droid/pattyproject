import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base


class PaymentStatus:
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    CAPTURED = "CAPTURED"
    PAID = "PAID"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"
    REFUNDED = "REFUNDED"


class PaymentProvider:
    MOCK = "MOCK"
    SQUARE = "SQUARE"
    STRIPE = "STRIPE"
    RAZORPAY = "RAZORPAY"
    ADYEN = "ADYEN"
    PAYPAL = "PAYPAL"
    CLIENT_GATEWAY = "CLIENT_GATEWAY"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(50), nullable=False, default=PaymentProvider.MOCK)
    transaction_id = Column(String(255), nullable=True, index=True)
    idempotency_key = Column(String(255), nullable=True, unique=True, index=True)
    
    amount = Column(Float, nullable=False, default=0.0)
    currency = Column(String(10), nullable=False, default="GBP")
    status = Column(String(50), nullable=False, default=PaymentStatus.PENDING)
    payment_method_type = Column(String(50), nullable=True, default="CARD")  # CARD, APPLE_PAY, GOOGLE_PAY
    
    raw_response = Column(JSON, nullable=True)
    error_code = Column(String(100), nullable=True)
    error_message = Column(String(500), nullable=True)
    refunded_amount = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    order = relationship("Order", back_populates="payments")
    events = relationship("PaymentEvent", back_populates="payment", cascade="all, delete-orphan")


class PaymentEvent(Base):
    __tablename__ = "payment_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    gateway_event_id = Column(String(255), unique=True, index=True, nullable=False)
    payment_id = Column(String(36), ForeignKey("payments.id", ondelete="SET NULL"), nullable=True, index=True)
    order_id = Column(String(36), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    provider = Column(String(50), nullable=False, default=PaymentProvider.MOCK)
    provider_reference = Column(String(255), nullable=True, index=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSON, nullable=True)
    processing_status = Column(String(50), nullable=False, default="PROCESSED")  # PROCESSED, FAILED, IGNORED, DUPLICATE
    error_message = Column(String(500), nullable=True)
    
    received_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    payment = relationship("Payment", back_populates="events")
    order = relationship("Order")

