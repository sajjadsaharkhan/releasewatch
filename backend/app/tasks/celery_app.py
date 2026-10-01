"""Celery application factory and beat schedule.

The Celery app is configured with Redis as both broker and result backend.
Import the ``celery_app`` object in task modules with ``@celery_app.task``.
"""

import logging
from datetime import timedelta

from celery import Celery, signals
from celery.schedules import crontab

from app.config import settings

# ── App factory ───────────────────────────────────────────────────────────────
celery_app = Celery(
    "releasewatch",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "app.tasks.notifications",
        "app.tasks.attachments",
        "app.tasks.reports",
        "app.tasks.search_index",
        "app.tasks.releases",
        "app.tasks.queue",
    ],
)

# ── Serialisation ─────────────────────────────────────────────────────────────
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Prevent tasks from running indefinitely (search_index jobs override these per-task)
    task_soft_time_limit=300,  # seconds — raises SoftTimeLimitExceeded
    task_time_limit=360,       # seconds — SIGKILL
    # Retry defaults
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# ── Worker start — build the search index if it is empty (engine PRD A.11) ──

@signals.worker_ready.connect
def _bootstrap_search_index(**kwargs):
    """Items exist but ``search_items`` is empty (a fresh upgrade from Phase 1,
    or a restored database): enqueue ``reindex_all`` once."""
    try:
        import asyncio
        from app.tasks.search_index import bootstrap_if_empty

        if asyncio.run(bootstrap_if_empty()):
            logging.info("Search index is empty; reindex_all enqueued.")
    except Exception as exc:
        logging.warning("Search index bootstrap check failed: %s", exc)


# ── Beat schedule ─────────────────────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    "flush-telegram-notifications": {
        "task": "app.tasks.notifications.flush_telegram_notifications",
        "schedule": timedelta(seconds=60),
        "options": {"queue": "notifications"},
    },
    "detect-regression-patterns-nightly": {
        "task": "app.tasks.reports.detect_regression_patterns",
        "schedule": crontab(hour=2, minute=0),  # 02:00 UTC nightly
        "options": {"queue": "default"},
    },
    # Slice 09 (§13): one notice per release per target date that passes.
    "notify-overdue-releases-daily": {
        "task": "app.tasks.releases.notify_overdue_releases",
        "schedule": crontab(hour=6, minute=0),
        "options": {"queue": "default"},
    },
    # Slice 10 (§13): due within 24 hours / overdue, once each, to the assignee.
    "notify-due-items-hourly": {
        "task": "app.tasks.queue.notify_due_items",
        "schedule": crontab(minute=5),
        "options": {"queue": "default"},
    },
    "invalidate-stale-report-cache-hourly": {
        "task": "app.tasks.reports.invalidate_report_cache",
        "schedule": crontab(minute=0),  # top of every hour
        "args": ([],),  # empty release_ids list = invalidate all
        "options": {"queue": "default"},
    },
}
