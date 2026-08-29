from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


# ==========================================
# 1. CUSTOMER SCHEMAS
# ==========================================

class LoyaltyTransactionResponse(BaseModel):
    id: str
    points: int
    transaction_type: str
    description: Optional[str] = None
    order_id: Optional[str] = None
    campaign_id: Optional[str] = None
    resulting_balance: Optional[int] = None
    admin_email: Optional[str] = None
    created_at: Any

    class Config:
        from_attributes = True


class MilestoneProgressResponse(BaseModel):
    milestone_id: str
    milestone_name: str
    points_required: int
    points_needed: int
    is_unlocked: bool
    progress_percent: float
    reward_value: float
    description: Optional[str] = None


class LoyaltyAccountOverviewResponse(BaseModel):
    available_points: int
    lifetime_points: int
    total_redeemed_points: int
    total_reversed_points: int
    reward_value: float
    is_redemption_available: bool
    min_redemption_points: int
    points_needed_for_redemption: int
    max_redeemable_reward: float
    redeemable_increments: List[int]
    active_campaign: Optional[Dict[str, Any]] = None
    primary_milestone: MilestoneProgressResponse
    transactions: List[LoyaltyTransactionResponse] = []


class LoyaltyRedeemRequest(BaseModel):
    points: int = Field(..., ge=1000, description="Points to redeem in whole 1,000-point increments (min 4,000)")

    @field_validator("points")
    @classmethod
    def validate_increment(cls, v: int) -> int:
        if v < 4000:
            raise ValueError("Minimum 4,000 Patty Points required for redemption.")
        if v % 1000 != 0:
            raise ValueError("Redemption must be in whole 1,000-point increments (e.g. 4,000, 5,000, 6,000).")
        return v


class LoyaltyRedeemResponse(BaseModel):
    success: bool
    points_redeemed: int
    reward_value: float
    remaining_balance: int
    coupon_code: Optional[str] = None
    message: str


# ==========================================
# 2. ADMIN SCHEMAS & CONFIG
# ==========================================

class LoyaltyProgramConfigResponse(BaseModel):
    id: str
    is_enabled: bool
    earning_rate_pence_per_point: int
    points_per_pound_reward: int
    min_redemption_points: int
    redemption_increment_points: int
    updated_at: Optional[Any] = None
    updated_by: Optional[str] = None

    class Config:
        from_attributes = True


class LoyaltyProgramConfigUpdate(BaseModel):
    is_enabled: Optional[bool] = None
    earning_rate_pence_per_point: Optional[int] = Field(None, ge=1)
    points_per_pound_reward: Optional[int] = Field(None, ge=100)
    min_redemption_points: Optional[int] = Field(None, ge=1000)
    redemption_increment_points: Optional[int] = Field(None, ge=100)


class LoyaltyManualAdjustmentRequest(BaseModel):
    user_id: str
    points_delta: int = Field(..., description="Signed points amount (+100 for credit, -100 for debit)")
    reason: str = Field(..., min_length=3, max_length=255, description="Mandatory audit explanation for manual adjustment")
    admin_notes: Optional[str] = None

    @field_validator("points_delta")
    @classmethod
    def non_zero_delta(cls, v: int) -> int:
        if v == 0:
            raise ValueError("Points adjustment cannot be 0.")
        return v

    @field_validator("reason")
    @classmethod
    def non_empty_reason(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned or len(cleaned) < 3:
            raise ValueError("A meaningful mandatory reason (at least 3 characters) must be provided for manual point adjustments.")
        return cleaned


# ==========================================
# 3. CAMPAIGN SCHEMAS
# ==========================================

class LoyaltyCampaignCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    campaign_type: str = Field("DOUBLE_POINTS", description="DOUBLE_POINTS, TRIPLE_POINTS, BONUS_POINTS, MULTIPLIER")
    multiplier: Optional[float] = Field(2.0, ge=1.0, le=10.0)
    bonus_points: Optional[int] = Field(0, ge=0)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: Optional[bool] = True
    eligible_products: Optional[List[str]] = None
    excluded_products: Optional[List[str]] = None
    eligible_categories: Optional[List[str]] = None
    excluded_categories: Optional[List[str]] = None


class LoyaltyCampaignUpdateRequest(BaseModel):
    name: Optional[str] = None
    campaign_type: Optional[str] = None
    multiplier: Optional[float] = None
    bonus_points: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    is_active: Optional[bool] = None
    eligible_products: Optional[List[str]] = None
    excluded_products: Optional[List[str]] = None
    eligible_categories: Optional[List[str]] = None
    excluded_categories: Optional[List[str]] = None


class LoyaltyCampaignResponse(BaseModel):
    id: str
    name: str
    campaign_type: str
    multiplier: float
    bonus_points: int
    start_date: Optional[Any] = None
    end_date: Optional[Any] = None
    is_active: bool
    eligible_products: Optional[List[str]] = None
    excluded_products: Optional[List[str]] = None
    eligible_categories: Optional[List[str]] = None
    excluded_categories: Optional[List[str]] = None
    created_at: Any
    updated_at: Optional[Any] = None

    class Config:
        from_attributes = True


# ==========================================
# 4. MILESTONE SCHEMAS
# ==========================================

class LoyaltyMilestoneCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    points_required: int = Field(4000, ge=1000)
    reward_type: Optional[str] = "REWARD_DISCOUNT"
    reward_value: Optional[float] = Field(4.0, ge=0.0)
    description: Optional[str] = None
    is_active: Optional[bool] = True
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class LoyaltyMilestoneUpdateRequest(BaseModel):
    name: Optional[str] = None
    points_required: Optional[int] = None
    reward_type: Optional[str] = None
    reward_value: Optional[float] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class LoyaltyMilestoneResponse(BaseModel):
    id: str
    name: str
    points_required: int
    reward_type: str
    reward_value: float
    description: Optional[str] = None
    is_active: bool
    start_date: Optional[Any] = None
    end_date: Optional[Any] = None
    created_at: Any
    updated_at: Optional[Any] = None

    class Config:
        from_attributes = True


# ==========================================
# 5. ADMIN ANALYTICS & MEMBER SUMMARIES
# ==========================================

class LoyaltyMemberSummary(BaseModel):
    user_id: str
    full_name: str
    email: str
    phone: Optional[str] = None
    role: Optional[str] = None
    available_points: int
    lifetime_points: int
    total_redeemed: int
    total_reversed: int
    reward_value: float
    is_redemption_eligible: bool
    created_at: Any


class LoyaltyAnalyticsResponse(BaseModel):
    total_members: int
    total_active_points: int
    total_points_issued: int
    total_points_redeemed: int
    total_points_reversed: int
    total_reward_value_issued: float
    total_reward_value_redeemed: float
    total_outstanding_liability_pounds: float
    active_campaigns_count: int
    is_programme_active: bool
