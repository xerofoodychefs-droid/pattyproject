import math
import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.models.loyalty import (
    LoyaltyAccount,
    LoyaltyTransaction,
    LoyaltyProgramConfig,
    LoyaltyCampaign,
    LoyaltyMilestone
)
from app.models.user import User, UserRole
from app.models.order import Order, OrderStatus, PaymentStatus

logger = logging.getLogger("pattyproject.loyalty")

# ==========================================
# 1. PROGRAM CONFIGURATION SERVICE
# ==========================================

def get_or_create_loyalty_config(db: Session) -> LoyaltyProgramConfig:
    """Fetches the singleton loyalty program configuration or initializes defaults."""
    config = db.query(LoyaltyProgramConfig).first()
    if not config:
        config = LoyaltyProgramConfig(
            id=str(uuid.uuid4()),
            is_enabled=True,
            earning_rate_pence_per_point=1,     # 1p = 1 point (£1 = 100 points)
            points_per_pound_reward=1000,       # 1,000 points = £1 reward (10% reward rate)
            min_redemption_points=4000,         # Minimum 4,000 points (£4 reward)
            redemption_increment_points=1000,   # Whole 1,000 point increments (£1)
            updated_at=datetime.now(timezone.utc),
            updated_by="SYSTEM"
        )
        db.add(config)
        db.commit()
        db.refresh(config)
    return config


def update_loyalty_config(
    db: Session,
    is_enabled: Optional[bool] = None,
    earning_rate_pence_per_point: Optional[int] = None,
    points_per_pound_reward: Optional[int] = None,
    min_redemption_points: Optional[int] = None,
    redemption_increment_points: Optional[int] = None,
    admin_email: Optional[str] = None
) -> LoyaltyProgramConfig:
    """Updates loyalty programme parameters and persists them to PostgreSQL."""
    config = get_or_create_loyalty_config(db)

    if is_enabled is not None:
        config.is_enabled = is_enabled
    if earning_rate_pence_per_point is not None and earning_rate_pence_per_point >= 1:
        config.earning_rate_pence_per_point = earning_rate_pence_per_point
    if points_per_pound_reward is not None and points_per_pound_reward >= 100:
        config.points_per_pound_reward = points_per_pound_reward
    if min_redemption_points is not None and min_redemption_points >= 1000:
        config.min_redemption_points = min_redemption_points
    if redemption_increment_points is not None and redemption_increment_points >= 100:
        config.redemption_increment_points = redemption_increment_points

    config.updated_at = datetime.now(timezone.utc)
    config.updated_by = admin_email or "SUPER_ADMIN"

    db.commit()
    db.refresh(config)
    logger.info(f"Loyalty configuration updated by {config.updated_by}. Enabled={config.is_enabled}")
    return config


# ==========================================
# 2. CAMPAIGNS & MULTIPLIERS ENGINE
# ==========================================

def get_active_campaign(db: Session, at_time: Optional[datetime] = None) -> Optional[LoyaltyCampaign]:
    """Finds currently running and active point multiplier/bonus campaign."""
    now = at_time or datetime.now(timezone.utc)
    # Filter active campaigns
    campaigns = db.query(LoyaltyCampaign).filter(LoyaltyCampaign.is_active == True).all()
    for camp in campaigns:
        if camp.start_date:
            start_tz = camp.start_date.replace(tzinfo=timezone.utc) if camp.start_date.tzinfo is None else camp.start_date
            if now < start_tz:
                continue
        if camp.end_date:
            end_tz = camp.end_date.replace(tzinfo=timezone.utc) if camp.end_date.tzinfo is None else camp.end_date
            if now > end_tz:
                continue
        return camp
    return None


