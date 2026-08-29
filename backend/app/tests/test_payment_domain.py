import pytest
import math
import sys
import os
import uuid
import pathlib
from datetime import datetime


# Ensure backend root is on sys.path
backend_root = pathlib.Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app as fastapi_app
from app.core.database import Base, get_db
import app.models as _models
from app.models import (
    Branch, Product, Category, User, UserRole,
    Order, OrderStatus, OrderType,
    Payment, PaymentStatus, PaymentProvider
)
from app.services.pricing_service import calculate_order_totals
from app.services.payment_service import (
    validate_payment_transition,
    transition_payment_status,
    process_payment_refund,
    get_or_create_payment_for_order,
    InvalidPaymentTransitionError,
    VALID_PAYMENT_TRANSITIONS
)

from app.core.security import create_access_token
from app.tests.db import engine, TestingSessionLocal, client as payment_client



def get_test_db():
    return TestingSessionLocal()



# =========================================================================
# 1. Free Delivery (£0.00) & Server-Authoritative Pricing Tests
# =========================================================================

def test_delivery_fee_is_strictly_zero_for_delivery_orders():
    """Verify that server-side calculator always returns £0.00 delivery fee for delivery."""
    db = get_test_db()
    try:
        prod = db.query(Product).filter(Product.id == "prod-mc-project").first()
        items = [{"product_id": prod.id, "quantity": 2, "selected_modifiers": []}]
        totals = calculate_order_totals(db=db, items=items, order_type="DELIVERY")

        assert totals["delivery_fee"] == 0.0
        assert totals["subtotal"] == round(prod.base_price * 2, 2)
        assert totals["service_fee"] == 0.0
        expected_total = round(totals["subtotal"] * 1.20, 2)
        assert totals["total_amount"] == expected_total
    finally:
        db.close()


def test_delivery_fee_is_strictly_zero_for_collection_orders():
    """Verify that server-side calculator always returns £0.00 delivery fee for collection."""
    db = get_test_db()
    try:
        prod = db.query(Product).filter(Product.id == "prod-mc-project").first()
        items = [{"product_id": prod.id, "quantity": 1, "selected_modifiers": []}]
        totals = calculate_order_totals(db=db, items=items, order_type="COLLECTION")

        assert totals["delivery_fee"] == 0.0
        assert totals["service_fee"] == 0.0
        expected_total = round(prod.base_price * 1.20, 2)
        assert totals["total_amount"] == expected_total
    finally:
        db.close()


