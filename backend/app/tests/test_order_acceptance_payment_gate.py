import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.order import Order, OrderStatus, OrderType, OrderStatusHistory, PaymentStatus
from app.models.payment import PaymentStatus as DetailedPaymentStatus
from app.models.branch import Branch, BranchUser
from app.models.user import User, UserRole
from app.core.security import create_access_token
from app.tests.db import client, TestingSessionLocal, reset_test_db


@pytest.fixture(autouse=True)
def setup_db():
    reset_test_db()
    yield


def _create_test_order(
    db: Session,
    order_id: str,
    order_number: str,
    branch_id: str = "branch-camden-001",
    status: str = OrderStatus.INCOMING,
    payment_status: str = PaymentStatus.PENDING
) -> str:
    order = Order(
        id=order_id,
        order_number=order_number,
        branch_id=branch_id,
        customer_name="Test Customer",
        customer_email="customer@example.com",
        customer_phone="+447123456789",
        order_type=OrderType.COLLECTION,
        status=status,
        subtotal=25.00,
        total_amount=25.00,
        payment_status=payment_status
    )
    db.add(order)
    db.commit()
    return order_id


# =============================================================================
# 1. AUTHORITATIVE PAYMENT GATE UNIT & API INTEGRATION TESTS
# =============================================================================

def test_paid_order_can_be_accepted():
    """Authoritative test: PAID order transitions from INCOMING to ACCEPTED with 200 OK."""
    db = TestingSessionLocal()
    order_id = _create_test_order(db, "ord-paid-001", "#PP1001", payment_status=PaymentStatus.PAID)
    db.close()

    admin_token = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])
    headers = {"Authorization": f"Bearer {admin_token}"}

    response = client.patch(
        f"/api/v1/orders/{order_id}/status",
        headers=headers,
        json={"status": "ACCEPTED", "notes": "Kitchen staff accepted order"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == OrderStatus.ACCEPTED
    assert data["payment_status"] == PaymentStatus.PAID

    # Verify DB persistence
    db = TestingSessionLocal()
    db_order = db.query(Order).filter(Order.id == order_id).first()
    assert db_order.status == OrderStatus.ACCEPTED
    assert db_order.payment_status == PaymentStatus.PAID
    db.close()


def test_pending_payment_order_cannot_be_accepted():
    """Authoritative test: PENDING payment order cannot be accepted; rejected with 400."""
    db = TestingSessionLocal()
    order_id = _create_test_order(db, "ord-pending-002", "#PP1002", payment_status=PaymentStatus.PENDING)
    db.close()

    admin_token = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])
    headers = {"Authorization": f"Bearer {admin_token}"}

    response = client.patch(
        f"/api/v1/orders/{order_id}/status",
        headers=headers,
        json={"status": "ACCEPTED"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Order cannot be accepted until payment is confirmed."

    # Verify DB order state remains unchanged (INCOMING)
    db = TestingSessionLocal()
    db_order = db.query(Order).filter(Order.id == order_id).first()
    assert db_order.status == OrderStatus.INCOMING
    assert db_order.payment_status == PaymentStatus.PENDING
    db.close()


def test_failed_payment_order_cannot_be_accepted():
    """Authoritative test: FAILED payment order cannot be accepted; rejected with 400."""
    db = TestingSessionLocal()
    order_id = _create_test_order(db, "ord-failed-003", "#PP1003", payment_status=PaymentStatus.FAILED)
    db.close()

    admin_token = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])
    headers = {"Authorization": f"Bearer {admin_token}"}

    response = client.patch(
        f"/api/v1/orders/{order_id}/status",
        headers=headers,
        json={"status": "ACCEPTED"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Order cannot be accepted until payment is confirmed."

    # Verify DB state remains INCOMING
    db = TestingSessionLocal()
    db_order = db.query(Order).filter(Order.id == order_id).first()
    assert db_order.status == OrderStatus.INCOMING
    db.close()


def test_cancelled_payment_order_cannot_be_accepted():
    """Authoritative test: CANCELLED payment order cannot be accepted; rejected with 400."""
    db = TestingSessionLocal()
    order_id = _create_test_order(db, "ord-cancelled-pay-004", "#PP1004", payment_status=DetailedPaymentStatus.CANCELLED)
    db.close()

    admin_token = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])
    headers = {"Authorization": f"Bearer {admin_token}"}

    response = client.patch(
        f"/api/v1/orders/{order_id}/status",
        headers=headers,
        json={"status": "ACCEPTED"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Order cannot be accepted until payment is confirmed."


def test_refunded_payment_order_cannot_be_accepted():
    """Authoritative test: REFUNDED payment order cannot be accepted; rejected with 400."""
    db = TestingSessionLocal()
    order_id = _create_test_order(db, "ord-refunded-pay-005", "#PP1005", payment_status=PaymentStatus.REFUNDED)
    db.close()

    admin_token = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])
    headers = {"Authorization": f"Bearer {admin_token}"}

    response = client.patch(
        f"/api/v1/orders/{order_id}/status",
        headers=headers,
        json={"status": "ACCEPTED"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Order cannot be accepted until payment is confirmed."


def test_none_or_empty_payment_status_order_cannot_be_accepted():
    """Authoritative test: Missing / None payment status cannot be accepted; rejected with 400."""
    db = TestingSessionLocal()
    order_id = _create_test_order(db, "ord-none-pay-006", "#PP1006", payment_status=None)
    db.close()

    admin_token = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])
    headers = {"Authorization": f"Bearer {admin_token}"}

    response = client.patch(
        f"/api/v1/orders/{order_id}/status",
        headers=headers,
        json={"status": "ACCEPTED"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Order cannot be accepted until payment is confirmed."


def test_non_paid_order_remains_incoming_without_history_pollution():
    """Verifies that rejected acceptance leaves status as INCOMING and does not insert ACCEPTED history."""
    db = TestingSessionLocal()
    order_id = _create_test_order(db, "ord-pollute-check-007", "#PP1007", payment_status=PaymentStatus.PENDING)
    db.close()

    admin_token = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])
    headers = {"Authorization": f"Bearer {admin_token}"}

    response = client.patch(
        f"/api/v1/orders/{order_id}/status",
        headers=headers,
        json={"status": "ACCEPTED"}
    )
    assert response.status_code == 400

    db = TestingSessionLocal()
    db_order = db.query(Order).filter(Order.id == order_id).first()
    assert db_order.status == OrderStatus.INCOMING

    histories = db.query(OrderStatusHistory).filter(OrderStatusHistory.order_id == order_id).all()
    assert not any(h.to_status == OrderStatus.ACCEPTED for h in histories)
    db.close()