def calculate_eligible_spend_and_points(
    db: Session,
    items: List[Dict[str, Any]],
    subtotal: float,
    discount_amount: float = 0.0,
    order_time: Optional[datetime] = None
) -> Dict[str, Any]:
    """
    Authoritative server-side calculation for loyalty points earning.
    Rules:
    - 1p eligible customer spend = 1 Patty Point (£1 = 100 points).
    - Delivery fee and service fee are excluded.
    - Non-merchandise discounts & loyalty redemptions reduce eligible spend.
    - Check active campaigns (Double Points 2x, Triple Points 3x, Bonus).
    """
    config = get_or_create_loyalty_config(db)
    if not config.is_enabled:
        return {
            "eligible_spend_pence": 0,
            "eligible_spend_pounds": 0.0,
            "base_points": 0,
            "points_earned": 0,
            "multiplier": 1.0,
            "bonus_points": 0,
            "campaign_id": None,
            "campaign_name": None
        }

    # Net eligible merchandise spend = subtotal - discount_amount
    net_eligible_amount = max(0.0, subtotal - discount_amount)
    eligible_pence = int(round(Decimal(str(net_eligible_amount)) * 100))

    # Base points: 1p = 1 point / earning_rate_pence_per_point
    rate = max(1, config.earning_rate_pence_per_point)
    base_points = eligible_pence // rate

    active_camp = get_active_campaign(db, at_time=order_time)
    multiplier = 1.0
    bonus = 0
    camp_id = None
    camp_name = None

    if active_camp:
        camp_id = active_camp.id
        camp_name = active_camp.name
        if active_camp.campaign_type == "DOUBLE_POINTS":
            multiplier = 2.0
        elif active_camp.campaign_type == "TRIPLE_POINTS":
            multiplier = 3.0
        elif active_camp.campaign_type == "BONUS_POINTS":
            bonus = active_camp.bonus_points or 0
        elif active_camp.campaign_type == "MULTIPLIER":
            multiplier = active_camp.multiplier or 1.0

    points_earned = int(round(base_points * multiplier)) + bonus

    return {
        "eligible_spend_pence": eligible_pence,
        "eligible_spend_pounds": float(round(Decimal(str(net_eligible_amount)), 2)),
        "base_points": base_points,
        "points_earned": points_earned,
        "multiplier": multiplier,
        "bonus_points": bonus,
        "campaign_id": camp_id,
        "campaign_name": camp_name
    }


# ==========================================
# 3. POINT AWARDING & IDEMPOTENCY
# ==========================================

def get_or_create_loyalty_account(db: Session, user_id: str) -> LoyaltyAccount:
    """Finds or initializes a customer loyalty account safely."""
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.role != UserRole.CUSTOMER:
        raise ValueError(f"Loyalty accounts can only be created for customers. User role is {user.role}.")

    loyalty = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == user_id).first()
    if not loyalty:
        loyalty = LoyaltyAccount(
            id=str(uuid.uuid4()),
            user_id=user_id,
            available_points=0,
            lifetime_points=0,
            tier="BRONZE",
            created_at=datetime.now(timezone.utc)
        )
        db.add(loyalty)
        db.flush()
    return loyalty


def award_order_loyalty_points(db: Session, order: Order) -> Optional[LoyaltyTransaction]:
    """
    Authoritative point awarding upon successfully completed / paid order.
    Enforces strict idempotency: identical order will never be awarded twice.
    """
    config = get_or_create_loyalty_config(db)
    if not config.is_enabled:
        logger.info(f"Loyalty programme is disabled. Skipping point award for Order {order.order_number}.")
        return None

    # Idempotency check: Don't award if already awarded for this order
    existing_tx = db.query(LoyaltyTransaction).filter(
        LoyaltyTransaction.order_id == order.id,
        LoyaltyTransaction.transaction_type.in_(["EARN", "DOUBLE_POINTS", "TRIPLE_POINTS", "BONUS", "EARNED"])
    ).first()
    if existing_tx:
        logger.info(f"Points already awarded for Order {order.order_number} (Tx {existing_tx.id}).")
        return existing_tx

    # Resolve user - LOYALTY IS CUSTOMER-ONLY
    user = None
    if order.customer_id:
        user = db.query(User).filter(User.id == order.customer_id).first()
    elif order.customer_email:
        user = db.query(User).filter(User.email == order.customer_email.strip().lower()).first()

    if not user or user.role != UserRole.CUSTOMER:
        logger.info(f"No registered customer found for Order {order.order_number} or user is not a customer. Skipping loyalty award.")
        return None

    loyalty = get_or_create_loyalty_account(db, user.id)

    # Determine points to award
    pts_to_award = order.points_earned if (order.points_earned and order.points_earned > 0) else None
    if pts_to_award is None:
        calc = calculate_eligible_spend_and_points(
            db=db,
            items=[],
            subtotal=order.subtotal,
            discount_amount=order.discount_amount,
            order_time=order.created_at
        )
        pts_to_award = calc["points_earned"]
        order.points_earned = pts_to_award

    if pts_to_award <= 0:
        return None

    # Determine transaction type based on active campaign
    active_camp = get_active_campaign(db, at_time=order.created_at)
    tx_type = "EARN"
    camp_id = None
    if active_camp:
        camp_id = active_camp.id
        if active_camp.campaign_type == "DOUBLE_POINTS":
            tx_type = "DOUBLE_POINTS"
        elif active_camp.campaign_type == "TRIPLE_POINTS":
            tx_type = "TRIPLE_POINTS"
        elif active_camp.campaign_type == "BONUS_POINTS":
            tx_type = "BONUS"

    loyalty.available_points += pts_to_award
    loyalty.lifetime_points += pts_to_award

    tx = LoyaltyTransaction(
        id=str(uuid.uuid4()),
        loyalty_account_id=loyalty.id,
        order_id=order.id,
        campaign_id=camp_id,
        points=pts_to_award,
        transaction_type=tx_type,
        description=f"Points earned from Order {order.order_number}",
        resulting_balance=loyalty.available_points,
        metadata_json={
            "order_number": order.order_number,
            "order_total": order.total_amount,
            "subtotal": order.subtotal,
            "discount_amount": order.discount_amount
        },
        created_at=datetime.now(timezone.utc)
    )
    db.add(tx)
    db.commit()
    db.refresh(loyalty)
    logger.info(f"Awarded {pts_to_award} Patty Points to User {user.email} for Order {order.order_number}. New Balance: {loyalty.available_points}")
    return tx