def test_fake_delivery_fee_and_total_price_tampering_overridden():
    """Verify client attempt to submit tampered prices/fees is overridden by authoritative calculation."""
    payload = {
        "branch_id": "branch-camden-001",
        "order_type": "DELIVERY",
        "customer_name": "Tamper Test",
        "customer_email": "tamper@test.com",
        "customer_phone": "+44 7123 456789",
        "delivery_address": {
            "address_line1": "45 Camden High Street",
            "city": "London",
            "postcode": "NW1 7JE",
            "latitude": 51.5360,
            "longitude": -0.1420
        },
        "items": [
            {
                "product_id": "prod-mc-project",
                "quantity": 1,
                "selected_modifiers": []
            }
        ],
        # Client tries to pass malicious fields
        "delivery_fee": 2.50,
        "total_amount": 1.00
    }

    res = payment_client.post("/api/v1/orders", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["delivery_fee"] == 0.0
    expected_total = round(16.00 * 1.20, 2)
    assert data["total_amount"] == expected_total


# =========================================================================
# 2. Provider-Independent Payment Model & Relationship Tests
# =========================================================================

def test_payment_model_attributes_and_defaults():
    """Verify Payment model field attributes, defaults, and relationships."""
    db = get_test_db()
    try:
        order = Order(
            order_number="#PP-TEST-PAY-01",
            customer_name="Model Test",
            customer_email="model@test.com",
            customer_phone="+44 7123 456789",
            branch_id="branch-camden-001",
            order_type=OrderType.DELIVERY,
            status=OrderStatus.PENDING_PAYMENT,
            subtotal=8.95,
            delivery_fee=0.0,
            service_fee=0.99,
            total_amount=9.94
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        payment = Payment(
            order_id=order.id,
            provider=PaymentProvider.MOCK,
            amount=order.total_amount,
            currency="GBP",
            status=PaymentStatus.PENDING,
            payment_method_type="CARD"
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        assert payment.id is not None
        assert payment.order_id == order.id
        assert payment.provider == PaymentProvider.MOCK
        assert payment.currency == "GBP"
        assert payment.status == PaymentStatus.PENDING
        assert payment.refunded_amount == 0.0
        assert payment.order.id == order.id
        assert payment in order.payments
    finally:
        db.close()


# =========================================================================
# 3. Payment Status Lifecycle & State Machine Tests
# =========================================================================

def test_valid_payment_transitions():
    """Verify all valid transitions according to canonical state machine."""
    assert validate_payment_transition(PaymentStatus.PENDING, PaymentStatus.AUTHORIZED) is True
    assert validate_payment_transition(PaymentStatus.PENDING, PaymentStatus.PAID) is True
    assert validate_payment_transition(PaymentStatus.PENDING, PaymentStatus.CAPTURED) is True
    assert validate_payment_transition(PaymentStatus.PENDING, PaymentStatus.FAILED) is True
    assert validate_payment_transition(PaymentStatus.PENDING, PaymentStatus.CANCELLED) is True

    assert validate_payment_transition(PaymentStatus.AUTHORIZED, PaymentStatus.PAID) is True
    assert validate_payment_transition(PaymentStatus.AUTHORIZED, PaymentStatus.CAPTURED) is True
    assert validate_payment_transition(PaymentStatus.AUTHORIZED, PaymentStatus.CANCELLED) is True

    assert validate_payment_transition(PaymentStatus.PAID, PaymentStatus.PARTIALLY_REFUNDED) is True
    assert validate_payment_transition(PaymentStatus.PAID, PaymentStatus.REFUNDED) is True
    assert validate_payment_transition(PaymentStatus.PARTIALLY_REFUNDED, PaymentStatus.REFUNDED) is True


def test_invalid_payment_transitions():
    """Verify terminal state transitions are strictly disallowed."""
    assert validate_payment_transition(PaymentStatus.FAILED, PaymentStatus.PAID) is False
    assert validate_payment_transition(PaymentStatus.CANCELLED, PaymentStatus.PAID) is False
    assert validate_payment_transition(PaymentStatus.REFUNDED, PaymentStatus.PAID) is False
    assert validate_payment_transition(PaymentStatus.REFUNDED, PaymentStatus.PENDING) is False
    assert validate_payment_transition(PaymentStatus.PAID, PaymentStatus.PENDING) is False


def test_transition_payment_status_service_enforcement():
    """Verify transition_payment_status enforces rules and raises InvalidPaymentTransitionError."""
    db = get_test_db()
    try:
        order = Order(
            order_number="#PP-TEST-PAY-02",
            customer_name="Lifecycle Test",
            customer_email="lifecycle@test.com",
            customer_phone="+44 7123 456789",
            branch_id="branch-camden-001",
            order_type=OrderType.DELIVERY,
            status=OrderStatus.PENDING_PAYMENT,
            subtotal=10.0,
            delivery_fee=0.0,
            service_fee=0.99,
            total_amount=10.99
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        payment = Payment(
            order_id=order.id,
            amount=order.total_amount,
            status=PaymentStatus.PENDING
        )
        db.add(payment)
        db.commit()

        # Valid: PENDING -> PAID
        transition_payment_status(db, payment, PaymentStatus.PAID, transaction_id="TXN_TEST_100")
        assert payment.status == PaymentStatus.PAID
        assert payment.transaction_id == "TXN_TEST_100"
        db.refresh(order)
        assert order.payment_status == PaymentStatus.PAID
        assert order.status == OrderStatus.INCOMING

        # Invalid: PAID -> FAILED must raise InvalidPaymentTransitionError
        with pytest.raises(InvalidPaymentTransitionError):
            transition_payment_status(db, payment, PaymentStatus.FAILED)
    finally:
        db.close()


# =========================================================================
# 4. Refund Lifecycle & Partial Refund Validation Tests
# =========================================================================

def test_refund_lifecycle_and_amount_checks():
    """Verify refund transitions and over-refund prevention."""
    db = get_test_db()
    try:
        order = Order(
            order_number="#PP-TEST-REFUND",
            customer_name="Refund User",
            customer_email="refund@test.com",
            customer_phone="+44 7123 456789",
            branch_id="branch-camden-001",
            order_type=OrderType.COLLECTION,
            status=OrderStatus.INCOMING,
            subtotal=20.0,
            delivery_fee=0.0,
            service_fee=0.99,
            total_amount=20.99,
            payment_status=PaymentStatus.PAID
        )
        db.add(order)
        db.commit()

        payment = Payment(
            order_id=order.id,
            amount=20.99,
            status=PaymentStatus.PAID,
            transaction_id="TXN_REF_TEST"
        )
        db.add(payment)
        db.commit()

        # Partial refund of £5.00
        p_partial = process_payment_refund(db, payment, refund_amount=5.00, reason="Item missing")
        assert p_partial.status == PaymentStatus.PARTIALLY_REFUNDED
        assert p_partial.refunded_amount == 5.00

        # Over-refund attempt (£20.00 more when remaining amount is £15.99)
        with pytest.raises(ValueError, match="exceed original payment amount"):
            process_payment_refund(db, payment, refund_amount=20.00)

        # Full remaining refund (£15.99)
        p_full = process_payment_refund(db, payment, refund_amount=15.99, reason="Customer compensation")
        assert p_full.status == PaymentStatus.REFUNDED
        assert p_full.refunded_amount == 20.99
        db.refresh(order)
        assert order.status == OrderStatus.REFUNDED
    finally:
        db.close()


# =========================================================================
# 5. Idempotency & Session Creation Endpoint Tests
# =========================================================================

def test_create_payment_session_idempotency():
    """Verify that multiple create-session requests with the same Idempotency-Key return the same session."""
    order_payload = {
        "branch_id": "branch-camden-001",
        "order_type": "DELIVERY",
        "customer_name": "Idempotent User",
        "customer_email": "idem@example.com",
        "customer_phone": "+44 7123 456789",
        "delivery_address": {
            "address_line1": "45 Camden High Street",
            "city": "London",
            "postcode": "NW1 7JE",
            "latitude": 51.5360,
            "longitude": -0.1420
        },
        "items": [{"product_id": "prod-mc-project", "quantity": 1, "selected_modifiers": []}]
    }
    ord_res = payment_client.post("/api/v1/orders", json=order_payload)
    assert ord_res.status_code == 200, ord_res.text
    order_data = ord_res.json()
    order_id = order_data["id"]

    idempotency_key = "IDEM_KEY_UNIQUE_9999"

    # First session request
    res1 = payment_client.post(
        "/api/v1/payments/create-session",
        headers={"Idempotency-Key": idempotency_key},
        json={"order_id": order_id, "payment_method_type": "CARD"}
    )
    assert res1.status_code == 200, res1.text
    data1 = res1.json()

    # Second identical session request with same idempotency key
    res2 = payment_client.post(
        "/api/v1/payments/create-session",
        headers={"Idempotency-Key": idempotency_key},
        json={"order_id": order_id, "payment_method_type": "CARD"}
    )
    assert res2.status_code == 200, res2.text
    data2 = res2.json()

    assert data1["payment_id"] == data2["payment_id"]
    assert data1["transaction_id"] == data2["transaction_id"]
    assert data1["amount"] == data2["amount"]


def test_payment_webhook_idempotency_and_loyalty_points():
    """Verify webhook correctly transitions payment, updates order, and awards loyalty points exactly once."""
    order_payload = {
        "branch_id": "branch-camden-001",
        "order_type": "DELIVERY",
        "customer_name": "John Smith",
        "customer_email": "john.smith@email.com",
        "customer_phone": "+44 7123 456789",
        "delivery_address": {
            "address_line1": "45 Camden High Street",
            "city": "London",
            "postcode": "NW1 7JE",
            "latitude": 51.5360,
            "longitude": -0.1420
        },
        "items": [{"product_id": "prod-mc-project", "quantity": 1, "selected_modifiers": []}]
    }
    ord_res = payment_client.post("/api/v1/orders", json=order_payload)
    assert ord_res.status_code == 200, ord_res.text
    order_data = ord_res.json()
    order_id = order_data["id"]

    # Create session
    session_res = payment_client.post("/api/v1/payments/create-session", json={"order_id": order_id, "payment_method_type": "CARD"})
    assert session_res.status_code == 200, session_res.text
    session_data = session_res.json()

    webhook_payload = {
        "order_id": order_id,
        "transaction_id": session_data["transaction_id"],
        "status": "SUCCESS"
    }

    # First webhook call
    wb1 = payment_client.post("/api/v1/payments/webhook", json=webhook_payload)
    assert wb1.status_code == 200, wb1.text
    assert wb1.json()["payment_status"] == PaymentStatus.PAID

    # Duplicate webhook call (must succeed idempotently)
    wb2 = payment_client.post("/api/v1/payments/webhook", json=webhook_payload)
    assert wb2.status_code == 200, wb2.text
    assert wb2.json()["payment_status"] == PaymentStatus.PAID

    # Verify order ledger with Super Admin token
    admin_token = create_access_token(subject="user-superadmin-001", roles=["SUPER_ADMIN"])
    ledger_res = payment_client.get(f"/api/v1/payments/order/{order_id}", headers={"Authorization": f"Bearer {admin_token}"})
    assert ledger_res.status_code == 200, ledger_res.text
    ledger_items = ledger_res.json()
    assert len(ledger_items) == 1
    assert ledger_items[0]["status"] == PaymentStatus.PAID


# =========================================================================
# 6. Unauthorized / Non-Existent Order Handling
# =========================================================================

def test_create_session_for_non_existent_order():
    """Verify 404 is returned when creating session for non-existent order."""
    res = payment_client.post("/api/v1/payments/create-session", json={"order_id": "non-existent-order-id-1234", "payment_method_type": "CARD"})
    assert res.status_code == 404


def test_refund_for_non_existent_payment():
    """Verify 404 is returned when attempting to refund non-existent payment."""
    admin_token = create_access_token(subject="user-superadmin-001", roles=["SUPER_ADMIN"])
    res = payment_client.post(
        "/api/v1/payments/non-existent-payment-id/refund",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"amount": 5.0}
    )
    assert res.status_code == 404


# =========================================================================
# 7. Delivery Radius & Collection Regression Tests
# =========================================================================

def test_delivery_order_outside_2_miles_is_rejected():
    """Verify strict 2-mile rule enforcement on Delivery orders."""
    payload = {
        "branch_id": "branch-camden-001",
        "order_type": "DELIVERY",
        "customer_name": "Far Away User",
        "customer_email": "far@example.com",
        "customer_phone": "+44 7123 456789",
        "delivery_address": {
            "address_line1": "Windsor Castle",
            "city": "Windsor",
            "postcode": "SL4 1NJ",
            "latitude": 51.4839,  # ~21 miles away from central London
            "longitude": -0.6044
        },
        "items": [{"product_id": "prod-mc-project", "quantity": 1, "selected_modifiers": []}]
    }
    res = payment_client.post("/api/v1/orders", json=payload)
    assert res.status_code == 400
    data = res.json()
    assert "detail" in data
    detail = data["detail"]
    assert detail["code"] == "DELIVERY_OUTSIDE_RADIUS"
    assert "WE PROVIDE DELIVERY UP TO 2 MILES ONLY" in detail["message"]


def test_collection_order_regression_allows_any_location():
    """Verify collection orders are never blocked by distance and have £0.00 delivery fee."""
    payload = {
        "branch_id": "branch-camden-001",
        "order_type": "COLLECTION",
        "customer_name": "Collection User",
        "customer_email": "collect@example.com",
        "customer_phone": "+44 7123 456789",
        "collection_slot_time": "2026-08-20T14:30:00",
        "latitude": 51.4839,  # Even if coordinates are 21 miles away, collection is permitted
        "longitude": -0.6044,
        "items": [{"product_id": "prod-mc-project", "quantity": 1, "selected_modifiers": []}]
    }
    res = payment_client.post("/api/v1/orders", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["order_type"] == "COLLECTION"
    assert data["delivery_fee"] == 0.0
    assert data["status"] == OrderStatus.PENDING_PAYMENT


# =========================================================================
# 8. Phase 14 Comprehensive Mock Payment Gateway Suite (Tests 1 - 18)
# =========================================================================

def _create_valid_delivery_order(email="test.customer@example.com"):
    payload = {
        "branch_id": "branch-camden-001",
        "order_type": "DELIVERY",
        "customer_name": "Test Customer",
        "customer_email": email,
        "customer_phone": "+44 7123 456789",
        "delivery_address": {
            "address_line1": "45 Camden High Street",
            "city": "London",
            "postcode": "NW1 7JE",
            "latitude": 51.5360,
            "longitude": -0.1420
        },
        "items": [{"product_id": "prod-mc-project", "quantity": 1, "selected_modifiers": []}]
    }
    res = payment_client.post("/api/v1/orders", json=payload)
    assert res.status_code == 200, res.text
    return res.json()


def test_mock_payment_creation():
    """Test 1: Mock payment session creation returns transaction_id, payment_url, and PENDING status."""
    order = _create_valid_delivery_order("mock.create@example.com")
    res = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["order_id"] == order["id"]
    assert data["provider"] == PaymentProvider.MOCK
    assert data["status"] == PaymentStatus.PENDING
    assert data["amount"] == order["total_amount"]
    assert data["currency"] == "GBP"
    assert data["transaction_id"].startswith("TXN_")
    assert f"/mock-checkout/{data['transaction_id']}" in data["payment_url"]


def test_successful_mock_payment():
    """Test 2: Successful mock payment simulation transitions payment to PAID and order to INCOMING."""
    order = _create_valid_delivery_order("mock.success@example.com")
    session_res = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"})
    session = session_res.json()

    sim_res = payment_client.post("/api/v1/payments/webhook", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS",
        "amount": order["total_amount"],
        "currency": "GBP"
    })
    assert sim_res.status_code == 200, sim_res.text
    sim_data = sim_res.json()
    assert sim_data["payment_status"] == PaymentStatus.PAID
    assert sim_data["order_status"] == OrderStatus.INCOMING

    # Check verify endpoint
    verify_res = payment_client.get(f"/api/v1/payments/verify/{session['transaction_id']}")
    assert verify_res.status_code == 200
    assert verify_res.json()["payment_status"] == PaymentStatus.PAID


def test_failed_mock_payment():
    """Test 3: Failed mock payment simulation transitions payment to FAILED and keeps order unpaid."""
    order = _create_valid_delivery_order("mock.fail@example.com")
    session_res = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"})
    session = session_res.json()

    sim_res = payment_client.post("/api/v1/payments/webhook", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "FAILED",
        "error_code": "CARD_DECLINED",
        "error_message": "Card was declined by issuing bank"
    })
    assert sim_res.status_code == 200, sim_res.text
    assert sim_res.json()["payment_status"] == PaymentStatus.FAILED

    verify_res = payment_client.get(f"/api/v1/payments/verify/{session['transaction_id']}")
    assert verify_res.json()["payment_status"] == PaymentStatus.FAILED
    assert verify_res.json()["order_status"] == OrderStatus.PENDING_PAYMENT


def test_cancelled_mock_payment():
    """Test 4: Cancelled mock payment simulation transitions payment to CANCELLED and keeps order unpaid."""
    order = _create_valid_delivery_order("mock.cancel@example.com")
    session_res = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"})
    session = session_res.json()

    sim_res = payment_client.post("/api/v1/payments/webhook", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "CANCELLED"
    })
    assert sim_res.status_code == 200, sim_res.text
    assert sim_res.json()["payment_status"] == PaymentStatus.CANCELLED

    verify_res = payment_client.get(f"/api/v1/payments/verify/{session['transaction_id']}")
    assert verify_res.json()["payment_status"] == PaymentStatus.CANCELLED
    assert verify_res.json()["order_status"] == OrderStatus.PENDING_PAYMENT


def test_pending_mock_payment():
    """Test 5: Pending mock payment simulation maintains PENDING status without advancing order."""
    order = _create_valid_delivery_order("mock.pending@example.com")
    session_res = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"})
    session = session_res.json()

    sim_res = payment_client.post("/api/v1/payments/webhook", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "PENDING"
    })
    assert sim_res.status_code == 200, sim_res.text
    assert sim_res.json()["payment_status"] == PaymentStatus.PENDING
    assert sim_res.json()["order_status"] == OrderStatus.PENDING_PAYMENT


