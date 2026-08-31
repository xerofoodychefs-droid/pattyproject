from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo
import pytest

from app.models.setting import ShopSetting
from app.models.user import User, UserRole
from app.models.branch import Branch
from app.models.product import Product, Category, Inventory
from app.models.cart import Cart
from app.core.security import create_access_token
from app.services.shop_hours_service import (
    is_shop_open,
    parse_time_string,
    get_or_create_shop_settings,
    get_authoritative_shop_status,
    validate_shop_open_for_ordering,
    UK_TZ
)
from app.core.websocket_manager import manager
from app.tests.db import client, TestingSessionLocal, reset_test_db

UK = ZoneInfo("Europe/London")


@pytest.fixture(autouse=True)
def setup_db():
    reset_test_db()
    yield


# =============================================================================
# 1. TIME PARSING & INTERVAL EVALUATION UNIT TESTS
# =============================================================================
def test_parse_time_string():
    assert parse_time_string("11:00") == time(11, 0)
    assert parse_time_string("00:00") == time(0, 0)
    assert parse_time_string("23:59") == time(23, 59)
    assert parse_time_string(" 08:30 ") == time(8, 30)
    assert parse_time_string("24:00") is None
    assert parse_time_string("11:60") is None
    assert parse_time_string("invalid") is None
    assert parse_time_string(None) is None


def test_is_shop_open_daytime_schedule():
    # 11:00 AM to 11:00 PM (11:00 - 23:00)
    open_t = "11:00"
    close_t = "23:00"

    # Exactly at opening time: 11:00 -> OPEN
    dt_open = datetime(2026, 8, 31, 11, 0, 0, tzinfo=UK)
    is_o, reason = is_shop_open(open_t, close_t, at_dt=dt_open)
    assert is_o is True
    assert reason == "OPEN"

    # Midday: 15:30 -> OPEN
    dt_mid = datetime(2026, 8, 31, 15, 30, 0, tzinfo=UK)
    is_o, reason = is_shop_open(open_t, close_t, at_dt=dt_mid)
    assert is_o is True
    assert reason == "OPEN"

    # Just before closing: 22:59 -> OPEN
    dt_late = datetime(2026, 8, 31, 22, 59, 59, tzinfo=UK)
    is_o, reason = is_shop_open(open_t, close_t, at_dt=dt_late)
    assert is_o is True
    assert reason == "OPEN"

    # Exactly at closing time: 23:00 -> CLOSED (half-open [start, end))
    dt_close = datetime(2026, 8, 31, 23, 0, 0, tzinfo=UK)
    is_o, reason = is_shop_open(open_t, close_t, at_dt=dt_close)
    assert is_o is False
    assert reason == "OUTSIDE_HOURS"

    # Morning before open: 09:00 -> CLOSED
    dt_morning = datetime(2026, 8, 31, 9, 0, 0, tzinfo=UK)
    is_o, reason = is_shop_open(open_t, close_t, at_dt=dt_morning)
    assert is_o is False
    assert reason == "OUTSIDE_HOURS"


def test_is_shop_open_overnight_schedule():
    # 18:00 to 02:00 (crosses midnight)
    open_t = "18:00"
    close_t = "02:00"

    # Evening before midnight: 21:00 -> OPEN
    dt_evening = datetime(2026, 8, 31, 21, 0, 0, tzinfo=UK)
    is_o, reason = is_shop_open(open_t, close_t, at_dt=dt_evening)
    assert is_o is True
    assert reason == "OPEN"

    # Midnight crossing: 00:00 -> OPEN
    dt_midnight = datetime(2026, 9, 1, 0, 0, 0, tzinfo=UK)
    is_o, reason = is_shop_open(open_t, close_t, at_dt=dt_midnight)
    assert is_o is True
    assert reason == "OPEN"

    # Early morning before close: 01:45 -> OPEN
    dt_early_am = datetime(2026, 9, 1, 1, 45, 0, tzinfo=UK)
    is_o, reason = is_shop_open(open_t, close_t, at_dt=dt_early_am)
    assert is_o is True
    assert reason == "OPEN"

    # Exactly at closing: 02:00 -> CLOSED
    dt_close = datetime(2026, 9, 1, 2, 0, 0, tzinfo=UK)
    is_o, reason = is_shop_open(open_t, close_t, at_dt=dt_close)
    assert is_o is False
    assert reason == "OUTSIDE_HOURS"

    # Daytime: 14:00 -> CLOSED
    dt_day = datetime(2026, 8, 31, 14, 0, 0, tzinfo=UK)
    is_o, reason = is_shop_open(open_t, close_t, at_dt=dt_day)
    assert is_o is False
    assert reason == "OUTSIDE_HOURS"


