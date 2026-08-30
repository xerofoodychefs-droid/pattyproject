from datetime import datetime, time, timezone
from typing import Optional, Tuple, List, Dict, Any
from zoneinfo import ZoneInfo
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, selectinload

from app.models.product import Category, Product, Inventory

UK_TZ = ZoneInfo("Europe/London")


def parse_time_string(time_str: Optional[str]) -> Optional[time]:
    """Parses HH:MM string into a time object."""
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


def is_category_schedule_open(category: Optional[Category], at_dt: Optional[datetime] = None) -> bool:
    """
    Authoritative single-source-of-truth UK category schedule evaluator.
    - Category must be active.
    - If schedule_enabled is False: returns True (unrestricted availability).
    - If schedule times are unconfigured: returns True.
    - Evaluates UK local wall-clock time (Europe/London) handling GMT/BST automatically.
    - Uses half-open interval [start, end) for daytime schedules (start < end):
        start_time <= current_time < end_time
    - Handles overnight schedules crossing midnight (start > end):
        current_time >= start_time OR current_time < end_time
    - Equal start and end (start == end): returns False.
    """
    if category is None:
        return True

    if not category.is_active:
        return False

    if not getattr(category, "schedule_enabled", False):
        return True

    start_str = getattr(category, "schedule_start_time", None)
    end_str = getattr(category, "schedule_end_time", None)

    start_t = parse_time_string(start_str)
    end_t = parse_time_string(end_str)

    if start_t is None or end_t is None:
        return True

    # Equal start and end times cannot be open
    if start_t == end_t:
        return False

    # Resolve UK datetime
    if at_dt is None:
        dt_uk = datetime.now(UK_TZ)
    elif at_dt.tzinfo is None:
        dt_uk = at_dt.replace(tzinfo=UK_TZ)
    else:
        dt_uk = at_dt.astimezone(UK_TZ)

    curr_t = dt_uk.time()

    # Standard daytime interval: e.g. 08:00 -> 12:00
    if start_t < end_t:
        return start_t <= curr_t < end_t

    # Overnight interval crossing midnight: e.g. 18:00 -> 02:00
    return curr_t >= start_t or curr_t < end_t


def get_category_schedule_status(category: Optional[Category], at_dt: Optional[datetime] = None) -> str:
    """
    Returns the dynamic schedule status string:
    - 'DISABLED': schedule_enabled is False
    - 'OPEN': category schedule is currently open
    - 'CLOSED': category schedule is currently closed
    """
    if category is None or not getattr(category, "schedule_enabled", False):
        return "DISABLED"

    if is_category_schedule_open(category, at_dt=at_dt):
        return "OPEN"

    return "CLOSED"


def is_product_effective_available(
    product: Product,
    branch_id: Optional[str] = None,
    db: Optional[Session] = None,
    at_dt: Optional[datetime] = None
) -> Tuple[bool, Optional[str]]:
    """
    Determines effective product availability combining:
    1. Product active state
    2. Manual out-of-stock state
    3. Category active state
    4. Category schedule open state (Europe/London)
    5. Branch inventory availability (if branch_id and db provided)
    Never mutates physical stock or product records.
    """
    if not product.is_active:
        return False, "Product is inactive"

    if getattr(product, "is_out_of_stock", False):
        return False, f"'{product.name}' is out of stock"

    cat = getattr(product, "category", None)
    if cat is not None:
        if not cat.is_active:
            return False, f"Category '{cat.name}' is inactive"
        if not is_category_schedule_open(cat, at_dt=at_dt):
            start_str = getattr(cat, "schedule_start_time", "00:00")
            end_str = getattr(cat, "schedule_end_time", "00:00")
            return (
                False,
                f"This item is currently unavailable because its category ('{cat.name}') is outside its serving hours ({start_str} - {end_str})."
            )

    if branch_id and branch_id != "ALL" and db is not None:
        inv = db.query(Inventory).filter(
            Inventory.branch_id == branch_id,
            Inventory.product_id == product.id
        ).first()
        if inv is not None:
            if not inv.is_available or (inv.stock_quantity is not None and inv.stock_quantity <= 0):
                return False, f"'{product.name}' is out of stock at selected branch"

    return True, None


def validate_order_items_availability(
    db: Session,
    items: List[Dict[str, Any]],
    branch_id: Optional[str] = None,
    at_dt: Optional[datetime] = None
) -> None:
    """
    Authoritative server-side pre-order / pre-cart validation:
    Validates that all line item products exist, are active, not out of stock,
    and belong to an active category whose schedule is currently OPEN in Europe/London.
    Raises HTTPException(status_code=400) on any violation.
    """
    if not items:
        raise HTTPException(status_code=400, detail="Cart contains no items.")

    for item in items:
        prod_id = item.get("product_id")
        if not prod_id:
            raise HTTPException(status_code=400, detail="Invalid item: missing product_id.")

        product = db.query(Product).options(
            selectinload(Product.category)
        ).filter(Product.id == prod_id).first()

        if not product or not product.is_active:
            raise HTTPException(status_code=400, detail=f"Product '{prod_id}' not found or inactive.")

        is_avail, reason = is_product_effective_available(
            product=product,
            branch_id=branch_id,
            db=db,
            at_dt=at_dt
        )
        if not is_avail:
            raise HTTPException(status_code=400, detail=reason or f"Item '{product.name}' is currently unavailable.")
