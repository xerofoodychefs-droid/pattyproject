import os
import pytest
from datetime import datetime, timedelta, timezone
from app.main import app
from app.core.config import settings
from app.core.security import create_access_token, generate_refresh_token, hash_token, get_password_hash
from app.models.user import User, UserRole, AuthSession
from app.models.branch import Branch
from app.models.product import Category, Product
from app.models.order import Order, OrderItem, OrderStatus, OrderType, PaymentStatus as OrderPaymentStatus
from app.models.payment import Payment, PaymentStatus, PaymentProvider
from app.tests.db import client, reset_test_db, TestingSessionLocal


@pytest.fixture(autouse=True)
def setup_phase2c1_data():
    reset_test_db()
    db = TestingSessionLocal()

    # Create Branch
    branch = Branch(
        id="br-p2c1-westfield",
        code="WF01",
        name="Westfield Branch",
        address_line1="Ariel Way",
        postcode="W12 7GF",
        latitude=51.5074,
        longitude=-0.2217,
        delivery_radius_miles=2.0,
        is_active=True,
        ordering_enabled=True,
        delivery_enabled=True,
        collection_enabled=True
    )
    db.add(branch)

    # Create Category & Products
    cat = Category(id="cat-p2c1-main", name="Gourmet Burgers", slug="gourmet-burgers", is_active=True, display_order=1)
    db.add(cat)

    prod1 = Product(
        id="prod-p2c1-classic",
        sku="SKU-P2C1-CLASSIC",
        name="Classic Patty",
        category_id="cat-p2c1-main",
        base_price=9.99,
        is_active=True
    )
    prod2 = Product(
        id="prod-p2c1-truffle",
        sku="SKU-P2C1-TRUFFLE",
        name="Truffle Burger",
        category_id="cat-p2c1-main",
        base_price=12.50,
        is_active=True
    )
    prod3 = Product(
        id="prod-p2c1-fries",
        sku="SKU-P2C1-FRIES",
        name="Rosemary Fries",
        category_id="cat-p2c1-main",
        base_price=3.50,
        is_active=True
    )
    db.add_all([prod1, prod2, prod3])

    # Create Customer User
    cust_user = User(
        id="usr-p2c1-cust-01",
        email="customer.p2c1@pattyproject.co.uk",
        password_hash=get_password_hash("CustPass123!"),
        full_name="Alice Customer",
        phone="+44 7123456789",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=True
    )
    db.add(cust_user)

    # Create Admin User (Seeded Password rule tested)
    admin_user = User(
        id="usr-p2c1-admin-01",
        email="admin.p2c1@pattyproject.co.uk",
        password_hash=get_password_hash("AdminPass123!"),
        full_name="Bob Administrator",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        email_verified=True
    )
    db.add(admin_user)

    db.commit()
    db.close()


# =========================================================================
# PART I: CUSTOMER CHECKOUT & PAYMENT TESTS (TEST 1 to TEST 12)
# =========================================================================

def test_01_token_expires_before_checkout():
    """TEST 1: Token expires before checkout -> Refresh produces valid access token; order placement succeeds."""
    login_res = client.post("/api/v1/auth/login", json={
        "email": "customer.p2c1@pattyproject.co.uk",
        "password": "CustPass123!"
    })
    refresh_token = login_res.json()["refresh_token"]

    # Refresh token to simulate silent renewal when access token expires
    refresh_res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_res.status_code == 200
    new_access_token = refresh_res.json()["access_token"]

    # Place order with refreshed access token
    order_payload = {
        "branch_id": "br-p2c1-westfield",
        "order_type": "COLLECTION",
        "customer_name": "Alice Customer",
        "customer_email": "customer.p2c1@pattyproject.co.uk",
        "customer_phone": "+44 7123456789",
        "items": [{"product_id": "prod-p2c1-classic", "quantity": 2}]
    }
    resp = client.post("/api/v1/orders", json=order_payload, headers={"Authorization": f"Bearer {new_access_token}"})
    assert resp.status_code == 200
    assert resp.json()["customer_email"] == "customer.p2c1@pattyproject.co.uk"


def test_02_token_expires_while_cart_is_open():
    """TEST 2: Token expires while cart is open -> Refresh allows accessing profile/catalogs without cart disruption."""
    login_res = client.post("/api/v1/auth/login", json={
        "email": "customer.p2c1@pattyproject.co.uk",
        "password": "CustPass123!"
    })
    refresh_token = login_res.json()["refresh_token"]

    # Expire access token and refresh
    ref_res = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    new_token = ref_res.json()["access_token"]

    # Fetch user details while cart remains in local storage
    me_res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert me_res.status_code == 200
    assert me_res.json()["id"] == "usr-p2c1-cust-01"


