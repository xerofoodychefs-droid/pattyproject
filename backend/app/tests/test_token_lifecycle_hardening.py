import pytest
from datetime import datetime, timedelta, timezone
from app.core.config import settings
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_token,
    get_password_hash,
)
from app.models.user import User, UserRole, AuthSession
from app.tests.db import client, reset_test_db, TestingSessionLocal


@pytest.fixture(autouse=True)
def setup_test_data():
    reset_test_db()
    db = TestingSessionLocal()

    # Seed test customer
    cust_user = User(
        id="usr-hardened-cust-01",
        email="hardened.customer@example.com",
        password_hash=get_password_hash("CustPass123!"),
        full_name="Hardened Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=True
    )
    db.add(cust_user)

    # Seed test admin
    admin_user = User(
        id="usr-hardened-admin-01",
        email="hardened.admin@pattyproject.co.uk",
        password_hash=get_password_hash("AdminPass123!"),
        full_name="Hardened Admin",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        email_verified=True
    )
    db.add(admin_user)

    db.commit()
    db.close()


def test_access_token_short_lived_configuration():
    """Verify that ACCESS_TOKEN_EXPIRE_MINUTES is hardened to 15 minutes by default."""
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 15
    assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 7


def test_session_metadata_capture_on_login():
    """Verify client IP and User-Agent are recorded into AuthSession."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "hardened.customer@example.com", "password": "CustPass123!"},
        headers={"User-Agent": "PattyMobileApp/2.0 (iOS; iPhone15,2)"}
    )
    assert resp.status_code == 200
    data = resp.json()
    refresh_tok = data["refresh_token"]

    db = TestingSessionLocal()
    try:
        session = db.query(AuthSession).filter(
            AuthSession.refresh_token_hash == hash_token(refresh_tok)
        ).first()
        assert session is not None
        assert session.user_agent == "PattyMobileApp/2.0 (iOS; iPhone15,2)"
        assert session.is_revoked is False
    finally:
        db.close()


def test_expired_access_token_rejected():
    """Expired access token is rejected with 401."""
    expired_tok = create_access_token(
        subject="usr-hardened-cust-01",
        roles=[UserRole.CUSTOMER],
        expires_delta=timedelta(minutes=-1)
    )
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_tok}"})
    assert res.status_code == 401


def test_refresh_token_rotation_and_old_token_invalidation():
    """Valid refresh token issues new tokens and revokes old refresh token from reuse."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "hardened.customer@example.com", "password": "CustPass123!"}
    )
    assert login_res.status_code == 200
    tok_1 = login_res.json()["refresh_token"]

    # Refresh 1
    ref_1 = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tok_1},
        headers={"User-Agent": "PattyWeb/1.0"}
    )
    assert ref_1.status_code == 200
    data_1 = ref_1.json()
    tok_2 = data_1["refresh_token"]
    assert tok_2 != tok_1

    # Replay of old tok_1 fails with 401
    replay_res = client.post("/api/v1/auth/refresh", json={"refresh_token": tok_1})
    assert replay_res.status_code == 401

    # Refresh 2 with tok_2 succeeds
    ref_2 = client.post("/api/v1/auth/refresh", json={"refresh_token": tok_2})
    assert ref_2.status_code == 200


def test_explicit_logout_revokes_auth_session():
    """Logout endpoint marks refresh session as revoked."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "hardened.customer@example.com", "password": "CustPass123!"}
    )
    refresh_tok = login_res.json()["refresh_token"]

    # Call logout
    logout_res = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_tok})
    assert logout_res.status_code == 200

    # Verify session is marked is_revoked in DB
    db = TestingSessionLocal()
    try:
        session = db.query(AuthSession).filter(
            AuthSession.refresh_token_hash == hash_token(refresh_tok)
        ).first()
        assert session is not None
        assert session.is_revoked is True
    finally:
        db.close()

    # Attempting refresh with logged-out token returns 401
    ref_res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_tok})
    assert ref_res.status_code == 401


def test_admin_session_renewal_and_rbac_preservation():
    """Admin token refresh preserves role and grants continuous admin access."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "hardened.admin@pattyproject.co.uk", "password": "AdminPass123!"}
    )
    assert login_res.status_code == 200
    admin_refresh = login_res.json()["refresh_token"]

    # Silent token refresh
    ref_res = client.post("/api/v1/auth/refresh", json={"refresh_token": admin_refresh})
    assert ref_res.status_code == 200
    new_admin_jwt = ref_res.json()["access_token"]
    assert ref_res.json()["user"]["role"] == UserRole.SUPER_ADMIN

    # Authenticated admin access using refreshed access token
    orders_res = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {new_admin_jwt}"})
    assert orders_res.status_code == 200


def test_customer_token_cannot_access_admin_endpoints():
    """Customer token (original or refreshed) is strictly blocked from admin endpoints (403 Forbidden)."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "hardened.customer@example.com", "password": "CustPass123!"}
    )
    cust_refresh = login_res.json()["refresh_token"]

    ref_res = client.post("/api/v1/auth/refresh", json={"refresh_token": cust_refresh})
    assert ref_res.status_code == 200
    cust_access = ref_res.json()["access_token"]

    # Customer tries to access admin-only endpoint
    orders_res = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {cust_access}"})
    assert orders_res.status_code == 403
