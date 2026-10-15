"""McpTokenService — every write to ``mcp_tokens``, and the kill switch (slice 15).

prd-mcp.md A.1/A.2, BR-M02–M04, BR-M20–M24, FR-M42–M45.

- ``create`` returns the plain value once; only its sha256 is stored (BR-M21).
- ``resolve`` turns an ``Authorization: Bearer rwm_…`` value into the owner,
  refusing in a fixed order with stable codes (``McpRefusal``).
- ``touch`` writes ``last_used_at`` at most once a minute per token.
- The kill switch is ``system_settings`` (category ``mcp``, key ``config``,
  ``{enabled}``), off when the row is missing, read through a 30 s Redis cache
  that a write clears.
"""

import hashlib
import secrets
import string
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes, selectinload

from app.core.auth import MCP_TOKEN_PREFIX
from app.core.errors import DomainError
from app.db.models.inbox_item import InboxEventType
from app.db.models.mcp_token import McpToken, McpTokenStatus
from app.db.models.system_setting import SystemSetting
from app.db.models.user import User
from app.policy import TECH_ROLES, is_tech

_PREFIX_LEN = 12  # "rwm_" + 8 characters, for the list (A.2)
_ALPHABET = string.digits + string.ascii_letters  # base62

MCP_DISABLED_MESSAGE = "MCP is disabled by the administrator"

_SETTING_CATEGORY = "mcp"
_SETTING_KEY = "config"
_ENABLED_CACHE_KEY = "rw:mcp:enabled"
_ENABLED_CACHE_SECONDS = 30
_TOUCH_KEY = "rw:mcp:touch:{}"
_TOUCH_SECONDS = 60

#: How long before expiry the owner hears about it (§8, AC-M38).
EXPIRY_NOTICE_WINDOW = timedelta(days=7)


class McpRefusal(Exception):
    """The MCP server refuses a request before any tool runs (A.8 codes)."""

    def __init__(self, code: str, message: str, http_status: int):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


_INVALID = ("token_invalid", "The MCP token is invalid, expired, or revoked.", 401)


def _invalid() -> McpRefusal:
    return McpRefusal(*_INVALID)


def generate_value() -> str:
    """``rwm_`` + 32 random bytes in base62 (A.2)."""
    n = int.from_bytes(secrets.token_bytes(32), "big")
    digits = []
    while n:
        n, r = divmod(n, 62)
        digits.append(_ALPHABET[r])
    return MCP_TOKEN_PREFIX + "".join(reversed(digits)).rjust(43, "0")


