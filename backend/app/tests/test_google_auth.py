import time
import uuid
import threading
import pytest
from datetime import datetime, timezone, timedelta
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from jose import jwt, jwk
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.config import settings
from app.core.database import Base, get_db
from app.models.user import User, UserRole, AuthProvider, UserAuthIdentity, AuthConsumedJti
from app.models.loyalty import LoyaltyAccount
from app.services.google_auth_service import (
    set_jwks_test_override,
    generate_nonce_and_state_token,
    GENERIC_AUTH_ERROR_DETAIL
)
from app.tests.db import client, reset_test_db, TestingSessionLocal

# RSA Keypair for deterministic testing
_rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_private_pem = _rsa_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
).decode("utf-8")

_public_pem = _rsa_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo
).decode("utf-8")

# Forged/Untrusted RSA Keypair for signature validation tests
_forged_rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_forged_private_pem = _forged_rsa_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
).decode("utf-8")

TEST_KID = "test-google-kid-2026"
TEST_JWKS = {
    TEST_KID: _public_pem
}


def make_test_google_id_token(
    sub: str = "google-sub-1001",
    email: str = "testuser@gmail.com",
    name: str = "Test Google User",
    email_verified: bool = True,
    aud: str = settings.GOOGLE_CLIENT_ID,
    iss: str = "https://accounts.google.com",
    exp_delta: int = 3600,
    nonce: str = "test-nonce-123",
    kid: str = TEST_KID,
    key_pem: str = _private_pem
) -> str:
    now = int(time.time())
    claims = {
        "sub": sub,
        "email": email,
        "name": name,
        "email_verified": email_verified,
        "aud": aud,
        "iss": iss,
        "exp": now + exp_delta,
        "iat": now,
        "nonce": nonce
    }
    return jwt.encode(claims, key_pem, algorithm="RS256", headers={"kid": kid})


@pytest.fixture(autouse=True)
def setup_google_auth_test_env():
    reset_test_db()
    set_jwks_test_override(TEST_JWKS)
    yield
    set_jwks_test_override(None)


def test_google_config_endpoint():
    """Verify GET /api/v1/auth/google/config returns public client_id."""
    resp = client.get("/api/v1/auth/google/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "client_id" in data
    assert data["client_id"] == settings.GOOGLE_CLIENT_ID


def test_google_nonce_endpoint():
    """Verify GET /api/v1/auth/google/nonce returns nonce and signed state token."""
    resp = client.get("/api/v1/auth/google/nonce")
    assert resp.status_code == 200
    data = resp.json()
    assert "nonce" in data
    assert "state_token" in data
    assert len(data["nonce"]) > 16


def test_google_auth_new_customer_and_loyalty_creation():
    """
    Test new customer Google login:
    - Atomically creates User + 100 bonus LoyaltyAccount + UserAuthIdentity
    - Issues standard Patty JWT
    """
    nonce_resp = client.get("/api/v1/auth/google/nonce").json()
    nonce = nonce_resp["nonce"]
    state_token = nonce_resp["state_token"]

    id_token = make_test_google_id_token(
        sub="google-sub-new-001",
        email="newgoogle@pattyproject.co.uk",
        name="New Google Customer",
        nonce=nonce
    )

    resp = client.post("/api/v1/auth/google", json={
        "id_token": id_token,
        "state_token": state_token
    })

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["user"]["email"] == "newgoogle@pattyproject.co.uk"
    assert data["user"]["full_name"] == "New Google Customer"
    assert data["user"]["role"] == "CUSTOMER"

    # Verify database persistence
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == "newgoogle@pattyproject.co.uk").first()
        assert user is not None
        assert user.password_hash is None
        assert user.is_active is True

        loyalty = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == user.id).first()
        assert loyalty is not None
        assert loyalty.available_points == 100
        assert loyalty.lifetime_points == 100

        ident = db.query(UserAuthIdentity).filter(
            UserAuthIdentity.provider == AuthProvider.GOOGLE,
            UserAuthIdentity.provider_subject == "google-sub-new-001"
        ).first()
        assert ident is not None
        assert ident.user_id == user.id
    finally:
        db.close()


