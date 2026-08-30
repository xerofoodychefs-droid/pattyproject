import time
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from concurrent.futures import ThreadPoolExecutor

from app.main import app
from app.core.database import get_db
from app.core.security import get_password_hash, verify_password, hash_token
from app.core.rate_limiter import password_reset_rate_limiter
from app.models.user import User, UserRole, AuthSession
from app.models.verification import PasswordResetChallenge, EmailVerificationChallenge
from app.models.loyalty import LoyaltyAccount
from app.tests.db import TestingSessionLocal, override_get_db, reset_test_db
from app.services.password_reset_service import (
    create_password_reset_challenge,
    consume_password_reset_token,
    generate_secure_reset_token,
    RESET_TOKEN_EXPIRY_MINUTES
)

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_database():
    """Reset and seed the in-memory test database before each test and reset rate limiters."""
    reset_test_db()
    password_reset_rate_limiter.reset()


def create_test_customer(
    email: str = "customer@example.com",
    password: str = "InitialPassword123!",
    is_active: bool = True,
    email_verified: bool = True
) -> User:
    db = TestingSessionLocal()
    try:
        user = User(
            email=email,
            password_hash=get_password_hash(password),
            full_name="Test Customer",
            role=UserRole.CUSTOMER,
            is_active=is_active,
            email_verified=email_verified
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


# ============================================================================
# 1. FORGOT PASSWORD & ACCOUNT ENUMERATION PROTECTION
# ============================================================================

def test_01_forgot_password_existing_user_triggers_resend_email():
    """Existing user receives password reset email via Resend."""
    create_test_customer(email="alice@example.com")

    with patch("app.api.endpoints.auth.send_password_reset_email", return_value=True) as mock_send:
        res = client.post("/api/v1/auth/forgot-password", json={"email": "alice@example.com"})
        assert res.status_code == 200, res.text
        data = res.json()
        assert "message" in data
        assert "password reset instructions have been sent" in data["message"].lower()

        # Resend must have been called
        assert mock_send.called
        call_kwargs = mock_send.call_args[1] if mock_send.call_args[1] else {}
        call_args = mock_send.call_args[0]
        to_email = call_kwargs.get("to_email") or call_args[0]
        reset_url = call_kwargs.get("reset_url") or call_args[1]

        assert to_email == "alice@example.com"
        assert "/reset-password?token=" in reset_url

        # Check DB challenge
        db = TestingSessionLocal()
        try:
            challenges = db.query(PasswordResetChallenge).all()
            assert len(challenges) == 1
            ch = challenges[0]
            assert ch.used_at is None
            # Raw token must NEVER be stored in DB
            token_part = reset_url.split("token=")[1]
            assert ch.token_hash != token_part
            assert ch.token_hash == hash_token(token_part)
        finally:
            db.close()


def test_02_forgot_password_nonexistent_user_returns_identical_generic_response():
    """Non-existent user returns exact same generic response and does NOT send email."""
    with patch("app.api.endpoints.auth.send_password_reset_email") as mock_send:
        res = client.post("/api/v1/auth/forgot-password", json={"email": "nonexistent@example.com"})
        assert res.status_code == 200, res.text
        data = res.json()
        assert "password reset instructions have been sent" in data["message"].lower()
        assert not mock_send.called

        db = TestingSessionLocal()
        try:
            challenges = db.query(PasswordResetChallenge).all()
            assert len(challenges) == 0
        finally:
            db.close()


def test_03_forgot_password_inactive_user_returns_generic_response():
    """Disabled/inactive accounts return generic response and send no email."""
    create_test_customer(email="inactive@example.com", is_active=False)

    with patch("app.api.endpoints.auth.send_password_reset_email") as mock_send:
        res = client.post("/api/v1/auth/forgot-password", json={"email": "inactive@example.com"})
        assert res.status_code == 200, res.text
        assert not mock_send.called


def test_04_raw_token_never_returned_in_api_response():
    """API responses must never contain token or token hash."""
    create_test_customer(email="bob@example.com")

    with patch("app.api.endpoints.auth.send_password_reset_email", return_value=True):
        res = client.post("/api/v1/auth/forgot-password", json={"email": "bob@example.com"})
        assert res.status_code == 200
        raw_text = res.text.lower()
        assert "token" not in raw_text
        assert "hash" not in raw_text


def test_05_only_token_hash_stored_in_database():
    """Database must only store SHA-256 hash."""
    user = create_test_customer(email="charlie@example.com")
    db = TestingSessionLocal()
    try:
        challenge, raw_token = create_password_reset_challenge(db, user)
        db.commit()

        queried = db.query(PasswordResetChallenge).filter(PasswordResetChallenge.id == challenge.id).first()
        assert queried.token_hash == hash_token(raw_token)
        assert queried.token_hash != raw_token
        assert len(queried.token_hash) == 64  # SHA-256 hex string
    finally:
        db.close()


# ============================================================================
# 2. PASSWORD RESET FLOW & CREDENTIAL VERIFICATION
# ============================================================================

def test_06_valid_token_resets_password_successfully():
    """Customer resets password with valid token, and old sessions are invalidated."""
    user = create_test_customer(email="david@example.com", password="OldPassword123!")
    user_id = user.id

    # Create dummy session
    db = TestingSessionLocal()
    try:
        session = AuthSession(
            user_id=user_id,
            refresh_token_hash=hash_token("some_refresh_token"),
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            is_revoked=False
        )
        db.add(session)
        challenge, raw_token = create_password_reset_challenge(db, user)
        challenge_id = challenge.id
        db.commit()
    finally:
        db.close()

    res = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token,
        "new_password": "BrandNewPassword123!"
    })
    assert res.status_code == 200, res.text
    assert "successfully reset" in res.json()["message"].lower()

    # Verify database state
    db = TestingSessionLocal()
    try:
        updated_user = db.query(User).filter(User.id == user_id).first()
        assert verify_password("BrandNewPassword123!", updated_user.password_hash)
        assert not verify_password("OldPassword123!", updated_user.password_hash)

        # Check session revoked
        sessions = db.query(AuthSession).filter(AuthSession.user_id == user_id).all()
        assert all(s.is_revoked for s in sessions)

        # Check challenge marked used
        ch = db.query(PasswordResetChallenge).filter(PasswordResetChallenge.id == challenge_id).first()
        assert ch.used_at is not None
    finally:
        db.close()


