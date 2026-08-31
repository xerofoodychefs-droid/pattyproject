import pytest
from app.tests.db import client, reset_test_db, TestingSessionLocal
from app.models.promotion import Coupon
from app.models.user import User, UserRole
from app.core.security import create_access_token
from app.db.seed import seed_system_promotions

@pytest.fixture(autouse=True)
def setup_db():
    reset_test_db()

def get_super_admin_token() -> str:
    return create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])

def test_01_all_six_system_promos_exist_in_db():
    """Ensure all 6 system promos are seeded and exist in the database."""
    db = TestingSessionLocal()
    try:
        codes = ["COMBO15", "FEAST20", "PATTY10", "WELCOME20", "LUNCH599", "SHAKEUP"]
        for code in codes:
            c = db.query(Coupon).filter(Coupon.code == code).first()
            assert c is not None, f"Coupon {code} should exist in database"
            assert c.is_active is True, f"Coupon {code} should be active"
    finally:
        db.close()

def test_02_get_available_promos_returns_active_db_coupons():
    """Ensure GET /available returns active database coupons."""
    resp = client.get("/api/v1/promotions/available")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    available_codes = [c["code"] for c in data]
    for code in ["COMBO15", "FEAST20", "PATTY10", "WELCOME20", "LUNCH599", "SHAKEUP"]:
        assert code in available_codes, f"Code {code} should be in available coupons"

def test_03_validate_active_coupon_success():
    """Ensure GET /validate returns valid discount for active database coupon."""
    resp = client.get("/api/v1/promotions/validate?code=COMBO15&subtotal=20.0")
    assert resp.status_code == 200
    res = resp.json()
    assert res["valid"] is True
    assert res["code"] == "COMBO15"
    assert res["discount_amount"] == 3.0  # 15% of 20.0
    assert res["coupon_type"] == "PERCENTAGE"

def test_04_validate_coupon_min_order_enforcement():
    """Ensure GET /validate rejects subtotal below min_order_value."""
    # FEAST20 has min_order_value = 20.0
    resp = client.get("/api/v1/promotions/validate?code=FEAST20&subtotal=10.0")
    assert resp.status_code == 400
    assert "minimum order" in resp.json()["detail"].lower()

def test_05_deactivated_coupon_is_hidden_from_available_and_rejected_in_validate():
    """CRITICAL SAFETY TEST: When an admin soft-deletes/deactivates a coupon,
    it MUST NOT appear in /available and MUST be rejected by /validate.
    No hardcoded fallback may resurrect it."""
    db = TestingSessionLocal()
    try:
        # Find WELCOME20
        coupon = db.query(Coupon).filter(Coupon.code == "WELCOME20").first()
        assert coupon is not None
        coupon_id = coupon.id
    finally:
        db.close()

    admin_headers = {"Authorization": f"Bearer {get_super_admin_token()}"}

    # Admin soft deletes the coupon
    del_resp = client.delete(f"/api/v1/promotions/coupons/{coupon_id}", headers=admin_headers)
    assert del_resp.status_code == 200

    # Verify in DB
    db = TestingSessionLocal()
    try:
        coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
        assert coupon.is_active is False
    finally:
        db.close()

    # Verify it is NOT in available coupons
    avail_resp = client.get("/api/v1/promotions/available")
    assert avail_resp.status_code == 200
    avail_codes = [c["code"] for c in avail_resp.json()]
    assert "WELCOME20" not in avail_codes, "Deactivated coupon WELCOME20 must NOT be in available promos"

    # Verify it is REJECTED by validate (No fallback resurrection!)
    val_resp = client.get("/api/v1/promotions/validate?code=WELCOME20&subtotal=50.0")
    assert val_resp.status_code == 400
    assert "invalid or expired" in val_resp.json()["detail"].lower()

def test_06_admin_list_coupons_cache_header():
    """Ensure /coupons uses real-time cache headers so admin gets immediate updates."""
    resp = client.get("/api/v1/promotions/coupons")
    assert resp.status_code == 200
    assert "no-cache" in resp.headers.get("cache-control", "")

def test_07_seed_idempotency_does_not_duplicate_or_overwrite():
    """Ensure running seed_system_promotions multiple times preserves existing customized values."""
    db = TestingSessionLocal()
    try:
        # Set PATTY10 to custom min_order_value = 15.0
        patty = db.query(Coupon).filter(Coupon.code == "PATTY10").first()
        if patty:
            patty.min_order_value = 15.0
            db.commit()

        count_before = db.query(Coupon).count()
        seed_system_promotions(db)
        count_after = db.query(Coupon).count()
        assert count_before == count_after, "Seed must not duplicate existing coupon records"

        patty_after = db.query(Coupon).filter(Coupon.code == "PATTY10").first()
        assert patty_after.min_order_value == 15.0, "Seed must not overwrite existing admin customization"
    finally:
        db.close()
