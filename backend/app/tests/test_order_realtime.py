import sys
import pathlib
import pytest
from datetime import datetime, timedelta, timezone

backend_root = pathlib.Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.tests.db import client, reset_test_db, TestingSessionLocal
from app.models import (
    User, UserRole, Branch, BranchUser, Order, OrderItem,
    OrderStatus, OrderType, PaymentStatus
)
from app.core.security import get_password_hash, create_access_token
from app.core.websocket_manager import manager, format_order_payload
from app.services.payment_service import process_payment_event, NormalizedPaymentEvent
from app.models.payment import Payment, PaymentProvider


@pytest.fixture(autouse=True)
def setup_realtime_environment():
    reset_test_db()
    db = TestingSessionLocal()

    # 1. Branch Admin - Camden
    camden_admin = User(
        id="user-camden-admin-01",
        email="camden.admin@pattyproject.co.uk",
        password_hash=get_password_hash("CamdenAdmin123!"),
        full_name="Camden Admin User",
        role=UserRole.BRANCH_ADMIN,
        is_active=True,
        email_verified=True
    )
    db.add(camden_admin)
    db.flush()

    bu_camden = BranchUser(
        user_id="user-camden-admin-01",
        branch_id="branch-camden-001"
    )
    db.add(bu_camden)

    # 2. Branch Admin - Westfield
    westfield_admin = User(
        id="user-westfield-admin-01",
        email="westfield.admin@pattyproject.co.uk",
        password_hash=get_password_hash("WestfieldAdmin123!"),
        full_name="Westfield Admin User",
        role=UserRole.BRANCH_ADMIN,
        is_active=True,
        email_verified=True
    )
    db.add(westfield_admin)
    db.flush()

    bu_westfield = BranchUser(
        user_id="user-westfield-admin-01",
        branch_id="branch-westfield-002"
    )
    db.add(bu_westfield)

    # 3. Standard Customer
    customer = User(
        id="user-cust-01",
        email="customer@example.com",
        password_hash=get_password_hash("Customer123!"),
        full_name="John Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=True
    )
    db.add(customer)

    # 4. Sample Order
    test_order = Order(
        id="order-rt-001",
        order_number="#PP9001",
        customer_name="Test Customer",
        customer_email="customer@example.com",
        customer_phone="+447123456789",
        branch_id="branch-camden-001",
        order_type=OrderType.COLLECTION,
        status=OrderStatus.INCOMING,
        subtotal=20.0,
        delivery_fee=0.0,
        service_fee=0.0,
        discount_amount=0.0,
        vat_amount=4.0,
        total_amount=20.0,
        payment_status=PaymentStatus.PAID
    )
    db.add(test_order)
    db.commit()
    db.close()


def test_websocket_auth_super_admin_success():
    token = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])
    with client.websocket_connect(f"/api/v1/admin/ws/orders?token={token}") as ws:
        data = ws.receive_json()
        assert data["type"] == "CONNECTED"
        assert data["user_id"] == "user-superadmin-001"
        assert data["role"] == UserRole.SUPER_ADMIN


def test_websocket_auth_branch_admin_success():
    token = create_access_token(subject="user-camden-admin-01", roles=[UserRole.BRANCH_ADMIN])
    with client.websocket_connect(f"/api/v1/admin/ws/orders?token={token}") as ws:
        data = ws.receive_json()
        assert data["type"] == "CONNECTED"
        assert data["user_id"] == "user-camden-admin-01"
        assert data["role"] == UserRole.BRANCH_ADMIN
        assert "branch-camden-001" in data["branch_ids"]


def test_websocket_auth_missing_token_rejected():
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/admin/ws/orders"):
            pass


def test_websocket_auth_invalid_token_rejected():
    with pytest.raises(Exception):
        with client.websocket_connect("/api/v1/admin/ws/orders?token=invalid.token.payload"):
            pass


def test_websocket_auth_expired_token_rejected():
    expired_token = create_access_token(
        subject="user-superadmin-001",
        roles=[UserRole.SUPER_ADMIN],
        expires_delta=timedelta(seconds=-60)
    )
    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/v1/admin/ws/orders?token={expired_token}") as ws:
            ws.receive_json()


