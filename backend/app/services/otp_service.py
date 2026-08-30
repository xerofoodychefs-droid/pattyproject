import hmac
import hashlib
import secrets
import time
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException, status

from app.core.config import settings
from app.models.verification import EmailVerificationChallenge
from app.models.user import User

OTP_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60


def generate_secure_otp() -> str:
    """
    Generates a cryptographically random 6-digit numeric OTP.
    Range: 100000 to 999999 inclusive.
    """
    code = secrets.randbelow(900000) + 100000
    return f"{code:06d}"


def hash_otp(email: str, otp: str, salt: str) -> str:
    """
    Computes a keyed HMAC-SHA256 hash of the OTP bound to the user's email and a unique salt.
    Never stores plaintext OTP.
    """
    key = f"{settings.SECRET_KEY}:{salt}".encode("utf-8")
    message = f"{email.strip().lower()}:{otp.strip()}".encode("utf-8")
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def verify_otp_hash(email: str, otp: str, salt: str, stored_hash: str) -> bool:
    """
    Performs constant-time comparison of submitted OTP against stored hash.
    Mitigates timing side-channel attacks.
    """
    calculated_hash = hash_otp(email=email, otp=otp, salt=salt)
    return secrets.compare_digest(stored_hash, calculated_hash)


def create_verification_challenge(
    db: Session,
    email: str,
    user_id: Optional[str] = None,
    full_name: Optional[str] = None,
    password_hash: Optional[str] = None,
    phone: Optional[str] = None
) -> Tuple[EmailVerificationChallenge, str]:
    """
    Invalidates any previous active challenges for this email,
    generates a secure 6-digit OTP, stores the hashed challenge,
    and returns the challenge model and the plaintext OTP (for immediate email dispatch only).
    """
    email_clean = email.strip().lower()
    now = datetime.now(timezone.utc)

    # Invalidate previous unexpired/unused challenges for this email
    active_challenges = db.query(EmailVerificationChallenge).filter(
        EmailVerificationChallenge.email == email_clean,
        EmailVerificationChallenge.used_at == None
    ).all()
    for ch in active_challenges:
        ch.used_at = now  # Mark as consumed/invalidated

    otp = generate_secure_otp()
    salt = secrets.token_hex(16)
    otp_hashed = hash_otp(email=email_clean, otp=otp, salt=salt)
    expires_at = now + timedelta(minutes=OTP_EXPIRY_MINUTES)

    challenge = EmailVerificationChallenge(
        user_id=user_id,
        email=email_clean,
        full_name=full_name.strip() if full_name else None,
        password_hash=password_hash,
        phone=phone.strip() if phone else None,
        otp_hash=otp_hashed,
        salt=salt,
        expires_at=expires_at,
        attempt_count=0,
        used_at=None,
        created_at=now
    )
    db.add(challenge)
    db.flush()

    return challenge, otp


def check_resend_cooldown(db: Session, email: str) -> Optional[int]:
    """
    Checks if a challenge was created recently.
    Returns remaining cooldown seconds if within 60s cooldown window, otherwise None.
    """
    email_clean = email.strip().lower()
    latest_challenge = db.query(EmailVerificationChallenge).filter(
        EmailVerificationChallenge.email == email_clean
    ).order_by(EmailVerificationChallenge.created_at.desc()).first()

    if not latest_challenge:
        return None

    now = datetime.now(timezone.utc)
    created_at = latest_challenge.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    elapsed = (now - created_at).total_seconds()
    if elapsed < RESEND_COOLDOWN_SECONDS:
        return int(RESEND_COOLDOWN_SECONDS - elapsed)

    return None
