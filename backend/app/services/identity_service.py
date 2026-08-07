"""Identity service — resolve an external principal to a local ``User``.

The local ``users`` table is the source of truth for all app FKs.  Every
external login must map to exactly one local user.  Resolution order:

1. Match an existing link by ``(provider, provider_subject)``.
2. Else match a local user by ``username`` and auto-link (the "same username
   everywhere" convention).
3. Else JIT-create the user, seeded with ``FEDERATED_DEFAULT_ROLE`` (Phase 1).
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models.user import User, UserRole
from app.db.models.user_identity import UserIdentity
from app.services.auth_providers.base import ExternalPrincipal

logger = logging.getLogger(__name__)


def _default_role() -> UserRole:
    try:
        return UserRole(settings.FEDERATED_DEFAULT_ROLE)
    except ValueError:
        logger.warning(
            "FEDERATED_DEFAULT_ROLE=%r is not a valid role; falling back to 'developer'",
            settings.FEDERATED_DEFAULT_ROLE,
        )
        return UserRole.developer


async def resolve_or_provision(db: AsyncSession, principal: ExternalPrincipal) -> User:
    """Return the local ``User`` for an authenticated external principal."""
    # 1. Existing link by (provider, subject).
    linked = await db.execute(
        select(UserIdentity)
        .where(
            UserIdentity.provider == principal.provider,
            UserIdentity.provider_subject == principal.subject,
        )
    )
    identity = linked.scalar_one_or_none()
    if identity is not None:
        user = await db.get(User, identity.user_id)
        if user is not None:
            return user

    # 2. Match a local user by username → auto-link.
    by_username = await db.execute(select(User).where(User.username == principal.username))
    user = by_username.scalar_one_or_none()

    # 3. JIT-create if still unknown.
    if user is None:
        user = User(
            name=principal.name or principal.username,
            username=principal.username,
            hashed_password=None,
            role=_default_role(),
        )
        db.add(user)
        await db.flush()  # assign user.id
        logger.info("JIT-provisioned user %r via %s", principal.username, principal.provider)

    db.add(
        UserIdentity(
            user_id=user.id,
            provider=principal.provider,
            provider_subject=principal.subject,
        )
    )
    await db.commit()
    await db.refresh(user)
    return user
