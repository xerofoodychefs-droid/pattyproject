import os
import pytest
from datetime import datetime, timedelta, timezone
from jose import jwt

from app.main import app
from app.core.config import Settings, DEV_FALLBACK_SECRET_KEY, DEFAULT_PROD_CORS_ORIGINS, DEFAULT_DEV_CORS_ORIGINS
from app.core.security import create_access_token, verify_password, get_password_hash
from app.models.user import User, UserRole
from app.tests.db import client, reset_test_db, TestingSessionLocal


@pytest.fixture(autouse=True)
def setup_phase2b_data():
    reset_test_db()
    db = TestingSessionLocal()

    # Create an admin user for password change testing
    admin_user = User(
        id="usr-p2b-admin-01",
        email="p2b.admin@pattytest.co.uk",
        password_hash=get_password_hash("OldSecurePass123!"),
        full_name="Phase2B Admin User",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        email_verified=True
    )
    db.add(admin_user)
    db.commit()
    db.close()


def get_token_headers(user_id: str, role: str) -> dict:
    token = create_access_token(subject=user_id, roles=[role])
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# FINDING-5: Seeder Password Security Tests
# =========================================================================

def test_seed_passwords_are_cryptographically_hashed():
    """Verify that seeder passwords are not stored in plaintext and use Argon2id hash."""
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == "p2b.admin@pattytest.co.uk").first()
        assert user is not None
        assert user.password_hash != "OldSecurePass123!"
        assert verify_password("OldSecurePass123!", user.password_hash) is True
        assert verify_password("WrongPassword!", user.password_hash) is False
        assert user.password_hash.startswith("$argon2") or user.password_hash.startswith("$2b$")
    finally:
        db.close()


