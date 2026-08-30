import os
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from fastapi import Request, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_token
from app.models.verification import PasswordResetChallenge
from app.models.user import User

RESET_TOKEN_EXPIRY_MINUTES = 30


def generate_secure_reset_token() -> str:
    """
    Generates a cryptographically random 256-bit URL-safe reset token.
    Entropy: 32 bytes (256 bits).
    """
    return secrets.token_urlsafe(32)


def get_frontend_base_url(request: Optional[Request] = None) -> str:
    """
    Determines the canonical HTTPS base URL for password reset links.
    In production: defaults to https://www.pattyproject.co.uk.
    In dev: respects FRONTEND_URL or matching CORS origin from Request.
    """
    env_url = os.getenv("FRONTEND_BASE_URL") or os.getenv("FRONTEND_URL")
    if env_url:
        return env_url.rstrip("/")

    if settings.is_production:
        return "https://www.pattyproject.co.uk"

    if request:
        origin = request.headers.get("origin")
        if origin:
            clean_origin = origin.rstrip("/")
            for allowed in settings.cors_origins:
                if clean_origin == allowed.rstrip("/"):
                    return clean_origin

    return "http://localhost:3000"


def create_password_reset_challenge(
    db: Session,
    user: User
) -> Tuple[PasswordResetChallenge, str]:
    """
    Invalidates any previous active reset challenges for this user,
    generates a high-entropy 256-bit token, stores only the SHA-256 hash,
    and returns (challenge, raw_token).

    Security:
    - Raw token is never persisted in the database.
    - Raw token is only returned to the caller for immediate email dispatch.
    - Expiration is set to 30 minutes.
    """
    now = datetime.now(timezone.utc)

    # Invalidate previous unconsumed challenges for this user
    active_challenges = db.query(PasswordResetChallenge).filter(
        PasswordResetChallenge.user_id == user.id,
        PasswordResetChallenge.used_at == None
    ).all()
    for ch in active_challenges:
        ch.used_at = now

    raw_token = generate_secure_reset_token()
    token_hash = hash_token(raw_token)
    expires_at = now + timedelta(minutes=RESET_TOKEN_EXPIRY_MINUTES)

    challenge = PasswordResetChallenge(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        used_at=None,
        created_at=now
    )
    db.add(challenge)
    db.flush()

    return challenge, raw_token


def consume_password_reset_token(
    db: Session,
    token: str
) -> Tuple[PasswordResetChallenge, User]:
    """
    Validates submitted raw reset token, checks expiration, single-use,
    and account active status. Atomically marks the challenge as used
    to guarantee concurrency-safety under race conditions.

    Returns (challenge, user).
    Raises HTTPException 400 with a generic message if invalid/expired/used.
    """
    clean_token = token.strip()
    if not clean_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset link. Please request a new one."
        )

    now = datetime.now(timezone.utc)
    token_hash = hash_token(clean_token)

    challenge = db.query(PasswordResetChallenge).filter(
        PasswordResetChallenge.token_hash == token_hash
    ).first()

    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset link. Please request a new one."
        )

    if challenge.used_at is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link has already been used. Please request a new one."
        )

    # Check expiration
    ch_expires = challenge.expires_at
    if ch_expires.tzinfo is None:
        ch_expires = ch_expires.replace(tzinfo=timezone.utc)

    if ch_expires < now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link has expired. Please request a new one."
        )

    user_id = challenge.user_id
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account associated with this reset link is inactive or no longer exists."
        )

    # Concurrency-safe atomic consumption:
    # Update used_at only if it is still None.
    rows_updated = db.query(PasswordResetChallenge).filter(
        PasswordResetChallenge.id == challenge.id,
        PasswordResetChallenge.used_at == None
    ).update({"used_at": now}, synchronize_session=False)

    if rows_updated != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This password reset link is already being processed or has been used."
        )

    return challenge, user
