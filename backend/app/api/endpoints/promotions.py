from typing import List, Dict, Any, Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Response
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from app.core.database import get_db
from app.models.promotion import Coupon, OfferSetting
from app.models.product import Category, Product, ProductModifier
from app.schemas.promotion import CouponCreateRequest, CouponResponse
from app.api.endpoints.auth import require_role
from app.models.user import UserRole, User

router = APIRouter()

PUBLIC_CACHE_CONTROL = "public, max-age=60, s-maxage=300, stale-while-revalidate=600"

DEFAULT_TODAYS_OFFERS: Dict[str, Any] = {
    "section_title": "TODAY'S OFFERS",
    "view_all_link": "/offers",
    "view_all_text": "VIEW ALL OFFERS",
    "cards": [
        {
            "id": "card-1",
            "title": "BURGER COMBO",
            "subtitle": "Burger + Fries + Drink",
            "badge": "SAVE 15%",
            "image_url": "https://images.unsplash.com/photo-1550547660-d9450f859349?auto=format&fit=crop&w=500&q=80",
            "bg_image": "offer_bg_1.png",
            "link_url": "/order"
        },
        {
            "id": "card-2",
            "title": "WING WEDNESDAY",
            "subtitle": "On All Wings",
            "badge": "20% OFF",
            "image_url": "https://images.unsplash.com/photo-1527477396000-e27163b481c2?auto=format&fit=crop&w=500&q=80",
            "bg_image": "offer_bg_2.png",
            "link_url": "/order"
        },
        {
            "id": "card-3",
            "title": "STUDENT OFFER",
            "subtitle": "On All Orders",
            "badge": "10% OFF",
            "badge_type": "id_badge",
            "image_url": "",
            "bg_image": "offer_bg_3.png",
            "link_url": "/order"
        }
    ]
}

DEFAULT_OFFERS_PAGE: Dict[str, Any] = {
    "banner": {
        "tagline": "EXCLUSIVE OFFERS",
        "headline_main": "DEALS THAT",
        "headline_highlight": "HIT DIFFERENT.",
        "description": "Handpicked combos, limited-time treats and exclusive perks crafted to make your meal even better.",
        "image_url": "/offers_combo_banner.png"
    },
    "offers": [
        {
            "id": "combo",
            "category": ["combos", "burgers"],
            "title": "BURGER COMBO",
            "tag": "BURGER + FRIES + DRINK",
            "tagIcon": "utensils",
            "badge": "SAVE 15%",
            "code": "COMBO15",
            "image": "/product_the_mc_project.png",
            "description": "Get our signature double smash burger served with seasoned skin-on fries and any cold drink of your choice."
        },
        {
            "id": "family",
            "category": ["combos", "burgers", "sides"],
            "title": "PATTY FEAST (FEEDS 4)",
            "tag": "4 BURGERS + 2 FRIES + 4 DRINKS",
            "tagIcon": "utensils",
            "badge": "POPULAR",
            "code": "FEAST20",
            "image": "/product_the_outlaw_project_.png",
            "description": "The ultimate burger party box! Includes 4 classic smash burgers, 2 large rosemary salt fries, and 4 refreshing drinks."
        },
        {
            "id": "lunch",
            "category": ["limited", "burgers"],
            "title": "LUNCH SPECIAL",
            "tag": "MON - FRI, 12PM - 4PM",
            "tagIcon": "clock",
            "badge": "£5.99 ONLY",
            "code": "LUNCH599",
            "image": "/product_pastrami_burger_.png",
            "description": "Quick lunch win! Single smash patty burger or crispy chicken sandwich with skin-on fries for just £5.99."
        },
        {
            "id": "shake",
            "category": ["drinks", "limited"],
            "title": "FREE SHAKE UPGRADE",
            "tag": "WITH ANY BURGER & FRIES ORDER",
            "tagIcon": "gift",
            "badge": "LIMITED TIME",
            "code": "SHAKEUP",
            "image": "https://images.unsplash.com/photo-1572490122747-3968b75cc699?auto=format&fit=crop&w=600&q=80",
            "description": "Upgrade your soft drink to any handmade gourmet milkshake for free when you order a burger and sides."
        }
    ]
}

DEFAULT_COMBO_DEALS: Dict[str, Any] = {
    "combos": []
}