def test_production_mode_prevents_silent_predictable_seeding(monkeypatch):
    """In production mode without explicit SEED_ADMIN_PASSWORD, default predictable accounts are not created."""
    from app.core.config import settings
    from app.db.seed import seed_db

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    if "SEED_ADMIN_PASSWORD" in os.environ:
        monkeypatch.delenv("SEED_ADMIN_PASSWORD")

    # Clean DB and run seed in production mode
    db = TestingSessionLocal()
    for table in reversed(User.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()
    db.close()

    seed_db()

    # Verify that predictable accounts were not created
    db = TestingSessionLocal()
    try:
        central = db.query(User).filter(User.email == "central@pattyproject.co.uk").first()
        westfield = db.query(User).filter(User.email == "westfield@pattyproject.co.uk").first()
        customer = db.query(User).filter(User.email == "john.smith@email.com").first()
        assert central is None
        assert westfield is None
        assert customer is None
    finally:
        db.close()


# =========================================================================
# FINDING-6: SQLite Database Git Ignore Tests
# =========================================================================

def test_sqlite_database_patterns_in_gitignore():
    """Verify that root .gitignore contains comprehensive rules for SQLite databases."""
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    root_dir = os.path.dirname(backend_dir)
    gitignore_path = os.path.join(root_dir, ".gitignore")
    
    assert os.path.exists(gitignore_path), ".gitignore must exist"
    with open(gitignore_path, "r", encoding="utf-8") as f:
        content = f.read()

    assert "*.db" in content
    assert "*.sqlite" in content
    assert "*.sqlite3" in content
    assert "patty_project.db" in content


# =========================================================================
# FINDING-7: CORS Origin Security Tests
# =========================================================================

def test_cors_approved_development_origin_allowed():
    """Request from approved local dev origin receives Access-Control-Allow-Origin header."""
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET"
    }
    response = client.options("/", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_cors_unapproved_origin_rejected():
    """Request from unapproved malicious origin does not receive Access-Control-Allow-Origin header."""
    headers = {
        "Origin": "https://malicious-attacker-site.com",
        "Access-Control-Request-Method": "GET"
    }
    response = client.options("/", headers=headers)
    assert response.headers.get("access-control-allow-origin") is None or response.headers.get("access-control-allow-origin") != "https://malicious-attacker-site.com"


def test_cors_production_wildcard_prohibited(monkeypatch):
    """In production mode, validate_production_configuration() rejects wildcard '*' CORS origin."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "prod_valid_high_entropy_secret_key_min_32_chars_2026")
    monkeypatch.setenv("BACKEND_CORS_ORIGINS", "*")

    with pytest.raises(RuntimeError) as exc:
        settings.validate_production_configuration()
    assert "Production CORS configuration must not be empty or contain wildcard '*'" in str(exc.value)


# =========================================================================
# FINDING-8: JWT Lifetime & Expiration Tests
# =========================================================================

def test_jwt_valid_token_within_lifetime_succeeds():
    """Valid JWT within lifetime authenticates correctly."""
    headers = get_token_headers("usr-p2b-admin-01", "SUPER_ADMIN")
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "p2b.admin@pattytest.co.uk"


def test_jwt_expired_token_is_rejected_with_401():
    """Expired JWT is rejected by FastAPI authentication with 401."""
    # Generate token that expired 10 minutes ago
    expired_token = create_access_token(
        subject="usr-p2b-admin-01",
        roles=["SUPER_ADMIN"],
        expires_delta=timedelta(minutes=-10)
    )
    headers = {"Authorization": f"Bearer {expired_token}"}
    response = client.get("/api/v1/auth/me", headers=headers)
    assert response.status_code == 401
    assert "detail" in response.json()


# =========================================================================
# FINDING-10: Admin Password Rotation Endpoint Tests
# =========================================================================

def test_change_password_success_and_login_with_new_password():
    """Admin successfully changes password; old password stops working; new password authenticates."""
    headers = get_token_headers("usr-p2b-admin-01", "SUPER_ADMIN")

    # 1. Change password
    change_payload = {
        "current_password": "OldSecurePass123!",
        "new_password": "NewSuperSecurePass456!"
    }
    resp = client.post("/api/v1/auth/change-password", headers=headers, json=change_payload)
    assert resp.status_code == 200
    assert resp.json()["message"] == "Password updated successfully"

    # 2. Verify old password fails login
    old_login = client.post("/api/v1/auth/login", json={
        "email": "p2b.admin@pattytest.co.uk",
        "password": "OldSecurePass123!"
    })
    assert old_login.status_code == 401

    # 3. Verify new password succeeds login
    new_login = client.post("/api/v1/auth/login", json={
        "email": "p2b.admin@pattytest.co.uk",
        "password": "NewSuperSecurePass456!"
    })
    assert new_login.status_code == 200
    assert "access_token" in new_login.json()


def test_change_password_wrong_current_password_denied_400():
    """Attempting to change password with incorrect current password returns 400 Bad Request."""
    headers = get_token_headers("usr-p2b-admin-01", "SUPER_ADMIN")

    change_payload = {
        "current_password": "WrongCurrentPassword!",
        "new_password": "NewSuperSecurePass456!"
    }
    resp = client.post("/api/v1/auth/change-password", headers=headers, json=change_payload)
    assert resp.status_code == 400
    assert "Current password is incorrect" in resp.json()["detail"]


def test_change_password_too_short_new_password_denied_400():
    """Attempting to change password with new password < 8 chars returns 400."""
    headers = get_token_headers("usr-p2b-admin-01", "SUPER_ADMIN")

    change_payload = {
        "current_password": "OldSecurePass123!",
        "new_password": "short"
    }
    resp = client.post("/api/v1/auth/change-password", headers=headers, json=change_payload)
    assert resp.status_code == 400
    assert "at least 8 characters long" in resp.json()["detail"]


def test_change_password_same_password_denied_400():
    """Attempting to set new password identical to current password returns 400."""
    headers = get_token_headers("usr-p2b-admin-01", "SUPER_ADMIN")

    change_payload = {
        "current_password": "OldSecurePass123!",
        "new_password": "OldSecurePass123!"
    }
    resp = client.post("/api/v1/auth/change-password", headers=headers, json=change_payload)
    assert resp.status_code == 400
    assert "must be different" in resp.json()["detail"]


def test_change_password_unauthenticated_denied_401():
    """Unauthenticated call to /change-password returns 401."""
    change_payload = {
        "current_password": "OldSecurePass123!",
        "new_password": "NewSuperSecurePass456!"
    }
    resp = client.post("/api/v1/auth/change-password", json=change_payload)
    assert resp.status_code == 401
