import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.user import User, UserRole
from app.models.verification import EmailVerificationChallenge
from app.models.loyalty import LoyaltyAccount
from app.tests.db import TestingSessionLocal, override_get_db, reset_test_db
from app.services.otp_service import (
    generate_secure_otp, hash_otp, verify_otp_hash,
    create_verification_challenge, OTP_MAX_ATTEMPTS, RESEND_COOLDOWN_SECONDS
)

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Reset and seed the in-memory test database before each test."""
    reset_test_db()


# ============================================================================
# 1. REGISTRATION & OTP DISPATCH (NO USER IN DB UNTIL VERIFIED)
# ============================================================================

def test_01_registration_does_not_create_user_and_dispatches_otp():
    """Requirement 1 & 2: Registration request does NOT create a User in DB, but creates challenge & dispatches OTP."""
    with patch("app.api.endpoints.auth.send_verification_otp_email", return_value=True) as mock_send:
        reg_payload = {
            "full_name": "Oliver Twist",
            "email": "oliver@example.com",
            "phone": "+44 7111 222333",
            "password": "SecurePassword123!"
        }
        res = client.post("/api/v1/auth/register", json=reg_payload)
        assert res.status_code == 200, res.text
        data = res.json()

        assert data["requires_verification"] is True
        assert data["email"] == "oliver@example.com"
        assert "access_token" not in data  # Tokens must NOT be issued prior to verification
        assert "otp" not in data           # OTP must NEVER be leaked to the client

        # Verify DB state: User MUST NOT exist yet!
        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(User.email == "oliver@example.com").first()
            assert user is None  # Must NOT create user yet!

            loyalty = db.query(LoyaltyAccount).all()
            assert not any(l.user_id == "oliver@example.com" for l in loyalty)

            challenge = db.query(EmailVerificationChallenge).filter(EmailVerificationChallenge.email == "oliver@example.com").first()
            assert challenge is not None
            assert challenge.full_name == "Oliver Twist"
            assert challenge.password_hash is not None
            assert challenge.password_hash != "SecurePassword123!"  # Securely hashed, never plaintext
            assert challenge.phone == "+44 7111 222333"
            assert challenge.used_at is None
            assert challenge.attempt_count == 0
            assert mock_send.called
        finally:
            db.close()


def test_02_otp_email_sent_with_correct_payload_and_branding():
    """Scenario 2: Verify email service builds correct Resend payload and headers."""
    from app.services.email_service import send_verification_otp_email, build_verification_otp_html, build_verification_otp_text

    html_content = build_verification_otp_html("654321")
    text_content = build_verification_otp_text("654321")

    assert "654321" in html_content
    assert "654321" in text_content
    assert "PATTY PROJECT UK" in html_content
    assert "10 minutes" in html_content

    # Verify mock HTTP client transmission
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_client.post.return_value = mock_resp

    with patch("app.core.config.settings.RESEND_API_KEY", "re_test_key_123"):
        success = send_verification_otp_email("test@example.com", "654321", client=mock_client)
        assert success is True
        assert mock_client.post.called
        call_kwargs = mock_client.post.call_args[1]
        assert call_kwargs["json"]["to"] == ["test@example.com"]
        assert call_kwargs["json"]["subject"] == "Verify your Patty Project account"


# ============================================================================
# 2. VERIFICATION & ACCOUNT CREATION
# ============================================================================

def test_03_valid_otp_creates_exactly_one_customer_and_awards_welcome_points():
    """Requirement 3 & 10: Valid OTP creates exactly one CUSTOMER, awards 100 welcome points, and returns tokens."""
    with patch("app.api.endpoints.auth.send_verification_otp_email", return_value=True):
        reg_payload = {
            "full_name": "Verify Me",
            "email": "verify.me@example.com",
            "phone": "+44 7555 123456",
            "password": "SecurePassword123!"
        }
        res_reg = client.post("/api/v1/auth/register", json=reg_payload)
        assert res_reg.status_code == 200

    # Retrieve challenge OTP
    db = TestingSessionLocal()
    try:
        challenge = db.query(EmailVerificationChallenge).filter(EmailVerificationChallenge.email == "verify.me@example.com").first()
        assert challenge is not None
        otp_test = "654321"
        challenge.otp_hash = hash_otp(email="verify.me@example.com", otp=otp_test, salt=challenge.salt)
        db.commit()
    finally:
        db.close()

    verify_payload = {
        "email": "verify.me@example.com",
        "otp": otp_test
    }
    res = client.post("/api/v1/auth/verify-email", json=verify_payload)
    assert res.status_code == 200, res.text
    data = res.json()

    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == "verify.me@example.com"
    assert data["user"]["full_name"] == "Verify Me"
    assert data["user"]["role"] == UserRole.CUSTOMER
    assert data["user"]["email_verified"] is True

    # Check DB state: Exactly one User and one LoyaltyAccount created
    db = TestingSessionLocal()
    try:
        users = db.query(User).filter(User.email == "verify.me@example.com").all()
        assert len(users) == 1
        user_db = users[0]
        assert user_db.role == UserRole.CUSTOMER
        assert user_db.email_verified is True
        assert user_db.is_active is True

        loyalty = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == user_db.id).all()
        assert len(loyalty) == 1
        assert loyalty[0].available_points == 100
        assert loyalty[0].lifetime_points == 100
    finally:
        db.close()


def test_04_invalid_otp_does_not_create_customer():
    """Requirement 4: Invalid OTP does not create a customer and increments attempts."""
    with patch("app.api.endpoints.auth.send_verification_otp_email", return_value=True):
        reg_payload = {
            "full_name": "Invalid OTP User",
            "email": "invalid.otp@example.com",
            "password": "SecurePassword123!"
        }
        client.post("/api/v1/auth/register", json=reg_payload)

    wrong_otp = "000000"
    res = client.post("/api/v1/auth/verify-email", json={"email": "invalid.otp@example.com", "otp": wrong_otp})
    assert res.status_code == 400
    assert "Invalid verification code" in res.json()["detail"]

    # Verify no customer was created
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == "invalid.otp@example.com").first()
        assert user is None

        ch = db.query(EmailVerificationChallenge).filter(EmailVerificationChallenge.email == "invalid.otp@example.com").first()
        assert ch.attempt_count == 1
        assert ch.used_at is None
    finally:
        db.close()


def test_05_expired_otp_does_not_create_customer():
    """Requirement 5: Expired OTP is rejected and does not create a customer."""
    with patch("app.api.endpoints.auth.send_verification_otp_email", return_value=True):
        client.post("/api/v1/auth/register", json={
            "full_name": "Expired User",
            "email": "expired@example.com",
            "password": "SecurePassword123!"
        })

    db = TestingSessionLocal()
    try:
        challenge = db.query(EmailVerificationChallenge).filter(EmailVerificationChallenge.email == "expired@example.com").first()
        otp_test = "123456"
        challenge.otp_hash = hash_otp(email="expired@example.com", otp=otp_test, salt=challenge.salt)
        # Manually backdate expiration
        challenge.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    res = client.post("/api/v1/auth/verify-email", json={"email": "expired@example.com", "otp": otp_test})
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()

    # User MUST NOT exist
    db = TestingSessionLocal()
    try:
        assert db.query(User).filter(User.email == "expired@example.com").first() is None
    finally:
        db.close()


def test_06_otp_cannot_be_reused():
    """Requirement 6: Already-used OTP cannot be replayed/reused."""
    with patch("app.api.endpoints.auth.send_verification_otp_email", return_value=True):
        client.post("/api/v1/auth/register", json={
            "full_name": "Replay User",
            "email": "replay@example.com",
            "password": "SecurePassword123!"
        })

    otp_test = "123456"
    db = TestingSessionLocal()
    try:
        ch = db.query(EmailVerificationChallenge).filter(EmailVerificationChallenge.email == "replay@example.com").first()
        ch.otp_hash = hash_otp(email="replay@example.com", otp=otp_test, salt=ch.salt)
        db.commit()
    finally:
        db.close()

    # First attempt: succeeds
    res1 = client.post("/api/v1/auth/verify-email", json={"email": "replay@example.com", "otp": otp_test})
    assert res1.status_code == 200

    # Second attempt with same OTP: fails
    res2 = client.post("/api/v1/auth/verify-email", json={"email": "replay@example.com", "otp": otp_test})
    assert res2.status_code == 400
    assert "no active verification code" in res2.json()["detail"].lower()


def test_07_too_many_incorrect_otp_attempts_blocked():
    """Requirement 7: 5 failed attempts locks challenge and rejects verification."""
    with patch("app.api.endpoints.auth.send_verification_otp_email", return_value=True):
        client.post("/api/v1/auth/register", json={
            "full_name": "Max Attempts",
            "email": "maxattempts@example.com",
            "password": "SecurePassword123!"
        })

    db = TestingSessionLocal()
    try:
        challenge = db.query(EmailVerificationChallenge).filter(EmailVerificationChallenge.email == "maxattempts@example.com").first()
        challenge.attempt_count = 5  # Reached max
        db.commit()
    finally:
        db.close()

    res = client.post("/api/v1/auth/verify-email", json={"email": "maxattempts@example.com", "otp": "123456"})
    assert res.status_code == 400
    assert "exceeded" in res.json()["detail"].lower()


def test_08_resend_rate_limited():
    """Requirement 8: Resend verification code is rate-limited by 60s cooldown."""
    with patch("app.api.endpoints.auth.send_verification_otp_email", return_value=True):
        client.post("/api/v1/auth/register", json={
            "full_name": "Cooldown User",
            "email": "cooldown@example.com",
            "password": "SecurePassword123!"
        })

    # Immediate resend should be blocked by 429
    res = client.post("/api/v1/auth/resend-verification", json={"email": "cooldown@example.com"})
    assert res.status_code == 429
    assert "Please wait" in res.json()["detail"]


def test_09_registration_cannot_specify_admin_roles():
    """Requirement 9: New public registration request cannot create SUPER_ADMIN or BRANCH_ADMIN."""
    with patch("app.api.endpoints.auth.send_verification_otp_email", return_value=True):
        client.post("/api/v1/auth/register", json={
            "full_name": "Hacker",
            "email": "hacker@example.com",
            "password": "SecurePassword123!",
            "role": "SUPER_ADMIN"  # Attempt to inject admin role
        })

    otp_test = "777777"
    db = TestingSessionLocal()
    try:
        ch = db.query(EmailVerificationChallenge).filter(EmailVerificationChallenge.email == "hacker@example.com").first()
        ch.otp_hash = hash_otp(email="hacker@example.com", otp=otp_test, salt=ch.salt)
        db.commit()
    finally:
        db.close()

    res = client.post("/api/v1/auth/verify-email", json={"email": "hacker@example.com", "otp": otp_test})
    assert res.status_code == 200
    data = res.json()
    assert data["user"]["role"] == UserRole.CUSTOMER  # Strictly created as CUSTOMER!

    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == "hacker@example.com").first()
        assert user.role == UserRole.CUSTOMER
    finally:
        db.close()


def test_10_unverified_registration_never_appears_in_admin_customers():
    """Requirement 12 & 13: Unverified registration never appears in Admin Customers list; verified appears."""
    from app.core.security import create_access_token
    admin_token = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])

    with patch("app.api.endpoints.auth.send_verification_otp_email", return_value=True):
        client.post("/api/v1/auth/register", json={
            "full_name": "Pending Customer",
            "email": "pending.customer@example.com",
            "password": "SecurePassword123!"
        })

    # Admin checks customer list: MUST NOT appear
    list_resp = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {admin_token}"})
    assert list_resp.status_code == 200
    assert not any(c["email"] == "pending.customer@example.com" for c in list_resp.json())

    # Now verify
    otp_test = "112233"
    db = TestingSessionLocal()
    try:
        ch = db.query(EmailVerificationChallenge).filter(EmailVerificationChallenge.email == "pending.customer@example.com").first()
        ch.otp_hash = hash_otp(email="pending.customer@example.com", otp=otp_test, salt=ch.salt)
        db.commit()
    finally:
        db.close()

    verify_resp = client.post("/api/v1/auth/verify-email", json={"email": "pending.customer@example.com", "otp": otp_test})
    assert verify_resp.status_code == 200

    # Admin checks customer list: MUST appear now
    list_resp_after = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {admin_token}"})
    assert list_resp_after.status_code == 200
    cust = next((c for c in list_resp_after.json() if c["email"] == "pending.customer@example.com"), None)
    assert cust is not None
    assert cust["name"] == "Pending Customer"
    assert cust["points"] == 100


def test_11_existing_verified_customer_accounts_remain_unchanged():
    """Requirement 11: Existing verified customer accounts log in normally without re-verification."""
    db = TestingSessionLocal()
    try:
        user = User(
            id="existing-cust-99",
            email="existing.verified@example.com",
            full_name="Existing Verified",
            password_hash=get_password_hash("Password123!"),
            role=UserRole.CUSTOMER,
            is_active=True,
            email_verified=True
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    res = client.post("/api/v1/auth/login", json={
        "email": "existing.verified@example.com",
        "password": "Password123!"
    })
    assert res.status_code == 200
    assert "access_token" in res.json()
    assert res.json()["user"]["email_verified"] is True
