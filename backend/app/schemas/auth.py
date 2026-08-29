from typing import Optional, List
import re
from pydantic import BaseModel, EmailStr, field_validator


class Token(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "bearer"
    user: "UserResponse"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    phone: Optional[str] = None
    password: str


class RegistrationResponse(BaseModel):
    message: str
    email: str
    requires_verification: bool = True


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    otp: str

    @field_validator("otp")
    @classmethod
    def validate_otp_format(cls, v: str) -> str:
        v_clean = v.strip()
        if not re.fullmatch(r"^\d{6}$", v_clean):
            raise ValueError("OTP must be exactly 6 numeric digits.")
        return v_clean


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class SocialLoginRequest(BaseModel):
    provider: str  # google, apple
    email: EmailStr
    full_name: Optional[str] = None
    provider_user_id: Optional[str] = None


class GoogleAuthRequest(BaseModel):
    id_token: str
    state_token: str


class GoogleNonceResponse(BaseModel):
    nonce: str
    state_token: str


class GoogleConfigResponse(BaseModel):
    client_id: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    phone: Optional[str] = None
    role: str
    is_active: bool
    email_verified: bool = False
    branch_ids: List[str] = []

    class Config:
        from_attributes = True


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


Token.model_rebuild()
