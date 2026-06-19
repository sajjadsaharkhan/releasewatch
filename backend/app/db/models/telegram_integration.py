"""TelegramIntegration ORM model — per-user Telegram account link."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TelegramIntegration(Base):
    """Stores the Telegram account linked to a Releasewatch user.

    Created when a user sends ``/integration <token>`` to the bot.
    Deleted on disconnect. One row per user (enforced by UNIQUE on user_id).
    """

    __tablename__ = "telegram_integrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    # Telegram's own numeric user ID (never changes, even if @handle changes)
    telegram_user_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, nullable=False, index=True
    )

    # Private chat ID for DMs — same as telegram_user_id for personal chats,
    # but stored separately so group/channel support can be added later.
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    telegram_username: Mapped[str | None] = mapped_column(String(128), nullable=True)
    telegram_full_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    telegram_first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    telegram_last_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Updated after each successful notification delivery
    last_event_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    user = relationship("User", back_populates="telegram_integration")

    def __repr__(self) -> str:
        return (
            f"<TelegramIntegration user={self.user_id} "
            f"tg={self.telegram_user_id} active={self.is_active}>"
        )
