"""Search index jobs (slice 12, engine PRD Appendix A.5), on Celery queue ``search``.

- ``index_item(issue_id)`` — rebuild one item's keyword row, recompute only the
  title/body/talk vectors whose text changed (hash compare, BR-S17), drop rows
  for comments that are gone or no longer used, and refresh the filter columns.
  A deleted item leaves the index.
- ``classify_comment(timeline_id)`` — the comment rule (Jev from 13); stores a
  ``comment_labels`` row. ``index_item`` labels any comment it finds without a
  current label the same way, so the two can run in either order.
- ``reindex_all()`` — ask the endpoint which model it serves, record it, and
  enqueue ``index_item`` for every item. Progress = items indexed with that
  model / items, read from counts; the Redis key records the run.

Writers call ``enqueue(db, issue_id)``: the job is sent only after ``db``
commits (a rolled-back change never reindexes), debounced per item — one
``SETNX`` guard and a 10 s countdown, so a burst of edits is one job.

Tests call the ``*_now`` bodies directly (the scheduled-job seam from 01).
"""

import asyncio
import json
import logging
from collections.abc import Iterable
from datetime import UTC, datetime

import redis
from sqlalchemy import delete, event, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models.issue import Issue, IssueStatus
from app.db.models.issue_timeline import IssueTimeline, TimelineEventType
from app.db.models.search import CommentLabel, SearchItem, SearchVector
from app.search import embeddings
from app.search.comment_rules import rule_label
from app.search.documents import build_documents, content_hash
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

QUEUE = "search"
#: Seconds an edit waits before its item is reindexed (A.5).
DEBOUNCE_SECONDS = 10
#: The per-item guard outlives the countdown, in case the job is slow to start.
_GUARD_TTL = 120
_GUARD_KEY = "rw:search:pending:{}"
#: The last ``reindex_all`` run: ``{started_at, model, total}``.
REINDEX_KEY = "rw:search:reindex"
_REINDEX_GUARD_KEY = "rw:search:reindex:pending"

#: Timeline events whose body is searchable talk: comments, and a recurrence's
#: public comment (slice 07).
TALK_EVENTS = (TimelineEventType.comment.value, TimelineEventType.recurrence.value)

_PENDING = "search_index_pending"
#: Advisory-lock namespace for per-item index runs.
_LOCK_NS = 12_001


def _value(x):
    return getattr(x, "value", x)


def _redis() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL, socket_timeout=2)


# ── Triggers ─────────────────────────────────────────────────────────────────


def enqueue(db: AsyncSession | Session, issue_id: int) -> None:
    """Reindex ``issue_id`` once ``db`` commits (A.5 triggers)."""
    session = db.sync_session if isinstance(db, AsyncSession) else db
    session.info.setdefault(_PENDING, set()).add(issue_id)


@event.listens_for(Session, "after_commit")
def _send_after_commit(session: Session) -> None:
    pending = session.info.pop(_PENDING, None)
    for issue_id in sorted(pending or ()):
        dispatch(issue_id)


@event.listens_for(Session, "after_soft_rollback")
def _forget_after_rollback(session: Session, previous_transaction) -> None:
    # Only the outermost rollback discards the work; a savepoint's does not.
    if previous_transaction.parent is None:
        session.info.pop(_PENDING, None)


def dispatch(issue_id: int) -> None:
    """Send ``index_item`` unless one is already waiting for this item."""
    try:
        if not _redis().set(_GUARD_KEY.format(issue_id), "1", nx=True, ex=_GUARD_TTL):
            return
    except redis.RedisError:
        logger.warning("search: debounce guard unavailable; enqueueing %s anyway", issue_id)
    index_item.apply_async((issue_id,), countdown=DEBOUNCE_SECONDS, queue=QUEUE)


def request_reindex_all() -> bool:
    """Start a full reindex unless one is already queued. True when sent."""
    try:
        if not _redis().set(_REINDEX_GUARD_KEY, "1", nx=True, ex=_GUARD_TTL):
            return False
    except redis.RedisError:
        pass
    reindex_all.apply_async(queue=QUEUE)
    return True


# ── Comment labels ───────────────────────────────────────────────────────────


async def _label_comments(db: AsyncSession, comments: Iterable[IssueTimeline]) -> dict[int, str]:
    """The current label of each comment, classifying (by the rule) any comment
    that has none or whose text changed since it was classified."""
    comments = list(comments)
    if not comments:
        return {}
    rows = (
        (
            await db.execute(
                select(CommentLabel).where(CommentLabel.timeline_id.in_([c.id for c in comments]))
            )
        )
        .scalars()
        .all()
    )
    existing = {r.timeline_id: r for r in rows}
    labels: dict[int, str] = {}
    for c in comments:
        h = content_hash(c.body or "")
        row = existing.get(c.id)
        if row is not None and row.content_hash == h:
            labels[c.id] = row.label
            continue
        labels[c.id] = await _store_rule_label(db, c, h)
    return labels


