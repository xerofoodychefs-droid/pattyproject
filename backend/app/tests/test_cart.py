import uuid
import threading
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.core.database import Base
from app.models.user import User, UserRole, AuthProvider
from app.models.product import Product, Category
from app.models.branch import Branch
from app.models.cart import Cart, CartItem
from app.core.security import get_password_hash, create_access_token
from app.tests.db import client, reset_test_db, TestingSessionLocal


@pytest.fixture(autouse=True)
def clean_cart_db():
    """Seeds test products and users on top of reset_test_db."""
    reset_test_db()

    db = TestingSessionLocal()
    try:
        p2 = Product(
            id="prod-bacon-burger",
            category_id="cat-burgers",
            name="Smoked Bacon Burger",
            sku="PP-BB-002",
            base_price=11.50,
            is_active=True
        )
        db.add(p2)

        u1 = User(
            id="user-account-a",
            email="account.a@pattyproject.co.uk",
            password_hash=get_password_hash("Password123!"),
            full_name="Account A User",
            role=UserRole.CUSTOMER,
            is_active=True,
            email_verified=True
        )
        u2 = User(
            id="user-account-b",
            email="account.b@pattyproject.co.uk",
            password_hash=get_password_hash("Password123!"),
            full_name="Account B User",
            role=UserRole.CUSTOMER,
            is_active=True,
            email_verified=True
        )
        db.add_all([u1, u2])
        db.commit()
    finally:
        db.close()


def get_token(email: str, user_id: str) -> str:
    return create_access_token(subject=user_id, roles=["CUSTOMER"])


# =========================================================================
# 1. GUEST CART CREATION & ISOLATION
# =========================================================================

def test_guest_cart_creation_and_session_id():
    """Guest adding item receives a cart bound only to their X-Guest-Session-ID."""
    guest_session_1 = str(uuid.uuid4())
    headers = {"X-Guest-Session-ID": guest_session_1}

    # 1. Empty cart initially
    r = client.get("/api/v1/cart", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["items"] == []
    assert data["session_id"] == guest_session_1
    assert data["user_id"] is None

    # 2. Add product
    add_r = client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": "prod-mc-project",
        "quantity": 2,
        "selected_modifiers": [{"name": "Extra Patty", "price": 3.00}]
    })
    assert add_r.status_code == 200
    cart_data = add_r.json()
    assert len(cart_data["items"]) == 1
    assert cart_data["items"][0]["product_id"] == "prod-mc-project"
    assert cart_data["items"][0]["quantity"] == 2
    assert cart_data["items"][0]["unit_price"] == 19.00
    assert cart_data["items"][0]["line_total"] == 38.00
    assert cart_data["subtotal"] == 38.00
    assert cart_data["item_count"] == 2


def test_guest_cart_isolation_between_two_sessions():
    """Two different guest session IDs have completely separate carts."""
    session_1 = str(uuid.uuid4())
    session_2 = str(uuid.uuid4())

    # Guest 1 adds Product 1
    client.post("/api/v1/cart/items", headers={"X-Guest-Session-ID": session_1}, json={
        "product_id": "prod-mc-project",
        "quantity": 1
    })

    # Guest 2 adds Product 2
    client.post("/api/v1/cart/items", headers={"X-Guest-Session-ID": session_2}, json={
        "product_id": "prod-bacon-burger",
        "quantity": 3
    })

    # Verify Guest 1 sees only Product 1
    r1 = client.get("/api/v1/cart", headers={"X-Guest-Session-ID": session_1}).json()
    assert len(r1["items"]) == 1
    assert r1["items"][0]["product_id"] == "prod-mc-project"
    assert r1["items"][0]["quantity"] == 1

    # Verify Guest 2 sees only Product 2
    r2 = client.get("/api/v1/cart", headers={"X-Guest-Session-ID": session_2}).json()
    assert len(r2["items"]) == 1
    assert r2["items"][0]["product_id"] == "prod-bacon-burger"
    assert r2["items"][0]["quantity"] == 3


# =========================================================================
# 2. AUTHENTICATED CART & MULTI-DEVICE SYNCHRONIZATION
# =========================================================================

def test_authenticated_user_cart_multi_device_sync():
    """
    Device 1: Account A logs in and adds Product A.
    Device 2: Account A logs in and fetches cart -> sees Product A.
    Device 2: Adds Product B.
    Device 1: Refreshes / GET /cart -> sees Product A + Product B.
    """
    token_a = get_token("account.a@pattyproject.co.uk", "user-account-a")
    headers_device_1 = {"Authorization": f"Bearer {token_a}"}
    headers_device_2 = {"Authorization": f"Bearer {token_a}"}

    # Device 1 adds Cheeseburger
    client.post("/api/v1/cart/items", headers=headers_device_1, json={
        "product_id": "prod-mc-project",
        "quantity": 1
    })

    # Device 2 fetches cart -> sees Cheeseburger
    r_dev2 = client.get("/api/v1/cart", headers=headers_device_2).json()
    assert len(r_dev2["items"]) == 1
    assert r_dev2["items"][0]["product_id"] == "prod-mc-project"
    assert r_dev2["user_id"] == "user-account-a"

    # Device 2 adds Bacon Burger
    client.post("/api/v1/cart/items", headers=headers_device_2, json={
        "product_id": "prod-bacon-burger",
        "quantity": 2
    })

    # Device 1 fetches cart -> sees both
    r_dev1 = client.get("/api/v1/cart", headers=headers_device_1).json()
    assert len(r_dev1["items"]) == 2
    prod_ids = {i["product_id"]: i["quantity"] for i in r_dev1["items"]}
    assert prod_ids == {"prod-mc-project": 1, "prod-bacon-burger": 2}


