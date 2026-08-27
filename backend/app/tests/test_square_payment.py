import pytest
import uuid
from unittest.mock import patch, AsyncMock, MagicMock
from app.tests.db import client, reset_test_db, TestingSessionLocal
from app.models.user import User, UserRole
from app.models.product import Category, Product
from app.models.order import Order, OrderItem, OrderStatus, PaymentStatus as OrderPaymentStatus, OrderType
from app.models.payment import Payment, PaymentStatus, PaymentProvider, PaymentEvent
from app.models.branch import Branch
from app.core.security import create_access_token
from app.core.config import settings
from app.services.square_service import SquarePaymentProvider, SquarePaymentError


@pytest.fixture(autouse=True)
def setup_db():
    reset_test_db()
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_test_order(db_session, total_amount=25.0, status=OrderStatus.PENDING_PAYMENT):
    branch_code = f"BR-{uuid.uuid4().hex[:4].upper()}"
    branch = Branch(
        id=str(uuid.uuid4()),
        code=branch_code,
        name="Edmonton Test Branch",
        address_line1="124 Edmonton Road",
        city="London",
        postcode="N9 0TY",
        latitude=51.6154,
        longitude=-0.0708,
        delivery_radius_miles=5.0,
        is_active=True
    )
    db_session.add(branch)

    order = Order(
        id=str(uuid.uuid4()),
        order_number=f"PP-{uuid.uuid4().hex[:6].upper()}",
        branch_id=branch.id,
        order_type=OrderType.COLLECTION,
        customer_name="John Doe",
        customer_email="john@example.com",
        customer_phone="+447123456789",
        status=status,
        payment_status=OrderPaymentStatus.PENDING,
        subtotal=total_amount,
        total_amount=total_amount,
        delivery_fee=0.0,
        service_fee=0.0
    )
    db_session.add(order)
    db_session.commit()
    db_session.refresh(order)
    return order


def test_payment_config_endpoint():
    """Verifies public configuration endpoint returns proper details and never leaks tokens."""
    response = client.get("/api/v1/payments/config")
    assert response.status_code == 200
    data = response.json()
    assert "provider" in data
    assert "environment" in data
    # Strictly ensure access token is NEVER present in config response
    assert "access_token" not in data
    assert "SQUARE_ACCESS_TOKEN" not in data
    assert "secret" not in str(data).lower()


