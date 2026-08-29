import os
import pytest
import uuid
import urllib.parse
from fastapi.testclient import TestClient
from jose import jwt

from app.main import app
from app.core.config import Settings, DEV_FALLBACK_SECRET_KEY
from app.core.security import create_access_token
from app.models.user import User, UserRole
from app.models.order import Order, OrderStatus, OrderType, PaymentStatus
from app.models.payment import Payment, PaymentProvider
from app.models.branch import Branch, BranchUser
from app.tests.db import client, reset_test_db, TestingSessionLocal


@pytest.fixture(autouse=True)
def setup_security_test_data():
    reset_test_db()
    db = TestingSessionLocal()

    # 1. Super Admin
    super_admin = User(
        id="usr-super-admin-01",
        email="superadmin@pattytest.co.uk",
        password_hash="hash_super_admin",
        full_name="Super Administrator",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        email_verified=True
    )

    # 2. Branch Admin (Assigned to Camden Branch only)
    camden_admin = User(
        id="usr-camden-admin-01",
        email="camdenadmin@pattytest.co.uk",
        password_hash="hash_camden_admin",
        full_name="Camden Branch Admin",
        role=UserRole.BRANCH_ADMIN,
        is_active=True,
        email_verified=True
    )

    # 3. Customer A
    user_a = User(
        id="usr-cust-a-01",
        email="usera@pattytest.co.uk",
        password_hash="hash_usera",
        full_name="User Alpha",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=True
    )

    # 4. Customer B
    user_b = User(
        id="usr-cust-b-02",
        email="userb@pattytest.co.uk",
        password_hash="hash_userb",
        full_name="User Beta",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=True
    )

    db.add_all([super_admin, camden_admin, user_a, user_b])
    db.flush()

    # Camden Branch Assignment
    bu_camden = BranchUser(
        user_id=camden_admin.id,
        branch_id="branch-camden-001"
    )
    db.add(bu_camden)

    # Order belonging to Customer A (at Camden branch)
    order_a = Order(
        id="ord-alpha-1001",
        order_number="#PP1001",
        branch_id="branch-camden-001",
        customer_id=user_a.id,
        customer_name=user_a.full_name,
        customer_email=user_a.email,
        customer_phone="+447111111111",
        order_type=OrderType.DELIVERY,
        status=OrderStatus.ACCEPTED,
        subtotal=25.00,
        delivery_fee=0.00,
        service_fee=0.99,
        total_amount=25.99,
        payment_status=PaymentStatus.PAID
    )

    # Order belonging to Customer B (at Westfield branch)
    order_b = Order(
        id="ord-beta-2002",
        order_number="#PP2002",
        branch_id="branch-westfield-002",
        customer_id=user_b.id,
        customer_name=user_b.full_name,
        customer_email=user_b.email,
        customer_phone="+447222222222",
        order_type=OrderType.COLLECTION,
        status=OrderStatus.PREPARING,
        subtotal=18.00,
        delivery_fee=0.00,
        service_fee=0.99,
        total_amount=18.99,
        payment_status=PaymentStatus.PAID
    )

    # Guest Order (no customer_id, only email/phone)
    guest_order = Order(
        id="ord-guest-3003",
        order_number="#PP3003",
        branch_id="branch-camden-001",
        customer_id=None,
        customer_name="Guest Customer",
        customer_email="guest@pattytest.co.uk",
        customer_phone="+447333333333",
        order_type=OrderType.DELIVERY,
        status=OrderStatus.INCOMING,
        subtotal=15.00,
        delivery_fee=0.00,
        service_fee=0.99,
        total_amount=15.99,
        payment_status=PaymentStatus.PAID
    )

    db.add_all([order_a, order_b, guest_order])
    db.flush()

    # Completed Payment for Order A
    payment_a = Payment(
        id="pay-alpha-001",
        order_id=order_a.id,
        provider=PaymentProvider.MOCK,
        transaction_id="TXN_ALPHA_001",
        amount=25.99,
        currency="GBP",
        status=PaymentStatus.PAID,
        payment_method_type="CARD"
    )
    db.add(payment_a)

    db.commit()
    db.close()


def get_token_headers(user_id: str, role: str) -> dict:
    token = create_access_token(subject=user_id, roles=[role])
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# FINDING-1: JWT SECRET_KEY Security & Configuration Tests
# =========================================================================