def test_google_auth_existing_customer_resolution():
    """
    Test subsequent Google login for already-created customer:
    - Resolves existing user and preserves loyalty data without creating duplicate records.
    """
    # 1. First Login (Creates User)
    n1 = client.get("/api/v1/auth/google/nonce").json()
    t1 = make_test_google_id_token(sub="google-sub-repeat-002", email="repeat@patty.co.uk", nonce=n1["nonce"])
    r1 = client.post("/api/v1/auth/google", json={"id_token": t1, "state_token": n1["state_token"]})
    assert r1.status_code == 200
    user_id_1 = r1.json()["user"]["id"]

    db = TestingSessionLocal()
    users_before = db.query(User).count()
    loyalty_before = db.query(LoyaltyAccount).count()
    db.close()

    # 2. Second Login (Resolves Existing User)
    n2 = client.get("/api/v1/auth/google/nonce").json()
    t2 = make_test_google_id_token(sub="google-sub-repeat-002", email="repeat@patty.co.uk", nonce=n2["nonce"])
    r2 = client.post("/api/v1/auth/google", json={"id_token": t2, "state_token": n2["state_token"]})
    assert r2.status_code == 200
    assert r2.json()["user"]["id"] == user_id_1

    db = TestingSessionLocal()
    assert db.query(User).count() == users_before
    assert db.query(LoyaltyAccount).count() == loyalty_before
    db.close()


def test_google_auth_account_linking_existing_password_user():
    """
    Test account linking for existing password customer:
    1. Seed an existing customer with password and 250 loyalty points.
    2. Customer signs in with Google using the SAME verified email.
    3. Login succeeds, returning the same user.
    4. Google sub is linked to existing User record.
    5. No duplicate User or LoyaltyAccount is created.
    6. Password login still works with original password.
    7. Subsequent Google login succeeds via linked sub.
    """
    from app.services.customer_service import create_customer_with_loyalty
    from app.core.security import get_password_hash

    db = TestingSessionLocal()
    try:
        existing_user, loyalty = create_customer_with_loyalty(
            db=db,
            email="linking.customer@pattyproject.co.uk",
            full_name="Original Customer",
            password_hash=get_password_hash("Password123!"),
            welcome_points=250,
            email_verified=True
        )
        db.commit()
        original_user_id = existing_user.id
        original_loyalty_id = loyalty.id
    finally:
        db.close()

    # Step 1: Sign in with Google using the SAME verified email
    n = client.get("/api/v1/auth/google/nonce").json()
    t = make_test_google_id_token(
        sub="google-sub-linked-999",
        email="linking.customer@pattyproject.co.uk",
        name="Google Name Override",
        nonce=n["nonce"]
    )
    resp = client.post("/api/v1/auth/google", json={"id_token": t, "state_token": n["state_token"]})

    assert resp.status_code == 200
    data = resp.json()
    assert data["user"]["id"] == original_user_id
    assert data["user"]["email"] == "linking.customer@pattyproject.co.uk"
    assert "access_token" in data

    # Verify database state
    db = TestingSessionLocal()
    try:
        # Exactly 1 user, 1 loyalty account, 1 Google identity
        users = db.query(User).filter(User.email == "linking.customer@pattyproject.co.uk").all()
        assert len(users) == 1
        assert users[0].id == original_user_id
        assert users[0].email_verified is True
        assert users[0].password_hash is not None  # Password was NOT erased

        loyalty_accounts = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == original_user_id).all()
        assert len(loyalty_accounts) == 1
        assert loyalty_accounts[0].id == original_loyalty_id
        assert loyalty_accounts[0].available_points == 250  # Points preserved

        identities = db.query(UserAuthIdentity).filter(UserAuthIdentity.user_id == original_user_id).all()
        assert len(identities) == 1
        assert identities[0].provider == AuthProvider.GOOGLE
        assert identities[0].provider_subject == "google-sub-linked-999"
    finally:
        db.close()

    # Step 2: Verify original password authentication STILL works
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "linking.customer@pattyproject.co.uk",
        "password": "Password123!"
    })
    assert login_resp.status_code == 200
    assert login_resp.json()["user"]["id"] == original_user_id

    # Step 3: Verify subsequent Google login succeeds via linked identity
    n2 = client.get("/api/v1/auth/google/nonce").json()
    t2 = make_test_google_id_token(
        sub="google-sub-linked-999",
        email="linking.customer@pattyproject.co.uk",
        nonce=n2["nonce"]
    )
    resp2 = client.post("/api/v1/auth/google", json={"id_token": t2, "state_token": n2["state_token"]})
    assert resp2.status_code == 200
    assert resp2.json()["user"]["id"] == original_user_id


