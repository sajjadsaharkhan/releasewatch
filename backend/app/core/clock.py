"""Wall-clock seam for time-based rules.

Phase 2 code that stamps or compares time (status transitions, due states,
overdue checks, ...) takes ``now`` from :func:`get_now` instead of calling
``datetime.now()`` directly, so tests can control time deterministically
through the ``clock`` fixture (see ``backend/tests/conftest.py``). Phase 1
code keeps its own ``datetime.now()`` calls; convert them only where a
Phase 2 slice touches that code.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timezone

#: Tests set this (the ``clock`` fixture) so service-level code that has no
#: request to take ``now`` from — the Support channel outbox — sees frozen time.
now_override: Callable[[], datetime] | None = None


def utcnow() -> datetime:
    """The current UTC time, or the test clock's when one is installed."""
    return now_override() if now_override is not None else datetime.now(UTC)


async def get_now() -> datetime:
    """FastAPI dependency — the current UTC time."""
    return datetime.now(timezone.utc)
