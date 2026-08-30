import uuid
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base

class OrderStatus:
    INCOMING = "INCOMING"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    PAID = "PAID"
    ACCEPTED = "ACCEPTED"
    PREPARING = "PREPARING"
    READY = "READY"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    READY_FOR_COLLECTION = "READY_FOR_COLLECTION"
    DELIVERED = "DELIVERED"
    COLLECTED = "COLLECTED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    REFUND_PENDING = "REFUND_PENDING"
    REFUNDED = "REFUNDED"


class OrderType:
    DELIVERY = "DELIVERY"
    COLLECTION = "COLLECTION"

class PaymentStatus:
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"

class Order(Base):
    __tablename__ = "orders"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_number = Column(String(50), unique=True, index=True, nullable=False)  # e.g. #PP1258
    customer_id = Column(String(36), ForeignKey("users.id"), nullable=True)  # Nullable for guest checkout
    customer_name = Column(String(255), nullable=False)
    customer_email = Column(String(255), nullable=False)
    customer_phone = Column(String(50), nullable=False)
    
    branch_id = Column(String(36), ForeignKey("branches.id"), nullable=False)
    order_type = Column(String(50), nullable=False, default=OrderType.DELIVERY)
    status = Column(String(50), nullable=False, default=OrderStatus.PENDING_PAYMENT)
    
    delivery_address = Column(JSON, nullable=True)  # Address JSON structure
    collection_slot_time = Column(DateTime, nullable=True)
    delivery_instructions = Column(String(500), nullable=True)
    
    subtotal = Column(Float, nullable=False, default=0.0)
    delivery_fee = Column(Float, nullable=False, default=0.0)
    service_fee = Column(Float, nullable=False, default=0.0)
    discount_amount = Column(Float, nullable=False, default=0.0)
    vat_amount = Column(Float, nullable=False, default=0.0)
    total_amount = Column(Float, nullable=False, default=0.0)
    
    payment_method = Column(String(100), default="Client Payment Gateway")
    payment_status = Column(String(50), default=PaymentStatus.PENDING)
    payment_transaction_id = Column(String(255), nullable=True)
    
    coupon_code = Column(String(50), nullable=True)
    points_earned = Column(Integer, default=0)
    points_redeemed = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    customer = relationship("User", back_populates="orders")
    branch = relationship("Branch", back_populates="orders")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    status_history = relationship("OrderStatusHistory", back_populates="order", cascade="all, delete-orphan")
    print_jobs = relationship("PrintJob", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order", cascade="all, delete-orphan", order_by="Payment.created_at.desc()")

    @property
    def net_amount(self) -> float:
        """Deterministic extracted net amount: (subtotal - discount) - vat_amount."""
        gross = max(0.0, round(float(self.subtotal or 0.0) - float(self.discount_amount or 0.0), 2))
        return round(gross - float(self.vat_amount or 0.0), 2)

class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey("orders.id"), nullable=False)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False)
    product_name = Column(String(255), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)
    selected_modifiers = Column(JSON, nullable=True)  # List of selected add-on dicts

    order = relationship("Order", back_populates="items")
    product = relationship("Product", foreign_keys=[product_id], lazy="select")

    @property
    def image_url(self) -> Optional[str]:
        return self.product.image_url if self.product else None

class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    order_id = Column(String(36), ForeignKey("orders.id"), nullable=False)
    user_id = Column(String(36), nullable=True)  # Actor ID who triggered state change
    from_status = Column(String(50), nullable=True)
    to_status = Column(String(50), nullable=False)
    notes = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    order = relationship("Order", back_populates="status_history")