def test_google_auth_reject_different_google_sub_on_already_linked_user():
    """
    If a user already has Google sub-A linked, attempting to link a DIFFERENT Google sub-B
    for the same user email is safely rejected with 409 Conflict.
    """
    from app.services.customer_service import create_customer_with_loyalty
    from app.services.identity_service import create_identity_for_user

    db = TestingSessionLocal()
    try:
        user, _ = create_customer_with_loyalty(
            db=db,
            email="already.linked@pattyproject.co.uk",
            full_name="Already Linked",
            email_verified=True
        )
        create_identity_for_user(
            db=db,
            user_id=user.id,
            provider=AuthProvider.GOOGLE,
            provider_subject="google-sub-original-111"
        )
        db.commit()
    finally:
        db.close()

    # Try logging in with a DIFFERENT Google sub for the same email
    n = client.get("/api/v1/auth/google/nonce").json()
    t = make_test_google_id_token(
        sub="google-sub-different-222",
        email="already.linked@pattyproject.co.uk",
        nonce=n["nonce"]
    )
    resp = client.post("/api/v1/auth/google", json={"id_token": t, "state_token": n["state_token"]})
    assert resp.status_code == 409
    assert "different google account" in resp.json()["detail"].lower()


def test_google_auth_sub_linked_to_user_a_does_not_hijack_user_b():
    """
    If Google sub-A is linked to User A, but a token arrives with sub-A and email of User B,
    it must authenticate User A (the owner of sub-A) and NOT alter/merge User B.
    """
    from app.services.customer_service import create_customer_with_loyalty
    from app.services.identity_service import create_identity_for_user

    db = TestingSessionLocal()
    try:
        user_a, _ = create_customer_with_loyalty(
            db=db,
            email="user_a@pattyproject.co.uk",
            full_name="User A",
            email_verified=True
        )
        create_identity_for_user(
            db=db,
            user_id=user_a.id,
            provider=AuthProvider.GOOGLE,
            provider_subject="google-sub-user-a"
        )
        user_b, _ = create_customer_with_loyalty(
            db=db,
            email="user_b@pattyproject.co.uk",
            full_name="User B",
            email_verified=True
        )
        db.commit()
        user_a_id = user_a.id
        user_b_id = user_b.id
    finally:
        db.close()

    n = client.get("/api/v1/auth/google/nonce").json()
    t = make_test_google_id_token(
        sub="google-sub-user-a",
        email="user_b@pattyproject.co.uk",  # Email changed at Google
        nonce=n["nonce"]
    )
    resp = client.post("/api/v1/auth/google", json={"id_token": t, "state_token": n["state_token"]})
    assert resp.status_code == 200
    assert resp.json()["user"]["id"] == user_a_id  # Returns User A (owner of sub)

    # Verify User B was NOT modified or linked
    db = TestingSessionLocal()
    try:
        user_b_identities = db.query(UserAuthIdentity).filter(UserAuthIdentity.user_id == user_b_id).all()
        assert len(user_b_identities) == 0
    finally:
        db.close()


def test_google_auth_invalid_signature():
    """Verify forged signature is rejected with generic 401."""
    n = client.get("/api/v1/auth/google/nonce").json()
    t = make_test_google_id_token(nonce=n["nonce"], key_pem=_forged_private_pem)
    resp = client.post("/api/v1/auth/google", json={"id_token": t, "state_token": n["state_token"]})
    assert resp.status_code == 401
    assert resp.json()["detail"] == GENERIC_AUTH_ERROR_DETAIL


