"""Shared pytest fixtures for the API test suite.

Settings are overridden via environment variables *before* ``app.config`` is
imported anywhere, because ``config.settings`` is a module-level singleton
built once at import time. Everything below this env override runs against
``<POSTGRES_DB>_test`` on the same Postgres server the dev stack uses — never
against the real dev database.
"""

import os
import re

_base_db = os.environ.get("POSTGRES_DB", "releasewatch")
if not _base_db.endswith("_test"):
    os.environ["POSTGRES_DB"] = f"{_base_db}_test"
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-only")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("ADMIN_PASSWORD", "")

# Report caching (app/services/report_service.py) keys Redis by numeric id,
# and TRUNCATE ... RESTART IDENTITY makes those ids restart at 1 every test —
# sharing the dev stack's Redis logical DB would let a stale dev-traffic (or
# prior-run) cache entry leak into an assertion. Route tests to their own DB
# index instead of touching /0.
_redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_redis_url = re.sub(r"/\d+$", "", _redis_url)
os.environ["REDIS_URL"] = f"{_redis_url}/15"

import asyncio  # noqa: E402
import secrets  # noqa: E402
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator  # noqa: E402
from datetime import UTC, datetime, timedelta  # noqa: E402
from pathlib import Path  # noqa: E402

import asyncpg  # noqa: E402
import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from alembic.config import Config  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker  # noqa: E402

import app.db.models  # noqa: E402,F401 — registers every model's metadata
from alembic import command  # noqa: E402
from app.config import settings  # noqa: E402
from app.core.auth import create_access_token, get_password_hash  # noqa: E402
from app.core.clock import get_now  # noqa: E402
from app.core.redis_client import close_redis, init_redis  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.models.system_setting import SystemSetting  # noqa: E402
from app.db.models.telegram_integration import TelegramIntegration  # noqa: E402
from app.db.models.user import User, UserRole  # noqa: E402
from app.db.session import close_engine, get_engine, init_engine  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402
from app.tasks.attachments import validate_attachment  # noqa: E402
from app.tasks.notifications import send_telegram_notification  # noqa: E402
from app.tasks.search import embed_issue  # noqa: E402
from tests.factories import Factories  # noqa: E402

BACKEND_DIR = Path(__file__).resolve().parent.parent

# ── Test database: create + migrate once per session ─────────────────────────


async def _create_test_database() -> None:
    conn = await asyncpg.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        database="postgres",
    )
    try:
        try:
            await conn.execute(f'CREATE DATABASE "{settings.POSTGRES_DB}"')
        except asyncpg.exceptions.DuplicateDatabaseError:
            pass
    finally:
        await conn.close()

    conn = await asyncpg.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        database=settings.POSTGRES_DB,
    )
    try:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    finally:
        await conn.close()


@pytest.fixture(scope="session", autouse=True)
def _test_database() -> None:
    """Create the test database and bring it to ``head`` once per test run."""
    asyncio.run(_create_test_database())

    alembic_cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    command.upgrade(alembic_cfg, "head")


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _app_lifecycle(_test_database: None) -> AsyncIterator[None]:
    """Initialise the engine/Redis singletons the app's routes rely on.

    ``ASGITransport`` never runs FastAPI's own ``lifespan`` (S3 checks, admin
    bootstrap, embedding warm-up — none of which we want in tests), so the
    two pieces of state routes actually depend on are started directly.
    """
    await init_engine()
    await init_redis()
    from app.core.redis_client import get_redis_raw

    await (await get_redis_raw()).flushdb()  # clear leftovers from an interrupted prior run
    yield
    await close_redis()
    await close_engine()


# ── Per-test isolation: truncate, not rollback ────────────────────────────────


@pytest_asyncio.fixture(autouse=True)
async def _truncate_after_test(db_session: AsyncSession) -> AsyncIterator[None]:
    """Empty every table after each test.

    Rollback-based isolation is rejected because ``get_db`` commits and some
    code paths open their own sessions. ``issue_number_seq`` is a plain
    sequence (not a SERIAL/IDENTITY column) so ``RESTART IDENTITY`` never
    touches it — tests must not assert absolute ``issue_number`` values.
    """
    yield
    # TRUNCATE takes an ACCESS EXCLUSIVE lock; if `db_session` (used by the
    # telegram/factories fixtures) still had an open transaction touching one
    # of these tables, this would block forever waiting for a lock only
    # db_session's own teardown could release — and fixture teardown isn't
    # concurrent. Closing it out here first removes the ordering dependency.
    await db_session.rollback()
    table_names = [t.name for t in Base.metadata.sorted_tables if t.name != "alembic_version"]
    quoted = ", ".join(f'"{name}"' for name in table_names)
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))

    # Identity sequences restart at 1 every test, but report_service.py caches
    # by that same numeric id with no TTL — without this, test B could read
    # test A's cached report for "release 1".
    from app.core.redis_client import get_redis_raw

    await (await get_redis_raw()).flushdb()


