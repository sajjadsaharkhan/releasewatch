"""Jev settings: the one switch, the encrypted key, the model (slice 13, A.10, BR-S01, BR-S18).

``system_settings`` category ``jev``, key ``config``:
``{enabled, api_key_encrypted, model, last_test_ok_at, last_test_key_fingerprint}``.

- The key is encrypted with Fernet under a key derived from ``SECRET_KEY`` (HKDF,
  fixed info string) and is never returned by any API — only ``has_key`` and
  the last four characters.
- Jev can be switched on only after a successful Test connection **with the key
  saved now** (fingerprint match, AC-S19). Saving a new key switches Jev off
  and clears the test.
- ``is_enabled`` is the 30 s cached flag GET /features serves. Everything that
  acts on Jev asks ``client`` instead, which reads the row fresh: a PUT busts
  only its own process's cache, and a job acting on a worker's stale off would
  skip the backfill for good.
"""

import base64
import hashlib
import time
from dataclasses import dataclass
from datetime import UTC, datetime

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import attributes

from app.config import settings
from app.core.errors import DomainError
from app.db.models.system_setting import SystemSetting
from app.search.jev import DEFAULT_MODEL, JevClient

_HKDF_INFO = b"releasewatch/jev-api-key/v1"
_CACHE_SECONDS = 30.0
_cache: dict[str, tuple[float, bool]] = {}


@dataclass(frozen=True)
class JevConfig:
    enabled: bool
    api_key: str | None
    model: str
    last_test_ok_at: str | None
    last_test_key_fingerprint: str | None

    @property
    def has_key(self) -> bool:
        return bool(self.api_key)

    @property
    def key_last4(self) -> str | None:
        return self.api_key[-4:] if self.api_key else None

    @property
    def test_valid(self) -> bool:
        return bool(
            self.api_key
            and self.last_test_ok_at
            and self.last_test_key_fingerprint == fingerprint(self.api_key)
        )

    @property
    def active(self) -> bool:
        """Jev is used: switched on and a key is present (BR-S01)."""
        return self.enabled and self.has_key


def _fernet() -> Fernet:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_HKDF_INFO).derive(
        settings.SECRET_KEY.encode()
    )
    return Fernet(base64.urlsafe_b64encode(key))


def fingerprint(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()[:16]


def _bust() -> None:
    _cache.clear()


async def _row(db: AsyncSession) -> SystemSetting | None:
    return (
        await db.execute(
            select(SystemSetting).where(
                SystemSetting.category == "jev", SystemSetting.key == "config"
            )
        )
    ).scalar_one_or_none()


async def load(db: AsyncSession) -> JevConfig:
    row = await _row(db)
    v = (row.value if row else None) or {}
    api_key = None
    if v.get("api_key_encrypted"):
        try:
            api_key = _fernet().decrypt(v["api_key_encrypted"].encode()).decode()
        except InvalidToken:
            api_key = None  # SECRET_KEY changed: the stored key is unreadable, so there is none
    return JevConfig(
        enabled=bool(v.get("enabled")),
        api_key=api_key,
        model=v.get("model") or DEFAULT_MODEL,
        last_test_ok_at=v.get("last_test_ok_at"),
        last_test_key_fingerprint=v.get("last_test_key_fingerprint"),
    )


async def _write(db: AsyncSession, changes: dict) -> None:
    row = await _row(db)
    value = dict((row.value if row else None) or {})
    value.update(changes)
    if row is None:
        db.add(SystemSetting(category="jev", key="config", value=value, is_active=True))
    else:
        row.value = value
        attributes.flag_modified(row, "value")
    await db.flush()
    _bust()


async def update(
    db: AsyncSession,
    *,
    enabled: bool | None,
    api_key: str | None,
    model: str | None,
) -> tuple[JevConfig, bool]:
    """Apply a PUT. Returns ``(config, switched_on)`` — ``switched_on`` is True
    when Jev went from off to on (the caller then starts the backfill)."""
    before = await load(db)
    changes: dict = {}
    if model is not None:
        changes["model"] = model.strip() or DEFAULT_MODEL
    if api_key is not None and api_key.strip() and api_key.strip() != before.api_key:
        changes.update(
            {
                "api_key_encrypted": _fernet().encrypt(api_key.strip().encode()).decode(),
                # A new key needs a new test before Jev can run again (AC-S19).
                "enabled": False,
                "last_test_ok_at": None,
                "last_test_key_fingerprint": None,
            }
        )
    if changes:
        await _write(db, changes)
    current = await load(db)
    switched_on = False
    if enabled is not None and enabled != current.enabled:
        if enabled and not current.test_valid:
            raise DomainError(
                status.HTTP_409_CONFLICT,
                "Test the connection with the saved key before enabling Jev.",
                "jev_test_required",
            )
        await _write(db, {"enabled": enabled})
        switched_on = enabled
        current = await load(db)
    return current, switched_on


async def record_test(db: AsyncSession, ok: bool) -> None:
    current = await load(db)
    if ok and current.api_key:
        await _write(
            db,
            {
                "last_test_ok_at": datetime.now(tz=UTC).isoformat(),
                "last_test_key_fingerprint": fingerprint(current.api_key),
            },
        )


async def is_enabled(db: AsyncSession) -> bool:
    """``enabled and has_key``, cached 30 s in-process — the flag GET /features
    serves (A.10). Not for jobs: a PUT busts only the API process's cache, so a
    worker reading this could act on a stale off; jobs use ``client``."""
    hit = _cache.get("enabled")
    if hit and time.monotonic() - hit[0] < _CACHE_SECONDS:
        return hit[1]
    value = (await load(db)).active
    _cache["enabled"] = (time.monotonic(), value)
    return value


async def client(db: AsyncSession) -> JevClient | None:
    """A client when Jev is active, else None (the Jev-off path). Reads the row
    fresh, never the 30 s cache: the backfill runs in a worker whose cached
    flag an enabling PUT cannot bust, and a stale off would skip it for good."""
    config = await load(db)
    return JevClient(config.api_key, config.model) if config.active else None
