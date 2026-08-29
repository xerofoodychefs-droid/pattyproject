import random
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, Body, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.loyalty import (
    LoyaltyAccount,
    LoyaltyTransaction,
    LoyaltyReward,
    LoyaltyProgramConfig,
    LoyaltyCampaign,
    LoyaltyMilestone
)
from app.api.endpoints.auth import get_current_user, require_role
from app.models.user import User, UserRole
from app.schemas.loyalty import (
    LoyaltyAccountOverviewResponse,
    LoyaltyTransactionResponse,
    LoyaltyRedeemRequest,
    LoyaltyRedeemResponse,
    LoyaltyProgramConfigResponse,
    LoyaltyProgramConfigUpdate,
    LoyaltyManualAdjustmentRequest,
    LoyaltyCampaignCreateRequest,
    LoyaltyCampaignUpdateRequest,
    LoyaltyCampaignResponse,
    LoyaltyMilestoneCreateRequest,
    LoyaltyMilestoneUpdateRequest,
    LoyaltyMilestoneResponse,
    LoyaltyMemberSummary,
    LoyaltyAnalyticsResponse
)
from app.services.loyalty_service import (
    get_or_create_loyalty_config,
    update_loyalty_config,
    get_customer_loyalty_overview,
    validate_and_redeem_points,
    manual_adjust_points,
    get_admin_loyalty_analytics,
    get_admin_loyalty_members,
    get_admin_loyalty_transactions,
    get_active_campaign,
    get_or_create_default_milestone
)

router = APIRouter()


# ============================================================
# 1. CUSTOMER LOYALTY ENDPOINTS
# ============================================================

@router.get("/balance", response_model=Dict[str, Any])
def get_customer_loyalty_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns authoritative loyalty overview for the logged-in customer:
    Current point balance, £ reward value (1000 pts = £1), progress towards 4,000 pts milestone,
    redemption eligibility, active campaigns, and immutable transaction ledger.
    """
    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Loyalty programme is only accessible to customers."
        )
    overview = get_customer_loyalty_overview(db, current_user.id)

    # Legacy rewards compatibility
    rewards = db.query(LoyaltyReward).filter(LoyaltyReward.is_active == True).order_by(LoyaltyReward.points_required.asc()).all()
    formatted_rewards = []
    for r in rewards:
        unlocked = overview["available_points"] >= r.points_required
        points_needed = max(0, r.points_required - overview["available_points"])
        formatted_rewards.append({
            "id": r.id,
            "title": r.title,
            "description": r.description,
            "points_required": r.points_required,
            "reward_type": r.reward_type,
            "discount_value": r.discount_value,
            "unlocked": unlocked,
            "points_needed": points_needed,
        })

    # Include backwards-compatible fields alongside the authoritative new overview
    overview["rewards"] = formatted_rewards
    overview["tier"] = "MEMBER"
    overview["next_tier_name"] = "First Reward (4,000 PTS)"
    overview["next_tier_points"] = overview["min_redemption_points"]
    overview["points_to_next_tier"] = overview["points_needed_for_redemption"]
    overview["progress_percent"] = overview["primary_milestone"]["progress_percent"]

    return overview


@router.post("/redeem")
def redeem_customer_loyalty_points(
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Server-side authoritative point redemption validation and deduction.
    Enforces whole 1,000-point increments and minimum 4,000-point milestone threshold.
    """
    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Loyalty programme is only accessible to customers."
        )

    config = get_or_create_loyalty_config(db)
    if not config.is_enabled:
        raise HTTPException(
            status_code=400,
            detail={"code": "LOYALTY_DISABLED", "message": "Loyalty rewards programme is currently paused."}
        )

    points_to_redeem = payload.get("points")
    reward_id = payload.get("reward_id")

    # Handle legacy reward_id if points not explicitly provided
    if points_to_redeem is None and reward_id:
        reward = db.query(LoyaltyReward).filter(LoyaltyReward.id == reward_id, LoyaltyReward.is_active == True).first()
        if not reward:
            raise HTTPException(status_code=404, detail="Milestone reward not found.")
        points_to_redeem = reward.points_required

    if not points_to_redeem or points_to_redeem <= 0:
        raise HTTPException(status_code=400, detail="Points to redeem must be specified.")

    if points_to_redeem < config.min_redemption_points:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "MINIMUM_REDEMPTION_REQUIRED",
                "message": f"Minimum {config.min_redemption_points:,} Patty Points required for reward redemption."
            }
        )

    if points_to_redeem % config.redemption_increment_points != 0:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_REDEMPTION_INCREMENT",
                "message": f"Points can only be redeemed in whole {config.redemption_increment_points:,}-point increments (£1 per 1,000 points)."
            }
        )

    ok, msg, tx = validate_and_redeem_points(
        db=db,
        user_id=current_user.id,
        points_to_redeem=points_to_redeem
    )

    if not ok:
        raise HTTPException(status_code=400, detail={"code": "INSUFFICIENT_POINTS", "message": msg})

    reward_value = points_to_redeem / float(config.points_per_pound_reward)
    promo_code = f"LOYALTY{random.randint(100, 999)}"

    return {
        "success": True,
        "message": f"Successfully redeemed {points_to_redeem:,} Patty Points for £{reward_value:.2f} reward discount!",
        "points_redeemed": points_to_redeem,
        "reward_value": reward_value,
        "coupon_code": promo_code,
        "remaining_points": tx.resulting_balance if tx else 0
    }


