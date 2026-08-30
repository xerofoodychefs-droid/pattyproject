import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, Float, Integer, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base

class Category(Base):
    __tablename__ = "categories"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)  # Burgers, Chicken, Sides, Extras, Dips, Drinks
    slug = Column(String(100), unique=True, index=True, nullable=False)
    icon = Column(String(50), nullable=True)
    display_order = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)

    products = relationship("Product", back_populates="category")

class Product(Base):
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    category_id = Column(String(36), ForeignKey("categories.id"), nullable=False)
    name = Column(String(255), nullable=False)
    sku = Column(String(50), unique=True, index=True, nullable=False)
    short_description = Column(String(500), nullable=True)
    full_description = Column(String(2000), nullable=True)
    allergens = Column(String(500), nullable=True)
    ingredients = Column(String(500), nullable=True)  # Removable ingredients list
    image_url = Column(String(500), nullable=True)
    images = Column(JSON, nullable=True)  # List of preview photo URLs
    base_price = Column(Float, nullable=False)  # e.g. 8.95
    compare_at_price = Column(Float, nullable=True)
    rating = Column(Float, default=4.7)
    reviews_count = Column(Integer, default=120)
    is_bestseller = Column(Boolean, default=False)
    has_tax = Column(Boolean, default=True)
    has_service_charge = Column(Boolean, default=False)
    vat_category = Column(String(50), default="STANDARD_20")  # STANDARD_20, REDUCED_5, ZERO_0
    is_active = Column(Boolean, default=True)
    is_out_of_stock = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    category = relationship("Category", back_populates="products")
    modifiers = relationship("ProductModifier", back_populates="product", cascade="all, delete-orphan")
    choice_groups = relationship("ProductChoiceGroup", back_populates="product", cascade="all, delete-orphan", order_by="ProductChoiceGroup.display_order.asc()")
    inventory_records = relationship("Inventory", back_populates="product", cascade="all, delete-orphan")

class ProductChoiceGroup(Base):
    __tablename__ = "product_choice_groups"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(String(36), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(150), nullable=False)
    min_selections = Column(Integer, nullable=False, default=1)
    max_selections = Column(Integer, nullable=False, default=1)
    is_required = Column(Boolean, nullable=False, default=True)
    display_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    product = relationship("Product", back_populates="choice_groups")
    options = relationship("ProductChoiceOption", back_populates="group", cascade="all, delete-orphan", order_by="ProductChoiceOption.display_order.asc()")

class ProductChoiceOption(Base):
    __tablename__ = "product_choice_options"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_id = Column(String(36), ForeignKey("product_choice_groups.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(150), nullable=False)
    price_delta = Column(Float, nullable=False, default=0.0)
    is_active = Column(Boolean, nullable=False, default=True)
    display_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    group = relationship("ProductChoiceGroup", back_populates="options")

class ProductModifier(Base):
    __tablename__ = "product_modifiers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False)
    name = Column(String(100), nullable=False)  # e.g. Extra Beef Patty, Bacon, Jalapeños, Extra Cheese
    price = Column(Float, nullable=False, default=0.0)  # e.g. 2.00, 1.50
    is_required = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    product = relationship("Product", back_populates="modifiers")

class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    branch_id = Column(String(36), ForeignKey("branches.id"), nullable=False)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False)
    stock_quantity = Column(Integer, default=100)
    low_stock_threshold = Column(Integer, default=10)
    is_available = Column(Boolean, default=True)

    branch = relationship("Branch", back_populates="inventory_items")
    product = relationship("Product", back_populates="inventory_records")
