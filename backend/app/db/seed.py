import os
from app.core.config import settings
from app.core.database import SessionLocal, engine, Base
from app.core.security import get_password_hash
from app.models import (
    User, UserRole, CustomerAddress,
    Branch, BranchUser,
    Category, Product, ProductModifier, Inventory,
    Order, OrderItem, OrderStatusHistory, OrderStatus, OrderType,
    Payment, PaymentStatus, PaymentProvider,
    LoyaltyAccount, LoyaltyTransaction, LoyaltyReward,
    Coupon, Printer
)

DEV_DEFAULT_ADMIN_PWD = "dev_admin_password_123!"
DEV_DEFAULT_BRANCH_PWD = "dev_branch_password_123!"
DEV_DEFAULT_CUST_PWD = "dev_customer_password_123!"

def ensure_schema_up_to_date(eng):
    from sqlalchemy import inspect, text
    try:
        inspector = inspect(eng)
        existing_tables = inspector.get_table_names()
        with eng.begin() as conn:
            for table_name, table in Base.metadata.tables.items():
                if table_name in existing_tables:
                    existing_cols = {c['name']: c for c in inspector.get_columns(table_name)}
                    for col in table.columns:
                        if col.name not in existing_cols:
                            col_type = col.type.compile(eng.dialect)
                            sql = f'ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type}'
                            conn.execute(text(sql))
    except Exception as e:
        print(f"Warning during schema migration check: {e}")

