"""
Test Suite for Combo Offer Choice Selection Limits.

Validates:
1. Exactly one selection (min=1, max=1) -> 200 OK.
2. Zero optional selections (min=0, max=2) -> 200 OK.
3. Multiple allowed selections (min=2, max=2) -> 200 OK.
4. Minimum violation (min=1, max=1 with 0 choices) -> 400 Bad Request.
5. Maximum violation (min=1, max=1 with 2 choices) -> 400 Bad Request.
6. Admin min > max rejection (min=2, max=1) -> 400 Bad Request.
7. Admin max > available choices rejection (max=5 with 4 choices) -> 400 Bad Request.
8. Admin negative limits rejection (min=-1 or max=-1) -> 400 Bad Request.
9. Existing combos without limits -> preserved legacy behavior (optional modifiers).
10. Duplicate selections within choice group -> 400 Bad Request.
11. Price-delta authoritative calculation -> extra £1.50 added to unit and order price.
12. Backend cart enforcement -> POST /cart/items validates selection limits authoritatively.
"""
import pytest
from app.models.user import User, UserRole
from app.models.product import Category, Product, ProductModifier, ProductChoiceGroup, ProductChoiceOption, Inventory
from app.models.branch import Branch
from app.models.setting import ShopSetting
from app.models.promotion import OfferSetting
from app.tests.db import client, TestingSessionLocal, reset_test_db
from app.core.security import create_access_token


@pytest.fixture(autouse=True)
def setup_database():
    reset_test_db()
    db = TestingSessionLocal()
    try:
        # Ensure shop is open 24/7 for testing
        shop_setting = db.query(ShopSetting).filter(ShopSetting.key == "global").first()
        if not shop_setting:
            shop_setting = ShopSetting(key="global", opening_time="00:00", closing_time="23:59")
            db.add(shop_setting)
        else:
            shop_setting.opening_time = "00:00"
            shop_setting.closing_time = "23:59"

        db.commit()
    finally:
        db.close()


def get_admin_headers():
    token = create_access_token(subject="user-superadmin-001", roles=[UserRole.SUPER_ADMIN])
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# 1. Admin Validation Tests (PUT /api/v1/promotions/settings/combo-deals)
# =========================================================================

def test_admin_min_greater_than_max_rejected():
    """Admin configuration with min > max (e.g. min=2, max=1) must be rejected with 400."""
    payload = {
        "combos": [
            {
                "id": "combo-invalid-1",
                "name": "Wings Deal",
                "base_price": 9.99,
                "min_choices": 2,
                "max_choices": 1,
                "choice_group_name": "Drink choices",
                "modifiers": [
                    {"name": "Coke", "price": 0.0},
                    {"name": "Fanta", "price": 0.0}
                ]
            }
        ]
    }
    res = client.put("/api/v1/promotions/settings/combo-deals", json=payload, headers=get_admin_headers())
    assert res.status_code == 400
    assert "cannot exceed maximum choices" in res.json()["detail"]


def test_admin_max_greater_than_available_choices_rejected():
    """Admin configuration with max > available choices count must be rejected with 400."""
    payload = {
        "combos": [
            {
                "id": "combo-invalid-2",
                "name": "Wings Deal",
                "base_price": 9.99,
                "min_choices": 1,
                "max_choices": 5,
                "choice_group_name": "Drink choices",
                "modifiers": [
                    {"name": "Coke", "price": 0.0},
                    {"name": "Fanta", "price": 0.0},
                    {"name": "Sprite", "price": 0.0},
                    {"name": "Pepsi", "price": 0.0}
                ]
            }
        ]
    }
    res = client.put("/api/v1/promotions/settings/combo-deals", json=payload, headers=get_admin_headers())
    assert res.status_code == 400
    assert "cannot exceed the number of available choices" in res.json()["detail"]


def test_admin_negative_limits_rejected():
    """Admin configuration with negative min or max must be rejected with 400."""
    payload_neg_min = {
        "combos": [
            {
                "id": "combo-neg-min",
                "name": "Wings Deal",
                "base_price": 9.99,
                "min_choices": -1,
                "max_choices": 1,
                "modifiers": [{"name": "Coke", "price": 0.0}]
            }
        ]
    }
    res = client.put("/api/v1/promotions/settings/combo-deals", json=payload_neg_min, headers=get_admin_headers())
    assert res.status_code == 400
    assert "cannot be negative" in res.json()["detail"]

    payload_neg_max = {
        "combos": [
            {
                "id": "combo-neg-max",
                "name": "Wings Deal",
                "base_price": 9.99,
                "min_choices": 0,
                "max_choices": -1,
                "modifiers": [{"name": "Coke", "price": 0.0}]
            }
        ]
    }
    res2 = client.put("/api/v1/promotions/settings/combo-deals", json=payload_neg_max, headers=get_admin_headers())
    assert res2.status_code == 400
    assert "cannot be negative" in res2.json()["detail"]