async def _store_rule_label(db: AsyncSession, comment: IssueTimeline, h: str) -> str:
    label = rule_label(comment.body)
    stmt = insert(CommentLabel).values(
        timeline_id=comment.id,
        issue_id=comment.issue_id,
        label=label,
        source="rule",
        confidence=None,
        content_hash=h,
        jev_model=None,
        classified_at=func.now(),
    )
    await db.execute(
        stmt.on_conflict_do_update(
            index_elements=[CommentLabel.timeline_id],
            set_={
                "label": stmt.excluded.label,
                "source": "rule",
                "confidence": None,
                "content_hash": h,
                "jev_model": None,
                "classified_at": func.now(),
                "issue_id": comment.issue_id,
            },
        )
    )
    return label


async def classify_comment_now(timeline_id: int) -> str | None:
    from app.db.session import task_session

    async with task_session() as db:
        comment = await db.get(IssueTimeline, timeline_id)
        if comment is None or _value(comment.event_type) not in TALK_EVENTS:
            return None
        label = await _store_rule_label(db, comment, content_hash(comment.body or ""))
        await db.commit()
    dispatch(comment.issue_id)
    return label


# ── index_item ───────────────────────────────────────────────────────────────


async def _remove(db: AsyncSession, issue_id: int) -> None:
    await db.execute(delete(SearchVector).where(SearchVector.issue_id == issue_id))
    await db.execute(delete(SearchItem).where(SearchItem.issue_id == issue_id))


def _wanted(docs) -> list[dict]:
    rows = [
        {
            "kind": "title",
            "chunk_no": 0,
            "timeline_id": None,
            "is_internal": False,
            "text": docs.title,
        }
    ]
    rows += [
        {"kind": "body", "chunk_no": i, "timeline_id": None, "is_internal": False, "text": t}
        for i, t in enumerate(docs.body_chunks)
    ]
    rows += [
        {
            "kind": "talk",
            "chunk_no": 0,
            "timeline_id": t.timeline_id,
            "is_internal": t.is_internal,
            "text": t.text,
        }
        for t in docs.talk
    ]
    for r in rows:
        r["content_hash"] = content_hash(r["text"])
    return [r for r in rows if r["text"]]


def _slot(kind: str, chunk_no: int, timeline_id: int | None) -> tuple:
    return (kind, chunk_no, timeline_id)


async def index_item_in(db: AsyncSession, issue_id: int) -> dict:
    """Bring one item's index rows up to date inside ``db`` (not committed)."""
    # One run per item at a time: an edit landing mid-run starts a second job,
    # which waits here instead of inserting the same vector slots twice.
    await db.execute(text("SELECT pg_advisory_xact_lock(:ns, :id)"), {"ns": _LOCK_NS, "id": issue_id})
    issue = await db.get(Issue, issue_id)
    if issue is None or issue.deleted_at is not None:
        await _remove(db, issue_id)
        return {"issue_id": issue_id, "removed": True}

    comments = (
        (
            await db.execute(
                select(IssueTimeline)
                .where(
                    IssueTimeline.issue_id == issue_id,
                    IssueTimeline.event_type.in_(TALK_EVENTS),
                    IssueTimeline.body.is_not(None),
                )
                .order_by(IssueTimeline.created_at, IssueTimeline.id)
            )
        )
        .scalars()
        .all()
    )
    labels = await _label_comments(db, comments)
    docs = build_documents(issue, comments, labels)
    wanted = _wanted(docs)

    config = await embeddings.load_config(db)
    existing = (
        (await db.execute(select(SearchVector).where(SearchVector.issue_id == issue_id)))
        .scalars()
        .all()
    )
    by_slot = {_slot(v.kind, v.chunk_no, v.timeline_id): v for v in existing}

    def reusable(w: dict) -> bool:
        v = by_slot.get(_slot(w["kind"], w["chunk_no"], w["timeline_id"]))
        return (
            v is not None
            and config.embed_model is not None
            and v.embed_model == config.embed_model
            and v.content_hash == w["content_hash"]
        )

    to_embed = [w for w in wanted if not reusable(w)]
    model = config.embed_model
    if to_embed:
        result = await embeddings.embed(config.endpoint, [w["text"] for w in to_embed])
        if result.model != config.embed_model:
            # The service now serves another model: never keep vectors of two
            # models side by side (BR-S16) — embed this item fully, record the
            # model, and reindex everything else.
            if config.embed_model is not None:
                logger.warning(
                    "search: model changed %s → %s; starting a full reindex",
                    config.embed_model,
                    result.model,
                )
                request_reindex_all()
            await embeddings.save_config(db, embed_model=result.model)
            if len(to_embed) != len(wanted):
                to_embed = wanted
                result = await embeddings.embed(config.endpoint, [w["text"] for w in to_embed])
        model = result.model
        for w, vec in zip(to_embed, result.vectors, strict=True):
            w["embedding"] = vec

    keep_ids = {
        by_slot[_slot(w["kind"], w["chunk_no"], w["timeline_id"])].id
        for w in wanted
        if "embedding" not in w
    }
    stale = [v.id for v in existing if v.id not in keep_ids]
    if stale:
        await db.execute(delete(SearchVector).where(SearchVector.id.in_(stale)))
    for w in wanted:
        if "embedding" in w:
            db.add(
                SearchVector(
                    issue_id=issue_id,
                    kind=w["kind"],
                    chunk_no=w["chunk_no"],
                    timeline_id=w["timeline_id"],
                    is_internal=w["is_internal"],
                    content_hash=w["content_hash"],
                    embed_model=model,
                    embedding=w["embedding"],
                )
            )

    values = {
        "project_id": issue.project_id,
        "type": _value(issue.type),
        "status": _value(issue.status),
        "source": _value(issue.source),
        "priority": _value(issue.priority),
        "is_cancelled": _value(issue.status) == IssueStatus.cancelled.value,
        "keyword_text": docs.keyword_text,
        "keyword_hash": content_hash(docs.keyword_text),
        "embed_model": model,
        "indexed_at": func.now(),
    }
    stmt = insert(SearchItem).values(issue_id=issue_id, **values)
    await db.execute(stmt.on_conflict_do_update(index_elements=[SearchItem.issue_id], set_=values))
    await db.flush()
    return {
        "issue_id": issue_id,
        "embedded": [f"{w['kind']}:{w['chunk_no']}:{w['timeline_id']}" for w in to_embed],
        "removed_vectors": len(stale),
    }


