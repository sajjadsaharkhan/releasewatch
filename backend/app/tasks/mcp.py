"""Celery tasks — the daily MCP token expiry notice (slice 15, prd-mcp.md §8)."""

import asyncio
import logging
from datetime import UTC, datetime

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def notify_expiring_mcp_tokens(now: datetime) -> list[int]:
    """Tell each owner once, seven days before a token expires (AC-M38).
    Takes ``now`` (slice 01's clock rule) so tests control it."""
    from app.db.session import task_session
    from app.services.mcp_token_service import mcp_token_service

    async with task_session() as db:
        notified = await mcp_token_service.notify_expiring(db, now)
        await db.commit()
    return notified


@celery_app.task(name="app.tasks.mcp.notify_expiring_mcp_tokens", queue="default")
def notify_expiring_mcp_tokens_task() -> list[int]:
    notified = asyncio.run(notify_expiring_mcp_tokens(datetime.now(tz=UTC)))
    logger.info("MCP token expiry notices sent: %s", notified)
    return notified