# =========================================================================
# 2. Sync & Product Choice Group Reconciliation Tests
# =========================================================================

def test_combo_syncs_to_product_choice_group():
    """Configuring choices with min=1, max=1 creates ProductChoiceGroup in the database."""
    payload = {
        "combos": [
            {
                "id": "combo-wings-deal",
                "name": "Wings Deal",
                "base_price": 10.99,
                "min_choices": 1,
                "max_choices": 1,
                "choice_group_name": "Drink choices",
                "modifiers": [
                    {"name": "Coke", "price": 0.0},
                    {"name": "Fanta", "price": 0.0},
                    {"name": "Pepsi", "price": 0.0},
                    {"name": "Premium Shake", "price": 1.50}
                ]
            }
        ]
    }
    res = client.put("/api/v1/promotions/settings/combo-deals", json=payload, headers=get_admin_headers())
    assert res.status_code == 200

    db = TestingSessionLocal()
    prod = db.query(Product).filter(Product.name == "Wings Deal").first()
    assert prod is not None
    assert prod.name == "Wings Deal"
    assert len(prod.modifiers) == 0  # Modifiers cleared when choice group is active

    groups = db.query(ProductChoiceGroup).filter(ProductChoiceGroup.product_id == prod.id).all()
    assert len(groups) == 1
    grp = groups[0]
    assert grp.name == "Drink choices"
    assert grp.min_selections == 1
    assert grp.max_selections == 1
    assert grp.is_required is True

    options = db.query(ProductChoiceOption).filter(ProductChoiceOption.group_id == grp.id).all()
    assert len(options) == 4
    opt_names = {o.name: o.price_delta for o in options}
    assert opt_names["Coke"] == 0.0
    assert opt_names["Premium Shake"] == 1.50
    db.close()


def test_existing_combos_without_limits_preserve_modifiers():
    """Existing combos without explicit choice limits continue syncing as optional ProductModifiers."""
    payload = {
        "combos": [
            {
                "id": "combo-legacy-feast",
                "name": "Legacy Feast",
                "base_price": 19.99,
                "modifiers": [
                    {"name": "Extra Sauce", "price": 0.50},
                    {"name": "Large Fries Upgrade", "price": 1.00}
                ]
            }
        ]
    }
    res = client.put("/api/v1/promotions/settings/combo-deals", json=payload, headers=get_admin_headers())
    assert res.status_code == 200

    db = TestingSessionLocal()
    prod = db.query(Product).filter(Product.name == "Legacy Feast").first()
    assert prod is not None
    # Choice groups should be empty
    groups = db.query(ProductChoiceGroup).filter(ProductChoiceGroup.product_id == prod.id).all()
    assert len(groups) == 0
    # Modifiers should exist
    mods = db.query(ProductModifier).filter(ProductModifier.product_id == prod.id).all()
    assert len(mods) == 2
    assert {m.name for m in mods} == {"Extra Sauce", "Large Fries Upgrade"}
    db.close()


# =========================================================================
# 3. Authoritative Ordering & Cart Enforcement Tests
# =========================================================================

def setup_wings_deal_combo(min_c=1, max_c=1):
    payload = {
        "combos": [
            {
                "id": "wings-test",
                "name": "Wings Deal",
                "base_price": 10.00,
                "min_choices": min_c,
                "max_choices": max_c,
                "choice_group_name": "Drink choices",
                "modifiers": [
                    {"name": "Coke", "price": 0.0},
                    {"name": "Fanta", "price": 0.0},
                    {"name": "Pepsi", "price": 0.0},
                    {"name": "Premium Shake", "price": 1.50}
                ]
            }
        ]
    }
    client.put("/api/v1/promotions/settings/combo-deals", json=payload, headers=get_admin_headers())

    db = TestingSessionLocal()
    prod = db.query(Product).filter(Product.name == "Wings Deal").first()
    # Add inventory
    inv = db.query(Inventory).filter(Inventory.product_id == prod.id).first()
    if not inv:
        db.add(Inventory(branch_id="branch-camden-001", product_id=prod.id, stock_quantity=100, is_available=True))
        db.commit()

    grp = db.query(ProductChoiceGroup).filter(ProductChoiceGroup.product_id == prod.id).first()
    opts = {o.name: o.id for o in db.query(ProductChoiceOption).filter(ProductChoiceOption.group_id == grp.id).all()}
    prod_id = prod.id
    grp_id = grp.id
    db.close()
    return prod_id, grp_id, opts