# ==========================================
# 4. REFUNDS, REVERSALS & REDEMPTION RESTORATION
# ==========================================

def reverse_order_loyalty_points(
    db: Session,
    order: Order,
    refund_amount: Optional[float] = None,
    reason: Optional[str] = None
) -> Optional[LoyaltyTransaction]:
    """
    Reverses loyalty points for full or partial refunds.
    Full refund: reverses all earned points for the order.
    Partial refund: reverses proportional points based on refunded eligible amount.
    """
    user = None
    if order.customer_id:
        user = db.query(User).filter(User.id == order.customer_id).first()
    elif order.customer_email:
        user = db.query(User).filter(User.email == order.customer_email.strip().lower()).first()

    if not user or user.role != UserRole.CUSTOMER:
        return None

    loyalty = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == user.id).first()
    if not loyalty:
        return None

    # Find points originally awarded for this order
    earn_txs = db.query(LoyaltyTransaction).filter(
        LoyaltyTransaction.order_id == order.id,
        LoyaltyTransaction.points > 0,
        LoyaltyTransaction.transaction_type.in_(["EARN", "DOUBLE_POINTS", "TRIPLE_POINTS", "BONUS", "EARNED"])
    ).all()
    total_earned_on_order = sum(t.points for t in earn_txs)

    if total_earned_on_order <= 0:
        return None

    # Find points already reversed for this order
    prev_reversals = db.query(LoyaltyTransaction).filter(
        LoyaltyTransaction.order_id == order.id,
        LoyaltyTransaction.points < 0,
        LoyaltyTransaction.transaction_type.in_(["REVERSE", "REFUND_ADJUSTMENT", "REVERSED"])
    ).all()
    total_already_reversed = abs(sum(t.points for t in prev_reversals))

    net_points_eligible_for_reversal = max(0, total_earned_on_order - total_already_reversed)
    if net_points_eligible_for_reversal <= 0:
        logger.info(f"Points for Order {order.order_number} already fully reversed.")
        return None

    # Calculate points to reverse
    if refund_amount is not None and refund_amount > 0 and order.total_amount > 0:
        # Partial refund proportional calculation
        proportion = Decimal(str(refund_amount)) / Decimal(str(order.total_amount))
        pts_to_reverse = int(round(Decimal(str(total_earned_on_order)) * proportion))
        pts_to_reverse = min(pts_to_reverse, net_points_eligible_for_reversal)
        tx_type = "REFUND_ADJUSTMENT"
    else:
        # Full refund
        pts_to_reverse = net_points_eligible_for_reversal
        tx_type = "REVERSE"

    if pts_to_reverse <= 0:
        return None

    # Deduct points from balance
    loyalty.available_points = max(0, loyalty.available_points - pts_to_reverse)
    loyalty.lifetime_points = max(0, loyalty.lifetime_points - pts_to_reverse)

    tx = LoyaltyTransaction(
        id=str(uuid.uuid4()),
        loyalty_account_id=loyalty.id,
        order_id=order.id,
        points=-pts_to_reverse,
        transaction_type=tx_type,
        description=f"Reversed points for refund on Order {order.order_number}: {reason or 'Order refund'}",
        resulting_balance=loyalty.available_points,
        metadata_json={
            "order_number": order.order_number,
            "refund_amount": refund_amount,
            "reason": reason
        },
        created_at=datetime.now(timezone.utc)
    )
    db.add(tx)
    db.commit()
    db.refresh(loyalty)
    logger.info(f"Reversed {pts_to_reverse} points for Order {order.order_number}. New balance: {loyalty.available_points}")
    return tx