def test_is_shop_open_edge_cases():
    # Equal times: invalid -> CLOSED
    is_o, reason = is_shop_open("11:00", "11:00")
    assert is_o is False
    assert reason == "INVALID_HOURS"

    # None / Empty
    is_o, reason = is_shop_open(None, "23:00")
    assert is_o is False
    assert reason == "INVALID_HOURS"

    is_o, reason = is_shop_open("11:00", "")
    assert is_o is False
    assert reason == "INVALID_HOURS"


def test_uk_daylight_saving_handling():
    # In Summer (BST = UTC+1): 11:30 BST corresponds to 10:30 UTC -> OPEN
    dt_summer_utc = datetime(2026, 7, 15, 10, 30, 0, tzinfo=timezone.utc)
    is_o, _ = is_shop_open("11:00", "23:00", at_dt=dt_summer_utc)
    assert is_o is True

    # In Summer (BST = UTC+1): 23:30 BST corresponds to 22:30 UTC -> CLOSED
    dt_summer_closed_utc = datetime(2026, 7, 15, 22, 30, 0, tzinfo=timezone.utc)
    is_o, _ = is_shop_open("11:00", "23:00", at_dt=dt_summer_closed_utc)
    assert is_o is False

    # In Winter (GMT = UTC+0): 11:30 GMT corresponds to 11:30 UTC -> OPEN
    dt_winter_utc = datetime(2026, 1, 15, 11, 30, 0, tzinfo=timezone.utc)
    is_o, _ = is_shop_open("11:00", "23:00", at_dt=dt_winter_utc)
    assert is_o is True


# =============================================================================
# 2. PUBLIC & ADMIN API ENDPOINT TESTS
# =============================================================================
def test_public_shop_status_endpoint():
    db = TestingSessionLocal()
    get_or_create_shop_settings(db)
    db.close()

    response = client.get("/api/v1/shop/status")
    assert response.status_code == 200
    data = response.json()
    assert "is_open" in data
    assert "opening_time" in data
    assert "closing_time" in data
    assert "reason" in data
    assert data["timezone"] == "Europe/London"


def test_super_admin_get_and_patch_settings():
    db = TestingSessionLocal()
    super_admin = User(id="sa-shop-1", email="super_shop@patty.co.uk", full_name="Super Admin", role=UserRole.SUPER_ADMIN, is_active=True)
    db.add(super_admin)
    db.commit()

    sa_token = create_access_token(subject="sa-shop-1", roles=[UserRole.SUPER_ADMIN])
    headers = {"Authorization": f"Bearer {sa_token}"}
    db.close()

    # GET settings
    get_res = client.get("/api/v1/shop/admin/settings", headers=headers)
    assert get_res.status_code == 200
    data = get_res.json()
    assert "opening_time" in data
    assert "closing_time" in data

    # PATCH settings to new hours
    patch_res = client.patch(
        "/api/v1/shop/admin/settings",
        json={"opening_time": "10:00", "closing_time": "22:00"},
        headers=headers
    )
    assert patch_res.status_code == 200
    updated_data = patch_res.json()
    assert updated_data["opening_time"] == "10:00"
    assert updated_data["closing_time"] == "22:00"

    # Verify DB persistence
    db = TestingSessionLocal()
    setting = db.query(ShopSetting).filter(ShopSetting.key == "global").first()
    assert setting.opening_time == "10:00"
    assert setting.closing_time == "22:00"
    db.close()


