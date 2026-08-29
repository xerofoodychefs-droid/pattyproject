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


def test_google_auth_email_collision_anti_takeover_and_anti_enumeration():
    """
    Test email collision protection:
    - If customer exists with local password, an unlinked Google login with same email
      is REJECTED with generic 401 failure to prevent account takeover and email enumeration.
    """
    # Register local customer and verify email
    reg_resp = client.post("/api/v1/auth/register", json={
        "email": "victim@pattyproject.co.uk",
        "password": "Password123!",
        "full_name": "Victim Customer"
    })
    assert reg_resp.status_code == 200

    db = TestingSessionLocal()
    try:
        victim_user = db.query(User).filter(User.email == "victim@pattyproject.co.uk").first()
        assert victim_user is not None
        victim_user.email_verified = True
        db.commit()
    finally:
        db.close()

    # Attacker tries to log in with Google using victim's email
    n = client.get("/api/v1/auth/google/nonce").json()
    t = make_test_google_id_token(
        sub="attacker-sub-666",
        email="victim@pattyproject.co.uk",
        nonce=n["nonce"]
    )
    resp = client.post("/api/v1/auth/google", json={"id_token": t, "state_token": n["state_token"]})

    assert resp.status_code == 401
    assert resp.json()["detail"] == GENERIC_AUTH_ERROR_DETAIL

    # Verify victim account was not altered
    db = TestingSessionLocal()
    try:
        ident = db.query(UserAuthIdentity).filter(UserAuthIdentity.provider_subject == "attacker-sub-666").first()
        assert ident is None

        # Verify local login still works
        login_resp = client.post("/api/v1/auth/login", json={
            "email": "victim@pattyproject.co.uk",
            "password": "Password123!"
        })
        assert login_resp.status_code == 200
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