def test_websocket_auth_customer_token_rejected():
    customer_token = create_access_token(subject="user-cust-01", roles=[UserRole.CUSTOMER])
    with pytest.raises(Exception):
        with client.websocket_connect(f"/api/v1/admin/ws/orders?token={customer_token}") as ws:
            ws.receive_json()


def test_websocket_ping_pong():
    token = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])
    with client.websocket_connect(f"/api/v1/admin/ws/orders?token={token}") as ws:
        _ = ws.receive_json()  # Handshake CONNECTED
        ws.send_json({"type": "PING"})
        pong = ws.receive_json()
        assert pong["type"] == "PONG"
        assert "timestamp" in pong


def test_websocket_branch_isolation():
    token_camden = create_access_token(subject="user-camden-admin-01", roles=[UserRole.BRANCH_ADMIN])
    token_westfield = create_access_token(subject="user-westfield-admin-01", roles=[UserRole.BRANCH_ADMIN])
    token_super = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])

    with client.websocket_connect(f"/api/v1/admin/ws/orders?token={token_camden}") as ws_camden, \
         client.websocket_connect(f"/api/v1/admin/ws/orders?token={token_westfield}") as ws_westfield, \
         client.websocket_connect(f"/api/v1/admin/ws/orders?token={token_super}") as ws_super:

        # Consume connection acks
        assert ws_camden.receive_json()["type"] == "CONNECTED"
        assert ws_westfield.receive_json()["type"] == "CONNECTED"
        assert ws_super.receive_json()["type"] == "CONNECTED"

        # Broadcast event for Camden branch
        order_payload = {
            "id": "order-rt-001",
            "order_number": "#PP9001",
            "branch_id": "branch-camden-001",
            "status": "INCOMING",
            "payment_status": "PAID"
        }
        manager.sync_broadcast_order_event(
            event_type="ORDER_INCOMING",
            order_data=order_payload,
            branch_id="branch-camden-001"
        )

        # 1. Camden Admin MUST receive Camden event
        camden_msg = ws_camden.receive_json()
        assert camden_msg["type"] == "ORDER_INCOMING"
        assert camden_msg["order"]["branch_id"] == "branch-camden-001"

        # 2. Super Admin MUST receive Camden event
        super_msg = ws_super.receive_json()
        assert super_msg["type"] == "ORDER_INCOMING"
        assert super_msg["order"]["branch_id"] == "branch-camden-001"

        # 3. Westfield Admin MUST NOT receive Camden event (send ping to verify socket is idle)
        ws_westfield.send_json({"type": "PING"})
        westfield_pong = ws_westfield.receive_json()
        assert westfield_pong["type"] == "PONG"  # Directly received PONG without intervening Camden event


def test_order_status_accept_broadcast_and_idempotency():
    token_super = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])

    with client.websocket_connect(f"/api/v1/admin/ws/orders?token={token_super}") as ws:
        _ = ws.receive_json()  # CONNECTED ack

        # Call status update endpoint to ACCEPT the order
        headers = {"Authorization": f"Bearer {token_super}"}
        res1 = client.patch(
            "/api/v1/orders/order-rt-001/status",
            json={"status": "ACCEPTED", "notes": "Accepted by kitchen"},
            headers=headers
        )
        assert res1.status_code == 200
        assert res1.json()["status"] == "ACCEPTED"

        # Verify WebSocket broadcast received
        msg = ws.receive_json()
        assert msg["type"] == "ORDER_STATUS_CHANGED"
        assert msg["order"]["id"] == "order-rt-001"
        assert msg["order"]["status"] == "ACCEPTED"

        # Call status update again with same status (Idempotent call)
        res2 = client.patch(
            "/api/v1/orders/order-rt-001/status",
            json={"status": "ACCEPTED", "notes": "Duplicate click"},
            headers=headers
        )
        assert res2.status_code == 200
        assert res2.json()["status"] == "ACCEPTED"