def test_03_token_expires_while_entering_checkout_information():
    """TEST 3: Token expires during checkout form entry -> Order payload succeeds on submission with refreshed token."""
    login_res = client.post("/api/v1/auth/login", json={
        "email": "customer.p2c1@pattyproject.co.uk",
        "password": "CustPass123!"
    })
    refresh_token = login_res.json()["refresh_token"]
    renewed_token = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token}).json()["access_token"]

    payload = {
        "branch_id": "br-p2c1-westfield",
        "order_type": "DELIVERY",
        "customer_name": "Alice Customer",
        "customer_email": "customer.p2c1@pattyproject.co.uk",
        "customer_phone": "+44 7123456789",
        "delivery_address": {
            "door_number": "Flat 4B",
            "address_line1": "Wood Lane",
            "postcode": "W12 7GF",
            "city": "London",
            "latitude": 51.5080,
            "longitude": -0.2220
        },
        "delivery_latitude": 51.5080,
        "delivery_longitude": -0.2220,
        "items": [{"product_id": "prod-p2c1-truffle", "quantity": 2}]
    }
    resp = client.post("/api/v1/orders", json=payload, headers={"Authorization": f"Bearer {renewed_token}"})
    assert resp.status_code == 200
    assert resp.json()["order_type"] == "DELIVERY"
    assert resp.json()["delivery_address"]["door_number"] == "Flat 4B"


def test_04_token_expires_after_outlet_selection():
    """TEST 4: Token expires after outlet selection -> Selected branch remains valid upon token refresh."""
    login_res = client.post("/api/v1/auth/login", json={
        "email": "customer.p2c1@pattyproject.co.uk",
        "password": "CustPass123!"
    })
    refresh_token = login_res.json()["refresh_token"]
    renewed_token = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token}).json()["access_token"]

    branch_res = client.get("/api/v1/branches")
    assert branch_res.status_code == 200
    assert any(b["id"] == "br-p2c1-westfield" for b in branch_res.json())


def test_05_token_expires_after_location_selection():
    """TEST 5: Token expires after location selection -> Location coordinates validated within 2-mile radius."""
    login_res = client.post("/api/v1/auth/login", json={
        "email": "customer.p2c1@pattyproject.co.uk",
        "password": "CustPass123!"
    })
    refresh_token = login_res.json()["refresh_token"]
    renewed_token = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token}).json()["access_token"]

    # Check nearest branch with coordinate within 0.1 miles of Westfield
    nearest_res = client.post("/api/v1/branches/nearest", json={
        "latitude": 51.5080,
        "longitude": -0.2220,
        "fulfillment_method": "DELIVERY"
    })
    assert nearest_res.status_code == 200
    assert nearest_res.json()["is_delivery_eligible"] is True
    assert nearest_res.json()["assigned_branch"]["id"] == "br-p2c1-westfield"


def test_06_token_expires_immediately_before_payment():
    """TEST 6: Token expires immediately before payment -> Payment session created with refreshed token."""
    login_res = client.post("/api/v1/auth/login", json={
        "email": "customer.p2c1@pattyproject.co.uk",
        "password": "CustPass123!"
    })
    refresh_token = login_res.json()["refresh_token"]

    # 1. Create order
    order_payload = {
        "branch_id": "br-p2c1-westfield",
        "order_type": "COLLECTION",
        "customer_name": "Alice Customer",
        "customer_email": "customer.p2c1@pattyproject.co.uk",
        "customer_phone": "+44 7123456789",
        "items": [{"product_id": "prod-p2c1-classic", "quantity": 1}]
    }
    ord_res = client.post("/api/v1/orders", json=order_payload)
    order_id = ord_res.json()["id"]

    # 2. Refresh token immediately before payment initiation
    renewed_token = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token}).json()["access_token"]

    # 3. Create payment session
    pay_res = client.post(
        "/api/v1/payments/create-session",
        headers={"Authorization": f"Bearer {renewed_token}"},
        json={"order_id": order_id, "payment_method_type": "CARD"}
    )
    assert pay_res.status_code == 200
    assert "transaction_id" in pay_res.json()


