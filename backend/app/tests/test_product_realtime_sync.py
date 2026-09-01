import sys
import pathlib
import uuid
import pytest

# Ensure backend root is on sys.path
backend_root = pathlib.Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.tests.db import client, reset_test_db, TestingSessionLocal
from app.models import User, UserRole, Product, Category, Inventory, Branch
from app.core.security import get_password_hash, create_access_token


@pytest.fixture(autouse=True)
def setup_product_realtime_test():
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

    cat = db.query(Category).first()
    if not cat:
        cat = Category(id="cat-burgers", name="Burgers", slug="burgers", is_active=True, display_order=0)
        db.add(cat)

    db.commit()
    db.close()


def get_token_header(user_id: str, email: str, role) -> dict:
    role_str = role if isinstance(role, str) else role.value
    token = create_access_token(
        subject=user_id,
        roles=[role_str]
    )
    return {"Authorization": f"Bearer {token}"}


def test_01_product_create_emits_realtime_event():
    """Super Admin creating a product emits a 'product_changed' event with action='created'."""
    super_headers = get_token_header("user-super-admin-001", "superadmin@pattyproject.co.uk", UserRole.SUPER_ADMIN)

    with client.websocket_connect("/api/v1/ws/products") as ws:
        init_msg = ws.receive_json()
        assert init_msg["type"] == "CONNECTED"

        # Super Admin creates a new product
        create_res = client.post(
            "/api/v1/products",
            headers=super_headers,
            json={
                "category_id": "cat-burgers",
                "name": "Truffle Burger",
                "base_price": 14.50,
                "sku": f"TRUFFLE-{uuid.uuid4().hex[:6].upper()}"
            }
        )
        assert create_res.status_code == 200
        new_prod_id = create_res.json()["id"]

        event = ws.receive_json()
        assert event["type"] == "product_changed"
        assert event["action"] == "created"
        assert event["product_id"] == new_prod_id


def test_02_product_update_emits_realtime_event():
    """Super Admin updating product details (price, name, etc.) emits 'product_changed' with action='updated'."""
    super_headers = get_token_header("user-super-admin-001", "superadmin@pattyproject.co.uk", UserRole.SUPER_ADMIN)

    with client.websocket_connect("/api/v1/ws/products") as ws:
        init_msg = ws.receive_json()
        assert init_msg["type"] == "CONNECTED"

        # Super Admin updates prod-mc-project price & name
        update_res = client.put(
            "/api/v1/products/prod-mc-project",
            headers=super_headers,
            json={
                "name": "The MC Project (Updated)",
                "base_price": 17.50
            }
        )
        assert update_res.status_code == 200

        event = ws.receive_json()
        assert event["type"] == "product_changed"
        assert event["action"] == "updated"
        assert event["product_id"] == "prod-mc-project"


def test_03_product_delete_emits_realtime_event():
    """Super Admin deleting a product emits 'product_changed' with action='deleted'."""
    super_headers = get_token_header("user-super-admin-001", "superadmin@pattyproject.co.uk", UserRole.SUPER_ADMIN)

    # First create a temporary product
    create_res = client.post(
        "/api/v1/products",
        headers=super_headers,
        json={
            "category_id": "cat-burgers",
            "name": "Temp Delete Burger",
            "base_price": 9.99,
            "sku": f"DEL-{uuid.uuid4().hex[:6].upper()}"
        }
    )
    assert create_res.status_code == 200
    temp_id = create_res.json()["id"]

    with client.websocket_connect("/api/v1/ws/products") as ws:
        assert ws.receive_json()["type"] == "CONNECTED"

        # Super Admin deletes the product
        del_res = client.delete(
            f"/api/v1/products/{temp_id}",
            headers=super_headers
        )
        assert del_res.status_code == 200

        event1 = ws.receive_json()
        assert event1["type"] == "product_changed"
        assert event1["action"] == "deleted"
        assert event1["product_id"] == temp_id

        event2 = ws.receive_json()
        assert event2["type"] == "product_availability_changed"
        assert event2["product_id"] == temp_id
        assert event2["is_out_of_stock"] is True


def test_04_inventory_toggle_emits_realtime_event_with_branch_id():
    """Branch inventory toggle broadcasts product_changed with branch_id."""
    super_headers = get_token_header("user-super-admin-001", "superadmin@pattyproject.co.uk", UserRole.SUPER_ADMIN)

    with client.websocket_connect("/api/v1/ws/products") as ws:
        assert ws.receive_json()["type"] == "CONNECTED"

        toggle_res = client.post(
            "/api/v1/inventory/toggle",
            headers=super_headers,
            json={
                "branch_id": "branch-camden",
                "product_id": "prod-mc-project",
                "is_available": False
            }
        )
        assert toggle_res.status_code == 200

        event1 = ws.receive_json()
        assert event1["type"] == "product_changed"
        assert event1["action"] == "updated"
        assert event1["product_id"] == "prod-mc-project"
        assert event1["branch_id"] == "branch-camden"

        event2 = ws.receive_json()
        assert event2["type"] == "product_availability_changed"
        assert event2["product_id"] == "prod-mc-project"
        assert event2["is_out_of_stock"] is True


def test_05_failed_product_mutation_does_not_emit_event():
    """Invalid product creation (e.g. 404 or validation error) does not emit WebSocket event."""
    super_headers = get_token_header("user-super-admin-001", "superadmin@pattyproject.co.uk", UserRole.SUPER_ADMIN)

    with client.websocket_connect("/api/v1/ws/products") as ws:
        assert ws.receive_json()["type"] == "CONNECTED"

        # Attempt to update a non-existent product
        res = client.put(
            "/api/v1/products/non-existent-product-id-99999",
            headers=super_headers,
            json={"name": "Ghost Burger"}
        )
        assert res.status_code == 404

        # Send ping to verify no event was queued
        ws.send_json({"type": "PING"})
        pong = ws.receive_json()
        assert pong["type"] == "PONG"