def test_webhook_payment_transition_broadcasts_incoming():
    db = TestingSessionLocal()
    # Create order in PENDING_PAYMENT state
    pending_order = Order(
        id="order-pending-webhook-01",
        order_number="#PP9002",
        customer_name="Webhook Customer",
        customer_email="wh@example.com",
        customer_phone="+447123456780",
        branch_id="branch-camden-001",
        order_type=OrderType.DELIVERY,
        status=OrderStatus.PENDING_PAYMENT,
        subtotal=25.0,
        total_amount=25.0,
        payment_status=PaymentStatus.PENDING
    )
    db.add(pending_order)
    db.commit()

    # Pre-create payment record
    pm = Payment(
        id="pm-wh-001",
        order_id="order-pending-webhook-01",
        provider=PaymentProvider.MOCK,
        transaction_id="TXN_WH_001",
        amount=25.0,
        currency="GBP",
        status=PaymentStatus.PENDING
    )
    db.add(pm)
    db.commit()
    db.close()

    token_camden = create_access_token(subject="user-camden-admin-01", roles=[UserRole.BRANCH_ADMIN])

    with client.websocket_connect(f"/api/v1/admin/ws/orders?token={token_camden}") as ws:
        _ = ws.receive_json()  # CONNECTED ack

        # Trigger payment event
        db_session = TestingSessionLocal()
        event = NormalizedPaymentEvent(
            event_id="evt_sq_unique_999",
            provider=PaymentProvider.MOCK,
            event_type="SUCCESS",
            order_id="order-pending-webhook-01",
            transaction_id="TXN_WH_001",
            amount=25.0,
            currency="GBP"
        )
        result = process_payment_event(db=db_session, event=event)
        db_session.close()

        assert result["status"] == "SUCCESS"

        # Verify WebSocket received ORDER_INCOMING
        msg = ws.receive_json()
        assert msg["type"] == "ORDER_INCOMING"
        assert msg["order"]["id"] == "order-pending-webhook-01"
        assert msg["order"]["status"] == "INCOMING"
        assert msg["order"]["payment_status"] == "PAID"


def test_payment_amount_mismatch_rejected():
    db = TestingSessionLocal()
    pending_order = Order(
        id="order-amount-mismatch-01",
        order_number="#PP9003",
        customer_name="Tampering Customer",
        customer_email="tamper@example.com",
        customer_phone="+447123456781",
        branch_id="branch-camden-001",
        order_type=OrderType.COLLECTION,
        status=OrderStatus.PENDING_PAYMENT,
        subtotal=50.0,
        total_amount=50.0,
        payment_status=PaymentStatus.PENDING
    )
    db.add(pending_order)
    pm = Payment(
        id="pm-tamper-001",
        order_id="order-amount-mismatch-01",
        provider=PaymentProvider.MOCK,
        transaction_id="TXN_TAMPER_001",
        amount=50.0,
        currency="GBP",
        status=PaymentStatus.PENDING
    )
    db.add(pm)
    db.commit()

    # Attempt payment event with £10 instead of £50
    event = NormalizedPaymentEvent(
        event_id="evt_tamper_100",
        provider=PaymentProvider.MOCK,
        event_type="SUCCESS",
        order_id="order-amount-mismatch-01",
        transaction_id="TXN_TAMPER_001",
        amount=10.0,
        currency="GBP"
    )
    with pytest.raises(ValueError, match="Amount mismatch"):
        process_payment_event(db=db, event=event)

    db.refresh(pending_order)
    # Order must remain PENDING_PAYMENT
    assert pending_order.status == OrderStatus.PENDING_PAYMENT
    assert pending_order.payment_status == PaymentStatus.PENDING
    db.close()


