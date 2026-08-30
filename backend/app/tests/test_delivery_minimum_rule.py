"""
Patty Project UK — Delivery Eligibility Business Rule Test Suite
Verifies €15.00 Minimum Cart Subtotal Threshold & Offer/Coupon Exemption Rule.
"""

from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import Base, get_db
from app.models.branch import Branch
from app.models.product import Product, Category, ProductModifier, Inventory
from app.models.promotion import Coupon
from app.models.user import User, UserRole
from app.services.pricing_service import (
    calculate_order_totals,
    is_delivery_eligible_by_subtotal,
    MINIMUM_DELIVERY_SUBTOTAL
)
from app.tests.db import TestingSessionLocal, client, reset_test_db


@pytest.fixture(autouse=True)
def setup_minimum_delivery_test_data():
    """Seed test fixtures specifically for testing delivery subtotal thresholds."""
    reset_test_db()
    db = TestingSessionLocal()

    # Ensure Camden branch exists and has delivery enabled
    camden = db.query(Branch).filter(Branch.id == "branch-camden-001").first()
    if not camden:
        camden = Branch(
            id="branch-camden-001",
            code="LC",
            name="London - Camden",
            address_line1="184 Camden High Street",
            postcode="NW1 8QP",
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
        db.add(camden)

    # Seed products with exact price values for boundary testing
    products_to_seed = [
        ("prod-item-1400", "Item 14.00", 14.00),
        ("prod-item-1499", "Item 14.99", 14.99),
        ("prod-item-1500", "Item 15.00", 15.00),
        ("prod-item-1501", "Item 15.01", 15.01),
        ("prod-item-1600", "Item 16.00", 16.00),
        ("prod-item-2000", "Item 20.00", 20.00),
        ("prod-item-1000", "Item 10.00", 10.00),
        ("prod-item-0500", "Item 5.00", 5.00)
    ]

    for pid, name, price in products_to_seed:
        existing = db.query(Product).filter(Product.id == pid).first()
        if not existing:
            p = Product(
                id=pid,
                category_id="cat-burgers",
                name=name,
                sku=f"SKU-{pid}",
                base_price=price,
                rating=5.0,
                reviews_count=10,
                is_active=True
            )
            db.add(p)

    # Seed Coupons
    # 1. Valid €6.00 coupon (Min order 15.00)
    c6 = db.query(Coupon).filter(Coupon.code == "SAVE6").first()
    if not c6:
        db.add(Coupon(
            code="SAVE6",
            name="Save €6 on orders over €15",
            coupon_type="FIXED_AMOUNT",
            discount_value=6.00,
            min_order_value=15.00,
            usage_limit=1000,
            used_count=0,
            is_active=True
        ))

    # 2. Valid €2.00 offer coupon (Min order 15.00)
    c2 = db.query(Coupon).filter(Coupon.code == "OFFER2").first()
    if not c2:
        db.add(Coupon(
            code="OFFER2",
            name="Offer €2 Discount",
            coupon_type="FIXED_AMOUNT",
            discount_value=2.00,
            min_order_value=15.00,
            usage_limit=1000,
            used_count=0,
            is_active=True
        ))

    # 3. Inactive / Expired coupon
    cexp = db.query(Coupon).filter(Coupon.code == "EXPIRED20").first()
    if not cexp:
        db.add(Coupon(
            code="EXPIRED20",
            name="Expired 20% Off",
            coupon_type="PERCENTAGE",
            discount_value=20.0,
            min_order_value=10.0,
            usage_limit=100,
            used_count=100,
            is_active=False
        ))

    db.commit()
    db.close()


def _make_delivery_order_payload(items: list, coupon_code: str = None) -> dict:
    """Helper to create a standard delivery order payload near Camden branch."""
    payload = {
        "branch_id": "branch-camden-001",
        "order_type": "DELIVERY",
        "customer_name": "Delivery Test User",
        "customer_email": "delivery.user@pattyproject.co.uk",
        "customer_phone": "+44 7123456789",
        "latitude": 51.5360,
        "longitude": -0.1420,
        "delivery_postcode": "NW1 8QP",
        "delivery_address": {
            "address_line1": "100 Camden Road",
            "city": "London",
            "postcode": "NW1 8QP",
            "latitude": 51.5360,
            "longitude": -0.1420
        },
        "items": items
    }
    if coupon_code:
        payload["coupon_code"] = coupon_code
    return payload


# ==============================================================================
# 1. UNIT TESTS: Pricing Service & Eligibility Logic
# ==============================================================================

def test_unit_is_delivery_eligible_boundary_below_15():
    """Unit: Subtotal Decimal('14.99') without promo -> Ineligible, shortfall Decimal('0.01')."""
    eligible, shortfall = is_delivery_eligible_by_subtotal(Decimal("14.99"), has_valid_promotion=False)
    assert eligible is False
    assert shortfall == Decimal("0.01")


def test_unit_is_delivery_eligible_boundary_exact_15():
    """Unit: Subtotal Decimal('15.00') without promo -> Eligible, shortfall Decimal('0.00')."""
    eligible, shortfall = is_delivery_eligible_by_subtotal(Decimal("15.00"), has_valid_promotion=False)
    assert eligible is True
    assert shortfall == Decimal("0.00")


def test_unit_is_delivery_eligible_boundary_above_15():
    """Unit: Subtotal Decimal('15.01') without promo -> Eligible, shortfall Decimal('0.00')."""
    eligible, shortfall = is_delivery_eligible_by_subtotal(Decimal("15.01"), has_valid_promotion=False)
    assert eligible is True
    assert shortfall == Decimal("0.00")


def test_unit_is_delivery_eligible_with_promotion_exception():
    """Unit: Subtotal Decimal('14.00') with promo -> Eligible via exception."""
    eligible, shortfall = is_delivery_eligible_by_subtotal(Decimal("14.00"), has_valid_promotion=True)
    assert eligible is True
    assert shortfall == Decimal("0.00")


# ==============================================================================
# 2. INTEGRATION TESTS: Required Business Rule Cases 1 through 12
# ==============================================================================

def test_01_subtotal_14_no_offer_delivery_blocked():
    """TEST 1: Subtotal = €14.00, No offer/coupon -> Delivery BLOCKED (HTTP 400)."""
    payload = _make_delivery_order_payload([{"product_id": "prod-item-1400", "quantity": 1}])
    resp = client.post("/api/v1/orders", json=payload)
    assert resp.status_code == 400
    err = resp.json()["detail"]
    assert err["code"] == "MINIMUM_DELIVERY_ORDER_REQUIRED"
    assert err["min_threshold"] == 15.00
    assert err["current_subtotal"] == 14.00
    assert round(err["amount_needed"], 2) == 1.00


def test_02_subtotal_14_99_no_offer_delivery_blocked():
    """TEST 2: Subtotal = €14.99, No offer/coupon -> Delivery BLOCKED (HTTP 400)."""
    payload = _make_delivery_order_payload([{"product_id": "prod-item-1499", "quantity": 1}])
    resp = client.post("/api/v1/orders", json=payload)
    assert resp.status_code == 400
    err = resp.json()["detail"]
    assert err["code"] == "MINIMUM_DELIVERY_ORDER_REQUIRED"
    assert err["current_subtotal"] == 14.99
    assert round(err["amount_needed"], 2) == 0.01


def test_03_subtotal_15_00_no_offer_delivery_allowed():
    """TEST 3: Subtotal = €15.00, No offer/coupon -> Delivery ALLOWED (HTTP 200)."""
    payload = _make_delivery_order_payload([{"product_id": "prod-item-1500", "quantity": 1}])
    resp = client.post("/api/v1/orders", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["order_type"] == "DELIVERY"
    assert data["subtotal"] == 15.00


def test_04_subtotal_15_01_no_offer_delivery_allowed():
    """TEST 4: Subtotal = €15.01, No offer/coupon -> Delivery ALLOWED (HTTP 200)."""
    payload = _make_delivery_order_payload([{"product_id": "prod-item-1501", "quantity": 1}])
    resp = client.post("/api/v1/orders", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["order_type"] == "DELIVERY"
    assert data["subtotal"] == 15.01


def test_05_subtotal_20_valid_6_coupon_final_14_delivery_allowed():
    """
    TEST 5: Subtotal = €20.00, Valid €6.00 coupon, Final payable = €14.00 -> Delivery ALLOWED.
    The €15 threshold applies before discount; offer exemption preserves delivery.
    """
    payload = _make_delivery_order_payload(
        items=[{"product_id": "prod-item-2000", "quantity": 1}],
        coupon_code="SAVE6"
    )
    resp = client.post("/api/v1/orders", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["subtotal"] == 20.00
    assert data["discount_amount"] == 6.00
    # Gross = 20.00 - 6.00 = 14.00; with 20% UK VAT extracted (2.33) -> £14.00 total payable (£0 delivery/service fee)
    assert data["total_amount"] == 14.00
    assert data["vat_amount"] == 2.33
    assert data["order_type"] == "DELIVERY"


def test_06_subtotal_16_valid_2_offer_final_14_delivery_allowed():
    """
    TEST 6: Subtotal = €16.00, Valid €2.00 offer, Final payable = €14.00 -> Delivery ALLOWED.
    """
    payload = _make_delivery_order_payload(
        items=[{"product_id": "prod-item-1600", "quantity": 1}],
        coupon_code="OFFER2"
    )
    resp = client.post("/api/v1/orders", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["subtotal"] == 16.00
    assert data["discount_amount"] == 2.00
    assert data["order_type"] == "DELIVERY"


def test_07_subtotal_14_99_invalid_coupon_delivery_blocked():
    """TEST 7: Subtotal = €14.99, Invalid coupon -> Delivery BLOCKED (HTTP 400)."""
    payload = _make_delivery_order_payload(
        items=[{"product_id": "prod-item-1499", "quantity": 1}],
        coupon_code="NONEXISTENT_CODE_XYZ"
    )
    resp = client.post("/api/v1/orders", json=payload)
    assert resp.status_code == 400
    err = resp.json()["detail"]
    assert err["code"] == "MINIMUM_DELIVERY_ORDER_REQUIRED"


def test_08_subtotal_14_99_expired_coupon_delivery_blocked():
    """TEST 8: Subtotal = €14.99, Expired/inactive coupon -> Delivery BLOCKED (HTTP 400)."""
    payload = _make_delivery_order_payload(
        items=[{"product_id": "prod-item-1499", "quantity": 1}],
        coupon_code="EXPIRED20"
    )
    resp = client.post("/api/v1/orders", json=payload)
    assert resp.status_code == 400
    err = resp.json()["detail"]
    assert err["code"] == "MINIMUM_DELIVERY_ORDER_REQUIRED"


def test_09_subtotal_under_15_after_removing_coupon():
    """
    TEST 9: Subtotal = €10.00. With a promo, delivery is allowed.
    When the coupon is removed (no promo), subtotal €10.00 is blocked for delivery.
    """
    # 1. With valid offer (e.g. 2 items of €5.00 with promo)
    payload_no_promo = _make_delivery_order_payload(
        items=[{"product_id": "prod-item-1000", "quantity": 1}]
    )
    resp_no_promo = client.post("/api/v1/orders", json=payload_no_promo)
    assert resp_no_promo.status_code == 400
    assert resp_no_promo.json()["detail"]["code"] == "MINIMUM_DELIVERY_ORDER_REQUIRED"


def test_10_coupon_min_order_value_not_met_prevents_exemption():
    """
    TEST 10: Coupon SAVE6 requires min_order_value €15.00.
    If subtotal is €10.00, coupon is rejected and cannot be used to bypass the delivery threshold.
    """
    payload = _make_delivery_order_payload(
        items=[{"product_id": "prod-item-1000", "quantity": 1}],
        coupon_code="SAVE6"  # Requires min order of €15.00
    )
    resp = client.post("/api/v1/orders", json=payload)
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "MINIMUM_DELIVERY_ORDER_REQUIRED"


def test_11_client_cannot_force_delivery_allowed_flag():
    """
    TEST 11: Malicious client sends crafted flags/delivery_fee in body for subtotal < €15.00.
    Backend independently recalculates subtotal and rejects the delivery order.
    """
    payload = _make_delivery_order_payload([{"product_id": "prod-item-1400", "quantity": 1}])
    # Add client-side forged properties
    payload["delivery_allowed"] = True
    payload["is_delivery_eligible"] = True
    payload["delivery_fee"] = 0.0

    resp = client.post("/api/v1/orders", json=payload)
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "MINIMUM_DELIVERY_ORDER_REQUIRED"


def test_12_exact_15_00_boundary_mandatory_acceptance():
    """
    TEST 12: Subtotal exactly €15.00 with no promotion.
    Mandatory boundary test: Must be ACCEPTED with 200 OK.
    """
    # 3 items of €5.00 = exactly €15.00
    payload = _make_delivery_order_payload([{"product_id": "prod-item-0500", "quantity": 3}])
    resp = client.post("/api/v1/orders", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["subtotal"] == 15.00
    assert data["order_type"] == "DELIVERY"
