"""Celery tasks — async embedding of issues into the vector search index.

embed_issue(issue_id)
    Builds field-grouped documents for an issue and its comments, calls the
    configured embedding API, and upserts rows into issue_embeddings.
    Skips any group whose content_hash has not changed (avoids redundant API calls).
    Idempotent — safe to enqueue multiple times; debounce via countdown=10.
"""

from __future__ import annotations

import asyncio
import logging

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    name="app.tasks.search.embed_issue",
    max_retries=3,
    default_retry_delay=15,
    queue="default",
    soft_time_limit=120,
    time_limit=180,
)
def embed_issue(self, issue_id: int) -> dict:
    """Embed all field groups for an issue; skip unchanged groups via content_hash.

    Parameters
    ----------
    issue_id:
        Primary key of the Issue row to embed.
    """
    try:
        return asyncio.run(_embed_issue_async(issue_id))
    except _EmbedSkip as exc:
        logger.info("embed_issue(%s) skipped: %s", issue_id, exc)
        return {"skipped": True, "reason": str(exc)}
    except Exception as exc:
        logger.exception("embed_issue(%s) failed: %s", issue_id, exc)
        raise self.retry(exc=exc)


class _EmbedSkip(Exception):
    """Non-error condition — embedding intentionally not performed."""


async def _embed_issue_async(issue_id: int) -> dict:
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from app.config import settings
    from app.db.models.issue import Issue
    from app.db.models.issue_timeline import IssueTimeline, TimelineEventType
    from app.services.search_service import (
        EmbeddingConfigMissing,
        _load_llm_config,
        build_field_groups,
        content_hash,
        embed_texts,
        upsert_embedding,
        delete_group,
        get_hash,
    )

    # Celery workers never go through FastAPI lifespan, so we create a
    # short-lived engine directly — same pattern as the attachments task.
    engine = create_async_engine(settings.database_url, pool_pre_ping=True)
    async with AsyncSession(engine) as db:
        # Load LLM config
        try:
            cfg = await _load_llm_config(db)
        except EmbeddingConfigMissing as exc:
            raise _EmbedSkip(str(exc)) from exc

        # Load issue
        result = await db.execute(select(Issue).where(Issue.id == issue_id))
        issue = result.scalar_one_or_none()
        if issue is None:
            raise _EmbedSkip(f"Issue {issue_id} not found")

        # Load comment bodies
        comments_result = await db.execute(
            select(IssueTimeline.body)
            .where(
                IssueTimeline.issue_id == issue_id,
                IssueTimeline.event_type == TimelineEventType.comment,
                IssueTimeline.body.isnot(None),
            )
            .order_by(IssueTimeline.created_at)
        )
        comment_bodies = [row[0] for row in comments_result.fetchall() if row[0]]

        # Capture scalar values before any commit (post-commit ORM attrs expire)
        project_id = issue.project_id
        groups = build_field_groups(issue, comment_bodies)

        # Separate scalar groups (core, repro) from per-comment talk list
        scalar_groups: dict[str, str] = {}
        comment_texts: list[str] = []
        for name, value in groups.items():
            if name == "talk":
                comment_texts = value  # list[str]
            else:
                scalar_groups[name] = value  # str

        # ── Scalar groups (core, repro): skip if content unchanged ──────────
        to_embed: dict[str, str] = {}
        for name, text in scalar_groups.items():
            if not text.strip():
                await delete_group(db, issue_id, name)
                continue
            h = content_hash(cfg["model"], text)
            existing_hash = await get_hash(db, issue_id, name)
            if existing_hash == h:
                continue
            to_embed[name] = text

        # ── Talk group: always delete old rows, then re-insert per-comment ──
        await delete_group(db, issue_id, "talk")
        for body in comment_texts:
            to_embed[f"__talk__{body}"] = body  # sentinel prefix to mark as talk

        if not to_embed:
            logger.debug("embed_issue(%s): all groups up-to-date", issue_id)
            return {"issue_id": issue_id, "groups_embedded": 0}

        # Batch embed everything in one call
        group_keys = list(to_embed.keys())
        texts = list(to_embed.values())
        vectors = await embed_texts(cfg, texts)

        # Validate dimension
        expected_dim = cfg["dimension"]
        for key, vec in zip(group_keys, vectors):
            if len(vec) != expected_dim:
                raise ValueError(
                    f"Embedding model returned dim={len(vec)}, expected dim={expected_dim}."
                )
            if key.startswith("__talk__"):
                body = to_embed[key]
                h = content_hash(cfg["model"], body)
                await upsert_embedding(db, issue_id, project_id, "talk", vec, h, cfg["model"])
            else:
                h = content_hash(cfg["model"], to_embed[key])
                await upsert_embedding(db, issue_id, project_id, key, vec, h, cfg["model"])

        await db.commit()

        # Invalidate Redis search cache for this project
        try:
            import redis.asyncio as aioredis
            from app.config import settings as _s
            r = aioredis.from_url(_s.REDIS_URL, decode_responses=True)
            pattern = f"search:{project_id}:*"
            cursor = 0
            while True:
                cursor, keys = await r.scan(cursor, match=pattern, count=100)
                if keys:
                    await r.delete(*keys)
                if cursor == 0:
                    break
            await r.aclose()
        except Exception:
            logger.warning("Failed to invalidate search cache for project %s", project_id)

        logger.info(
            "embed_issue(%s): embedded groups=%s", issue_id, group_names
        )
        return {"issue_id": issue_id, "groups_embedded": len(group_names), "groups": group_names}
