import sys
import pathlib
import pytest
from fastapi.testclient import TestClient

# Ensure backend root is on sys.path
backend_root = pathlib.Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.tests.db import client, reset_test_db, TestingSessionLocal
from app.models import User, UserRole, Branch, BranchUser
from app.core.security import get_password_hash, create_access_token


def get_auth_header(user_id: str, email: str, role: str) -> dict:
    token = create_access_token(subject=user_id, roles=[role])
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def setup_lifecycle_environment():
    reset_test_db()
    db = TestingSessionLocal()

    # Create a customer for testing
    customer = User(
        id="cust-001",
        email="customer@example.com",
        password_hash=get_password_hash("CustomerPass123!"),
        full_name="Regular Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=True
    )
    db.add(customer)
    db.commit()
    db.close()


def test_super_admin_creates_branch_with_admin():
    sa_headers = get_auth_header("user-superadmin-001", "admin@pattyproject.co.uk", "SUPER_ADMIN")
    payload = {
        "name": "London - Soho",
        "code": "SOHO",
        "address_line1": "45 Wardour Street",
        "postcode": "W1D 6PB",
        "city": "London",
        "latitude": 51.513,
        "longitude": -0.132,
        "admin_name": "Soho Branch Admin",
        "admin_email": "soho.admin@pattyproject.co.uk",
        "admin_password": "SohoPassword123!"
    }

    res = client.post("/api/v1/branches", json=payload, headers=sa_headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["name"] == "London - Soho"
    assert data["code"] == "SOHO"
    assert data["admin"] is not None
    assert data["admin"]["email"] == "soho.admin@pattyproject.co.uk"
    assert data["admin"]["name"] == "Soho Branch Admin"
    assert "password" not in data["admin"]
    assert "password_hash" not in data["admin"]

    # Verify user in database
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "soho.admin@pattyproject.co.uk").first()
    assert user is not None
    assert user.role == UserRole.BRANCH_ADMIN
    assert user.is_active is True
    assert user.email_verified is True
    assert len(user.branch_assignments) == 1
    assert user.branch_assignments[0].branch_id == data["id"]
    db.close()


def test_branch_admin_can_login_with_email_and_password():
    # 1. Create branch with admin
    sa_headers = get_auth_header("user-superadmin-001", "admin@pattyproject.co.uk", "SUPER_ADMIN")
    payload = {
        "name": "London - Covent Garden",
        "code": "COVENT",
        "address_line1": "12 Russell St",
        "postcode": "WC2B 5HZ",
        "city": "London",
        "latitude": 51.512,
        "longitude": -0.121,
        "admin_name": "Covent Admin",
        "admin_email": "covent@pattyproject.co.uk",
        "admin_password": "CoventPassword123!"
    }
    create_res = client.post("/api/v1/branches", json=payload, headers=sa_headers)
    assert create_res.status_code == 200

    # 2. Login with correct credentials
    login_res = client.post("/api/v1/auth/login", json={
        "email": "covent@pattyproject.co.uk",
        "password": "CoventPassword123!"
    })
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "access_token" in login_data
    assert login_data["user"]["role"] == "BRANCH_ADMIN"
    assert len(login_data["user"]["branch_ids"]) == 1
    assert login_data["user"]["branch_ids"][0] == create_res.json()["id"]

    # 3. Login with wrong password fails
    bad_login = client.post("/api/v1/auth/login", json={
        "email": "covent@pattyproject.co.uk",
        "password": "WrongPassword999!"
    })
    assert bad_login.status_code == 401


def test_duplicate_email_rejected_safely():
    sa_headers = get_auth_header("user-superadmin-001", "admin@pattyproject.co.uk", "SUPER_ADMIN")

    # Try creating branch admin with existing customer email
    payload = {
        "name": "London - Duplicate Test",
        "code": "DUPTEST",
        "address_line1": "10 Duplicate Way",
        "postcode": "NW1 0LT",
        "city": "London",
        "latitude": 51.539,
        "longitude": -0.142,
        "admin_name": "Dupe Admin",
        "admin_email": "customer@example.com",  # Already belongs to customer
        "admin_password": "DupePassword123!"
    }
    res = client.post("/api/v1/branches", json=payload, headers=sa_headers)
    assert res.status_code == 400
    assert "already exists" in res.json()["detail"].lower()


