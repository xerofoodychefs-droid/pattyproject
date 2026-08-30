import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from app.core.database import get_db
from app.core.security import (
    verify_password, get_password_hash, create_access_token,
    generate_refresh_token, hash_token
)
from app.core.config import settings
from app.models.user import User, UserRole, CustomerAddress, AuthSession
from app.models.verification import EmailVerificationChallenge, PasswordResetChallenge
from app.models.loyalty import LoyaltyAccount
from app.schemas.auth import (
    LoginRequest, RegisterRequest, SocialLoginRequest, Token, UserResponse,
    GoogleAuthRequest, GoogleNonceResponse, GoogleConfigResponse, ChangePasswordRequest,
    RefreshTokenRequest, LogoutRequest,
    VerifyEmailRequest, ResendVerificationRequest, RegistrationResponse,
    ForgotPasswordRequest, ForgotPasswordResponse, ResetPasswordRequest, ResetPasswordResponse
)
from app.core.rate_limiter import password_reset_rate_limiter
from app.services.customer_service import create_customer_with_loyalty
from app.services.google_auth_service import (
    generate_nonce_and_state_token,
    consume_state_token,
    verify_google_id_token,
    authenticate_google_customer
)
from app.services.otp_service import (
    create_verification_challenge,
    verify_otp_hash,
    check_resend_cooldown,
    OTP_MAX_ATTEMPTS
)
from app.services.password_reset_service import (
    create_password_reset_challenge,
    consume_password_reset_token,
    get_frontend_base_url
)
from app.services.email_service import (
    send_verification_otp_email,
    send_password_reset_email
)
import logging

logger = logging.getLogger("patty_project.auth")

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise credentials_exception
    return user

oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)

def get_optional_current_user(token: str = Depends(oauth2_scheme_optional), db: Session = Depends(get_db)):
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id:
            return db.query(User).filter(User.id == user_id).first()
    except Exception:
        return None
    return None

def require_role(roles: list):
    def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions for this action"
            )
        return current_user
    return role_checker


def create_user_session(db: Session, user: User, http_req: Optional[Request] = None) -> Token:
    """Helper to issue short-lived access token and create persistent AuthSession record."""
    access_token = create_access_token(subject=user.id, roles=[user.role])
    refresh_token = generate_refresh_token()
    refresh_hash = hash_token(refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    ua = http_req.headers.get("user-agent", "")[:255] if http_req else None
    ip = http_req.client.host[:45] if http_req and http_req.client else None

    session = AuthSession(
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        expires_at=expires_at,
        is_revoked=False,
        user_agent=ua,
        ip_address=ip
    )
    db.add(session)
    db.commit()

    branch_ids = [bu.branch_id for bu in user.branch_assignments]
    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        role=user.role,
        is_active=user.is_active,
        email_verified=user.email_verified,
        branch_ids=branch_ids
    )
    return Token(access_token=access_token, refresh_token=refresh_token, user=user_resp)


@router.post("/login", response_model=Token)
def login(request: LoginRequest, http_req: Request, db: Session = Depends(get_db)):
    email_clean = request.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()

    if not user and "@" in email_clean:
        # Fallback search for dot-relaxed email variations (e.g., john.smith vs johnsmith)
        all_users = db.query(User).all()
        target_normalized = email_clean.replace(".", "")
        for u in all_users:
            if u.email.lower().replace(".", "") == target_normalized:
                user = u
                break

    if not user or not user.password_hash or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Account disabled")

    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please enter the verification code sent to your email."
        )

    # Safe guard for BRANCH_ADMIN: must have at least one active branch assignment
    if user.role == UserRole.BRANCH_ADMIN and len(user.branch_assignments) == 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Branch Admin account has no active branch assignment."
        )

    return create_user_session(db=db, user=user, http_req=http_req)


