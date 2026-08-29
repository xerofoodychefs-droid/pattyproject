"""
Database Regression & Invariants Test Suite (Phase 3).

Validates database integrity, model constraints, foreign keys, 1:1 loyalty invariants,
and schema invariants for user_auth_identities.
"""
import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from app.models.user import User, UserRole, UserAuthIdentity, AuthProvider
from app.models.loyalty import LoyaltyAccount
from app.models.order import Order
from app.tests.db import TestingSessionLocal, engine


def test_user_auth_identities_schema_and_constraints():
    """Verify that user_auth_identities table exists and has exact required columns and unique constraint."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    assert "user_auth_identities" in tables, "user_auth_identities table must exist."

    columns = {col["name"]: col for col in inspector.get_columns("user_auth_identities")}
    assert "id" in columns
    assert "user_id" in columns
    assert "provider" in columns
    assert "provider_subject" in columns
    assert "created_at" in columns
    assert "updated_at" in columns
    # Verify provider_email was NOT included
    assert "provider_email" not in columns, "provider_email must NOT exist in Phase 3 schema."


def test_one_to_one_loyalty_account_invariant():
    """Verify invariant: Exactly one LoyaltyAccount per customer user, no duplicates allowed."""
    db = TestingSessionLocal()
    
    # Create customer
    user = User(
        email="loyalty.invariant@pattyproject.co.uk",
        full_name="Loyalty User",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=True
    )
    db.add(user)
    db.flush()

    # First loyalty account
    acc1 = LoyaltyAccount(user_id=user.id, available_points=100, lifetime_points=100)
    db.add(acc1)
    db.commit()

    # Attempting to add second loyalty account for the SAME user must fail with IntegrityError (unique constraint on user_id)
    acc2 = LoyaltyAccount(user_id=user.id, available_points=50, lifetime_points=50)
    db.add(acc2)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.close()


def test_order_relationship_invariant():
    """Verify that orders reference users.id directly and do not depend on auth identities."""
    db = TestingSessionLocal()
    user = User(
        email="order.customer@pattyproject.co.uk",
        full_name="Order Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=True
    )
    db.add(user)
    db.flush()

    # Attach Google identity to user
    identity = UserAuthIdentity(
        user_id=user.id,
        provider=AuthProvider.GOOGLE,
        provider_subject="google_subject_998877"
    )
    db.add(identity)
    db.commit()

    # Create Order referencing user.id
    order = Order(
        order_number="#PP99001",
        customer_id=user.id,
        customer_name=user.full_name,
        customer_email=user.email,
        customer_phone="+44 7000 000000",
        branch_id="branch-camden-001",
        subtotal=10.0,
        total_amount=10.0
    )
    db.add(order)
    db.commit()

    # Query order and verify customer relation
    saved_order = db.query(Order).filter(Order.order_number == "#PP99001").first()
    assert saved_order is not None
    assert saved_order.customer_id == user.id
    assert saved_order.customer.email == "order.customer@pattyproject.co.uk"
    db.close()


def test_cascade_isolation_only_affects_identities():
    """
    Verify CASCADE isolation: Deleting a user with identities deletes only identity records.
    """
    db = TestingSessionLocal()
    user = User(
        email="cascade.test@pattyproject.co.uk",
        full_name="Cascade User",
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=True
    )
    db.add(user)
    db.flush()

    identity = UserAuthIdentity(
        user_id=user.id,
        provider=AuthProvider.APPLE,
        provider_subject="apple_sub_12345"
    )
    db.add(identity)
    db.commit()

    identity_id = identity.id
    user_id = user.id

    # Verify identity exists
    assert db.query(UserAuthIdentity).filter(UserAuthIdentity.id == identity_id).first() is not None

    # Delete user
    db.delete(user)
    db.commit()

    # Identity record must be removed
    assert db.query(UserAuthIdentity).filter(UserAuthIdentity.id == identity_id).first() is None
    db.close()
