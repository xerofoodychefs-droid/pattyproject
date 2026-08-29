import sys
import pathlib
import pytest
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
backend_root = pathlib.Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.tests.db import client, reset_test_db, TestingSessionLocal
from app.models import (
    User, UserRole, Branch, BranchUser, Product, Order, OrderItem,
    OrderStatus, OrderType, PaymentStatus, Inventory
)
from app.core.security import get_password_hash, create_access_token


@pytest.fixture(autouse=True)
def setup_rbac_environment():
    reset_test_db()
    db = TestingSessionLocal()

    # Create Branch Admin for Camden
    camden_admin = User(
        id="user-camden-admin-001",
        email="camden.admin@pattyproject.co.uk",
        password_hash=get_password_hash("CamdenAdmin123!"),
        full_name="Camden Branch Admin",
        role=UserRole.BRANCH_ADMIN,
        is_active=True,
        email_verified=True
    )
    db.add(camden_admin)
    db.flush()

    bu_camden = BranchUser(
        user_id="user-camden-admin-001",
        branch_id="branch-camden-001"
    )
    db.add(bu_camden)

    # Create Branch Admin for Westfield
    westfield_admin = User(
        id="user-westfield-admin-002",
        email="westfield.admin@pattyproject.co.uk",
        password_hash=get_password_hash("WestfieldAdmin123!"),
        full_name="Westfield Branch Admin",
        role=UserRole.BRANCH_ADMIN,
        is_active=True,
        email_verified=True
    )
    db.add(westfield_admin)
    db.flush()

    bu_westfield = BranchUser(
        user_id="user-westfield-admin-002",
        branch_id="branch-westfield-002"
    )
    db.add(bu_westfield)

    # Create Camden Order
    camden_order = Order(
        id="order-camden-001",
        order_number="PP-CAMDEN-101",
        branch_id="branch-camden-001",
        customer_name="Alice Camden",
        customer_email="alice@example.com",
        customer_phone="+447123456789",
        order_type=OrderType.DELIVERY,
        status=OrderStatus.INCOMING,
        subtotal=15.00,
        total_amount=17.50,
        payment_status=PaymentStatus.PENDING
    )
    db.add(camden_order)

    # Create Westfield Order
    westfield_order = Order(
        id="order-westfield-002",
        order_number="PP-WESTFIELD-202",
        branch_id="branch-westfield-002",
        customer_name="Bob Westfield",
        customer_email="bob@example.com",
        customer_phone="+447987654321",
        order_type=OrderType.COLLECTION,
        status=OrderStatus.ACCEPTED,
        subtotal=20.00,
        total_amount=20.00,
        payment_status=PaymentStatus.PAID
    )
    db.add(westfield_order)

    # Create Inventory items
    inv_camden = Inventory(
        id="inv-camden-001",
        branch_id="branch-camden-001",
        product_id="prod-mc-project",
        stock_quantity=50,
        low_stock_threshold=10,
        is_available=True
    )
    inv_westfield = Inventory(
        id="inv-westfield-002",
        branch_id="branch-westfield-002",
        product_id="prod-mc-project",
        stock_quantity=30,
        low_stock_threshold=10,
        is_available=True
    )
    db.add_all([inv_camden, inv_westfield])

    db.commit()
    db.close()


def get_auth_header(user_id: str, email: str, role: str) -> dict:
    token = create_access_token(
        subject=user_id,
        roles=[role]
    )
    return {"Authorization": f"Bearer {token}"}


# -------------------------------------------------------------
# 1. SUPER ADMIN PERMISSION TESTS
# -------------------------------------------------------------

def test_super_admin_can_view_all_orders():
    headers = get_auth_header("user-superadmin-001", "admin@pattyproject.co.uk", "SUPER_ADMIN")
    response = client.get("/api/v1/orders", headers=headers)
    assert response.status_code == 200
    orders = response.json()
    assert len(orders) >= 2
    order_numbers = [o["order_number"] for o in orders]
    assert "PP-CAMDEN-101" in order_numbers
    assert "PP-WESTFIELD-202" in order_numbers


def test_super_admin_can_filter_orders_by_branch():
    headers = get_auth_header("user-superadmin-001", "admin@pattyproject.co.uk", "SUPER_ADMIN")
    response = client.get("/api/v1/orders?branch_id=branch-camden-001", headers=headers)
    assert response.status_code == 200
    orders = response.json()
    assert len(orders) == 1
    assert orders[0]["order_number"] == "PP-CAMDEN-101"