def seed_db():
    if not settings.is_production:
        Base.metadata.create_all(bind=engine)
    ensure_schema_up_to_date(engine)
    db = SessionLocal()
    
    # Check if database is already seeded
    if db.query(User).filter(User.email == "admin@pattyproject.co.uk").first():
        # Backfill payments and align 0.00 delivery fee for existing orders
        orders = db.query(Order).all()
        for ord in orders:
            if ord.delivery_fee != 0.0:
                ord.delivery_fee = 0.0
                ord.total_amount = round(max(0.0, ord.subtotal - ord.discount_amount + 0.0 + ord.service_fee), 2)
            
            # Ensure payment record exists
            if not ord.payments:
                pm = Payment(
                    order_id=ord.id,
                    provider=PaymentProvider.MOCK,
                    transaction_id=ord.payment_transaction_id or f"TXN_{ord.id[:8].upper()}",
                    amount=ord.total_amount,
                    currency="GBP",
                    status=PaymentStatus.PAID if ord.payment_status == "PAID" else PaymentStatus.PENDING,
                    payment_method_type="CARD"
                )
                db.add(pm)
        # Ensure any legacy admin loyalty accounts have 0 points without deleting immutable audit ledger history
        admin_users = db.query(User).filter(User.role.in_([UserRole.SUPER_ADMIN, UserRole.BRANCH_ADMIN])).all()
        for au in admin_users:
            admin_loyalty = db.query(LoyaltyAccount).filter(LoyaltyAccount.user_id == au.id).first()
            if admin_loyalty and (admin_loyalty.available_points != 0 or admin_loyalty.lifetime_points != 0):
                admin_loyalty.available_points = 0
                admin_loyalty.lifetime_points = 0
                print(f"Sanitized non-customer loyalty balance to 0 for {au.role} {au.email}.")
        db.commit()
        print("Database already seeded. Verified payments, £0.00 delivery fees, and customer-only loyalty accounts.")
        db.close()
        return

    print("Seeding database with Patty Project UK initial data...")

    if settings.is_production:
        admin_pwd = os.getenv("SEED_ADMIN_PASSWORD")
        if not admin_pwd or len(admin_pwd) < 12:
            print("Production environment: Skipping default user creation. Create administrative accounts via CLI or environment variables.")
        else:
            admin_email = os.getenv("SEED_ADMIN_EMAIL", "admin@pattyproject.co.uk")
            if not db.query(User).filter(User.email == admin_email).first():
                admin = User(
                    email=admin_email,
                    password_hash=get_password_hash(admin_pwd),
                    full_name="Super Admin",
                    role=UserRole.SUPER_ADMIN,
                    is_active=True,
                    email_verified=True
                )
                db.add(admin)
                db.commit()
                print(f"Production Super Admin '{admin_email}' seeded securely from environment.")
        db.close()
        return
    else:
        # Development Seeding with environment-overridable credentials
        admin_pwd = os.getenv("SEED_ADMIN_PASSWORD", DEV_DEFAULT_ADMIN_PWD)
        branch_pwd = os.getenv("SEED_BRANCH_PASSWORD", DEV_DEFAULT_BRANCH_PWD)
        cust_pwd = os.getenv("SEED_CUSTOMER_PASSWORD", DEV_DEFAULT_CUST_PWD)

        # 1. Create Super Admin User
        admin = User(
            email="admin@pattyproject.co.uk",
            password_hash=get_password_hash(admin_pwd),
            full_name="Super Admin",
            phone="+44 20 7946 0912",
            role=UserRole.SUPER_ADMIN,
            is_active=True,
            email_verified=True
        )
        db.add(admin)

        # 2. Create Branch Admins
        central_admin = User(
            email="central@pattyproject.co.uk",
            password_hash=get_password_hash(branch_pwd),
            full_name="London Central Admin",
            phone="+44 7700 900111",
            role=UserRole.BRANCH_ADMIN,
            is_active=True,
            email_verified=True
        )
        westfield_admin = User(
            email="westfield@pattyproject.co.uk",
            password_hash=get_password_hash(branch_pwd),
            full_name="London Westfield Admin",
            phone="+44 7700 900222",
            role=UserRole.BRANCH_ADMIN,
            is_active=True,
            email_verified=True
        )
        db.add_all([central_admin, westfield_admin])

        # 3. Create Sample Customer Users
        customer = User(
            email="john.smith@email.com",
            password_hash=get_password_hash(cust_pwd),
            full_name="John Smith",
            phone="+44 7123 456789",
            role=UserRole.CUSTOMER,
            is_active=True,
            email_verified=True
        )
        customer2 = User(
            email="johnsmith@email.com",
            password_hash=get_password_hash(cust_pwd),
            full_name="John Smith",
            phone="+44 7123 456789",
            role=UserRole.CUSTOMER,
            is_active=True,
            email_verified=True
        )
        db.add_all([customer, customer2])
        db.flush()

    # 4. Create Saved Delivery Addresses for Customers
    addr1 = CustomerAddress(
        user_id=customer.id,
        address_line1="123 Baker Street",
        address_line2="Flat 4B",
        city="London",
        postcode="NW1 6XE",
        label="Home",
        is_default=True
    )
    addr2 = CustomerAddress(
        user_id=customer.id,
        address_line1="45 Oxford Street",
        address_line2="",
        city="London",
        postcode="W1D 2DZ",
        label="Work",
        is_default=False
    )
    db.add_all([addr1, addr2])

    # 5. Create UK Branches
    branch_central = Branch(
        name="Patty Project - Central London",
        code="PP-LDN-01",
        address_line1="10-12 Russell Street, Covent Garden, London",
        city="London",
        postcode="WC2B 5HZ",
        phone="+44 20 7123 4567",
        latitude=51.5126,
        longitude=-0.1215,
        delivery_enabled=True,
        collection_enabled=True,
        ordering_enabled=True,
        delivery_radius_miles=2.0,
        is_active=True,
        opening_hours={
            "monday": {"open": "11:00", "close": "23:00"},
            "tuesday": {"open": "11:00", "close": "23:00"},
            "wednesday": {"open": "11:00", "close": "23:00"},
            "thursday": {"open": "11:00", "close": "23:00"},
            "friday": {"open": "11:00", "close": "00:00"},
            "saturday": {"open": "11:00", "close": "00:00"},
            "sunday": {"open": "12:00", "close": "22:00"}
        }
    )

    branch_westfield = Branch(
        name="Patty Project - Westfield Stratford",
        code="PP-LDN-02",
        address_line1="The Arcade, Westfield Stratford City, London",
        city="London",
        postcode="E20 1EQ",
        phone="+44 20 8987 6543",
        latitude=51.5434,
        longitude=-0.0072,
        delivery_enabled=True,
        collection_enabled=True,
        ordering_enabled=True,
        delivery_radius_miles=2.0,
        is_active=True,
        opening_hours={
            "monday": {"open": "11:30", "close": "22:30"},
            "tuesday": {"open": "11:30", "close": "22:30"},
            "wednesday": {"open": "11:30", "close": "22:30"},
            "thursday": {"open": "11:30", "close": "22:30"},
            "friday": {"open": "11:30", "close": "23:30"},
            "saturday": {"open": "11:30", "close": "23:30"},
            "sunday": {"open": "12:00", "close": "21:30"}
        }
    )
    db.add_all([branch_central, branch_westfield])
    db.flush()

    # Assign branch admins
    db.add_all([
        BranchUser(user_id=central_admin.id, branch_id=branch_central.id),
        BranchUser(user_id=westfield_admin.id, branch_id=branch_westfield.id)
    ])

    # 6. Create Menu Categories
    cat_burgers = Category(name="Gourmet Burgers", slug="gourmet-burgers", display_order=1)
    cat_chicken = Category(name="Crispy Chicken", slug="crispy-chicken", display_order=2)
    cat_sides = Category(name="Loaded Sides", slug="loaded-sides", display_order=3)
    cat_shakes = Category(name="Craft Shakes", slug="craft-shakes", display_order=4)
    cat_drinks = Category(name="Drinks", slug="drinks", display_order=5)
    cat_sauces = Category(name="House Dips", slug="house-dips", display_order=6)
    db.add_all([cat_burgers, cat_chicken, cat_sides, cat_shakes, cat_drinks, cat_sauces])
    db.flush()

    # 7. Create Products
    p1 = Product(
        category_id=cat_burgers.id,
        name="Classic Beef Burger",
        sku="BURGER-CLASSIC",
        short_description="Dry-aged prime beef patty, American cheddar, crispy lettuce, tomato, pickles & signature Patty sauce in toasted brioche.",
        base_price=8.99,
        image_url="/images/products/classic-burger.jpg",
        is_active=True,
        is_bestseller=True
    )
    p2 = Product(
        category_id=cat_burgers.id,
        name="Double Patty Smash",
        sku="BURGER-DOUBLE-SMASH",
        short_description="Two 3.5oz dry-aged beef patties smashed ultra-crispy, double American cheese, caramelized onions & smoky mayo.",
        base_price=11.95,
        image_url="/images/products/double-smash.jpg",
        is_active=True,
        is_bestseller=True
    )
    p3 = Product(
        category_id=cat_chicken.id,
        name="Spicy Nashville Chicken",
        sku="CHICKEN-NASHVILLE",
        short_description="Buttermilk fried chicken breast dipped in Nashville hot oil, topped with sweet slaw, dill pickles & garlic aioli.",
        base_price=9.45,
        image_url="/images/products/nashville-chicken.jpg",
        is_active=True,
        is_bestseller=True
    )
    p4 = Product(
        category_id=cat_burgers.id,
        name="Truffle Mushroom Burger",
        sku="BURGER-TRUFFLE",
        short_description="Beef patty topped with Swiss cheese, sautéed garlic butter mushrooms and rich black truffle mayo.",
        base_price=10.95,
        image_url="/images/products/truffle-burger.jpg",
        is_active=True,
        is_bestseller=False
    )
    p5 = Product(
        category_id=cat_sides.id,
        name="French Fries (Regular)",
        sku="SIDE-FRIES-REG",
        short_description="Crispy golden skin-on fries seasoned with sea salt and rosemary dust.",
        base_price=2.49,
        image_url="/images/products/fries.jpg",
        is_active=True,
        is_bestseller=False
    )
    p6 = Product(
        category_id=cat_sides.id,
        name="Loaded Cheesy Bacon Fries",
        sku="SIDE-LOADED-FRIES",
        short_description="Fries smothered in warm cheese sauce, crispy beef bacon bits and diced jalapeños.",
        base_price=6.45,
        image_url="/images/products/loaded-fries.jpg",
        is_active=True,
        is_bestseller=True
    )
    p7 = Product(
        category_id=cat_drinks.id,
        name="Coca Cola 500ml",
        sku="DRINK-COKE-500ML",
        short_description="Chilled 500ml Coca-Cola bottle.",
        base_price=1.59,
        image_url="/images/products/coke.jpg",
        is_active=True,
        is_bestseller=False
    )
    db.add_all([p1, p2, p3, p4, p5, p6, p7])
    db.flush()

    # 8. Modifiers for Products
    db.add_all([
        ProductModifier(product_id=p1.id, name="Extra Cheddar Slice", price=0.80, is_active=True),
        ProductModifier(product_id=p1.id, name="Crispy Beef Bacon", price=1.50, is_active=True),
        ProductModifier(product_id=p1.id, name="Jalapeño Slices", price=0.50, is_active=True),
        ProductModifier(product_id=p2.id, name="Extra Beef Patty", price=3.00, is_active=True),
        ProductModifier(product_id=p2.id, name="Fried Egg", price=1.20, is_active=True),
        ProductModifier(product_id=p3.id, name="Extra Hot Sauce", price=0.50, is_active=True)
    ])

    # 9. Loyalty Accounts
    loyalty_c1 = LoyaltyAccount(user_id=customer.id, available_points=450, lifetime_points=1200, tier="SILVER")
    loyalty_c2 = LoyaltyAccount(user_id=customer2.id, available_points=210, lifetime_points=500, tier="BRONZE")
    db.add_all([loyalty_c1, loyalty_c2])
    db.flush()

    # Loyalty Rewards
    r1 = LoyaltyReward(title="Free Regular Fries", points_required=150, reward_type="FREE_ITEM", product_id=p5.id, is_active=True)
    r2 = LoyaltyReward(title="£5 Voucher", points_required=300, reward_type="DISCOUNT_FIXED", discount_value=5.00, is_active=True)
    r3 = LoyaltyReward(title="Free Classic Burger", points_required=500, reward_type="FREE_ITEM", product_id=p1.id, is_active=True)
    db.add_all([r1, r2, r3])

    # 10. Promotional Coupons
    cpn1 = Coupon(code="PATTY10", name="10% off entire order", coupon_type="PERCENTAGE", discount_value=10.0, min_order_value=15.0, is_active=True)
    cpn2 = Coupon(code="BURGER5", name="£5 off orders over £25", coupon_type="FIXED_AMOUNT", discount_value=5.0, min_order_value=25.0, is_active=True)
    cpn3 = Coupon(code="FREESHIP", name="Free delivery promotion", coupon_type="FREE_SHIPPING", discount_value=0.0, min_order_value=0.0, is_active=True)
    db.add_all([cpn1, cpn2, cpn3])

    # 11. Printers
    printer1 = Printer(branch_id=branch_central.id, name="Central Kitchen Receipt Printer", ip_address="192.168.1.201", is_active=True)
    printer2 = Printer(branch_id=branch_westfield.id, name="Westfield Kitchen Printer", ip_address="192.168.1.202", is_active=True)
    db.add_all([printer1, printer2])

    # 12. Seed Real Sample Orders
    order_incoming = Order(
        order_number="#PP1260",
        customer_id=customer.id,
        customer_name="John Smith",
        customer_email="john.smith@email.com",
        customer_phone="+44 7987 654321",
        branch_id=branch_central.id,
        order_type=OrderType.DELIVERY,
        status=OrderStatus.INCOMING,
        delivery_address={
            "address_line1": "14 Regent Street",
            "city": "London",
            "postcode": "NW1 5RT"
        },
        delivery_instructions="Ring the bell on arrival",
        subtotal=20.47,
        delivery_fee=0.0,
        service_fee=0.0,
        discount_amount=0.0,
        vat_amount=3.41,
        total_amount=20.47,
        payment_method="Online (Card)",
        payment_status=PaymentStatus.PAID,
        payment_transaction_id="TXN9823412345",
        points_earned=204
    )

    order_accepted = Order(
        order_number="#PP1259",
        customer_id=customer2.id,
        customer_name="David Miller",
        customer_email="david.m@email.com",
        customer_phone="+44 7890 123456",
        branch_id=branch_westfield.id,
        order_type=OrderType.COLLECTION,
        status=OrderStatus.ACCEPTED,
        subtotal=18.40,
        delivery_fee=0.0,
        service_fee=0.0,
        discount_amount=0.0,
        vat_amount=3.07,
        total_amount=18.40,
        payment_method="Online (Card)",
        payment_status=PaymentStatus.PAID,
        payment_transaction_id="TXN5544332211",
        points_earned=184
    )

    sample_order = Order(
        order_number="#PP1258",
        customer_id=customer.id,
        customer_name="John Smith",
        customer_email="john.smith@email.com",
        customer_phone="+44 7123 456789",
        branch_id=branch_central.id,
        order_type=OrderType.DELIVERY,
        status=OrderStatus.PREPARING,
        delivery_address={
            "address_line1": "123 Baker Street",
            "address_line2": "Near Baker Street Station",
            "city": "London",
            "postcode": "W1U 6EP"
        },
        delivery_instructions="Leave at the door",
        subtotal=15.46,
        delivery_fee=0.0,
        service_fee=0.0,
        discount_amount=0.0,
        vat_amount=2.58,
        total_amount=15.46,
        payment_method="Online (Card)",
        payment_status=PaymentStatus.PAID,
        payment_transaction_id="TXN4789632145",
        points_earned=154
    )

    order_ready = Order(
        order_number="#PP1257",
        customer_id=customer2.id,
        customer_name="Emma Watson",
        customer_email="emma.w@email.com",
        customer_phone="+44 7456 789012",
        branch_id=branch_central.id,
        order_type=OrderType.DELIVERY,
        status=OrderStatus.READY,
        delivery_address={
            "address_line1": "78 Oxford Street",
            "city": "London",
            "postcode": "W1D 1BS"
        },
        delivery_instructions="Deliver to front desk",
        subtotal=23.88,
        delivery_fee=0.0,
        service_fee=0.0,
        discount_amount=0.0,
        vat_amount=3.98,
        total_amount=23.88,
        payment_method="Online (Card)",
        payment_status=PaymentStatus.PAID,
        payment_transaction_id="TXN7788990011",
        points_earned=238
    )

    order_delivered = Order(
        order_number="#PP1256",
        customer_id=customer.id,
        customer_name="Liam Gallagher",
        customer_email="liam.g@email.com",
        customer_phone="+44 7321 654987",
        branch_id=branch_westfield.id,
        order_type=OrderType.DELIVERY,
        status=OrderStatus.DELIVERED,
        delivery_address={
            "address_line1": "55 Shepherd's Bush Green",
            "city": "London",
            "postcode": "W12 8QE"
        },
        delivery_instructions="Call when outside",
        subtotal=13.44,
        delivery_fee=0.0,
        service_fee=0.0,
        discount_amount=0.0,
        vat_amount=2.24,
        total_amount=13.44,
        payment_method="Online (Card)",
        payment_status=PaymentStatus.PAID,
        payment_transaction_id="TXN6655443322",
        points_earned=134
    )

    db.add_all([order_incoming, order_accepted, sample_order, order_ready, order_delivered])
    db.flush()

    # Associated payment ledger entries for seeded orders
    db.add_all([
        Payment(order_id=order_incoming.id, provider=PaymentProvider.MOCK, transaction_id=order_incoming.payment_transaction_id, amount=order_incoming.total_amount, currency="GBP", status=PaymentStatus.PAID, payment_method_type="CARD"),
        Payment(order_id=order_accepted.id, provider=PaymentProvider.MOCK, transaction_id=order_accepted.payment_transaction_id, amount=order_accepted.total_amount, currency="GBP", status=PaymentStatus.PAID, payment_method_type="CARD"),
        Payment(order_id=sample_order.id, provider=PaymentProvider.MOCK, transaction_id=sample_order.payment_transaction_id, amount=sample_order.total_amount, currency="GBP", status=PaymentStatus.PAID, payment_method_type="CARD"),
        Payment(order_id=order_ready.id, provider=PaymentProvider.MOCK, transaction_id=order_ready.payment_transaction_id, amount=order_ready.total_amount, currency="GBP", status=PaymentStatus.PAID, payment_method_type="CARD"),
        Payment(order_id=order_delivered.id, provider=PaymentProvider.MOCK, transaction_id=order_delivered.payment_transaction_id, amount=order_delivered.total_amount, currency="GBP", status=PaymentStatus.PAID, payment_method_type="CARD")
    ])

    db.add_all([
        OrderItem(order_id=order_incoming.id, product_id=p1.id, product_name="Classic Beef Burger", quantity=2, unit_price=8.99, total_price=17.98),
        OrderItem(order_id=order_incoming.id, product_id=p5.id, product_name="French Fries (Regular)", quantity=1, unit_price=2.49, total_price=2.49),
        OrderStatusHistory(order_id=order_incoming.id, from_status=None, to_status=OrderStatus.INCOMING, notes="Order placed by customer"),

        OrderItem(order_id=order_accepted.id, product_id=p2.id, product_name="Double Patty Smash", quantity=1, unit_price=11.95, total_price=11.95),
        OrderItem(order_id=order_accepted.id, product_id=p6.id, product_name="Loaded Cheesy Bacon Fries", quantity=1, unit_price=6.45, total_price=6.45),
        OrderStatusHistory(order_id=order_accepted.id, from_status=OrderStatus.INCOMING, to_status=OrderStatus.ACCEPTED, notes="Order accepted by store"),

        OrderItem(order_id=sample_order.id, product_id=p1.id, product_name="Classic Beef Burger", quantity=1, unit_price=8.99, total_price=8.99, selected_modifiers=[{"name": "No onion"}, {"name": "Extra cheese", "price": 0.80}]),
        OrderItem(order_id=sample_order.id, product_id=p5.id, product_name="French Fries (Regular)", quantity=1, unit_price=2.49, total_price=2.49),
        OrderItem(order_id=sample_order.id, product_id=p7.id, product_name="Coca Cola 500ml", quantity=2, unit_price=1.59, total_price=3.18),
        OrderStatusHistory(order_id=sample_order.id, from_status=OrderStatus.ACCEPTED, to_status=OrderStatus.PREPARING, notes="Kitchen preparing food"),

        OrderItem(order_id=order_ready.id, product_id=p3.id, product_name="Spicy Nashville Chicken", quantity=2, unit_price=9.45, total_price=18.90),
        OrderItem(order_id=order_ready.id, product_id=p5.id, product_name="French Fries (Regular)", quantity=2, unit_price=2.49, total_price=4.98),
        OrderStatusHistory(order_id=order_ready.id, from_status=OrderStatus.PREPARING, to_status=OrderStatus.READY, notes="Order packed and ready for driver"),

        OrderItem(order_id=order_delivered.id, product_id=p4.id, product_name="Truffle Mushroom Burger", quantity=1, unit_price=10.95, total_price=10.95),
        OrderItem(order_id=order_delivered.id, product_id=p5.id, product_name="French Fries (Regular)", quantity=1, unit_price=2.49, total_price=2.49),
        OrderStatusHistory(order_id=order_delivered.id, from_status=OrderStatus.READY, to_status=OrderStatus.DELIVERED, notes="Driver delivered order to customer")
    ])

    db.commit()
    db.close()
    print("Database seeding completed successfully!")


if __name__ == "__main__":
    seed_db()