# =========================================================================
# 3. ACCOUNT SWITCHING & ISOLATION
# =========================================================================

def test_account_switching_isolation():
    """
    1. Account A logs in, adds Product A.
    2. Account A logs out.
    3. Account B logs in on the same client.
    4. Account B must NOT see Product A.
    5. Account B adds Product B.
    6. Account B logs out.
    7. Account A logs in.
    8. Account A sees Product A, but NOT Product B.
    """
    token_a = get_token("account.a@pattyproject.co.uk", "user-account-a")
    token_b = get_token("account.b@pattyproject.co.uk", "user-account-b")

    # Step 1: Account A adds Cheeseburger
    client.post("/api/v1/cart/items", headers={"Authorization": f"Bearer {token_a}"}, json={
        "product_id": "prod-mc-project",
        "quantity": 2
    })

    # Step 3 & 4: Account B logs in -> sees empty cart
    r_b = client.get("/api/v1/cart", headers={"Authorization": f"Bearer {token_b}"}).json()
    assert r_b["items"] == []
    assert r_b["user_id"] == "user-account-b"

    # Step 5: Account B adds Bacon Burger
    client.post("/api/v1/cart/items", headers={"Authorization": f"Bearer {token_b}"}, json={
        "product_id": "prod-bacon-burger",
        "quantity": 1
    })

    # Step 7 & 8: Account A logs in again -> sees only Cheeseburger
    r_a = client.get("/api/v1/cart", headers={"Authorization": f"Bearer {token_a}"}).json()
    assert len(r_a["items"]) == 1
    assert r_a["items"][0]["product_id"] == "prod-mc-project"
    assert r_a["items"][0]["quantity"] == 2


# =========================================================================
# 4. GUEST -> AUTHENTICATED CART MERGE
# =========================================================================

def test_guest_to_authenticated_cart_merge():
    """
    Guest adds Product A (Mc Project x 1).
    Account A already has Product A (Mc Project x 2) + Product B (Bacon Burger x 1).
    Merge on login combining line items:
    Result: Mc Project x 3, Bacon Burger x 1.
    Guest cart is deleted/retired.
    """
    token_a = get_token("account.a@pattyproject.co.uk", "user-account-a")
    guest_session = str(uuid.uuid4())

    # Pre-populate Account A cart
    client.post("/api/v1/cart/items", headers={"Authorization": f"Bearer {token_a}"}, json={
        "product_id": "prod-mc-project",
        "quantity": 2
    })
    client.post("/api/v1/cart/items", headers={"Authorization": f"Bearer {token_a}"}, json={
        "product_id": "prod-bacon-burger",
        "quantity": 1
    })

    # Guest adds Mc Project x 1
    client.post("/api/v1/cart/items", headers={"X-Guest-Session-ID": guest_session}, json={
        "product_id": "prod-mc-project",
        "quantity": 1
    })

    # Perform Merge on Login
    merge_resp = client.post(
        "/api/v1/cart/merge",
        headers={"Authorization": f"Bearer {token_a}", "X-Guest-Session-ID": guest_session},
        json={"guest_session_id": guest_session}
    )
    assert merge_resp.status_code == 200
    merged_data = merge_resp.json()
    assert merged_data["user_id"] == "user-account-a"
    assert len(merged_data["items"]) == 2

    counts = {item["product_id"]: item["quantity"] for item in merged_data["items"]}
    assert counts["prod-mc-project"] == 3
    assert counts["prod-bacon-burger"] == 1

    # Verify guest cart is now deleted / empty
    guest_check = client.get("/api/v1/cart", headers={"X-Guest-Session-ID": guest_session}).json()
    assert guest_check["items"] == []


# =========================================================================
# 5. SECURITY & HORIZONTAL PRIVILEGE ESCALATION
# =========================================================================