def test_stale_client_cannot_bypass_backend_when_payment_is_unpaid():
    """
    Simulates race condition: Client believes order is ready to accept, but backend
    checks authoritative database payment state which is PENDING -> Must be rejected.
    """
    db = TestingSessionLocal()
    order_id = _create_test_order(db, "ord-race-008", "#PP1008", payment_status=PaymentStatus.PENDING)
    db.close()

    admin_token = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Direct API request trying to force ACCEPTED
    response = client.patch(
        f"/api/v1/orders/{order_id}/status",
        headers=headers,
        json={"status": "ACCEPTED", "notes": "Client attempting acceptance"}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Order cannot be accepted until payment is confirmed."


# =============================================================================
# 2. PRESERVATION OF EXISTING LIFECYCLE TRANSITIONS & RBAC
# =============================================================================

def test_other_order_transitions_remain_intact():
    """Verifies that normal lifecycle transitions beyond ACCEPTED remain unaffected."""
    db = TestingSessionLocal()
    order_id = _create_test_order(db, "ord-lifecycle-009", "#PP1009", status=OrderStatus.ACCEPTED, payment_status=PaymentStatus.PAID)
    db.close()

    admin_token = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. ACCEPTED -> PREPARING
    r1 = client.patch(f"/api/v1/orders/{order_id}/status", headers=headers, json={"status": "PREPARING"})
    assert r1.status_code == 200
    assert r1.json()["status"] == OrderStatus.PREPARING

    # 2. PREPARING -> READY
    r2 = client.patch(f"/api/v1/orders/{order_id}/status", headers=headers, json={"status": "READY"})
    assert r2.status_code == 200
    assert r2.json()["status"] == OrderStatus.READY

    # 3. READY -> DELIVERED
    r3 = client.patch(f"/api/v1/orders/{order_id}/status", headers=headers, json={"status": "DELIVERED"})
    assert r3.status_code == 200
    assert r3.json()["status"] == OrderStatus.DELIVERED


def test_incoming_order_can_be_cancelled_regardless_of_payment():
    """Verifies that cancellation of an INCOMING order remains supported."""
    db = TestingSessionLocal()
    order_id = _create_test_order(db, "ord-cancel-010", "#PP1010", payment_status=PaymentStatus.PENDING)
    db.close()

    admin_token = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])
    headers = {"Authorization": f"Bearer {admin_token}"}

    response = client.patch(
        f"/api/v1/orders/{order_id}/status",
        headers=headers,
        json={"status": "CANCELLED", "notes": "Customer requested cancellation"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == OrderStatus.CANCELLED


def test_branch_admin_authorization_preserved_on_paid_order():
    """Verifies Branch Admin can accept PAID orders for assigned branch, but 403 on unassigned branch."""
    db = TestingSessionLocal()
    branch_admin = User(
        id="user-camden-admin-test",
        email="camden_admin_test@patty.co.uk",
        full_name="Camden Admin",
        role=UserRole.BRANCH_ADMIN,
        is_active=True
    )
    bu = BranchUser(user_id=branch_admin.id, branch_id="branch-camden-001")
    db.add_all([branch_admin, bu])

    camden_paid_id = _create_test_order(db, "ord-camden-paid", "#PP-C-01", branch_id="branch-camden-001", payment_status=PaymentStatus.PAID)
    westfield_paid_id = _create_test_order(db, "ord-westfield-paid", "#PP-W-01", branch_id="branch-westfield-002", payment_status=PaymentStatus.PAID)
    db.close()

    ba_token = create_access_token(subject="user-camden-admin-test", roles=[UserRole.BRANCH_ADMIN])
    headers = {"Authorization": f"Bearer {ba_token}"}

    # 1. Assigned branch (Camden) -> 200 OK
    res_camden = client.patch(
        f"/api/v1/orders/{camden_paid_id}/status",
        headers=headers,
        json={"status": "ACCEPTED"}
    )
    assert res_camden.status_code == 200
    assert res_camden.json()["status"] == OrderStatus.ACCEPTED

    # 2. Unassigned branch (Westfield) -> 403 Forbidden
    res_westfield = client.patch(
        f"/api/v1/orders/{westfield_paid_id}/status",
        headers=headers,
        json={"status": "ACCEPTED"}
    )
    assert res_westfield.status_code == 403
    assert "outside assigned branch" in res_westfield.json()["detail"]


def test_unauthenticated_and_customer_cannot_update_status():
    """Verifies unauthenticated callers and customers cannot update status (401/403)."""
    db = TestingSessionLocal()
    order_id = _create_test_order(db, "ord-auth-check", "#PP-AUTH", payment_status=PaymentStatus.PAID)
    cust = User(id="user-cust-test-1", email="cust@patty.co.uk", full_name="Cust", role=UserRole.CUSTOMER, is_active=True)
    db.add(cust)
    db.commit()
    db.close()

    # 1. Unauthenticated -> 401
    r_unauth = client.patch(f"/api/v1/orders/{order_id}/status", json={"status": "ACCEPTED"})
    assert r_unauth.status_code == 401

    # 2. Customer -> 403
    cust_token = create_access_token(subject="user-cust-test-1", roles=[UserRole.CUSTOMER])
    r_cust = client.patch(
        f"/api/v1/orders/{order_id}/status",
        headers={"Authorization": f"Bearer {cust_token}"},
        json={"status": "ACCEPTED"}
    )
    assert r_cust.status_code == 403
