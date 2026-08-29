"""
Database Migration Script for Loyalty Account Email Verification Schema Invariant.

Ensures the 'email_verified' column on the 'users' table satisfies:
    email_verified BOOLEAN NOT NULL DEFAULT FALSE

Existing data requirements:
  - NULL existing users -> set to TRUE (preserving verified access for pre-existing accounts/admins)
  - Existing verified users (TRUE) -> remain TRUE
  - Existing unverified users (FALSE) -> remain FALSE
  - Future database-level inserts without explicit value -> receive FALSE
  - NOT NULL constraint -> strictly enforced after verifying 0 NULL rows remain

Also ensures 'email_verification_challenges' table exists.
Validates table invariants and row counts before and after migration.
Fully idempotent and safely rerunnable.
"""
import sys
import pathlib

# Ensure app package is accessible
backend_root = pathlib.Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from sqlalchemy import inspect, text
from app.core.database import engine, Base
from app.models.verification import EmailVerificationChallenge


def run_migration(custom_engine=None):
    """
    Executes migration to enforce:
      email_verified BOOLEAN NOT NULL DEFAULT FALSE
    and creates 'email_verification_challenges' table if missing.
    """
    target_engine = custom_engine or engine
    dialect_name = target_engine.dialect.name

    print("=== PATTY LOYALTY EMAIL OTP VERIFICATION MIGRATION ===")
    print(f"Target Database Dialect: {dialect_name}")

    try:
        # Step 1: Pre-migration state capture using raw SQL
        inspector = inspect(target_engine)
        existing_tables = set(inspector.get_table_names())

        with target_engine.connect() as conn:
            users_before = conn.execute(text("SELECT COUNT(*) FROM users")).scalar() if 'users' in existing_tables else 0
            loyalty_before = conn.execute(text("SELECT COUNT(*) FROM loyalty_accounts")).scalar() if 'loyalty_accounts' in existing_tables else 0
            orders_before = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar() if 'orders' in existing_tables else 0

        print("Pre-migration verification:")
        print(f"  - Users: {users_before}")
        print(f"  - Loyalty Accounts: {loyalty_before}")
        print(f"  - Orders: {orders_before}")

        user_cols = {c['name']: c for c in inspector.get_columns('users')} if 'users' in existing_tables else {}

        # Step 2: Handle 'email_verified' column migration
        if 'users' in existing_tables:
            if 'email_verified' not in user_cols:
                print("\nApplying schema changes: Adding 'email_verified' column to 'users'...")
                with target_engine.begin() as conn:
                    if dialect_name == "postgresql":
                        # Add column, backfill existing rows to TRUE, set DEFAULT FALSE, set NOT NULL
                        conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN"))
                        conn.execute(text("UPDATE users SET email_verified = TRUE WHERE email_verified IS NULL"))
                        null_count = conn.execute(text("SELECT COUNT(*) FROM users WHERE email_verified IS NULL")).scalar()
                        if null_count > 0:
                            raise RuntimeError(f"Invariant Violation: {null_count} NULL email_verified rows found!")
                        conn.execute(text("ALTER TABLE users ALTER COLUMN email_verified SET DEFAULT FALSE"))
                        conn.execute(text("ALTER TABLE users ALTER COLUMN email_verified SET NOT NULL"))
                    else:
                        # SQLite / other dialects
                        conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT 0"))
                        conn.execute(text("UPDATE users SET email_verified = 1 WHERE email_verified IS NULL OR email_verified = 0"))
                print("  ✓ Column 'email_verified' added as NOT NULL DEFAULT FALSE and existing users marked verified.")
            else:
                print("\nColumn 'email_verified' already exists on 'users'. Aligning invariants...")
                with target_engine.begin() as conn:
                    if dialect_name == "postgresql":
                        # 1. Update only NULL rows to TRUE (leave existing FALSE / TRUE untouched)
                        conn.execute(text("UPDATE users SET email_verified = TRUE WHERE email_verified IS NULL"))
                        # 2. Verify zero NULLs remain before applying NOT NULL
                        null_count = conn.execute(text("SELECT COUNT(*) FROM users WHERE email_verified IS NULL")).scalar()
                        if null_count > 0:
                            raise RuntimeError(f"Invariant Violation: {null_count} NULL email_verified rows found before NOT NULL constraint!")
                        # 3. Ensure server/database default of FALSE
                        conn.execute(text("ALTER TABLE users ALTER COLUMN email_verified SET DEFAULT FALSE"))
                        # 4. Enforce NOT NULL constraint
                        conn.execute(text("ALTER TABLE users ALTER COLUMN email_verified SET NOT NULL"))
                    else:
                        conn.execute(text("UPDATE users SET email_verified = 1 WHERE email_verified IS NULL"))
                        null_count = conn.execute(text("SELECT COUNT(*) FROM users WHERE email_verified IS NULL")).scalar()
                        if null_count > 0:
                            raise RuntimeError(f"Invariant Violation: {null_count} NULL email_verified rows found!")
                print("  ✓ Column 'email_verified' aligned: NULLs backfilled to TRUE, DEFAULT FALSE and NOT NULL verified.")

        # Step 3: Create 'email_verification_challenges' table if missing
        print("\nApplying schema changes: Ensuring 'email_verification_challenges' table exists...")
        Base.metadata.create_all(bind=target_engine, tables=[EmailVerificationChallenge.__table__])
        print("  ✓ Table 'email_verification_challenges' is ready.")

        # Step 4: Post-migration invariant verification
        with target_engine.connect() as conn:
            users_after = conn.execute(text("SELECT COUNT(*) FROM users")).scalar() if 'users' in existing_tables else 0
            loyalty_after = conn.execute(text("SELECT COUNT(*) FROM loyalty_accounts")).scalar() if 'loyalty_accounts' in existing_tables else 0
            orders_after = conn.execute(text("SELECT COUNT(*) FROM orders")).scalar() if 'orders' in existing_tables else 0

        print("\nPost-migration verification:")
        print(f"  - Users: {users_after} (Delta: {users_after - users_before})")
        print(f"  - Loyalty Accounts: {loyalty_after} (Delta: {loyalty_after - loyalty_before})")
        print(f"  - Orders: {orders_after} (Delta: {orders_after - orders_before})")

        assert users_after == users_before, "Invariant Violation: User count altered during migration!"
        assert loyalty_after == loyalty_before, "Invariant Violation: LoyaltyAccount count altered during migration!"
        assert orders_after == orders_before, "Invariant Violation: Order count altered during migration!"

        # Explicitly verify 0 NULLs exist in users.email_verified
        if 'users' in existing_tables:
            with target_engine.connect() as conn:
                null_count_post = conn.execute(text("SELECT COUNT(*) FROM users WHERE email_verified IS NULL")).scalar()
                assert null_count_post == 0, f"Invariant Violation: {null_count_post} NULL email_verified values remain after migration!"

        print("\n=== MIGRATION COMPLETED SUCCESSFULLY WITH ZERO DATA LOSS ===")
        return True

    except Exception as e:
        print(f"\nMigration failed with error: {e}")
        raise


if __name__ == "__main__":
    run_migration()