def test_google_auth_expired_token():
    """Verify expired token is rejected with generic 401."""
    n = client.get("/api/v1/auth/google/nonce").json()
    t = make_test_google_id_token(nonce=n["nonce"], exp_delta=-3600)
    resp = client.post("/api/v1/auth/google", json={"id_token": t, "state_token": n["state_token"]})
    assert resp.status_code == 401
    assert resp.json()["detail"] == GENERIC_AUTH_ERROR_DETAIL


def test_google_auth_wrong_audience():
    """Verify wrong audience (aud) is rejected with generic 401."""
    n = client.get("/api/v1/auth/google/nonce").json()
    t = make_test_google_id_token(nonce=n["nonce"], aud="unauthorized-client-id.apps.google.com")
    resp = client.post("/api/v1/auth/google", json={"id_token": t, "state_token": n["state_token"]})
    assert resp.status_code == 401
    assert resp.json()["detail"] == GENERIC_AUTH_ERROR_DETAIL


def test_google_auth_unverified_email():
    """Verify unverified Google email (email_verified=False) is rejected with generic 401."""
    n = client.get("/api/v1/auth/google/nonce").json()
    t = make_test_google_id_token(nonce=n["nonce"], email_verified=False)
    resp = client.post("/api/v1/auth/google", json={"id_token": t, "state_token": n["state_token"]})
    assert resp.status_code == 401
    assert resp.json()["detail"] == GENERIC_AUTH_ERROR_DETAIL


def test_google_auth_nonce_mismatch():
    """Verify nonce mismatch between state_token and ID token is rejected with generic 401."""
    n = client.get("/api/v1/auth/google/nonce").json()
    t = make_test_google_id_token(nonce="different-untrusted-nonce")
    resp = client.post("/api/v1/auth/google", json={"id_token": t, "state_token": n["state_token"]})
    assert resp.status_code == 401
    assert resp.json()["detail"] == GENERIC_AUTH_ERROR_DETAIL


def test_google_auth_state_token_replay_protection():
    """Verify state token cannot be replayed twice."""
    n = client.get("/api/v1/auth/google/nonce").json()
    t = make_test_google_id_token(sub="replay-sub-1", email="replay1@patty.co.uk", nonce=n["nonce"])

    # First call succeeds
    r1 = client.post("/api/v1/auth/google", json={"id_token": t, "state_token": n["state_token"]})
    assert r1.status_code == 200

    # Second call with identical state token fails (consumed JTI)
    r2 = client.post("/api/v1/auth/google", json={"id_token": t, "state_token": n["state_token"]})
    assert r2.status_code == 401
    assert r2.json()["detail"] == GENERIC_AUTH_ERROR_DETAIL


def test_google_auth_inactive_user_rejected():
    """Verify disabled account is rejected with generic 401."""
    n1 = client.get("/api/v1/auth/google/nonce").json()
    t1 = make_test_google_id_token(sub="sub-disabled-001", email="disabled@patty.co.uk", nonce=n1["nonce"])
    r1 = client.post("/api/v1/auth/google", json={"id_token": t1, "state_token": n1["state_token"]})
    assert r1.status_code == 200
    user_id = r1.json()["user"]["id"]

    # Deactivate user
    db = TestingSessionLocal()
    user = db.query(User).filter(User.id == user_id).first()
    user.is_active = False
    db.commit()
    db.close()

    # Attempt login again
    n2 = client.get("/api/v1/auth/google/nonce").json()
    t2 = make_test_google_id_token(sub="sub-disabled-001", email="disabled@patty.co.uk", nonce=n2["nonce"])
    r2 = client.post("/api/v1/auth/google", json={"id_token": t2, "state_token": n2["state_token"]})
    assert r2.status_code == 401
    assert r2.json()["detail"] == GENERIC_AUTH_ERROR_DETAIL