def sync_combo_deals_to_products(db: Session, combos: List[Dict[str, Any]]):
    """Ensures Combo Offers category exists and syncs combo products so customers can directly order them from the menu."""
    try:
        combo_cat = db.query(Category).filter(
            (Category.slug == "combo-offers") | (Category.slug == "combos") | (Category.name == "Combo Offers")
        ).first()
        
        if not combo_cat:
            combo_cat = Category(
                name="Combo Offers",
                slug="combo-offers",
                icon="utensils",
                display_order=0,
                is_active=True
            )
            db.add(combo_cat)
            db.flush()
        else:
            if not combo_cat.is_active:
                combo_cat.is_active = True
                db.flush()

        active_skus = set()
        active_names = set()

        for item in combos:
            c_id = item.get("id") or f"combo-{uuid.uuid4().hex[:8]}"
            name = (item.get("name") or item.get("title") or "Combo Offer").strip()
            base_price = float(item.get("base_price", item.get("price", 9.99)))
            compare_at_price = float(item.get("compare_at_price")) if item.get("compare_at_price") else None
            short_desc = item.get("description") or item.get("subtitle") or "Special meal combo"
            image_url = (item.get("image_url") or item.get("image") or "").strip() or None
            ingredients = item.get("ingredients")
            if isinstance(ingredients, list):
                ingredients = ", ".join(ingredients)
            is_active = item.get("is_active", True)
            
            sku_code = f"COMBO-{item.get('id', name.replace(' ', '-').upper())}"
            active_skus.add(sku_code)
            active_names.add(name.lower())

            prod = db.query(Product).filter((Product.sku == sku_code) | (Product.name == name)).first()
            
            if not prod:
                prod = Product(
                    category_id=combo_cat.id,
                    name=name,
                    sku=sku_code,
                    short_description=short_desc,
                    full_description=short_desc,
                    ingredients=ingredients,
                    base_price=base_price,
                    compare_at_price=compare_at_price,
                    image_url=image_url,
                    images=[image_url] if image_url else [],
                    is_active=is_active,
                    is_bestseller=True
                )
                db.add(prod)
                db.flush()
            else:
                prod.category_id = combo_cat.id
                prod.name = name
                prod.sku = sku_code
                prod.short_description = short_desc
                prod.full_description = short_desc
                prod.ingredients = ingredients
                prod.base_price = base_price
                prod.compare_at_price = compare_at_price
                prod.image_url = image_url
                prod.images = [image_url] if image_url else []
                prod.is_active = is_active
                db.flush()

            mods = item.get("modifiers", [])
            if isinstance(mods, list):
                db.query(ProductModifier).filter(ProductModifier.product_id == prod.id).delete()
                for m in mods:
                    if isinstance(m, dict) and m.get("name"):
                        db.add(ProductModifier(
                            product_id=prod.id,
                            name=m["name"],
                            price=float(m.get("price", 0.0)),
                            is_active=True
                        ))

        # Deactivate any combo products that were removed from the combo list
        existing_combos = db.query(Product).filter(Product.category_id == combo_cat.id).all()
        for ec in existing_combos:
            if ec.sku not in active_skus and ec.name.lower() not in active_names:
                ec.is_active = False

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error syncing combo deals: {e}")

FALLBACK_OFFER_CODES: Dict[str, Dict[str, Any]] = {
    "COMBO15": {
        "name": "Burger Combo Discount",
        "description": "15% OFF on burger combos & meals",
        "coupon_type": "PERCENTAGE",
        "discount_value": 15.0,
        "min_order_value": 10.0,
        "badge": "15% OFF"
    },
    "FEAST20": {
        "name": "Party Feast Discount",
        "description": "20% OFF on family & party bundle orders",
        "coupon_type": "PERCENTAGE",
        "discount_value": 20.0,
        "min_order_value": 20.0,
        "badge": "20% OFF"
    },
    "PATTY10": {
        "name": "10% Off Everything",
        "description": "Save 10% on your entire food order",
        "coupon_type": "PERCENTAGE",
        "discount_value": 10.0,
        "min_order_value": 5.0,
        "badge": "10% OFF"
    },
    "WELCOME20": {
        "name": "Welcome New Customer",
        "description": "20% OFF your first Patty Project order",
        "coupon_type": "PERCENTAGE",
        "discount_value": 20.0,
        "min_order_value": 12.0,
        "badge": "WELCOME DEAL"
    },
    "LUNCH599": {
        "name": "Lunch Special Saver",
        "description": "Save £3.00 on quick lunch orders",
        "coupon_type": "FIXED_AMOUNT",
        "discount_value": 3.0,
        "min_order_value": 8.0,
        "badge": "£3.00 OFF"
    },
    "SHAKEUP": {
        "name": "Free Shake Upgrade Deal",
        "description": "Save £3.50 with burger & sides shake upgrade",
        "coupon_type": "FIXED_AMOUNT",
        "discount_value": 3.5,
        "min_order_value": 10.0,
        "badge": "FREE SHAKE"
    }
}