def restore_redeemed_loyalty_points(
    db: Session,
    order: Order,
    reason: Optional[str] = None
) -> Optional[LoyaltyTransaction]:
    """
    Restores points that were redeemed on an order when that order is cancelled or refunded.
    Ensures idempotency: points are restored at most once.
    """
    if not order.points_redeemed or order.points_redeemed <= 0:
        return None

    user = None
    if order.customer_id:
        user = db.query(User).filter(User.id == order.customer_id).first()
    elif order.customer_email:
        user = db.query(User).filter(User.email == order.customer_email.strip().lower()).first()

    if not user or user.role != UserRole.CUSTOMER:
        return None

    loyalty = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == user.id).first()
    if not loyalty:
        return None

    # Check if restoration already occurred for this order
    existing_restoration = db.query(LoyaltyTransaction).filter(
        LoyaltyTransaction.order_id == order.id,
        LoyaltyTransaction.points > 0,
        LoyaltyTransaction.transaction_type.in_(["REVERSE", "REFUND_ADJUSTMENT"])
    ).first()
    if existing_restoration:
        logger.info(f"Redeemed points for Order {order.order_number} already restored (Tx {existing_restoration.id}).")
        return existing_restoration

    pts_to_restore = order.points_redeemed
    loyalty.available_points += pts_to_restore

    tx = LoyaltyTransaction(
        id=str(uuid.uuid4()),
        loyalty_account_id=loyalty.id,
        order_id=order.id,
        points=pts_to_restore,
        transaction_type="REVERSE",
        description=f"Restored {pts_to_restore} redeemed points from cancelled/refunded Order {order.order_number}",
        resulting_balance=loyalty.available_points,
        metadata_json={
            "order_number": order.order_number,
            "restored_points": pts_to_restore,
            "reason": reason or "Order cancelled / refunded"
        },
        created_at=datetime.now(timezone.utc)
    )
    db.add(tx)
    db.commit()
    db.refresh(loyalty)
    logger.info(f"Restored {pts_to_restore} redeemed points for User {user.email} from Order {order.order_number}. New balance: {loyalty.available_points}")
    return tx


# ==========================================
# 5. REDEMPTION ENGINE
# ==========================================

def validate_and_redeem_points(
    db: Session,
    user_id: str,
    points_to_redeem: int,
    order_id: Optional[str] = None
) -> Tuple[bool, str, Optional[LoyaltyTransaction]]:
    """
    Server-side authoritative validator and processor for point redemptions.
    Enforces:
    - Programme enabled
    - Customer owns the points
    - Minimum threshold (4,000 points)
    - Whole 1,000-point increments only
    - Balance sufficiency
    """
    config = get_or_create_loyalty_config(db)
    if not config.is_enabled:
        return False, "Loyalty rewards programme is currently paused.", None

    if points_to_redeem < config.min_redemption_points:
        return False, f"Minimum {config.min_redemption_points:,} Patty Points required to redeem rewards.", None

    if points_to_redeem % config.redemption_increment_points != 0:
        return False, f"Redemptions must be in whole {config.redemption_increment_points:,}-point increments.", None

    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.role != UserRole.CUSTOMER:
        return False, "Loyalty rewards can only be redeemed by customers.", None

    account = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == user_id).first()
    if not account:
        return False, "Loyalty account not found.", None

    if account.available_points < points_to_redeem:
        return False, f"Insufficient points balance. You have {account.available_points:,} points but tried to redeem {points_to_redeem:,}.", None

    # Deduct points
    account.available_points -= points_to_redeem
    reward_pounds = points_to_redeem / config.points_per_pound_reward

    tx = LoyaltyTransaction(
        id=str(uuid.uuid4()),
        loyalty_account_id=account.id,
        order_id=order_id,
        points=-points_to_redeem,
        transaction_type="REDEEM",
        description=f"Redeemed {points_to_redeem:,} Patty Points for £{reward_pounds:.2f} reward discount",
        resulting_balance=account.available_points,
        metadata_json={
            "points_redeemed": points_to_redeem,
            "reward_value": reward_pounds,
            "order_id": order_id
        },
        created_at=datetime.now(timezone.utc)
    )
    db.add(tx)
    db.commit()
    db.refresh(account)
    logger.info(f"Redeemed {points_to_redeem} points for User {user_id}. Remaining balance: {account.available_points}")
    return True, f"Successfully redeemed {points_to_redeem:,} Patty Points for £{reward_pounds:.2f} reward.", tx