def test_google_auth_concurrency_race_condition(tmp_path):
    """
    Concurrency Race Condition Test:
    Simultaneously issue 4 concurrent requests trying to create the same new Google identity.
    Verifies that exactly ONE user, ONE loyalty account, and ONE Google identity is created,
    and all concurrent threads resolve cleanly to the same user without duplicate records.
    """
    db_file = tmp_path / "google_concurrency.db"
    concurrency_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False, "timeout": 30.0}
    )
    Base.metadata.create_all(bind=concurrency_engine)
    ConcSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=concurrency_engine)

    from app.services.google_auth_service import authenticate_google_customer

    google_data = {
        "sub": "concurrency-google-sub-777",
        "email": "concurrency_google@patty.co.uk",
        "name": "Concurrency User"
    }

    results = []
    errors = []

    def worker():
        session = ConcSessionLocal()
        try:
            user = authenticate_google_customer(session, google_data)
            results.append(user.id)
        except Exception as e:
            errors.append(e)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All threads must succeed and return the exact same user ID
    assert len(errors) == 0
    assert len(results) == 4
    assert len(set(results)) == 1

    # Verify exactly 1 user, 1 loyalty account, and 1 Google identity in database
    verify_db = ConcSessionLocal()
    try:
        users = verify_db.query(User).filter(User.email == "concurrency_google@patty.co.uk").all()
        assert len(users) == 1

        loyalty = verify_db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == users[0].id).all()
        assert len(loyalty) == 1
        assert loyalty[0].available_points == 100

        identities = verify_db.query(UserAuthIdentity).filter(
            UserAuthIdentity.provider_subject == "concurrency-google-sub-777"
        ).all()
        assert len(identities) == 1
    finally:
        verify_db.close()


def test_google_auth_complete_otp_registration_then_google_linking_lifecycle(monkeypatch):
    """
    Complete Lifecycle Test:
    1. Register with email + password.
    2. Before OTP: NO User, NO LoyaltyAccount in DB.
    3. Verify OTP: exactly ONE User and ONE LoyaltyAccount created.
    4. Google Sign-In with SAME verified email:
       - Returns HTTP 200 with the exact same user ID.
       - Links Google sub.
       - Leaves password and loyalty points untouched.
       - Does NOT create duplicate user or loyalty account.
    5. Google Sign-In again: succeeds with same user ID.
    6. Email + Password login: still succeeds with original password.
    7. Database verification: exactly 1 user, 1 loyalty account, 1 Google identity.
    """
    sent_emails = []

    def mock_send(to_email, otp):
        sent_emails.append({"to_email": to_email, "otp": otp})
        return True

    monkeypatch.setattr("app.api.endpoints.auth.send_verification_otp_email", mock_send)

    test_email = "otp.lifecycle@pattyproject.co.uk"
    test_password = "Password123!"

    # 1. Registration
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": test_email,
        "password": test_password,
        "full_name": "OTP Lifecycle Customer",
        "phone": "07111222333"
    })
    assert reg_resp.status_code == 200
    assert reg_resp.json()["requires_verification"] is True

    # 2. Before OTP: Assert NO User, NO LoyaltyAccount
    db = TestingSessionLocal()
    try:
        assert db.query(User).filter(User.email == test_email).first() is None
        assert db.query(LoyaltyAccount).count() == 0
    finally:
        db.close()

    assert len(sent_emails) == 1
    otp_code = sent_emails[0]["otp"]

    # 3. OTP Verification
    verify_resp = client.post("/api/v1/auth/verify-email", json={
        "email": test_email,
        "otp": otp_code
    })
    assert verify_resp.status_code == 200
    created_user_id = verify_resp.json()["user"]["id"]

    # After OTP: exactly 1 User and 1 LoyaltyAccount
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == test_email).first()
        assert user is not None
        assert user.id == created_user_id
        assert user.email_verified is True
        loyalty = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == created_user_id).first()
        assert loyalty is not None
        assert loyalty.available_points == 100
    finally:
        db.close()

    # 4. First Google Sign-In with SAME email
    n1 = client.get("/api/v1/auth/google/nonce").json()
    t1 = make_test_google_id_token(
        sub="google-sub-lifecycle-777",
        email=test_email,
        name="Google Name",
        nonce=n1["nonce"]
    )
    g_resp1 = client.post("/api/v1/auth/google", json={"id_token": t1, "state_token": n1["state_token"]})
    assert g_resp1.status_code == 200
    assert g_resp1.json()["user"]["id"] == created_user_id
    assert "access_token" in g_resp1.json()

    # 5. Second Google Sign-In
    n2 = client.get("/api/v1/auth/google/nonce").json()
    t2 = make_test_google_id_token(
        sub="google-sub-lifecycle-777",
        email=test_email,
        nonce=n2["nonce"]
    )
    g_resp2 = client.post("/api/v1/auth/google", json={"id_token": t2, "state_token": n2["state_token"]})
    assert g_resp2.status_code == 200
    assert g_resp2.json()["user"]["id"] == created_user_id

    # 6. Email + Password login still works
    pw_resp = client.post("/api/v1/auth/login", json={
        "email": test_email,
        "password": test_password
    })
    assert pw_resp.status_code == 200
    assert pw_resp.json()["user"]["id"] == created_user_id

    # 7. Final Database Integrity Check
    db = TestingSessionLocal()
    try:
        users = db.query(User).filter(User.email == test_email).all()
        assert len(users) == 1
        assert users[0].id == created_user_id
        assert users[0].password_hash is not None

        loyalty_accounts = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == created_user_id).all()
        assert len(loyalty_accounts) == 1
        assert loyalty_accounts[0].available_points == 100

        identities = db.query(UserAuthIdentity).filter(UserAuthIdentity.user_id == created_user_id).all()
        assert len(identities) == 1
        assert identities[0].provider == AuthProvider.GOOGLE
        assert identities[0].provider_subject == "google-sub-lifecycle-777"
    finally:
        db.close()