@router.post("/register", response_model=RegistrationResponse)
@router.post("/register/request-otp", response_model=RegistrationResponse)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    email_clean = request.email.strip().lower()

    # 1. Validate registration fields
    if not request.full_name or not request.full_name.strip():
        raise HTTPException(status_code=400, detail="Full name is required")
    if not email_clean or "@" not in email_clean:
        raise HTTPException(status_code=400, detail="Valid email is required")
    if not request.password or len(request.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")

    # 2. Check if a VERIFIED account already exists
    existing = db.query(User).filter(User.email == email_clean).first()
    if existing and existing.email_verified:
        raise HTTPException(status_code=400, detail="Email already registered")

    # 3. Securely hash password
    pwd_hash = get_password_hash(request.password)

    # 4. Create verification challenge WITHOUT creating permanent user in database
    challenge, otp = create_verification_challenge(
        db=db,
        email=email_clean,
        user_id=existing.id if existing else None,
        full_name=request.full_name.strip(),
        password_hash=pwd_hash,
        phone=request.phone.strip() if request.phone else None
    )
    db.commit()

    # 5. Dispatch verification code via Resend
    try:
        send_verification_otp_email(to_email=email_clean, otp=otp)
    except Exception:
        # If email delivery fails, clean up challenge so no orphaned un-emailed OTP exists
        try:
            db.delete(challenge)
            db.commit()
        except Exception:
            db.rollback()
        raise

    return RegistrationResponse(
        message="Verification code sent to your email.",
        email=email_clean,
        requires_verification=True
    )


@router.post("/verify-email", response_model=Token)
@router.post("/register/verify-otp", response_model=Token)
def verify_email(request: VerifyEmailRequest, http_req: Request, db: Session = Depends(get_db)):
    email_clean = request.email.strip().lower()
    now = datetime.now(timezone.utc)

    # Find latest active challenge
    challenge = db.query(EmailVerificationChallenge).filter(
        EmailVerificationChallenge.email == email_clean,
        EmailVerificationChallenge.used_at == None
    ).order_by(EmailVerificationChallenge.created_at.desc()).first()

    if not challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active verification code found. Please request a new code."
        )

    exp = challenge.expires_at.replace(tzinfo=timezone.utc) if challenge.expires_at.tzinfo is None else challenge.expires_at
    if exp < now:
        challenge.used_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired. Please request a new code."
        )

    if challenge.attempt_count >= OTP_MAX_ATTEMPTS:
        challenge.used_at = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum verification attempts exceeded. Please request a new code."
        )

    # Constant-time comparison
    if not verify_otp_hash(email=email_clean, otp=request.otp, salt=challenge.salt, stored_hash=challenge.otp_hash):
        challenge.attempt_count += 1
        db.commit()
        remaining = max(0, OTP_MAX_ATTEMPTS - challenge.attempt_count)
        if remaining > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid verification code. {remaining} attempt{'s' if remaining != 1 else ''} remaining."
            )
        else:
            challenge.used_at = now
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum verification attempts exceeded. Please request a new code."
            )

    # Successful verification
    challenge.used_at = now

    # Invalidate any remaining active challenges for this email
    active_challenges = db.query(EmailVerificationChallenge).filter(
        EmailVerificationChallenge.email == email_clean,
        EmailVerificationChallenge.used_at == None
    ).all()
    for ch in active_challenges:
        ch.used_at = now

    # Check if user already exists in DB
    user = None
    if challenge.user_id:
        user = db.query(User).filter(User.id == challenge.user_id).first()
    if not user:
        user = db.query(User).filter(User.email == email_clean).first()

    if user:
        # Existing unverified user being verified
        user.email_verified = True
        user.is_active = True
        if challenge.full_name:
            user.full_name = challenge.full_name
        if challenge.password_hash:
            user.password_hash = challenge.password_hash
        if challenge.phone:
            user.phone = challenge.phone
        if not user.loyalty_account:
            loyalty_acc = LoyaltyAccount(
                user_id=user.id,
                available_points=100,
                lifetime_points=100
            )
            db.add(loyalty_acc)
    else:
        # BRAND NEW REGISTRATION: Create permanent CUSTOMER and 100 Welcome Points ONLY NOW
        user, loyalty_acc = create_customer_with_loyalty(
            db=db,
            email=email_clean,
            full_name=challenge.full_name or "Customer",
            password_hash=challenge.password_hash,
            phone=challenge.phone,
            welcome_points=100,
            email_verified=True
        )
        challenge.user_id = user.id

    db.commit()
    db.refresh(user)

    # Issue authorized session & tokens
    return create_user_session(db=db, user=user, http_req=http_req)


@router.post("/resend-verification")
def resend_verification(request: ResendVerificationRequest, db: Session = Depends(get_db)):
    email_clean = request.email.strip().lower()

    # Rate limiting & cooldown check
    cooldown = check_resend_cooldown(db, email_clean)
    if cooldown is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {cooldown} seconds before requesting a new verification code."
        )

    # Check if existing verified account
    user = db.query(User).filter(User.email == email_clean).first()
    if user and user.email_verified:
        return {"message": "This account is already verified. Please sign in."}

    # Find previous pending challenge data if any
    latest_challenge = db.query(EmailVerificationChallenge).filter(
        EmailVerificationChallenge.email == email_clean
    ).order_by(EmailVerificationChallenge.created_at.desc()).first()

    if not user and not latest_challenge:
        # Safe response to prevent account enumeration
        return {"message": "If an unverified account exists for this email, a verification code has been sent."}

    challenge, otp = create_verification_challenge(
        db=db,
        email=email_clean,
        user_id=user.id if user else None,
        full_name=latest_challenge.full_name if latest_challenge else (user.full_name if user else None),
        password_hash=latest_challenge.password_hash if latest_challenge else (user.password_hash if user else None),
        phone=latest_challenge.phone if latest_challenge else (user.phone if user else None)
    )
    db.commit()

    send_verification_otp_email(to_email=email_clean, otp=otp)

    return {"message": "A new verification code has been sent to your email."}


