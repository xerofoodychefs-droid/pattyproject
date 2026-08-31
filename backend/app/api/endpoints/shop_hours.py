from typing import Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User, UserRole
from app.models.setting import ShopSetting
from app.api.endpoints.auth import get_current_user
from app.services.shop_hours_service import (
    parse_time_string,
    get_or_create_shop_settings,
    get_authoritative_shop_status,
    is_shop_open
)
from app.core.websocket_manager import manager

router = APIRouter()


class ShopStatusResponse(BaseModel):
    is_open: bool
    opening_time: str
    closing_time: str
    reason: str
    timezone: str
    current_uk_time: str
    updated_at: Optional[str] = None


class ShopSettingsResponse(BaseModel):
    id: str
    opening_time: str
    closing_time: str
    is_open: bool
    reason: str
    timezone: str
    updated_at: Optional[str] = None


class ShopSettingsUpdateRequest(BaseModel):
    opening_time: str = Field(..., description="Opening time in HH:MM format (24-hour)")
    closing_time: str = Field(..., description="Closing time in HH:MM format (24-hour)")

    @field_validator("opening_time", "closing_time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        clean = v.strip()
        t = parse_time_string(clean)
        if t is None:
            raise ValueError("Time must be in HH:MM 24-hour format (e.g. 11:00 or 23:00)")
        return f"{t.hour:02d}:{t.minute:02d}"


def require_super_admin(current_user: User = Depends(get_current_user)) -> User:
    """Strict authorization dependency ensuring only SUPER_ADMIN can manage global shop hours."""
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only Super Administrators are authorized to configure global shop opening hours."
        )
    return current_user


# -----------------------------------------------------------------------------
# Public Shop Availability Endpoint
# -----------------------------------------------------------------------------
@router.get("/status", response_model=ShopStatusResponse)
def get_shop_status(db: Session = Depends(get_db)):
    """
    Public read-only endpoint returning authoritative real-time shop open/closed status.
    Uses Europe/London timezone.
    """
    return get_authoritative_shop_status(db)


# -----------------------------------------------------------------------------
# Super Admin Shop Settings Endpoints
# -----------------------------------------------------------------------------
@router.get("/admin/settings", response_model=ShopSettingsResponse)
def get_admin_shop_settings(
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """
    Super Admin endpoint to inspect current global shop hours configuration and live open status.
    """
    setting = get_or_create_shop_settings(db)
    status_info = get_authoritative_shop_status(db)
    return ShopSettingsResponse(
        id=setting.id,
        opening_time=setting.opening_time,
        closing_time=setting.closing_time,
        is_open=status_info["is_open"],
        reason=status_info["reason"],
        timezone=status_info["timezone"],
        updated_at=setting.updated_at.isoformat() if setting.updated_at else None
    )


@router.patch("/admin/settings", response_model=ShopSettingsResponse)
def update_admin_shop_settings(
    payload: ShopSettingsUpdateRequest,
    current_user: User = Depends(require_super_admin),
    db: Session = Depends(get_db)
):
    """
    Super Admin endpoint to update global opening and closing times.
    - Validates HH:MM format.
    - Enforces opening_time != closing_time.
    - Persists settings in shop_settings.
    - Recalculates live open status.
    - Broadcasts real-time shop_status_changed event to all connected customers and admins.
    """
    if payload.opening_time == payload.closing_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Opening time and closing time cannot be identical."
        )

    setting = get_or_create_shop_settings(db)
    setting.opening_time = payload.opening_time
    setting.closing_time = payload.closing_time
    setting.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(setting)

    # Recalculate live status
    is_open, reason = is_shop_open(setting.opening_time, setting.closing_time)

    # Broadcast updated status immediately to all connected clients
    manager.sync_broadcast_shop_status(
        is_open=is_open,
        opening_time=setting.opening_time,
        closing_time=setting.closing_time,
        reason=reason
    )

    status_info = get_authoritative_shop_status(db)
    return ShopSettingsResponse(
        id=setting.id,
        opening_time=setting.opening_time,
        closing_time=setting.closing_time,
        is_open=status_info["is_open"],
        reason=status_info["reason"],
        timezone=status_info["timezone"],
        updated_at=setting.updated_at.isoformat() if setting.updated_at else None
    )