def test_google_auth_concurrency_race_condition_on_account_linking(tmp_path):
    """
    Concurrent Account Linking Race Condition Test:
    An existing password customer is seeded.
    4 simultaneous concurrent requests try to link the same Google sub to this user.
    Verifies that all 4 threads resolve cleanly to the same user, exactly 1 Google identity is linked,
    and no duplicate users or loyalty accounts are created.
    """
    db_file = tmp_path / "google_linking_concurrency.db"
    concurrency_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False, "timeout": 30.0}
    )
    Base.metadata.create_all(bind=concurrency_engine)
    ConcSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=concurrency_engine)

    from app.services.customer_service import create_customer_with_loyalty
    from app.services.google_auth_service import authenticate_google_customer
    from app.core.security import get_password_hash

    # Seed existing customer
    seed_db = ConcSessionLocal()
    try:
        user, _ = create_customer_with_loyalty(
            db=seed_db,
            email="concurrent.linking@pattyproject.co.uk",
            full_name="Concurrent Linking User",
            password_hash=get_password_hash("Password123!"),
            welcome_points=300,
            email_verified=True
        )
        seed_db.commit()
        seeded_user_id = user.id
    finally:
        seed_db.close()

    google_data = {
        "sub": "concurrency-linking-sub-888",
        "email": "concurrent.linking@pattyproject.co.uk",
        "name": "Google Name"
    }

    results = []
    errors = []

    def worker():
        session = ConcSessionLocal()
        try:
            user = authenticate_google_customer(session, google_data)
            results.append(user.id)
        except Exception as e:
            errors.append(e)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All threads must succeed and return the exact same user ID
    assert len(errors) == 0
    assert len(results) == 4
    assert len(set(results)) == 1
    assert results[0] == seeded_user_id

    # Verify exactly 1 user, 1 loyalty account, and 1 Google identity in database
    verify_db = ConcSessionLocal()
    try:
        users = verify_db.query(User).filter(User.email == "concurrent.linking@pattyproject.co.uk").all()
        assert len(users) == 1
        assert users[0].id == seeded_user_id

        loyalty = verify_db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == seeded_user_id).all()
        assert len(loyalty) == 1
        assert loyalty[0].available_points == 300

        identities = verify_db.query(UserAuthIdentity).filter(
            UserAuthIdentity.provider_subject == "concurrency-linking-sub-888"
        ).all()
        assert len(identities) == 1
        assert identities[0].user_id == seeded_user_id
    finally:
        verify_db.close()
