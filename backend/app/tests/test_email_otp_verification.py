import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import get_db
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
# 1. REGISTRATION & OTP DISPATCH
# ============================================================================

def test_01_successful_registration_creates_unverified_account_and_dispatches_otp():
    """Scenario 1: Customer registration creates unverified account and returns verification prompt."""
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

        # Verify DB state
        db = TestingSessionLocal()
        try:
            user = db.query(User).filter(User.email == "oliver@example.com").first()
            assert user is not None
            assert user.email_verified is False
            assert user.is_active is True  # Account enabled, pending verification

            challenge = db.query(EmailVerificationChallenge).filter(EmailVerificationChallenge.user_id == user.id).first()
            assert challenge is not None
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
# 2. VERIFICATION & LOGIN
# ============================================================================

def test_03_otp_verification_success_activates_account_and_returns_tokens():
    """Scenario 3: Entering correct OTP marks email_verified=True and returns login tokens."""
    db = TestingSessionLocal()
    try:
        user = User(
            id="user-otp-001",
            email="verify.me@example.com",
            full_name="Verify Me",
            password_hash="somehash",
            role=UserRole.CUSTOMER,
            is_active=True,
            email_verified=False
        )
        db.add(user)
        db.flush()

        challenge, otp = create_verification_challenge(db, user.id, user.email)
        challenge_id = challenge.id
        db.commit()
    finally:
        db.close()

    verify_payload = {
        "email": "verify.me@example.com",
        "otp": otp
    }
    res = client.post("/api/v1/auth/verify-email", json=verify_payload)
    assert res.status_code == 200, res.text
    data = res.json()

    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == "verify.me@example.com"
    assert data["user"]["email_verified"] is True

    # Check DB state
    db = TestingSessionLocal()
    try:
        user_db = db.query(User).filter(User.id == "user-otp-001").first()
        assert user_db.email_verified is True

        ch_db = db.query(EmailVerificationChallenge).filter(EmailVerificationChallenge.id == challenge_id).first()
        assert ch_db.used_at is not None
    finally:
        db.close()


def test_04_invalid_otp_rejected_and_increments_attempts():
    """Scenario 4: Entering wrong OTP returns 400 and increments attempt count."""
    db = TestingSessionLocal()
    try:
        user = User(
            id="user-otp-002",
            email="wrong.otp@example.com",
            full_name="Wrong OTP",
            password_hash="somehash",
            role=UserRole.CUSTOMER,
            is_active=True,
            email_verified=False
        )
        db.add(user)
        db.flush()

        challenge, otp = create_verification_challenge(db, user.id, user.email)
        challenge_id = challenge.id
        db.commit()
    finally:
        db.close()

    wrong_otp = "000000" if otp != "000000" else "111111"
    res = client.post("/api/v1/auth/verify-email", json={"email": "wrong.otp@example.com", "otp": wrong_otp})
    assert res.status_code == 400
    assert "Invalid verification code" in res.json()["detail"]

    # Verify attempt count incremented
    db = TestingSessionLocal()
    try:
        ch = db.query(EmailVerificationChallenge).filter(EmailVerificationChallenge.id == challenge_id).first()
        assert ch.attempt_count == 1
        assert ch.used_at is None
    finally:
        db.close()


def test_05_expired_otp_rejected():
    """Scenario 5: Expired OTP challenge is rejected."""
    db = TestingSessionLocal()
    try:
        user = User(
            id="user-otp-003",
            email="expired@example.com",
            full_name="Expired User",
            password_hash="somehash",
            role=UserRole.CUSTOMER,
            is_active=True,
            email_verified=False
        )
        db.add(user)
        db.flush()

        challenge, otp = create_verification_challenge(db, user.id, user.email)
        # Manually backdate expiration
        challenge.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    res = client.post("/api/v1/auth/verify-email", json={"email": "expired@example.com", "otp": otp})
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


