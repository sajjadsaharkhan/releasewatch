"""User ORM model."""

from datetime import datetime

import enum

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserRole(str, enum.Enum):
    """Roles a team member can hold within Releasewatch."""

    qa = "qa"
    developer = "developer"
    triage_lead = "triage_lead"
    cto = "cto"
    admin = "admin"


class User(Base):
    """Platform user / team member.

    Telegram linking is optional — a user connects their account by sending the
    one-time ``connect_token`` to the bot.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        String(32), nullable=False, default=UserRole.qa
    )

    # Telegram linking — token used to pair via /integration command in the bot
    connect_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    connect_token_expires: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Display
    title: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        doc="Job title or position"
    )
    bio: Mapped[str | None] = mapped_column(
        String(2000), nullable=True,
        doc="User biography"
    )
    avatar_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        doc="S3 URL for uploaded profile image"
    )
    avatar_color: Mapped[str] = mapped_column(
        String(7), nullable=False, default="#6366f1",
        doc="Hex colour used for the avatar fallback, e.g. #6366f1"
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    projects = relationship("Project", back_populates="creator", foreign_keys="Project.created_by_id")
    reported_issues = relationship("Issue", back_populates="reporter", foreign_keys="Issue.reporter_id")
    assigned_issues = relationship("Issue", back_populates="assignee", foreign_keys="Issue.assignee_id")
    inbox_items = relationship("InboxItem", foreign_keys="InboxItem.user_id", back_populates="user")
    telegram_integration = relationship(
        "TelegramIntegration", back_populates="user", uselist=False
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} role={self.role}>"