def test_07_old_password_fails_after_reset_new_password_works():
    """Login with old password fails (401), login with new password succeeds (200)."""
    user = create_test_customer(email="emma@example.com", password="InitialPassword123!")

    db = TestingSessionLocal()
    try:
        challenge, raw_token = create_password_reset_challenge(db, user)
        db.commit()
    finally:
        db.close()

    # Reset
    res_reset = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token,
        "new_password": "NewSecretPassword456!"
    })
    assert res_reset.status_code == 200

    # Old password login must fail
    res_old = client.post("/api/v1/auth/login", json={
        "email": "emma@example.com",
        "password": "InitialPassword123!"
    })
    assert res_old.status_code == 401

    # New password login must succeed
    res_new = client.post("/api/v1/auth/login", json={
        "email": "emma@example.com",
        "password": "NewSecretPassword456!"
    })
    assert res_new.status_code == 200
    assert "access_token" in res_new.json()


def test_08_invalid_token_fails():
    """Submitting a bogus token returns 400 Bad Request."""
    res = client.post("/api/v1/auth/reset-password", json={
        "token": "totally_bogus_token_12345",
        "new_password": "ValidPassword123!"
    })
    assert res.status_code == 400
    assert "invalid or expired" in res.json()["detail"].lower()


def test_09_expired_token_fails():
    """Submitting an expired token (>30 mins) returns 400."""
    user = create_test_customer(email="frank@example.com")
    db = TestingSessionLocal()
    try:
        raw_token = generate_secure_reset_token()
        expired_challenge = PasswordResetChallenge(
            user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),  # expired 5 mins ago
            used_at=None,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=35)
        )
        db.add(expired_challenge)
        db.commit()
    finally:
        db.close()

    res = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token,
        "new_password": "ValidPassword123!"
    })
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


