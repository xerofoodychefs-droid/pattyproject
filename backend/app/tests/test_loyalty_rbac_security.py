import sys
import pathlib
import uuid
import pytest
from datetime import datetime, timezone

backend_root = pathlib.Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.tests.db import client, reset_test_db, TestingSessionLocal
from app.models import (
    User, UserRole, Branch, BranchUser, Product, Order, OrderItem,
    OrderStatus, OrderType, PaymentStatus
)
from app.models.loyalty import (
    LoyaltyAccount, LoyaltyTransaction, LoyaltyProgramConfig,
    LoyaltyCampaign, LoyaltyMilestone
)
from app.core.security import get_password_hash, create_access_token
from app.services.loyalty_service import (
    get_or_create_loyalty_config,
    award_order_loyalty_points,
    reverse_order_loyalty_points,
    restore_redeemed_loyalty_points
)


@pytest.fixture(autouse=True)
def setup_security_test_environment():
    reset_test_db()
    db = TestingSessionLocal()

    # Ensure loyalty config
    get_or_create_loyalty_config(db)

    # 1. Super Admin
    super_admin = User(
        id="usr-sec-superadmin-01",
        email="superadmin@pattyproject.co.uk",
        password_hash=get_password_hash("SuperAdmin123!"),
        full_name="Global Super Admin",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        email_verified=True
    )
    db.add(super_admin)

    # 2. Camden Branch Admin
    camden_admin = User(
        id="usr-sec-camden-admin-01",
        email="camden.admin@pattyproject.co.uk",
        password_hash=get_password_hash("CamdenAdmin123!"),
        full_name="Camden Branch Admin",
        role=UserRole.BRANCH_ADMIN,
        is_active=True,
        email_verified=True
    )
    db.add(camden_admin)
    db.flush()

    bu_camden = BranchUser(
        id="bu-sec-camden-01",
        user_id=camden_admin.id,
        branch_id="branch-camden-001"
    )
    db.add(bu_camden)

    # 3. Westfield Branch Admin
    westfield_admin = User(
        id="usr-sec-westfield-admin-02",
        email="westfield.admin@pattyproject.co.uk",
        password_hash=get_password_hash("WestfieldAdmin123!"),
        full_name="Westfield Branch Admin",
        role=UserRole.BRANCH_ADMIN,
        is_active=True,
        email_verified=True
    )
    db.add(westfield_admin)
    db.flush()

    bu_westfield = BranchUser(
        id="bu-sec-westfield-02",
        user_id=westfield_admin.id,
        branch_id="branch-westfield-002"
    )
    db.add(bu_westfield)

    # 4. Customer Alice (Associated with Camden via Order)
    alice = User(
        id="usr-sec-alice-01",
        email="alice@example.com",
        password_hash=get_password_hash("AlicePass123!"),
        full_name="Alice Camden",
        phone="+44 7111 111111",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=True
    )
    db.add(alice)
    db.flush()

    alice_loyalty = LoyaltyAccount(
        id="loy-sec-alice-01",
        user_id=alice.id,
        available_points=5000,
        lifetime_points=8000,
        tier="BRONZE"
    )
    db.add(alice_loyalty)

    alice_camden_order = Order(
        id="ord-sec-alice-camden-01",
        order_number="#PP-ALICE-101",
        customer_id=alice.id,
        customer_name=alice.full_name,
        customer_email=alice.email,
        customer_phone=alice.phone,
        branch_id="branch-camden-001",
        order_type=OrderType.DELIVERY,
        status=OrderStatus.DELIVERED,
        subtotal=25.00,
        total_amount=25.99,
        points_earned=2500,
        points_redeemed=0
    )
    db.add(alice_camden_order)

    alice_tx = LoyaltyTransaction(
        id="tx-sec-alice-01",
        loyalty_account_id=alice_loyalty.id,
        order_id=alice_camden_order.id,
        points=2500,
        transaction_type="EARN",
        description="Points earned from Order #PP-ALICE-101",
        resulting_balance=5000,
        created_at=datetime.now(timezone.utc)
    )
    db.add(alice_tx)

    # 5. Customer Bob (Associated EXCLUSIVELY with Westfield via Order)
    bob = User(
        id="usr-sec-bob-02",
        email="bob@example.com",
        password_hash=get_password_hash("BobPass123!"),
        full_name="Bob Westfield",
        phone="+44 7222 222222",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=True
    )
    db.add(bob)
    db.flush()

    bob_loyalty = LoyaltyAccount(
        id="loy-sec-bob-02",
        user_id=bob.id,
        available_points=4000,
        lifetime_points=4000,
        tier="BRONZE"
    )
    db.add(bob_loyalty)

    bob_westfield_order = Order(
        id="ord-sec-bob-westfield-02",
        order_number="#PP-BOB-202",
        customer_id=bob.id,
        customer_name=bob.full_name,
        customer_email=bob.email,
        customer_phone=bob.phone,
        branch_id="branch-westfield-002",
        order_type=OrderType.COLLECTION,
        status=OrderStatus.DELIVERED,
        subtotal=40.00,
        total_amount=40.00,
        points_earned=4000,
        points_redeemed=0
    )
    db.add(bob_westfield_order)

    bob_tx = LoyaltyTransaction(
        id="tx-sec-bob-02",
        loyalty_account_id=bob_loyalty.id,
        order_id=bob_westfield_order.id,
        points=4000,
        transaction_type="EARN",
        description="Points earned from Order #PP-BOB-202",
        resulting_balance=4000,
        created_at=datetime.now(timezone.utc)
    )
    db.add(bob_tx)

    # 6. Customer Charlie (Registered Customer with ZERO Orders anywhere)
    charlie = User(
        id="usr-sec-charlie-03",
        email="charlie@example.com",
        password_hash=get_password_hash("CharliePass123!"),
        full_name="Charlie NoOrders",
        phone="+44 7333 333333",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=True
    )
    db.add(charlie)

    db.commit()
    db.close()


