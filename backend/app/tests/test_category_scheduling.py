import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.database import Base
from app.models.product import Category, Product, Inventory
from app.models.branch import Branch
from app.models.user import User, UserRole
from app.core.security import create_access_token
from app.services.availability_service import (
    is_category_schedule_open,
    get_category_schedule_status,
    is_product_effective_available,
    validate_order_items_availability,
    UK_TZ
)
from app.tests.db import client, TestingSessionLocal, engine, reset_test_db


@pytest.fixture(autouse=True)
def setup_db():
    reset_test_db()
    yield


def test_time_boundaries_half_open_interval():
    """
    Test exact half-open time boundaries: start <= current < end.
    For schedule 08:00 -> 12:00 in Europe/London:
    07:59:59 -> CLOSED
    08:00:00 -> OPEN
    08:00:01 -> OPEN
    11:59:59 -> OPEN
    12:00:00 -> CLOSED
    12:00:01 -> CLOSED
    """
    cat = Category(
        name="Breakfast",
        slug="breakfast",
        is_active=True,
        schedule_enabled=True,
        schedule_start_time="08:00",
        schedule_end_time="12:00"
    )

    # 07:59:59 UK time
    t1 = datetime(2026, 6, 15, 7, 59, 59, tzinfo=UK_TZ)
    assert is_category_schedule_open(cat, at_dt=t1) is False
    assert get_category_schedule_status(cat, at_dt=t1) == "CLOSED"

    # 08:00:00 UK time (Exact start boundary -> OPEN)
    t2 = datetime(2026, 6, 15, 8, 0, 0, tzinfo=UK_TZ)
    assert is_category_schedule_open(cat, at_dt=t2) is True
    assert get_category_schedule_status(cat, at_dt=t2) == "OPEN"

    # 08:00:01 UK time
    t3 = datetime(2026, 6, 15, 8, 0, 1, tzinfo=UK_TZ)
    assert is_category_schedule_open(cat, at_dt=t3) is True

    # 11:59:59 UK time
    t4 = datetime(2026, 6, 15, 11, 59, 59, tzinfo=UK_TZ)
    assert is_category_schedule_open(cat, at_dt=t4) is True
    assert get_category_schedule_status(cat, at_dt=t4) == "OPEN"

    # 12:00:00 UK time (Exact end boundary -> CLOSED)
    t5 = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UK_TZ)
    assert is_category_schedule_open(cat, at_dt=t5) is False
    assert get_category_schedule_status(cat, at_dt=t5) == "CLOSED"

    # 12:00:01 UK time
    t6 = datetime(2026, 6, 15, 12, 0, 1, tzinfo=UK_TZ)
    assert is_category_schedule_open(cat, at_dt=t6) is False


def test_overnight_schedule_crossing_midnight():
    """
    Test overnight schedules crossing midnight (start > end).
    For schedule 18:00 -> 02:00 in Europe/London:
    17:59:59 -> CLOSED
    18:00:00 -> OPEN
    23:59:59 -> OPEN
    00:00:00 -> OPEN
    01:59:59 -> OPEN
    02:00:00 -> CLOSED
    02:00:01 -> CLOSED
    """
    cat = Category(
        name="Late Night",
        slug="late-night",
        is_active=True,
        schedule_enabled=True,
        schedule_start_time="18:00",
        schedule_end_time="02:00"
    )

    # 17:59:59
    assert is_category_schedule_open(cat, at_dt=datetime(2026, 6, 15, 17, 59, 59, tzinfo=UK_TZ)) is False

    # 18:00:00 (Start boundary -> OPEN)
    assert is_category_schedule_open(cat, at_dt=datetime(2026, 6, 15, 18, 0, 0, tzinfo=UK_TZ)) is True

    # 23:59:59
    assert is_category_schedule_open(cat, at_dt=datetime(2026, 6, 15, 23, 59, 59, tzinfo=UK_TZ)) is True

    # 00:00:00 (Midnight -> OPEN)
    assert is_category_schedule_open(cat, at_dt=datetime(2026, 6, 16, 0, 0, 0, tzinfo=UK_TZ)) is True

    # 01:59:59
    assert is_category_schedule_open(cat, at_dt=datetime(2026, 6, 16, 1, 59, 59, tzinfo=UK_TZ)) is True

    # 02:00:00 (End boundary -> CLOSED)
    assert is_category_schedule_open(cat, at_dt=datetime(2026, 6, 16, 2, 0, 0, tzinfo=UK_TZ)) is False

    # 02:00:01
    assert is_category_schedule_open(cat, at_dt=datetime(2026, 6, 16, 2, 0, 1, tzinfo=UK_TZ)) is False


