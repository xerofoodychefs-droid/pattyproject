"""
Comprehensive test suite for "Choose 2" / Menu Choice Groups functionality.

Validates:
1. Normal product without choices works.
2. Super Admin can create product with "Choose 2" choice group.
3. Product choice groups are returned by GET /products.
4. Ordering with 0 choices selected -> 400 Bad Request.
5. Ordering with 1 choice selected -> 400 Bad Request.
6. Ordering with 2 valid choices -> 200 OK.
7. Ordering with 3 choices selected -> 400 Bad Request.
8. Invalid option ID -> 400 Bad Request.
9. Inactive option -> 400 Bad Request.
10. Option from another product/group -> 400 Bad Request.
11. Client price tampering is ignored by server authoritative pricing.
12. Choice selection appears in order item snapshot.
13. Existing modifier pricing still works alongside choice groups.
14. Normal product checkout without choice groups remains 100% functional.
"""
import pytest
from app.models.user import User, UserRole
from app.models.product import Category, Product, ProductModifier, ProductChoiceGroup, ProductChoiceOption, Inventory
from app.models.branch import Branch
from app.models.order import Order, OrderItem
from app.tests.db import client, TestingSessionLocal, reset_test_db
from app.core.security import create_access_token


@pytest.fixture(autouse=True)
def setup_database():
    reset_test_db()
    db = TestingSessionLocal()
    try:
        # Create Super Admin
        admin = User(
            email="superadmin@pattyproject.co.uk",
            full_name="Super Admin",
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            email_verified=True
        )
        db.add(admin)

        # Create Branch
        branch = Branch(
            code="BR-CENTRAL",
            name="Central Branch",
            address_line1="123 Patty Way",
            postcode="SW1A 1AA",
            city="London",
            latitude=51.5074,
            longitude=-0.1278,
            delivery_enabled=True,
            collection_enabled=True,
            ordering_enabled=True,
            delivery_radius_miles=5.0,
            is_active=True
        )
        db.add(branch)

        # Create Category
        cat = Category(
            name="Breakfast",
            slug="breakfast",
            display_order=1,
            is_active=True
        )
        db.add(cat)
        db.commit()
    finally:
        db.close()


def get_admin_headers():
    db = TestingSessionLocal()
    admin = db.query(User).filter(User.role == UserRole.SUPER_ADMIN).first()
    admin_id = admin.id
    db.close()
    token = create_access_token(subject=admin_id, roles=[UserRole.SUPER_ADMIN])
    return {"Authorization": f"Bearer {token}"}


def test_normal_product_without_choices():
    """Test 1: Existing normal product without choices can be created and retrieved with empty choice_groups."""
    db = TestingSessionLocal()
    cat = db.query(Category).first()
    cat_id = cat.id
    db.close()

    create_payload = {
        "category_id": cat_id,
        "name": "Classic Cheeseburger",
        "sku": "CLASSIC-001",
        "base_price": 8.99,
        "modifiers": [
            {"name": "Extra Patty", "price": 2.50}
        ]
    }
    res = client.post("/api/v1/products", json=create_payload, headers=get_admin_headers())
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["name"] == "Classic Cheeseburger"
    assert data["choice_groups"] == []
    assert len(data["modifiers"]) == 1