def test_payment_currency_mismatch_rejected():
    db = TestingSessionLocal()
    pending_order = Order(
        id="order-currency-mismatch-01",
        order_number="#PP9004",
        customer_name="Currency Customer",
        customer_email="curr@example.com",
        customer_phone="+447123456782",
        branch_id="branch-camden-001",
        order_type=OrderType.COLLECTION,
        status=OrderStatus.PENDING_PAYMENT,
        subtotal=20.0,
        total_amount=20.0,
        payment_status=PaymentStatus.PENDING
    )
    db.add(pending_order)
    pm = Payment(
        id="pm-curr-001",
        order_id="order-currency-mismatch-01",
        provider=PaymentProvider.MOCK,
        transaction_id="TXN_CURR_001",
        amount=20.0,
        currency="GBP",
        status=PaymentStatus.PENDING
    )
    db.add(pm)
    db.commit()

    # Attempt payment event with USD instead of GBP
    event = NormalizedPaymentEvent(
        event_id="evt_curr_100",
        provider=PaymentProvider.MOCK,
        event_type="SUCCESS",
        order_id="order-currency-mismatch-01",
        transaction_id="TXN_CURR_001",
        amount=20.0,
        currency="USD"
    )
    with pytest.raises(ValueError, match="Invalid currency"):
        process_payment_event(db=db, event=event)

    db.refresh(pending_order)
    assert pending_order.status == OrderStatus.PENDING_PAYMENT
    db.close()


def test_duplicate_webhook_idempotent_no_duplicate_alert():
    db = TestingSessionLocal()
    order = Order(
        id="order-dup-webhook-01",
        order_number="#PP9005",
        customer_name="Dup Webhook Cust",
        customer_email="dup@example.com",
        customer_phone="+447123456783",
        branch_id="branch-camden-001",
        order_type=OrderType.DELIVERY,
        status=OrderStatus.PENDING_PAYMENT,
        subtotal=30.0,
        total_amount=30.0,
        payment_status=PaymentStatus.PENDING
    )
    db.add(order)
    pm = Payment(
        id="pm-dup-001",
        order_id="order-dup-webhook-01",
        provider=PaymentProvider.MOCK,
        transaction_id="TXN_DUP_001",
        amount=30.0,
        currency="GBP",
        status=PaymentStatus.PENDING
    )
    db.add(pm)
    db.commit()

    event = NormalizedPaymentEvent(
        event_id="evt_idempotent_repeat_01",
        provider=PaymentProvider.MOCK,
        event_type="SUCCESS",
        order_id="order-dup-webhook-01",
        transaction_id="TXN_DUP_001",
        amount=30.0,
        currency="GBP"
    )

    # First delivery
    res1 = process_payment_event(db=db, event=event)
    assert res1["status"] == "SUCCESS"
    assert res1["order_status"] == OrderStatus.INCOMING

    # Second delivery with identical event_id (Duplicate webhook retry)
    res2 = process_payment_event(db=db, event=event)
    assert res2["status"] == "SUCCESS"
    assert "idempotent" in res2["message"].lower()

    db.refresh(order)
    assert order.status == OrderStatus.INCOMING
    db.close()


def test_failed_payment_event_no_incoming_alert():
    db = TestingSessionLocal()
    order = Order(
        id="order-fail-pay-01",
        order_number="#PP9006",
        customer_name="Failed Pay Cust",
        customer_email="fail@example.com",
        customer_phone="+447123456784",
        branch_id="branch-camden-001",
        order_type=OrderType.COLLECTION,
        status=OrderStatus.PENDING_PAYMENT,
        subtotal=15.0,
        total_amount=15.0,
        payment_status=PaymentStatus.PENDING
    )
    db.add(order)
    pm = Payment(
        id="pm-fail-001",
        order_id="order-fail-pay-01",
        provider=PaymentProvider.MOCK,
        transaction_id="TXN_FAIL_001",
        amount=15.0,
        currency="GBP",
        status=PaymentStatus.PENDING
    )
    db.add(pm)
    db.commit()

    event = NormalizedPaymentEvent(
        event_id="evt_fail_01",
        provider=PaymentProvider.MOCK,
        event_type="FAILED",
        order_id="order-fail-pay-01",
        transaction_id="TXN_FAIL_001",
        amount=15.0,
        currency="GBP",
        error_code="CARD_DECLINED",
        error_message="Insufficient funds on card"
    )

    res = process_payment_event(db=db, event=event)
    assert res["status"] == "SUCCESS"

    db.refresh(order)
    assert order.status == OrderStatus.PENDING_PAYMENT  # Order not marked as incoming
    assert order.payment_status == PaymentStatus.FAILED
    db.close()