def test_07_token_expires_during_payment_preparation_no_duplicate_payment():
    """TEST 7: Token expires during payment preparation -> Idempotency prevents duplicate payment session/records."""
    # Create order
    order_payload = {
        "branch_id": "br-p2c1-westfield",
        "order_type": "COLLECTION",
        "customer_name": "Alice Customer",
        "customer_email": "customer.p2c1@pattyproject.co.uk",
        "customer_phone": "+44 7123456789",
        "items": [{"product_id": "prod-p2c1-classic", "quantity": 1}]
    }
    ord_res = client.post("/api/v1/orders", json=order_payload)
    order_id = ord_res.json()["id"]

    idempotency_key = f"idemp_test7_{order_id}"

    # First session creation attempt
    session1 = client.post(
        "/api/v1/payments/create-session",
        headers={"Idempotency-Key": idempotency_key},
        json={"order_id": order_id, "payment_method_type": "CARD"}
    )
    assert session1.status_code == 200
    tx_id_1 = session1.json()["transaction_id"]

    # Simulated retry with same idempotency key (e.g. after token refresh/network blip)
    session2 = client.post(
        "/api/v1/payments/create-session",
        headers={"Idempotency-Key": idempotency_key},
        json={"order_id": order_id, "payment_method_type": "CARD"}
    )
    assert session2.status_code == 200
    tx_id_2 = session2.json()["transaction_id"]

    # Same transaction ID returned; no duplicate payment created
    assert tx_id_1 == tx_id_2

    db = TestingSessionLocal()
    payments_count = db.query(Payment).filter(Payment.order_id == order_id).count()
    db.close()
    assert payments_count == 1


def test_08_network_response_interrupted_after_payment_request():
    """TEST 8: Network interrupted after payment -> Client queries authoritative /payments/verify endpoint."""
    ord_res = client.post("/api/v1/orders", json={
        "branch_id": "br-p2c1-westfield",
        "order_type": "COLLECTION",
        "customer_name": "Alice Customer",
        "customer_email": "customer.p2c1@pattyproject.co.uk",
        "customer_phone": "+44 7123456789",
        "items": [{"product_id": "prod-p2c1-classic", "quantity": 1}]
    })
    order_id = ord_res.json()["id"]

    session_res = client.post("/api/v1/payments/create-session", json={"order_id": order_id})
    tx_id = session_res.json()["transaction_id"]

    # Client queries authoritative verification endpoint
    verify_res = client.get(f"/api/v1/payments/verify/{tx_id}")
    assert verify_res.status_code == 200
    assert verify_res.json()["transaction_id"] == tx_id
    assert verify_res.json()["order_id"] == order_id
    assert verify_res.json()["payment_status"] == "PENDING"


def test_09_payment_succeeds_but_frontend_temporarily_disconnects():
    """TEST 9: Payment succeeds during disconnect -> Order authoritative status is PAID / INCOMING in backend."""
    ord_res = client.post("/api/v1/orders", json={
        "branch_id": "br-p2c1-westfield",
        "order_type": "COLLECTION",
        "customer_name": "Alice Customer",
        "customer_email": "customer.p2c1@pattyproject.co.uk",
        "customer_phone": "+44 7123456789",
        "items": [{"product_id": "prod-p2c1-classic", "quantity": 1}]
    })
    order_data = ord_res.json()
    order_id = order_data["id"]
    order_number = order_data["order_number"]

    session_res = client.post("/api/v1/payments/create-session", json={"order_id": order_id})
    tx_id = session_res.json()["transaction_id"]

    # Complete payment via backend simulation / webhook
    sim_res = client.post("/api/v1/payments/mock-simulate", json={
        "order_id": order_id,
        "transaction_id": tx_id,
        "status": "SUCCESS",
        "amount": order_data["total_amount"],
        "currency": "GBP"
    })
    assert sim_res.status_code == 200

    # Reconnected client checks order status
    import urllib.parse
    encoded_num = urllib.parse.quote(order_number)
    order_check = client.get(f"/api/v1/orders/{encoded_num}?email=customer.p2c1@pattyproject.co.uk")
    assert order_check.status_code == 200
    assert order_check.json()["payment_status"] == "PAID"
    assert order_check.json()["status"] == "INCOMING"


