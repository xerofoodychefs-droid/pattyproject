import pytest
from app.tests.db import client, reset_test_db, TestingSessionLocal
from app.models.user import User, UserRole
from app.models.promotion import OfferSetting
from app.core.security import get_password_hash, create_access_token

# Sample base64 image data URL (1x1 red PNG)
SAMPLE_BASE64_IMAGE = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
SAMPLE_CUSTOM_URL_1 = "https://pattyproject.co.uk/uploads/custom_burger_combo.webp"
SAMPLE_CUSTOM_URL_2 = "https://pattyproject.co.uk/uploads/custom_wings_promo.webp"
SAMPLE_CUSTOM_URL_3 = "https://pattyproject.co.uk/uploads/custom_student_deal.webp"

@pytest.fixture(autouse=True)
def setup_db():
    reset_test_db()

def get_super_admin_token() -> str:
    return create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])

def get_branch_admin_token() -> str:
    db = TestingSessionLocal()
    try:
        branch_user = db.query(User).filter(User.email == "branchmanager@pattyproject.co.uk").first()
        if not branch_user:
            branch_user = User(
                id="user-branchadmin-001",
                email="branchmanager@pattyproject.co.uk",
                password_hash=get_password_hash("Branch123!"),
                full_name="Branch Manager",
                role=UserRole.BRANCH_ADMIN,
                is_active=True,
                email_verified=True
            )
            db.add(branch_user)
            db.commit()
            db.refresh(branch_user)
        return create_access_token(subject=branch_user.id, roles=[UserRole.BRANCH_ADMIN])
    finally:
        db.close()


def test_01_get_default_todays_offers_when_no_custom_saved():
    """When no custom configuration is saved, GET returns DEFAULT_TODAYS_OFFERS."""
    res = client.get("/api/v1/promotions/settings/todays-offers")
    assert res.status_code == 200
    data = res.json()
    assert data["section_title"] == "TODAY'S OFFERS"
    assert len(data["cards"]) == 3
    assert data["cards"][0]["title"] == "BURGER COMBO"
    assert data["cards"][1]["title"] == "WING WEDNESDAY"
    assert data["cards"][2]["title"] == "STUDENT OFFER"