def test_horizontal_authorization_and_tampering_protection():
    """
    Account B must NOT be able to modify, delete, or view Account A's cart items.
    """
    token_a = get_token("account.a@pattyproject.co.uk", "user-account-a")
    token_b = get_token("account.b@pattyproject.co.uk", "user-account-b")

    # Account A adds Cheeseburger
    add_a = client.post("/api/v1/cart/items", headers={"Authorization": f"Bearer {token_a}"}, json={
        "product_id": "prod-mc-project",
        "quantity": 1
    }).json()
    item_id_a = add_a["items"][0]["id"]

    # Account B tries to update Account A's cart item
    patch_b = client.patch(
        f"/api/v1/cart/items/{item_id_a}",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"quantity": 99}
    )
    assert patch_b.status_code == 404

    # Account B tries to delete Account A's cart item
    delete_b = client.delete(
        f"/api/v1/cart/items/{item_id_a}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert delete_b.status_code == 404

    # Verify Account A's item remains quantity 1
    r_a = client.get("/api/v1/cart", headers={"Authorization": f"Bearer {token_a}"}).json()
    assert len(r_a["items"]) == 1
    assert r_a["items"][0]["quantity"] == 1


# =========================================================================
# 6. CART ITEM MUTATIONS & SETTINGS
# =========================================================================

def test_cart_item_update_and_remove():
    """Test updating quantity to higher, lower, and 0 (delete), as well as explicit remove."""
    token = get_token("account.a@pattyproject.co.uk", "user-account-a")
    headers = {"Authorization": f"Bearer {token}"}

    # Add item
    add_r = client.post("/api/v1/cart/items", headers=headers, json={
        "product_id": "prod-mc-project",
        "quantity": 1
    }).json()
    item_id = add_r["items"][0]["id"]

    # Update quantity to 4
    u_r = client.patch(f"/api/v1/cart/items/{item_id}", headers=headers, json={"quantity": 4}).json()
    assert u_r["items"][0]["quantity"] == 4

    # Update quantity to 0 -> item deleted
    del_r = client.patch(f"/api/v1/cart/items/{item_id}", headers=headers, json={"quantity": 0}).json()
    assert len(del_r["items"]) == 0

    # Add again and clear cart
    client.post("/api/v1/cart/items", headers=headers, json={"product_id": "prod-bacon-burger", "quantity": 2})
    clear_r = client.post("/api/v1/cart/clear", headers=headers).json()
    assert len(clear_r["items"]) == 0


def test_cart_settings_update():
    """Test updating branch and order type."""
    token = get_token("account.a@pattyproject.co.uk", "user-account-a")
    headers = {"Authorization": f"Bearer {token}"}

    r = client.patch("/api/v1/cart/settings", headers=headers, json={
        "branch_id": "branch-camden-001",
        "order_type": "DELIVERY",
        "coupon_code": "WELCOME10"
    }).json()
    assert r["branch_id"] == "branch-camden-001"
    assert r["order_type"] == "DELIVERY"
    assert r["coupon_code"] == "WELCOME10"


def test_forged_user_id_in_request_body_is_ignored():
    """
    If a malicious client sends user_id='user-account-b' in the request body while authenticated as Account A,
    the cart must STILL belong to Account A and Account B's cart must NOT be touched.
    """
    token_a = get_token("account.a@pattyproject.co.uk", "user-account-a")
    token_b = get_token("account.b@pattyproject.co.uk", "user-account-b")

    # Malicious request by Account A attempting to inject Account B's ID
    resp = client.post(
        "/api/v1/cart/items",
        headers={"Authorization": f"Bearer {token_a}"},
        json={
            "product_id": "prod-mc-project",
            "quantity": 2,
            "user_id": "user-account-b"  # Forged user ID
        }
    )
    assert resp.status_code == 200
    assert resp.json()["user_id"] == "user-account-a"

    # Verify Account B's cart is still empty
    r_b = client.get("/api/v1/cart", headers={"Authorization": f"Bearer {token_b}"}).json()
    assert r_b["items"] == []

    # Verify Account B's cart is still empty
    r_b = client.get("/api/v1/cart", headers={"Authorization": f"Bearer {token_b}"}).json()
    assert r_b["items"] == []


def test_concurrent_cart_creation_thread_safety(tmp_path):
    """
    Concurrency Race Condition Test:
    Simultaneously issue 4 concurrent requests trying to resolve/create the cart for the same user.
    Verifies that all threads resolve cleanly without duplicate carts or unhandled errors.
    """
    db_file = tmp_path / "cart_concurrency.db"
    concurrency_engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False, "timeout": 30.0}
    )
    Base.metadata.create_all(bind=concurrency_engine)
    ConcSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=concurrency_engine)

    from app.services.cart_service import get_or_create_cart

    # Seed test user
    seed_session = ConcSessionLocal()
    try:
        user = User(
            id="conc-user-123",
            email="conc@patty.co.uk",
            password_hash="pw",
            full_name="Conc User",
            role=UserRole.CUSTOMER,
            is_active=True
        )
        seed_session.add(user)
        seed_session.commit()
    finally:
        seed_session.close()

    results = []
    errors = []

    def worker():
        session = ConcSessionLocal()
        try:
            cart = get_or_create_cart(session, user_id="conc-user-123")
            results.append(cart.id)
        except Exception as e:
            errors.append(e)
        finally:
            session.close()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All threads must succeed and return the exact same cart ID
    assert len(errors) == 0
    assert len(results) == 4
    assert len(set(results)) == 1

    # Verify exactly 1 cart in database
    verify_session = ConcSessionLocal()
    try:
        carts = verify_session.query(Cart).filter(Cart.user_id == "conc-user-123").all()
        assert len(carts) == 1
    finally:
        verify_session.close()

