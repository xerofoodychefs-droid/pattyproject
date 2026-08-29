import re
from pydantic import BaseModel, EmailStr, Field, field_validator


class ContactFormRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100, description="Customer first name")
    last_name: str = Field(..., min_length=1, max_length=100, description="Customer last name")
    email: EmailStr = Field(..., max_length=255, description="Customer email address")
    subject: str = Field(..., min_length=1, max_length=200, description="Subject of the message")
    message: str = Field(..., min_length=1, max_length=5000, description="Message content")

    @field_validator("first_name", "last_name", "message", mode="before")
    @classmethod
    def validate_non_empty_stripped(cls, v: str) -> str:
        if isinstance(v, str):
            stripped = v.strip()
            if not stripped:
                raise ValueError("Field cannot be empty or whitespace only")
            return stripped
        return v

    @field_validator("subject", mode="before")
    @classmethod
    def validate_subject_sanitized(cls, v: str) -> str:
        if isinstance(v, str):
            # Strip and sanitize newlines to prevent header injection
            cleaned = re.sub(r"[\r\n]+", " ", v).strip()
            if not cleaned:
                raise ValueError("Subject cannot be empty or whitespace only")
            return cleaned
        return v

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        if isinstance(v, str):
            cleaned = v.strip().lower()
            if not cleaned:
                raise ValueError("Email cannot be empty")
            return cleaned
        return v


class ContactFormResponse(BaseModel):
    message: str = "Your message has been sent successfully."