def test_choose_two_product_lifecycle_and_validation():
    """Tests 2-14: Complete test suite covering creation, GET, validation rules, pricing, snapshots, and modifiers."""
    db = TestingSessionLocal()
    cat = db.query(Category).first()
    branch = db.query(Branch).first()
    cat_id = cat.id
    branch_id = branch.id
    db.close()

    # 1. Create Breakfast Deal with "Choose any 2"
    create_payload = {
        "category_id": cat_id,
        "name": "Breakfast Deal",
        "sku": "BRK-DEAL-01",
        "base_price": 7.99,
        "modifiers": [
            {"name": "Extra Hot Sauce", "price": 0.50}
        ],
        "choice_groups": [
            {
                "name": "Choose any 2",
                "min_selections": 2,
                "max_selections": 2,
                "is_required": True,
                "display_order": 0,
                "options": [
                    {"name": "Sausage", "price_delta": 0.0, "is_active": True},
                    {"name": "Bacon", "price_delta": 0.0, "is_active": True},
                    {"name": "Egg", "price_delta": 0.0, "is_active": True},
                    {"name": "Hash Brown", "price_delta": 0.0, "is_active": True},
                    {"name": "Artisan Halloumi", "price_delta": 1.50, "is_active": True},
                    {"name": "Turkey Bacon (Sold Out)", "price_delta": 0.0, "is_active": False}
                ]
            }
        ]
    }
    create_res = client.post("/api/v1/products", json=create_payload, headers=get_admin_headers())
    assert create_res.status_code == 200, create_res.text
    prod_data = create_res.json()
    product_id = prod_data["id"]

    # 2. Add inventory so the product is orderable
    db = TestingSessionLocal()
    inv = Inventory(
        branch_id=branch_id,
        product_id=product_id,
        stock_quantity=50,
        is_available=True
    )
    db.add(inv)
    db.commit()
    db.close()

    # 3. GET /products verifies choice_groups and options
    get_res = client.get(f"/api/v1/products/{product_id}")
    assert get_res.status_code == 200
    p_info = get_res.json()
    assert len(p_info["choice_groups"]) == 1
    grp = p_info["choice_groups"][0]
    assert grp["name"] == "Choose any 2"
    assert grp["min_selections"] == 2
    assert grp["max_selections"] == 2
    assert len(grp["options"]) == 6

    options_by_name = {opt["name"]: opt for opt in grp["options"]}
    opt_sausage = options_by_name["Sausage"]
    opt_bacon = options_by_name["Bacon"]
    opt_egg = options_by_name["Egg"]
    opt_halloumi = options_by_name["Artisan Halloumi"]
    opt_inactive = options_by_name["Turkey Bacon (Sold Out)"]

    base_order_payload = {
        "branch_id": branch_id,
        "order_type": "COLLECTION",
        "customer_name": "John Doe",
        "customer_email": "john.doe@example.com",
        "customer_phone": "+44 7000 000000"
    }

    # 4. Test: 0 choices selected -> 400 Bad Request
    order_0 = dict(base_order_payload, items=[
        {
            "product_id": product_id,
            "quantity": 1,
            "selected_choices": []
        }
    ])
    res_0 = client.post("/api/v1/orders", json=order_0)
    assert res_0.status_code == 400
    assert "Please select exactly 2 items for Choose any 2." in res_0.json()["detail"]

    # 5. Test: 1 choice selected -> 400 Bad Request
    order_1 = dict(base_order_payload, items=[
        {
            "product_id": product_id,
            "quantity": 1,
            "selected_choices": [
                {"group_id": grp["id"], "option_id": opt_sausage["id"]}
            ]
        }
    ])
    res_1 = client.post("/api/v1/orders", json=order_1)
    assert res_1.status_code == 400
    assert "Please select exactly 2 items for Choose any 2." in res_1.json()["detail"]

    # 7. Test: 3 choices selected -> 400 Bad Request
    order_3 = dict(base_order_payload, items=[
        {
            "product_id": product_id,
            "quantity": 1,
            "selected_choices": [
                {"group_id": grp["id"], "option_id": opt_sausage["id"]},
                {"group_id": grp["id"], "option_id": opt_bacon["id"]},
                {"group_id": grp["id"], "option_id": opt_egg["id"]}
            ]
        }
    ])
    res_3 = client.post("/api/v1/orders", json=order_3)
    assert res_3.status_code == 400
    assert "You can select at most 2 items for Choose any 2." in res_3.json()["detail"]

    # 8. Test: Invalid option ID -> 400 Bad Request
    order_invalid_opt = dict(base_order_payload, items=[
        {
            "product_id": product_id,
            "quantity": 1,
            "selected_choices": [
                {"group_id": grp["id"], "option_id": opt_sausage["id"]},
                {"group_id": grp["id"], "option_id": "non-existent-opt-id"}
            ]
        }
    ])
    res_invalid = client.post("/api/v1/orders", json=order_invalid_opt)
    assert res_invalid.status_code == 400

    # 9. Test: Inactive option -> 400 Bad Request
    order_inactive = dict(base_order_payload, items=[
        {
            "product_id": product_id,
            "quantity": 1,
            "selected_choices": [
                {"group_id": grp["id"], "option_id": opt_sausage["id"]},
                {"group_id": grp["id"], "option_id": opt_inactive["id"]}
            ]
        }
    ])
    res_inactive = client.post("/api/v1/orders", json=order_inactive)
    assert res_inactive.status_code == 400
    assert "is invalid or unavailable" in res_inactive.json()["detail"]

    # 10. Test: Option from another product/group -> 400 Bad Request
    db = TestingSessionLocal()
    other_prod = Product(
        category_id=cat_id,
        name="Other Item",
        sku="OTHER-001",
        base_price=5.00
    )
    db.add(other_prod)
    db.flush()
    other_grp = ProductChoiceGroup(product_id=other_prod.id, name="Other Group")
    db.add(other_grp)
    db.flush()
    other_opt = ProductChoiceOption(group_id=other_grp.id, name="Foreign Option")
    db.add(other_opt)
    db.commit()
    foreign_opt_id = other_opt.id
    db.close()

    order_foreign = dict(base_order_payload, items=[
        {
            "product_id": product_id,
            "quantity": 1,
            "selected_choices": [
                {"group_id": grp["id"], "option_id": opt_sausage["id"]},
                {"group_id": grp["id"], "option_id": foreign_opt_id}
            ]
        }
    ])
    res_foreign = client.post("/api/v1/orders", json=order_foreign)
    assert res_foreign.status_code == 400

    # 10b. Test: Duplicate choice submissions within the same group -> 400 Bad Request
    order_duplicate = dict(base_order_payload, items=[
        {
            "product_id": product_id,
            "quantity": 1,
            "selected_choices": [
                {"group_id": grp["id"], "option_id": opt_sausage["id"]},
                {"group_id": grp["id"], "option_id": opt_sausage["id"]}
            ]
        }
    ])
    res_duplicate = client.post("/api/v1/orders", json=order_duplicate)
    assert res_duplicate.status_code == 400
    assert "Duplicate choices are not permitted" in res_duplicate.json()["detail"]

    # 6 & 11 & 12: 2 valid selections + client price tampering attempt -> 200 OK with server authoritative price
    order_valid = dict(base_order_payload, items=[
        {
            "product_id": product_id,
            "quantity": 1,
            "selected_choices": [
                {"group_id": grp["id"], "option_id": opt_sausage["id"], "price_delta": 999.0}, # Tampered price
                {"group_id": grp["id"], "option_id": opt_halloumi["id"], "price_delta": -50.0} # Tampered price
            ]
        }
    ])
    res_valid = client.post("/api/v1/orders", json=order_valid)
    assert res_valid.status_code == 200, res_valid.text
    order_data = res_valid.json()

    # Price verification: base (£7.99) + Sausage (£0.00) + Halloumi (£1.50) = £9.49
    # Tampered client prices are completely ignored
    assert order_data["subtotal"] == 9.49

    # 12. Choice selection appears in order snapshot
    db = TestingSessionLocal()
    order_in_db = db.query(Order).filter(Order.id == order_data["id"]).first()
    item_in_db = order_in_db.items[0]
    choice_names = [m["name"] for m in item_in_db.selected_modifiers]
    assert any("Sausage" in name for name in choice_names)
    assert any("Artisan Halloumi" in name for name in choice_names)
    db.close()

    # 13. Existing modifier pricing still works alongside choice groups
    order_with_modifier = dict(base_order_payload, items=[
        {
            "product_id": product_id,
            "quantity": 1,
            "selected_modifiers": [{"name": "Extra Hot Sauce", "price": 0.50}],
            "selected_choices": [
                {"group_id": grp["id"], "option_id": opt_sausage["id"]},
                {"group_id": grp["id"], "option_id": opt_bacon["id"]}
            ]
        }
    ])
    res_mod = client.post("/api/v1/orders", json=order_with_modifier)
    assert res_mod.status_code == 200
    # base (£7.99) + Extra Hot Sauce (£0.50) + Sausage (£0.00) + Bacon (£0.00) = £8.49
    assert res_mod.json()["subtotal"] == 8.49

    # 14. Existing normal product checkout without choices still works 100%
    normal_prod = Product(
        category_id=cat_id,
        name="Plain Pancakes",
        sku="PANCAKE-01",
        base_price=4.50
    )
    db = TestingSessionLocal()
    db.add(normal_prod)
    db.flush()
    db.add(Inventory(branch_id=branch_id, product_id=normal_prod.id, stock_quantity=10, is_available=True))
    db.commit()
    normal_prod_id = normal_prod.id
    db.close()

    order_normal = dict(base_order_payload, items=[
        {
            "product_id": normal_prod_id,
            "quantity": 2
        }
    ])
    res_norm = client.post("/api/v1/orders", json=order_normal)
    assert res_norm.status_code == 200
    assert res_norm.json()["subtotal"] == 9.00

    # 15. Same product with different choice selections on separate lines in same order
    order_multi_line = dict(base_order_payload, items=[
        {
            "product_id": product_id,
            "quantity": 1,
            "selected_choices": [
                {"group_id": grp["id"], "option_id": opt_sausage["id"]},
                {"group_id": grp["id"], "option_id": opt_bacon["id"]}
            ]
        },
        {
            "product_id": product_id,
            "quantity": 1,
            "selected_choices": [
                {"group_id": grp["id"], "option_id": opt_egg["id"]},
                {"group_id": grp["id"], "option_id": opt_halloumi["id"]}
            ]
        }
    ])
    res_multi = client.post("/api/v1/orders", json=order_multi_line)
    assert res_multi.status_code == 200
    # Line 1: £7.99 + £0.00 = £7.99
    # Line 2: £7.99 + £1.50 = £9.49
    # Total subtotal: £17.48
    assert res_multi.json()["subtotal"] == 17.48

    # 16. Multiple choice groups on the same product (e.g. Choose 1 Rasher + Choose 1 Sausage)
    multi_group_payload = {
        "category_id": cat_id,
        "name": "Breakfast Bun Combo",
        "sku": "BUN-COMBO-01",
        "base_price": 6.99,
        "choice_groups": [
            {
                "name": "Choose your rasher",
                "min_selections": 1,
                "max_selections": 1,
                "is_required": True,
                "display_order": 0,
                "options": [
                    {"name": "Pork Bacon", "price_delta": 0.0, "is_active": True},
                    {"name": "Turkey Bacon", "price_delta": 0.50, "is_active": True}
                ]
            },
            {
                "name": "Choose your sausage",
                "min_selections": 1,
                "max_selections": 1,
                "is_required": True,
                "display_order": 1,
                "options": [
                    {"name": "Pork Sausage", "price_delta": 0.0, "is_active": True},
                    {"name": "Chicken Sausage", "price_delta": 0.0, "is_active": True}
                ]
            }
        ]
    }
    combo_res = client.post("/api/v1/products", json=multi_group_payload, headers=get_admin_headers())
    assert combo_res.status_code == 200
    combo_data = combo_res.json()
    combo_id = combo_data["id"]

    db = TestingSessionLocal()
    db.add(Inventory(branch_id=branch_id, product_id=combo_id, stock_quantity=10, is_available=True))
    db.commit()
    db.close()

    g_rasher = combo_data["choice_groups"][0]
    g_sausage = combo_data["choice_groups"][1]
    opt_turkey = [o for o in g_rasher["options"] if o["name"] == "Turkey Bacon"][0]
    opt_chicken = [o for o in g_sausage["options"] if o["name"] == "Chicken Sausage"][0]

    # Incomplete selection (missing sausage group) -> 400
    incomplete_order = dict(base_order_payload, items=[
        {
            "product_id": combo_id,
            "quantity": 1,
            "selected_choices": [
                {"group_id": g_rasher["id"], "option_id": opt_turkey["id"]}
            ]
        }
    ])
    res_incomp = client.post("/api/v1/orders", json=incomplete_order)
    assert res_incomp.status_code == 400
    assert "Choose your sausage" in res_incomp.json()["detail"]

    # Complete selection across both groups -> 200
    complete_order = dict(base_order_payload, items=[
        {
            "product_id": combo_id,
            "quantity": 1,
            "selected_choices": [
                {"group_id": g_rasher["id"], "option_id": opt_turkey["id"]},
                {"group_id": g_sausage["id"], "option_id": opt_chicken["id"]}
            ]
        }
    ])
    res_comp = client.post("/api/v1/orders", json=complete_order)
    assert res_comp.status_code == 200
    # base (£6.99) + Turkey Bacon (£0.50) + Chicken Sausage (£0.00) = £7.49
    assert res_comp.json()["subtotal"] == 7.49
