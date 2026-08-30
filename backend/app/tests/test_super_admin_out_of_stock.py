import sys
import pathlib
import pytest

# Ensure backend root is on sys.path
backend_root = pathlib.Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.tests.db import client, reset_test_db, TestingSessionLocal
from app.models import User, UserRole, Product, Category, Inventory, Branch
from app.core.security import get_password_hash, create_access_token


@pytest.fixture(autouse=True)
def setup_out_of_stock_environment():
    reset_test_db()
    db = TestingSessionLocal()

    # Create Super Admin
    super_admin = User(
        id="user-super-admin-001",
        email="superadmin@pattyproject.co.uk",
        password_hash=get_password_hash("SuperAdmin123!"),
        full_name="Super Admin",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        email_verified=True
    )
    # Create Branch Admin
    branch_admin = User(
        id="user-branch-admin-001",
        email="branchadmin@pattyproject.co.uk",
        password_hash=get_password_hash("BranchAdmin123!"),
        full_name="Branch Admin",
        role=UserRole.BRANCH_ADMIN,
        is_active=True,
        email_verified=True
    )
    # Create Customer
    customer = User(
        id="user-customer-001",
        email="customer@example.com",
        password_hash=get_password_hash("Customer123!"),
        full_name="Customer User",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=True
    )
    db.add_all([super_admin, branch_admin, customer])
    db.commit()
    db.close()


def get_token_header(user_id: str, email: str, role: str) -> dict:
    token = create_access_token(
        subject=user_id,
        roles=[role]
    )
    return {"Authorization": f"Bearer {token}"}