def test_super_admin_can_manage_branch_admin_via_dedicated_endpoint():
    sa_headers = get_auth_header("user-superadmin-001", "admin@pattyproject.co.uk", "SUPER_ADMIN")
    branch_id = "branch-camden-001"

    # Initially Camden has no admin
    get_res = client.get(f"/api/v1/branches/{branch_id}/admin", headers=sa_headers)
    assert get_res.status_code == 200
    assert get_res.json() is None

    # Create admin for Camden
    create_admin_payload = {
        "name": "Camden Manager",
        "email": "manager.camden@pattyproject.co.uk",
        "password": "CamdenManagerPass123!"
    }
    post_res = client.post(f"/api/v1/branches/{branch_id}/admin", json=create_admin_payload, headers=sa_headers)
    assert post_res.status_code == 200
    admin_data = post_res.json()
    assert admin_data["email"] == "manager.camden@pattyproject.co.uk"
    assert admin_data["name"] == "Camden Manager"
    assert admin_data["is_active"] is True

    # Update admin credentials (email & password)
    update_admin_payload = {
        "name": "Senior Camden Manager",
        "email": "senior.camden@pattyproject.co.uk",
        "password": "NewSeniorPassword123!"
    }
    put_res = client.post(f"/api/v1/branches/{branch_id}/admin", json=update_admin_payload, headers=sa_headers)
    assert put_res.status_code == 200
    updated_data = put_res.json()
    assert updated_data["email"] == "senior.camden@pattyproject.co.uk"
    assert updated_data["name"] == "Senior Camden Manager"

    # Login with new credentials succeeds
    login_new = client.post("/api/v1/auth/login", json={
        "email": "senior.camden@pattyproject.co.uk",
        "password": "NewSeniorPassword123!"
    })
    assert login_new.status_code == 200

    # Old credentials fail
    login_old = client.post("/api/v1/auth/login", json={
        "email": "manager.camden@pattyproject.co.uk",
        "password": "CamdenManagerPass123!"
    })
    assert login_old.status_code == 401


def test_delete_branch_admin_endpoint():
    sa_headers = get_auth_header("user-superadmin-001", "admin@pattyproject.co.uk", "SUPER_ADMIN")
    branch_id = "branch-camden-001"

    # Create admin
    client.post(f"/api/v1/branches/{branch_id}/admin", json={
        "name": "Temp Admin",
        "email": "temp.admin@pattyproject.co.uk",
        "password": "TempPassword123!"
    }, headers=sa_headers)

    # Delete admin
    del_res = client.delete(f"/api/v1/branches/{branch_id}/admin", headers=sa_headers)
    assert del_res.status_code == 200

    # Check that admin is now None
    get_res = client.get(f"/api/v1/branches/{branch_id}/admin", headers=sa_headers)
    assert get_res.status_code == 200
    assert get_res.json() is None

    # User should now be deactivated
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "temp.admin@pattyproject.co.uk").first()
    assert user is not None
    assert user.is_active is False
    db.close()


def test_unassigned_branch_admin_cannot_login():
    db = TestingSessionLocal()
    orphan_admin = User(
        id="orphan-001",
        email="orphan.admin@pattyproject.co.uk",
        password_hash=get_password_hash("OrphanPass123!"),
        full_name="Orphaned Branch Admin",
        role=UserRole.BRANCH_ADMIN,
        is_active=True,
        email_verified=True
    )
    db.add(orphan_admin)
    db.commit()
    db.close()

    # Login should be blocked with 403
    res = client.post("/api/v1/auth/login", json={
        "email": "orphan.admin@pattyproject.co.uk",
        "password": "OrphanPass123!"
    })
    assert res.status_code == 403
    assert "no active branch assignment" in res.json()["detail"].lower()


def test_existing_super_admin_and_customer_logins_unaffected():
    # Super Admin login
    sa_res = client.post("/api/v1/auth/login", json={
        "email": "admin@pattyproject.co.uk",
        "password": "Admin123!"
    })
    assert sa_res.status_code == 200
    assert sa_res.json()["user"]["role"] == "SUPER_ADMIN"

    # Customer login
    cust_res = client.post("/api/v1/auth/login", json={
        "email": "customer@example.com",
        "password": "CustomerPass123!"
    })
    assert cust_res.status_code == 200
    assert cust_res.json()["user"]["role"] == "CUSTOMER"