def hash_value(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


# ── Kill switch ───────────────────────────────────────────────────────────────


async def _setting_row(db: AsyncSession) -> SystemSetting | None:
    return (
        await db.execute(
            select(SystemSetting).where(
                SystemSetting.category == _SETTING_CATEGORY, SystemSetting.key == _SETTING_KEY,
            )
        )
    ).scalar_one_or_none()


async def is_enabled(db: AsyncSession) -> bool:
    """The kill switch, through a 30 s Redis cache (Redis down: read the row)."""
    from app.core.redis_client import get_redis_raw

    try:
        redis = await get_redis_raw()
        cached = await redis.get(_ENABLED_CACHE_KEY)
    except Exception:
        redis, cached = None, None
    if cached is not None:
        return cached in ("1", b"1")
    row = await _setting_row(db)
    enabled = bool(((row.value if row else None) or {}).get("enabled"))
    if redis is not None:
        try:
            await redis.set(_ENABLED_CACHE_KEY, "1" if enabled else "0", ex=_ENABLED_CACHE_SECONDS)
        except Exception:
            pass
    return enabled


async def set_enabled(db: AsyncSession, enabled: bool) -> None:
    """Switch MCP on or off and commit. Tokens are left as they are (FR-M45)."""
    from app.core.redis_client import get_redis_raw

    row = await _setting_row(db)
    if row is None:
        db.add(SystemSetting(
            category=_SETTING_CATEGORY, key=_SETTING_KEY, value={"enabled": enabled},
            is_active=True,
        ))
    else:
        row.value = {**(row.value or {}), "enabled": enabled}
        attributes.flag_modified(row, "value")
    # Commit before clearing the cache: a request in between would cache the old value.
    await db.commit()
    try:
        await (await get_redis_raw()).delete(_ENABLED_CACHE_KEY)
    except Exception:
        pass


# ── Tokens ────────────────────────────────────────────────────────────────────


class McpTokenService:
    async def create(
        self, db: AsyncSession, user: User, *, name: str, lifetime_days: int, now: datetime,
    ) -> tuple[McpToken, str]:
        """A new token for ``user``; returns it with its value — the only time
        the value exists outside the caller's memory (BR-M21)."""
        if not await is_enabled(db):
            raise DomainError(status.HTTP_409_CONFLICT, MCP_DISABLED_MESSAGE, "mcp_disabled")
        value = generate_value()
        token = McpToken(
            user_id=user.id,
            name=name,
            token_hash=hash_value(value),
            token_prefix=value[:_PREFIX_LEN],
            created_at=now,
            expires_at=now + timedelta(days=lifetime_days),
        )
        db.add(token)
        await db.flush()
        await self._notify(db, InboxEventType.mcp_token_created, token, user)
        return token, value

    async def revoke(self, db: AsyncSession, token: McpToken, by: User, now: datetime) -> McpToken:
        """Revoke a token; the next request with it is refused (BR-M23).
        Revoking twice keeps the first revocation."""
        if token.revoked_at is None:
            token.revoked_at = now
            token.revoked_by_id = by.id
            await db.flush()
        return token

    async def owned(self, db: AsyncSession, user: User, token_id: int) -> McpToken:
        """``user``'s token ``token_id`` — 404 for anyone else's."""
        token = await db.get(McpToken, token_id)
        if token is None or token.user_id != user.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Token not found")
        return token

    async def by_id(self, db: AsyncSession, token_id: int) -> McpToken:
        """Any user's token ``token_id`` (Settings → MCP) — 404 if there is none."""
        token = await db.get(McpToken, token_id)
        if token is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Token not found")
        return token

    # Both lists leave revoked tokens out (2026-10-15 product decision, CONTEXT.md
    # D19); the rows stay, so agent content can still point at them (BR-M24).

    async def list_for(self, db: AsyncSession, user: User) -> list[McpToken]:
        return list((await db.execute(
            select(McpToken).where(McpToken.user_id == user.id, McpToken.revoked_at.is_(None))
            .order_by(McpToken.created_at.desc(), McpToken.id.desc())
        )).scalars().all())

    async def list_all(self, db: AsyncSession) -> list[McpToken]:
        return list((await db.execute(
            select(McpToken).options(selectinload(McpToken.user))
            .where(McpToken.revoked_at.is_(None))
            .order_by(McpToken.created_at.desc(), McpToken.id.desc())
        )).scalars().all())

    async def resolve(
        self, db: AsyncSession, bearer: str | None, now: datetime,
    ) -> tuple[User, McpToken]:
        """The owner and token behind a bearer value, or ``McpRefusal`` — in
        this order: MCP disabled, not an MCP token or unknown, revoked,
        expired, owner inactive (all ``token_invalid``), owner not tech."""
        if not await is_enabled(db):
            raise McpRefusal("mcp_disabled", MCP_DISABLED_MESSAGE, 403)
        # BR-M02: only an rwm_ value is ever looked up — a web JWT never is.
        if not bearer or not bearer.startswith(MCP_TOKEN_PREFIX):
            raise _invalid()
        token = (await db.execute(
            select(McpToken).where(McpToken.token_hash == hash_value(bearer))
        )).scalar_one_or_none()
        if token is None or token.status_at(now) is not McpTokenStatus.active:
            raise _invalid()
        user = await db.get(User, token.user_id)
        if user is None or not user.is_active:
            raise _invalid()
        if not is_tech(user.role):
            raise McpRefusal("not_tech", "MCP is available to tech users only.", 403)
        return user, token

    async def touch(self, db: AsyncSession, token: McpToken, now: datetime) -> None:
        """``last_used_at = now``, at most once a minute per token (A.2)."""
        from app.core.redis_client import get_redis_raw

        try:
            first = await (await get_redis_raw()).set(
                _TOUCH_KEY.format(token.id), "1", nx=True, ex=_TOUCH_SECONDS,
            )
        except Exception:
            first = True
        if first:
            token.last_used_at = now
            await db.flush()

    async def notify_expiring(self, db: AsyncSession, now: datetime) -> list[int]:
        """One notice per active token expiring within seven days (§8, AC-M38) —
        only to owners who can still use it (active, tech; BR-M04)."""
        tokens = (await db.execute(
            select(McpToken).join(User, User.id == McpToken.user_id).where(
                User.is_active.is_(True),
                User.role.in_(sorted(TECH_ROLES)),
                McpToken.revoked_at.is_(None),
                McpToken.expires_at > now,
                McpToken.expires_at <= now + EXPIRY_NOTICE_WINDOW,
                McpToken.expiry_notified_at.is_(None),
            ).order_by(McpToken.id)
        )).scalars().all()
        for token in tokens:
            token.expiry_notified_at = now
            await self._notify(
                db, InboxEventType.mcp_token_expiring, token, await db.get_one(User, token.user_id),
            )
        await db.flush()
        return [t.id for t in tokens]

    @staticmethod
    async def _notify(
        db: AsyncSession, trigger: InboxEventType, token: McpToken, owner: User,
    ) -> None:
        from app.services.inbox_service import inbox_service

        await inbox_service.fan_out_user(
            db, trigger, owner,
            meta={
                "token_id": token.id,
                "token_name": token.name,
                "expires_at": token.expires_at.isoformat(),
            },
        )


mcp_token_service = McpTokenService()