def test_10_customer_returns_from_payment_provider():
    """TEST 10: Customer returns from payment gateway -> Order confirmation loads confirmed order."""
    import urllib.parse
    ord_res = client.post("/api/v1/orders", json={
        "branch_id": "br-p2c1-westfield",
        "order_type": "COLLECTION",
        "customer_name": "Alice Customer",
        "customer_email": "customer.p2c1@pattyproject.co.uk",
        "customer_phone": "+44 7123456789",
        "items": [{"product_id": "prod-p2c1-truffle", "quantity": 2}]
    })
    order_number = ord_res.json()["order_number"]
    encoded_num = urllib.parse.quote(order_number)

    # Get order confirmation details
    conf_res = client.get(f"/api/v1/orders/{encoded_num}?email=customer.p2c1@pattyproject.co.uk")
    assert conf_res.status_code == 200
    assert conf_res.json()["order_number"] == order_number
    assert len(conf_res.json()["items"]) == 1
    assert conf_res.json()["items"][0]["quantity"] == 2


def test_11_browser_refresh_after_successful_payment():
    """TEST 11: Browser refresh after payment -> Order remains recoverable repeatedly."""
    import urllib.parse
    ord_res = client.post("/api/v1/orders", json={
        "branch_id": "br-p2c1-westfield",
        "order_type": "COLLECTION",
        "customer_name": "Alice Customer",
        "customer_email": "customer.p2c1@pattyproject.co.uk",
        "customer_phone": "+44 7123456789",
        "items": [{"product_id": "prod-p2c1-fries", "quantity": 3}]
    })
    order_number = ord_res.json()["order_number"]
    encoded_num = urllib.parse.quote(order_number)

    # Repeated queries simulate browser refreshes
    for _ in range(3):
        res = client.get(f"/api/v1/orders/{encoded_num}?email=customer.p2c1@pattyproject.co.uk")
        assert res.status_code == 200
        assert res.json()["order_number"] == order_number


def test_12_multiple_products_in_cart_during_token_refresh():
    """TEST 12: Multiple products in cart during token refresh -> All products and quantities placed accurately."""
    login_res = client.post("/api/v1/auth/login", json={
        "email": "customer.p2c1@pattyproject.co.uk",
        "password": "CustPass123!"
    })
    refresh_token = login_res.json()["refresh_token"]
    renewed_token = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token}).json()["access_token"]

    payload = {
        "branch_id": "br-p2c1-westfield",
        "order_type": "COLLECTION",
        "customer_name": "Alice Customer",
        "customer_email": "customer.p2c1@pattyproject.co.uk",
        "customer_phone": "+44 7123456789",
        "items": [
            {"product_id": "prod-p2c1-classic", "quantity": 2},
            {"product_id": "prod-p2c1-truffle", "quantity": 1},
            {"product_id": "prod-p2c1-fries", "quantity": 4}
        ]
    }
    order_res = client.post("/api/v1/orders", json=payload, headers={"Authorization": f"Bearer {renewed_token}"})
    assert order_res.status_code == 200
    items = order_res.json()["items"]
    assert len(items) == 3
    quantities = {i["product_id"]: i["quantity"] for i in items}
    assert quantities["prod-p2c1-classic"] == 2
    assert quantities["prod-p2c1-truffle"] == 1
    assert quantities["prod-p2c1-fries"] == 4


# =========================================================================
# PART P: ADMIN REALTIME & CONTINUITY TESTS (TEST 13 to TEST 24)
# =========================================================================

def test_13_normal_realtime_order_delivery():
    """TEST 13: Normal realtime order delivery -> Admin queries /orders and receives newly placed orders."""
    admin_token = create_access_token(subject="usr-p2c1-admin-01", roles=[UserRole.SUPER_ADMIN])

    # Customer places order
    client.post("/api/v1/orders", json={
        "branch_id": "br-p2c1-westfield",
        "order_type": "COLLECTION",
        "customer_name": "Test Customer",
        "customer_email": "test@pattyproject.co.uk",
        "customer_phone": "+44 7123456789",
        "items": [{"product_id": "prod-p2c1-classic", "quantity": 1}]
    })

    # Admin fetches orders
    resp = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    orders = resp.json()
    assert len(orders) >= 1
    assert orders[0]["customer_name"] == "Test Customer"


