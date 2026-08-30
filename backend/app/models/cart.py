import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, ForeignKey, JSON, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base


class Cart(Base):
    __tablename__ = "carts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    session_id = Column(String(64), nullable=True, index=True)  # Secure guest session identifier
    order_type = Column(String(50), nullable=False, default="COLLECTION")  # DELIVERY or COLLECTION
    branch_id = Column(String(36), ForeignKey("branches.id", ondelete="SET NULL"), nullable=True)
    coupon_code = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="cart")
    branch = relationship("Branch")
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan", order_by="CartItem.created_at.asc()")

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_active_user_cart"),
    )


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cart_id = Column(String(36), ForeignKey("carts.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    selected_modifiers = Column(JSON, nullable=True)  # List of {name, price}
    selected_choices = Column(JSON, nullable=True)    # List of {group_id, group_name, option_id, option_name, price_delta}
    removed_ingredients = Column(JSON, nullable=True) # List of ingredient strings
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    cart = relationship("Cart", back_populates="items")
    product = relationship("Product")
