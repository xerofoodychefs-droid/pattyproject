from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.models.product import Product, ProductModifier, ProductChoiceGroup, ProductChoiceOption
from app.models.promotion import Coupon
from app.models.loyalty import LoyaltyReward
from app.services.loyalty_service import calculate_eligible_spend_and_points, get_or_create_loyalty_config

# Canonical delivery minimum merchandise threshold
MINIMUM_DELIVERY_SUBTOTAL = Decimal("15.00")


def is_delivery_eligible_by_subtotal(
    subtotal: Decimal,
    has_valid_promotion: bool
) -> Tuple[bool, Decimal]:
    """
    Evaluates delivery eligibility based on cart merchandise subtotal and promotions:
    - Normal cart: subtotal >= €15.00 -> Delivery ALLOWED
    - Normal cart: subtotal < €15.00 -> Delivery BLOCKED
    - Offer / Coupon Exception: If a valid offer/coupon is applied, delivery remains ALLOWED
      even if the discount causes the final payable cart amount to fall below €15.00.
    """
    if has_valid_promotion:
        return True, Decimal("0.00")
    if subtotal >= MINIMUM_DELIVERY_SUBTOTAL:
        return True, Decimal("0.00")
    shortfall = MINIMUM_DELIVERY_SUBTOTAL - subtotal
    return False, shortfall