@router.get("/validate")
def validate_coupon(code: str = Query(...), subtotal: float = Query(...), db: Session = Depends(get_db)):
    """Validates coupon code against current subtotal."""
    clean_code = code.strip().upper()
    coupon = db.query(Coupon).filter(Coupon.code == clean_code, Coupon.is_active == True).first()
    
    if coupon:
        if subtotal < coupon.min_order_value:
            raise HTTPException(status_code=400, detail=f"Code requires minimum order of £{coupon.min_order_value:.2f}")

        if coupon.used_count >= coupon.usage_limit:
            raise HTTPException(status_code=400, detail="Coupon usage limit reached")

        discount = 0.0
        if coupon.coupon_type == "PERCENTAGE":
            discount = round(subtotal * (coupon.discount_value / 100.0), 2)
        elif coupon.coupon_type == "FIXED_AMOUNT":
            discount = min(float(coupon.discount_value), subtotal)

        return {
            "valid": True,
            "code": coupon.code,
            "discount_amount": discount,
            "calculated_discount": discount,
            "coupon_type": coupon.coupon_type,
            "discount_value": coupon.discount_value,
            "message": f"Promo code '{coupon.code}' applied! Saved £{discount:.2f}"
        }

    # Fallback to configured offer codes
    if clean_code in FALLBACK_OFFER_CODES:
        info = FALLBACK_OFFER_CODES[clean_code]
        if subtotal < info["min_order_value"]:
            raise HTTPException(status_code=400, detail=f"Code requires minimum order of £{info['min_order_value']:.2f}")

        discount = 0.0
        if info["coupon_type"] == "PERCENTAGE":
            discount = round(subtotal * (info["discount_value"] / 100.0), 2)
        elif info["coupon_type"] == "FIXED_AMOUNT":
            discount = min(float(info["discount_value"]), subtotal)

        return {
            "valid": True,
            "code": clean_code,
            "discount_amount": discount,
            "calculated_discount": discount,
            "coupon_type": info["coupon_type"],
            "discount_value": info["discount_value"],
            "message": f"Promo code '{clean_code}' applied! Saved £{discount:.2f}"
        }

    raise HTTPException(status_code=400, detail="Invalid or expired promo code")

@router.get("/available")
def get_available_coupons(response: Response, db: Session = Depends(get_db)):
    """Returns list of available promo codes with description, code and discount for customer cart display."""
    response.headers["Cache-Control"] = PUBLIC_CACHE_CONTROL
    db_coupons = db.query(Coupon).filter(Coupon.is_active == True).all()
    results = []
    seen = set()

    for c in db_coupons:
        seen.add(c.code.upper())
        results.append({
            "code": c.code,
            "name": c.name,
            "description": f"{c.discount_value}% OFF on all eligible items" if c.coupon_type == "PERCENTAGE" else f"£{c.discount_value:.2f} OFF your order",
            "coupon_type": c.coupon_type,
            "discount_value": c.discount_value,
            "min_order_value": c.min_order_value,
            "badge": f"{int(c.discount_value)}% OFF" if c.coupon_type == "PERCENTAGE" else f"£{c.discount_value:.2f} OFF"
        })

    for code, info in FALLBACK_OFFER_CODES.items():
        if code not in seen:
            results.append({
                "code": code,
                "name": info["name"],
                "description": info["description"],
                "coupon_type": info["coupon_type"],
                "discount_value": info["discount_value"],
                "min_order_value": info["min_order_value"],
                "badge": info["badge"]
            })

    return results