def test_02_super_admin_saves_custom_images_and_all_card_fields():
    """Super Admin uploads/saves custom images (base64 and URLs) and text for all 3 cards."""
    admin_token = get_super_admin_token()

    custom_payload = {
        "section_title": "SPECIAL CHEF OFFERS",
        "view_all_link": "/offers",
        "view_all_text": "EXPLORE ALL DEALS",
        "cards": [
            {
                "id": "card-1",
                "title": "ULTIMATE SMASH COMBO",
                "subtitle": "Double Patty + Loaded Fries + Milkshake",
                "badge": "SAVE 25%",
                "image_url": SAMPLE_BASE64_IMAGE,
                "bg_image": "offer_bg_1.png",
                "link_url": "/order"
            },
            {
                "id": "card-2",
                "title": "BUFFALO WINGS EXTRAVAGANZA",
                "subtitle": "12 Crispy Wings with Blue Cheese",
                "badge": "30% OFF",
                "image_url": SAMPLE_CUSTOM_URL_2,
                "bg_image": "offer_bg_2.png",
                "link_url": "/order"
            },
            {
                "id": "card-3",
                "title": "EXCLUSIVE STUDENT PERK",
                "subtitle": "Free Drink with Any Meal",
                "badge": "STUDENT DEAL",
                "badge_type": "id_badge",
                "image_url": SAMPLE_CUSTOM_URL_3,
                "bg_image": "offer_bg_3.png",
                "link_url": "/order"
            }
        ]
    }

    res = client.put(
        "/api/v1/promotions/settings/todays-offers",
        json=custom_payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200
    saved = res.json()
    assert saved["section_title"] == "SPECIAL CHEF OFFERS"
    assert saved["cards"][0]["image_url"] == SAMPLE_BASE64_IMAGE
    assert saved["cards"][1]["image_url"] == SAMPLE_CUSTOM_URL_2
    assert saved["cards"][2]["image_url"] == SAMPLE_CUSTOM_URL_3


def test_03_saved_custom_images_persist_and_survive_get_requests():
    """
    CRITICAL BUG REGRESSION TEST:
    A subsequent GET request MUST return the exact uploaded images and MUST NOT
    revert to Unsplash placeholders or default fallback images.
    """
    admin_token = get_super_admin_token()

    custom_payload = {
        "section_title": "TODAY'S EXCLUSIVES",
        "view_all_link": "/offers",
        "view_all_text": "VIEW ALL OFFERS",
        "cards": [
            {
                "id": "card-1",
                "title": "BURGER COMBO",
                "subtitle": "Burger + Fries + Drink",
                "badge": "SAVE 15%",
                "image_url": SAMPLE_BASE64_IMAGE,
                "bg_image": "offer_bg_1.png",
                "link_url": "/order"
            },
            {
                "id": "card-2",
                "title": "WING WEDNESDAY",
                "subtitle": "On All Wings",
                "badge": "20% OFF",
                "image_url": SAMPLE_CUSTOM_URL_2,
                "bg_image": "offer_bg_2.png",
                "link_url": "/order"
            },
            {
                "id": "card-3",
                "title": "STUDENT OFFER",
                "subtitle": "On All Orders",
                "badge": "10% OFF",
                "image_url": SAMPLE_CUSTOM_URL_3,
                "bg_image": "offer_bg_3.png",
                "link_url": "/order"
            }
        ]
    }

    # 1. Save
    res_save = client.put(
        "/api/v1/promotions/settings/todays-offers",
        json=custom_payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_save.status_code == 200

    # 2. Multiple subsequent GET requests (simulating customer visits, admin reloads)
    for _ in range(3):
        res_get = client.get("/api/v1/promotions/settings/todays-offers")
        assert res_get.status_code == 200
        data = res_get.json()
        assert data["section_title"] == "TODAY'S EXCLUSIVES"
        # Verify uploaded images are preserved exactly
        assert data["cards"][0]["image_url"] == SAMPLE_BASE64_IMAGE
        assert data["cards"][1]["image_url"] == SAMPLE_CUSTOM_URL_2
        assert data["cards"][2]["image_url"] == SAMPLE_CUSTOM_URL_3
        # Verify it did NOT revert to Unsplash
        assert "unsplash.com" not in data["cards"][0]["image_url"]
        assert "unsplash.com" not in data["cards"][1]["image_url"]


def test_04_direct_database_persistence_verification():
    """Verify that the JSON record in offer_settings table contains the exact saved configuration."""
    admin_token = get_super_admin_token()

    custom_payload = {
        "section_title": "DB PERSISTENCE TEST",
        "view_all_link": "/offers",
        "view_all_text": "VIEW ALL",
        "cards": [
            {
                "id": "card-1",
                "title": "TEST TITLE 1",
                "subtitle": "TEST SUBTITLE 1",
                "badge": "50% OFF",
                "image_url": SAMPLE_BASE64_IMAGE,
                "link_url": "/order"
            }
        ]
    }

    res = client.put(
        "/api/v1/promotions/settings/todays-offers",
        json=custom_payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res.status_code == 200

    # Inspect direct database state
    db = TestingSessionLocal()
    try:
        setting = db.query(OfferSetting).filter(OfferSetting.key == "todays_offers").first()
        assert setting is not None
        assert setting.data["section_title"] == "DB PERSISTENCE TEST"
        assert setting.data["cards"][0]["image_url"] == SAMPLE_BASE64_IMAGE
    finally:
        db.close()


def test_05_super_admin_can_replace_image():
    """Super Admin can replace an existing uploaded image with a new image."""
    admin_token = get_super_admin_token()

    # Step 1: Save initial image
    payload_v1 = {
        "section_title": "TODAY'S OFFERS",
        "cards": [
            {"id": "card-1", "title": "Burger Combo", "subtitle": "Fries", "badge": "10%", "image_url": SAMPLE_CUSTOM_URL_1}
        ]
    }
    client.put("/api/v1/promotions/settings/todays-offers", json=payload_v1, headers={"Authorization": f"Bearer {admin_token}"})

    # Step 2: Replace with new image
    NEW_IMAGE_URL = "https://pattyproject.co.uk/uploads/new_burger_combo_v2.png"
    payload_v2 = {
        "section_title": "TODAY'S OFFERS",
        "cards": [
            {"id": "card-1", "title": "Burger Combo", "subtitle": "Fries", "badge": "10%", "image_url": NEW_IMAGE_URL}
        ]
    }
    res_update = client.put("/api/v1/promotions/settings/todays-offers", json=payload_v2, headers={"Authorization": f"Bearer {admin_token}"})
    assert res_update.status_code == 200
    assert res_update.json()["cards"][0]["image_url"] == NEW_IMAGE_URL

    # Step 3: Fetch and confirm new image is returned
    res_get = client.get("/api/v1/promotions/settings/todays-offers")
    assert res_get.json()["cards"][0]["image_url"] == NEW_IMAGE_URL


def test_06_branch_admin_cannot_overwrite_super_admin_todays_offers():
    """Branch Admin / Branch Manager is rejected with 403 Forbidden when trying to update Today's Offers."""
    branch_token = get_branch_admin_token()

    malicious_payload = {
        "section_title": "BRANCH OVERWRITE ATTEMPT",
        "cards": []
    }

    res = client.put(
        "/api/v1/promotions/settings/todays-offers",
        json=malicious_payload,
        headers={"Authorization": f"Bearer {branch_token}"}
    )
    assert res.status_code == 403


def test_07_unauthenticated_requests_cannot_update_todays_offers():
    """Anonymous/unauthenticated PUT requests are rejected with 401 Unauthorized."""
    res = client.put("/api/v1/promotions/settings/todays-offers", json={"section_title": "Hacked"})
    assert res.status_code == 401


def test_08_reset_defaults_explicitly_restores_defaults_and_persists():
    """Reset Defaults only executes when explicitly sent by Super Admin, restoring default images."""
    admin_token = get_super_admin_token()

    # Step 1: Save custom configuration
    custom_payload = {
        "section_title": "CUSTOM BEFORE RESET",
        "cards": [{"id": "card-1", "title": "Custom", "subtitle": "Sub", "badge": "5%", "image_url": SAMPLE_BASE64_IMAGE}]
    }
    client.put("/api/v1/promotions/settings/todays-offers", json=custom_payload, headers={"Authorization": f"Bearer {admin_token}"})

    # Step 2: Explicit Reset Defaults (sending default payload)
    from app.api.endpoints.promotions import DEFAULT_TODAYS_OFFERS
    res_reset = client.put(
        "/api/v1/promotions/settings/todays-offers",
        json=DEFAULT_TODAYS_OFFERS,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_reset.status_code == 200
    assert res_reset.json()["section_title"] == "TODAY'S OFFERS"
    assert len(res_reset.json()["cards"]) == 3

    # Step 3: GET confirms defaults are published
    res_get = client.get("/api/v1/promotions/settings/todays-offers")
    assert res_get.json()["section_title"] == "TODAY'S OFFERS"


def test_09_offers_page_and_combo_deals_preserve_custom_images():
    """Offers Page and Combo Deals settings also preserve uploaded images without stripping."""
    admin_token = get_super_admin_token()

    offers_page_payload = {
        "banner": {
            "tagline": "EXCLUSIVE",
            "headline_main": "DEALS",
            "headline_highlight": "SPECIAL",
            "description": "Best food",
            "image_url": SAMPLE_BASE64_IMAGE
        },
        "offers": [
            {
                "id": "offer-1",
                "category": ["combos"],
                "title": "Custom Combo",
                "tag": "COMBO",
                "tagIcon": "utensils",
                "badge": "10% OFF",
                "code": "CUST10",
                "image": SAMPLE_BASE64_IMAGE,
                "description": "Custom description"
            }
        ]
    }

    res_put = client.put(
        "/api/v1/promotions/settings/offers-page",
        json=offers_page_payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_put.status_code == 200

    res_get = client.get("/api/v1/promotions/settings/offers-page")
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["banner"]["image_url"] == SAMPLE_BASE64_IMAGE
    assert data["offers"][0]["image"] == SAMPLE_BASE64_IMAGE