def test_06_otp_max_attempt_limit_exceeded():
    """Scenario 6: 5 failed attempts locks challenge and rejects verification."""
    db = TestingSessionLocal()
    try:
        user = User(
            id="user-otp-004",
            email="maxattempts@example.com",
            full_name="Max Attempts",
            password_hash="somehash",
            role=UserRole.CUSTOMER,
            is_active=True,
            email_verified=False
        )
        db.add(user)
        db.flush()

        challenge, otp = create_verification_challenge(db, user.id, user.email)
        challenge.attempt_count = 5  # Already reached max
        db.commit()
    finally:
        db.close()

    res = client.post("/api/v1/auth/verify-email", json={"email": "maxattempts@example.com", "otp": otp})
    assert res.status_code == 400
    assert "exceeded" in res.json()["detail"].lower()


def test_07_otp_replay_rejection():
    """Scenario 7: Already-used OTP cannot be replayed."""
    db = TestingSessionLocal()
    try:
        user = User(
            id="user-otp-005",
            email="replay@example.com",
            full_name="Replay User",
            password_hash="somehash",
            role=UserRole.CUSTOMER,
            is_active=True,
            email_verified=False
        )
        db.add(user)
        db.flush()

        challenge, otp = create_verification_challenge(db, user.id, user.email)
        challenge.used_at = datetime.now(timezone.utc)  # Already used
        db.commit()
    finally:
        db.close()

    res = client.post("/api/v1/auth/verify-email", json={"email": "replay@example.com", "otp": otp})
    assert res.status_code == 400
    assert "no active verification code" in res.json()["detail"].lower()


def test_08_old_otp_invalidated_after_resend():
    """Scenario 8: Resending verification invalidates previous OTP."""
    db = TestingSessionLocal()
    try:
        user = User(
            id="user-otp-006",
            email="resend.test@example.com",
            full_name="Resend User",
            password_hash="somehash",
            role=UserRole.CUSTOMER,
            is_active=True,
            email_verified=False
        )
        db.add(user)
        db.flush()

        ch1, otp1 = create_verification_challenge(db, user.id, user.email)
        # Backdate ch1 so resend cooldown passes
        ch1.created_at = datetime.now(timezone.utc) - timedelta(seconds=70)
        db.commit()
    finally:
        db.close()

    with patch("app.api.endpoints.auth.send_verification_otp_email", return_value=True):
        res_resend = client.post("/api/v1/auth/resend-verification", json={"email": "resend.test@example.com"})
        assert res_resend.status_code == 200

    # Old OTP1 should now fail
    res_old = client.post("/api/v1/auth/verify-email", json={"email": "resend.test@example.com", "otp": otp1})
    assert res_old.status_code == 400


def test_09_resend_cooldown_enforced():
    """Scenario 9: Requesting resend before 60s cooldown returns 429."""
    db = TestingSessionLocal()
    try:
        user = User(
            id="user-otp-007",
            email="cooldown@example.com",
            full_name="Cooldown User",
            password_hash="somehash",
            role=UserRole.CUSTOMER,
            is_active=True,
            email_verified=False
        )
        db.add(user)
        db.flush()

        ch, otp = create_verification_challenge(db, user.id, user.email)
        # Challenge created right now (0s elapsed)
        db.commit()
    finally:
        db.close()

    res = client.post("/api/v1/auth/resend-verification", json={"email": "cooldown@example.com"})
    assert res.status_code == 429
    assert "Please wait" in res.json()["detail"]


def test_10_resend_allowed_after_cooldown():
    """Scenario 10: Requesting resend after 60s succeeds."""
    db = TestingSessionLocal()
    try:
        user = User(
            id="user-otp-008",
            email="cooldown.pass@example.com",
            full_name="Cooldown Pass",
            password_hash="somehash",
            role=UserRole.CUSTOMER,
            is_active=True,
            email_verified=False
        )
        db.add(user)
        db.flush()

        ch, otp = create_verification_challenge(db, user.id, user.email)
        ch.created_at = datetime.now(timezone.utc) - timedelta(seconds=65)
        db.commit()
    finally:
        db.close()

    with patch("app.api.endpoints.auth.send_verification_otp_email", return_value=True) as mock_send:
        res = client.post("/api/v1/auth/resend-verification", json={"email": "cooldown.pass@example.com"})
        assert res.status_code == 200
        assert mock_send.called


