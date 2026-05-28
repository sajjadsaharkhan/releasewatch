"""SystemSetting ORM model — stores key-value configuration settings."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SystemSetting(Base):
    """System-wide configuration setting stored as key-value pairs.

    Settings are organized by category (e.g., 'proxy', 'llm', 'general').
    Each key has a JSON value for complex configuration objects.
    """

    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    category: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        doc="Setting category: proxy, llm, general, etc."
    )
    key: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True,
        doc="Setting key within the category"
    )
    value: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict,
        doc="Setting value as JSON object"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        doc="Whether this setting is active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), server_onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<SystemSetting category={self.category!r} key={self.key!r}>"
