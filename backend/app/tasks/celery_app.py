"""Celery application factory and beat schedule.

The Celery app is configured with Redis as both broker and result backend.
Import the ``celery_app`` object in task modules with ``@celery_app.task``.
"""

from celery import Celery
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
    # Prevent tasks from running indefinitely
    task_soft_time_limit=60,   # seconds — raises SoftTimeLimitExceeded
    task_time_limit=120,       # seconds — SIGKILL
    # Retry defaults
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# ── Beat schedule ─────────────────────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    "detect-regression-patterns-nightly": {
        "task": "app.tasks.reports.detect_regression_patterns",
        "schedule": crontab(hour=2, minute=0),  # 02:00 UTC nightly
        "options": {"queue": "default"},
    },
    "invalidate-stale-report-cache-hourly": {
        "task": "app.tasks.reports.invalidate_report_cache",
        "schedule": crontab(minute=0),  # top of every hour
        "args": ([],),  # empty release_ids list = invalidate all
        "options": {"queue": "default"},
    },
}
