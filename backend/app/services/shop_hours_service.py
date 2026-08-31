from datetime import datetime, time, timezone
from typing import Optional, Tuple, Dict, Any
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.setting import ShopSetting

UK_TZ = ZoneInfo("Europe/London")


def parse_time_string(time_str: Optional[str]) -> Optional[time]:
    """Parses HH:MM 24-hour string into a time object."""
    if not time_str:
        return None
    clean = time_str.strip()
    try:
        parts = clean.split(":")
        if len(parts) != 2:
            return None
        hour, minute = int(parts[0]), int(parts[1])
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return time(hour, minute, 0)
    except (ValueError, TypeError):
        return None
    return None


def is_shop_open(
    opening_time_str: Optional[str],
    closing_time_str: Optional[str],
    at_dt: Optional[datetime] = None
) -> Tuple[bool, str]:
    """
    Authoritative evaluation of global shop open/closed status.
    - Evaluates UK local wall-clock time (Europe/London) handling GMT/BST automatically.
    - Standard daytime interval (start < end):
        start_time <= current_time < end_time
    - Overnight interval crossing midnight (start > end):
        current_time >= start_time OR current_time < end_time
    - Equal opening and closing times (start == end): returns (False, "INVALID_HOURS").
    """
    start_t = parse_time_string(opening_time_str)
    end_t = parse_time_string(closing_time_str)

    if start_t is None or end_t is None:
        return False, "INVALID_HOURS"

    if start_t == end_t:
        return False, "INVALID_HOURS"

    # Resolve UK datetime
    if at_dt is None:
        dt_uk = datetime.now(UK_TZ)
    elif at_dt.tzinfo is None:
        dt_uk = at_dt.replace(tzinfo=UK_TZ)
    else:
        dt_uk = at_dt.astimezone(UK_TZ)

    curr_t = dt_uk.time()

    # Standard daytime interval: e.g. 11:00 -> 23:00
    if start_t < end_t:
        if start_t <= curr_t < end_t:
            return True, "OPEN"
        return False, "OUTSIDE_HOURS"

    # Overnight interval crossing midnight: e.g. 18:00 -> 02:00
    if curr_t >= start_t or curr_t < end_t:
        return True, "OPEN"
    return False, "OUTSIDE_HOURS"


def get_or_create_shop_settings(db: Session) -> ShopSetting:
    """Retrieves or initializes the singleton global ShopSetting row."""
    setting = db.query(ShopSetting).filter(ShopSetting.key == "global").first()
    if setting:
        return setting

    try:
        new_setting = ShopSetting(
            key="global",
            opening_time="11:00",
            closing_time="23:00"
        )
        db.add(new_setting)
        db.commit()
        db.refresh(new_setting)
        return new_setting
    except IntegrityError:
        db.rollback()
        winning_setting = db.query(ShopSetting).filter(ShopSetting.key == "global").first()
        if winning_setting:
            return winning_setting
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to initialize shop settings"
        )


def get_authoritative_shop_status(
    db: Session,
    at_dt: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Computes current authoritative shop status dictionary.
    Safe for public consumption.
    """
    setting = get_or_create_shop_settings(db)
    is_open, reason = is_shop_open(
        opening_time_str=setting.opening_time,
        closing_time_str=setting.closing_time,
        at_dt=at_dt
    )

    if at_dt is None:
        dt_uk = datetime.now(UK_TZ)
    elif at_dt.tzinfo is None:
        dt_uk = at_dt.replace(tzinfo=UK_TZ)
    else:
        dt_uk = at_dt.astimezone(UK_TZ)

    return {
        "is_open": is_open,
        "opening_time": setting.opening_time,
        "closing_time": setting.closing_time,
        "reason": reason,
        "timezone": "Europe/London",
        "current_uk_time": dt_uk.strftime("%H:%M"),
        "updated_at": setting.updated_at.isoformat() if setting.updated_at else None
    }


def validate_shop_open_for_ordering(
    db: Session,
    at_dt: Optional[datetime] = None
) -> None:
    """
    Enforces that the shop is currently open for ordering.
    Raises HTTPException(status_code=400) if the shop is closed.
    """
    status_info = get_authoritative_shop_status(db, at_dt=at_dt)
    if not status_info["is_open"]:
        open_t = status_info.get("opening_time", "11:00")
        close_t = status_info.get("closing_time", "23:00")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The shop is currently closed. Ordering is available during our opening hours ({open_t} - {close_t})."
        )
