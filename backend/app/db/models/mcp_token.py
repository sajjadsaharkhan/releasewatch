"""MCP tokens (slice 15, prd-mcp.md A.2) — the credential a coding agent holds.

Only the sha256 of the value is stored (BR-M21); the value itself is returned
once, by ``McpTokenService.create``. Status is derived from ``revoked_at`` and
``expires_at``, never stored. Rows are never deleted (BR-M24): later slices
point agent content at the token that wrote it.
"""

import enum
from datetime import datetime

from sqlalchemy import CHAR, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class McpTokenStatus(str, enum.Enum):
    active = "active"
    expired = "expired"
    revoked = "revoked"


#: The only lifetimes a token can have (BR-M20) — no "never expires".
MCP_TOKEN_LIFETIME_DAYS: tuple[int, ...] = (30, 90, 365)
#: Preselected in the Create token form (FR-M40, AC-M37).
MCP_TOKEN_DEFAULT_LIFETIME_DAYS = 90


class McpToken(Base):
    __tablename__ = "mcp_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    token_hash: Mapped[str] = mapped_column(CHAR(64), nullable=False, unique=True)
    #: The first characters of the value ("rwm_a1b2c3d4"), so the owner can tell tokens apart.
    token_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )
    #: Set once the seven-days-before-expiry notice went out (§8, AC-M38).
    expiry_notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user = relationship("User", foreign_keys=[user_id])

    def status_at(self, now: datetime) -> McpTokenStatus:
        if self.revoked_at is not None:
            return McpTokenStatus.revoked
        if self.expires_at <= now:
            return McpTokenStatus.expired
        return McpTokenStatus.active

    def __repr__(self) -> str:
        return f"<McpToken id={self.id} user_id={self.user_id} prefix={self.token_prefix!r}>"