def test_jwt_production_requires_explicit_strong_secret():
    """In production mode, settings.validate_production_configuration() must raise RuntimeError if SECRET_KEY is missing or weak."""
    orig_env = os.environ.get("ENVIRONMENT")
    orig_secret = os.environ.get("SECRET_KEY")

    try:
        os.environ["ENVIRONMENT"] = "production"
        if "SECRET_KEY" in os.environ:
            del os.environ["SECRET_KEY"]

        test_settings = Settings()
        assert test_settings.is_production is True
        
        with pytest.raises(RuntimeError) as exc:
            test_settings.validate_production_configuration()
        assert "CRITICAL SECURITY CONFIGURATION ERROR" in str(exc.value)

        # Test weak/short secret (< 32 chars)
        os.environ["SECRET_KEY"] = "short_secret_key"
        test_settings_short = Settings()
        with pytest.raises(RuntimeError) as exc_short:
            test_settings_short.validate_production_configuration()
        assert "at least 32 characters long" in str(exc_short.value)

        # Test valid high-entropy 32+ char secret in production
        os.environ["SECRET_KEY"] = "prod_super_secure_jwt_secret_key_2026_uk_enterprise_grade_entropy"
        test_settings_valid = Settings()
        test_settings_valid.validate_production_configuration()  # Must not raise

    finally:
        if orig_env is not None:
            os.environ["ENVIRONMENT"] = orig_env
        else:
            os.environ.pop("ENVIRONMENT", None)
        if orig_secret is not None:
            os.environ["SECRET_KEY"] = orig_secret
        else:
            os.environ.pop("SECRET_KEY", None)


def test_jwt_development_allows_fallback():
    """In development mode, validate_production_configuration does not fail on default secret."""
    test_settings = Settings(ENVIRONMENT="development", SECRET_KEY=DEV_FALLBACK_SECRET_KEY)
    assert test_settings.is_production is False
    test_settings.validate_production_configuration()  # Should not raise


def test_jwt_valid_signature_accepted_and_invalid_rejected():
    """Valid JWT signed with configured key authenticates /auth/me; tampered/wrongly signed JWT returns 401."""
    # Valid token
    valid_token = create_access_token(subject="usr-super-admin-01", roles=["SUPER_ADMIN"])
    resp_valid = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {valid_token}"})
    assert resp_valid.status_code == 200
    assert resp_valid.json()["email"] == "superadmin@pattytest.co.uk"

    # Invalid token signed with attacker key
    fake_token = jwt.encode({"sub": "usr-super-admin-01", "roles": ["SUPER_ADMIN"]}, "ATTACKER_SIGNING_KEY", algorithm="HS256")
    resp_invalid = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {fake_token}"})
    assert resp_invalid.status_code == 401


# =========================================================================
# FINDING-2: Admin Orders Authentication & Role Enforcement Tests
# =========================================================================

def test_admin_orders_unauthenticated_denied_401():
    """Unauthenticated caller calling GET /api/v1/orders must be rejected with 401."""
    resp = client.get("/api/v1/orders")
    assert resp.status_code == 401
    assert "detail" in resp.json()


def test_admin_orders_customer_denied_403():
    """Authenticated normal customer calling GET /api/v1/orders must be rejected with 403 Forbidden."""
    customer_headers = get_token_headers("usr-cust-a-01", "CUSTOMER")
    resp = client.get("/api/v1/orders", headers=customer_headers)
    assert resp.status_code == 403
    assert "Not enough permissions" in resp.json()["detail"]


def test_admin_orders_super_admin_allowed_200():
    """Super Admin can list all orders across branches."""
    admin_headers = get_token_headers("usr-super-admin-01", "SUPER_ADMIN")
    resp = client.get("/api/v1/orders", headers=admin_headers)
    assert resp.status_code == 200
    orders = resp.json()
    assert len(orders) >= 3


def test_admin_orders_branch_admin_isolated_to_assigned_branch():
    """Branch Admin sees only assigned branch orders."""
    camden_headers = get_token_headers("usr-camden-admin-01", "BRANCH_ADMIN")
    resp = client.get("/api/v1/orders", headers=camden_headers)
    assert resp.status_code == 200
    orders = resp.json()
    for o in orders:
        assert o["branch_id"] == "branch-camden-001"


def test_admin_order_status_update_unauthenticated_denied_401():
    """Unauthenticated status transition PATCH request must be denied with 401."""
    resp = client.patch("/api/v1/orders/ord-alpha-1001/status", json={"status": "CANCELLED"})
    assert resp.status_code == 401


def test_admin_order_status_update_customer_denied_403():
    """Customer trying to update order status must receive 403 Forbidden."""
    customer_headers = get_token_headers("usr-cust-a-01", "CUSTOMER")
    resp = client.patch("/api/v1/orders/ord-alpha-1001/status", headers=customer_headers, json={"status": "CANCELLED"})
    assert resp.status_code == 403