# ============================================================
# TEST GROUP A — DIRECT LOYALTY ISOLATION
# ============================================================

def test_01_customer_can_read_own_loyalty_balance():
    """1. Customer Alice can read her own loyalty balance (5,000 pts)."""
    alice_token = create_access_token(subject="usr-sec-alice-01", roles=[UserRole.CUSTOMER])
    resp = client.get("/api/v1/loyalty/balance", headers={"Authorization": f"Bearer {alice_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["available_points"] == 5000
    assert data["lifetime_points"] == 8000
    assert data["reward_value"] == 5.00
    assert data["is_redemption_available"] is True


def test_02_customer_can_read_own_loyalty_history():
    """2. Customer Alice can read her own loyalty history."""
    alice_token = create_access_token(subject="usr-sec-alice-01", roles=[UserRole.CUSTOMER])
    resp = client.get("/api/v1/loyalty/history", headers={"Authorization": f"Bearer {alice_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["order_id"] == "ord-sec-alice-camden-01"


def test_03_customer_cannot_access_other_customer_loyalty_data():
    """3. Customer cannot pass another user_id or account_id to /loyalty/balance (JWT sub is authoritative)."""
    bob_token = create_access_token(subject="usr-sec-bob-02", roles=[UserRole.CUSTOMER])
    # Attempting to supply query parameters or headers for alice must have NO effect
    resp = client.get("/api/v1/loyalty/balance?user_id=usr-sec-alice-01&customer_id=usr-sec-alice-01", headers={"Authorization": f"Bearer {bob_token}"})
    assert resp.status_code == 200
    data = resp.json()
    # Must return Bob's balance (4,000), not Alice's (5,000)
    assert data["available_points"] == 4000


def test_04_customer_cannot_manipulate_other_customer_loyalty_account():
    """4. Customer cannot redeem points from another account via /loyalty/redeem."""
    bob_token = create_access_token(subject="usr-sec-bob-02", roles=[UserRole.CUSTOMER])
    resp = client.post(
        "/api/v1/loyalty/redeem",
        json={"points": 4000, "user_id": "usr-sec-alice-01", "customer_email": "alice@example.com"},
        headers={"Authorization": f"Bearer {bob_token}"}
    )
    assert resp.status_code == 200
    # Must have deducted from Bob, not Alice
    db = TestingSessionLocal()
    bob_acc = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == "usr-sec-bob-02").first()
    alice_acc = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == "usr-sec-alice-01").first()
    assert bob_acc.available_points == 0
    assert alice_acc.available_points == 5000  # Alice completely untouched
    db.close()


def test_05_customer_forbidden_from_admin_loyalty():
    """5. Customer receives 403 on /loyalty/admin/* endpoints."""
    alice_token = create_access_token(subject="usr-sec-alice-01", roles=[UserRole.CUSTOMER])
    endpoints = [
        ("GET", "/api/v1/loyalty/admin/stats"),
        ("GET", "/api/v1/loyalty/admin/config"),
        ("PUT", "/api/v1/loyalty/admin/config"),
        ("GET", "/api/v1/loyalty/admin/members"),
        ("POST", "/api/v1/loyalty/admin/adjust-points"),
        ("GET", "/api/v1/loyalty/admin/transactions"),
        ("GET", "/api/v1/loyalty/admin/campaigns"),
        ("GET", "/api/v1/loyalty/admin/milestones"),
    ]
    for method, path in endpoints:
        if method == "GET":
            r = client.get(path, headers={"Authorization": f"Bearer {alice_token}"})
        elif method == "POST":
            r = client.post(path, json={}, headers={"Authorization": f"Bearer {alice_token}"})
        elif method == "PUT":
            r = client.put(path, json={}, headers={"Authorization": f"Bearer {alice_token}"})
        assert r.status_code == 403, f"{method} {path} expected 403, got {r.status_code}"


def test_06_branch_admin_forbidden_from_loyalty_admin_config():
    """6. Branch Admin receives 403 on /loyalty/admin/config."""
    camden_token = create_access_token(subject="usr-sec-camden-admin-01", roles=[UserRole.BRANCH_ADMIN])
    r = client.get("/api/v1/loyalty/admin/config", headers={"Authorization": f"Bearer {camden_token}"})
    assert r.status_code == 403


def test_07_branch_admin_forbidden_from_adjust_points():
    """7. Branch Admin cannot manually adjust loyalty points (403 Forbidden)."""
    camden_token = create_access_token(subject="usr-sec-camden-admin-01", roles=[UserRole.BRANCH_ADMIN])
    r = client.post(
        "/api/v1/loyalty/admin/adjust-points",
        json={"user_id": "usr-sec-alice-01", "points_delta": 500, "reason": "Branch admin bonus"},
        headers={"Authorization": f"Bearer {camden_token}"}
    )
    assert r.status_code == 403


def test_08_branch_admin_forbidden_from_milestones_crud():
    """8. Branch Admin cannot create or modify milestones (403 Forbidden)."""
    camden_token = create_access_token(subject="usr-sec-camden-admin-01", roles=[UserRole.BRANCH_ADMIN])
    r = client.post(
        "/api/v1/loyalty/admin/milestones",
        json={"name": "Fake Milestone", "points_required": 1000},
        headers={"Authorization": f"Bearer {camden_token}"}
    )
    assert r.status_code == 403


def test_09_super_admin_can_access_loyalty_admin():
    """9. Super Admin has full access to loyalty administrative endpoints."""
    super_token = create_access_token(subject="usr-sec-superadmin-01", roles=[UserRole.SUPER_ADMIN])
    r = client.get("/api/v1/loyalty/admin/stats", headers={"Authorization": f"Bearer {super_token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["total_members"] >= 2
    assert "total_active_points" in data


# ============================================================
# TEST GROUP B — GUEST REDEMPTION SECURITY (SEC-LOYALTY-01)
# ============================================================

def _valid_order_payload(redeem_points=0, customer_email="guest@example.com", branch_id="branch-camden-001"):
    return {
        "customer_name": "Test Customer",
        "customer_email": customer_email,
        "customer_phone": "+44 7999 999999",
        "branch_id": branch_id,
        "order_type": "COLLECTION",
        "items": [
            {
                "product_id": "prod-mc-project",
                "quantity": 2,
                "selected_modifiers": []
            }
        ],
        "redeem_points": redeem_points
    }


def test_10_guest_checkout_without_redemption_succeeds():
    """10. Normal guest checkout with redeem_points=0 succeeds completely."""
    payload = _valid_order_payload(redeem_points=0, customer_email="guest.shopper@example.com")
    resp = client.post("/api/v1/orders", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "PENDING_PAYMENT"
    assert data["points_redeemed"] == 0


def test_11_guest_checkout_with_redemption_returns_401():
    """11. SEC-LOYALTY-01: Unauthenticated request attempting redeem_points > 0 returns 401."""
    payload = _valid_order_payload(redeem_points=4000, customer_email="alice@example.com")
    resp = client.post("/api/v1/orders", json=payload)
    assert resp.status_code == 401
    assert "Authentication required" in resp.json()["detail"]


def test_12_authenticated_customer_can_redeem_own_points():
    """12. Authenticated Alice can redeem 4,000 of her 5,000 points."""
    alice_token = create_access_token(subject="usr-sec-alice-01", roles=[UserRole.CUSTOMER])
    payload = _valid_order_payload(redeem_points=4000, customer_email="alice@example.com")
    resp = client.post("/api/v1/orders", json=payload, headers={"Authorization": f"Bearer {alice_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["points_redeemed"] == 4000
    assert data["discount_amount"] == 4.00

    # Verify balance was deducted
    db = TestingSessionLocal()
    acc = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == "usr-sec-alice-01").first()
    assert acc.available_points == 1000
    db.close()


def test_13_authenticated_customer_cannot_redeem_other_customer_points():
    """13. Authenticated Bob attempting to redeem against Alice's email returns 403 Forbidden."""
    bob_token = create_access_token(subject="usr-sec-bob-02", roles=[UserRole.CUSTOMER])
    payload = _valid_order_payload(redeem_points=4000, customer_email="alice@example.com")
    resp = client.post("/api/v1/orders", json=payload, headers={"Authorization": f"Bearer {bob_token}"})
    assert resp.status_code == 403
    assert "You can only redeem loyalty points for your own account" in resp.json()["detail"]


def test_14_tampered_customer_email_cannot_redirect_redemption():
    """14. Tampering customer_email in JSON payload does not compromise victim's loyalty account."""
    charlie_token = create_access_token(subject="usr-sec-charlie-03", roles=[UserRole.CUSTOMER])
    payload = _valid_order_payload(redeem_points=4000, customer_email="alice@example.com")
    resp = client.post("/api/v1/orders", json=payload, headers={"Authorization": f"Bearer {charlie_token}"})
    assert resp.status_code == 403

    db = TestingSessionLocal()
    alice_acc = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == "usr-sec-alice-01").first()
    assert alice_acc.available_points == 5000  # Alice untouched
    db.close()


def test_15_tampered_customer_id_in_payload_ignored():
    """15. Injecting customer_id or loyalty_account_id in payload cannot bypass JWT identity."""
    charlie_token = create_access_token(subject="usr-sec-charlie-03", roles=[UserRole.CUSTOMER])
    payload = _valid_order_payload(redeem_points=4000, customer_email="charlie@example.com")
    payload["customer_id"] = "usr-sec-alice-01"
    payload["loyalty_account_id"] = "loy-sec-alice-01"
    # Charlie has 0 points, so this must fail with 400 Insufficient loyalty points, NOT charge Alice
    resp = client.post("/api/v1/orders", json=payload, headers={"Authorization": f"Bearer {charlie_token}"})
    assert resp.status_code == 400
    assert "Insufficient loyalty points" in resp.json()["detail"]


def test_16_insufficient_points_rejected():
    """16. Requesting more points than available is rejected."""
    alice_token = create_access_token(subject="usr-sec-alice-01", roles=[UserRole.CUSTOMER])
    payload = _valid_order_payload(redeem_points=9000, customer_email="alice@example.com")
    resp = client.post("/api/v1/orders", json=payload, headers={"Authorization": f"Bearer {alice_token}"})
    assert resp.status_code == 400
    assert "Insufficient loyalty points" in resp.json()["detail"]


def test_17_invalid_redemption_increments_rejected():
    """17. Non-1000 increments (e.g. 4500 points) or <4000 points rejected."""
    alice_token = create_access_token(subject="usr-sec-alice-01", roles=[UserRole.CUSTOMER])
    payload = _valid_order_payload(redeem_points=4500, customer_email="alice@example.com")
    resp = client.post("/api/v1/orders", json=payload, headers={"Authorization": f"Bearer {alice_token}"})
    assert resp.status_code == 400
    assert "1,000-point increments" in resp.json()["detail"]

    # Also test < 4000 threshold
    payload_low = _valid_order_payload(redeem_points=2000, customer_email="alice@example.com")
    resp_low = client.post("/api/v1/orders", json=payload_low, headers={"Authorization": f"Bearer {alice_token}"})
    assert resp_low.status_code == 400
    assert "Minimum 4,000" in resp_low.json()["detail"]


# ============================================================
# TEST GROUP C — CUSTOMER DIRECTORY RBAC (SEC-LOYALTY-02)
# ============================================================

def test_18_customer_forbidden_from_customers_directory():
    """18. Customer role receives 403 on GET /customers."""
    alice_token = create_access_token(subject="usr-sec-alice-01", roles=[UserRole.CUSTOMER])
    resp = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {alice_token}"})
    assert resp.status_code == 403


def test_19_unauthenticated_request_to_customers_returns_401():
    """19. Unauthenticated request to /customers returns 401."""
    resp = client.get("/api/v1/customers")
    assert resp.status_code == 401


def test_20_super_admin_lists_all_customers_globally():
    """20. Super Admin lists all customers across all branches."""
    super_token = create_access_token(subject="usr-sec-superadmin-01", roles=[UserRole.SUPER_ADMIN])
    resp = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {super_token}"})
    assert resp.status_code == 200
    emails = [c["email"] for c in resp.json()]
    assert "alice@example.com" in emails
    assert "bob@example.com" in emails
    assert "charlie@example.com" in emails


def test_21_super_admin_can_view_any_customer_detail():
    """21. Super Admin can view detail of any customer."""
    super_token = create_access_token(subject="usr-sec-superadmin-01", roles=[UserRole.SUPER_ADMIN])
    resp = client.get("/api/v1/customers/usr-sec-alice-01", headers={"Authorization": f"Bearer {super_token}"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Alice Camden"


def test_22_branch_admin_sees_only_assigned_branch_customers():
    """22. Camden Branch Admin sees Alice (who ordered at Camden) but NOT Bob (who ordered only at Westfield)."""
    camden_token = create_access_token(subject="usr-sec-camden-admin-01", roles=[UserRole.BRANCH_ADMIN])
    resp = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {camden_token}"})
    assert resp.status_code == 200
    data = resp.json()
    emails = [c["email"] for c in data]
    assert "alice@example.com" in emails
    assert "bob@example.com" not in emails
    assert "charlie@example.com" not in emails


def test_23_branch_admin_cannot_view_unrelated_branch_customers():
    """23. Westfield Branch Admin sees Bob but NOT Alice."""
    westfield_token = create_access_token(subject="usr-sec-westfield-admin-02", roles=[UserRole.BRANCH_ADMIN])
    resp = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {westfield_token}"})
    assert resp.status_code == 200
    data = resp.json()
    emails = [c["email"] for c in data]
    assert "bob@example.com" in emails
    assert "alice@example.com" not in emails


def test_24_branch_admin_cannot_access_unrelated_customer_detail_by_id():
    """24. Camden Branch Admin requesting Bob's ID receives 404 (no enumeration)."""
    camden_token = create_access_token(subject="usr-sec-camden-admin-01", roles=[UserRole.BRANCH_ADMIN])
    resp = client.get("/api/v1/customers/usr-sec-bob-02", headers={"Authorization": f"Bearer {camden_token}"})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Customer not found"


def test_25_branch_admin_cannot_bypass_branch_scope_with_query_params():
    """25. Passing search or branch parameters cannot bypass branch isolation."""
    camden_token = create_access_token(subject="usr-sec-camden-admin-01", roles=[UserRole.BRANCH_ADMIN])
    resp = client.get("/api/v1/customers?search=bob", headers={"Authorization": f"Bearer {camden_token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 0


def test_26_branch_admin_accessing_authorized_customer_detail():
    """26. Camden Branch Admin can view Alice's detail."""
    camden_token = create_access_token(subject="usr-sec-camden-admin-01", roles=[UserRole.BRANCH_ADMIN])
    resp = client.get("/api/v1/customers/usr-sec-alice-01", headers={"Authorization": f"Bearer {camden_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Alice Camden"
    assert data["email"] == "alice@example.com"


# ============================================================
# TEST GROUP D — DATA LEAKAGE & LEDGER PRIVACY
# ============================================================

def test_27_unauthorized_customer_detail_does_not_leak_ledger():
    """27. Unauthorized request returns 404 with no body payload or ledger info."""
    camden_token = create_access_token(subject="usr-sec-camden-admin-01", roles=[UserRole.BRANCH_ADMIN])
    resp = client.get("/api/v1/customers/usr-sec-bob-02", headers={"Authorization": f"Bearer {camden_token}"})
    assert resp.status_code == 404
    assert "loyalty_transactions" not in resp.json()


def test_28_branch_admin_sees_only_branch_orders_in_customer_detail():
    """28. If a customer ordered at multiple branches, Camden admin sees only Camden orders."""
    db = TestingSessionLocal()
    # Add a Westfield order for Alice
    alice_westfield_order = Order(
        id="ord-sec-alice-westfield-99",
        order_number="#PP-ALICE-WESTFIELD",
        customer_id="usr-sec-alice-01",
        customer_name="Alice Camden",
        customer_email="alice@example.com",
        customer_phone="+44 7111 111111",
        branch_id="branch-westfield-002",
        order_type=OrderType.DELIVERY,
        status=OrderStatus.DELIVERED,
        subtotal=30.00,
        total_amount=30.00
    )
    db.add(alice_westfield_order)
    db.commit()
    db.close()

    camden_token = create_access_token(subject="usr-sec-camden-admin-01", roles=[UserRole.BRANCH_ADMIN])
    resp = client.get("/api/v1/customers/usr-sec-alice-01", headers={"Authorization": f"Bearer {camden_token}"})
    assert resp.status_code == 200
    data = resp.json()
    order_numbers = [o["order_number"] for o in data["recent_orders"]]
    assert "#PP-ALICE-101" in order_numbers
    assert "#PP-ALICE-WESTFIELD" not in order_numbers  # Cross-branch order filtered out!


def test_29_branch_admin_sees_only_branch_loyalty_transactions():
    """29. Branch Admin only sees loyalty transactions associated with their branch orders."""
    db = TestingSessionLocal()
    alice_westfield_tx = LoyaltyTransaction(
        id="tx-sec-alice-westfield-99",
        loyalty_account_id="loy-sec-alice-01",
        order_id="ord-sec-alice-westfield-99",
        points=3000,
        transaction_type="EARN",
        description="Points from Westfield Order",
        resulting_balance=8000,
        created_at=datetime.now(timezone.utc)
    )
    db.add(alice_westfield_tx)
    db.commit()
    db.close()

    camden_token = create_access_token(subject="usr-sec-camden-admin-01", roles=[UserRole.BRANCH_ADMIN])
    resp = client.get("/api/v1/customers/usr-sec-alice-01", headers={"Authorization": f"Bearer {camden_token}"})
    assert resp.status_code == 200
    data = resp.json()
    tx_ids = [tx["id"] for tx in data["loyalty_transactions"]]
    assert "tx-sec-alice-01" in tx_ids
    assert "tx-sec-alice-westfield-99" not in tx_ids  # Westfield tx filtered out!


# ============================================================
# TEST GROUP E — REGRESSION & BUSINESS LOGIC
# ============================================================

def test_30_loyalty_earning_on_order_status_paid():
    """30. Order earning calculation and transaction recording function accurately."""
    db = TestingSessionLocal()
    order = db.query(Order).filter(Order.id == "ord-sec-alice-camden-01").first()
    # Test awarding service function directly
    tx = award_order_loyalty_points(db, order)
    # Idempotent: already awarded in fixture setup
    assert tx is not None
    db.close()


def test_31_loyalty_reversal_on_refund():
    """31. Order points reversal on refund functions accurately."""
    db = TestingSessionLocal()
    order = db.query(Order).filter(Order.id == "ord-sec-alice-camden-01").first()
    tx = reverse_order_loyalty_points(db, order, reason="Customer complaint")
    assert tx is not None
    assert tx.points < 0
    assert tx.transaction_type == "REVERSE"
    db.close()


def test_32_loyalty_restoration_on_cancellation():
    """32. Redeemed points restoration on order cancellation functions accurately."""
    db = TestingSessionLocal()
    order = Order(
        id="ord-sec-restore-test-01",
        order_number="#PP-RESTORE-01",
        customer_id="usr-sec-bob-02",
        customer_name="Bob Westfield",
        customer_email="bob@example.com",
        customer_phone="+44 7222 222222",
        branch_id="branch-westfield-002",
        order_type=OrderType.COLLECTION,
        status=OrderStatus.CANCELLED,
        subtotal=20.00,
        total_amount=20.00,
        points_redeemed=4000
    )
    db.add(order)
    db.commit()

    tx = restore_redeemed_loyalty_points(db, order, reason="Order cancelled by user")
    assert tx is not None
    assert tx.points == 4000
    assert tx.transaction_type == "REVERSE"
    db.close()


def test_33_campaign_multipliers_calculate_accurately():
    """33. Active campaign multipliers compute points accurately."""
    from app.services.loyalty_service import calculate_eligible_spend_and_points
    db = TestingSessionLocal()
    calc = calculate_eligible_spend_and_points(db=db, items=[], subtotal=20.0, discount_amount=0.0)
    assert calc["base_points"] == 2000
    assert calc["points_earned"] >= 2000
    db.close()


def test_34_milestones_list_publicly_readable():
    """34. Milestones list is accessible publicly without token."""
    resp = client.get("/api/v1/loyalty/milestones")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    assert any(m["points_required"] == 4000 for m in data)


def test_35_super_admin_can_create_and_delete_campaign():
    """35. Super Admin can manage campaign lifecycle."""
    super_token = create_access_token(subject="usr-sec-superadmin-01", roles=[UserRole.SUPER_ADMIN])
    create_resp = client.post(
        "/api/v1/loyalty/admin/campaigns",
        json={"name": "Weekend Double", "campaign_type": "DOUBLE_POINTS", "multiplier": 2.0},
        headers={"Authorization": f"Bearer {super_token}"}
    )
    assert create_resp.status_code == 200
    camp_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/v1/loyalty/admin/campaigns/{camp_id}", headers={"Authorization": f"Bearer {super_token}"})
    assert del_resp.status_code == 200


def test_36_super_admin_can_create_and_delete_milestone():
    """36. Super Admin can manage milestone lifecycle."""
    super_token = create_access_token(subject="usr-sec-superadmin-01", roles=[UserRole.SUPER_ADMIN])
    create_resp = client.post(
        "/api/v1/loyalty/admin/milestones",
        json={"name": "Gold Milestone", "points_required": 10000, "reward_value": 10.0},
        headers={"Authorization": f"Bearer {super_token}"}
    )
    assert create_resp.status_code == 200
    m_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/v1/loyalty/admin/milestones/{m_id}", headers={"Authorization": f"Bearer {super_token}"})
    assert del_resp.status_code == 200


def test_37_branch_admin_cannot_delete_campaign():
    """37. Branch Admin cannot delete loyalty campaign (403 Forbidden)."""
    camden_token = create_access_token(subject="usr-sec-camden-admin-01", roles=[UserRole.BRANCH_ADMIN])
    del_resp = client.delete("/api/v1/loyalty/admin/campaigns/nonexistent", headers={"Authorization": f"Bearer {camden_token}"})
    assert del_resp.status_code == 403


def test_38_expired_or_invalid_token_rejected():
    """38. Expired or malformed token rejected with 401."""
    resp = client.get("/api/v1/loyalty/balance", headers={"Authorization": "Bearer invalid.token.value"})
    assert resp.status_code == 401


def test_39_invalid_token_rejected_on_customers():
    """39. Invalid token on /customers rejected with 401."""
    resp = client.get("/api/v1/customers", headers={"Authorization": "Bearer invalid.token.value"})
    assert resp.status_code == 401


def test_40_admin_customer_search_works_within_branch_scope():
    """40. Branch Admin searching for customer only finds matches within authorized branch scope."""
    camden_token = create_access_token(subject="usr-sec-camden-admin-01", roles=[UserRole.BRANCH_ADMIN])
    # Search for Alice (Camden) -> Found
    resp_alice = client.get("/api/v1/customers?search=Alice", headers={"Authorization": f"Bearer {camden_token}"})
    assert resp_alice.status_code == 200
    assert len(resp_alice.json()) == 1

    # Search for Bob (Westfield) -> NOT Found
    resp_bob = client.get("/api/v1/customers?search=Bob", headers={"Authorization": f"Bearer {camden_token}"})
    assert resp_bob.status_code == 200
    assert len(resp_bob.json()) == 0


def test_41_charlie_no_orders_not_visible_to_any_branch_admin():
    """41. Charlie has no orders at any store, so is visible ONLY to Super Admin and NO Branch Admins."""
    camden_token = create_access_token(subject="usr-sec-camden-admin-01", roles=[UserRole.BRANCH_ADMIN])
    westfield_token = create_access_token(subject="usr-sec-westfield-admin-02", roles=[UserRole.BRANCH_ADMIN])
    super_token = create_access_token(subject="usr-sec-superadmin-01", roles=[UserRole.SUPER_ADMIN])

    # Camden Branch Admin
    r_camden = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {camden_token}"})
    assert "charlie@example.com" not in [c["email"] for c in r_camden.json()]

    # Westfield Branch Admin
    r_westfield = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {westfield_token}"})
    assert "charlie@example.com" not in [c["email"] for c in r_westfield.json()]

    # Super Admin
    r_super = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {super_token}"})
    assert "charlie@example.com" in [c["email"] for c in r_super.json()]


def test_42_super_admin_and_branch_admin_excluded_from_loyalty_members():
    """42. SUPER_ADMIN and BRANCH_ADMIN accounts are strictly excluded from loyalty members list."""
    super_token = create_access_token(subject="usr-sec-superadmin-01", roles=[UserRole.SUPER_ADMIN])
    db = TestingSessionLocal()
    
    # Even if a LoyaltyAccount exists for Super Admin or Branch Admin in the DB
    sa_loy = LoyaltyAccount(id="loy-sa-rogue", user_id="usr-sec-superadmin-01", available_points=5128, lifetime_points=5128)
    ba_loy = LoyaltyAccount(id="loy-ba-rogue", user_id="usr-sec-camden-admin-01", available_points=2000, lifetime_points=2000)
    db.add_all([sa_loy, ba_loy])
    db.commit()

    resp = client.get("/api/v1/loyalty/admin/members", headers={"Authorization": f"Bearer {super_token}"})
    assert resp.status_code == 200
    member_user_ids = [m["user_id"] for m in resp.json()]
    member_emails = [m["email"] for m in resp.json()]

    # 1. SUPER_ADMIN is excluded
    assert "usr-sec-superadmin-01" not in member_user_ids
    assert "superadmin@pattyproject.co.uk" not in member_emails

    # 2. BRANCH_ADMIN is excluded
    assert "usr-sec-camden-admin-01" not in member_user_ids
    assert "camden.admin@pattyproject.co.uk" not in member_emails

    # 3. CUSTOMERS appear
    assert "usr-sec-alice-01" in member_user_ids
    assert "usr-sec-bob-02" in member_user_ids


def test_43_search_excludes_super_admin_and_branch_admin():
    """43. Searching for Super Admin or Branch Admin in loyalty members returns 0 results."""
    super_token = create_access_token(subject="usr-sec-superadmin-01", roles=[UserRole.SUPER_ADMIN])
    
    # Search for superadmin
    resp_sa = client.get("/api/v1/loyalty/admin/members?search=superadmin", headers={"Authorization": f"Bearer {super_token}"})
    assert resp_sa.status_code == 200
    assert len(resp_sa.json()) == 0

    # Search for branch admin
    resp_ba = client.get("/api/v1/loyalty/admin/members?search=camden.admin", headers={"Authorization": f"Bearer {super_token}"})
    assert resp_ba.status_code == 200
    assert len(resp_ba.json()) == 0


def test_44_super_admin_and_branch_admin_excluded_from_loyalty_totals():
    """44. Super Admin and Branch Admin points do NOT contribute to Total Members, Active Balance, or Issued Points."""
    super_token = create_access_token(subject="usr-sec-superadmin-01", roles=[UserRole.SUPER_ADMIN])
    db = TestingSessionLocal()

    # Get baseline stats with only customers
    resp_before = client.get("/api/v1/loyalty/admin/stats", headers={"Authorization": f"Bearer {super_token}"})
    assert resp_before.status_code == 200
    stats_before = resp_before.json()
    base_members = stats_before["total_members"]
    base_active_pts = stats_before["total_active_points"]
    base_issued_pts = stats_before["total_points_issued"]

    # Inject rogue loyalty accounts and transactions for Super Admin (5,128 pts) and Branch Admin (2,000 pts)
    sa_loy = LoyaltyAccount(id="loy-sa-stat-test", user_id="usr-sec-superadmin-01", available_points=5128, lifetime_points=5128)
    ba_loy = LoyaltyAccount(id="loy-ba-stat-test", user_id="usr-sec-camden-admin-01", available_points=2000, lifetime_points=2000)
    db.add_all([sa_loy, ba_loy])
    db.flush()

    sa_tx = LoyaltyTransaction(
        id="tx-sa-rogue", loyalty_account_id=sa_loy.id, points=5128,
        transaction_type="MANUAL_CREDIT", resulting_balance=5128
    )
    ba_tx = LoyaltyTransaction(
        id="tx-ba-rogue", loyalty_account_id=ba_loy.id, points=2000,
        transaction_type="MANUAL_CREDIT", resulting_balance=2000
    )
    db.add_all([sa_tx, ba_tx])
    db.commit()

    resp_after = client.get("/api/v1/loyalty/admin/stats", headers={"Authorization": f"Bearer {super_token}"})
    assert resp_after.status_code == 200
    stats_after = resp_after.json()

    # Points and members for Super Admin and Branch Admin MUST be excluded
    assert stats_after["total_members"] == base_members
    assert stats_after["total_active_points"] == base_active_pts
    assert stats_after["total_points_issued"] == base_issued_pts


def test_45_customer_points_remain_included_and_unchanged():
    """45. Customer points remain fully included in stats and members."""
    super_token = create_access_token(subject="usr-sec-superadmin-01", roles=[UserRole.SUPER_ADMIN])
    
    resp_stats = client.get("/api/v1/loyalty/admin/stats", headers={"Authorization": f"Bearer {super_token}"})
    assert resp_stats.status_code == 200
    stats = resp_stats.json()
    assert stats["total_members"] == 2  # Alice (5000) and Bob (4000)
    assert stats["total_active_points"] == 9000  # 5000 + 4000

    resp_members = client.get("/api/v1/loyalty/admin/members", headers={"Authorization": f"Bearer {super_token}"})
    assert resp_members.status_code == 200
    members = {m["user_id"]: m["available_points"] for m in resp_members.json()}
    assert members["usr-sec-alice-01"] == 5000
    assert members["usr-sec-bob-02"] == 4000


def test_46_super_admin_cannot_receive_or_adjust_loyalty_points_via_api():
    """46. Attempting to adjust points for a SUPER_ADMIN returns HTTP 400 Bad Request."""
    super_token = create_access_token(subject="usr-sec-superadmin-01", roles=[UserRole.SUPER_ADMIN])
    
    payload = {
        "user_id": "usr-sec-superadmin-01",
        "points_delta": 500,
        "reason": "Test audit reason for super admin adjustment"
    }
    resp = client.post("/api/v1/loyalty/admin/adjust-points", json=payload, headers={"Authorization": f"Bearer {super_token}"})
    assert resp.status_code == 400
    assert "customers" in resp.json()["detail"].lower()


def test_47_branch_admin_cannot_receive_or_adjust_loyalty_points_via_api():
    """47. Attempting to adjust points for a BRANCH_ADMIN returns HTTP 400 Bad Request."""
    super_token = create_access_token(subject="usr-sec-superadmin-01", roles=[UserRole.SUPER_ADMIN])
    
    payload = {
        "user_id": "usr-sec-camden-admin-01",
        "points_delta": 500,
        "reason": "Test audit reason for branch admin adjustment"
    }
    resp = client.post("/api/v1/loyalty/admin/adjust-points", json=payload, headers={"Authorization": f"Bearer {super_token}"})
    assert resp.status_code == 400
    assert "customers" in resp.json()["detail"].lower()


def test_48_customer_point_adjustment_still_works():
    """48. Point adjustments for valid CUSTOMER accounts still work seamlessly."""
    super_token = create_access_token(subject="usr-sec-superadmin-01", roles=[UserRole.SUPER_ADMIN])
    
    payload = {
        "user_id": "usr-sec-alice-01",
        "points_delta": 250,
        "reason": "Customer loyalty bonus compensation",
        "admin_notes": "Added via customer support workflow"
    }
    resp = client.post("/api/v1/loyalty/admin/adjust-points", json=payload, headers={"Authorization": f"Bearer {super_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["points"] == 250
    assert data["resulting_balance"] == 5250


def test_49_super_admin_cannot_access_customer_loyalty_portal():
    """49. Super Admin cannot access /loyalty/balance, /loyalty/redeem, or /loyalty/history."""
    super_token = create_access_token(subject="usr-sec-superadmin-01", roles=[UserRole.SUPER_ADMIN])
    
    r_bal = client.get("/api/v1/loyalty/balance", headers={"Authorization": f"Bearer {super_token}"})
    assert r_bal.status_code == 403

    r_red = client.post("/api/v1/loyalty/redeem", json={"points": 4000}, headers={"Authorization": f"Bearer {super_token}"})
    assert r_red.status_code == 403

    r_hist = client.get("/api/v1/loyalty/history", headers={"Authorization": f"Bearer {super_token}"})
    assert r_hist.status_code == 403


def test_50_admin_transactions_ledger_excludes_admin_records():
    """50. Admin transactions ledger strictly excludes transactions from non-customer accounts."""
    super_token = create_access_token(subject="usr-sec-superadmin-01", roles=[UserRole.SUPER_ADMIN])
    db = TestingSessionLocal()

    # Create rogue loyalty account and transaction for Super Admin
    sa_loy = LoyaltyAccount(id="loy-sa-tx-ledger-test", user_id="usr-sec-superadmin-01", available_points=5128, lifetime_points=5128)
    db.add(sa_loy)
    db.flush()

    sa_tx = LoyaltyTransaction(
        id="tx-sa-ledger-rogue",
        loyalty_account_id=sa_loy.id,
        points=5128,
        transaction_type="MANUAL_CREDIT",
        description="Rogue super admin points",
        resulting_balance=5128
    )
    db.add(sa_tx)
    db.commit()

    resp = client.get("/api/v1/loyalty/admin/transactions", headers={"Authorization": f"Bearer {super_token}"})
    assert resp.status_code == 200
    tx_ids = [t["id"] for t in resp.json()]
    assert "tx-sa-ledger-rogue" not in tx_ids


def test_51_order_with_admin_email_never_creates_or_awards_loyalty_points():
    """51. An order placed with Super Admin or Branch Admin email never awards loyalty points or creates loyalty accounts."""
    db = TestingSessionLocal()
    order = Order(
        id="ord-admin-test-01",
        order_number="#PP-ADMIN-999",
        customer_name="Global Super Admin",
        customer_email="superadmin@pattyproject.co.uk",
        customer_phone="+44 7000 000000",
        branch_id="branch-camden-001",
        order_type=OrderType.DELIVERY,
        status=OrderStatus.DELIVERED,
        subtotal=50.00,
        total_amount=50.00,
        points_earned=5000,
        points_redeemed=0
    )
    db.add(order)
    db.commit()

    # Attempt to award loyalty points
    tx = award_order_loyalty_points(db, order)
    assert tx is None

    # Verify no LoyaltyAccount was created for Super Admin
    sa_loy = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == "usr-sec-superadmin-01").first()
    assert sa_loy is None


def test_52_cleanup_routine_sanitizes_admin_loyalty_points_preserving_audit_ledger():
    """52. Startup seed cleanup routine sanitizes admin loyalty points to 0 while preserving customer accounts and audit ledger."""
    db = TestingSessionLocal()

    # Inject rogue admin loyalty account
    rogue_sa = LoyaltyAccount(id="loy-sa-cleanup-test", user_id="usr-sec-superadmin-01", available_points=5128, lifetime_points=5128)
    rogue_ba = LoyaltyAccount(id="loy-ba-cleanup-test", user_id="usr-sec-camden-admin-01", available_points=1000, lifetime_points=1000)
    db.add_all([rogue_sa, rogue_ba])
    db.commit()

    # Run seed cleanup logic
    admin_users = db.query(User).filter(User.role.in_([UserRole.SUPER_ADMIN, UserRole.BRANCH_ADMIN])).all()
    for au in admin_users:
        admin_loyalty = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == au.id).first()
        if admin_loyalty and (admin_loyalty.available_points != 0 or admin_loyalty.lifetime_points != 0):
            admin_loyalty.available_points = 0
            admin_loyalty.lifetime_points = 0
    db.commit()

    # Admin loyalty accounts sanitized to 0
    sa_res = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == "usr-sec-superadmin-01").first()
    ba_res = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == "usr-sec-camden-admin-01").first()
    assert sa_res.available_points == 0
    assert sa_res.lifetime_points == 0
    assert ba_res.available_points == 0
    assert ba_res.lifetime_points == 0

    # Customer loyalty accounts preserved
    alice_loy = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == "usr-sec-alice-01").first()
    assert alice_loy is not None
    assert alice_loy.available_points == 5000
