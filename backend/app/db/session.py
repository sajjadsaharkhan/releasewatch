"""Async SQLAlchemy engine and session management.

Usage
-----
In FastAPI route handlers, inject the session with::

    async def my_route(db: AsyncSession = Depends(get_db)):
        ...

In Celery tasks (each task runs in its own ``asyncio.run()`` / event loop)
use ``task_session()`` instead — it creates a fresh NullPool engine per call
so there are no event-loop-binding conflicts::

    async with task_session() as db:
        ...
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import settings

# ── Module-level singletons (initialised in lifespan) ────────────────────────
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


async def init_engine() -> None:
    """Create the async engine and session factory.

    Called once during application startup inside the lifespan context manager.
    """
    global _engine, _session_factory

    _engine = create_async_engine(
        settings.database_url,
        echo=settings.ENVIRONMENT == "development",
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )
    _session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def close_engine() -> None:
    """Dispose the async engine on application shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


def get_engine() -> AsyncEngine:
    """Return the module-level async engine (must be initialised first)."""
    if _engine is None:
        raise RuntimeError("Database engine not initialised. Call init_engine() first.")
    return _engine


@asynccontextmanager
async def task_session() -> AsyncIterator[AsyncSession]:
    """Yield an ``AsyncSession`` suitable for use inside Celery tasks.

    Each Celery task runs in its own ``asyncio.run()`` call (its own event
    loop).  SQLAlchemy's connection pool binds connections to the event loop
    that created them, so reusing a pooled engine across ``asyncio.run()``
    boundaries raises asyncpg errors.  Using ``NullPool`` sidesteps this: a
    fresh connection is opened and immediately closed for every session, with
    no pooling state shared between event loops.
    """
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            yield session
    finally:
        await engine.dispose()


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency that yields an ``AsyncSession`` per request.

    The session is automatically committed on success or rolled back on error,
    then closed regardless.
    """
    if _session_factory is None:
        raise RuntimeError("Session factory not initialised. Call init_engine() first.")

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