@router.get("/history", response_model=List[LoyaltyTransactionResponse])
def get_customer_loyalty_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns immutable loyalty transaction history for the logged-in customer."""
    if current_user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Loyalty programme is only accessible to customers."
        )
    account = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == current_user.id).first()
    if not account:
        return []
    return db.query(LoyaltyTransaction).filter(
        LoyaltyTransaction.loyalty_account_id == account.id
    ).order_by(LoyaltyTransaction.created_at.desc()).all()


@router.get("/campaigns", response_model=List[LoyaltyCampaignResponse])
def list_active_loyalty_campaigns(db: Session = Depends(get_db)):
    """Returns currently active promotional campaigns for customer visibility."""
    return db.query(LoyaltyCampaign).filter(LoyaltyCampaign.is_active == True).all()


@router.get("/milestones", response_model=List[LoyaltyMilestoneResponse])
def list_active_loyalty_milestones(db: Session = Depends(get_db)):
    """Returns loyalty milestones (including authoritative 4,000-point first redemption milestone)."""
    get_or_create_default_milestone(db)
    return db.query(LoyaltyMilestone).filter(LoyaltyMilestone.is_active == True).order_by(LoyaltyMilestone.points_required.asc()).all()


# ============================================================
# 2. ADMIN LOYALTY CONTROLS & MANAGEMENT (Super Admin Only)
# ============================================================

@router.get("/admin/config", response_model=LoyaltyProgramConfigResponse)
def get_admin_loyalty_config(
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Retrieves authoritative loyalty programme configuration."""
    return get_or_create_loyalty_config(db)