# ── Raw DB session — fixture infrastructure only, never for test assertions ──


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """A raw session for bootstrapping state no API endpoint can create yet.

    Tests themselves must not query the ORM to assert results (HTTP
    responses, the inbox, and the Telegram recorder are the allowed
    observations) — this fixture exists only for fixture-level bootstrapping
    such as the very first admin user or a fake Telegram link.
    """
    factory = async_sessionmaker(get_engine(), class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


# ── HTTP client + auth ────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=fastapi_app)
    async with AsyncClient(transport=transport, base_url="http://test/api/v1") as c:
        yield c


@pytest_asyncio.fixture
async def client_for() -> AsyncIterator[Callable[[object], Awaitable[AsyncClient]]]:
    """Fixture factory — mint an authenticated ``AsyncClient`` for any user.

    ``user`` needs only ``.id`` and ``.role`` (works for both ORM ``User``
    rows and the ``SimpleNamespace`` objects the factories return from API
    responses). Mirrors ``app/api/v1/auth.py::_mint_pair`` without going
    through ``/auth/login``.
    """
    opened: list[AsyncClient] = []

    async def _make(user) -> AsyncClient:
        role = user.role.value if hasattr(user.role, "value") else user.role
        token = create_access_token({"sub": str(user.id), "role": role})
        transport = ASGITransport(app=fastapi_app)
        c = AsyncClient(
            transport=transport,
            base_url="http://test/api/v1",
            headers={"Authorization": f"Bearer {token}"},
        )
        opened.append(c)
        return c

    yield _make

    for c in opened:
        await c.aclose()


# ── Factories ──────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def _bootstrap_admin(db_session: AsyncSession) -> User:
    """Insert the very first admin directly.

    No endpoint can create it without an admin already existing — the one
    sanctioned exception to "factories go through the API".
    """
    admin = User(
        name="Test Admin",
        username=f"admin-{secrets.token_hex(4)}",
        hashed_password=get_password_hash("test-password-123"),
        role=UserRole.admin,
        is_active=True,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest_asyncio.fixture
async def factories(client_for, _bootstrap_admin: User) -> Factories:
    """Small factory helpers (user, project, release, issue) via the API."""
    admin_client = await client_for(_bootstrap_admin)
    return Factories(admin_client, admin_id=_bootstrap_admin.id)


# ── Fakes at the edges ────────────────────────────────────────────────────────


class TelegramOutbox:
    """Records every Telegram send instead of sending it.

    ``link_telegram(user)`` creates a real ``TelegramIntegration`` row (the
    one thing no API endpoint can fake, since linking normally requires a
    round-trip through the bot) and remembers the chat id so ``sent_to``
    stays a plain in-memory lookup.
    """

    def __init__(self, db_session: AsyncSession):
        self._db = db_session
        self.sent: list[tuple[int, str, dict]] = []
        self._chat_ids: dict[int, int] = {}

    async def link_telegram(self, user) -> int:
        chat_id = 1_000_000 + len(self._chat_ids) + 1
        self._chat_ids[user.id] = chat_id
        integration = TelegramIntegration(
            user_id=user.id,
            telegram_user_id=chat_id,
            chat_id=chat_id,
            is_active=True,
        )
        self._db.add(integration)
        await self._db.commit()
        return chat_id

    def sent_to(self, user) -> list[tuple[str, dict]]:
        chat_id = self._chat_ids.get(user.id)
        if chat_id is None:
            return []
        return [(template, context) for cid, template, context in self.sent if cid == chat_id]


@pytest_asyncio.fixture(autouse=True)
async def telegram(monkeypatch: pytest.MonkeyPatch, db_session: AsyncSession) -> TelegramOutbox:
    """Autouse: every Telegram send is recorded, never actually sent.

    ``InboxFanOutService`` bails out before enqueuing anything unless a
    ``SystemSetting(category="telegram", key="config")`` row has a
    ``bot_token`` — that row is seeded here so recipients with a linked
    account actually reach the (faked) dispatch call.
    """
    db_session.add(
        SystemSetting(
            category="telegram",
            key="config",
            value={"bot_token": "test-bot-token"},
            is_active=True,
        )
    )
    await db_session.commit()

    outbox = TelegramOutbox(db_session)

    def _fake_apply_async(args=None, kwargs=None, **_ignored):
        args = list(args or [])
        kwargs = kwargs or {}
        chat_id = args[0] if len(args) > 0 else kwargs.get("chat_id")
        template_name = args[1] if len(args) > 1 else kwargs.get("template_name")
        context = args[2] if len(args) > 2 else kwargs.get("context")
        outbox.sent.append((chat_id, template_name, context))

    monkeypatch.setattr(send_telegram_notification, "apply_async", _fake_apply_async)
    return outbox


@pytest.fixture(autouse=True)
def background_jobs(monkeypatch: pytest.MonkeyPatch) -> dict[str, list]:
    """Autouse: embedding + attachment-validation jobs become no-ops.

    Exposed so a test can assert a job *was enqueued* without doing the real
    (heavy / S3-dependent) work.
    """
    calls: dict[str, list] = {"embed_issue": [], "validate_attachment": []}

    def _fake_embed(args=None, kwargs=None, **_ignored):
        calls["embed_issue"].append((args, kwargs))

    def _fake_validate(args=None, kwargs=None, **_ignored):
        calls["validate_attachment"].append((args, kwargs))

    monkeypatch.setattr(embed_issue, "apply_async", _fake_embed)
    monkeypatch.setattr(validate_attachment, "apply_async", _fake_validate)
    return calls


# ── Clock ──────────────────────────────────────────────────────────────────


class Clock:
    """Controllable ``now`` for time-based rules — see ``app/core/clock.py``."""

    def __init__(self) -> None:
        self._now = datetime.now(UTC)

    def set(self, dt: datetime) -> None:
        self._now = dt

    def advance(self, **kwargs) -> None:
        self._now += timedelta(**kwargs)

    def __call__(self) -> datetime:
        return self._now


@pytest.fixture
def clock() -> Iterator[Clock]:
    c = Clock()
    fastapi_app.dependency_overrides[get_now] = c
    yield c
    fastapi_app.dependency_overrides.pop(get_now, None)
