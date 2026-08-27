import pytest
import uuid
from app.tests.db import client, reset_test_db, TestingSessionLocal
from app.models.user import User, UserRole
from app.models.product import Category, Product, ProductModifier, Inventory
from app.models.order import Order, OrderItem, OrderStatus, PaymentStatus, OrderType
from app.models.branch import Branch
from app.core.security import create_access_token

@pytest.fixture(autouse=True)
def setup_db():
    reset_test_db()
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_product_deletion_safety(setup_db):
    db_session = setup_db

    # Create a test category
    cat_id = str(uuid.uuid4())
    cat = Category(
        id=cat_id,
        name="Test Burgers",
        slug=f"test-burgers-{uuid.uuid4().hex[:6]}",
        is_active=True
    )
    db_session.add(cat)

    # Create Admin User
    admin_id = str(uuid.uuid4())
    admin_user = User(
        id=admin_id,
        email=f"admin-{uuid.uuid4().hex[:6]}@pattyproject.co.uk",
        password_hash="fakehashadmin",
        full_name="Admin Test",
        role=UserRole.SUPER_ADMIN,
        is_active=True
    )
    db_session.add(admin_user)

    # Create Customer User
    cust_id = str(uuid.uuid4())
    cust_user = User(
        id=cust_id,
        email=f"cust-{uuid.uuid4().hex[:6]}@example.com",
        password_hash="fakehashcust",
        full_name="Customer Test",
        role=UserRole.CUSTOMER,
        is_active=True
    )
    db_session.add(cust_user)

    # Create Branch
    branch_id = str(uuid.uuid4())
    branch = Branch(
        id=branch_id,
        name="Test Branch Delete",
        code=f"TB{uuid.uuid4().hex[:4].upper()}",
        address_line1="123 High Street",
        postcode="SW1A 1AA",
        latitude=51.5,
        longitude=-0.1,
        is_active=True
    )
    db_session.add(branch)

    # Product 1: No orders -> Should Hard Delete
    prod1_id = str(uuid.uuid4())
    prod1 = Product(
        id=prod1_id,
        category_id=cat_id,
        name="Delete Me Hard",
        sku=f"DEL-HARD-{uuid.uuid4().hex[:6]}",
        base_price=9.99,
        is_active=True
    )
    db_session.add(prod1)

    # Product 2: Has historical order -> Should Safe Soft-Delete / Archive
    prod2_id = str(uuid.uuid4())
    prod2 = Product(
        id=prod2_id,
        category_id=cat_id,
        name="Historical Ordered Burger",
        sku=f"HIST-{uuid.uuid4().hex[:6]}",
        base_price=12.50,
        is_active=True
    )
    db_session.add(prod2)
    db_session.commit()

    # Create Historical Order referencing Product 2
    order_id = str(uuid.uuid4())
    order = Order(
        id=order_id,
        order_number=f"#PP{uuid.uuid4().hex[:4].upper()}",
        customer_id=cust_id,
        customer_name="Customer Test",
        customer_email="cust@example.com",
        customer_phone="07123456789",
        branch_id=branch_id,
        order_type=OrderType.DELIVERY,
        status=OrderStatus.DELIVERED,
        subtotal=12.50,
        total_amount=12.50,
        payment_status=PaymentStatus.PAID
    )
    db_session.add(order)

    order_item = OrderItem(
        id=str(uuid.uuid4()),
        order_id=order_id,
        product_id=prod2_id,
        product_name="Historical Ordered Burger",
        quantity=1,
        unit_price=12.50,
        total_price=12.50
    )
    db_session.add(order_item)
    db_session.commit()

    # Generate Tokens
    admin_token = create_access_token(subject=admin_id, roles=[UserRole.SUPER_ADMIN])
    cust_token = create_access_token(subject=cust_id, roles=[UserRole.CUSTOMER])

    # 1. Non-admin (Customer) attempts delete -> MUST be 403 Forbidden
    res_unauth = client.delete(
        f"/api/v1/products/{prod1_id}",
        headers={"Authorization": f"Bearer {cust_token}"}
    )
    assert res_unauth.status_code == 403

    # 2. Admin deletes Product 1 (No orders) -> Hard Deleted
    res_del1 = client.delete(
        f"/api/v1/products/{prod1_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_del1.status_code == 200
    assert db_session.query(Product).filter(Product.id == prod1_id).first() is None

    # 3. Admin deletes Product 2 (Has Historical Orders) -> Safe Archived without DB error
    res_del2 = client.delete(
        f"/api/v1/products/{prod2_id}",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert res_del2.status_code == 200
    
    # Verify Product 2 is marked inactive (archived)
    p2_db = db_session.query(Product).filter(Product.id == prod2_id).first()
    assert p2_db is not None
    assert p2_db.is_active is False

    # Verify historical order and order item are 100% INTACT
    order_db = db_session.query(Order).filter(Order.id == order_id).first()
    assert order_db is not None
    assert len(order_db.items) == 1
    assert order_db.items[0].product_name == "Historical Ordered Burger"
    assert order_db.items[0].total_price == 12.50

    # 4. Verify GET /api/v1/products does NOT return deactivated Product 2
    res_list = client.get("/api/v1/products")
    assert res_list.status_code == 200
    active_ids = [p["id"] for p in res_list.json()]
    assert prod1_id not in active_ids
    assert prod2_id not in active_ids
