from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.user import User, UserRole
from app.models.loyalty import LoyaltyAccount


def create_customer_with_loyalty(
    db: Session,
    email: str,
    full_name: str,
    password_hash: Optional[str] = None,
    phone: Optional[str] = None,
    welcome_points: int = 100,
    email_verified: bool = False
) -> Tuple[User, LoyaltyAccount]:
    """
    Atomic customer creation service shared between standard registration and Google OAuth.
    Guarantees that exactly ONE User and exactly ONE LoyaltyAccount are created in the same transaction.
    """
    user = User(
        email=email.strip().lower(),
        password_hash=password_hash,
        full_name=full_name.strip(),
        phone=phone.strip() if phone else None,
        role=UserRole.CUSTOMER,
        is_active=True,
        email_verified=email_verified
    )
    db.add(user)
    db.flush()  # Populates user.id for relational foreign keys

    loyalty_acc = LoyaltyAccount(
        user_id=user.id,
        available_points=welcome_points,
        lifetime_points=welcome_points
    )
    db.add(loyalty_acc)
    return user, loyalty_acc