def test_exactly_one_selection_success():
    """Ordering a combo configured with min=1, max=1 with exactly one selection succeeds."""
    prod_id, grp_id, opts = setup_wings_deal_combo(1, 1)

    order_payload = {
        "branch_id": "branch-camden-001",
        "order_type": "COLLECTION",
        "customer_name": "Jane Doe",
        "customer_email": "jane@example.com",
        "customer_phone": "+44 7000 111222",
        "items": [
            {
                "product_id": prod_id,
                "quantity": 1,
                "selected_choices": [
                    {"group_id": grp_id, "option_id": opts["Coke"]}
                ]
            }
        ]
    }
    res = client.post("/api/v1/orders", json=order_payload)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["total_amount"] == 10.00


def test_price_delta_authoritative_addition():
    """Selecting a choice with a price delta (e.g. +£1.50) authoritatively updates total."""
    prod_id, grp_id, opts = setup_wings_deal_combo(1, 1)

    order_payload = {
        "branch_id": "branch-camden-001",
        "order_type": "COLLECTION",
        "customer_name": "Jane Doe",
        "customer_email": "jane@example.com",
        "customer_phone": "+44 7000 111222",
        "items": [
            {
                "product_id": prod_id,
                "quantity": 1,
                "selected_choices": [
                    {"group_id": grp_id, "option_id": opts["Premium Shake"]}
                ]
            }
        ]
    }
    res = client.post("/api/v1/orders", json=order_payload)
    assert res.status_code == 200, res.text
    data = res.json()
    # 10.00 base + 1.50 price delta = 11.50
    assert data["total_amount"] == 11.50


def test_minimum_violation_rejected():
    """Ordering combo with 0 choices when min=1 must be rejected with 400."""
    prod_id, grp_id, opts = setup_wings_deal_combo(1, 1)

    order_payload = {
        "branch_id": "branch-camden-001",
        "order_type": "COLLECTION",
        "customer_name": "Jane Doe",
        "customer_email": "jane@example.com",
        "customer_phone": "+44 7000 111222",
        "items": [
            {
                "product_id": prod_id,
                "quantity": 1,
                "selected_choices": []
            }
        ]
    }
    res = client.post("/api/v1/orders", json=order_payload)
    assert res.status_code == 400
    assert "Please select exactly 1 items for Drink choices." in res.json()["detail"]


def test_maximum_violation_rejected():
    """Ordering combo with 2 choices when max=1 must be rejected with 400."""
    prod_id, grp_id, opts = setup_wings_deal_combo(1, 1)

    order_payload = {
        "branch_id": "branch-camden-001",
        "order_type": "COLLECTION",
        "customer_name": "Jane Doe",
        "customer_email": "jane@example.com",
        "customer_phone": "+44 7000 111222",
        "items": [
            {
                "product_id": prod_id,
                "quantity": 1,
                "selected_choices": [
                    {"group_id": grp_id, "option_id": opts["Coke"]},
                    {"group_id": grp_id, "option_id": opts["Fanta"]}
                ]
            }
        ]
    }
    res = client.post("/api/v1/orders", json=order_payload)
    assert res.status_code == 400
    assert "You can select at most 1 items for Drink choices." in res.json()["detail"]


def test_multiple_allowed_selections_success_and_violation():
    """Combo configured with min=2, max=2 accepts exactly 2 and rejects 1 or 3."""
    prod_id, grp_id, opts = setup_wings_deal_combo(2, 2)

    # 1 selection -> 400
    order_1 = {
        "branch_id": "branch-camden-001",
        "order_type": "COLLECTION",
        "customer_name": "Jane Doe",
        "customer_email": "jane@example.com",
        "customer_phone": "+44 7000 111222",
        "items": [
            {
                "product_id": prod_id,
                "quantity": 1,
                "selected_choices": [
                    {"group_id": grp_id, "option_id": opts["Coke"]}
                ]
            }
        ]
    }
    res_1 = client.post("/api/v1/orders", json=order_1)
    assert res_1.status_code == 400
    assert "Please select exactly 2 items for Drink choices." in res_1.json()["detail"]

    # 2 selections -> 200 OK
    order_2 = {
        "branch_id": "branch-camden-001",
        "order_type": "COLLECTION",
        "customer_name": "Jane Doe",
        "customer_email": "jane@example.com",
        "customer_phone": "+44 7000 111222",
        "items": [
            {
                "product_id": prod_id,
                "quantity": 1,
                "selected_choices": [
                    {"group_id": grp_id, "option_id": opts["Coke"]},
                    {"group_id": grp_id, "option_id": opts["Fanta"]}
                ]
            }
        ]
    }
    res_2 = client.post("/api/v1/orders", json=order_2)
    assert res_2.status_code == 200

    # 3 selections -> 400
    order_3 = {
        "branch_id": "branch-camden-001",
        "order_type": "COLLECTION",
        "customer_name": "Jane Doe",
        "customer_email": "jane@example.com",
        "customer_phone": "+44 7000 111222",
        "items": [
            {
                "product_id": prod_id,
                "quantity": 1,
                "selected_choices": [
                    {"group_id": grp_id, "option_id": opts["Coke"]},
                    {"group_id": grp_id, "option_id": opts["Fanta"]},
                    {"group_id": grp_id, "option_id": opts["Pepsi"]}
                ]
            }
        ]
    }
    res_3 = client.post("/api/v1/orders", json=order_3)
    assert res_3.status_code == 400
    assert "You can select at most 2 items for Drink choices." in res_3.json()["detail"]