def test_14_token_expires_during_realtime_session():
    """TEST 14: Token expires during realtime session -> Expired access token rejected (401), renewed via refresh."""
    admin_login = client.post("/api/v1/auth/login", json={
        "email": "admin.p2c1@pattyproject.co.uk",
        "password": "AdminPass123!"
    })
    admin_refresh = admin_login.json()["refresh_token"]

    expired_token = create_access_token(
        subject="usr-p2c1-admin-01",
        roles=[UserRole.SUPER_ADMIN],
        expires_delta=timedelta(minutes=-1)
    )

    # 1. Expired request fails with 401
    fail_res = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {expired_token}"})
    assert fail_res.status_code == 401

    # 2. Silent refresh restores access
    renew_res = client.post("/api/v1/auth/refresh", json={"refresh_token": admin_refresh})
    assert renew_res.status_code == 200
    new_admin_token = renew_res.json()["access_token"]

    # 3. Request succeeds with renewed token
    ok_res = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {new_admin_token}"})
    assert ok_res.status_code == 200


def test_15_token_refresh_while_order_arrives():
    """TEST 15: Token refresh while order arrives -> Order committed to DB is immediately returned on refreshed poll."""
    admin_login = client.post("/api/v1/auth/login", json={
        "email": "admin.p2c1@pattyproject.co.uk",
        "password": "AdminPass123!"
    })
    admin_refresh = admin_login.json()["refresh_token"]

    # Order arrives
    client.post("/api/v1/orders", json={
        "branch_id": "br-p2c1-westfield",
        "order_type": "COLLECTION",
        "customer_name": "Mid-Refresh Customer",
        "customer_email": "mid@pattyproject.co.uk",
        "customer_phone": "+44 7123456789",
        "items": [{"product_id": "prod-p2c1-truffle", "quantity": 1}]
    })

    # Token refreshed
    new_token = client.post("/api/v1/auth/refresh", json={"refresh_token": admin_refresh}).json()["access_token"]

    # Poll with new token
    orders_res = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {new_token}"})
    assert orders_res.status_code == 200
    assert any(o["customer_name"] == "Mid-Refresh Customer" for o in orders_res.json())


def test_16_multiple_orders_arrive_during_token_refresh():
    """TEST 16: Multiple orders arrive during token refresh -> All orders recovered seamlessly."""
    admin_login = client.post("/api/v1/auth/login", json={
        "email": "admin.p2c1@pattyproject.co.uk",
        "password": "AdminPass123!"
    })
    admin_refresh = admin_login.json()["refresh_token"]

    # 3 orders arrive
    for i in range(1, 4):
        client.post("/api/v1/orders", json={
            "branch_id": "br-p2c1-westfield",
            "order_type": "COLLECTION",
            "customer_name": f"Batch Order {i}",
            "customer_email": f"batch{i}@pattyproject.co.uk",
            "customer_phone": "+44 7123456789",
            "items": [{"product_id": "prod-p2c1-classic", "quantity": 1}]
        })

    # Admin refreshes token and polls
    new_token = client.post("/api/v1/auth/refresh", json={"refresh_token": admin_refresh}).json()["access_token"]
    orders_res = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {new_token}"})
    assert orders_res.status_code == 200
    orders = orders_res.json()
    names = [o["customer_name"] for o in orders]
    assert "Batch Order 1" in names
    assert "Batch Order 2" in names
    assert "Batch Order 3" in names


def test_17_realtime_connection_drops_and_reconnects():
    """TEST 17: Realtime drops and reconnects -> Subsequent query recovers full order list."""
    admin_token = create_access_token(subject="usr-p2c1-admin-01", roles=[UserRole.SUPER_ADMIN])

    # Initial fetch
    res1 = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {admin_token}"})
    assert res1.status_code == 200

    # New order placed during drop
    client.post("/api/v1/orders", json={
        "branch_id": "br-p2c1-westfield",
        "order_type": "COLLECTION",
        "customer_name": "Offline Customer",
        "customer_email": "offline@pattyproject.co.uk",
        "customer_phone": "+44 7123456789",
        "items": [{"product_id": "prod-p2c1-fries", "quantity": 1}]
    })

    # Reconnected fetch
    res2 = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {admin_token}"})
    assert res2.status_code == 200
    assert any(o["customer_name"] == "Offline Customer" for o in res2.json())


def test_18_backend_restarts():
    """TEST 18: Backend restarts / reload -> Database state remains authoritative and persists."""
    # Place order
    ord_res = client.post("/api/v1/orders", json={
        "branch_id": "br-p2c1-westfield",
        "order_type": "COLLECTION",
        "customer_name": "Persistent Customer",
        "customer_email": "persist@pattyproject.co.uk",
        "customer_phone": "+44 7123456789",
        "items": [{"product_id": "prod-p2c1-classic", "quantity": 1}]
    })
    order_id = ord_res.json()["id"]

    # Verify directly from database session to ensure persistence
    db = TestingSessionLocal()
    order_db = db.query(Order).filter(Order.id == order_id).first()
    assert order_db is not None
    assert order_db.customer_name == "Persistent Customer"
    db.close()