# ==========================================
# 6. ADMIN MANUAL ADJUSTMENTS & AUDIT
# ==========================================

def manual_adjust_points(
    db: Session,
    user_id: str,
    points_delta: int,
    reason: str,
    admin_user: User,
    admin_notes: Optional[str] = None
) -> LoyaltyTransaction:
    """
    Applies manual credit or debit to customer balance with MANDATORY reason and auditable record.
    """
    if points_delta == 0:
        raise ValueError("Points adjustment cannot be zero.")

    clean_reason = reason.strip() if reason else ""
    if not clean_reason or len(clean_reason) < 3:
        raise ValueError("A mandatory audit reason (at least 3 characters) is required for manual point adjustments.")

    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise ValueError("User not found.")
    if target_user.role != UserRole.CUSTOMER:
        raise ValueError("Loyalty points can only be managed for customers.")

    loyalty = get_or_create_loyalty_account(db, user_id)

    # Check for debit exceeding available points
    if points_delta < 0 and loyalty.available_points + points_delta < 0:
        raise ValueError(
            f"Cannot debit {abs(points_delta):,} points. Customer only has {loyalty.available_points:,} points available."
        )

    loyalty.available_points += points_delta
    if points_delta > 0:
        loyalty.lifetime_points += points_delta

    tx_type = "MANUAL_CREDIT" if points_delta > 0 else "MANUAL_DEBIT"
    action_word = "Added" if points_delta > 0 else "Deducted"

    tx = LoyaltyTransaction(
        id=str(uuid.uuid4()),
        loyalty_account_id=loyalty.id,
        admin_id=admin_user.id,
        admin_email=admin_user.email,
        points=points_delta,
        transaction_type=tx_type,
        description=f"Admin {action_word} {abs(points_delta):,} points: {clean_reason}",
        resulting_balance=loyalty.available_points,
        metadata_json={
            "reason": clean_reason,
            "admin_notes": admin_notes,
            "admin_email": admin_user.email,
            "admin_id": admin_user.id,
            "adjusted_at": datetime.now(timezone.utc).isoformat()
        },
        created_at=datetime.now(timezone.utc)
    )
    db.add(tx)
    db.commit()
    db.refresh(loyalty)
    logger.info(f"Admin {admin_user.email} adjusted points for User {user_id} by {points_delta}. Reason: {clean_reason}")
    return tx


# ==========================================
# 7. CUSTOMER OVERVIEW & MILESTONES
# ==========================================

