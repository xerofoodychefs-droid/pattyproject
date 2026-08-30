import secrets
import time
import uuid
import re
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Tuple, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from jose import jwt, JWTError
import httpx

from app.core.config import settings
from app.models.user import User, UserAuthIdentity, AuthProvider, AuthConsumedJti
from app.services.identity_service import find_identity, create_identity_for_user, IdentityConflictError
from app.services.customer_service import create_customer_with_loyalty

GENERIC_AUTH_ERROR_DETAIL = "Unable to complete sign in with Google. Please use your standard login method."
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ["accounts.google.com", "https://accounts.google.com"]

# In-memory JWKS cache
_jwks_cache: Dict[str, Any] = {
    "keys": {},
    "expires_at": 0.0
}

# Test override hook for deterministic testing
_jwks_test_override: Optional[Dict[str, Any]] = None


def set_jwks_test_override(override: Optional[Dict[str, Any]]):
    """Allows test fixtures to provide deterministic public keys for testing."""
    global _jwks_test_override
    _jwks_test_override = override


def generate_nonce_and_state_token() -> Tuple[str, str]:
    """
    Generates a cryptographically random nonce and binds it into an HMAC-SHA256 signed state token.
    State token contains: nonce, jti (unique token ID), exp (10 min TTL), type ('google_state').
    """
    nonce = secrets.token_urlsafe(32)
    jti = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=10)

    claims = {
        "nonce": nonce,
        "jti": jti,
        "type": "google_state",
        "exp": int(exp.timestamp()),
        "iat": int(now.timestamp())
    }

    state_token = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return nonce, state_token


def consume_state_token(db: Session, state_token: str) -> str:
    """
    Decodes state token, verifies signature and expiration, records the JTI in auth_consumed_jtis
    to prevent replay attacks across all processes/replicas, and returns expected nonce.
    """
    try:
        payload = jwt.decode(state_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR_DETAIL)

    if payload.get("type") != "google_state":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR_DETAIL)

    jti = payload.get("jti")
    nonce = payload.get("nonce")
    exp_ts = payload.get("exp")

    if not jti or not nonce or not exp_ts:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR_DETAIL)

    # Check multi-process database anti-replay table
    existing = db.query(AuthConsumedJti).filter(AuthConsumedJti.jti == jti).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR_DETAIL)

    try:
        exp_dt = datetime.fromtimestamp(exp_ts, tz=timezone.utc)
        consumed = AuthConsumedJti(jti=jti, expires_at=exp_dt)
        db.add(consumed)
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR_DETAIL)

    return nonce