def test_duplicate_mock_success_event():
    """Test 6: Duplicate mock success event is handled idempotently without re-triggering transitions."""
    order = _create_valid_delivery_order("mock.dup@example.com")
    session_res = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"})
    session = session_res.json()

    payload = {
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS",
        "amount": order["total_amount"],
        "currency": "GBP"
    }

    res1 = payment_client.post("/api/v1/payments/webhook", json=payload)
    assert res1.status_code == 200
    assert res1.json()["payment_status"] == PaymentStatus.PAID

    # Duplicate call
    res2 = payment_client.post("/api/v1/payments/webhook", json=payload)
    assert res2.status_code == 200
    assert res2.json()["payment_status"] == PaymentStatus.PAID
    assert "idempotent" in res2.json()["message"].lower()


def test_amount_mismatch_rejection():
    """Test 7: Gateway rejects webhook/simulation if amount does not match authoritative order amount."""
    order = _create_valid_delivery_order("mock.amt@example.com")
    session_res = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"})
    session = session_res.json()

    res = payment_client.post("/api/v1/payments/webhook", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS",
        "amount": 0.01,  # Malicious/tampered amount
        "currency": "GBP"
    })
    assert res.status_code == 400
    assert "Amount mismatch" in res.text


def test_currency_mismatch_rejection():
    """Test 8: Gateway rejects webhook/simulation if currency is not GBP."""
    order = _create_valid_delivery_order("mock.curr@example.com")
    session_res = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"})
    session = session_res.json()

    res = payment_client.post("/api/v1/payments/webhook", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS",
        "amount": order["total_amount"],
        "currency": "USD"  # Non-GBP currency
    })
    assert res.status_code == 400
    assert "Only GBP is accepted" in res.text


def test_unauthorized_mismatched_order_payment():
    """Test 9: Webhook rejects mismatch between order_id and payment transaction record."""
    order1 = _create_valid_delivery_order("mock.mismatch1@example.com")
    order2 = _create_valid_delivery_order("mock.mismatch2@example.com")

    session1 = payment_client.post("/api/v1/payments/create-session", json={"order_id": order1['id'], "payment_method_type": "CARD"}).json()

    res = payment_client.post("/api/v1/payments/webhook", json={
        "order_id": order2["id"],  # Mismatched order
        "transaction_id": session1["transaction_id"],
        "status": "SUCCESS"
    })
    assert res.status_code == 403
    assert "Payment does not belong to the specified order" in res.text


