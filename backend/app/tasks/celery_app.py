"""Celery application factory and beat schedule.

The Celery app is configured with Redis as both broker and result backend.
Import the ``celery_app`` object in task modules with ``@celery_app.task``.
"""

import logging

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
        "app.tasks.search",
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
    # Prevent tasks from running indefinitely (embed_issue overrides these per-task)
    task_soft_time_limit=300,  # seconds — raises SoftTimeLimitExceeded
    task_time_limit=360,       # seconds — SIGKILL
    # Retry defaults
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# ── Worker process init — pre-load embedding model once per fork worker ───────

@signals.worker_process_init.connect
def _preload_embedding_model(**kwargs):
    """Load the fastembed ONNX model into memory before the first task runs.

    Each Celery fork worker is a separate process; without this the model
    cold-loads inside the first task, which exhausts the soft time limit.
    """
    try:
        import asyncio
        from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
        from app.services.search_service import _load_llm_config, _embed_local, _E5_MODELS

        async def _warm():
            engine = create_async_engine(settings.database_url, pool_pre_ping=True)
            async with AsyncSession(engine) as db:
                cfg = await _load_llm_config(db)
            await engine.dispose()
            if cfg.get("provider") == "local":
                prefix = "query: " if cfg["model"] in _E5_MODELS else ""
                await _embed_local(cfg["model"], ["warmup"], prefix=prefix)
                logging.info("Worker process: embedding model '%s' ready.", cfg["model"])

        asyncio.run(_warm())
    except Exception as exc:
        logging.warning("Worker process: embedding model pre-load failed: %s", exc)


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
