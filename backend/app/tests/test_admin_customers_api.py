import pytest
from app.core.security import create_access_token, get_password_hash
from app.models.user import User, UserRole
from app.models.loyalty import LoyaltyAccount
from app.models.order import Order, OrderStatus, OrderType
from app.tests.db import client, reset_test_db, TestingSessionLocal


@pytest.fixture(autouse=True)
def setup_customer_test_data():
    reset_test_db()
    db = TestingSessionLocal()

    # Customer 1: Has 1500 points, 2 orders, verified
    cust1 = User(
        id="usr-cust-01",
        email="customer1@example.com",
        password_hash=get_password_hash("Pass123!"),
        full_name="Alice Brown",
        phone="+44 7111 222333",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=True
    )
    db.add(cust1)
    db.flush()

    loyalty1 = LoyaltyAccount(
        id="loy-01",
        user_id=cust1.id,
        available_points=1500,
        lifetime_points=2500
    )
    db.add(loyalty1)

    order1 = Order(
        id="ord-01",
        order_number="#PP-1001",
        customer_id=cust1.id,
        customer_name=cust1.full_name,
        customer_email=cust1.email,
        customer_phone=cust1.phone,
        branch_id="branch-camden-001",
        order_type=OrderType.DELIVERY,
        status=OrderStatus.DELIVERED,
        subtotal=20.0,
        total_amount=22.5
    )
    order2 = Order(
        id="ord-02",
        order_number="#PP-1002",
        customer_id=cust1.id,
        customer_name=cust1.full_name,
        customer_email=cust1.email,
        customer_phone=cust1.phone,
        branch_id="branch-camden-001",
        order_type=OrderType.COLLECTION,
        status=OrderStatus.COLLECTED,
        subtotal=15.0,
        total_amount=15.0
    )
    db.add(order1)
    db.add(order2)

    # Customer 2: Has 0 points, no loyalty account row, 0 orders, verified
    cust2 = User(
        id="usr-cust-02",
        email="customer2@example.com",
        password_hash=get_password_hash("Pass123!"),
        full_name="Bob Green",
        phone="+44 7444 555666",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=True
    )
    db.add(cust2)

    # Customer 3: Unverified customer (MUST NOT appear in admin customers list)
    cust3_unverified = User(
        id="usr-cust-unverified-03",
        email="unverified.user@example.com",
        password_hash=get_password_hash("Pass123!"),
        full_name="Unverified Charlie",
        phone="+44 7999 111222",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=False
    )
    db.add(cust3_unverified)

    db.commit()
    db.close()


def test_admin_can_list_real_customers():
    """Super Admin can list real customers with accurate loyalty balances and order counts."""
    admin_token = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])
    
    resp = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2

    # Verify Alice Brown
    alice = next((c for c in data if c["email"] == "customer1@example.com"), None)
    assert alice is not None
    assert alice["name"] == "Alice Brown"
    assert alice["phone"] == "+44 7111 222333"
    assert alice["orders"] == 2
    assert alice["points"] == 1500
    assert alice["lifetime_points"] == 2500

    # Verify Bob Green (Zero points, no loyalty row, 0 orders)
    bob = next((c for c in data if c["email"] == "customer2@example.com"), None)
    assert bob is not None
    assert bob["name"] == "Bob Green"
    assert bob["orders"] == 0
    assert bob["points"] == 0


def test_customer_token_forbidden_from_admin_customers_api():
    """Customer token cannot access admin customers endpoint (403 Forbidden)."""
    cust_token = create_access_token(subject="usr-cust-01", roles=[UserRole.CUSTOMER])
    resp = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {cust_token}"})
    assert resp.status_code == 403


def test_unauthenticated_request_rejected_401():
    """Unauthenticated request to admin customers endpoint fails with 401."""
    resp = client.get("/api/v1/customers")
    assert resp.status_code == 401


def test_search_customers_by_name_or_email():
    """Search query filters customers accurately."""
    admin_token = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])

    # Search for "alice"
    resp_alice = client.get("/api/v1/customers?search=alice", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp_alice.status_code == 200
    data_alice = resp_alice.json()
    assert len(data_alice) == 1
    assert data_alice[0]["email"] == "customer1@example.com"

    # Search for "green"
    resp_green = client.get("/api/v1/customers?search=green", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp_green.status_code == 200
    data_green = resp_green.json()
    assert len(data_green) == 1
    assert data_green[0]["email"] == "customer2@example.com"


def test_newly_registered_customer_automatically_appears():
    """When a new customer registers, they appear in admin customers ONLY AFTER OTP verification."""
    admin_token = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])

    # 1. New customer requests registration
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": "new.shopper@example.com",
        "full_name": "New Shopper",
        "phone": "+44 7999 888777",
        "password": "SecurePassword123!"
    })
    assert reg_resp.status_code == 200

    # 2. Before OTP verification: customer MUST NOT appear in Admin Customers list
    list_resp_before = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {admin_token}"})
    assert list_resp_before.status_code == 200
    data_before = list_resp_before.json()
    assert not any(c["email"] == "new.shopper@example.com" for c in data_before)

    # 3. Simulate OTP verification
    from app.services.otp_service import hash_otp
    otp_test = "654321"
    db = TestingSessionLocal()
    try:
        from app.models.verification import EmailVerificationChallenge
        ch = db.query(EmailVerificationChallenge).filter(EmailVerificationChallenge.email == "new.shopper@example.com").first()
        assert ch is not None
        ch.otp_hash = hash_otp(email="new.shopper@example.com", otp=otp_test, salt=ch.salt)
        db.commit()
    finally:
        db.close()

    verify_resp = client.post("/api/v1/auth/verify-email", json={
        "email": "new.shopper@example.com",
        "otp": otp_test
    })
    assert verify_resp.status_code == 200

    # 4. After OTP verification: customer MUST appear in Admin Customers list
    list_resp_after = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {admin_token}"})
    assert list_resp_after.status_code == 200
    data_after = list_resp_after.json()
    
    new_cust = next((c for c in data_after if c["email"] == "new.shopper@example.com"), None)
    assert new_cust is not None
    assert new_cust["name"] == "New Shopper"
    assert new_cust["points"] == 100  # Welcome points
    assert new_cust["orders"] == 0


def test_get_customer_detail_endpoint():
    """Admin can get single customer detail with recent orders."""
    admin_token = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])

    detail_resp = client.get("/api/v1/customers/usr-cust-01", headers={"Authorization": f"Bearer {admin_token}"})
    assert detail_resp.status_code == 200
    data = detail_resp.json()
    assert data["id"] == "usr-cust-01"
    assert data["name"] == "Alice Brown"
    assert data["orders"] == 2
    assert len(data["recent_orders"]) == 2
    assert data["recent_orders"][0]["order_number"] in ["#PP-1001", "#PP-1002"]