def test_disabled_schedule_retains_normal_availability():
    """
    When schedule_enabled is False, category is available 24/7 without time restrictions.
    """
    cat = Category(
        name="Drinks",
        slug="drinks",
        is_active=True,
        schedule_enabled=False,
        schedule_start_time="08:00",
        schedule_end_time="12:00"
    )

    t_midnight = datetime(2026, 6, 15, 3, 0, 0, tzinfo=UK_TZ)
    assert is_category_schedule_open(cat, at_dt=t_midnight) is True
    assert get_category_schedule_status(cat, at_dt=t_midnight) == "DISABLED"


def test_multiple_categories_independent_schedules():
    """
    Test multiple categories evaluated independently at different UK wall-clock times.
    """
    breakfast = Category(name="Breakfast", slug="breakfast", is_active=True, schedule_enabled=True, schedule_start_time="08:00", schedule_end_time="12:00")
    burgers = Category(name="Burgers", slug="burgers", is_active=True, schedule_enabled=True, schedule_start_time="12:00", schedule_end_time="23:00")
    tenders = Category(name="Tenders", slug="tenders", is_active=True, schedule_enabled=True, schedule_start_time="17:00", schedule_end_time="22:00")
    drinks = Category(name="Drinks", slug="drinks", is_active=True, schedule_enabled=False)

    # 10:30 UK time
    t_1030 = datetime(2026, 6, 15, 10, 30, 0, tzinfo=UK_TZ)
    assert is_category_schedule_open(breakfast, at_dt=t_1030) is True
    assert is_category_schedule_open(burgers, at_dt=t_1030) is False
    assert is_category_schedule_open(tenders, at_dt=t_1030) is False
    assert is_category_schedule_open(drinks, at_dt=t_1030) is True

    # 14:00 UK time
    t_1400 = datetime(2026, 6, 15, 14, 0, 0, tzinfo=UK_TZ)
    assert is_category_schedule_open(breakfast, at_dt=t_1400) is False
    assert is_category_schedule_open(burgers, at_dt=t_1400) is True
    assert is_category_schedule_open(tenders, at_dt=t_1400) is False
    assert is_category_schedule_open(drinks, at_dt=t_1400) is True

    # 19:00 UK time
    t_1900 = datetime(2026, 6, 15, 19, 0, 0, tzinfo=UK_TZ)
    assert is_category_schedule_open(breakfast, at_dt=t_1900) is False
    assert is_category_schedule_open(burgers, at_dt=t_1900) is True
    assert is_category_schedule_open(tenders, at_dt=t_1900) is True
    assert is_category_schedule_open(drinks, at_dt=t_1900) is True


def test_stock_invariance_under_schedule_changes():
    """
    CRITICAL: Category scheduling must never mutate actual product stock or inventory records.
    Stock = 20 remains exactly 20 when schedule is OPEN and when schedule is CLOSED.
    """
    db = TestingSessionLocal()
    cat = Category(id="cat-inv-1", name="Breakfast", slug="breakfast", is_active=True, schedule_enabled=True, schedule_start_time="08:00", schedule_end_time="12:00")
    prod = Product(id="prod-inv-1", category_id="cat-inv-1", name="Morning Roll", sku="ROLL-01", base_price=4.50, is_active=True, is_out_of_stock=False)
    branch = Branch(id="br-inv-1", code="BR1", name="Central", address_line1="1 High St", postcode="W1 1AA", city="London", latitude=51.5, longitude=-0.1, is_active=True)
    inv = Inventory(id="inv-1", branch_id="br-inv-1", product_id="prod-inv-1", stock_quantity=20, is_available=True)

    db.add_all([cat, prod, branch, inv])
    db.commit()

    prod.category = cat

    # At 10:00 (OPEN): Effective availability is True, Stock is 20
    t_open = datetime(2026, 6, 15, 10, 0, 0, tzinfo=UK_TZ)
    is_avail, _ = is_product_effective_available(prod, branch_id="br-inv-1", db=db, at_dt=t_open)
    assert is_avail is True
    db.refresh(inv)
    assert inv.stock_quantity == 20

    # At 12:00 (CLOSED): Effective availability is False, Stock MUST STILL BE 20
    t_closed = datetime(2026, 6, 15, 12, 0, 0, tzinfo=UK_TZ)
    is_avail, reason = is_product_effective_available(prod, branch_id="br-inv-1", db=db, at_dt=t_closed)
    assert is_avail is False
    assert "outside its serving hours" in reason
    db.refresh(inv)
    assert inv.stock_quantity == 20  # Never mutated
    assert prod.is_out_of_stock is False  # Never mutated

    db.close()