def test_terminal_state_transition_rejected():
    db = TestingSessionLocal()
    cancelled_order = Order(
        id="order-cancelled-01",
        order_number="#PP9007",
        customer_name="Cancelled Cust",
        customer_email="canc@example.com",
        customer_phone="+447123456785",
        branch_id="branch-camden-001",
        order_type=OrderType.COLLECTION,
        status=OrderStatus.CANCELLED,
        subtotal=20.0,
        total_amount=20.0,
        payment_status=PaymentStatus.CANCELLED
    )
    db.add(cancelled_order)
    db.commit()
    db.close()

    token_super = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])
    headers = {"Authorization": f"Bearer {token_super}"}

    # Attempt to reopen a CANCELLED order to ACCEPTED
    res = client.patch(
        "/api/v1/orders/order-cancelled-01/status",
        json={"status": "ACCEPTED", "notes": "Attempting invalid reopen"},
        headers=headers
    )
    assert res.status_code == 400
    assert "terminal" in res.json()["detail"].lower()


def test_reconnect_resynchronization_via_rest():
    token_camden = create_access_token(subject="user-camden-admin-01", roles=[UserRole.BRANCH_ADMIN])
    headers = {"Authorization": f"Bearer {token_camden}"}

    # Admin fetches orders list via REST
    res = client.get("/api/v1/orders", headers=headers)
    assert res.status_code == 200
    orders_list = res.json()
    assert isinstance(orders_list, list)
    # The seeded Camden order (#PP9001) is in INCOMING state
    camden_orders = [o for o in orders_list if o["id"] == "order-rt-001"]
    assert len(camden_orders) == 1
    assert camden_orders[0]["status"] == OrderStatus.INCOMING


def test_multi_order_alert_flow_sequential_accept():
    """
    Validates the end-to-end alert life cycle for multiple concurrent orders:
    1. Three orders arrive and transition to INCOMING + PAID.
    2. SuperAdmin receives all 3 ORDER_INCOMING WebSocket events.
    3. Orders are accepted one by one; each emits ORDER_STATUS_CHANGED.
    """
    db = TestingSessionLocal()
    order_ids = ["order-multi-001", "order-multi-002", "order-multi-003"]
    for i, oid in enumerate(order_ids, start=1):
        ord_obj = Order(
            id=oid,
            order_number=f"#PP800{i}",
            customer_name=f"Customer {i}",
            customer_email=f"cust{i}@example.com",
            customer_phone=f"+44710000000{i}",
            branch_id="branch-camden-001",
            order_type=OrderType.DELIVERY,
            status=OrderStatus.PENDING_PAYMENT,
            subtotal=20.0 + i,
            total_amount=20.0 + i,
            payment_status=PaymentStatus.PENDING
        )
        db.add(ord_obj)
        pm = Payment(
            id=f"pm-multi-00{i}",
            order_id=oid,
            provider=PaymentProvider.MOCK,
            transaction_id=f"TXN_MULTI_00{i}",
            amount=20.0 + i,
            currency="GBP",
            status=PaymentStatus.PENDING
        )
        db.add(pm)
    db.commit()
    db.close()

    token_super = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])
    headers = {"Authorization": f"Bearer {token_super}"}

    with client.websocket_connect(f"/api/v1/admin/ws/orders?token={token_super}") as ws:
        assert ws.receive_json()["type"] == "CONNECTED"

        # 1. Trigger payment confirmations for all 3 orders
        for i, oid in enumerate(order_ids, start=1):
            db_s = TestingSessionLocal()
            evt = NormalizedPaymentEvent(
                event_id=f"evt_multi_pay_00{i}",
                provider=PaymentProvider.MOCK,
                event_type="SUCCESS",
                order_id=oid,
                transaction_id=f"TXN_MULTI_00{i}",
                amount=20.0 + i,
                currency="GBP"
            )
            res = process_payment_event(db=db_s, event=evt)
            db_s.close()
            assert res["status"] == "SUCCESS"

            msg = ws.receive_json()
            assert msg["type"] == "ORDER_INCOMING"
            assert msg["order"]["id"] == oid
            assert msg["order"]["status"] == OrderStatus.INCOMING
            assert msg["order"]["payment_status"] == PaymentStatus.PAID

        # 2. Sequentially accept order 1, order 2, order 3
        for oid in order_ids:
            accept_res = client.patch(
                f"/api/v1/orders/{oid}/status",
                json={"status": "ACCEPTED", "notes": f"Accepted {oid}"},
                headers=headers
            )
            assert accept_res.status_code == 200
            assert accept_res.json()["status"] == OrderStatus.ACCEPTED

            status_msg = ws.receive_json()
            assert status_msg["type"] == "ORDER_STATUS_CHANGED"
            assert status_msg["order"]["id"] == oid
            assert status_msg["order"]["status"] == OrderStatus.ACCEPTED


