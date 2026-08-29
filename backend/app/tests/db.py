import sys
import pathlib
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure backend root is on sys.path
backend_root = pathlib.Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.main import app
from app.core.database import Base, get_db
import app.models as _all_models_registered
from app.models import (
    User, UserRole, CustomerAddress, UserAuthIdentity, AuthProvider, AuthConsumedJti, AuthSession,
    Branch, BranchUser,
    Category, Product, ProductModifier,
    Order, OrderItem, OrderStatusHistory, OrderStatus, OrderType,
    Payment, PaymentStatus, PaymentProvider,
    LoyaltyAccount, LoyaltyTransaction, LoyaltyReward,
    Coupon
)
from app.core.security import get_password_hash

import threading

# Single shared in-memory SQLite database with thread-safe session lock
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
_db_lock = threading.RLock()


def override_get_db():
    with _db_lock:
        db = TestingSessionLocal()
    try:
        yield db
    finally:
        with _db_lock:
            db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def reset_test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Clear all existing tables
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()

    # Seed Super Admin
    admin_user = User(
        id="user-superadmin-001",
        email="admin@pattyproject.co.uk",
        password_hash=get_password_hash("Admin123!"),
        full_name="Super Admin",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        email_verified=True
    )

    # Seed Camden branch
    camden = Branch(
        id="branch-camden-001",
        code="LC",
        name="London - Camden",
        address_line1="45 Camden High Street",
        postcode="NW1 7JE",
        city="London",
        latitude=51.5360,
        longitude=-0.1420,
        phone="+44 20 7417 5211",
        delivery_enabled=True,
        collection_enabled=True,
        ordering_enabled=True,
        delivery_radius_miles=2.0,
        is_active=True
    )

    # Seed Westfield branch
    westfield = Branch(
        id="branch-westfield-002",
        code="LW",
        name="London - Westfield",
        address_line1="Ariel Way, Shepherd's Bush",
        postcode="W12 7GF",
        city="London",
        latitude=51.5074,
        longitude=-0.2217,
        phone="+44 20 8749 8899",
        delivery_enabled=True,
        collection_enabled=True,
        ordering_enabled=True,
        delivery_radius_miles=2.0,
        is_active=True
    )

    # Seed Category
    cat = Category(
        id="cat-burgers",
        name="Burgers",
        slug="burgers",
        icon="hamburger",
        display_order=1
    )

    # Seed Product
    prod = Product(
        id="prod-mc-project",
        category_id="cat-burgers",
        name="Mc Project",
        sku="BURG001",
        base_price=16.00,
        rating=4.8,
        reviews_count=100,
        is_active=True
    )

    db.add_all([admin_user, camden, westfield, cat, prod])
    db.commit()
    db.close()
