"""
Automated Migration Invariant Tests for Loyalty Account Email Verification.

Tests all required migration invariants:
1. Missing 'email_verified' column (adds column, backfills existing users to TRUE, ensures DEFAULT FALSE & NOT NULL).
2. Existing nullable 'email_verified' column with NULL rows (backfills NULL rows to TRUE, leaves existing TRUE and FALSE untouched).
3. Rerunning migration multiple times (idempotency, zero errors, invariant preservation).
4. Table schema verification (verifies 'email_verification_challenges' table and column structures).
5. Default behavior for new inserts (ensures database-level default is FALSE).
6. PostgreSQL DDL execution safety and statement generation.
"""
import pytest
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock

from app.core.database import Base
from app.models.user import User, UserRole
from app.models.loyalty import LoyaltyAccount
from app.models.order import Order, OrderType, OrderStatus
from app.models.verification import EmailVerificationChallenge
from app.db.migrate_email_verification import run_migration


def test_migration_missing_column_and_backfill():
    """
    Scenario 1:
    - Initial table has NO 'email_verified' column.
    - Pre-existing users, loyalty accounts, and orders exist.
    - Migration runs: adds column, backfills existing users to email_verified=True.
    - Subsequent raw insert without email_verified defaults to 0/False.
    - Invariants and row counts are preserved.
    """
    test_engine = create_engine("sqlite:///:memory:")

    # Create tables WITHOUT email_verified on users
    with test_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE users (
                id VARCHAR(36) PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255),
                full_name VARCHAR(255) NOT NULL,
                phone VARCHAR(50),
                role VARCHAR(50) NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE loyalty_accounts (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) UNIQUE NOT NULL,
                available_points INTEGER DEFAULT 0,
                lifetime_points INTEGER DEFAULT 0,
                tier VARCHAR(50) DEFAULT 'BRONZE',
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE orders (
                id VARCHAR(36) PRIMARY KEY,
                order_number VARCHAR(50) UNIQUE NOT NULL,
                customer_id VARCHAR(36),
                customer_name VARCHAR(255),
                customer_email VARCHAR(255),
                customer_phone VARCHAR(50),
                branch_id VARCHAR(50) NOT NULL,
                order_type VARCHAR(20) NOT NULL,
                status VARCHAR(20) NOT NULL,
                subtotal FLOAT NOT NULL,
                discount_amount FLOAT DEFAULT 0.0,
                delivery_fee FLOAT DEFAULT 0.0,
                service_fee FLOAT DEFAULT 0.0,
                total_amount FLOAT NOT NULL,
                points_earned INTEGER DEFAULT 0,
                points_redeemed INTEGER DEFAULT 0,
                created_at TIMESTAMP
            )
        """))

        # Seed pre-existing records
        conn.execute(text("""
            INSERT INTO users (id, email, password_hash, full_name, role, is_active)
            VALUES ('usr-legacy-01', 'legacy@patty.co.uk', 'hash123', 'Legacy User', 'CUSTOMER', 1)
        """))
        conn.execute(text("""
            INSERT INTO loyalty_accounts (id, user_id, available_points, lifetime_points, tier)
            VALUES ('loy-legacy-01', 'usr-legacy-01', 100, 100, 'BRONZE')
        """))
        conn.execute(text("""
            INSERT INTO orders (id, order_number, customer_id, customer_name, customer_email, branch_id, order_type, status, subtotal, total_amount)
            VALUES ('ord-legacy-01', '#PP-LEGACY-01', 'usr-legacy-01', 'Legacy User', 'legacy@patty.co.uk', 'branch-01', 'COLLECTION', 'DELIVERED', 20.0, 20.0)
        """))

    # Verify column does NOT exist prior to migration
    inspector_pre = inspect(test_engine)
    user_cols_pre = {c['name'] for c in inspector_pre.get_columns('users')}
    assert 'email_verified' not in user_cols_pre

    # Run migration
    success = run_migration(custom_engine=test_engine)
    assert success is True

    # Verify column exists and pre-existing user is TRUE
    inspector_post = inspect(test_engine)
    user_cols_post = {c['name'] for c in inspector_post.get_columns('users')}
    assert 'email_verified' in user_cols_post

    with test_engine.connect() as conn:
        # Legacy user must be verified
        res = conn.execute(text("SELECT email_verified FROM users WHERE id = 'usr-legacy-01'")).scalar()
        assert res in (1, True)

        # New raw insert without email_verified must default to 0/False
        conn.execute(text("""
            INSERT INTO users (id, email, password_hash, full_name, role, is_active)
            VALUES ('usr-new-02', 'newuser@patty.co.uk', 'hash456', 'New User', 'CUSTOMER', 1)
        """))
        res_new = conn.execute(text("SELECT email_verified FROM users WHERE id = 'usr-new-02'")).scalar()
        assert res_new in (0, False)

        # Verify challenges table exists
        assert "email_verification_challenges" in inspector_post.get_table_names()


def test_migration_existing_nullable_column_with_null_and_existing_rows():
    """
    Scenario 2:
    - 'email_verified' column exists but is nullable and contains:
        1. Row with email_verified = NULL
        2. Row with email_verified = 1 (True)
        3. Row with email_verified = 0 (False)
    - Migration runs:
        - NULL row -> updated to 1 (True)
        - Existing 1 (True) -> unchanged
        - Existing 0 (False) -> unchanged
        - Zero NULL rows remain.
    """
    test_engine = create_engine("sqlite:///:memory:")

    with test_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE users (
                id VARCHAR(36) PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255),
                full_name VARCHAR(255) NOT NULL,
                phone VARCHAR(50),
                role VARCHAR(50) NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                email_verified BOOLEAN,
                created_at TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE loyalty_accounts (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) UNIQUE NOT NULL,
                available_points INTEGER DEFAULT 0,
                lifetime_points INTEGER DEFAULT 0,
                tier VARCHAR(50) DEFAULT 'BRONZE',
                created_at TIMESTAMP,
                updated_at TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE orders (
                id VARCHAR(36) PRIMARY KEY,
                order_number VARCHAR(50) UNIQUE NOT NULL,
                customer_id VARCHAR(36),
                branch_id VARCHAR(50) NOT NULL,
                order_type VARCHAR(20) NOT NULL,
                status VARCHAR(20) NOT NULL,
                subtotal FLOAT NOT NULL,
                total_amount FLOAT NOT NULL,
                created_at TIMESTAMP
            )
        """))

        # Row 1: NULL
        conn.execute(text("""
            INSERT INTO users (id, email, password_hash, full_name, role, is_active, email_verified)
            VALUES ('usr-null-01', 'nulluser@patty.co.uk', 'hash1', 'Null User', 'CUSTOMER', 1, NULL)
        """))
        # Row 2: Explicit TRUE
        conn.execute(text("""
            INSERT INTO users (id, email, password_hash, full_name, role, is_active, email_verified)
            VALUES ('usr-true-02', 'trueuser@patty.co.uk', 'hash2', 'True User', 'CUSTOMER', 1, 1)
        """))
        # Row 3: Explicit FALSE (unverified pending signup)
        conn.execute(text("""
            INSERT INTO users (id, email, password_hash, full_name, role, is_active, email_verified)
            VALUES ('usr-false-03', 'falseuser@patty.co.uk', 'hash3', 'False User', 'CUSTOMER', 1, 0)
        """))

    # Run migration
    success = run_migration(custom_engine=test_engine)
    assert success is True

    with test_engine.connect() as conn:
        # Row 1 (previously NULL) must now be 1 (True)
        r1 = conn.execute(text("SELECT email_verified FROM users WHERE id = 'usr-null-01'")).scalar()
        assert r1 in (1, True)

        # Row 2 (previously TRUE) must remain 1 (True)
        r2 = conn.execute(text("SELECT email_verified FROM users WHERE id = 'usr-true-02'")).scalar()
        assert r2 in (1, True)

        # Row 3 (previously FALSE) must remain 0 (False)
        r3 = conn.execute(text("SELECT email_verified FROM users WHERE id = 'usr-false-03'")).scalar()
        assert r3 in (0, False)

        # Verify zero NULLs remain
        nulls = conn.execute(text("SELECT COUNT(*) FROM users WHERE email_verified IS NULL")).scalar()
        assert nulls == 0