def test_uk_daylight_saving_transitions():
    """
    Test Europe/London timezone handling across GMT (UTC+0) in winter and BST (UTC+1) in summer.
    A schedule of 08:00 -> 12:00 operates on UK wall-clock time in both seasons.
    """
    cat = Category(
        name="Breakfast",
        slug="breakfast",
        is_active=True,
        schedule_enabled=True,
        schedule_start_time="08:00",
        schedule_end_time="12:00"
    )

    # Summer (BST = UTC+1): 08:30 BST corresponds to 07:30 UTC
    dt_summer_utc = datetime(2026, 7, 15, 7, 30, 0, tzinfo=timezone.utc)
    assert is_category_schedule_open(cat, at_dt=dt_summer_utc) is True

    # Summer (BST = UTC+1): 12:30 BST corresponds to 11:30 UTC -> CLOSED
    dt_summer_closed = datetime(2026, 7, 15, 11, 30, 0, tzinfo=timezone.utc)
    assert is_category_schedule_open(cat, at_dt=dt_summer_closed) is False

    # Winter (GMT = UTC+0): 08:30 GMT corresponds to 08:30 UTC
    dt_winter_utc = datetime(2026, 1, 15, 8, 30, 0, tzinfo=timezone.utc)
    assert is_category_schedule_open(cat, at_dt=dt_winter_utc) is True