def test_super_admin_receives_multi_branch_orders_unhindered():
    """
    Validates that SuperAdmin receives ORDER_INCOMING events across ALL branches
    without branch filtering interference.
    """
    token_super = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])

    with client.websocket_connect(f"/api/v1/admin/ws/orders?token={token_super}") as ws:
        assert ws.receive_json()["type"] == "CONNECTED"

        # Broadcast from Camden
        manager.sync_broadcast_order_event(
            event_type="ORDER_INCOMING",
            order_data={"id": "ord-cam-1", "branch_id": "branch-camden-001", "status": "INCOMING"},
            branch_id="branch-camden-001"
        )
        msg1 = ws.receive_json()
        assert msg1["type"] == "ORDER_INCOMING"
        assert msg1["order"]["branch_id"] == "branch-camden-001"

        # Broadcast from Westfield
        manager.sync_broadcast_order_event(
            event_type="ORDER_INCOMING",
            order_data={"id": "ord-west-1", "branch_id": "branch-westfield-002", "status": "INCOMING"},
            branch_id="branch-westfield-002"
        )
        msg2 = ws.receive_json()
        assert msg2["type"] == "ORDER_INCOMING"
        assert msg2["order"]["branch_id"] == "branch-westfield-002"


def test_order_rejection_emits_status_changed():
    """
    Validates that rejecting or cancelling an incoming order emits ORDER_STATUS_CHANGED,
    which allows the frontend to remove the alert and stop the alarm.
    """
    db = TestingSessionLocal()
    order = Order(
        id="order-reject-001",
        order_number="#PP8099",
        customer_name="Reject Customer",
        customer_email="rej@example.com",
        customer_phone="+447100000099",
        branch_id="branch-camden-001",
        order_type=OrderType.DELIVERY,
        status=OrderStatus.INCOMING,
        subtotal=30.0,
        total_amount=30.0,
        payment_status=PaymentStatus.PAID
    )
    db.add(order)
    db.commit()
    db.close()

    token_super = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])
    headers = {"Authorization": f"Bearer {token_super}"}

    with client.websocket_connect(f"/api/v1/admin/ws/orders?token={token_super}") as ws:
        assert ws.receive_json()["type"] == "CONNECTED"

        res = client.patch(
            "/api/v1/orders/order-reject-001/status",
            json={"status": "REJECTED", "notes": "Kitchen out of stock"},
            headers=headers
        )
        assert res.status_code == 200
        assert res.json()["status"] == OrderStatus.REJECTED

        msg = ws.receive_json()
        assert msg["type"] == "ORDER_STATUS_CHANGED"
        assert msg["order"]["id"] == "order-reject-001"
        assert msg["order"]["status"] == OrderStatus.REJECTED


def test_unfiltered_incoming_orders_reconciliation():
    """
    Validates that GET /api/v1/orders?status=INCOMING returns all active unaccepted paid orders
    for authoritative alert state reconciliation.
    """
    token_super = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])
    headers = {"Authorization": f"Bearer {token_super}"}

    res = client.get("/api/v1/orders?status=INCOMING", headers=headers)
    assert res.status_code == 200
    orders = res.json()
    assert isinstance(orders, list)
    # All returned orders must have status == 'INCOMING'
    for o in orders:
        assert o["status"] == OrderStatus.INCOMING