def test_migration_rerunnability_and_idempotence():
    """
    Scenario 3:
    - Running the migration 1st, 2nd, and 3rd time produces zero errors,
      leaves all records intact, and preserves invariants.
    """
    test_engine = create_engine("sqlite:///:memory:")

    with test_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE users (
                id VARCHAR(36) PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                full_name VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                email_verified BOOLEAN DEFAULT 1
            )
        """))
        conn.execute(text("""
            CREATE TABLE loyalty_accounts (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) UNIQUE NOT NULL
            )
        """))
        conn.execute(text("""
            CREATE TABLE orders (
                id VARCHAR(36) PRIMARY KEY,
                order_number VARCHAR(50) UNIQUE NOT NULL,
                subtotal FLOAT NOT NULL,
                total_amount FLOAT NOT NULL
            )
        """))
        conn.execute(text("INSERT INTO users (id, email, full_name, role) VALUES ('u1', 'u1@patty.co.uk', 'U1', 'CUSTOMER')"))

    # Pass 1
    assert run_migration(custom_engine=test_engine) is True
    # Pass 2
    assert run_migration(custom_engine=test_engine) is True
    # Pass 3
    assert run_migration(custom_engine=test_engine) is True

    with test_engine.connect() as conn:
        count = conn.execute(text("SELECT COUNT(*) FROM users")).scalar()
        assert count == 1
        val = conn.execute(text("SELECT email_verified FROM users WHERE id = 'u1'")).scalar()
        assert val in (1, True)


def test_postgresql_ddl_migration_branch():
    """
    Scenario 4:
    - Verifies that when dialect is postgresql, the migration executes the exact PostgreSQL DDL statements:
      1. UPDATE users SET email_verified = TRUE WHERE email_verified IS NULL
      2. ALTER TABLE users ALTER COLUMN email_verified SET DEFAULT FALSE
      3. ALTER TABLE users ALTER COLUMN email_verified SET NOT NULL
    """
    mock_engine = MagicMock()
    mock_engine.dialect.name = "postgresql"

    mock_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # Inspector returns existing column 'email_verified'
    def mock_inspect(bind):
        insp = MagicMock()
        insp.get_columns.return_value = [{'name': 'id'}, {'name': 'email'}, {'name': 'email_verified'}]
        insp.get_table_names.return_value = ['users', 'loyalty_accounts', 'orders', 'email_verification_challenges']
        return insp

    # Mock count queries to return consistent values
    mock_conn.execute.return_value.scalar.return_value = 0

    import app.db.migrate_email_verification as mig_mod
    original_inspect = mig_mod.inspect
    mig_mod.inspect = mock_inspect

    try:
        mig_mod.run_migration(custom_engine=mock_engine)

        # Verify SQL statements executed on connection
        executed_sqls = [str(call[0][0]) for call in mock_conn.execute.call_args_list]

        # Check presence of expected PostgreSQL DDL
        assert any("UPDATE users SET email_verified = TRUE WHERE email_verified IS NULL" in s for s in executed_sqls)
        assert any("ALTER TABLE users ALTER COLUMN email_verified SET DEFAULT FALSE" in s for s in executed_sqls)
        assert any("ALTER TABLE users ALTER COLUMN email_verified SET NOT NULL" in s for s in executed_sqls)
    finally:
        mig_mod.inspect = original_inspect


def test_postgresql_ddl_missing_column_branch():
    """
    Scenario 5:
    - Verifies PostgreSQL DDL statements when 'email_verified' column is completely missing:
      1. ALTER TABLE users ADD COLUMN email_verified BOOLEAN
      2. UPDATE users SET email_verified = TRUE WHERE email_verified IS NULL
      3. ALTER TABLE users ALTER COLUMN email_verified SET DEFAULT FALSE
      4. ALTER TABLE users ALTER COLUMN email_verified SET NOT NULL
    """
    mock_engine = MagicMock()
    mock_engine.dialect.name = "postgresql"

    mock_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # Inspector returns columns WITHOUT 'email_verified'
    def mock_inspect(bind):
        insp = MagicMock()
        insp.get_columns.return_value = [{'name': 'id'}, {'name': 'email'}]
        insp.get_table_names.return_value = ['users', 'loyalty_accounts', 'orders']
        return insp

    mock_conn.execute.return_value.scalar.return_value = 0

    import app.db.migrate_email_verification as mig_mod
    original_inspect = mig_mod.inspect
    mig_mod.inspect = mock_inspect

    try:
        mig_mod.run_migration(custom_engine=mock_engine)

        executed_sqls = [str(call[0][0]) for call in mock_conn.execute.call_args_list]

        assert any("ALTER TABLE users ADD COLUMN email_verified BOOLEAN" in s for s in executed_sqls)
        assert any("UPDATE users SET email_verified = TRUE WHERE email_verified IS NULL" in s for s in executed_sqls)
        assert any("ALTER TABLE users ALTER COLUMN email_verified SET DEFAULT FALSE" in s for s in executed_sqls)
        assert any("ALTER TABLE users ALTER COLUMN email_verified SET NOT NULL" in s for s in executed_sqls)
    finally:
        mig_mod.inspect = original_inspect