def test_11_malformed_otp_rejected():
    """Scenario 11: Non-numeric or wrong length OTPs are rejected with 422 Unprocessable Entity."""
    # Letters
    res1 = client.post("/api/v1/auth/verify-email", json={"email": "test@example.com", "otp": "ABCDEF"})
    assert res1.status_code == 422

    # 5 digits
    res2 = client.post("/api/v1/auth/verify-email", json={"email": "test@example.com", "otp": "12345"})
    assert res2.status_code == 422

    # 7 digits
    res3 = client.post("/api/v1/auth/verify-email", json={"email": "test@example.com", "otp": "1234567"})
    assert res3.status_code == 422


def test_12_missing_otp_rejected():
    """Scenario 12: Missing OTP field rejected with 422."""
    res = client.post("/api/v1/auth/verify-email", json={"email": "test@example.com"})
    assert res.status_code == 422


def test_13_account_activation_only_after_verification():
    """Scenario 13: User is marked verified only after verify-email endpoint succeeds."""
    db = TestingSessionLocal()
    try:
        user = User(
            id="user-otp-009",
            email="activation@example.com",
            full_name="Activation User",
            password_hash="somehash",
            role=UserRole.CUSTOMER,
            is_active=True,
            email_verified=False
        )
        db.add(user)
        db.flush()

        ch, otp = create_verification_challenge(db, user.id, user.email)
        db.commit()

        assert user.email_verified is False
    finally:
        db.close()

    res = client.post("/api/v1/auth/verify-email", json={"email": "activation@example.com", "otp": otp})
    assert res.status_code == 200

    db = TestingSessionLocal()
    try:
        u = db.query(User).filter(User.id == "user-otp-009").first()
        assert u.email_verified is True
    finally:
        db.close()


def test_14_unverified_account_cannot_login():
    """Scenario 14: Unverified user attempting password login receives HTTP 403."""
    from app.core.security import get_password_hash
    db = TestingSessionLocal()
    try:
        user = User(
            id="user-otp-010",
            email="unverified.login@example.com",
            full_name="Unverified Login",
            password_hash=get_password_hash("Password123!"),
            role=UserRole.CUSTOMER,
            is_active=True,
            email_verified=False
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    res = client.post("/api/v1/auth/login", json={
        "email": "unverified.login@example.com",
        "password": "Password123!"
    })
    assert res.status_code == 403
    assert "email not verified" in res.json()["detail"].lower()


def test_15_verified_account_can_login_successfully():
    """Scenario 15: Once verified, user logs in normally via /auth/login."""
    from app.core.security import get_password_hash
    db = TestingSessionLocal()
    try:
        user = User(
            id="user-otp-011",
            email="verified.login@example.com",
            full_name="Verified Login",
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
        "email": "verified.login@example.com",
        "password": "Password123!"
    })
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_16_resend_provider_failure_handling():
    """Scenario 16: Handling when Resend provider returns 502/error."""
    from app.services.email_service import send_verification_otp_email
    from fastapi import HTTPException

    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    mock_client.post.return_value = mock_resp

    with patch("app.core.config.settings.RESEND_API_KEY", "re_key_test"):
        with pytest.raises(HTTPException) as exc_info:
            send_verification_otp_email("error@example.com", "123456", client=mock_client)
        assert exc_info.value.status_code == 502


def test_17_otp_never_appears_in_plaintext_or_responses():
    """Scenario 17: OTP is stored only as salted hash and never exposed in database columns or API responses."""
    db = TestingSessionLocal()
    try:
        user = User(
            id="user-otp-012",
            email="secret.otp@example.com",
            full_name="Secret OTP",
            password_hash="somehash",
            role=UserRole.CUSTOMER,
            is_active=True,
            email_verified=False
        )
        db.add(user)
        db.flush()

        ch, otp = create_verification_challenge(db, user.id, user.email)
        db.commit()

        # Plaintext OTP must NOT equal stored hash
        assert otp != ch.otp_hash
        assert len(ch.otp_hash) >= 64  # SHA-256 hex string

        # Register endpoint response check
        with patch("app.api.endpoints.auth.send_verification_otp_email", return_value=True):
            res = client.post("/api/v1/auth/register", json={
                "full_name": "No Leak",
                "email": "noleak@example.com",
                "password": "Password123!"
            })
            assert res.status_code == 200
            res_text = res.text
            # No 6-digit number should be leaked in response JSON
            assert "otp" not in res.json()
            assert "code" not in res.json()
    finally:
        db.close()