def test_successful_square_payment(setup_db):
    """Verifies that a valid Square nonce charges successfully and transitions order to INCOMING."""
    db_session = setup_db
    order = create_test_order(db_session, total_amount=32.50)

    mock_square_response = {
        "payment": {
            "id": f"sq_pay_{uuid.uuid4().hex[:12]}",
            "status": "COMPLETED",
            "amount_money": {"amount": 3250, "currency": "GBP"},
            "reference_id": order.id,
            "receipt_url": "https://squareup.com/receipt/preview/xyz"
        }
    }

    mock_client = AsyncMock()
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 200
    mock_post_resp.json.return_value = mock_square_response
    mock_client.post.return_value = mock_post_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        with patch.object(settings, "PAYMENT_PROVIDER", "square"):
            with patch.object(settings, "SQUARE_LOCATION_ID", "TEST_LOC_123"):
                with patch.object(settings, "SQUARE_ACCESS_TOKEN", "fake_test_token"):
                    response = client.post(
                        "/api/v1/payments/create-session",
                        json={
                            "order_id": order.id,
                            "payment_method_type": "CARD",
                            "source_id": "cnon:card-nonce-ok"
                        },
                        headers={"Idempotency-Key": f"idemp_{order.id}_1"}
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert data["status"] == PaymentStatus.PAID
                    assert data["order_id"] == order.id
                    assert data["amount"] == 32.50
                    assert data["transaction_id"].startswith("sq_pay_")

                    # Verify in database
                    db_session.refresh(order)
                    assert order.payment_status == OrderPaymentStatus.PAID
                    assert order.status == OrderStatus.INCOMING


def test_declined_square_payment(setup_db):
    """Verifies that card decline returns a clean user-facing error and leaves order unpaid."""
    db_session = setup_db
    order = create_test_order(db_session, total_amount=19.99)

    mock_square_error = {
        "errors": [
            {
                "code": "CARD_DECLINED",
                "category": "PAYMENT_METHOD_ERROR",
                "detail": "Card declined."
            }
        ]
    }

    mock_client = AsyncMock()
    mock_post_resp = MagicMock()
    mock_post_resp.status_code = 400
    mock_post_resp.json.return_value = mock_square_error
    mock_client.post.return_value = mock_post_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        with patch.object(settings, "PAYMENT_PROVIDER", "square"):
            with patch.object(settings, "SQUARE_LOCATION_ID", "TEST_LOC_123"):
                with patch.object(settings, "SQUARE_ACCESS_TOKEN", "fake_test_token"):
                    response = client.post(
                        "/api/v1/payments/create-session",
                        json={
                            "order_id": order.id,
                            "payment_method_type": "CARD",
                            "source_id": "cnon:card-nonce-declined"
                        }
                    )

                    assert response.status_code == 400
                    data = response.json()
                    assert "declined" in str(data).lower() or "payment" in str(data).lower()

                    # Database check: order must remain unpaid
                    db_session.refresh(order)
                    assert order.payment_status == OrderPaymentStatus.PENDING
                    assert order.status == OrderStatus.PENDING_PAYMENT


def test_invalid_order_payment():
    """Verifies that non-existent orders return 404."""
    response = client.post(
        "/api/v1/payments/create-session",
        json={
            "order_id": str(uuid.uuid4()),
            "payment_method_type": "CARD",
            "source_id": "cnon:card-nonce-ok"
        }
    )
    assert response.status_code == 404


def test_cancelled_order_payment_rejected(setup_db):
    """Verifies that cancelled orders cannot be charged."""
    db_session = setup_db
    order = create_test_order(db_session, total_amount=20.0, status=OrderStatus.CANCELLED)

    response = client.post(
        "/api/v1/payments/create-session",
        json={
            "order_id": order.id,
            "payment_method_type": "CARD",
            "source_id": "cnon:card-nonce-ok"
        }
    )
    assert response.status_code == 400
    assert "cancelled" in response.json()["detail"].lower()


def test_already_paid_order_protection(setup_db):
    """Verifies that an already paid order returns the existing payment idempotently."""
    db_session = setup_db
    order = create_test_order(db_session, total_amount=15.0)
    order.payment_status = OrderPaymentStatus.PAID
    order.status = OrderStatus.INCOMING

    payment = Payment(
        id=str(uuid.uuid4()),
        order_id=order.id,
        provider=PaymentProvider.SQUARE,
        transaction_id="sq_pay_already_paid",
        amount=15.0,
        currency="GBP",
        status=PaymentStatus.PAID
    )
    db_session.add(payment)
    db_session.commit()

    response = client.post(
        "/api/v1/payments/create-session",
        json={
            "order_id": order.id,
            "payment_method_type": "CARD",
            "source_id": "cnon:card-nonce-ok"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == PaymentStatus.PAID
    assert data["transaction_id"] == "sq_pay_already_paid"


def test_square_webhook_signature_and_event(setup_db):
    """Verifies that Square webhook events are normalized and processed safely."""
    db_session = setup_db
    order = create_test_order(db_session, total_amount=22.0)

    payment = Payment(
        id=str(uuid.uuid4()),
        order_id=order.id,
        provider=PaymentProvider.SQUARE,
        transaction_id="sq_pay_webhook_test",
        amount=22.0,
        currency="GBP",
        status=PaymentStatus.PENDING
    )
    db_session.add(payment)
    db_session.commit()

    webhook_payload = {
        "event_id": f"evt_{uuid.uuid4().hex[:8]}",
        "type": "payment.updated",
        "data": {
            "object": {
                "payment": {
                    "id": "sq_pay_webhook_test",
                    "reference_id": order.id,
                    "status": "COMPLETED",
                    "amount_money": {"amount": 2200, "currency": "GBP"}
                }
            }
        }
    }

    with patch.object(settings, "PAYMENT_PROVIDER", "square"):
        with patch.object(settings, "SQUARE_ACCESS_TOKEN", "fake_test_token"):
            response = client.post(
                "/api/v1/payments/webhook",
                json=webhook_payload,
                headers={"x-square-hmacsha256-signature": "dummy_sig"}
            )
            assert response.status_code == 200

            db_session.refresh(order)
            db_session.refresh(payment)
            assert payment.status == PaymentStatus.PAID
            assert order.payment_status == OrderPaymentStatus.PAID
            assert order.status == OrderStatus.INCOMING