def fetch_google_jwks(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Fetches Google's public JWKS certificates with HTTP Cache-Control header caching and dynamic refresh.
    """
    global _jwks_cache
    now = time.time()

    if _jwks_test_override is not None:
        return _jwks_test_override

    if not force_refresh and _jwks_cache["expires_at"] > now and _jwks_cache["keys"]:
        return _jwks_cache["keys"]

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(GOOGLE_CERTS_URL)
            if resp.status_code != 200:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR_DETAIL)

            data = resp.json()
            keys_dict = {key["kid"]: key for key in data.get("keys", []) if "kid" in key}

            # Parse Cache-Control max-age header
            cache_control = resp.headers.get("cache-control", "")
            match = re.search(r"max-age=(\d+)", cache_control)
            max_age = int(match.group(1)) if match else 3600

            _jwks_cache = {
                "keys": keys_dict,
                "expires_at": now + max_age
            }
            return keys_dict
    except Exception:
        if _jwks_cache["keys"]:
            return _jwks_cache["keys"]
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR_DETAIL)


def verify_google_id_token(id_token: str, expected_nonce: str) -> Dict[str, Any]:
    """
    Cryptographically verifies Google ID token:
    1. Extracts 'kid' from unverified header
    2. Fetches public RSA JWKS (with key rotation support on unknown kid)
    3. Verifies RS256 signature
    4. Validates 'iss', 'aud', 'exp', 'email_verified', and 'nonce'
    """
    try:
        unverified_header = jwt.get_unverified_header(id_token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR_DETAIL)

    kid = unverified_header.get("kid")
    if not kid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR_DETAIL)

    jwks = fetch_google_jwks()
    if kid not in jwks:
        # Key rotation check: refresh JWKS once
        jwks = fetch_google_jwks(force_refresh=True)

    if kid not in jwks:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR_DETAIL)

    key_data = jwks[kid]

    try:
        payload = jwt.decode(
            id_token,
            key_data,
            algorithms=["RS256"],
            audience=settings.GOOGLE_CLIENT_ID,
            issuer=GOOGLE_ISSUERS
        )
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR_DETAIL)

    # Validate email_verified claim
    email_verified = payload.get("email_verified")
    if email_verified is not True and str(email_verified).lower() != "true":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR_DETAIL)

    # Validate nonce claim
    token_nonce = payload.get("nonce")
    if not token_nonce or token_nonce != expected_nonce:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR_DETAIL)

    return payload


def authenticate_google_customer(db: Session, google_payload: Dict[str, Any]) -> User:
    """
    Resolves or creates the Patty Customer based on verified Google token claims:
    - Step 1: Query canonical Google identity by stable `sub`. If found, authenticate that existing customer.
    - Step 2: If no Google identity found by `sub`, search for an existing customer by verified Google email.
              If found:
                a) Verify that the existing customer is active.
                b) Check if the existing customer is already linked to a DIFFERENT Google `sub`.
                   If so, reject with a safe 409 Conflict error.
                c) Safely link the Google `sub` to the existing customer account.
                d) Preserve existing password_hash, loyalty account, points, orders, and profile data.
                e) Set email_verified=True if not already set.
                f) Commit and return the existing customer.
    - Step 3: If no existing customer by email, atomically create User + LoyaltyAccount + UserAuthIdentity.
              Handles multi-thread concurrency race conditions cleanly via database uniqueness constraints and deterministic rollback-requery.
    """
    sub = str(google_payload.get("sub", "")).strip()
    email = str(google_payload.get("email", "")).strip().lower()
    name = str(google_payload.get("name", "")).strip() or (email.split("@")[0].capitalize() if email else "Customer")

    if not sub or not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR_DETAIL)

    # Step 1: Query canonical Google identity by stable `sub`
    existing_identity = find_identity(db, AuthProvider.GOOGLE, sub)
    if existing_identity:
        user = db.query(User).filter(User.id == existing_identity.user_id).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR_DETAIL)
        return user

    # Step 2: Search for existing customer by verified Google email (Account Linking)
    existing_user_by_email = db.query(User).filter(User.email == email).first()
    if existing_user_by_email:
        if not existing_user_by_email.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR_DETAIL)

        # Check if this existing customer already has a Google identity linked
        existing_google_identities = [
            ident for ident in existing_user_by_email.auth_identities
            if ident.provider == AuthProvider.GOOGLE
        ]
        if existing_google_identities:
            # If already linked to THIS sub, return the user
            if any(ident.provider_subject == sub for ident in existing_google_identities):
                return existing_user_by_email

            # Different Google sub already linked to this profile - reject to prevent account conflict
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A different Google account is already linked to this profile. Please log in with your original credentials."
            )

        # Safely link Google identity to existing customer
        try:
            create_identity_for_user(
                db=db,
                user_id=existing_user_by_email.id,
                provider=AuthProvider.GOOGLE,
                provider_subject=sub
            )
            if not existing_user_by_email.email_verified:
                existing_user_by_email.email_verified = True
            db.commit()
            db.refresh(existing_user_by_email)
            return existing_user_by_email
        except (IntegrityError, IdentityConflictError):
            db.rollback()
            # Concurrency race condition: winning thread already linked the identity
            winning_identity = find_identity(db, AuthProvider.GOOGLE, sub)
            if winning_identity and winning_identity.user_id == existing_user_by_email.id:
                return existing_user_by_email

            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR_DETAIL)

    # Step 3: Atomic creation of brand new Customer + Loyalty + Google Identity
    try:
        user, loyalty = create_customer_with_loyalty(
            db=db,
            email=email,
            full_name=name,
            password_hash=None,
            welcome_points=100,
            email_verified=True
        )
        create_identity_for_user(
            db=db,
            user_id=user.id,
            provider=AuthProvider.GOOGLE,
            provider_subject=sub
        )
        db.commit()
        db.refresh(user)
        return user
    except (IntegrityError, IdentityConflictError):
        db.rollback()
        # Concurrency race condition: Another thread created user or identity
        # Deterministically check by identity first
        winning_identity = find_identity(db, AuthProvider.GOOGLE, sub)
        if winning_identity:
            winning_user = db.query(User).filter(User.id == winning_identity.user_id).first()
            if winning_user and winning_user.is_active:
                return winning_user

        # Deterministically check by email
        winning_user_by_email = db.query(User).filter(User.email == email).first()
        if winning_user_by_email and winning_user_by_email.is_active:
            winning_identity = find_identity(db, AuthProvider.GOOGLE, sub)
            if winning_identity and winning_identity.user_id == winning_user_by_email.id:
                return winning_user_by_email

            try:
                create_identity_for_user(
                    db=db,
                    user_id=winning_user_by_email.id,
                    provider=AuthProvider.GOOGLE,
                    provider_subject=sub
                )
                db.commit()
                db.refresh(winning_user_by_email)
                return winning_user_by_email
            except (IntegrityError, IdentityConflictError):
                db.rollback()
                winning_identity = find_identity(db, AuthProvider.GOOGLE, sub)
                if winning_identity and winning_identity.user_id == winning_user_by_email.id:
                    return winning_user_by_email

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=GENERIC_AUTH_ERROR_DETAIL)