def test_zero_optional_selections_success():
    """Combo configured with min=0, max=1 accepts 0 selections and accepts 1 selection."""
    prod_id, grp_id, opts = setup_wings_deal_combo(0, 1)

    # 0 selections -> 200 OK
    order_0 = {
        "branch_id": "branch-camden-001",
        "order_type": "COLLECTION",
        "customer_name": "Jane Doe",
        "customer_email": "jane@example.com",
        "customer_phone": "+44 7000 111222",
        "items": [
            {
                "product_id": prod_id,
                "quantity": 1,
                "selected_choices": []
            }
        ]
    }
    res_0 = client.post("/api/v1/orders", json=order_0)
    assert res_0.status_code == 200

    # 1 selection -> 200 OK
    order_1 = {
        "branch_id": "branch-camden-001",
        "order_type": "COLLECTION",
        "customer_name": "Jane Doe",
        "customer_email": "jane@example.com",
        "customer_phone": "+44 7000 111222",
        "items": [
            {
                "product_id": prod_id,
                "quantity": 1,
                "selected_choices": [
                    {"group_id": grp_id, "option_id": opts["Coke"]}
                ]
            }
        ]
    }
    res_1 = client.post("/api/v1/orders", json=order_1)
    assert res_1.status_code == 200


def test_duplicate_selections_rejected():
    """Submitting duplicate choices within the same choice group is rejected with 400."""
    prod_id, grp_id, opts = setup_wings_deal_combo(2, 2)

    order_dup = {
        "branch_id": "branch-camden-001",
        "order_type": "COLLECTION",
        "customer_name": "Jane Doe",
        "customer_email": "jane@example.com",
        "customer_phone": "+44 7000 111222",
        "items": [
            {
                "product_id": prod_id,
                "quantity": 1,
                "selected_choices": [
                    {"group_id": grp_id, "option_id": opts["Coke"]},
                    {"group_id": grp_id, "option_id": opts["Coke"]}
                ]
            }
        ]
    }
    res = client.post("/api/v1/orders", json=order_dup)
    assert res.status_code == 400
    assert "Duplicate choices are not permitted for Drink choices." in res.json()["detail"]


def test_backend_cart_enforcement():
    """POST /cart/items authoritatively validates choice group selection limits."""
    prod_id, grp_id, opts = setup_wings_deal_combo(1, 1)

    # 1. Add item with 0 choices when min=1 -> 400
    res_0 = client.post(
        "/api/v1/cart/items",
        json={
            "product_id": prod_id,
            "quantity": 1,
            "selected_choices": []
        }
    )
    assert res_0.status_code == 400
    assert "Please select exactly 1 items for Drink choices." in res_0.json()["detail"]

    # 2. Add item with 2 choices when max=1 -> 400
    res_2 = client.post(
        "/api/v1/cart/items",
        json={
            "product_id": prod_id,
            "quantity": 1,
            "selected_choices": [
                {"group_id": grp_id, "option_id": opts["Coke"]},
                {"group_id": grp_id, "option_id": opts["Fanta"]}
            ]
        }
    )
    assert res_2.status_code == 400
    assert "You can select at most 1 items for Drink choices." in res_2.json()["detail"]

    # 3. Add item with valid 1 choice -> 200 OK
    res_1 = client.post(
        "/api/v1/cart/items",
        json={
            "product_id": prod_id,
            "quantity": 1,
            "selected_choices": [
                {"group_id": grp_id, "option_id": opts["Coke"]}
            ]
        }
    )
    assert res_1.status_code == 200
    cart_data = res_1.json()
    assert len(cart_data["items"]) == 1
    assert len(cart_data["items"][0]["selected_choices"]) == 1
    assert cart_data["items"][0]["selected_choices"][0]["option_name"] == "Coke"
