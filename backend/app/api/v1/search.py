"""Search API — semantic + hybrid search over issues.

GET  /search?q=<query>&project_id=<id>&limit=20
POST /search/reindex        (admin) — enqueue embedding backfill for all issues
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_role
from app.core.redis_client import get_cached, set_cached
from app.db.models.user import User, UserRole
from app.db.session import get_db
from app.services.search_service import search as _search

import hashlib
import json

logger = logging.getLogger(__name__)
router = APIRouter()

_CACHE_TTL = 60  # seconds


def _cache_key(project_id: int, q: str) -> str:
    h = hashlib.sha256(q.lower().encode()).hexdigest()[:16]
    return f"search:{project_id}:{h}"


@router.get("", summary="Semantic + hybrid search over issues")
async def search_issues(
    q: str = Query(..., min_length=1, max_length=500, description="Search query"),
    project_id: int = Query(..., description="Project to search within"),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Run hybrid semantic search (vector + FTS fused with RRF) over issues.

    Falls back to pure full-text search when the LLM embedding model is not
    configured.  Results include a ``matched_via`` field showing which retrievers
    surfaced each hit (useful for relevance debugging).
    """
    cache_key = _cache_key(project_id, q)
    cached = await get_cached(cache_key)
    if cached is not None:
        return cached

    result = await _search(db, q, project_id, limit=limit)

    await set_cached(cache_key, result, ttl=_CACHE_TTL)
    return result


@router.post(
    "/reindex",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue embedding backfill (admin only)",
)
async def reindex(
    project_id: int | None = Query(None, description="Limit reindex to one project; omit for all"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.admin)),
) -> dict:
    """Enqueue embed_issue tasks for every issue that has no embedding or whose
    embedding was produced by a different model than the currently configured one.

    Tasks are staggered with increasing countdowns to avoid hammering the
    embedding API.
    """
    from app.tasks.search import embed_issue

    # Determine current model from settings
    row = await db.execute(
        text("SELECT value FROM system_settings WHERE category='llm' AND key='config' AND is_active=true LIMIT 1")
    )
    raw = row.scalar_one_or_none()
    cfg = raw if isinstance(raw, dict) else (json.loads(raw) if isinstance(raw, str) else {})
    current_model = cfg.get("embeddingModel") or cfg.get("embedding_model", "")

    # Find issues missing embeddings or with stale model
    where = "TRUE"
    params: dict = {}
    if project_id is not None:
        where = "i.project_id = :pid"
        params["pid"] = project_id

    if current_model:
        stale_q = text(f"""
            SELECT i.id FROM issues i
            WHERE {where}
              AND NOT EXISTS (
                SELECT 1 FROM issue_embeddings e
                WHERE e.issue_id = i.id
                  AND e.model = :model
                  AND e.field_group = 'core'
              )
        """)
        params["model"] = current_model
    else:
        stale_q = text(f"""
            SELECT i.id FROM issues i
            WHERE {where}
              AND NOT EXISTS (
                SELECT 1 FROM issue_embeddings e WHERE e.issue_id = i.id
              )
        """)

    result = await db.execute(stale_q, params)
    issue_ids = [row[0] for row in result.fetchall()]

    if not issue_ids:
        return {"enqueued": 0, "message": "All issues are up-to-date"}

    # Stagger tasks in batches of 50; each batch 5 s apart
    batch_size = 50
    enqueued = 0
    for i, iid in enumerate(issue_ids):
        countdown = (i // batch_size) * 5
        embed_issue.apply_async((iid,), countdown=countdown)
        enqueued += 1

    logger.info("reindex: enqueued %d embed_issue tasks (project_id=%s)", enqueued, project_id)
    return {"enqueued": enqueued, "message": f"Enqueued {enqueued} embedding tasks"}
