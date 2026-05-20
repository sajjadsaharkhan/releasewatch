"""Async Redis client — connection management, pub/sub helpers, and caching.

The module maintains a single shared ``redis.asyncio.Redis`` connection pool
that is initialised during application startup and closed on shutdown.
"""

import json
from typing import Any, AsyncIterator

import redis.asyncio as aioredis

from app.config import settings

# ── Module-level connection pool singleton ────────────────────────────────────
_redis: aioredis.Redis | None = None


async def init_redis() -> None:
    """Create the Redis connection pool.

    Called once during application lifespan startup.
    """
    global _redis
    _redis = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    # Eagerly verify the connection
    await _redis.ping()


async def close_redis() -> None:
    """Close and discard the Redis connection pool on shutdown."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def get_redis_raw() -> aioredis.Redis:
    """Return the raw Redis client (used internally and for health checks)."""
    if _redis is None:
        raise RuntimeError("Redis not initialised. Call init_redis() first.")
    return _redis


# ── FastAPI dependency ────────────────────────────────────────────────────────

async def get_redis() -> AsyncIterator[aioredis.Redis]:
    """FastAPI dependency — yield the shared Redis client for use in routes."""
    if _redis is None:
        raise RuntimeError("Redis not initialised. Call init_redis() first.")
    yield _redis


# ── Pub/sub helpers ───────────────────────────────────────────────────────────

async def publish(channel: str, data: Any) -> None:
    """Publish a JSON-serialised message to a Redis channel.

    Parameters
    ----------
    channel:
        Redis pub/sub channel name, e.g. ``"ws:dashboard"`` or ``"ws:inbox:{user_id}"``.
    data:
        Any JSON-serialisable value.
    """
    client = await get_redis_raw()
    await client.publish(channel, json.dumps(data, default=str))


# ── Caching helpers ───────────────────────────────────────────────────────────

async def get_cached(key: str) -> Any | None:
    """Retrieve a JSON-deserialised value from Redis.

    Returns ``None`` if the key does not exist or has expired.
    """
    client = await get_redis_raw()
    raw = await client.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def set_cached(key: str, value: Any, ttl: int | None = None) -> None:
    """Store a JSON-serialised value in Redis with an optional TTL.

    Parameters
    ----------
    key:
        Redis key.
    value:
        Any JSON-serialisable value.
    ttl:
        Time-to-live in seconds.  Defaults to ``settings.REDIS_CACHE_TTL``.
    """
    client = await get_redis_raw()
    ttl = ttl if ttl is not None else settings.REDIS_CACHE_TTL
    await client.set(key, json.dumps(value, default=str), ex=ttl)


async def delete_cached(key: str) -> None:
    """Delete a cached key from Redis."""
    client = await get_redis_raw()
    await client.delete(key)