def calculate_order_totals(
    db: Session,
    items: List[Dict[str, Any]],
    order_type: str = "DELIVERY",
    coupon_code: Optional[str] = None,
    redeem_reward_id: Optional[str] = None,
    redeem_points: Optional[int] = None
) -> Dict[str, Any]:
    """
    Authoritative server-side price calculator.
    Recalculates product prices, add-on modifiers, coupons, loyalty points redemption,
    delivery fees, and VAT.
    Enforces the €15.00 minimum delivery threshold and offer/coupon exemption.
    Authoritatively calculates Patty Points earning (1p = 1pt with active campaign multipliers).
    """
    subtotal = 0.0
    item_breakdown = []

    for item in items:
        product_id = item.get("product_id")
        quantity = max(1, int(item.get("quantity", 1)))
        
        product = db.query(Product).filter(Product.id == product_id, Product.is_active == True).first()
        if not product:
            continue

        unit_price = product.base_price
        modifier_details = []

        # Add modifier costs
        selected_mods = item.get("selected_modifiers", [])
        for mod_input in selected_mods:
            mod_name = mod_input.get("name") if isinstance(mod_input, dict) else str(mod_input)
            db_mod = db.query(ProductModifier).filter(
                ProductModifier.product_id == product.id,
                ProductModifier.name == mod_name,
                ProductModifier.is_active == True
            ).first()
            if db_mod:
                unit_price += db_mod.price
                modifier_details.append({"name": db_mod.name, "price": db_mod.price})
            else:
                modifier_details.append({"name": mod_name, "price": 0.0})

        # Validate choice groups and compute choice price delta
        choice_details = []
        selected_choices_input = item.get("selected_choices", []) or []

        db_groups = db.query(ProductChoiceGroup).filter(
            ProductChoiceGroup.product_id == product.id
        ).order_by(ProductChoiceGroup.display_order.asc()).all()

        for grp in db_groups:
            # Find submitted choices for this group
            grp_choices = [
                c for c in selected_choices_input
                if isinstance(c, dict) and (
                    c.get("group_id") == grp.id or
                    c.get("group_name", "").strip().lower() == grp.name.strip().lower()
                )
            ]
            count = len(grp_choices)
            if (grp.is_required and count < grp.min_selections) or (count > 0 and count < grp.min_selections):
                if grp.min_selections == grp.max_selections:
                    msg = f"Please select exactly {grp.min_selections} items for {grp.name}."
                else:
                    msg = f"Please select at least {grp.min_selections} items for {grp.name}."
                raise HTTPException(status_code=400, detail=msg)
            if count > grp.max_selections:
                msg = f"You can select at most {grp.max_selections} items for {grp.name}."
                raise HTTPException(status_code=400, detail=msg)

            # Prevent duplicate option submissions within the same choice group
            opt_identifiers = [
                (c.get("option_id") or c.get("id") or c.get("option_name") or c.get("name"))
                for c in grp_choices
                if (c.get("option_id") or c.get("id") or c.get("option_name") or c.get("name"))
            ]
            if len(opt_identifiers) != len(set(opt_identifiers)):
                raise HTTPException(status_code=400, detail=f"Duplicate choices are not permitted for {grp.name}.")

            for c_input in grp_choices:
                opt_id = c_input.get("option_id") or c_input.get("id")
                opt_name = c_input.get("option_name") or c_input.get("name")

                query_opt = db.query(ProductChoiceOption).filter(
                    ProductChoiceOption.group_id == grp.id,
                    ProductChoiceOption.is_active == True
                )
                if opt_id:
                    db_opt = query_opt.filter(ProductChoiceOption.id == opt_id).first()
                else:
                    db_opt = query_opt.filter(ProductChoiceOption.name == opt_name).first()

                if not db_opt:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Selected choice '{opt_name or opt_id}' in '{grp.name}' is invalid or unavailable."
                    )

                unit_price += db_opt.price_delta
                choice_details.append({
                    "group_id": grp.id,
                    "group_name": grp.name,
                    "option_id": db_opt.id,
                    "option_name": db_opt.name,
                    "price_delta": db_opt.price_delta
                })

        line_total = round(unit_price * quantity, 2)
        subtotal += line_total

        item_breakdown.append({
            "product_id": product.id,
            "product_name": product.name,
            "quantity": quantity,
            "unit_price": round(unit_price, 2),
            "total_price": line_total,
            "selected_modifiers": modifier_details,
            "selected_choices": choice_details
        })

    subtotal = round(subtotal, 2)
    subtotal_decimal = Decimal(str(subtotal))
    discount_amount = 0.0
    is_coupon_applied = False
    is_reward_applied = False
    loyalty_points_redeemed = 0

    # Patty Project delivery is FREE (£0.00). Radius & subtotal are eligibility checks.
    delivery_fee = 0.0
    service_fee = 0.0

    # 1. Apply Coupon Discount if valid
    if coupon_code:
        coupon = db.query(Coupon).filter(
            Coupon.code == coupon_code.upper(),
            Coupon.is_active == True
        ).first()
        if coupon and subtotal >= coupon.min_order_value:
            if coupon.coupon_type == "PERCENTAGE":
                discount_amount = round(subtotal * (coupon.discount_value / 100.0), 2)
                is_coupon_applied = (discount_amount > 0)
            elif coupon.coupon_type == "FIXED_AMOUNT":
                discount_amount = min(subtotal, coupon.discount_value)
                is_coupon_applied = (discount_amount > 0)
            elif coupon.coupon_type == "FREE_SHIPPING":
                delivery_fee = 0.0
                is_coupon_applied = True

    # 2. Apply Whole-1000 Increment Loyalty Points Redemption (Authoritative 1,000 pts = £1)
    if redeem_points and redeem_points >= 4000 and redeem_points % 1000 == 0:
        config = get_or_create_loyalty_config(db)
        if config.is_enabled:
            loyalty_discount_value = redeem_points / float(config.points_per_pound_reward)
            # Cap loyalty discount so subtotal doesn't become negative
            applicable_loyalty_discount = min(max(0.0, subtotal - discount_amount), loyalty_discount_value)
            discount_amount = round(discount_amount + applicable_loyalty_discount, 2)
            loyalty_points_redeemed = redeem_points
            if applicable_loyalty_discount > 0:
                is_reward_applied = True

    # 3. Apply Legacy Milestone Reward Item (Backwards-compatibility)
    if redeem_reward_id:
        reward = db.query(LoyaltyReward).filter(LoyaltyReward.id == redeem_reward_id, LoyaltyReward.is_active == True).first()
        if reward and reward.reward_type == "FREE_ITEM" and reward.product_id:
            target_prod = db.query(Product).filter(Product.id == reward.product_id).first()
            if target_prod:
                reward_discount = min(subtotal - discount_amount, target_prod.base_price)
                discount_amount = round(discount_amount + reward_discount, 2)
                if reward_discount > 0:
                    is_reward_applied = True

    has_valid_promotion = is_coupon_applied or is_reward_applied or (discount_amount > 0)
    discount_amount = min(subtotal, round(discount_amount, 2))
    gross_amount = max(0.0, round(subtotal - discount_amount, 2))
    vat_amount = round(gross_amount * 20.0 / 120.0, 2)  # Standard 20% UK VAT extracted from VAT-inclusive gross
    net_amount = round(gross_amount - vat_amount, 2)    # Deterministic reconciliation: net_amount + vat_amount == gross_amount

    total_amount = round(gross_amount + delivery_fee + service_fee, 2)

    # 4. Authoritative server-side points calculation (1p = 1 pt with campaign multipliers)
    spend_calc = calculate_eligible_spend_and_points(
        db=db,
        items=item_breakdown,
        subtotal=subtotal,
        discount_amount=discount_amount
    )
    points_earned = spend_calc["points_earned"]

    is_delivery_allowed, delivery_shortfall = is_delivery_eligible_by_subtotal(
        subtotal=subtotal_decimal,
        has_valid_promotion=has_valid_promotion
    )

    return {
        "subtotal": subtotal,
        "delivery_fee": delivery_fee,
        "service_fee": service_fee,
        "discount_amount": discount_amount,
        "gross_amount": gross_amount,
        "net_amount": net_amount,
        "vat_amount": vat_amount,
        "total_amount": total_amount,
        "points_earned": points_earned,
        "points_redeemed": loyalty_points_redeemed,
        "campaign_multiplier": spend_calc.get("multiplier", 1.0),
        "campaign_id": spend_calc.get("campaign_id"),
        "is_promotion_applied": has_valid_promotion,
        "is_delivery_subtotal_eligible": is_delivery_allowed,
        "min_delivery_subtotal": float(MINIMUM_DELIVERY_SUBTOTAL),
        "delivery_shortfall": float(delivery_shortfall),
        "items": item_breakdown
    }