def test_admin_rbac_schedule_configuration():
    """
    Test Super Admin permissions vs unauthorized roles on category schedule configuration endpoint.
    """
    db = TestingSessionLocal()
    super_admin = User(id="sa-user-1", email="super@pattyproject.co.uk", full_name="Super Admin", role=UserRole.SUPER_ADMIN, is_active=True)
    branch_admin = User(id="ba-user-1", email="branch@pattyproject.co.uk", full_name="Branch Admin", role=UserRole.BRANCH_ADMIN, is_active=True)
    cat = Category(id="cat-sched-api-1", name="Breakfast", slug="breakfast", is_active=True, schedule_enabled=False)

    db.add_all([super_admin, branch_admin, cat])
    db.commit()

    sa_token = create_access_token(subject=super_admin.id, roles=[UserRole.SUPER_ADMIN])
    ba_token = create_access_token(subject=branch_admin.id, roles=[UserRole.BRANCH_ADMIN])

    # 1. Unauthenticated -> 401
    resp = client.put(f"/api/v1/categories/{cat.id}/schedule", json={"schedule_enabled": True, "schedule_start_time": "08:00", "schedule_end_time": "12:00"})
    assert resp.status_code == 401

    # 2. Branch Admin -> 403 Forbidden
    resp = client.put(
        f"/api/v1/categories/{cat.id}/schedule",
        headers={"Authorization": f"Bearer {ba_token}"},
        json={"schedule_enabled": True, "schedule_start_time": "08:00", "schedule_end_time": "12:00"}
    )
    assert resp.status_code == 403

    # 3. Super Admin equal start/end validation -> 400 Bad Request
    resp = client.put(
        f"/api/v1/categories/{cat.id}/schedule",
        headers={"Authorization": f"Bearer {sa_token}"},
        json={"schedule_enabled": True, "schedule_start_time": "08:00", "schedule_end_time": "08:00"}
    )
    assert resp.status_code == 400
    assert "Start time and end time cannot be equal" in resp.json()["detail"]

    # 4. Super Admin valid save -> 200 OK
    resp = client.put(
        f"/api/v1/categories/{cat.id}/schedule",
        headers={"Authorization": f"Bearer {sa_token}"},
        json={"schedule_enabled": True, "schedule_start_time": "08:00", "schedule_end_time": "12:00"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["schedule_enabled"] is True
    assert data["schedule_start_time"] == "08:00"
    assert data["schedule_end_time"] == "12:00"

    db.close()


def test_cart_add_validation_against_schedule():
    """
    Test cart addition is blocked if category schedule is closed.
    """
    db = TestingSessionLocal()
    # Schedule configured for 01:00 -> 02:00 (closed during normal daytime test execution)
    cat = Category(id="cat-cart-1", name="Early Bird", slug="early-bird", is_active=True, schedule_enabled=True, schedule_start_time="01:00", schedule_end_time="02:00")
    prod = Product(id="prod-cart-1", category_id="cat-cart-1", name="Early Bird Muffin", sku="MUFF-01", base_price=3.95, is_active=True, is_out_of_stock=False)
    db.add_all([cat, prod])
    db.commit()

    # If current time is outside 01:00-02:00, adding to cart should fail with HTTP 400
    now_uk = datetime.now(UK_TZ)
    if not (1 <= now_uk.hour < 2):
        resp = client.post(
            "/api/v1/cart/items",
            headers={"X-Guest-Session-ID": "test-cart-session-1"},
            json={"product_id": "prod-cart-1", "quantity": 1}
        )
        assert resp.status_code == 400
        assert "outside its serving hours" in resp.json()["detail"]

    db.close()


def test_stale_cart_and_order_creation_rejection():
    """
    CRITICAL ACCEPTANCE TEST:
    1. Direct API order creation with an item from a closed category MUST be rejected.
    2. Stale carts where category closes before order submission are rejected.
    """
    db = TestingSessionLocal()
    branch = Branch(
        id="br-order-1",
        code="BR1",
        name="London Central",
        address_line1="1 Oxford St",
        postcode="W1D 1BS",
        city="London",
        latitude=51.515,
        longitude=-0.130,
        is_active=True,
        ordering_enabled=True,
        collection_enabled=True,
        delivery_enabled=True
    )
    cat_closed = Category(
        id="cat-order-closed",
        name="Night Feast",
        slug="night-feast",
        is_active=True,
        schedule_enabled=True,
        schedule_start_time="03:00",
        schedule_end_time="04:00"  # Closed right now
    )
    prod_closed = Product(
        id="prod-order-closed",
        category_id="cat-order-closed",
        name="Midnight Burger",
        sku="MIDNIGHT-01",
        base_price=9.95,
        is_active=True,
        is_out_of_stock=False
    )

    db.add_all([branch, cat_closed, prod_closed])
    db.commit()

    now_uk = datetime.now(UK_TZ)
    if not (3 <= now_uk.hour < 4):
        # Attempt order creation
        order_payload = {
            "branch_id": "br-order-1",
            "order_type": "COLLECTION",
            "customer_name": "John Doe",
            "customer_email": "john@example.com",
            "customer_phone": "07123456789",
            "items": [
                {
                    "product_id": "prod-order-closed",
                    "quantity": 1,
                    "selected_modifiers": [],
                    "selected_choices": []
                }
            ]
        }

        resp = client.post("/api/v1/orders", json=order_payload)
        assert resp.status_code == 400
        assert "outside its serving hours" in resp.json()["detail"]

    db.close()


def test_product_api_effective_availability_reflection():
    """
    Test GET /api/v1/products and GET /api/v1/products/{id} return is_available: false
    when category schedule is closed, without modifying physical stock or is_out_of_stock flag.
    """
    db = TestingSessionLocal()
    cat_closed = Category(
        id="cat-api-closed",
        name="Night Grill",
        slug="night-grill",
        is_active=True,
        schedule_enabled=True,
        schedule_start_time="03:00",
        schedule_end_time="04:00"
    )
    prod = Product(
        id="prod-api-closed",
        category_id="cat-api-closed",
        name="Night Wings",
        sku="NWINGS-01",
        base_price=6.50,
        is_active=True,
        is_out_of_stock=False
    )
    db.add_all([cat_closed, prod])
    db.commit()

    now_uk = datetime.now(UK_TZ)
    if not (3 <= now_uk.hour < 4):
        # 1. Product listing
        resp = client.get(f"/api/v1/products?category_id={cat_closed.id}")
        assert resp.status_code == 200
        prods = resp.json()
        assert len(prods) == 1
        assert prods[0]["is_available"] is False
        assert prods[0]["is_out_of_stock"] is False  # Invariant: stock flag untouched

        # 2. Product details
        resp_detail = client.get(f"/api/v1/products/{prod.id}")
        assert resp_detail.status_code == 200
        detail = resp_detail.json()
        assert detail["is_available"] is False
        assert detail["is_out_of_stock"] is False

    db.close()


def test_stale_cart_simulation_state_transition():
    """
    Scenario:
    1. Category schedule is OFF -> User adds product to cart (succeeds).
    2. Admin enables schedule (setting it to currently closed).
    3. User submits checkout/order with previously added item -> Backend rejects with HTTP 400.
    """
    db = TestingSessionLocal()
    super_admin = User(id="sa-stale-1", email="super_stale@pattyproject.co.uk", full_name="Super Admin", role=UserRole.SUPER_ADMIN, is_active=True)
    branch = Branch(id="br-stale-1", code="BRS", name="Central", address_line1="1 High St", postcode="W1 1AA", city="London", latitude=51.5, longitude=-0.1, is_active=True, ordering_enabled=True, collection_enabled=True)
    cat = Category(id="cat-stale-1", name="Brunch", slug="brunch", is_active=True, schedule_enabled=False)
    prod = Product(id="prod-stale-1", category_id="cat-stale-1", name="Avocado Toast", sku="AVO-01", base_price=7.50, is_active=True, is_out_of_stock=False)

    db.add_all([super_admin, branch, cat, prod])
    db.commit()

    sa_token = create_access_token(subject=super_admin.id, roles=[UserRole.SUPER_ADMIN])

    # 1. Add item to cart while schedule is OFF -> Succeeds
    session_id = "stale-cart-session-123"
    resp_add = client.post(
        "/api/v1/cart/items",
        headers={"X-Guest-Session-ID": session_id},
        json={"product_id": prod.id, "quantity": 1}
    )
    assert resp_add.status_code == 200

    # 2. Admin enables schedule and sets it to closed (03:00 - 04:00)
    resp_sched = client.put(
        f"/api/v1/categories/{cat.id}/schedule",
        headers={"Authorization": f"Bearer {sa_token}"},
        json={"schedule_enabled": True, "schedule_start_time": "03:00", "schedule_end_time": "04:00"}
    )
    assert resp_sched.status_code == 200

    # 3. User attempts order creation -> Backend must reject stale item
    now_uk = datetime.now(UK_TZ)
    if not (3 <= now_uk.hour < 4):
        order_payload = {
            "branch_id": branch.id,
            "order_type": "COLLECTION",
            "customer_name": "Stale Customer",
            "customer_email": "customer@example.com",
            "customer_phone": "07000000000",
            "items": [{"product_id": prod.id, "quantity": 1}]
        }
        resp_order = client.post("/api/v1/orders", json=order_payload)
        assert resp_order.status_code == 400
        assert "outside its serving hours" in resp_order.json()["detail"]

    db.close()


def test_categories_list_schedule_fields_and_status():
    """
    Test GET /api/v1/categories returns schedule fields and calculated schedule_status.
    """
    db = TestingSessionLocal()
    c1 = Category(id="cat-list-1", name="Drinks", slug="drinks", is_active=True, display_order=1, schedule_enabled=False)
    c2 = Category(id="cat-list-2", name="Breakfast", slug="breakfast", is_active=True, display_order=2, schedule_enabled=True, schedule_start_time="08:00", schedule_end_time="12:00")
    db.add_all([c1, c2])
    db.commit()

    resp = client.get("/api/v1/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2

    cat_drinks = next(c for c in data if c["id"] == "cat-list-1")
    cat_bk = next(c for c in data if c["id"] == "cat-list-2")

    assert cat_drinks["schedule_enabled"] is False
    assert cat_drinks["schedule_status"] == "DISABLED"

    assert cat_bk["schedule_enabled"] is True
    assert cat_bk["schedule_start_time"] == "08:00"
    assert cat_bk["schedule_end_time"] == "12:00"
    assert cat_bk["schedule_status"] in ["OPEN", "CLOSED"]

    db.close()
