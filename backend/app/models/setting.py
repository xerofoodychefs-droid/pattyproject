import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime
from app.core.database import Base


class ShopSetting(Base):
    __tablename__ = "shop_settings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String(50), unique=True, index=True, nullable=False, default="global")
    opening_time = Column(String(5), nullable=False, default="11:00")  # HH:MM format (24-hour)
    closing_time = Column(String(5), nullable=False, default="23:00")  # HH:MM format (24-hour)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