def test_super_admin_can_update_any_order_status():
    headers = get_auth_header("user-superadmin-001", "admin@pattyproject.co.uk", "SUPER_ADMIN")
    response = client.patch(
        "/api/v1/orders/order-camden-001/status",
        headers=headers,
        json={"status": "PREPARING", "notes": "Super admin updated status"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "PREPARING"


def test_super_admin_can_view_and_update_all_inventory():
    headers = get_auth_header("user-superadmin-001", "admin@pattyproject.co.uk", "SUPER_ADMIN")
    
    # View inventory
    response = client.get("/api/v1/inventory", headers=headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 2

    # Update Camden inventory
    patch_res = client.patch(
        "/api/v1/inventory/inv-camden-001",
        headers=headers,
        json={"stock_quantity": 99, "is_available": False}
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["stock_quantity"] == 99
    assert patch_res.json()["is_available"] is False

    # Toggle Westfield inventory
    toggle_res = client.post(
        "/api/v1/inventory/toggle",
        headers=headers,
        json={"branch_id": "branch-westfield-002", "product_id": "prod-mc-project", "is_available": False}
    )
    assert toggle_res.status_code == 200
    assert toggle_res.json()["is_available"] is False


def test_super_admin_can_manage_products_and_categories():
    headers = get_auth_header("user-superadmin-001", "admin@pattyproject.co.uk", "SUPER_ADMIN")
    
    # Create category
    cat_res = client.post(
        "/api/v1/categories",
        headers=headers,
        json={"name": "Special Shakes", "icon": "cup", "display_order": 5}
    )
    assert cat_res.status_code == 200
    cat_id = cat_res.json()["id"]

    # Create product
    prod_res = client.post(
        "/api/v1/products",
        headers=headers,
        json={
            "category_id": cat_id,
            "name": "Vanilla Shake",
            "sku": "SHAKE-VAN-01",
            "base_price": 4.50
        }
    )
    assert prod_res.status_code == 200


# -------------------------------------------------------------
# 2. BRANCH ADMIN ISOLATION & PERMISSION TESTS
# -------------------------------------------------------------

def test_branch_admin_sees_only_assigned_branch_orders():
    camden_headers = get_auth_header("user-camden-admin-001", "camden.admin@pattyproject.co.uk", "BRANCH_ADMIN")
    response = client.get("/api/v1/orders", headers=camden_headers)
    assert response.status_code == 200
    orders = response.json()
    assert len(orders) == 1
    assert orders[0]["order_number"] == "PP-CAMDEN-101"
    assert orders[0]["branch_id"] == "branch-camden-001"


def test_branch_admin_cannot_query_other_branch_orders_via_query_param():
    camden_headers = get_auth_header("user-camden-admin-001", "camden.admin@pattyproject.co.uk", "BRANCH_ADMIN")
    response = client.get("/api/v1/orders?branch_id=branch-westfield-002", headers=camden_headers)
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


def test_branch_admin_can_manage_own_order_status():
    camden_headers = get_auth_header("user-camden-admin-001", "camden.admin@pattyproject.co.uk", "BRANCH_ADMIN")
    response = client.patch(
        "/api/v1/orders/order-camden-001/status",
        headers=camden_headers,
        json={"status": "ACCEPTED", "notes": "Accepted by Camden team"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "ACCEPTED"


def test_branch_admin_cannot_update_other_branch_order_status():
    camden_headers = get_auth_header("user-camden-admin-001", "camden.admin@pattyproject.co.uk", "BRANCH_ADMIN")
    response = client.patch(
        "/api/v1/orders/order-westfield-002/status",
        headers=camden_headers,
        json={"status": "PREPARING"}
    )
    assert response.status_code == 403
    assert "Cannot manage order outside assigned branch" in response.json()["detail"]


def test_branch_admin_cannot_inspect_other_branch_order_details():
    camden_headers = get_auth_header("user-camden-admin-001", "camden.admin@pattyproject.co.uk", "BRANCH_ADMIN")
    # Querying own Camden order -> 200
    own_res = client.get("/api/v1/orders/PP-CAMDEN-101", headers=camden_headers)
    assert own_res.status_code == 200

    # Querying other branch's order -> 403
    other_res = client.get("/api/v1/orders/PP-WESTFIELD-202", headers=camden_headers)
    assert other_res.status_code == 403
    assert "Access denied" in other_res.json()["detail"]


def test_branch_admin_sees_only_assigned_branch_inventory():
    camden_headers = get_auth_header("user-camden-admin-001", "camden.admin@pattyproject.co.uk", "BRANCH_ADMIN")
    response = client.get("/api/v1/inventory", headers=camden_headers)
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 1
    for item in items:
        assert item["branch_id"] == "branch-camden-001"


def test_branch_admin_cannot_query_other_branch_inventory_via_param():
    camden_headers = get_auth_header("user-camden-admin-001", "camden.admin@pattyproject.co.uk", "BRANCH_ADMIN")
    response = client.get("/api/v1/inventory?branch_id=branch-westfield-002", headers=camden_headers)
    assert response.status_code == 403
    assert "Access denied" in response.json()["detail"]


def test_branch_admin_can_update_own_branch_stock_and_toggle_availability():
    camden_headers = get_auth_header("user-camden-admin-001", "camden.admin@pattyproject.co.uk", "BRANCH_ADMIN")
    
    # Update Camden inventory item
    patch_res = client.patch(
        "/api/v1/inventory/inv-camden-001",
        headers=camden_headers,
        json={"stock_quantity": 42, "is_available": False}
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["stock_quantity"] == 42
    assert patch_res.json()["is_available"] is False

    # Toggle Camden stock back to In Stock
    toggle_res = client.post(
        "/api/v1/inventory/toggle",
        headers=camden_headers,
        json={"branch_id": "branch-camden-001", "product_id": "prod-mc-project", "is_available": True}
    )
    assert toggle_res.status_code == 200
    assert toggle_res.json()["is_available"] is True


def test_branch_admin_cannot_update_other_branch_stock():
    camden_headers = get_auth_header("user-camden-admin-001", "camden.admin@pattyproject.co.uk", "BRANCH_ADMIN")
    
    # Try updating Westfield inventory record directly
    patch_res = client.patch(
        "/api/v1/inventory/inv-westfield-002",
        headers=camden_headers,
        json={"stock_quantity": 0}
    )
    assert patch_res.status_code == 403
    assert "Cannot manage inventory outside assigned branch" in patch_res.json()["detail"]

    # Try toggling Westfield stock via toggle endpoint
    toggle_res = client.post(
        "/api/v1/inventory/toggle",
        headers=camden_headers,
        json={"branch_id": "branch-westfield-002", "product_id": "prod-mc-project", "is_available": False}
    )
    assert toggle_res.status_code == 403
    assert "Cannot manage inventory outside assigned branch" in toggle_res.json()["detail"]


def test_branch_admin_cannot_perform_super_admin_operations():
    camden_headers = get_auth_header("user-camden-admin-001", "camden.admin@pattyproject.co.uk", "BRANCH_ADMIN")

    # Create Product
    prod_res = client.post(
        "/api/v1/products",
        headers=camden_headers,
        json={"name": "Hacker Burger", "sku": "HACK-01", "base_price": 10.0}
    )
    assert prod_res.status_code == 403

    # Delete Product
    del_prod_res = client.delete("/api/v1/products/prod-mc-project", headers=camden_headers)
    assert del_prod_res.status_code == 403

    # Create Category
    cat_res = client.post(
        "/api/v1/categories",
        headers=camden_headers,
        json={"name": "Hacked Category"}
    )
    assert cat_res.status_code == 403

    # Create Branch
    branch_res = client.post(
        "/api/v1/branches",
        headers=camden_headers,
        json={"name": "Fake Branch", "code": "FB", "postcode": "EC1A 1BB", "city": "London", "address_line1": "1 Road"}
    )
    assert branch_res.status_code == 403

    # Delete Branch
    del_branch_res = client.delete("/api/v1/branches/branch-camden-001", headers=camden_headers)
    assert del_branch_res.status_code == 403

    # Create Coupon
    coupon_res = client.post(
        "/api/v1/promotions/coupons",
        headers=camden_headers,
        json={"code": "UNAUTH50", "name": "50% Off", "coupon_type": "PERCENTAGE", "discount_value": 50.0}
    )
    assert coupon_res.status_code == 403