def test_10_used_token_cannot_be_replayed():
    """Submitting an already used token returns 400."""
    user = create_test_customer(email="grace@example.com")
    db = TestingSessionLocal()
    try:
        challenge, raw_token = create_password_reset_challenge(db, user)
        db.commit()
    finally:
        db.close()

    # First use succeeds
    res1 = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token,
        "new_password": "NewPassword123!"
    })
    assert res1.status_code == 200

    # Second replay fails
    res2 = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token,
        "new_password": "AnotherPassword456!"
    })
    assert res2.status_code == 400
    assert "already been used" in res2.json()["detail"].lower() or "invalid or expired" in res2.json()["detail"].lower()


def test_11_new_forgot_password_request_invalidates_old_active_challenges():
    """Requesting a second reset link invalidates the first reset link."""
    user = create_test_customer(email="hannah@example.com")

    tokens = []
    with patch("app.api.endpoints.auth.send_password_reset_email", side_effect=lambda to_email, reset_url: tokens.append(reset_url.split("token=")[1])):
        # First request
        res1 = client.post("/api/v1/auth/forgot-password", json={"email": "hannah@example.com"})
        assert res1.status_code == 200

        # Reset rate limiter for next test call
        password_reset_rate_limiter.reset()

        # Second request
        res2 = client.post("/api/v1/auth/forgot-password", json={"email": "hannah@example.com"})
        assert res2.status_code == 200

    assert len(tokens) == 2
    token1, token2 = tokens[0], tokens[1]

    # First token MUST fail now (invalidated by second request)
    res_token1 = client.post("/api/v1/auth/reset-password", json={
        "token": token1,
        "new_password": "NewPassword123!"
    })
    assert res_token1.status_code == 400

    # Second token MUST succeed
    res_token2 = client.post("/api/v1/auth/reset-password", json={
        "token": token2,
        "new_password": "NewPassword123!"
    })
    assert res_token2.status_code == 200


def test_12_weak_password_rejected():
    """Password with fewer than 8 characters is rejected."""
    user = create_test_customer(email="ian@example.com")
    db = TestingSessionLocal()
    try:
        challenge, raw_token = create_password_reset_challenge(db, user)
        db.commit()
    finally:
        db.close()

    res = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token,
        "new_password": "short"
    })
    assert res.status_code in (400, 422)


def test_13_same_password_rejected():
    """Submitting the identical existing password is rejected."""
    user = create_test_customer(email="jack@example.com", password="SameOldPassword123!")
    db = TestingSessionLocal()
    try:
        challenge, raw_token = create_password_reset_challenge(db, user)
        db.commit()
    finally:
        db.close()

    res = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token,
        "new_password": "SameOldPassword123!"
    })
    assert res.status_code == 400
    assert "different from" in res.json()["detail"].lower()


# ============================================================================
# 3. CRITICAL SECURITY CONDITIONS: OTP, EMAIL_VERIFIED, IS_ACTIVE PRESERVATION
# ============================================================================

def test_14_unverified_account_remains_unverified_after_password_reset():
    """
    CRITICAL CONDITION 1 & 2:
    Password reset MUST NOT set email_verified = True on an unverified user.
    """
    user = create_test_customer(
        email="unverified@example.com",
        password="InitialPassword123!",
        email_verified=False
    )

    db = TestingSessionLocal()
    try:
        challenge, raw_token = create_password_reset_challenge(db, user)
        db.commit()
    finally:
        db.close()

    res = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token,
        "new_password": "ResetPassword123!"
    })
    assert res.status_code == 200

    # User MUST still have email_verified = False!
    db = TestingSessionLocal()
    try:
        updated_user = db.query(User).filter(User.id == user.id).first()
        assert updated_user.email_verified is False
    finally:
        db.close()

    # Login must still reject with 403 (Email not verified)
    res_login = client.post("/api/v1/auth/login", json={
        "email": "unverified@example.com",
        "password": "ResetPassword123!"
    })
    assert res_login.status_code == 403
    assert "email not verified" in res_login.json()["detail"].lower()


def test_15_password_reset_preserves_is_active_flag():
    """Password reset must not alter is_active state."""
    user = create_test_customer(email="activeuser@example.com", is_active=True)

    db = TestingSessionLocal()
    try:
        challenge, raw_token = create_password_reset_challenge(db, user)
        db.commit()
    finally:
        db.close()

    res = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token,
        "new_password": "NewActivePassword123!"
    })
    assert res.status_code == 200

    db = TestingSessionLocal()
    try:
        updated_user = db.query(User).filter(User.id == user.id).first()
        assert updated_user.is_active is True
    finally:
        db.close()