def test_super_admin_creates_branch_without_admin():
    sa_headers = get_auth_header("user-superadmin-001", "admin@pattyproject.co.uk", "SUPER_ADMIN")
    payload = {
        "name": "London - Holborn",
        "code": "HOLBORN",
        "address_line1": "88 Kingsway",
        "postcode": "WC2B 6AA",
        "city": "London",
        "latitude": 51.517,
        "longitude": -0.119
    }
    res = client.post("/api/v1/branches", json=payload, headers=sa_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "London - Holborn"
    assert data["admin"] is None


def test_branch_deletion_deactivates_sole_branch_admin():
    sa_headers = get_auth_header("user-superadmin-001", "admin@pattyproject.co.uk", "SUPER_ADMIN")

    # Create branch with admin
    create_res = client.post("/api/v1/branches", json={
        "name": "London - Mayfair",
        "code": "MAYFAIR",
        "address_line1": "10 Berkeley Square",
        "postcode": "W1J 6AA",
        "city": "London",
        "latitude": 51.509,
        "longitude": -0.145,
        "admin_name": "Mayfair Admin",
        "admin_email": "mayfair@pattyproject.co.uk",
        "admin_password": "MayfairPassword123!"
    }, headers=sa_headers)
    assert create_res.status_code == 200
    branch_id = create_res.json()["id"]

    # Delete the branch
    del_res = client.delete(f"/api/v1/branches/{branch_id}", headers=sa_headers)
    assert del_res.status_code == 200

    # The sole admin should be deactivated
    db = TestingSessionLocal()
    admin = db.query(User).filter(User.email == "mayfair@pattyproject.co.uk").first()
    assert admin is not None
    assert admin.is_active is False
    db.close()


def test_branch_deletion_does_not_deactivate_multi_branch_admin():
    sa_headers = get_auth_header("user-superadmin-001", "admin@pattyproject.co.uk", "SUPER_ADMIN")

    # Create two branches
    b1_res = client.post("/api/v1/branches", json={
        "name": "London - Multi One",
        "code": "MONE",
        "address_line1": "1 Multi Way",
        "postcode": "NW1 0AA",
        "city": "London",
        "latitude": 51.520,
        "longitude": -0.130,
        "admin_name": "Multi Admin",
        "admin_email": "multi.admin@pattyproject.co.uk",
        "admin_password": "MultiPassword123!"
    }, headers=sa_headers)
    assert b1_res.status_code == 200
    b1_id = b1_res.json()["id"]

    b2_res = client.post("/api/v1/branches", json={
        "name": "London - Multi Two",
        "code": "MTWO",
        "address_line1": "2 Multi Way",
        "postcode": "NW1 0BB",
        "city": "London",
        "latitude": 51.521,
        "longitude": -0.131
    }, headers=sa_headers)
    assert b2_res.status_code == 200
    b2_id = b2_res.json()["id"]

    # Assign same admin to branch 2 as well
    db = TestingSessionLocal()
    admin_user = db.query(User).filter(User.email == "multi.admin@pattyproject.co.uk").first()
    bu2 = BranchUser(user_id=admin_user.id, branch_id=b2_id)
    db.add(bu2)
    db.commit()
    db.close()

    # Delete branch 1
    del_res = client.delete(f"/api/v1/branches/{b1_id}", headers=sa_headers)
    assert del_res.status_code == 200

    # Admin should STILL be active because branch 2 remains assigned
    db = TestingSessionLocal()
    admin = db.query(User).filter(User.email == "multi.admin@pattyproject.co.uk").first()
    assert admin is not None
    assert admin.is_active is True
    assert len(admin.branch_assignments) == 1
    assert admin.branch_assignments[0].branch_id == b2_id
    db.close()


def test_non_super_admin_cannot_manage_branch_admins():
    cust_headers = get_auth_header("cust-001", "customer@example.com", "CUSTOMER")
    branch_id = "branch-camden-001"

    # Customer cannot create admin
    post_res = client.post(f"/api/v1/branches/{branch_id}/admin", json={
        "name": "Hacker",
        "email": "hacker@example.com",
        "password": "HackerPassword123!"
    }, headers=cust_headers)
    assert post_res.status_code == 403

    # Customer cannot delete admin
    del_res = client.delete(f"/api/v1/branches/{branch_id}/admin", headers=cust_headers)
    assert del_res.status_code == 403