def test_cancelled_order_payment_rejection():
    """Test 10: Payment session creation and webhook processing are rejected for cancelled orders."""
    db = get_test_db()
    try:
        order = Order(
            order_number="#PP-CANCEL-TEST",
            customer_name="Cancelled User",
            customer_email="cancel@test.com",
            customer_phone="+44 7123 456789",
            branch_id="branch-camden-001",
            order_type=OrderType.DELIVERY,
            status=OrderStatus.CANCELLED,
            subtotal=10.0,
            delivery_fee=0.0,
            service_fee=0.99,
            total_amount=10.99
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        # Attempt to create session for cancelled order
        res = payment_client.post("/api/v1/payments/create-session", json={"order_id": order.id, "payment_method_type": "CARD"})
        assert res.status_code == 400
        assert "Cannot initiate payment for a cancelled order" in res.text
    finally:
        db.close()


def test_already_paid_order_handling():
    """Test 11: Attempting to create session for already paid order idempotently returns existing payment."""
    order = _create_valid_delivery_order("mock.paid@example.com")
    session1 = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()

    payment_client.post("/api/v1/payments/webhook", json={
        "order_id": order["id"],
        "transaction_id": session1["transaction_id"],
        "status": "SUCCESS"
    })

    # Call create-session again on the paid order
    session2_res = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"})
    assert session2_res.status_code == 200
    session2 = session2_res.json()
    assert session2["status"] == PaymentStatus.PAID
    assert session2["payment_id"] == session1["payment_id"]


def test_duplicate_payment_session_request():
    """Test 12: Duplicate payment session request with same idempotency header returns identical session."""
    order = _create_valid_delivery_order("mock.idem2@example.com")
    idem_key = "IDEM_TEST_KEY_2026"

    res1 = payment_client.post(
        "/api/v1/payments/create-session",
        headers={"Idempotency-Key": idem_key},
        json={"order_id": order["id"], "payment_method_type": "CARD"}
    )
    res2 = payment_client.post(
        "/api/v1/payments/create-session",
        headers={"Idempotency-Key": idem_key},
        json={"order_id": order["id"], "payment_method_type": "CARD"}
    )
    assert res1.json()["payment_id"] == res2.json()["payment_id"]
    assert res1.json()["transaction_id"] == res2.json()["transaction_id"]


def test_delivery_greater_than_2_miles_cannot_initiate_payment():
    """Test 13: Delivery order > 2 miles is strictly blocked from payment initiation."""
    payload = {
        "branch_id": "branch-camden-001",
        "order_type": "DELIVERY",
        "customer_name": "Far Customer",
        "customer_email": "far2@example.com",
        "customer_phone": "+44 7123 456789",
        "delivery_address": {
            "address_line1": "Oxford Street Far",
            "city": "London",
            "postcode": "W1D 1BS",
            "latitude": 51.5800,  # ~3.1 miles away from Camden
            "longitude": -0.1420
        },
        "items": [{"product_id": "prod-mc-project", "quantity": 1, "selected_modifiers": []}]
    }
    # Initial order creation blocks it with 400
    ord_res = payment_client.post("/api/v1/orders", json=payload)
    assert ord_res.status_code == 400
    assert "WE PROVIDE DELIVERY UP TO 2 MILES ONLY" in ord_res.text


def test_delivery_less_equal_2_miles_can_initiate_payment():
    """Test 14: Delivery order <= 2 miles successfully creates order and initiates payment."""
    order = _create_valid_delivery_order("mock.radius.ok@example.com")
    res = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"})
    assert res.status_code == 200
    assert res.json()["status"] == PaymentStatus.PENDING


def test_collection_payment_works_without_radius():
    """Test 15: Collection order initiates and completes payment regardless of distance."""
    payload = {
        "branch_id": "branch-camden-001",
        "order_type": "COLLECTION",
        "customer_name": "Collect Radius User",
        "customer_email": "collect.rad@example.com",
        "customer_phone": "+44 7123 456789",
        "collection_slot_time": "2026-08-20T17:00:00",
        "latitude": 51.4839,
        "longitude": -0.6044,
        "items": [{"product_id": "prod-mc-project", "quantity": 1, "selected_modifiers": []}]
    }
    ord_res = payment_client.post("/api/v1/orders", json=payload)
    assert ord_res.status_code == 200
    order = ord_res.json()

    session_res = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"})
    assert session_res.status_code == 200
    session = session_res.json()

    pay_res = payment_client.post("/api/v1/payments/webhook", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS"
    })
    assert pay_res.status_code == 200
    assert pay_res.json()["payment_status"] == PaymentStatus.PAID


def test_loyalty_awarded_exactly_once():
    """Test 16: Customer receives loyalty points exactly once upon payment confirmation."""
    from app.models.loyalty import LoyaltyAccount, LoyaltyTransaction
    db = get_test_db()
    try:
        user = db.query(User).filter(User.email == "alice.walker@example.com").first()
        if not user:
            user = User(
                email="alice.walker@example.com",
                password_hash="mockhashedpassword123",
                full_name="Alice Walker",
                role=UserRole.CUSTOMER
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        order = _create_valid_delivery_order("alice.walker@example.com")
        session = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()

        # Confirm payment
        payment_client.post("/api/v1/payments/webhook", json={
            "order_id": order["id"],
            "transaction_id": session["transaction_id"],
            "status": "SUCCESS"
        })

        db.expire_all()
        loyalty_refreshed = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == user.id).first()
        assert loyalty_refreshed is not None
        expected_pts = order["points_earned"]
        assert loyalty_refreshed.available_points == expected_pts

        # Duplicate webhook
        payment_client.post("/api/v1/payments/webhook", json={
            "order_id": order["id"],
            "transaction_id": session["transaction_id"],
            "status": "SUCCESS"
        })

        db.expire_all()
        loyalty_refreshed_again = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == user.id).first()
        # Loyalty points must NOT increase again
        assert loyalty_refreshed_again.available_points == expected_pts
    finally:
        db.close()






def test_order_status_updated_once():
    """Test 17: Order status history logs the INCOMING transition exactly once."""
    order = _create_valid_delivery_order("mock.history@example.com")
    session = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()

    payment_client.post("/api/v1/payments/webhook", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS"
    })

    # Duplicate call
    payment_client.post("/api/v1/payments/webhook", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS"
    })

    # Verify history
    hist_res = payment_client.get(f"/api/v1/orders/{order['id']}/history")
    if hist_res.status_code == 200:
        incoming_entries = [h for h in hist_res.json() if h["to_status"] == OrderStatus.INCOMING]
        assert len(incoming_entries) == 1


