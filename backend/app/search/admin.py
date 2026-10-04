"""Settings → Search (slice 12, FR-S17, FR-S19): endpoint, model, API key, index status.

Index progress comes from counts — items indexed with the current model out
of all live items — plus the last ``reindex_all`` run recorded in Redis.
"""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.core.redis_client import get_redis_raw
from app.db.models.issue import Issue
from app.db.models.search import CommentLabel, SearchItem
from app.search import embeddings, jev_settings
from app.search.comment_rules import RULE_KEPT
from app.search.jev import JevClient
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
        reported = await embeddings.probe(config.endpoint, timeout=3.0, **config.request_args())
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
        "jev": await jev_status(db),
        "embedding_endpoint": config.endpoint,
        "default_endpoint": embeddings.default_endpoint(),
        "is_default_endpoint": config.is_default,
        # The model name requested from the service; "" lets the service choose.
        "embedding_model": config.model,
        # The key itself never leaves.
        "has_key": config.has_key,
        "key_last4": config.key_last4,
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


async def change_config(
    db: AsyncSession,
    endpoint: str,
    *,
    model: str | None = None,
    api_key: str | None = None,
) -> bool:
    """Save a new endpoint, requested model and/or API key. The result must answer
    with 1024-dim vectors; a different endpoint or reported model starts a full
    reindex (FR-S19). ``model``/``api_key`` None keep the saved value, "" clears
    it. Returns whether a reindex started."""
    endpoint = endpoint.strip().rstrip("/")
    if not endpoint.startswith(("http://", "https://")):
        raise DomainError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Enter an http:// or https:// URL.",
            "invalid_embedding_endpoint",
        )
    current = await embeddings.load_config(db)
    candidate = replace(
        current,
        model=current.model if model is None else model.strip(),
        api_key=current.api_key if api_key is None else (api_key.strip() or None),
    )
    try:
        reported = await embeddings.probe(endpoint, **candidate.request_args())
    except embeddings.EmbeddingError as exc:
        raise DomainError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"The embedding endpoint did not answer correctly: {exc}",
            "embedding_endpoint_unreachable",
        ) from exc
    changed = endpoint != current.endpoint or reported != current.embed_model
    # Record the new model now: from here on search reads only its rows, so
    # the old model's vectors are never compared with the new one's (BR-S16).
    await embeddings.save_config(
        db, endpoint=endpoint, embed_model=reported, model=model, api_key=api_key
    )
    return changed


async def jev_status(db: AsyncSession) -> dict:
    """The Jev panel. The key itself never leaves (BR-S18, AC-S20)."""
    jev = await jev_settings.load(db)
    remaining = await db.scalar(
        select(func.count()).select_from(CommentLabel)
        .where(CommentLabel.source == "rule", CommentLabel.label == RULE_KEPT)
    )
    run = search_index.backfill_progress()
    return {
        "enabled": jev.enabled,
        "has_key": jev.has_key,
        "key_last4": jev.key_last4,
        "model": jev.model,
        "last_test_ok_at": jev.last_test_ok_at,
        "can_enable": jev.test_valid,
        "backfill": {
            "running": bool(run and not run.get("finished_at")),
            "done": run["done"] if run else 0,
            "total": run["total"] if run else 0,
            "remaining_rule_labels": remaining or 0,
            "finished_at": run.get("finished_at") if run else None,
        },
    }


async def test_jev(db: AsyncSession) -> dict:
    """Test connection with the saved key: one tiny Noul. A pass is recorded
    against this key, which is what lets Jev be switched on (AC-S19)."""
    jev = await jev_settings.load(db)
    if not jev.has_key:
        return {"ok": False, "latency_ms": 0, "model": None, "reason": "no_key"}
    outcome = await JevClient(
        jev.api_key, jev.model, await jev_settings.jev_proxy(db)
    ).ping()
    await jev_settings.record_test(db, outcome.ok)
    return {
        "ok": outcome.ok, "latency_ms": outcome.latency_ms, "model": outcome.model,
        "reason": outcome.reason,
    }
