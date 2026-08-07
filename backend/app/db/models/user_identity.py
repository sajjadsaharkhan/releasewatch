"""UserIdentity ORM model — links a local user to an external identity provider.

This is the vendor-neutral bridge that keeps the ``users`` table free of any
provider-specific columns.  A single user may hold several identities (e.g. a
local password *and* a Keycloak or LDAP login).  The durable link is the pair
``(provider, provider_subject)`` — never the username, which can change.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class UserIdentity(Base):
    """A link between one local ``User`` and one identity at an external provider."""

    __tablename__ = "user_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_subject", name="uq_identity_provider_subject"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(
        String(32), nullable=False, doc="Provider key, e.g. 'keycloak' or 'ldap'"
    )
    provider_subject: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Stable id from the provider (Keycloak 'sub' UUID, AD objectGUID/UPN)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    user = relationship("User", back_populates="identities")

    def __repr__(self) -> str:
        return f"<UserIdentity user_id={self.user_id} provider={self.provider!r}>"