@router.post("/refresh", response_model=Token)
def refresh_token(request: RefreshTokenRequest, http_req: Request, db: Session = Depends(get_db)):
    """
    Refreshes an access token using a valid, non-expired, non-revoked refresh token.
    Performs Refresh Token Rotation:
    - Generates a new refresh token and replaces the old token hash.
    - Mitigates token replay/theft.
    - Issues a fresh short-lived access token.
    """
    token_hash = hash_token(request.refresh_token)
    session = db.query(AuthSession).filter(
        AuthSession.refresh_token_hash == token_hash,
        AuthSession.is_revoked == False
    ).first()

    now_utc = datetime.now(timezone.utc)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    session_exp = session.expires_at.replace(tzinfo=timezone.utc) if session.expires_at.tzinfo is None else session.expires_at
    if session_exp < now_utc:
        session.is_revoked = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = session.user
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account disabled or user not found"
        )

    # Refresh Token Rotation: rotate refresh token and extend expiration
    new_refresh_token = generate_refresh_token()
    session.refresh_token_hash = hash_token(new_refresh_token)
    session.expires_at = now_utc + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    session.last_used_at = now_utc
    if http_req:
        session.user_agent = http_req.headers.get("user-agent", "")[:255]
        if http_req.client:
            session.ip_address = http_req.client.host[:45]
    db.commit()

    new_access_token = create_access_token(subject=user.id, roles=[user.role])
    branch_ids = [bu.branch_id for bu in user.branch_assignments]
    user_resp = UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        role=user.role,
        is_active=user.is_active,
        branch_ids=branch_ids
    )
    return Token(access_token=new_access_token, refresh_token=new_refresh_token, user=user_resp)


@router.post("/logout")
def logout(
    request: Optional[LogoutRequest] = None,
    current_user: Optional[User] = Depends(get_optional_current_user),
    db: Session = Depends(get_db)
):
    """
    Invalidates the active session and marks the refresh token as revoked.
    """
    if request and request.refresh_token:
        token_hash = hash_token(request.refresh_token)
        session = db.query(AuthSession).filter(AuthSession.refresh_token_hash == token_hash).first()
        if session:
            session.is_revoked = True
            db.commit()
    elif current_user:
        # Revoke all active sessions for current user if explicit refresh token is not provided
        sessions = db.query(AuthSession).filter(
            AuthSession.user_id == current_user.id,
            AuthSession.is_revoked == False
        ).all()
        for s in sessions:
            s.is_revoked = True
        db.commit()

    return {"message": "Logged out successfully"}


@router.get("/google/config", response_model=GoogleConfigResponse)
def get_google_config():
    """
    Returns public Google OAuth Client ID for frontend GIS initialization.
    """
    return GoogleConfigResponse(client_id=settings.GOOGLE_CLIENT_ID)


@router.get("/google/nonce", response_model=GoogleNonceResponse)
def get_google_nonce():
    """
    Generates a cryptographically random nonce and signed state token for Google GIS authentication.
    """
    nonce, state_token = generate_nonce_and_state_token()
    return GoogleNonceResponse(nonce=nonce, state_token=state_token)


@router.post("/google", response_model=Token)
def google_auth(request: GoogleAuthRequest, http_req: Request, db: Session = Depends(get_db)):
    """
    Verifies Google ID Token cryptographically against Google public JWKS,
    validates nonce and replay state, resolves or creates the customer atomically,
    and returns a standard Patty JWT and persistent AuthSession.
    """
    # Validate and consume state token across processes (Anti-Replay)
    expected_nonce = consume_state_token(db=db, state_token=request.state_token)

    # Cryptographically verify Google ID Token claims
    google_payload = verify_google_id_token(id_token=request.id_token, expected_nonce=expected_nonce)

    # Resolve existing customer or create new customer + loyalty + Google identity
    user = authenticate_google_customer(db=db, google_payload=google_payload)

    return create_user_session(db=db, user=user, http_req=http_req)