def get_or_create_default_milestone(db: Session) -> LoyaltyMilestone:
    """Ensures the primary 4,000-point First Redemption Milestone exists in PostgreSQL."""
    m = db.query(LoyaltyMilestone).filter(LoyaltyMilestone.points_required == 4000).first()
    if not m:
        m = LoyaltyMilestone(
            id=str(uuid.uuid4()),
            name="First Redemption Milestone",
            points_required=4000,
            reward_type="REWARD_DISCOUNT",
            reward_value=4.0,
            description="Unlock your first £4.00 loyalty reward at 4,000 Patty Points.",
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        db.add(m)
        db.commit()
        db.refresh(m)
    return m


def get_customer_loyalty_overview(db: Session, user_id: str) -> Dict[str, Any]:
    """
    Computes real-time customer loyalty overview, progress towards 4,000 pts milestone,
    available whole-£1 increments, and ledger history.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if user and user.role != UserRole.CUSTOMER:
        raise ValueError("Loyalty overview is only available for customers.")

    config = get_or_create_loyalty_config(db)
    loyalty = get_or_create_loyalty_account(db, user_id)
    primary_milestone = get_or_create_default_milestone(db)

    # Calculate points statistics from ledger
    transactions = db.query(LoyaltyTransaction).filter(
        LoyaltyTransaction.loyalty_account_id == loyalty.id
    ).order_by(LoyaltyTransaction.created_at.desc()).all()

    total_redeemed = sum(abs(t.points) for t in transactions if t.points < 0 and t.transaction_type in ["REDEEM", "REDEEMED"])
    total_reversed = sum(abs(t.points) for t in transactions if t.points < 0 and t.transaction_type in ["REVERSE", "REFUND_ADJUSTMENT", "REVERSED"])

    # Reward values
    available_pts = loyalty.available_points
    reward_value = round(available_pts / Decimal(str(config.points_per_pound_reward)), 2)

    # Primary milestone progress
    req = primary_milestone.points_required
    points_needed = max(0, req - available_pts)
    is_unlocked = available_pts >= req
    progress_percent = min(100.0, round((available_pts / req) * 100, 1)) if req > 0 else 100.0

    # Max redeemable whole-1000 increments
    redeemable_increments = []
    if is_unlocked and config.is_enabled:
        max_thousands = available_pts // config.redemption_increment_points
        start_thousands = config.min_redemption_points // config.redemption_increment_points
        for k in range(start_thousands, max_thousands + 1):
            redeemable_increments.append(k * config.redemption_increment_points)

    max_redeemable_reward = float((available_pts // config.redemption_increment_points) * (config.redemption_increment_points / config.points_per_pound_reward)) if is_unlocked else 0.0

    active_camp = get_active_campaign(db)
    active_camp_dict = None
    if active_camp:
        active_camp_dict = {
            "id": active_camp.id,
            "name": active_camp.name,
            "campaign_type": active_camp.campaign_type,
            "multiplier": active_camp.multiplier,
            "bonus_points": active_camp.bonus_points
        }

    return {
        "available_points": available_pts,
        "lifetime_points": loyalty.lifetime_points,
        "total_redeemed_points": total_redeemed,
        "total_reversed_points": total_reversed,
        "reward_value": float(reward_value),
        "is_redemption_available": is_unlocked and config.is_enabled,
        "min_redemption_points": config.min_redemption_points,
        "points_needed_for_redemption": points_needed,
        "max_redeemable_reward": max_redeemable_reward,
        "redeemable_increments": redeemable_increments,
        "active_campaign": active_camp_dict,
        "primary_milestone": {
            "milestone_id": primary_milestone.id,
            "milestone_name": primary_milestone.name,
            "points_required": primary_milestone.points_required,
            "points_needed": points_needed,
            "is_unlocked": is_unlocked,
            "progress_percent": progress_percent,
            "reward_value": primary_milestone.reward_value or 4.0,
            "description": primary_milestone.description
        },
        "transactions": [
            {
                "id": t.id,
                "points": t.points,
                "transaction_type": t.transaction_type,
                "description": t.description,
                "order_id": t.order_id,
                "campaign_id": t.campaign_id,
                "resulting_balance": t.resulting_balance,
                "admin_email": t.admin_email,
                "created_at": t.created_at.isoformat() if t.created_at else None
            }
            for t in transactions[:25]
        ]
    }


# ==========================================
# 8. ADMIN ANALYTICS & MEMBER MANAGEMENT
# ==========================================

def get_admin_loyalty_analytics(db: Session) -> Dict[str, Any]:
    """Calculates overall loyalty programme KPI metrics and liability for CUSTOMER accounts only."""
    config = get_or_create_loyalty_config(db)

    # Restrict strictly to CUSTOMER role accounts
    customer_accounts = (
        db.query(LoyaltyAccount)
        .join(User, LoyaltyAccount.user_id == User.id)
        .filter(func.upper(User.role) == UserRole.CUSTOMER)
    )

    total_members = customer_accounts.count()
    total_active_points = customer_accounts.with_entities(
        func.coalesce(func.sum(LoyaltyAccount.available_points), 0)
    ).scalar() or 0
    total_points_issued = customer_accounts.with_entities(
        func.coalesce(func.sum(LoyaltyAccount.lifetime_points), 0)
    ).scalar() or 0

    # Restrict transactions strictly to CUSTOMER accounts
    customer_txs = (
        db.query(LoyaltyTransaction)
        .join(LoyaltyAccount, LoyaltyTransaction.loyalty_account_id == LoyaltyAccount.id)
        .join(User, LoyaltyAccount.user_id == User.id)
        .filter(func.upper(User.role) == UserRole.CUSTOMER)
        .all()
    )
    total_redeemed = sum(abs(t.points) for t in customer_txs if t.points < 0 and t.transaction_type in ["REDEEM", "REDEEMED"])
    total_reversed = sum(abs(t.points) for t in customer_txs if t.points < 0 and t.transaction_type in ["REVERSE", "REFUND_ADJUSTMENT", "REVERSED"])

    pts_per_pound = max(1, config.points_per_pound_reward)
    outstanding_liability = round(total_active_points / pts_per_pound, 2)
    reward_issued = round(total_points_issued / pts_per_pound, 2)
    reward_redeemed = round(total_redeemed / pts_per_pound, 2)

    active_campaigns_count = db.query(LoyaltyCampaign).filter(LoyaltyCampaign.is_active == True).count()

    return {
        "total_members": total_members,
        "total_active_points": total_active_points,
        "total_points_issued": total_points_issued,
        "total_points_redeemed": total_redeemed,
        "total_points_reversed": total_reversed,
        "total_reward_value_issued": float(reward_issued),
        "total_reward_value_redeemed": float(reward_redeemed),
        "total_outstanding_liability_pounds": float(outstanding_liability),
        "active_campaigns_count": active_campaigns_count,
        "is_programme_active": config.is_enabled
    }


def get_admin_loyalty_members(
    db: Session,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Returns list of customer loyalty accounts with search and calculated statistics, strictly CUSTOMER-only."""
    config = get_or_create_loyalty_config(db)
    query = (
        db.query(LoyaltyAccount)
        .join(User, LoyaltyAccount.user_id == User.id)
        .filter(func.upper(User.role) == UserRole.CUSTOMER)
    )

    if search and search.strip():
        term = f"%{search.strip().lower()}%"
        query = query.filter(
            or_(
                func.lower(User.full_name).like(term),
                func.lower(User.email).like(term),
                func.lower(User.phone).like(term)
            )
        )

    accounts = query.order_by(LoyaltyAccount.available_points.desc()).offset(offset).limit(limit).all()

    results = []
    for acc in accounts:
        user = acc.user
        txs = acc.transactions or []
        total_redeemed = sum(abs(t.points) for t in txs if t.points < 0 and t.transaction_type in ["REDEEM", "REDEEMED"])
        total_reversed = sum(abs(t.points) for t in txs if t.points < 0 and t.transaction_type in ["REVERSE", "REFUND_ADJUSTMENT", "REVERSED"])
        reward_val = round(acc.available_points / config.points_per_pound_reward, 2)

        results.append({
            "user_id": acc.user_id,
            "full_name": user.full_name if user else "Unknown Customer",
            "email": user.email if user else "",
            "phone": user.phone if user else None,
            "role": user.role if user else UserRole.CUSTOMER,
            "available_points": acc.available_points,
            "lifetime_points": acc.lifetime_points,
            "total_redeemed": total_redeemed,
            "total_reversed": total_reversed,
            "reward_value": float(reward_val),
            "is_redemption_eligible": acc.available_points >= config.min_redemption_points,
            "created_at": acc.created_at
        })

    return results


def get_admin_loyalty_transactions(
    db: Session,
    tx_type: Optional[str] = None,
    user_id: Optional[str] = None,
    order_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[LoyaltyTransaction]:
    """Retrieves immutable loyalty transactions ledger with filters for CUSTOMER accounts only."""
    query = (
        db.query(LoyaltyTransaction)
        .join(LoyaltyAccount, LoyaltyTransaction.loyalty_account_id == LoyaltyAccount.id)
        .join(User, LoyaltyAccount.user_id == User.id)
        .filter(func.upper(User.role) == UserRole.CUSTOMER)
    )

    if tx_type and tx_type != "ALL":
        query = query.filter(LoyaltyTransaction.transaction_type == tx_type.upper())
    if user_id:
        query = query.filter(LoyaltyAccount.user_id == user_id)
    if order_id:
        query = query.filter(LoyaltyTransaction.order_id == order_id)

    return query.order_by(LoyaltyTransaction.created_at.desc()).offset(offset).limit(limit).all()
