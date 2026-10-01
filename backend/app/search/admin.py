"""Settings → Search (slice 12, FR-S17, FR-S19): endpoint, model, index status.

Index progress comes from counts — items indexed with the current model out
of all live items — plus the last ``reindex_all`` run recorded in Redis.
"""

import json
from datetime import UTC, datetime, timedelta

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.core.redis_client import get_redis_raw
from app.db.models.issue import Issue
from app.db.models.search import SearchItem
from app.search import embeddings
from app.tasks import search_index

#: A reindex run counts as in progress for this long after it started, while
#: items are still missing. Past it, the index is just incomplete (an item
#: failed to embed, or the worker is down) and Settings offers Reindex all.
REINDEX_ACTIVE = timedelta(minutes=30)


async def _last_run() -> dict | None:
    try:
        raw = await (await get_redis_raw()).get(search_index.REINDEX_KEY)
        return json.loads(raw) if raw else None
    except Exception:  # noqa: BLE001 — status still renders without it
        return None


async def status_of(db: AsyncSession) -> dict:
    config = await embeddings.load_config(db)
    try:
        reported = await embeddings.probe(config.endpoint, timeout=3.0)
        service = {"reachable": True, "model": reported, "error": None}
    except embeddings.EmbeddingError as exc:
        service = {"reachable": False, "model": None, "error": str(exc)}

    total = await db.scalar(
        select(func.count()).select_from(Issue).where(Issue.deleted_at.is_(None))
    )
    indexed = 0
    if config.embed_model:
        indexed = await db.scalar(
            select(func.count())
            .select_from(SearchItem)
            .join(Issue, Issue.id == SearchItem.issue_id)
            .where(Issue.deleted_at.is_(None), SearchItem.embed_model == config.embed_model)
        )
    last_run = await _last_run()
    missing = bool(total) and (indexed or 0) < total
    running = False
    if missing and last_run:
        started = datetime.fromisoformat(last_run["started_at"])
        running = datetime.now(tz=UTC) - started < REINDEX_ACTIVE
    return {
        "embedding_endpoint": config.endpoint,
        "default_endpoint": embeddings.default_endpoint(),
        "is_default_endpoint": config.is_default,
        # The model the index holds — what search compares against (BR-S16).
        "embed_model": config.embed_model,
        "service": service,
        "index": {
            "indexed": indexed or 0,
            "total": total or 0,
            "last_run_at": last_run["started_at"] if last_run else None,
            "in_progress": running,
            "incomplete": missing and not running,
        },
    }


async def change_endpoint(db: AsyncSession, endpoint: str) -> bool:
    """Save a new endpoint. The new endpoint must answer with 1024-dim vectors;
    a different endpoint or model starts a full reindex (FR-S19). Returns whether
    a reindex started."""
    endpoint = endpoint.strip().rstrip("/")
    if not endpoint.startswith(("http://", "https://")):
        raise DomainError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Enter an http:// or https:// URL.",
            "invalid_embedding_endpoint",
        )
    current = await embeddings.load_config(db)
    try:
        model = await embeddings.probe(endpoint)
    except embeddings.EmbeddingError as exc:
        raise DomainError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"The embedding endpoint did not answer correctly: {exc}",
            "embedding_endpoint_unreachable",
        ) from exc
    changed = endpoint != current.endpoint or model != current.embed_model
    # Record the new model now: from here on search reads only its rows, so
    # the old model's vectors are never compared with the new one's (BR-S16).
    await embeddings.save_config(db, endpoint=endpoint, embed_model=model)
    return changed