@router.post("/social-login", response_model=Token, deprecated=True)
def social_login(request: SocialLoginRequest, db: Session = Depends(get_db)):
    """
    Deprecated: Unverified social login endpoint disabled for security.
    Replaced by verified Google and Apple OAuth in upcoming release.
    """
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail="Unverified social login is deprecated and disabled for security. Verified Google and Apple authentication will be enabled in the next release."
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    branch_ids = [bu.branch_id for bu in current_user.branch_assignments]
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        phone=current_user.phone,
        role=current_user.role,
        is_active=current_user.is_active,
        branch_ids=branch_ids
    )


@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Secure password update for authenticated users & admins:
    - Verifies current password using Argon2id.
    - Validates new password length (minimum 8 characters).
    - Prevents reusing the same password.
    - Hashes new password with Argon2id and commits to database.
    - Invalidates all existing active sessions.
    - Never returns or logs plain text passwords.
    """
    if not current_user.password_hash or not verify_password(request.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    new_pwd = request.new_password.strip()
    if len(new_pwd) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters long"
        )

    if verify_password(new_pwd, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )

    current_user.password_hash = get_password_hash(new_pwd)
    # Revoke other active sessions on password change
    sessions = db.query(AuthSession).filter(
        AuthSession.user_id == current_user.id,
        AuthSession.is_revoked == False
    ).all()
    for s in sessions:
        s.is_revoked = True

    db.commit()
    return {"message": "Password updated successfully"}


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    request: ForgotPasswordRequest,
    http_req: Request,
    db: Session = Depends(get_db)
):
    """
    Public endpoint to initiate a password reset challenge:
    - Enforces IP and per-email rate limiting.
    - Prevents account enumeration by returning an identical generic response
      regardless of whether the account exists in the database.
    - If user exists and is active:
      - Invalidates any prior active reset challenges.
      - Generates a high-entropy 256-bit URL-safe token.
      - Stores only the SHA-256 hash with a 30-minute expiry.
      - Dispatches branded email via Resend with the single-use reset URL.
    - Never logs or exposes raw tokens or complete reset URLs.
    """
    password_reset_rate_limiter.check_forgot_password(request=http_req, email=request.email)
    email_clean = request.email.strip().lower()

    user = db.query(User).filter(User.email == email_clean).first()

    generic_response = ForgotPasswordResponse(
        message="If an account exists with that email address, password reset instructions have been sent."
    )

    if not user or not user.is_active:
        # Generic response for account enumeration mitigation
        return generic_response

    try:
        challenge, raw_token = create_password_reset_challenge(db=db, user=user)
        base_url = get_frontend_base_url(http_req)
        reset_url = f"{base_url}/reset-password?token={raw_token}"

        send_password_reset_email(to_email=user.email, reset_url=reset_url)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.error("Password reset email dispatch error: %s", type(exc).__name__)
        if settings.is_production:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Email delivery service is currently unavailable. Please try again later."
            )

    return generic_response


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    request: ResetPasswordRequest,
    http_req: Request,
    db: Session = Depends(get_db)
):
    """
    Public endpoint to complete a password reset:
    - Enforces rate limiting on token submission.
    - Validates token hash, expiry, single-use, and active user state.
    - Enforces minimum 8-character password strength.
    - Atomically consumes token (concurrency-safe against race conditions).
    - Hashes new password with Argon2id.
    - Does NOT modify email_verified or is_active (preserves OTP verification state).
    - Revokes all existing user sessions in AuthSession.
    - Invalidates all other active reset challenges for the user.
    """
    password_reset_rate_limiter.check_reset_password(request=http_req)

    # Validate and atomically consume token (raises 400 if invalid/expired/used)
    challenge, user = consume_password_reset_token(db=db, token=request.token)

    new_pwd = request.new_password.strip()
    if len(new_pwd) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters long"
        )

    if user.password_hash and verify_password(new_pwd, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from your current password"
        )

    # Securely hash new password with Argon2id
    user.password_hash = get_password_hash(new_pwd)

    # CRITICAL: Preserve email_verified and is_active (DO NOT alter)

    # Revoke all existing sessions for this user
    db.query(AuthSession).filter(
        AuthSession.user_id == user.id,
        AuthSession.is_revoked == False
    ).update({"is_revoked": True})

    # Invalidate any other active reset challenges for this user
    now = datetime.now(timezone.utc)
    db.query(PasswordResetChallenge).filter(
        PasswordResetChallenge.user_id == user.id,
        PasswordResetChallenge.used_at == None
    ).update({"used_at": now})

    db.commit()

    return ResetPasswordResponse(
        message="Your password has been successfully reset. You can now sign in with your new password."
    )