@router.get("/coupons", response_model=List[CouponResponse])
@router.get("", response_model=List[CouponResponse])
def list_coupons(response: Response, db: Session = Depends(get_db)):
    """List all active coupons for admin dashboard and customer promotional displays."""
    response.headers["Cache-Control"] = PUBLIC_CACHE_CONTROL
    return db.query(Coupon).filter(Coupon.is_active == True).order_by(Coupon.created_at.desc()).all()

@router.post("/coupons", response_model=CouponResponse)
@router.post("", response_model=CouponResponse)
def create_coupon(
    request: CouponCreateRequest,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Super Admin create new promotional coupon with auto uppercase conversion."""
    clean_code = request.code.strip().upper()
    existing = db.query(Coupon).filter(Coupon.code == clean_code, Coupon.is_active == True).first()
    if existing:
        raise HTTPException(status_code=400, detail="Coupon code already exists.")

    new_coupon = Coupon(
        code=clean_code,
        name=request.name.strip(),
        coupon_type=request.coupon_type,
        discount_value=request.discount_value,
        min_order_value=request.min_order_value or 0.0,
        usage_limit=request.usage_limit or 1000,
        used_count=0,
        is_active=True
    )
    db.add(new_coupon)
    db.commit()
    db.refresh(new_coupon)
    return new_coupon

@router.delete("/coupons/{coupon_id}")
@router.delete("/{coupon_id}")
def delete_coupon(
    coupon_id: str,
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Super Admin soft delete / deactivate a coupon."""
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found.")
    coupon.is_active = False
    db.commit()
    return {"message": "Coupon deleted successfully"}

# =============================================================
# DYNAMIC OFFERS CONFIGURATION ENDPOINTS (HOME, OFFERS PAGE & COMBOS)
# =============================================================

@router.get("/settings/todays-offers")
def get_todays_offers_settings(response: Response, db: Session = Depends(get_db)):
    """Fetch active Today's Offers configuration for home page with fallback."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    setting = db.query(OfferSetting).filter(OfferSetting.key == "todays_offers").first()
    if setting and setting.data:
        return setting.data
    return DEFAULT_TODAYS_OFFERS

@router.put("/settings/todays-offers")
def update_todays_offers_settings(
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Super Admin update Today's Offers configuration."""
    setting = db.query(OfferSetting).filter(OfferSetting.key == "todays_offers").first()
    if not setting:
        setting = OfferSetting(key="todays_offers", data=payload)
        db.add(setting)
    else:
        setting.data = payload
        flag_modified(setting, "data")
    db.commit()
    db.refresh(setting)
    return setting.data

@router.get("/settings/offers-page")
def get_offers_page_settings(response: Response, db: Session = Depends(get_db)):
    """Fetch active Offers Page configuration with fallback."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    setting = db.query(OfferSetting).filter(OfferSetting.key == "offers_page").first()
    if setting and setting.data:
        return setting.data
    return DEFAULT_OFFERS_PAGE

@router.put("/settings/offers-page")
def update_offers_page_settings(
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Super Admin update Offers Page configuration."""
    setting = db.query(OfferSetting).filter(OfferSetting.key == "offers_page").first()
    if not setting:
        setting = OfferSetting(key="offers_page", data=payload)
        db.add(setting)
    else:
        setting.data = payload
        flag_modified(setting, "data")
    db.commit()
    db.refresh(setting)
    return setting.data

@router.get("/settings/combo-deals")
def get_combo_deals_settings(response: Response, db: Session = Depends(get_db)):
    """Fetch active Combo Deals configuration."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    setting = db.query(OfferSetting).filter(OfferSetting.key == "combo_deals").first()
    if setting and setting.data:
        return setting.data
    return DEFAULT_COMBO_DEALS

@router.put("/settings/combo-deals")
def update_combo_deals_settings(
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(require_role([UserRole.SUPER_ADMIN])),
    db: Session = Depends(get_db)
):
    """Super Admin update Combo Deals configuration and sync to menu products."""
    setting = db.query(OfferSetting).filter(OfferSetting.key == "combo_deals").first()
    if not setting:
        setting = OfferSetting(key="combo_deals", data=payload)
        db.add(setting)
    else:
        setting.data = payload
        flag_modified(setting, "data")
    db.commit()
    db.refresh(setting)
    
    # Sync combos to products table under Combo Offers category on admin write
    sync_combo_deals_to_products(db, payload.get("combos", []))
    
    return setting.data