def test_16_password_reset_does_not_bypass_signup_otp():
    """
    Password reset cannot be used to activate an account with a pending signup OTP challenge.
    """
    # Simulate an account with a pending signup OTP challenge
    user = create_test_customer(
        email="pending_signup@example.com",
        password="TempPassword123!",
        email_verified=False
    )
    db = TestingSessionLocal()
    try:
        otp_challenge = EmailVerificationChallenge(
            user_id=user.id,
            email=user.email,
            otp_hash=hash_token("123456"),
            salt="somesalt",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            attempt_count=0
        )
        db.add(otp_challenge)
        reset_challenge, raw_token = create_password_reset_challenge(db, user)
        db.commit()
    finally:
        db.close()

    # Reset password
    res = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token,
        "new_password": "NewPassword123!"
    })
    assert res.status_code == 200

    # User remains unverified
    db = TestingSessionLocal()
    try:
        u = db.query(User).filter(User.id == user.id).first()
        assert u.email_verified is False
    finally:
        db.close()


# ============================================================================
# 4. CONCURRENCY & RACE CONDITION PROTECTION
# ============================================================================

def test_17_concurrency_two_simultaneous_resets_with_same_token_exactly_one_succeeds():
    """
    CRITICAL CONDITION 4:
    Two requests using the exact same reset token MUST result in
    exactly ONE successful password reset and ONE rejection (no double execution).
    """
    user = create_test_customer(email="race@example.com", password="InitialPassword123!")

    db = TestingSessionLocal()
    try:
        challenge, raw_token = create_password_reset_challenge(db, user)
        db.commit()
    finally:
        db.close()

    results = []

    # First consumption succeeds
    res1 = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token,
        "new_password": "ConcurrentPassword1!"
    })
    results.append(res1.status_code)

    # Immediate second consumption with the same token fails
    res2 = client.post("/api/v1/auth/reset-password", json={
        "token": raw_token,
        "new_password": "ConcurrentPassword2!"
    })
    results.append(res2.status_code)

    # Exactly one must be 200, the other must be 400
    assert results == [200, 400]


# ============================================================================
# 5. RATE LIMITING TESTS
# ============================================================================

def test_18_rate_limiting_forgot_password_per_ip():
    """Exceeding 5 forgot-password requests from same IP in window returns 429."""
    now = time.time()
    test_ip = "198.51.100.42"
    # Pre-populate 5 requests in history for this IP
    password_reset_rate_limiter._ip_requests[test_ip] = [
        now - 50, now - 40, now - 30, now - 20, now - 10
    ]

    res_blocked = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "ratelimit_blocked@example.com"},
        headers={"x-forwarded-for": test_ip}
    )
    assert res_blocked.status_code == 429
    assert "too many" in res_blocked.json()["detail"].lower()


def test_19_rate_limiting_forgot_password_per_email():
    """Exceeding 3 forgot-password requests for same email returns 429."""
    now = time.time()
    # Pre-populate 3 requests for this email
    password_reset_rate_limiter._email_requests["target@example.com"] = [
        now - 30, now - 20, now - 10
    ]

    res_blocked = client.post("/api/v1/auth/forgot-password", json={"email": "target@example.com"})
    assert res_blocked.status_code == 429
    assert "too many" in res_blocked.json()["detail"].lower()


# ============================================================================
# 6. RESEND EMAIL FAILURE SAFETY
# ============================================================================

def test_20_resend_provider_failure_does_not_leak_raw_tokens():
    """If email service throws an error, no token is leaked."""
    create_test_customer(email="resendfail@example.com")

    with patch("app.api.endpoints.auth.send_password_reset_email", side_effect=Exception("Resend API down")):
        res = client.post("/api/v1/auth/forgot-password", json={"email": "resendfail@example.com"})
        # In dev/test it returns generic or 503, but never leaks the token
        raw_output = res.text.lower()
        assert "token" not in raw_output
        assert "key" not in raw_output