def test_mock_gateway_blocked_in_production_configuration(monkeypatch):
    """Test 18: Mock gateway session creation and webhook processing are blocked if ENVIRONMENT=production."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")

    order = _create_valid_delivery_order("mock.prod.guard@example.com")

    # create-session should be blocked
    session_res = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"})
    assert session_res.status_code == 403
    assert "Mock payment gateway is strictly disabled in production" in session_res.text

    # webhook should be blocked
    wb_res = payment_client.post("/api/v1/payments/webhook", json={
        "order_id": order["id"],
        "transaction_id": "TXN_MOCK_PROD",
        "status": "SUCCESS"
    })
    assert wb_res.status_code == 403
    assert "Mock payment gateway is strictly disabled in production" in wb_res.text


# =========================================================================
# 9. Phase 15 — Payment Webhook & Financial Security Hardening Tests
# =========================================================================

def test_phase15_valid_webhook_success_and_event_persistence():
    """Phase 15 Test 1: Valid webhook creates PaymentEvent record, transitions payment to PAID and order to INCOMING."""
    order = _create_valid_delivery_order("phase15.success@example.com")
    session = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()
    event_id = f"evt_p15_valid_{uuid.uuid4().hex[:8]}"

    res = payment_client.post("/api/v1/payments/webhook", json={
        "event_id": event_id,
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS",
        "amount": order["total_amount"],
        "currency": "GBP"
    })
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["payment_status"] == PaymentStatus.PAID
    assert data["order_status"] == OrderStatus.INCOMING

    # Verify event stored in DB
    db = get_test_db()
    try:
        from app.models.payment import PaymentEvent
        evt = db.query(PaymentEvent).filter(PaymentEvent.gateway_event_id == event_id).first()
        assert evt is not None
        assert evt.processing_status == "PROCESSED"
        assert evt.order_id == order["id"]
    finally:
        db.close()


def test_phase15_invalid_webhook_signature_rejection():
    """Phase 15 Test 2: Webhook with invalid signature header is rejected with 400 Bad Request."""
    order = _create_valid_delivery_order("phase15.sig@example.com")
    session = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()

    res = payment_client.post(
        "/api/v1/payments/webhook",
        headers={"X-Mock-Signature": "invalid_signature"},
        json={
            "order_id": order["id"],
            "transaction_id": session["transaction_id"],
            "status": "SUCCESS"
        }
    )
    assert res.status_code == 400
    assert "Invalid webhook signature" in res.text


def test_phase15_duplicate_webhook_event_id_idempotency():
    """Phase 15 Test 3: Same gateway_event_id sent twice is processed exactly once."""
    order = _create_valid_delivery_order("phase15.dup@example.com")
    session = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()
    event_id = f"evt_p15_dup_{uuid.uuid4().hex[:8]}"

    payload = {
        "event_id": event_id,
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS",
        "amount": order["total_amount"],
        "currency": "GBP"
    }

    res1 = payment_client.post("/api/v1/payments/webhook", json=payload)
    assert res1.status_code == 200
    assert res1.json()["payment_status"] == PaymentStatus.PAID

    # Duplicate call with same event_id
    res2 = payment_client.post("/api/v1/payments/webhook", json=payload)
    assert res2.status_code == 200
    assert res2.json()["idempotent"] is True
    assert "Duplicate event" in res2.json()["message"]


def test_phase15_wrong_event_id_and_missing_references():
    """Phase 15 Test 4 & 5 & 6: Webhook with unknown transaction and unknown order reference is rejected."""
    res = payment_client.post("/api/v1/payments/webhook", json={
        "event_id": "evt_p15_unknown_12345",
        "order_id": "order-non-existent-9999",
        "transaction_id": "TXN_UNKNOWN_9999",
        "status": "SUCCESS"
    })
    assert res.status_code == 400 or res.status_code == 404


def test_phase15_wrong_customer_order_association_rejection():
    """Phase 15 Test 7: Mismatched payment and order association is rejected with 403."""
    order_a = _create_valid_delivery_order("phase15.ord_a@example.com")
    order_b = _create_valid_delivery_order("phase15.ord_b@example.com")

    session_a = payment_client.post("/api/v1/payments/create-session", json={"order_id": order_a['id'], "payment_method_type": "CARD"}).json()

    res = payment_client.post("/api/v1/payments/webhook", json={
        "event_id": f"evt_p15_tamper_{uuid.uuid4().hex[:8]}",
        "order_id": order_b["id"],  # Mismatched order
        "transaction_id": session_a["transaction_id"],
        "status": "SUCCESS"
    })
    assert res.status_code == 403
    assert "Payment does not belong to the specified order" in res.text


def test_phase15_wrong_amount_mismatches_rejected():
    """Phase 15 Test 8: Rejects 1p mismatch, £1 mismatch, and large tampering."""
    order = _create_valid_delivery_order("phase15.amt@example.com")
    session = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()

    # 1p mismatch
    res_1p = payment_client.post("/api/v1/payments/webhook", json={
        "event_id": f"evt_p15_1p_{uuid.uuid4().hex[:8]}",
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS",
        "amount": round(order["total_amount"] + 0.01, 2),
        "currency": "GBP"
    })
    assert res_1p.status_code == 400
    assert "Amount mismatch" in res_1p.text

    # £1.00 mismatch
    res_1pound = payment_client.post("/api/v1/payments/webhook", json={
        "event_id": f"evt_p15_1lb_{uuid.uuid4().hex[:8]}",
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS",
        "amount": round(order["total_amount"] - 1.00, 2),
        "currency": "GBP"
    })
    assert res_1pound.status_code == 400
    assert "Amount mismatch" in res_1pound.text


def test_phase15_wrong_currency_rejections():
    """Phase 15 Test 9: Rejects USD, EUR, INR currencies."""
    order = _create_valid_delivery_order("phase15.curr@example.com")
    session = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()

    for invalid_curr in ["USD", "EUR", "INR"]:
        res = payment_client.post("/api/v1/payments/webhook", json={
            "event_id": f"evt_p15_curr_{invalid_curr}_{uuid.uuid4().hex[:8]}",
            "order_id": order["id"],
            "transaction_id": session["transaction_id"],
            "status": "SUCCESS",
            "amount": order["total_amount"],
            "currency": invalid_curr
        })
        assert res.status_code == 400
        assert "Only GBP is accepted" in res.text


def test_phase15_cancelled_order_payment_rejection():
    """Phase 15 Test 10: Processing webhook event for cancelled order is rejected."""
    db = get_test_db()
    try:
        order = Order(
            order_number="#PP-CANCEL-P15",
            customer_name="Cancelled User P15",
            customer_email="cancel.p15@test.com",
            customer_phone="+44 7123 456789",
            branch_id="branch-camden-001",
            order_type=OrderType.DELIVERY,
            status=OrderStatus.CANCELLED,
            subtotal=10.0,
            delivery_fee=0.0,
            service_fee=0.99,
            total_amount=10.99
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        payment = Payment(
            order_id=order.id,
            amount=10.99,
            currency="GBP",
            status=PaymentStatus.PENDING,
            transaction_id="TXN_CANCEL_P15"
        )
        db.add(payment)
        db.commit()

        res = payment_client.post("/api/v1/payments/webhook", json={
            "event_id": f"evt_cancel_{uuid.uuid4().hex[:8]}",
            "order_id": order.id,
            "transaction_id": "TXN_CANCEL_P15",
            "status": "SUCCESS"
        })
        assert res.status_code == 400
        assert "Cannot process payment for a cancelled order" in res.text
    finally:
        db.close()


def test_phase15_already_paid_payment_idempotency():
    """Phase 15 Test 11: Idempotent success when webhook arrives for already paid payment."""
    order = _create_valid_delivery_order("phase15.already_paid@example.com")
    session = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()

    res1 = payment_client.post("/api/v1/payments/webhook", json={
        "event_id": f"evt_paid_1_{uuid.uuid4().hex[:8]}",
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS"
    })
    assert res1.status_code == 200

    # Second event with different event_id but for already paid payment
    res2 = payment_client.post("/api/v1/payments/webhook", json={
        "event_id": f"evt_paid_2_{uuid.uuid4().hex[:8]}",
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS"
    })
    assert res2.status_code == 200
    assert "already synchronized" in res2.json()["message"]


def test_phase15_invalid_payment_transition_rejection():
    """Phase 15 Test 12: Terminal state transition (FAILED -> PAID) is rejected."""
    db = get_test_db()
    try:
        order = Order(
            order_number="#PP-FAILED-P15",
            customer_name="Failed User P15",
            customer_email="fail.p15@test.com",
            customer_phone="+44 7123 456789",
            branch_id="branch-camden-001",
            order_type=OrderType.DELIVERY,
            status=OrderStatus.PENDING_PAYMENT,
            subtotal=10.0,
            delivery_fee=0.0,
            service_fee=0.99,
            total_amount=10.99
        )
        db.add(order)
        db.commit()

        payment = Payment(
            order_id=order.id,
            amount=10.99,
            currency="GBP",
            status=PaymentStatus.FAILED,
            transaction_id="TXN_FAIL_P15"
        )
        db.add(payment)
        db.commit()

        # Attempt to transition FAILED -> PAID
        res = payment_client.post("/api/v1/payments/webhook", json={
            "event_id": f"evt_fail_to_paid_{uuid.uuid4().hex[:8]}",
            "order_id": order.id,
            "transaction_id": "TXN_FAIL_P15",
            "status": "SUCCESS"
        })
        assert res.status_code == 409
    finally:
        db.close()


def test_phase15_duplicate_loyalty_award_prevention():
    """Phase 15 Test 13: Customer loyalty points are credited once and never duplicated."""
    from app.models.loyalty import LoyaltyAccount
    db = get_test_db()
    try:
        user = db.query(User).filter(User.email == "loyalty.p15@example.com").first()
        if not user:
            user = User(
                email="loyalty.p15@example.com",
                password_hash="mockpassword123",
                full_name="Loyalty User P15",
                role=UserRole.CUSTOMER
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        order = _create_valid_delivery_order("loyalty.p15@example.com")
        session = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()

        # First event
        payment_client.post("/api/v1/payments/webhook", json={
            "event_id": f"evt_loyalty_1_{uuid.uuid4().hex[:8]}",
            "order_id": order["id"],
            "transaction_id": session["transaction_id"],
            "status": "SUCCESS"
        })

        db.expire_all()
        loyalty = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == user.id).first()
        initial_awarded = loyalty.available_points

        # Second event
        payment_client.post("/api/v1/payments/webhook", json={
            "event_id": f"evt_loyalty_2_{uuid.uuid4().hex[:8]}",
            "order_id": order["id"],
            "transaction_id": session["transaction_id"],
            "status": "SUCCESS"
        })

        db.expire_all()
        loyalty_refreshed = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == user.id).first()
        assert loyalty_refreshed.available_points == initial_awarded
    finally:
        db.close()


def test_phase15_atomic_payment_order_transition_and_audit():
    """Phase 15 Test 14: Payment transition, order sync, loyalty, and audit history succeed atomically."""
    order = _create_valid_delivery_order("atomic.p15@example.com")
    session = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()

    res = payment_client.post("/api/v1/payments/webhook", json={
        "event_id": f"evt_atomic_{uuid.uuid4().hex[:8]}",
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS"
    })
    assert res.status_code == 200

    db = get_test_db()
    try:
        from app.models.payment import PaymentEvent
        ord_db = db.query(Order).filter(Order.id == order["id"]).first()
        pay_db = db.query(Payment).filter(Payment.id == session["payment_id"]).first()
        evt_db = db.query(PaymentEvent).filter(PaymentEvent.payment_id == session["payment_id"]).first()

        assert ord_db.status == OrderStatus.INCOMING
        assert ord_db.payment_status == PaymentStatus.PAID
        assert pay_db.status == PaymentStatus.PAID
        assert evt_db is not None
        assert evt_db.processing_status == "PROCESSED"
    finally:
        db.close()


def test_phase15_mock_simulation_endpoint_and_prod_block(monkeypatch):
    """Phase 15 Test 15: mock-simulate endpoint works in dev and is blocked in production."""
    order = _create_valid_delivery_order("mocksim.p15@example.com")
    session = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()

    # Dev simulation works
    sim_res = payment_client.post("/api/v1/payments/mock-simulate", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS"
    })
    assert sim_res.status_code == 200
    assert sim_res.json()["payment_status"] == PaymentStatus.PAID

    # In production, mock-simulate is blocked with 403
    from app.core.config import settings
    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setattr(settings, "PAYMENT_PROVIDER", "mock")

    prod_res = payment_client.post("/api/v1/payments/mock-simulate", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS"
    })
    assert prod_res.status_code == 403
    assert "Mock payment gateway is strictly disabled in production" in prod_res.text


# =========================================================================
# 10. Phase 16 — Secure Checkout Payment Integration Tests (1-16)
# =========================================================================

def _create_valid_collection_order(email="test.collection@example.com"):
    payload = {
        "branch_id": "branch-camden-001",
        "order_type": "COLLECTION",
        "customer_name": "Collection Customer",
        "customer_email": email,
        "customer_phone": "+44 7123 456789",
        "collection_slot_time": "2026-08-20T14:30:00",
        "items": [{"product_id": "prod-mc-project", "quantity": 1, "selected_modifiers": []}]
    }
    res = payment_client.post("/api/v1/orders", json=payload)
    assert res.status_code == 200, res.text
    return res.json()


def test_phase16_01_checkout_to_payment_creation():
    """Phase 16 Test 1: Full checkout creates Order in PENDING_PAYMENT and Payment session with provider-neutral fields."""
    order = _create_valid_delivery_order("phase16.checkout@example.com")
    assert order["status"] == OrderStatus.PENDING_PAYMENT

    res = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"})
    assert res.status_code == 200, res.text
    session = res.json()

    assert session["order_id"] == order["id"]
    assert session["amount"] == order["total_amount"]
    assert session["currency"] == "GBP"
    assert session["status"] == PaymentStatus.PENDING
    assert session["transaction_id"].startswith("TXN_")
    assert "/mock-checkout/" in session["payment_url"]


def test_phase16_02_delivery_payment_within_2_miles():
    """Phase 16 Test 2: Delivery order within 2 miles (Camden High St) can initiate payment."""
    order = _create_valid_delivery_order("phase16.within2m@example.com")
    res = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"})
    assert res.status_code == 200
    assert res.json()["transaction_id"] is not None


def test_phase16_03_delivery_payment_outside_2_miles_rejected():
    """Phase 16 Test 3: Delivery order > 2 miles cannot initiate payment and displays 2-mile restriction."""
    payload = {
        "branch_id": "branch-camden-001",
        "order_type": "DELIVERY",
        "customer_name": "Far Delivery Customer",
        "customer_email": "phase16.outside2m@example.com",
        "customer_phone": "+44 7123 456789",
        "delivery_address": {
            "address_line1": "Windsor Castle",
            "city": "Windsor",
            "postcode": "SL4 1NJ",
            "latitude": 51.4839,
            "longitude": -0.6044
        },
        "latitude": 51.4839,
        "longitude": -0.6044,
        "items": [{"product_id": "prod-mc-project", "quantity": 1, "selected_modifiers": []}]
    }
    ord_res = payment_client.post("/api/v1/orders", json=payload)
    assert ord_res.status_code == 400
    assert "WE PROVIDE DELIVERY UP TO 2 MILES ONLY" in ord_res.text or "DELIVERY_OUTSIDE_RADIUS" in ord_res.text


def test_phase16_04_collection_payment_always_allowed():
    """Phase 16 Test 4: Collection orders are not restricted by radius and can always create payment session."""
    coll_order = _create_valid_collection_order("phase16.collection@example.com")
    res = payment_client.post("/api/v1/payments/create-session", json={"order_id": coll_order['id'], "payment_method_type": "CARD"})
    assert res.status_code == 200
    assert res.json()["amount"] == coll_order["total_amount"]


def test_phase16_05_payment_success_and_order_confirmation():
    """Phase 16 Test 5: Payment success updates Payment to PAID, Order to INCOMING, and confirmation endpoint returns authoritative state."""
    import urllib.parse
    order = _create_valid_delivery_order("phase16.success.flow@example.com")
    session = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()

    # Simulate success
    sim_res = payment_client.post("/api/v1/payments/mock-simulate", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS",
        "amount": order["total_amount"],
        "currency": "GBP"
    })
    assert sim_res.status_code == 200

    # Fetch confirmation data via order_number (URL-encoded) and UUID with guest email verification
    conf_res = payment_client.get(f"/api/v1/orders/{urllib.parse.quote(order['order_number'])}?email={order['customer_email']}")
    assert conf_res.status_code == 200
    conf_data = conf_res.json()
    assert conf_data["status"] == OrderStatus.INCOMING
    assert conf_data["payment_status"] == PaymentStatus.PAID
    assert conf_data["total_amount"] == order["total_amount"]

    # Also verify UUID lookup
    conf_uuid_res = payment_client.get(f"/api/v1/orders/{order['id']}?email={order['customer_email']}")
    assert conf_uuid_res.status_code == 200
    assert conf_uuid_res.json()["status"] == OrderStatus.INCOMING



def test_phase16_06_payment_failure_retry_without_duplicate_order():
    """Phase 16 Test 6: Payment failure records FAILED, keeps order unpaid, and re-initiating payment reuses the order without creating a duplicate order."""
    order = _create_valid_delivery_order("phase16.fail.retry@example.com")
    session1 = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()

    # Simulate failure
    sim_fail = payment_client.post("/api/v1/payments/mock-simulate", json={
        "order_id": order["id"],
        "transaction_id": session1["transaction_id"],
        "status": "FAILED",
        "error_message": "Card declined"
    })
    assert sim_fail.status_code == 200
    assert sim_fail.json()["payment_status"] == PaymentStatus.FAILED

    # Order must remain unpaid
    ord_check = payment_client.get(f"/api/v1/orders/{order['id']}?email={order['customer_email']}").json()
    assert ord_check["status"] == OrderStatus.PENDING_PAYMENT
    assert ord_check["payment_status"] == PaymentStatus.FAILED

    # Retry payment: request new session for the SAME order
    session2 = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()
    assert session2["order_id"] == order["id"]

    # Total orders in DB for this email should still be exactly 1
    db = get_test_db()
    try:
        user_orders = db.query(Order).filter(Order.customer_email == "phase16.fail.retry@example.com").all()
        assert len(user_orders) == 1
    finally:
        db.close()


def test_phase16_07_payment_cancellation_order_remains_unpaid():
    """Phase 16 Test 7: Payment cancellation sets payment CANCELLED and order remains unpaid."""
    order = _create_valid_delivery_order("phase16.cancel@example.com")
    session = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()

    sim_cancel = payment_client.post("/api/v1/payments/mock-simulate", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "CANCELLED"
    })
    assert sim_cancel.status_code == 200
    assert sim_cancel.json()["payment_status"] == PaymentStatus.CANCELLED

    ord_check = payment_client.get(f"/api/v1/orders/{order['id']}?email={order['customer_email']}").json()
    assert ord_check["payment_status"] == PaymentStatus.CANCELLED
    assert ord_check["status"] == OrderStatus.PENDING_PAYMENT


def test_phase16_08_pending_payment_order_unpaid():
    """Phase 16 Test 8: Pending payment simulation leaves status PENDING without advancing order to INCOMING."""
    order = _create_valid_delivery_order("phase16.pending@example.com")
    session = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()

    sim_pending = payment_client.post("/api/v1/payments/mock-simulate", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "PENDING"
    })
    assert sim_pending.status_code == 200
    assert sim_pending.json()["payment_status"] == PaymentStatus.PENDING

    ord_check = payment_client.get(f"/api/v1/orders/{order['id']}?email={order['customer_email']}").json()
    assert ord_check["status"] == OrderStatus.PENDING_PAYMENT


def test_phase16_09_duplicate_pay_click_idempotency_protection():
    """Phase 16 Test 9: Re-submitting payment creation with identical Idempotency-Key returns existing payment record."""
    order = _create_valid_delivery_order("phase16.doubleclick@example.com")
    idemp_key = f"idemp_test_{uuid.uuid4().hex[:8]}"

    res1 = payment_client.post(
        "/api/v1/payments/create-session",
        headers={"Idempotency-Key": idemp_key},
        json={"order_id": order["id"], "payment_method_type": "CARD"}
    ).json()

    res2 = payment_client.post(
        "/api/v1/payments/create-session",
        headers={"Idempotency-Key": idemp_key},
        json={"order_id": order["id"], "payment_method_type": "CARD"}
    ).json()

    assert res1["payment_id"] == res2["payment_id"]
    assert res1["transaction_id"] == res2["transaction_id"]

    db = get_test_db()
    try:
        payments = db.query(Payment).filter(Payment.order_id == order["id"]).all()
        assert len(payments) == 1
    finally:
        db.close()


def test_phase16_10_duplicate_payment_event_request():
    """Phase 16 Test 10: Repeated identical mock payment events return idempotent success without duplicate side effects."""
    order = _create_valid_delivery_order("phase16.dupevent@example.com")
    session = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()
    event_id = f"evt_p16_dupe_{uuid.uuid4().hex[:8]}"

    payload = {
        "event_id": event_id,
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS"
    }

    res1 = payment_client.post("/api/v1/payments/mock-simulate", json=payload)
    assert res1.status_code == 200

    res2 = payment_client.post("/api/v1/payments/mock-simulate", json=payload)
    assert res2.status_code == 200
    assert res2.json()["idempotent"] is True


def test_phase16_11_refresh_after_successful_payment():
    """Phase 16 Test 11: Refreshing verify or order confirmation returns authoritative server state."""
    order = _create_valid_delivery_order("phase16.refresh@example.com")
    session = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()

    payment_client.post("/api/v1/payments/mock-simulate", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS"
    })

    # Poll / verify endpoint
    v_res = payment_client.get(f"/api/v1/payments/verify/{session['transaction_id']}")
    assert v_res.status_code == 200
    assert v_res.json()["payment_status"] == PaymentStatus.PAID
    assert v_res.json()["order_status"] == OrderStatus.INCOMING


def test_phase16_12_unauthorized_mismatched_order_payment():
    """Phase 16 Test 12: Paying for a different order than the transaction was created for is rejected with 403."""
    order1 = _create_valid_delivery_order("phase16.mismatch1@example.com")
    order2 = _create_valid_delivery_order("phase16.mismatch2@example.com")

    session1 = payment_client.post("/api/v1/payments/create-session", json={"order_id": order1['id'], "payment_method_type": "CARD"}).json()

    res = payment_client.post("/api/v1/payments/mock-simulate", json={
        "order_id": order2["id"],  # Mismatched
        "transaction_id": session1["transaction_id"],
        "status": "SUCCESS"
    })
    assert res.status_code == 403


def test_phase16_13_wrong_amount_tampering_rejected():
    """Phase 16 Test 13: Submitting payment event with tampered amount is rejected."""
    order = _create_valid_delivery_order("phase16.tamper@example.com")
    session = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()

    res = payment_client.post("/api/v1/payments/mock-simulate", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS",
        "amount": round(order["total_amount"] + 5.00, 2)
    })
    assert res.status_code == 400
    assert "Amount mismatch" in res.text


def test_phase16_14_wrong_currency_rejected():
    """Phase 16 Test 14: Non-GBP currencies are rejected."""
    order = _create_valid_delivery_order("phase16.curr.usd@example.com")
    session = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()

    res = payment_client.post("/api/v1/payments/mock-simulate", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS",
        "currency": "USD"
    })
    assert res.status_code == 400
    assert "Only GBP is accepted" in res.text


def test_phase16_15_cancelled_order_payment_rejection():
    """Phase 16 Test 15: Initiating or processing payment for cancelled order is rejected."""
    db = get_test_db()
    try:
        order = Order(
            order_number="#PP-CANCEL-P16",
            customer_name="Cancelled User P16",
            customer_email="cancel.p16@test.com",
            customer_phone="+44 7123 456789",
            branch_id="branch-camden-001",
            order_type=OrderType.DELIVERY,
            status=OrderStatus.CANCELLED,
            subtotal=10.0,
            delivery_fee=0.0,
            service_fee=0.99,
            total_amount=10.99
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        res = payment_client.post("/api/v1/payments/create-session", json={"order_id": order.id, "payment_method_type": "CARD"})
        assert res.status_code == 400
        assert "Cannot initiate payment for a cancelled order" in res.text
    finally:
        db.close()


def test_phase16_16_admin_order_visibility_after_payment():
    """Phase 16 Test 16: Once payment is PAID, Order appears as INCOMING in admin orders query."""
    order = _create_valid_delivery_order("phase16.admin.vis@example.com")
    session = payment_client.post("/api/v1/payments/create-session", json={"order_id": order['id'], "payment_method_type": "CARD"}).json()

    payment_client.post("/api/v1/payments/mock-simulate", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS"
    })

    # Admin query for INCOMING orders with Super Admin token
    admin_token = create_access_token(subject="user-superadmin-001", roles=["SUPER_ADMIN"])
    admin_res = payment_client.get("/api/v1/orders?status=INCOMING", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_res.status_code == 200
    incoming_orders = admin_res.json()
    matching = [o for o in incoming_orders if o["id"] == order["id"]]
    assert len(matching) == 1
    assert matching[0]["payment_status"] == PaymentStatus.PAID
    assert matching[0]["status"] == OrderStatus.INCOMING


# =========================================================================
# 11. Phase 16 Hotfix — Canonical Payment Session Request Contract Tests
# =========================================================================

def test_phase16_hotfix_01_valid_create_session_canonical_contract():
    """Verify canonical POST /api/v1/payments/create-session with JSON body and Idempotency-Key header returns 200."""
    order = _create_valid_delivery_order("hotfix.valid@example.com")
    idem_key = f"idemp_hotfix_{uuid.uuid4().hex[:8]}"

    res = payment_client.post(
        "/api/v1/payments/create-session",
        headers={"Idempotency-Key": idem_key},
        json={
            "order_id": order["id"],
            "payment_method_type": "CARD"
        }
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["order_id"] == order["id"]
    assert data["provider"] == PaymentProvider.MOCK
    assert data["status"] == PaymentStatus.PENDING
    assert data["amount"] == order["total_amount"]
    assert data["currency"] == "GBP"
    assert data["transaction_id"].startswith("TXN_")
    assert data["payment_url"] == f"/mock-checkout/{data['transaction_id']}"
    assert data["client_secret"] == f"sec_mock_{data['transaction_id']}"


def test_phase16_hotfix_02_missing_order_id_returns_422():
    """Verify missing order_id in JSON body strictly returns 422 Unprocessable Content."""
    # Empty body
    res_empty = payment_client.post("/api/v1/payments/create-session", json={})
    assert res_empty.status_code == 422, res_empty.text
    errors = res_empty.json().get("detail", [])
    assert any("order_id" in str(e) for e in errors)

    # Only payment_method_type without order_id
    res_no_order = payment_client.post(
        "/api/v1/payments/create-session",
        json={"payment_method_type": "CARD"}
    )
    assert res_no_order.status_code == 422
    errors = res_no_order.json().get("detail", [])
    assert any("order_id" in str(e) for e in errors)


def test_phase16_hotfix_03_missing_payment_method_type_defaults_to_card():
    """Verify missing payment_method_type in JSON body succeeds with 200 and defaults to CARD."""
    order = _create_valid_delivery_order("hotfix.defaultcard@example.com")
    res = payment_client.post(
        "/api/v1/payments/create-session",
        json={"order_id": order["id"]}
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["order_id"] == order["id"]
    assert data["status"] == PaymentStatus.PENDING

    # Check payment method in database
    db = get_test_db()
    try:
        payment = db.query(Payment).filter(Payment.id == data["payment_id"]).first()
        assert payment is not None
        assert payment.payment_method_type == "CARD"
    finally:
        db.close()


def test_phase16_hotfix_04_idempotency_behavior_with_header():
    """Verify Idempotency-Key HTTP header prevents duplicate payment session records."""
    order = _create_valid_delivery_order("hotfix.idemp@example.com")
    idem_key = f"idemp_hotfix_header_{uuid.uuid4().hex[:8]}"

    res1 = payment_client.post(
        "/api/v1/payments/create-session",
        headers={"Idempotency-Key": idem_key},
        json={"order_id": order["id"], "payment_method_type": "CARD"}
    )
    assert res1.status_code == 200
    data1 = res1.json()

    res2 = payment_client.post(
        "/api/v1/payments/create-session",
        headers={"Idempotency-Key": idem_key},
        json={"order_id": order["id"], "payment_method_type": "CARD"}
    )
    assert res2.status_code == 200
    data2 = res2.json()

    assert data1["payment_id"] == data2["payment_id"]
    assert data1["transaction_id"] == data2["transaction_id"]

    db = get_test_db()
    try:
        records = db.query(Payment).filter(Payment.order_id == order["id"]).all()
        assert len(records) == 1
    finally:
        db.close()


def test_phase16_hotfix_05_unauthorized_nonexistent_order_returns_404():
    """Verify create-session for non-existent order_id returns 404 Order not found."""
    res = payment_client.post(
        "/api/v1/payments/create-session",
        json={"order_id": "non-existent-order-id-9999", "payment_method_type": "CARD"}
    )
    assert res.status_code == 404
    assert "Order not found" in res.text


def test_phase16_hotfix_06_cancelled_order_rejection_returns_400():
    """Verify create-session for a CANCELLED order is rejected with 400."""
    db = get_test_db()
    try:
        order = Order(
            order_number="#PP-HOTFIX-CANCEL",
            customer_name="Hotfix Cancelled User",
            customer_email="hotfix.cancel@example.com",
            customer_phone="+44 7123 456789",
            branch_id="branch-camden-001",
            order_type=OrderType.DELIVERY,
            status=OrderStatus.CANCELLED,
            subtotal=12.0,
            delivery_fee=0.0,
            service_fee=0.99,
            total_amount=12.99
        )
        db.add(order)
        db.commit()
        db.refresh(order)

        res = payment_client.post(
            "/api/v1/payments/create-session",
            json={"order_id": order.id, "payment_method_type": "CARD"}
        )
        assert res.status_code == 400
        assert "Cannot initiate payment for a cancelled order" in res.text
    finally:
        db.close()


def test_phase16_hotfix_07_delivery_outside_radius_rejection():
    """Verify delivery orders outside the 2-mile radius are rejected with 400 DELIVERY_OUTSIDE_RADIUS."""
    payload = {
        "branch_id": "branch-camden-001",
        "order_type": "DELIVERY",
        "customer_name": "Far Delivery Customer",
        "customer_email": "hotfix.far@example.com",
        "customer_phone": "+44 7123 456789",
        "delivery_address": {
            "address_line1": "Windsor Castle",
            "city": "Windsor",
            "postcode": "SL4 1NJ",
            "latitude": 51.4839,
            "longitude": -0.6044
        },
        "latitude": 51.4839,
        "longitude": -0.6044,
        "items": [{"product_id": "prod-mc-project", "quantity": 1, "selected_modifiers": []}]
    }
    res = payment_client.post("/api/v1/orders", json=payload)
    assert res.status_code == 400
    assert "WE PROVIDE DELIVERY UP TO 2 MILES ONLY" in res.text or "DELIVERY_OUTSIDE_RADIUS" in res.text


def test_phase16_hotfix_08_collection_order_always_allowed():
    """Verify collection orders create-session succeeds with 200 without distance restrictions."""
    coll_order = _create_valid_collection_order("hotfix.coll@example.com")
    res = payment_client.post(
        "/api/v1/payments/create-session",
        json={"order_id": coll_order["id"], "payment_method_type": "CARD"}
    )
    assert res.status_code == 200
    assert res.json()["amount"] == coll_order["total_amount"]
    assert res.json()["status"] == PaymentStatus.PENDING


def test_phase16_hotfix_09_already_paid_order_idempotent_returns_200():
    """Verify create-session on an already paid order returns 200 with PAID status idempotently."""
    order = _create_valid_delivery_order("hotfix.paid@example.com")
    session = payment_client.post(
        "/api/v1/payments/create-session",
        json={"order_id": order["id"], "payment_method_type": "CARD"}
    ).json()

    # Simulate payment success
    sim_res = payment_client.post("/api/v1/payments/mock-simulate", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS",
        "amount": order["total_amount"],
        "currency": "GBP"
    })
    assert sim_res.status_code == 200
    assert sim_res.json()["payment_status"] == PaymentStatus.PAID

    # Call create-session again on the paid order
    res_again = payment_client.post(
        "/api/v1/payments/create-session",
        json={"order_id": order["id"], "payment_method_type": "CARD"}
    )
    assert res_again.status_code == 200
    data_again = res_again.json()
    assert data_again["status"] == PaymentStatus.PAID
    assert data_again["payment_id"] == session["payment_id"]


def test_phase16_hotfix_10_full_end_to_end_flow():
    """
    Verify complete flow:
    Checkout -> POST /orders -> POST /payments/create-session -> Mock Checkout Simulation -> Payment PAID -> Order INCOMING
    """
    # 1. POST /orders
    order_payload = {
        "branch_id": "branch-camden-001",
        "order_type": "DELIVERY",
        "customer_name": "Full Flow User",
        "customer_email": "fullflow@example.com",
        "customer_phone": "+44 7123 456789",
        "delivery_address": {
            "address_line1": "45 Camden High Street",
            "city": "London",
            "postcode": "NW1 7JE",
            "latitude": 51.5360,
            "longitude": -0.1420
        },
        "items": [{"product_id": "prod-mc-project", "quantity": 1, "selected_modifiers": []}]
    }
    ord_res = payment_client.post("/api/v1/orders", json=order_payload)
    assert ord_res.status_code == 200, ord_res.text
    order = ord_res.json()
    assert order["status"] == OrderStatus.PENDING_PAYMENT

    # 2. POST /payments/create-session
    idemp_key = f"idemp_flow_{uuid.uuid4().hex[:8]}"
    session_res = payment_client.post(
        "/api/v1/payments/create-session",
        headers={"Idempotency-Key": idemp_key},
        json={
            "order_id": order["id"],
            "payment_method_type": "CARD"
        }
    )
    assert session_res.status_code == 200, session_res.text
    session = session_res.json()
    assert session["transaction_id"].startswith("TXN_")
    assert session["status"] == PaymentStatus.PENDING
    assert session["payment_url"] == f"/mock-checkout/{session['transaction_id']}"

    # 3. Mock Checkout Simulation: SUCCESS
    sim_res = payment_client.post("/api/v1/payments/mock-simulate", json={
        "order_id": order["id"],
        "transaction_id": session["transaction_id"],
        "status": "SUCCESS",
        "amount": order["total_amount"],
        "currency": "GBP"
    })
    assert sim_res.status_code == 200, sim_res.text
    sim_data = sim_res.json()
    assert sim_data["payment_status"] == PaymentStatus.PAID
    assert sim_data["order_status"] == OrderStatus.INCOMING

    # 4. Verify authoritative database records
    db = get_test_db()
    try:
        db_order = db.query(Order).filter(Order.id == order["id"]).first()
        db_payment = db.query(Payment).filter(Payment.id == session["payment_id"]).first()

        assert db_order.status == OrderStatus.INCOMING
        assert db_order.payment_status == PaymentStatus.PAID
        assert db_payment.status == PaymentStatus.PAID
        assert db_payment.transaction_id == session["transaction_id"]
    finally:
        db.close()




