import pytest
from app.tests.db import client, reset_test_db, TestingSessionLocal
from app.models.user import User, UserRole
from app.models.branch import Branch
from app.models.order import Order, OrderStatus
from app.core.security import create_access_token
import uuid

@pytest.fixture(autouse=True)
def setup_db():
    reset_test_db()
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_branch_stats_endpoint_and_route_order_integrity(setup_db):
    db_session = setup_db
    # 1. Create a test branch
    test_branch = Branch(
        id=str(uuid.uuid4()),
        code=f"TS{uuid.uuid4().hex[:3].upper()}",
        name="Test London Stats Branch",
        address_line1="100 Oxford Street",
        postcode="W1D 1LL",
        city="London",
        latitude=51.5154,
        longitude=-0.1342,
        is_active=True
    )
    db_session.add(test_branch)
    db_session.commit()

    # 2. Add an incoming order and a delivered order
    order1 = Order(
        id=str(uuid.uuid4()),
        order_number=f"#TS-{uuid.uuid4().hex[:4].upper()}",
        customer_name="Alice Smith",
        customer_email="alice@example.com",
        customer_phone="07123456789",
        branch_id=test_branch.id,
        status=OrderStatus.INCOMING,
        total_amount=25.0
    )
    order2 = Order(
        id=str(uuid.uuid4()),
        order_number=f"#TS-{uuid.uuid4().hex[:4].upper()}",
        customer_name="Bob Jones",
        customer_email="bob@example.com",
        customer_phone="07987654321",
        branch_id=test_branch.id,
        status=OrderStatus.DELIVERED,
        total_amount=30.0
    )
    db_session.add_all([order1, order2])
    db_session.commit()

    # 3. Create Super Admin user
    super_admin = User(
        id=str(uuid.uuid4()),
        email=f"admin_{uuid.uuid4().hex[:4]}@example.com",
        full_name="Admin Test",
        role=UserRole.SUPER_ADMIN,
        is_active=True,
        email_verified=True
    )
    db_session.add(super_admin)
    db_session.commit()

    token = create_access_token(subject=super_admin.id, roles=[super_admin.role])

    # Test GET /api/v1/branches/stats (Ensure it does not route to /{branch_id})
    res = client.get("/api/v1/branches/stats", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
    stats_list = res.json()
    assert isinstance(stats_list, list)

    target_stats = next((s for s in stats_list if s["branch_id"] == test_branch.id), None)
    assert target_stats is not None
    assert target_stats["total_orders"] == 2
    assert target_stats["pending_orders"] == 1
    assert target_stats["completed_orders"] == 1
    assert target_stats["cancelled_orders"] == 0

    # Test that normal parameterized /{branch_id} update works as expected
    update_res = client.patch(
        f"/api/v1/branches/{test_branch.id}",
        json={"phone": "020 7946 0999"},
        headers={"Authorization": f"Bearer {token}"}
    )
    assert update_res.status_code == 200
    assert update_res.json()["phone"] == "020 7946 0999"
