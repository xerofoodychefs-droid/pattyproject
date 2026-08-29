import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Table, UniqueConstraint
from sqlalchemy.orm import relationship
from app.core.database import Base

class UserRole:
    SUPER_ADMIN = "SUPER_ADMIN"
    BRANCH_ADMIN = "BRANCH_ADMIN"
    CUSTOMER = "CUSTOMER"

class AuthProvider:
    LOCAL = "LOCAL"
    GOOGLE = "GOOGLE"
    APPLE = "APPLE"

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=True)  # Nullable for OAuth-only users
    full_name = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    role = Column(String(50), nullable=False, default=UserRole.CUSTOMER)
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    branch_assignments = relationship("BranchUser", back_populates="user", cascade="all, delete-orphan")
    addresses = relationship("CustomerAddress", back_populates="user", cascade="all, delete-orphan")
    cards = relationship("CustomerCard", back_populates="user", cascade="all, delete-orphan")
    orders = relationship("Order", back_populates="customer")
    loyalty_account = relationship("LoyaltyAccount", back_populates="user", uselist=False)
    auth_identities = relationship("UserAuthIdentity", back_populates="user", cascade="all, delete-orphan")
    sessions = relationship("AuthSession", back_populates="user", cascade="all, delete-orphan")
    verification_challenges = relationship("EmailVerificationChallenge", back_populates="user", cascade="all, delete-orphan")

class UserAuthIdentity(Base):
    __tablename__ = "user_auth_identities"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(50), nullable=False)           # GOOGLE, APPLE
    provider_subject = Column(String(255), nullable=False)  # Immutable provider subject ID (sub)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = relationship("User", back_populates="auth_identities")

    __table_args__ = (
        UniqueConstraint("provider", "provider_subject", name="uq_provider_subject"),
    )

class CustomerAddress(Base):
    __tablename__ = "customer_addresses"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    label = Column(String(50), default="Home")  # Home, Work, Other
    address_line1 = Column(String(255), nullable=False)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False, default="London")
    postcode = Column(String(20), nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="addresses")

class CustomerCard(Base):
    __tablename__ = "customer_cards"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    card_brand = Column(String(50), nullable=False, default="Mastercard")  # Mastercard, Visa, RuPay, etc.
    last4 = Column(String(4), nullable=False, default="4242")
    cardholder_name = Column(String(255), nullable=False, default="John Doe")
    expiry_month = Column(String(2), nullable=False, default="08")
    expiry_year = Column(String(2), nullable=False, default="27")
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="cards")

class AuthConsumedJti(Base):
    __tablename__ = "auth_consumed_jtis"

    jti = Column(String(64), primary_key=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    is_revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_used_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    user_agent = Column(String(255), nullable=True)
    ip_address = Column(String(45), nullable=True)

    # Relationships
    user = relationship("User", back_populates="sessions")