def test_branch_admin_cannot_update_settings():
    db = TestingSessionLocal()
    branch_admin = User(id="ba-shop-1", email="ba_shop@patty.co.uk", full_name="Branch Admin", role=UserRole.BRANCH_ADMIN, is_active=True)
    db.add(branch_admin)
    db.commit()

    ba_token = create_access_token(subject="ba-shop-1", roles=[UserRole.BRANCH_ADMIN])
    headers = {"Authorization": f"Bearer {ba_token}"}
    db.close()

    response = client.patch(
        "/api/v1/shop/admin/settings",
        json={"opening_time": "09:00", "closing_time": "21:00"},
        headers=headers
    )
    assert response.status_code == 403
    assert "Super Administrators" in response.json()["detail"]


def test_customer_cannot_update_settings():
    db = TestingSessionLocal()
    customer = User(id="cust-shop-1", email="cust_shop@patty.co.uk", full_name="Customer", role=UserRole.CUSTOMER, is_active=True)
    db.add(customer)
    db.commit()

    cust_token = create_access_token(subject="cust-shop-1", roles=[UserRole.CUSTOMER])
    headers = {"Authorization": f"Bearer {cust_token}"}
    db.close()

    response = client.patch(
        "/api/v1/shop/admin/settings",
        json={"opening_time": "09:00", "closing_time": "21:00"},
        headers=headers
    )
    assert response.status_code == 403


def test_unauthenticated_cannot_update_settings():
    response = client.patch(
        "/api/v1/shop/admin/settings",
        json={"opening_time": "09:00", "closing_time": "21:00"}
    )
    assert response.status_code in [401, 403]


def test_identical_times_rejected():
    db = TestingSessionLocal()
    super_admin = User(id="sa-shop-2", email="sa2_shop@patty.co.uk", full_name="Super Admin 2", role=UserRole.SUPER_ADMIN, is_active=True)
    db.add(super_admin)
    db.commit()

    sa_token = create_access_token(subject="sa-shop-2", roles=[UserRole.SUPER_ADMIN])
    headers = {"Authorization": f"Bearer {sa_token}"}
    db.close()

    response = client.patch(
        "/api/v1/shop/admin/settings",
        json={"opening_time": "12:00", "closing_time": "12:00"},
        headers=headers
    )
    assert response.status_code == 400
    assert "identical" in response.json()["detail"].lower()


# =============================================================================
# 3. BACKEND ENFORCEMENT TESTS (Cart & Orders)
# =============================================================================
def test_cart_and_order_enforcement_when_shop_closed():
    db = TestingSessionLocal()

    # Set shop hours so that the shop is definitively CLOSED right now
    setting = get_or_create_shop_settings(db)
    now_uk = datetime.now(UK_TZ)
    if now_uk.hour >= 12:
        setting.opening_time = "03:00"
        setting.closing_time = "04:00"
    else:
        setting.opening_time = "22:00"
        setting.closing_time = "23:00"
    db.commit()
    db.close()

    # 1. Attempt adding item to cart -> Must fail with 400
    cart_res = client.post(
        "/api/v1/cart/items",
        json={"product_id": "prod-mc-project", "quantity": 1},
        headers={"X-Guest-Session-ID": "test-closed-cart-session"}
    )
    assert cart_res.status_code == 400
    assert "closed" in cart_res.json()["detail"].lower()

    # 2. Attempt creating an order -> Must fail with 400
    order_res = client.post(
        "/api/v1/orders/",
        json={
            "branch_id": "branch-camden-001",
            "order_type": "COLLECTION",
            "customer_name": "Test User",
            "customer_phone": "07123456789",
            "customer_email": "test@example.com",
            "items": [{"product_id": "prod-mc-project", "quantity": 1}]
        }
    )
    assert order_res.status_code == 400
    assert "closed" in order_res.json()["detail"].lower()


# =============================================================================
# 4. WEBSOCKET BROADCAST METHOD TESTS
# =============================================================================
def test_websocket_broadcast_methods():
    # Verify manager methods execute cleanly without unhandled exceptions
    manager.sync_broadcast_shop_status(
        is_open=True,
        opening_time="11:00",
        closing_time="23:00",
        reason="OPEN"
    )
    manager.sync_broadcast_shop_status(
        is_open=False,
        opening_time="11:00",
        closing_time="23:00",
        reason="OUTSIDE_HOURS"
    )
