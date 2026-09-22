"""Wall-clock seam for time-based rules.

Phase 2 code that stamps or compares time (status transitions, due states,
overdue checks, ...) takes ``now`` from :func:`get_now` instead of calling
``datetime.now()`` directly, so tests can control time deterministically
through the ``clock`` fixture (see ``backend/tests/conftest.py``). Phase 1
code keeps its own ``datetime.now()`` calls; convert them only where a
Phase 2 slice touches that code.
"""

from datetime import datetime, timezone


async def get_now() -> datetime:
    """FastAPI dependency — the current UTC time."""
    return datetime.now(timezone.utc)
