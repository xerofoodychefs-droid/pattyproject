import pytest
import urllib.parse
from app.tests.db import client, reset_test_db, TestingSessionLocal
from app.models.order import Order, OrderStatus, OrderType, PaymentStatus
from app.models.user import User, UserRole
from app.core.security import get_password_hash, create_access_token

@pytest.fixture(autouse=True)
def setup_test():
    reset_test_db()
    db = TestingSessionLocal()

    # Create customer user
    customer = User(
        id="user-cust-01",
        email="customer.alice@example.com",
        password_hash=get_password_hash("password123"),
        full_name="Alice Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=True
    )
    db.add(customer)

    # Create another customer user
    other_customer = User(
        id="user-cust-02",
        email="customer.bob@example.com",
        password_hash=get_password_hash("password123"),
        full_name="Bob Intruder",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=True
    )
    db.add(other_customer)

    # Create Guest Order
    guest_order = Order(
        id="order-uuid-guest-1234",
        order_number="#PP3854",
        customer_name="Guest Customer",
        customer_email="vaisaakhvinodnair@gmail.com",
        customer_phone="+44 7123456789",
        branch_id="branch-camden-001",
        order_type=OrderType.COLLECTION,
        status=OrderStatus.INCOMING,
        payment_status=PaymentStatus.PAID,
        payment_method="GOOGLE_PAY",
        subtotal=2.0,
        delivery_fee=0.0,
        service_fee=0.0,
        discount_amount=0.0,
        vat_amount=0.33,
        total_amount=2.0
    )
    db.add(guest_order)

    # Create Registered Customer Order
    registered_order = Order(
        id="order-uuid-cust-5678",
        order_number="#PP9999",
        customer_id="user-cust-01",
        customer_name="Alice Customer",
        customer_email="customer.alice@example.com",
        customer_phone="+44 7987654321",
        branch_id="branch-camden-001",
        order_type=OrderType.COLLECTION,
        status=OrderStatus.INCOMING,
        payment_status=PaymentStatus.PAID,
        payment_method="CARD",
        subtotal=15.0,
        delivery_fee=0.0,
        service_fee=0.0,
        discount_amount=0.0,
        vat_amount=2.5,
        total_amount=15.0
    )
    db.add(registered_order)

    db.commit()
    db.close()


def test_guest_order_lookup_by_uuid():
    """Guest customer can retrieve order using canonical UUID and email parameter."""
    res = client.get("/api/v1/orders/order-uuid-guest-1234?email=vaisaakhvinodnair@gmail.com")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "order-uuid-guest-1234"
    assert data["order_number"] == "#PP3854"
    assert data["customer_email"] == "vaisaakhvinodnair@gmail.com"
    assert data["payment_status"] == "PAID"


def test_guest_order_lookup_by_full_order_number():
    """Guest customer can retrieve order using full #PP3854 order number."""
    encoded_num = urllib.parse.quote("#PP3854")
    res = client.get(f"/api/v1/orders/{encoded_num}?email=vaisaakhvinodnair@gmail.com")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "order-uuid-guest-1234"
    assert data["order_number"] == "#PP3854"


def test_guest_order_lookup_by_stripped_order_number():
    """Guest customer can retrieve order using clean PP3854 (without hash prefix)."""
    res = client.get("/api/v1/orders/PP3854?email=vaisaakhvinodnair@gmail.com")
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "order-uuid-guest-1234"
    assert data["order_number"] == "#PP3854"


def test_guest_order_lookup_without_email_fails_securely():
    """Guest order lookup without email parameter is rejected with HTTP 401."""
    res = client.get("/api/v1/orders/order-uuid-guest-1234")
    assert res.status_code == 401


def test_guest_order_lookup_with_wrong_email_fails_securely():
    """Guest order lookup with mismatched email is rejected with HTTP 401."""
    res = client.get("/api/v1/orders/order-uuid-guest-1234?email=wrong@example.com")
    assert res.status_code == 401


def test_authenticated_customer_can_lookup_own_order():
    """Authenticated customer can retrieve their own order without email query param."""
    token = create_access_token(subject="user-cust-01", roles=[UserRole.CUSTOMER])
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/v1/orders/order-uuid-cust-5678", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == "order-uuid-cust-5678"
    assert data["order_number"] == "#PP9999"


def test_authenticated_customer_cannot_lookup_another_users_order():
    """Authenticated customer cannot view another user's order (IDOR protection)."""
    token = create_access_token(subject="user-cust-02", roles=[UserRole.CUSTOMER])
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/v1/orders/order-uuid-cust-5678", headers=headers)
    assert res.status_code == 403


def test_super_admin_can_lookup_any_order():
    """Super admin can view any order directly without email parameter."""
    token = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/api/v1/orders/order-uuid-guest-1234", headers=headers)
    assert res.status_code == 200
    assert res.json()["order_number"] == "#PP3854"