async def index_item_now(issue_id: int) -> dict:
    from app.db.session import task_session

    try:
        _redis().delete(_GUARD_KEY.format(issue_id))
    except redis.RedisError:
        pass
    async with task_session() as db:
        result = await index_item_in(db, issue_id)
        await db.commit()
    return result


# ── reindex_all ──────────────────────────────────────────────────────────────


async def reindex_all_now(now: datetime | None = None) -> dict:
    from app.db.session import task_session

    try:
        _redis().delete(_REINDEX_GUARD_KEY)
    except redis.RedisError:
        pass
    async with task_session() as db:
        config = await embeddings.load_config(db)
        model = await embeddings.probe(config.endpoint)
        await embeddings.save_config(db, embed_model=model)
        ids = (
            (
                await db.execute(
                    select(Issue.id).where(Issue.deleted_at.is_(None)).order_by(Issue.id)
                )
            )
            .scalars()
            .all()
        )
        # Items deleted since they were indexed.
        live = select(Issue.id).where(Issue.deleted_at.is_(None))
        await db.execute(delete(SearchVector).where(SearchVector.issue_id.not_in(live)))
        await db.execute(delete(SearchItem).where(SearchItem.issue_id.not_in(live)))
        await db.commit()

    run = {
        "started_at": (now or datetime.now(tz=UTC)).isoformat(),
        "model": model,
        "total": len(ids),
    }
    try:
        _redis().set(REINDEX_KEY, json.dumps(run))
    except redis.RedisError:
        logger.warning("search: could not record the reindex run")
    for issue_id in ids:
        dispatch(issue_id)
    return run


async def bootstrap_if_empty() -> bool:
    """Worker start (A.11): items exist but the index is empty → reindex all."""
    from app.db.session import task_session

    async with task_session() as db:
        indexed = await db.scalar(select(func.count()).select_from(SearchItem))
        items = await db.scalar(
            select(func.count()).select_from(Issue).where(Issue.deleted_at.is_(None))
        )
    if indexed == 0 and items:
        return request_reindex_all()
    return False


# ── Celery tasks ─────────────────────────────────────────────────────────────


@celery_app.task(
    bind=True,
    name="app.tasks.search_index.index_item",
    queue=QUEUE,
    max_retries=5,
    default_retry_delay=30,
    soft_time_limit=120,
    time_limit=180,
)
def index_item(self, issue_id: int) -> dict:
    try:
        return asyncio.run(index_item_now(issue_id))
    except embeddings.EmbeddingError as exc:
        logger.warning("index_item(%s): %s", issue_id, exc)
        raise self.retry(exc=exc) from exc


@celery_app.task(name="app.tasks.search_index.classify_comment", queue=QUEUE)
def classify_comment(timeline_id: int) -> str | None:
    return asyncio.run(classify_comment_now(timeline_id))


@celery_app.task(
    bind=True,
    name="app.tasks.search_index.reindex_all",
    queue=QUEUE,
    max_retries=10,
    default_retry_delay=30,
)
def reindex_all(self) -> dict:
    try:
        return asyncio.run(reindex_all_now())
    except embeddings.EmbeddingError as exc:
        logger.warning("reindex_all: %s", exc)
        raise self.retry(exc=exc) from exc