def test_admin_order_status_update_admin_allowed_200():
    """Super Admin successfully updates order status."""
    admin_headers = get_token_headers("usr-super-admin-01", "SUPER_ADMIN")
    resp = client.patch(
        "/api/v1/orders/ord-alpha-1001/status",
        headers=admin_headers,
        json={"status": "PREPARING", "notes": "Kitchen started order"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "PREPARING"


# =========================================================================
# FINDING-3: Payment Refund Endpoint Authorization Tests
# =========================================================================

def test_payment_refund_unauthenticated_denied_401():
    """Unauthenticated caller attempting refund must receive 401 Unauthorized."""
    resp = client.post("/api/v1/payments/pay-alpha-001/refund", json={"amount": 10.0, "reason": "Customer request"})
    assert resp.status_code == 401


def test_payment_refund_customer_denied_403():
    """Normal customer attempting refund must receive 403 Forbidden."""
    customer_headers = get_token_headers("usr-cust-a-01", "CUSTOMER")
    resp = client.post(
        "/api/v1/payments/pay-alpha-001/refund",
        headers=customer_headers,
        json={"amount": 10.0, "reason": "Customer request"}
    )
    assert resp.status_code == 403
    assert "Not enough permissions" in resp.json()["detail"]


def test_payment_refund_branch_admin_denied_403():
    """Branch Admin attempting refund must receive 403 Forbidden (Only Super Admin can refund)."""
    camden_headers = get_token_headers("usr-camden-admin-01", "BRANCH_ADMIN")
    resp = client.post(
        "/api/v1/payments/pay-alpha-001/refund",
        headers=camden_headers,
        json={"amount": 10.0, "reason": "Branch admin request"}
    )
    assert resp.status_code == 403


def test_payment_refund_super_admin_allowed_200():
    """Super Admin successfully processes a partial refund."""
    admin_headers = get_token_headers("usr-super-admin-01", "SUPER_ADMIN")
    resp = client.post(
        "/api/v1/payments/pay-alpha-001/refund",
        headers=admin_headers,
        json={"amount": 5.0, "reason": "Authorized partial refund"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PARTIALLY_REFUNDED"
    assert data["refunded_amount"] == 5.0


def test_payment_inquiry_unauthenticated_denied_401():
    """Unauthenticated calls to /payments/{id} and /payments/order/{id} return 401."""
    resp1 = client.get("/api/v1/payments/pay-alpha-001")
    assert resp1.status_code == 401
    resp2 = client.get("/api/v1/payments/order/ord-alpha-1001")
    assert resp2.status_code == 401


def test_payment_inquiry_customer_b_cannot_inspect_customer_a_payment_403():
    """Customer B cannot view Customer A's payment details."""
    user_b_headers = get_token_headers("usr-cust-b-02", "CUSTOMER")
    resp = client.get("/api/v1/payments/pay-alpha-001", headers=user_b_headers)
    assert resp.status_code == 403


# =========================================================================
# FINDING-4: Order IDOR & PII Enumeration Tests
# =========================================================================

def test_order_idor_user_b_cannot_retrieve_user_a_order_403():
    """Customer B attempting to inspect Customer A's order by ID or order_number receives 403 Forbidden."""
    user_b_headers = get_token_headers("usr-cust-b-02", "CUSTOMER")

    # Accessing Customer A's order by UUID
    resp_uuid = client.get("/api/v1/orders/ord-alpha-1001", headers=user_b_headers)
    assert resp_uuid.status_code == 403
    assert "Access denied" in resp_uuid.json()["detail"]

    # Accessing Customer A's order by order_number
    resp_num = client.get(f"/api/v1/orders/{urllib.parse.quote('#PP1001')}", headers=user_b_headers)
    assert resp_num.status_code == 403
    assert "Access denied" in resp_num.json()["detail"]


def test_order_idor_user_a_can_retrieve_own_order_200():
    """Customer A can successfully inspect their own order."""
    user_a_headers = get_token_headers("usr-cust-a-01", "CUSTOMER")

    resp_uuid = client.get("/api/v1/orders/ord-alpha-1001", headers=user_a_headers)
    assert resp_uuid.status_code == 200
    assert resp_uuid.json()["id"] == "ord-alpha-1001"
    assert resp_uuid.json()["customer_email"] == "usera@pattytest.co.uk"

    resp_num = client.get(f"/api/v1/orders/{urllib.parse.quote('#PP1001')}", headers=user_a_headers)
    assert resp_num.status_code == 200
    assert resp_num.json()["order_number"] == "#PP1001"


def test_order_idor_unauthenticated_without_email_denied_401():
    """Unauthenticated caller without email verification attempting to enumerate orders receives 401."""
    resp = client.get(f"/api/v1/orders/{urllib.parse.quote('#PP1001')}")
    assert resp.status_code == 401
    assert "Authentication or customer email verification required" in resp.json()["detail"]


def test_order_idor_unauthenticated_with_valid_email_allowed_200():
    """Guest/unauthenticated customer with matching email query parameter can access order confirmation."""
    resp = client.get(
        f"/api/v1/orders/{urllib.parse.quote('#PP3003')}?email=guest@pattytest.co.uk"
    )
    assert resp.status_code == 200
    assert resp.json()["order_number"] == "#PP3003"


def test_order_idor_unauthenticated_with_wrong_email_denied_401():
    """Unauthenticated caller with mismatched email receives 401."""
    resp = client.get(
        f"/api/v1/orders/{urllib.parse.quote('#PP3003')}?email=attacker@evil.com"
    )
    assert resp.status_code == 401


def test_order_idor_admin_allowed_200():
    """Super Admin can inspect any customer order."""
    admin_headers = get_token_headers("usr-super-admin-01", "SUPER_ADMIN")
    resp = client.get("/api/v1/orders/ord-alpha-1001", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == "ord-alpha-1001"
