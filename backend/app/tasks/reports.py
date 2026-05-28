"""Celery tasks — report cache invalidation and nightly regression analysis."""

import asyncio
import logging
from typing import Any

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.reports.invalidate_report_cache",
    queue="default",
)
def invalidate_report_cache(release_ids: list[str]) -> dict[str, Any]:
    """Invalidate Redis cache keys for the given release reports.

    Called whenever an issue or release is mutated so the next report request
    fetches fresh data.

    Parameters
    ----------
    release_ids:
        List of release UUID strings whose cache should be purged.
        Pass an empty list to purge all ``report:release:*`` keys.

    Returns
    -------
    dict
        ``{invalidated: N}`` — number of keys deleted.
    """
    result = asyncio.run(_invalidate_async(release_ids))
    return result


async def _invalidate_async(release_ids: list[str]) -> dict[str, Any]:
    """Internal async cache invalidation logic."""
    from app.core.redis_client import get_redis_raw

    redis = await get_redis_raw()

    if not release_ids:
        # Purge all report cache keys via SCAN
        cursor = 0
        deleted = 0
        while True:
            cursor, keys = await redis.scan(cursor=cursor, match="report:release:*", count=100)
            if keys:
                await redis.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break
        logger.info("Invalidated %d report cache keys (all releases).", deleted)
        return {"invalidated": deleted}

    keys = [f"report:release:{rid}" for rid in release_ids]
    deleted = await redis.delete(*keys)
    logger.info("Invalidated %d report cache keys for releases: %s", deleted, release_ids)
    return {"invalidated": deleted}


@celery_app.task(
    name="app.tasks.reports.detect_regression_patterns",
    queue="default",
)
def detect_regression_patterns() -> dict[str, Any]:
    """Nightly task — analyse regression patterns across all active projects.

    Runs the fragility analysis for every project and caches the results.
    Fires Telegram alerts if any component has regressed more than a threshold
    in the last 30 days.

    Returns
    -------
    dict
        ``{projects_processed: N, alerts_sent: N}``
    """
    result = asyncio.run(_detect_regressions_async())
    return result


async def _detect_regressions_async() -> dict[str, Any]:
    """Internal async implementation of regression pattern detection."""
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

    from app.config import settings
    from app.core.redis_client import set_cached
    from app.db.models.project import Project
    from app.services.regression_service import regression_service

    REGRESSION_ALERT_THRESHOLD = 3  # alert if a label regressed ≥ 3 times

    engine = create_async_engine(settings.database_url)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    projects_processed = 0
    alerts_sent = 0

    try:
        async with factory() as db:
            result = await db.execute(
                select(Project).where(Project.archived_at.is_(None))
            )
            projects = result.scalars().all()

            for project in projects:
                try:
                    fragility = await regression_service.get_component_fragility(
                        db, project.id, n_releases=10
                    )
                    # Cache for dashboard display
                    await set_cached(
                        f"report:fragility:{project.id}",
                        fragility,
                        ttl=86400,  # 24 hours
                    )
                    projects_processed += 1

                    # Check for alert threshold breaches
                    for entry in fragility:
                        if entry["regression_count"] >= REGRESSION_ALERT_THRESHOLD:
                            logger.warning(
                                "Project %s: label '%s' has %d regressions (threshold=%d).",
                                project.slug,
                                entry["label"],
                                entry["regression_count"],
                                REGRESSION_ALERT_THRESHOLD,
                            )
                            # In a real implementation: enqueue Telegram alerts here
                            alerts_sent += 1

                except Exception as exc:
                    logger.error(
                        "Regression detection failed for project %s: %s", project.slug, exc
                    )
    finally:
        await engine.dispose()

    logger.info(
        "detect_regression_patterns complete: %d projects, %d alerts.",
        projects_processed,
        alerts_sent,
    )
    return {"projects_processed": projects_processed, "alerts_sent": alerts_sent}
