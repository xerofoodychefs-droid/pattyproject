import os
import pytest
from datetime import datetime, timedelta, timezone
from app.main import app
from app.core.config import settings
from app.core.security import create_access_token, generate_refresh_token, hash_token, get_password_hash, verify_password
from app.models.user import User, UserRole, AuthSession
from app.tests.db import client, reset_test_db, TestingSessionLocal


@pytest.fixture(autouse=True)
def setup_phase2c_data():
    reset_test_db()
    db = TestingSessionLocal()

    # Create a test customer
    cust_user = User(
        id="usr-p2c-cust-01",
        email="p2c.customer@example.com",
        password_hash=get_password_hash("CustomerPass123!"),
        full_name="Phase 2C Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=True
    )
    db.add(cust_user)
    db.commit()
    db.close()


# =========================================================================
# 1. Login & Token Pair Issuance Tests
# =========================================================================

def test_login_issues_access_and_refresh_tokens():
    """Login returns both access_token and refresh_token and creates an active AuthSession."""
    resp = client.post("/api/v1/auth/login", json={
        "email": "p2c.customer@example.com",
        "password": "CustomerPass123!"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert len(data["refresh_token"]) > 20

    # Verify session persisted in DB
    db = TestingSessionLocal()
    try:
        token_hash = hash_token(data["refresh_token"])
        session = db.query(AuthSession).filter(AuthSession.refresh_token_hash == token_hash).first()
        assert session is not None
        assert session.user_id == "usr-p2c-cust-01"
        assert session.is_revoked is False
    finally:
        db.close()


def test_login_with_invalid_credentials_fails_401():
    """Invalid password returns 401 and creates no session."""
    resp = client.post("/api/v1/auth/login", json={
        "email": "p2c.customer@example.com",
        "password": "WrongPassword!"
    })
    assert resp.status_code == 401


def test_admin_credentials_continue_working():
    """Existing seeded superadmin user logs in cleanly and receives token pair."""
    resp = client.post("/api/v1/auth/login", json={
        "email": "admin@pattyproject.co.uk",
        "password": "Admin123!"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["role"] == UserRole.SUPER_ADMIN
    assert "access_token" in data
    assert "refresh_token" in data


# =========================================================================
# 2. Access Token Validation Tests
# =========================================================================

def test_valid_access_token_allows_protected_requests():
    """Valid access token accesses /api/v1/auth/me successfully."""
    login_res = client.post("/api/v1/auth/login", json={
        "email": "p2c.customer@example.com",
        "password": "CustomerPass123!"
    })
    token = login_res.json()["access_token"]

    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "p2c.customer@example.com"


def test_expired_access_token_rejected_401():
    """Expired access token is rejected by authentication with 401."""
    expired_token = create_access_token(
        subject="usr-p2c-cust-01",
        roles=[UserRole.CUSTOMER],
        expires_delta=timedelta(minutes=-5)
    )
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert me_res.status_code == 401


# =========================================================================
# 3. Session Renewal & Refresh Token Rotation Tests
# =========================================================================

def test_refresh_token_rotation_and_new_tokens():
    """Valid refresh token produces new access token and rotates refresh token."""
    login_res = client.post("/api/v1/auth/login", json={
        "email": "p2c.customer@example.com",
        "password": "CustomerPass123!"
    })
    initial_refresh = login_res.json()["refresh_token"]

    # Call /refresh
    refresh_res = client.post("/api/v1/auth/refresh", json={"refresh_token": initial_refresh})
    assert refresh_res.status_code == 200
    new_data = refresh_res.json()
    assert "access_token" in new_data
    assert "refresh_token" in new_data
    new_refresh = new_data["refresh_token"]
    assert new_refresh != initial_refresh  # Refresh Token was rotated!

    # Verify old refresh token can no longer be used (Replay Protection)
    replay_res = client.post("/api/v1/auth/refresh", json={"refresh_token": initial_refresh})
    assert replay_res.status_code == 401

    # Verify new refresh token works
    second_refresh = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert second_refresh.status_code == 200


def test_refresh_with_expired_refresh_token_fails_401():
    """Expired refresh token fails with 401."""
    db = TestingSessionLocal()
    token = generate_refresh_token()
    token_hash = hash_token(token)
    session = AuthSession(
        user_id="usr-p2c-cust-01",
        refresh_token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        is_revoked=False
    )
    db.add(session)
    db.commit()
    db.close()

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert resp.status_code == 401


def test_refresh_with_revoked_session_fails_401():
    """Revoked session fails with 401."""
    db = TestingSessionLocal()
    token = generate_refresh_token()
    token_hash = hash_token(token)
    session = AuthSession(
        user_id="usr-p2c-cust-01",
        refresh_token_hash=token_hash,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
        is_revoked=True  # Revoked!
    )
    db.add(session)
    db.commit()
    db.close()

    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": token})
    assert resp.status_code == 401


# =========================================================================
# 4. Explicit Logout & Session Invalidation Tests
# =========================================================================

def test_logout_revokes_refresh_session():
    """Explicit logout marks session as revoked, preventing subsequent refresh."""
    login_res = client.post("/api/v1/auth/login", json={
        "email": "p2c.customer@example.com",
        "password": "CustomerPass123!"
    })
    refresh_token = login_res.json()["refresh_token"]

    # Logout
    logout_res = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout_res.status_code == 200
    assert logout_res.json()["message"] == "Logged out successfully"

    # Verify refresh is rejected after logout
    refresh_res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_res.status_code == 401


# =========================================================================
# 5. Admin Continuous Use & Usability Tests
# =========================================================================

def test_admin_continuous_session_renewal_without_forced_logout():
    """Admin logs in, renews session via refresh token, and continues accessing admin endpoints seamlessly."""
    admin_login = client.post("/api/v1/auth/login", json={
        "email": "admin@pattyproject.co.uk",
        "password": "Admin123!"
    })
    assert admin_login.status_code == 200
    admin_data = admin_login.json()
    admin_refresh = admin_data["refresh_token"]

    # Admin accesses protected admin orders
    orders_res = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {admin_data['access_token']}"})
    assert orders_res.status_code == 200

    # Simulate access token expiration, silent renewal via refresh token
    renew_res = client.post("/api/v1/auth/refresh", json={"refresh_token": admin_refresh})
    assert renew_res.status_code == 200
    renewed_token = renew_res.json()["access_token"]

    # Admin continues working without manual re-login
    orders_res_2 = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {renewed_token}"})
    assert orders_res_2.status_code == 200


# =========================================================================
# 6. Password Change Session Invalidation Tests
# =========================================================================

def test_password_change_invalidates_prior_sessions():
    """Changing password revokes old active sessions; old password fails; new password succeeds."""
    login_res = client.post("/api/v1/auth/login", json={
        "email": "p2c.customer@example.com",
        "password": "CustomerPass123!"
    })
    old_access = login_res.json()["access_token"]
    old_refresh = login_res.json()["refresh_token"]

    # Change password
    change_res = client.post(
        "/api/v1/auth/change-password",
        headers={"Authorization": f"Bearer {old_access}"},
        json={
            "current_password": "CustomerPass123!",
            "new_password": "NewBrandSecurePass789!"
        }
    )
    assert change_res.status_code == 200

    # Prior refresh token is now revoked
    revoked_refresh_res = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert revoked_refresh_res.status_code == 401

    # Old password fails login
    old_login = client.post("/api/v1/auth/login", json={
        "email": "p2c.customer@example.com",
        "password": "CustomerPass123!"
    })
    assert old_login.status_code == 401

    # New password succeeds login
    new_login = client.post("/api/v1/auth/login", json={
        "email": "p2c.customer@example.com",
        "password": "NewBrandSecurePass789!"
    })
    assert new_login.status_code == 200
    assert "access_token" in new_login.json()
    assert "refresh_token" in new_login.json()