def test_1_super_admin_sets_product_out_of_stock_preserves_inventory_rows():
    """TEST 1: Super Admin sets product Out of Stock. Product.is_out_of_stock = true, no Inventory rows changed."""
    db = TestingSessionLocal()
    initial_invs = {inv.id: (inv.branch_id, inv.is_available, inv.stock_quantity) for inv in db.query(Inventory).filter(Inventory.product_id == "prod-mc-project").all()}
    db.close()

    super_headers = get_token_header("user-super-admin-001", "superadmin@pattyproject.co.uk", UserRole.SUPER_ADMIN)
    patch_res = client.patch(
        "/api/v1/admin/products/prod-mc-project/availability",
        headers=super_headers,
        json={"is_out_of_stock": True}
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["is_out_of_stock"] is True
    assert patch_res.json()["is_available"] is False

    db2 = TestingSessionLocal()
    prod = db2.query(Product).filter(Product.id == "prod-mc-project").first()
    assert prod.is_out_of_stock is True

    # Verify NO Inventory rows were modified
    current_invs = {inv.id: (inv.branch_id, inv.is_available, inv.stock_quantity) for inv in db2.query(Inventory).filter(Inventory.product_id == "prod-mc-project").all()}
    assert current_invs == initial_invs
    db2.close()


def test_2_super_admin_sets_product_available_preserves_inventory_rows():
    """TEST 2: Super Admin sets product Available. Product.is_out_of_stock = false, no Inventory rows changed."""
    db = TestingSessionLocal()
    prod = db.query(Product).filter(Product.id == "prod-mc-project").first()
    prod.is_out_of_stock = True
    db.commit()
    initial_invs = {inv.id: (inv.branch_id, inv.is_available, inv.stock_quantity) for inv in db.query(Inventory).filter(Inventory.product_id == "prod-mc-project").all()}
    db.close()

    super_headers = get_token_header("user-super-admin-001", "superadmin@pattyproject.co.uk", UserRole.SUPER_ADMIN)
    patch_res = client.patch(
        "/api/v1/admin/products/prod-mc-project/availability",
        headers=super_headers,
        json={"is_out_of_stock": False}
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["is_out_of_stock"] is False
    assert patch_res.json()["is_available"] is True

    db2 = TestingSessionLocal()
    prod2 = db2.query(Product).filter(Product.id == "prod-mc-project").first()
    assert prod2.is_out_of_stock is False
    current_invs = {inv.id: (inv.branch_id, inv.is_available, inv.stock_quantity) for inv in db2.query(Inventory).filter(Inventory.product_id == "prod-mc-project").all()}
    assert current_invs == initial_invs
    db2.close()


def test_3_and_4_hierarchical_branch_inventory_preservation():
    """TEST 3 & 4: Branch A has is_available=False, Branch B has is_available=True.
    Set global product Out of Stock -> both effectively unavailable, inventory rows unchanged.
    Set global product back Available -> Branch A remains unavailable, Branch B remains available.
    """
    db = TestingSessionLocal()
    inv_camden = db.query(Inventory).filter(Inventory.branch_id == "branch-camden-001", Inventory.product_id == "prod-mc-project").first()
    if not inv_camden:
        inv_camden = Inventory(id="inv-camden-test", branch_id="branch-camden-001", product_id="prod-mc-project", stock_quantity=50, is_available=False)
        db.add(inv_camden)
    else:
        inv_camden.is_available = False

    inv_westfield = db.query(Inventory).filter(Inventory.branch_id == "branch-westfield-002", Inventory.product_id == "prod-mc-project").first()
    if not inv_westfield:
        inv_westfield = Inventory(id="inv-westfield-test", branch_id="branch-westfield-002", product_id="prod-mc-project", stock_quantity=50, is_available=True)
        db.add(inv_westfield)
    else:
        inv_westfield.is_available = True

    prod = db.query(Product).filter(Product.id == "prod-mc-project").first()
    prod.is_out_of_stock = False
    db.commit()
    db.close()

    super_headers = get_token_header("user-super-admin-001", "superadmin@pattyproject.co.uk", UserRole.SUPER_ADMIN)

    # 1. Set global Out of Stock = True
    patch_res = client.patch(
        "/api/v1/admin/products/prod-mc-project/availability",
        headers=super_headers,
        json={"is_out_of_stock": True}
    )
    assert patch_res.status_code == 200

    # Query for Camden and Westfield
    res_camden = client.get("/api/v1/products/prod-mc-project?branch_id=branch-camden-001").json()
    res_westfield = client.get("/api/v1/products/prod-mc-project?branch_id=branch-westfield-002").json()
    assert res_camden["is_available"] is False
    assert res_westfield["is_available"] is False

    # Check underlying Inventory rows in DB
    db2 = TestingSessionLocal()
    inv_c = db2.query(Inventory).filter(Inventory.branch_id == "branch-camden-001", Inventory.product_id == "prod-mc-project").first()
    inv_w = db2.query(Inventory).filter(Inventory.branch_id == "branch-westfield-002", Inventory.product_id == "prod-mc-project").first()
    assert inv_c.is_available is False  # Camden row untouched
    assert inv_w.is_available is True   # Westfield row untouched
    db2.close()

    # 2. Set global Out of Stock back to False
    patch_res2 = client.patch(
        "/api/v1/admin/products/prod-mc-project/availability",
        headers=super_headers,
        json={"is_out_of_stock": False}
    )
    assert patch_res2.status_code == 200

    # Camden must remain unavailable, Westfield must be available!
    res_camden2 = client.get("/api/v1/products/prod-mc-project?branch_id=branch-camden-001").json()
    res_westfield2 = client.get("/api/v1/products/prod-mc-project?branch_id=branch-westfield-002").json()
    assert res_camden2["is_available"] is False
    assert res_westfield2["is_available"] is True


def test_category_level_out_of_stock_toggle_and_isolation():
    """TEST: Super Admin can toggle an entire category Out of Stock and Available.
    - All products in that category are updated.
    - Products in other categories remain unchanged.
    - Branch Inventory records are completely untouched.
    """
    db = TestingSessionLocal()
    # Find a category with multiple products
    cat = db.query(Category).first()
    assert cat is not None
    cat_id = cat.id

    cat_prods = db.query(Product).filter(Product.category_id == cat_id).all()
    other_prods = db.query(Product).filter(Product.category_id != cat_id).all()

    # Reset all products in this category to Available (False)
    for p in cat_prods:
        p.is_out_of_stock = False
    for p in other_prods:
        p.is_out_of_stock = False
    db.commit()

    # Record snapshot of all inventory rows before category operation
    initial_all_invs = {(inv.branch_id, inv.product_id): (inv.is_available, inv.stock_quantity) for inv in db.query(Inventory).all()}
    db.close()

    super_headers = get_token_header("user-super-admin-001", "superadmin@pattyproject.co.uk", UserRole.SUPER_ADMIN)

    # 1. Super Admin marks category Out of Stock
    cat_patch_res = client.patch(
        f"/api/v1/admin/categories/{cat_id}/availability",
        headers=super_headers,
        json={"is_out_of_stock": True}
    )
    assert cat_patch_res.status_code == 200
    res_json = cat_patch_res.json()
    assert res_json["category_id"] == cat_id
    assert res_json["is_out_of_stock"] is True
    assert res_json["updated_products_count"] == len(cat_prods)

    # Verify all products in the category have is_out_of_stock = True
    db2 = TestingSessionLocal()
    for p in db2.query(Product).filter(Product.category_id == cat_id).all():
        assert p.is_out_of_stock is True

    # Verify products in other categories are UNCHANGED (is_out_of_stock = False)
    for p in db2.query(Product).filter(Product.category_id != cat_id).all():
        assert p.is_out_of_stock is False

    # Verify NO Inventory rows were modified anywhere in the database
    current_all_invs = {(inv.branch_id, inv.product_id): (inv.is_available, inv.stock_quantity) for inv in db2.query(Inventory).all()}
    assert current_all_invs == initial_all_invs
    db2.close()

    # 2. Super Admin marks category Available again
    cat_patch_res2 = client.patch(
        f"/api/v1/admin/categories/{cat_id}/availability",
        headers=super_headers,
        json={"is_out_of_stock": False}
    )
    assert cat_patch_res2.status_code == 200
    assert cat_patch_res2.json()["is_out_of_stock"] is False

    # Verify all products in the category have is_out_of_stock = False
    db3 = TestingSessionLocal()
    for p in db3.query(Product).filter(Product.category_id == cat_id).all():
        assert p.is_out_of_stock is False

    # Verify Inventory rows remain untouched
    current_all_invs2 = {(inv.branch_id, inv.product_id): (inv.is_available, inv.stock_quantity) for inv in db3.query(Inventory).all()}
    assert current_all_invs2 == initial_all_invs
    db3.close()


def test_category_availability_rbac():
    """TEST: Only Super Admin can mutate category availability. Branch Admin & Customer receive 403, Anon receives 401."""
    db = TestingSessionLocal()
    cat = db.query(Category).first()
    cat_id = cat.id
    db.close()

    branch_headers = get_token_header("user-branch-admin-001", "branchadmin@pattyproject.co.uk", UserRole.BRANCH_ADMIN)
    customer_headers = get_token_header("user-customer-001", "customer@example.com", UserRole.CUSTOMER)

    # Branch Admin -> 403 Forbidden
    res_branch = client.patch(
        f"/api/v1/admin/categories/{cat_id}/availability",
        headers=branch_headers,
        json={"is_out_of_stock": True}
    )
    assert res_branch.status_code == 403

    # Customer -> 403 Forbidden
    res_cust = client.patch(
        f"/api/v1/admin/categories/{cat_id}/availability",
        headers=customer_headers,
        json={"is_out_of_stock": True}
    )
    assert res_cust.status_code == 403

    # Unauthenticated -> 401 Unauthorized
    res_anon = client.patch(
        f"/api/v1/admin/categories/{cat_id}/availability",
        json={"is_out_of_stock": True}
    )
    assert res_anon.status_code == 401


def test_no_out_of_stock_category_exists():
    """TEST: Verify no fake 'Out of Stock' category is stored or returned by /categories."""
    cat_res = client.get("/api/v1/categories")
    assert cat_res.status_code == 200
    cat_names = [c["name"].lower() for c in cat_res.json()]
    assert "out of stock" not in cat_names


def test_5_global_out_of_stock_rejects_order():
    """TEST 5: Global product is Out of Stock. Attempt an order -> Order rejected."""
    db = TestingSessionLocal()
    prod = db.query(Product).filter(Product.id == "prod-mc-project").first()
    prod.is_out_of_stock = True
    inv = db.query(Inventory).filter(Inventory.branch_id == "branch-camden-001", Inventory.product_id == "prod-mc-project").first()
    if inv:
        inv.is_available = True
        inv.stock_quantity = 50
    db.commit()
    db.close()

    customer_headers = get_token_header("user-customer-001", "customer@example.com", UserRole.CUSTOMER)
    order_payload = {
        "branch_id": "branch-camden-001",
        "order_type": "COLLECTION",
        "customer_name": "Test Customer",
        "customer_phone": "07123456789",
        "customer_email": "customer@example.com",
        "items": [
            {
                "product_id": "prod-mc-project",
                "quantity": 1,
                "selected_modifiers": []
            }
        ]
    }
    res = client.post("/api/v1/orders", headers=customer_headers, json=order_payload)
    assert res.status_code == 400
    assert "out of stock" in res.json()["detail"].lower()


def test_6_branch_inventory_unavailable_rejects_order():
    """TEST 6: Global product is Available. Branch Inventory.is_available = False. Attempt an order -> Order rejected."""
    db = TestingSessionLocal()
    prod = db.query(Product).filter(Product.id == "prod-mc-project").first()
    prod.is_out_of_stock = False
    inv = db.query(Inventory).filter(Inventory.branch_id == "branch-camden-001", Inventory.product_id == "prod-mc-project").first()
    if not inv:
        inv = Inventory(id="inv-camden-001", branch_id="branch-camden-001", product_id="prod-mc-project", stock_quantity=50, is_available=False)
        db.add(inv)
    else:
        inv.is_available = False
        inv.stock_quantity = 50
    db.commit()
    db.close()

    customer_headers = get_token_header("user-customer-001", "customer@example.com", UserRole.CUSTOMER)
    order_payload = {
        "branch_id": "branch-camden-001",
        "order_type": "COLLECTION",
        "customer_name": "Test Customer",
        "customer_phone": "07123456789",
        "customer_email": "customer@example.com",
        "items": [
            {
                "product_id": "prod-mc-project",
                "quantity": 1,
                "selected_modifiers": []
            }
        ]
    }
    res = client.post("/api/v1/orders", headers=customer_headers, json=order_payload)
    assert res.status_code == 400
    assert "out of stock" in res.json()["detail"].lower()


def test_7_branch_inventory_stock_quantity_zero_rejects_order():
    """TEST 7: Global product is Available. Branch Inventory.is_available = True, stock_quantity = 0. Attempt an order -> Order rejected."""
    db = TestingSessionLocal()
    prod = db.query(Product).filter(Product.id == "prod-mc-project").first()
    prod.is_out_of_stock = False
    inv = db.query(Inventory).filter(Inventory.branch_id == "branch-camden-001", Inventory.product_id == "prod-mc-project").first()
    if not inv:
        inv = Inventory(id="inv-camden-001", branch_id="branch-camden-001", product_id="prod-mc-project", stock_quantity=0, is_available=True)
        db.add(inv)
    else:
        inv.is_available = True
        inv.stock_quantity = 0
    db.commit()
    db.close()

    customer_headers = get_token_header("user-customer-001", "customer@example.com", UserRole.CUSTOMER)
    order_payload = {
        "branch_id": "branch-camden-001",
        "order_type": "COLLECTION",
        "customer_name": "Test Customer",
        "customer_phone": "07123456789",
        "customer_email": "customer@example.com",
        "items": [
            {
                "product_id": "prod-mc-project",
                "quantity": 1,
                "selected_modifiers": []
            }
        ]
    }
    res = client.post("/api/v1/orders", headers=customer_headers, json=order_payload)
    assert res.status_code == 400
    assert "out of stock" in res.json()["detail"].lower()


def test_8_branch_admin_cannot_toggle_product_out_of_stock():
    """TEST 8: Normal Admin (Branch Admin) attempts to change Product.is_out_of_stock -> 403 Forbidden."""
    branch_headers = get_token_header("user-branch-admin-001", "branchadmin@pattyproject.co.uk", UserRole.BRANCH_ADMIN)
    patch_res = client.patch(
        "/api/v1/admin/products/prod-mc-project/availability",
        headers=branch_headers,
        json={"is_out_of_stock": True}
    )
    assert patch_res.status_code == 403


def test_9_customer_cannot_toggle_product_out_of_stock():
    """TEST 9: Customer attempts to change Product.is_out_of_stock -> 403 Forbidden."""
    customer_headers = get_token_header("user-customer-001", "customer@example.com", UserRole.CUSTOMER)
    patch_res = client.patch(
        "/api/v1/admin/products/prod-mc-project/availability",
        headers=customer_headers,
        json={"is_out_of_stock": True}
    )
    assert patch_res.status_code == 403