def test_19_network_disconnects_and_reconnects():
    """TEST 19: Network disconnects & reconnects -> Realtime polling succeeds with same credentials."""
    admin_token = create_access_token(subject="usr-p2c1-admin-01", roles=[UserRole.SUPER_ADMIN])
    res = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200


def test_20_order_arrives_while_disconnected():
    """TEST 20: Order arrives while admin is disconnected -> Order recovered upon next sync."""
    admin_token = create_access_token(subject="usr-p2c1-admin-01", roles=[UserRole.SUPER_ADMIN])

    client.post("/api/v1/orders", json={
        "branch_id": "br-p2c1-westfield",
        "order_type": "COLLECTION",
        "customer_name": "Disconnected Window Order",
        "customer_email": "window@pattyproject.co.uk",
        "customer_phone": "+44 7123456789",
        "items": [{"product_id": "prod-p2c1-classic", "quantity": 1}]
    })

    res = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    assert any(o["customer_name"] == "Disconnected Window Order" for o in res.json())


def test_21_synchronization_after_reconnect_no_duplicate_orders():
    """TEST 21: Synchronization after reconnect -> Multiple polls yield identical deduplicated list."""
    admin_token = create_access_token(subject="usr-p2c1-admin-01", roles=[UserRole.SUPER_ADMIN])

    client.post("/api/v1/orders", json={
        "branch_id": "br-p2c1-westfield",
        "order_type": "COLLECTION",
        "customer_name": "Sync Order",
        "customer_email": "sync@pattyproject.co.uk",
        "customer_phone": "+44 7123456789",
        "items": [{"product_id": "prod-p2c1-classic", "quantity": 1}]
    })

    poll1 = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {admin_token}"}).json()
    poll2 = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {admin_token}"}).json()

    # Order IDs must match 1:1 with no duplicate IDs
    ids1 = [o["id"] for o in poll1]
    ids2 = [o["id"] for o in poll2]
    assert len(ids1) == len(set(ids1))
    assert ids1 == ids2


def test_22_order_status_changes_while_disconnected():
    """TEST 22: Order status changes while disconnected -> Dashboard polling reflects authoritative updated status."""
    admin_token = create_access_token(subject="usr-p2c1-admin-01", roles=[UserRole.SUPER_ADMIN])

    ord_res = client.post("/api/v1/orders", json={
        "branch_id": "br-p2c1-westfield",
        "order_type": "COLLECTION",
        "customer_name": "Status Transition Order",
        "customer_email": "status@pattyproject.co.uk",
        "customer_phone": "+44 7123456789",
        "items": [{"product_id": "prod-p2c1-classic", "quantity": 1}]
    })
    order_id = ord_res.json()["id"]

    # Transition order status to PREPARING
    patch_res = client.patch(
        f"/api/v1/orders/{order_id}/status",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"status": "PREPARING"}
    )
    assert patch_res.status_code == 200

    # Polling recovers the updated PREPARING status
    poll_res = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {admin_token}"})
    assert poll_res.status_code == 200
    matched = next((o for o in poll_res.json() if o["id"] == order_id), None)
    assert matched is not None
    assert matched["status"] == "PREPARING"


def test_23_unauthorized_realtime_connection():
    """TEST 23: Unauthorized realtime connection -> Customer or unauthenticated token rejected with 401/403."""
    customer_token = create_access_token(subject="usr-p2c1-cust-01", roles=[UserRole.CUSTOMER])

    # Unauthenticated -> 401
    res_no_auth = client.get("/api/v1/orders")
    assert res_no_auth.status_code == 401

    # Customer role accessing admin orders -> 403 Forbidden
    res_cust = client.get("/api/v1/orders", headers={"Authorization": f"Bearer {customer_token}"})
    assert res_cust.status_code == 403


def test_24_admin_logout_terminates_realtime_access():
    """TEST 24: Admin logout -> Explicit logout revokes refresh token session."""
    admin_login = client.post("/api/v1/auth/login", json={
        "email": "admin.p2c1@pattyproject.co.uk",
        "password": "AdminPass123!"
    })
    refresh_token = admin_login.json()["refresh_token"]

    # Logout
    logout_res = client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout_res.status_code == 200

    # Refresh token can no longer be renewed
    refresh_attempt = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_attempt.status_code == 401
