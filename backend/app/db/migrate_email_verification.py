"""
Database Migration Script for Loyalty Account Email Verification Challenges.

Safely introduces the 'email_verification_challenges' table and 'email_verified' column on 'users'
with pre- and post-migration invariant validation to ensure zero data loss.
"""
import sys
import pathlib

# Ensure app package is accessible
backend_root = pathlib.Path(__file__).resolve().parent.parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from sqlalchemy import inspect, text
from app.core.database import engine, Base, SessionLocal
from app.models.user import User
from app.models.verification import EmailVerificationChallenge
from app.models.loyalty import LoyaltyAccount
from app.models.order import Order


def run_migration(custom_engine=None):
    """
    Executes migration:
    1. Adds 'email_verified' column to 'users' if missing, backfilling existing users to email_verified=True.
    2. Creates 'email_verification_challenges' table.
    3. Validates invariants.
    """
    target_engine = custom_engine or engine
    db = SessionLocal(bind=target_engine)

    print("=== PATTY LOYALTY EMAIL OTP VERIFICATION MIGRATION ===")

    try:
        # Step 1: Pre-migration state capture
        users_before = db.query(User).count()
        loyalty_before = db.query(LoyaltyAccount).count()
        orders_before = db.query(Order).count()

        print("Pre-migration verification:")
        print(f"  - Users: {users_before}")
        print(f"  - Loyalty Accounts: {loyalty_before}")
        print(f"  - Orders: {orders_before}")

        # Step 2: Add 'email_verified' column to users if not present
        inspector = inspect(target_engine)
        user_cols = {c['name'] for c in inspector.get_columns('users')}
        if 'email_verified' not in user_cols:
            print("\nApplying schema changes: Adding 'email_verified' column to 'users'...")
            with target_engine.begin() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0"))
                # Set all pre-existing users to verified so existing accounts/admins are preserved
                conn.execute(text("UPDATE users SET email_verified = 1 WHERE email_verified IS NULL OR email_verified = 0"))
            print("  ✓ Column 'email_verified' added and existing users marked verified.")
        else:
            print("\nColumn 'email_verified' already exists on 'users'.")

        # Step 3: Create 'email_verification_challenges' table
        print("\nApplying schema changes: Creating 'email_verification_challenges' table...")
        Base.metadata.create_all(bind=target_engine, tables=[EmailVerificationChallenge.__table__])
        print("  ✓ Table 'email_verification_challenges' is ready.")

        # Step 4: Post-migration invariant verification
        users_after = db.query(User).count()
        loyalty_after = db.query(LoyaltyAccount).count()
        orders_after = db.query(Order).count()

        print("\nPost-migration verification:")
        print(f"  - Users: {users_after} (Delta: {users_after - users_before})")
        print(f"  - Loyalty Accounts: {loyalty_after} (Delta: {loyalty_after - loyalty_before})")
        print(f"  - Orders: {orders_after} (Delta: {orders_after - orders_before})")

        assert users_after == users_before, "Invariant Violation: User count altered during migration!"
        assert loyalty_after == loyalty_before, "Invariant Violation: LoyaltyAccount count altered during migration!"
        assert orders_after == orders_before, "Invariant Violation: Order count altered during migration!"

        print("\n=== MIGRATION COMPLETED SUCCESSFULLY WITH ZERO DATA LOSS ===")
        return True

    except Exception as e:
        print(f"\nMigration failed with error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