@router.put("/admin/config", response_model=LoyaltyProgramConfigResponse)
def update_admin_loyalty_config(
    payload: LoyaltyProgramConfigUpdate,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Updates loyalty programme parameters with Save & Publish persistence to PostgreSQL."""
    return update_loyalty_config(
        db=db,
        is_enabled=payload.is_enabled,
        earning_rate_pence_per_point=payload.earning_rate_pence_per_point,
        points_per_pound_reward=payload.points_per_pound_reward,
        min_redemption_points=payload.min_redemption_points,
        redemption_increment_points=payload.redemption_increment_points,
        admin_email=current_user.email
    )


@router.get("/admin/stats", response_model=LoyaltyAnalyticsResponse)
def get_admin_loyalty_stats(
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Calculates overall loyalty programme analytics, liabilities, issued/redeemed totals."""
    return get_admin_loyalty_analytics(db)


@router.get("/admin/members", response_model=List[LoyaltyMemberSummary])
def get_admin_loyalty_members_list(
    search: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Search and paginate customer loyalty members."""
    return get_admin_loyalty_members(db=db, search=search, limit=limit, offset=offset)


@router.post("/admin/adjust-points", response_model=LoyaltyTransactionResponse)
def manual_points_adjustment(
    payload: LoyaltyManualAdjustmentRequest,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """
    Manually add or deduct points for a customer with MANDATORY audit reason and transaction recording.
    """
    target_user = db.query(User).filter(User.id == payload.user_id).first()
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
    if target_user.role != UserRole.CUSTOMER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Loyalty points can only be adjusted for customers."
        )

    try:
        tx = manual_adjust_points(
            db=db,
            user_id=payload.user_id,
            points_delta=payload.points_delta,
            reason=payload.reason,
            admin_user=current_user,
            admin_notes=payload.admin_notes
        )
        return tx
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/admin/transactions", response_model=List[LoyaltyTransactionResponse])
def get_admin_loyalty_ledger(
    type: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    order_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Fetches auditable immutable loyalty transactions ledger."""
    return get_admin_loyalty_transactions(
        db=db,
        tx_type=type,
        user_id=user_id,
        order_id=order_id,
        limit=limit,
        offset=offset
    )


# ============================================================
# 3. ADMIN CAMPAIGN MANAGEMENT (CRUD)
# ============================================================

@router.get("/admin/campaigns", response_model=List[LoyaltyCampaignResponse])
def get_admin_campaigns(
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Lists all loyalty campaigns."""
    return db.query(LoyaltyCampaign).order_by(LoyaltyCampaign.created_at.desc()).all()


@router.post("/admin/campaigns", response_model=LoyaltyCampaignResponse)
def create_admin_campaign(
    payload: LoyaltyCampaignCreateRequest,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Creates a new Double Points, Triple Points, Bonus Points, or Custom Multiplier campaign."""
    camp = LoyaltyCampaign(
        id=str(uuid.uuid4()),
        name=payload.name,
        campaign_type=payload.campaign_type.upper(),
        multiplier=payload.multiplier or 1.0,
        bonus_points=payload.bonus_points or 0,
        start_date=payload.start_date,
        end_date=payload.end_date,
        is_active=payload.is_active if payload.is_active is not None else True,
        eligible_products=payload.eligible_products,
        excluded_products=payload.excluded_products,
        eligible_categories=payload.eligible_categories,
        excluded_categories=payload.excluded_categories,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db.add(camp)
    db.commit()
    db.refresh(camp)
    return camp


@router.put("/admin/campaigns/{campaign_id}", response_model=LoyaltyCampaignResponse)
def update_admin_campaign(
    campaign_id: str,
    payload: LoyaltyCampaignUpdateRequest,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Updates an existing loyalty campaign."""
    camp = db.query(LoyaltyCampaign).filter(LoyaltyCampaign.id == campaign_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    if payload.name is not None:
        camp.name = payload.name
    if payload.campaign_type is not None:
        camp.campaign_type = payload.campaign_type.upper()
    if payload.multiplier is not None:
        camp.multiplier = payload.multiplier
    if payload.bonus_points is not None:
        camp.bonus_points = payload.bonus_points
    if payload.start_date is not None:
        camp.start_date = payload.start_date
    if payload.end_date is not None:
        camp.end_date = payload.end_date
    if payload.is_active is not None:
        camp.is_active = payload.is_active
    if payload.eligible_products is not None:
        camp.eligible_products = payload.eligible_products
    if payload.excluded_products is not None:
        camp.excluded_products = payload.excluded_products
    if payload.eligible_categories is not None:
        camp.eligible_categories = payload.eligible_categories
    if payload.excluded_categories is not None:
        camp.excluded_categories = payload.excluded_categories

    camp.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(camp)
    return camp


@router.delete("/admin/campaigns/{campaign_id}")
def delete_admin_campaign(
    campaign_id: str,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Deactivates/deletes a loyalty campaign."""
    camp = db.query(LoyaltyCampaign).filter(LoyaltyCampaign.id == campaign_id).first()
    if not camp:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    db.delete(camp)
    db.commit()
    return {"success": True, "message": "Campaign deleted successfully."}


# ============================================================
# 4. ADMIN MILESTONE MANAGEMENT (CRUD)
# ============================================================

@router.get("/admin/milestones", response_model=List[LoyaltyMilestoneResponse])
def get_admin_milestones(
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Lists all configurable milestones."""
    get_or_create_default_milestone(db)
    return db.query(LoyaltyMilestone).order_by(LoyaltyMilestone.points_required.asc()).all()


@router.post("/admin/milestones", response_model=LoyaltyMilestoneResponse)
def create_admin_milestone(
    payload: LoyaltyMilestoneCreateRequest,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Creates a new configurable milestone for future expansion."""
    m = LoyaltyMilestone(
        id=str(uuid.uuid4()),
        name=payload.name,
        points_required=payload.points_required,
        reward_type=payload.reward_type or "REWARD_DISCOUNT",
        reward_value=payload.reward_value or 4.0,
        description=payload.description,
        is_active=payload.is_active if payload.is_active is not None else True,
        start_date=payload.start_date,
        end_date=payload.end_date,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@router.put("/admin/milestones/{milestone_id}", response_model=LoyaltyMilestoneResponse)
def update_admin_milestone(
    milestone_id: str,
    payload: LoyaltyMilestoneUpdateRequest,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Updates a configurable milestone."""
    m = db.query(LoyaltyMilestone).filter(LoyaltyMilestone.id == milestone_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Milestone not found.")

    if payload.name is not None:
        m.name = payload.name
    if payload.points_required is not None:
        m.points_required = payload.points_required
    if payload.reward_type is not None:
        m.reward_type = payload.reward_type
    if payload.reward_value is not None:
        m.reward_value = payload.reward_value
    if payload.description is not None:
        m.description = payload.description
    if payload.is_active is not None:
        m.is_active = payload.is_active
    if payload.start_date is not None:
        m.start_date = payload.start_date
    if payload.end_date is not None:
        m.end_date = payload.end_date

    m.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(m)
    return m


@router.delete("/admin/milestones/{milestone_id}")
def delete_admin_milestone(
    milestone_id: str,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Deletes/deactivates a milestone."""
    m = db.query(LoyaltyMilestone).filter(LoyaltyMilestone.id == milestone_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Milestone not found.")
    db.delete(m)
    db.commit()
    return {"success": True, "message": "Milestone deleted successfully."}
