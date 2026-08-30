import uuid
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import Base
from app.models.product import Product, Category
from app.models.branch import Branch
from app.models.order import Order, OrderStatus, OrderType, PaymentStatus
from app.models.promotion import Coupon
from app.models.user import User, UserRole
from app.services.pricing_service import calculate_order_totals
from app.services.square_service import SquarePaymentProvider
from app.tests.db import client, reset_test_db, TestingSessionLocal


@pytest.fixture(autouse=True)
def setup_billing_test_db():
    """Seeds test database with exact reference products and coupons."""
    reset_test_db()
    db = TestingSessionLocal()
    try:
        # 1. Exact Reference Products
        p1 = Product(
            id="prod-mc-project-ref",
            category_id="cat-burgers",
            name="MC Project",
            sku="PP-MC-01",
            base_price=6.95,
            is_active=True
        )
        p2 = Product(
            id="prod-outlaw-project-ref",
            category_id="cat-burgers",
            name="Outlaw Project",
            sku="PP-OP-01",
            base_price=4.45,
            is_active=True
        )
        p3 = Product(
            id="prod-localised-fries-ref",
            category_id="cat-burgers",
            name="Localised Fries",
            sku="PP-LF-01",
            base_price=6.45,
            is_active=True
        )
        p_hundred = Product(
            id="prod-hundred-ref",
            category_id="cat-burgers",
            name="Catering Special",
            sku="PP-CAT-100",
            base_price=100.00,
            is_active=True
        )
        p_big = Product(
            id="prod-big-ref",
            category_id="cat-burgers",
            name="Party Feast",
            sku="PP-PARTY-24090",
            base_price=240.90,
            is_active=True
        )
        db.add_all([p1, p2, p3, p_hundred, p_big])

        # 2. Reference Discount Coupon (£2.00 fixed)
        coupon_2 = Coupon(
            id="coupon-save2",
            code="SAVE2",
            name="Save £2",
            coupon_type="FIXED_AMOUNT",
            discount_value=2.00,
            min_order_value=0.00,
            is_active=True
        )
        coupon_big = Coupon(
            id="coupon-save1345",
            code="SAVE1345",
            name="Save £13.45",
            coupon_type="FIXED_AMOUNT",
            discount_value=13.45,
            min_order_value=0.00,
            is_active=True
        )
        db.add_all([coupon_2, coupon_big])
        db.commit()
    finally:
        db.close()


# =========================================================================
# TEST 1 — EXACT REFERENCE BILL CALCULATION & RECONCILIATION
# =========================================================================
def test_01_exact_reference_bill_calculation():
    """
    Exact reference bill:
    1  MC Project        £6.95
    1  Outlaw Project    £4.45
    1  Localised Fries   £6.45
    ---------------------------
    3  ITEM(S)          £17.85
       Discount         -£2.00
    ---------------------------
       AMOUNT DUE       £15.85

    Rate: 20% | Net: £13.21 | Tax: £2.64 | Gross: £15.85
    Reconciliation: Net (£13.21) + Tax (£2.64) == Gross (£15.85)
    """
    db = TestingSessionLocal()
    try:
        items = [
            {"product_id": "prod-mc-project-ref", "quantity": 1},
            {"product_id": "prod-outlaw-project-ref", "quantity": 1},
            {"product_id": "prod-localised-fries-ref", "quantity": 1}
        ]
        totals = calculate_order_totals(
            db=db,
            items=items,
            order_type="DELIVERY",
            coupon_code="SAVE2"
        )

        assert totals["subtotal"] == 17.85
        assert totals["discount_amount"] == 2.00
        assert totals["gross_amount"] == 15.85
        assert totals["vat_amount"] == 2.64
        assert totals["net_amount"] == 13.21
        assert totals["delivery_fee"] == 0.00
        assert totals["service_fee"] == 0.00
        assert totals["total_amount"] == 15.85

        # Strict financial reconciliation
        assert round(totals["net_amount"] + totals["vat_amount"], 2) == totals["gross_amount"]
        assert totals["total_amount"] == totals["gross_amount"]
    finally:
        db.close()


# =========================================================================
# TEST 2 — £100.00 VAT-INCLUSIVE GROSS RECONCILIATION
# =========================================================================
def test_02_hundred_pound_vat_inclusive_reconciliation():
    """
    Gross = £100.00
    VAT (20% extracted): round(100.00 * 20 / 120, 2) = round(16.6666..., 2) = £16.67
    Net: round(100.00 - 16.67, 2) = £83.33
    Reconciliation: £83.33 + £16.67 == £100.00
    """
    db = TestingSessionLocal()
    try:
        items = [{"product_id": "prod-hundred-ref", "quantity": 1}]
        totals = calculate_order_totals(db=db, items=items, order_type="COLLECTION")

        assert totals["subtotal"] == 100.00
        assert totals["discount_amount"] == 0.00
        assert totals["gross_amount"] == 100.00
        assert totals["vat_amount"] == 16.67
        assert totals["net_amount"] == 83.33
        assert totals["total_amount"] == 100.00
        assert round(totals["net_amount"] + totals["vat_amount"], 2) == 100.00
    finally:
        db.close()


# =========================================================================
# TEST 3 — DISCOUNTED £227.45 GROSS ORDER
# =========================================================================
def test_03_discounted_order_reconciliation():
    """
    Subtotal = £240.90
    Discount = £13.45
    Gross = £227.45
    VAT (20% extracted): round(227.45 * 20 / 120, 2) = round(37.90833..., 2) = £37.91
    Net: round(227.45 - 37.91, 2) = £189.54
    Reconciliation: £189.54 + £37.91 == £227.45
    """
    db = TestingSessionLocal()
    try:
        items = [{"product_id": "prod-big-ref", "quantity": 1}]
        totals = calculate_order_totals(
            db=db,
            items=items,
            order_type="DELIVERY",
            coupon_code="SAVE1345"
        )

        assert totals["subtotal"] == 240.90
        assert totals["discount_amount"] == 13.45
        assert totals["gross_amount"] == 227.45
        assert totals["vat_amount"] == 37.91
        assert totals["net_amount"] == 189.54
        assert totals["total_amount"] == 227.45
        assert round(totals["net_amount"] + totals["vat_amount"], 2) == 227.45
    finally:
        db.close()


# =========================================================================
# TEST 4 — PAYMENT MINOR UNITS & SQUARE PAYLOAD VERIFICATION
# =========================================================================
def test_04_payment_minor_units_for_reference_bill(monkeypatch):
    """
    For a £15.85 reference order, the payment processor (Square / Apple Pay / Google Pay)
    MUST receive exactly 1585 pence (integer minor units).
    """
    provider = SquarePaymentProvider()
    provider.location_id = "LOC_TEST_123"
    provider.access_token = "fake_access_token"

    captured_payload = {}

    async def fake_post(url, json, headers):
        nonlocal captured_payload
        captured_payload = json
        class FakeResp:
            status_code = 200
            def json(self):
                return {
                    "payment": {
                        "id": "sq_pay_test_999",
                        "status": "COMPLETED",
                        "amount_money": json["amount_money"],
                        "receipt_url": "https://squareup.com/receipt/test"
                    }
                }
        return FakeResp()

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, json=None, headers=None):
            return await fake_post(url, json, headers)

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    import asyncio
    res = asyncio.run(
        provider.charge_source(
            order_id="order-ref-001",
            amount=15.85,
            source_id="cnon:test-nonce",
            currency="GBP"
        )
    )

    assert captured_payload["amount_money"]["amount"] == 1585
    assert captured_payload["amount_money"]["currency"] == "GBP"
    assert res["status"] == PaymentStatus.PAID


# =========================================================================
# TEST 5 — SERVER-SIDE ANTI-TAMPERING VERIFICATION
# =========================================================================
def test_05_client_anti_tampering_authoritative_backend_wins():
    """
    Client submits malicious/tampered pricing fields:
    - total_amount: 1.00
    - vat_amount: 0.10
    - subtotal: 5.00
    - delivery_fee: 10.00
    Backend MUST ignore client figures and authoritatively calculate £15.85 (with VAT £2.64).
    """
    payload = {
        "branch_id": "branch-camden-001",
        "order_type": "DELIVERY",
        "customer_name": "Tamper Test Customer",
        "customer_email": "tamper@pattyproject.co.uk",
        "customer_phone": "+44 7123 456789",
        "delivery_address": {
            "address_line1": "45 Camden High Street",
            "city": "London",
            "postcode": "NW1 7JE",
            "latitude": 51.5360,
            "longitude": -0.1420
        },
        "coupon_code": "SAVE2",
        "items": [
            {"product_id": "prod-mc-project-ref", "quantity": 1},
            {"product_id": "prod-outlaw-project-ref", "quantity": 1},
            {"product_id": "prod-localised-fries-ref", "quantity": 1}
        ],
        # Client attempts tampering
        "subtotal": 5.00,
        "vat_amount": 0.10,
        "delivery_fee": 10.00,
        "total_amount": 1.00
    }

    res = client.post("/api/v1/orders", json=payload)
    assert res.status_code == 200, res.text
    data = res.json()

    assert data["subtotal"] == 17.85
    assert data["discount_amount"] == 2.00
    assert data["vat_amount"] == 2.64
    assert data["net_amount"] == 13.21
    assert data["delivery_fee"] == 0.00
    assert data["service_fee"] == 0.00
    assert data["total_amount"] == 15.85


# =========================================================================
# TEST 6 & 7 — DELIVERY FEE & SERVICE FEE INTEGRITY
# =========================================================================
def test_06_delivery_and_service_fee_integrity():
    """Verify delivery fee is £0.00 and service fee is £0.00."""
    db = TestingSessionLocal()
    try:
        items = [{"product_id": "prod-mc-project-ref", "quantity": 3}]
        totals = calculate_order_totals(db=db, items=items, order_type="DELIVERY")

        assert totals["delivery_fee"] == 0.00
        assert totals["service_fee"] == 0.00
        assert totals["total_amount"] == totals["gross_amount"]
    finally:
        db.close()


# =========================================================================
# TEST 8 — ORM ORDER NET AMOUNT PROPERTY
# =========================================================================
def test_08_order_orm_model_net_amount_property():
    """Verify Order.net_amount property dynamically reconciles net + vat == gross."""
    ord = Order(
        order_number="#PP9999",
        customer_name="John Doe",
        customer_email="john@example.com",
        customer_phone="+44 7000 000000",
        branch_id="branch-covent-garden",
        subtotal=17.85,
        discount_amount=2.00,
        vat_amount=2.64,
        total_amount=15.85
    )
    assert ord.net_amount == 13.21
    assert round(ord.net_amount + ord.vat_amount, 2) == 15.85
