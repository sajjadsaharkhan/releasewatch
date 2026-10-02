"""Search index jobs (slice 12, engine PRD Appendix A.5), on Celery queue ``search``.

- ``index_item(issue_id)`` — rebuild one item's keyword row, recompute only the
  title/body/talk vectors whose text changed (hash compare, BR-S17), drop rows
  for comments that are gone or no longer used, and refresh the filter columns.
  A deleted item leaves the index.
- ``classify_comment(timeline_id)`` — the rule, then Jev when it is on (slice
  13); stores a ``comment_labels`` row. ``index_item`` labels any comment it
  finds without a current label the same way, so the two can run in either order.
- ``backfill_comment_classification()`` — when Jev is switched on, reclassify
  once the comments the rule kept, and reindex the items they belong to.
- ``compute_duplicate_hints(issue_id)`` — slice 14: when a bug enters New, its
  title or description changes while New, or it moves project during triage.
  Replaces the stored hints wholesale (``app/search/duplicate_hints.py``).
- ``reindex_all()`` — ask the endpoint which model it serves, record it, and
  enqueue ``index_item`` for every item. Progress = items indexed with that
  model / items, read from counts; the Redis key records the run.

Writers call ``enqueue(db, issue_id)`` — and ``enqueue_hints(db, issue_id)``
for the hint triggers — the jobs are sent only after ``db`` commits (a
rolled-back change never reindexes), debounced per item — one ``SETNX`` guard
and a 10 s countdown, so a burst of edits is one job.

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
from app.search import embeddings, jev_settings
from app.search.comment_rules import RULE_DROPPED, RULE_KEPT, rule_label
from app.search.documents import build_documents, content_hash
from app.search.jev import JevClient
from app.search.normalize import normalize, strip_markdown
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
_PENDING_HINTS = "search_duplicate_hints_pending"
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


def enqueue_hints(db: AsyncSession | Session, issue_id: int) -> None:
    """Recompute ``issue_id``'s duplicate hints once ``db`` commits (A.5)."""
    session = db.sync_session if isinstance(db, AsyncSession) else db
    session.info.setdefault(_PENDING_HINTS, set()).add(issue_id)


@event.listens_for(Session, "after_commit")
def _send_after_commit(session: Session) -> None:
    pending = session.info.pop(_PENDING, None)
    for issue_id in sorted(pending or ()):
        dispatch(issue_id)
    pending_hints = session.info.pop(_PENDING_HINTS, None)
    for issue_id in sorted(pending_hints or ()):
        dispatch_hints(issue_id)


@event.listens_for(Session, "after_soft_rollback")
def _forget_after_rollback(session: Session, previous_transaction) -> None:
    # Only the outermost rollback discards the work; a savepoint's does not.
    if previous_transaction.parent is None:
        session.info.pop(_PENDING, None)
        session.info.pop(_PENDING_HINTS, None)


def dispatch(issue_id: int) -> None:
    """Send ``index_item`` unless one is already waiting for this item."""
    try:
        if not _redis().set(_GUARD_KEY.format(issue_id), "1", nx=True, ex=_GUARD_TTL):
            return
    except redis.RedisError:
        logger.warning("search: debounce guard unavailable; enqueueing %s anyway", issue_id)
    index_item.apply_async((issue_id,), countdown=DEBOUNCE_SECONDS, queue=QUEUE)


#: The hint job's own guard key: recomputing can run while an index job waits.
_HINT_GUARD_KEY = "rw:search:hints:pending:{}"


def dispatch_hints(issue_id: int, countdown: int = DEBOUNCE_SECONDS) -> None:
    """Send ``compute_duplicate_hints`` unless one is already waiting. Edits
    wait out the debounce; opening a never-judged bug passes ``countdown=0``."""
    try:
        if not _redis().set(_HINT_GUARD_KEY.format(issue_id), "1", nx=True, ex=_GUARD_TTL):
            return
    except redis.RedisError:
        logger.warning("search: hint debounce guard unavailable; enqueueing %s anyway", issue_id)
    compute_duplicate_hints.apply_async((issue_id,), countdown=countdown, queue=QUEUE)


#: Opening a never-judged bug asks for a run at most once per this many seconds,
#: so a job that fails (or never stamps the bug) cannot turn polling into a
#: stream of paid Jev calls.
HINTS_ON_OPEN_TTL = 60
_HINTS_ON_OPEN_KEY = "rw:search:hints:open:{}"


def request_hints_on_open(issue_id: int) -> None:
    """Start a hint run for a bug opened before it was ever judged — now, not
    after an edit's debounce — but no more than once a minute per bug."""
    try:
        if not _redis().set(_HINTS_ON_OPEN_KEY.format(issue_id), "1", nx=True, ex=HINTS_ON_OPEN_TTL):
            return
    except redis.RedisError:
        logger.warning("search: on-open guard unavailable; skipping hints for %s", issue_id)
        return
    dispatch_hints(issue_id, countdown=0)


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

#: Label used for a comment in build_documents: the label, or (label, confidence) for Jev.
Label = str | tuple[str, float | None]


async def _store_label(
    db: AsyncSession, comment: IssueTimeline, h: str, label: str, *, source: str = "rule",
    confidence: float | None = None, jev_model: str | None = None,
) -> None:
    values = {
        "label": label, "source": source, "confidence": confidence, "content_hash": h,
        "jev_model": jev_model, "classified_at": func.now(), "issue_id": comment.issue_id,
    }
    stmt = insert(CommentLabel).values(timeline_id=comment.id, **values)
    await db.execute(
        stmt.on_conflict_do_update(index_elements=[CommentLabel.timeline_id], set_=values)
    )


async def classify(
    db: AsyncSession, comment: IssueTimeline, issue: Issue | None, jev: JevClient | None,
) -> Label:
    """Classify one comment and store it (A.6): the rule first — ``rule_dropped``
    stays dropped without a Jev call — then Jev when it is on. A failed Jev call
    stores the rule result with ``source='rule'``, so the backfill retries it."""
    h = content_hash(comment.body or "")
    label = rule_label(comment.body)
    if label != RULE_DROPPED and jev is not None and issue is not None:
        outcome, result = await jev.classify_comment(
            issue.title, normalize(strip_markdown(issue.description)),
            normalize(strip_markdown(comment.body)), background=True,
        )
        if outcome.ok and result:
            jev_label, confidence = result
            await _store_label(
                db, comment, h, jev_label, source="jev", confidence=confidence,
                jev_model=outcome.model or jev.model,
            )
            return (jev_label, confidence)
    await _store_label(db, comment, h, label)
    return label


async def _label_comments(
    db: AsyncSession, issue: Issue, comments: Iterable[IssueTimeline],
) -> dict[int, Label]:
    """The current label of each comment, classifying any comment that has none
    or whose text changed since it was classified. A stored label is kept as it
    is — a Jev label stays when Jev is switched off (BR-S14)."""
    comments = list(comments)
    if not comments:
        return {}
    rows = (await db.execute(
        select(CommentLabel).where(CommentLabel.timeline_id.in_([c.id for c in comments]))
    )).scalars().all()
    existing = {r.timeline_id: r for r in rows}
    jev: JevClient | None = None
    jev_loaded = False
    labels: dict[int, Label] = {}
    for c in comments:
        row = existing.get(c.id)
        if row is not None and row.content_hash == content_hash(c.body or ""):
            labels[c.id] = (row.label, row.confidence) if row.source == "jev" else row.label
            continue
        if not jev_loaded:
            jev, jev_loaded = await jev_settings.client(db), True
        labels[c.id] = await classify(db, c, issue, jev)
    return labels


async def classify_comment_now(timeline_id: int) -> Label | None:
    from app.db.session import task_session

    async with task_session() as db:
        comment = await db.get(IssueTimeline, timeline_id)
        if comment is None or _value(comment.event_type) not in TALK_EVENTS:
            return None
        issue = await db.get(Issue, comment.issue_id)
        label = await classify(db, comment, issue, await jev_settings.client(db))
        await db.commit()
    dispatch(comment.issue_id)
    return label


# ── Backfill when Jev is switched on (BR-S14, AC-S17) ─────────────────────────

BACKFILL_KEY = "rw:search:jev_backfill"
BACKFILL_BATCH = 100


def request_backfill() -> None:
    backfill_comment_classification.apply_async(queue=QUEUE)


async def backfill_comment_classification_now(now: datetime | None = None) -> dict:
    """Reclassify, once, the comments the rule kept (``source='rule'``,
    ``label='rule_kept'``) — in batches of 100 — and reindex the items whose
    labels changed. ``rule_dropped`` and Jev labels are never touched, so a
    second run finds nothing to do. Progress is written to Redis for Settings."""
    from app.db.session import task_session

    async with task_session() as db:
        jev = await jev_settings.client(db)
        if jev is None:
            return {"skipped": "jev_off"}
        total = await db.scalar(
            select(func.count()).select_from(CommentLabel)
            .where(CommentLabel.source == "rule", CommentLabel.label == RULE_KEPT)
        )
    progress = {
        "started_at": (now or datetime.now(tz=UTC)).isoformat(), "total": total or 0,
        "done": 0, "failed": 0, "finished_at": None,
    }

    def _save() -> None:
        try:
            _redis().set(BACKFILL_KEY, json.dumps(progress))
        except redis.RedisError:
            pass

    _save()
    last_id = 0
    touched: set[int] = set()
    while True:
        async with task_session() as db:
            rows = (await db.execute(
                select(CommentLabel)
                .where(
                    CommentLabel.source == "rule", CommentLabel.label == RULE_KEPT,
                    CommentLabel.timeline_id > last_id,
                )
                .order_by(CommentLabel.timeline_id)
                .limit(BACKFILL_BATCH)
            )).scalars().all()
            if not rows:
                break
            for row in rows:
                last_id = row.timeline_id
                comment = await db.get(IssueTimeline, row.timeline_id)
                if comment is None:
                    continue
                issue = await db.get(Issue, row.issue_id)
                label = await classify(db, comment, issue, jev)
                if isinstance(label, tuple):
                    progress["done"] += 1
                    touched.add(row.issue_id)
                else:
                    progress["failed"] += 1
            await db.commit()
        _save()
    progress["finished_at"] = datetime.now(tz=UTC).isoformat()
    _save()
    for issue_id in sorted(touched):
        dispatch(issue_id)
    return progress


def backfill_progress() -> dict | None:
    try:
        raw = _redis().get(BACKFILL_KEY)
        return json.loads(raw) if raw else None
    except (redis.RedisError, ValueError):
        return None


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
    labels = await _label_comments(db, issue, comments)
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
        result = await embeddings.embed(
            config.endpoint, [w["text"] for w in to_embed], **config.request_args()
        )
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
                result = await embeddings.embed(
                    config.endpoint, [w["text"] for w in to_embed], **config.request_args()
                )
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


# ── compute_duplicate_hints (slice 14) ───────────────────────────────────────


async def compute_duplicate_hints_now(issue_id: int) -> dict:
    from app.db.session import task_session
    from app.search import duplicate_hints

    try:
        _redis().delete(_HINT_GUARD_KEY.format(issue_id))
    except redis.RedisError:
        pass
    async with task_session() as db:
        result = await duplicate_hints.compute_in(db, issue_id)
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
        model = await embeddings.probe(config.endpoint, **config.request_args())
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


@celery_app.task(
    name="app.tasks.search_index.backfill_comment_classification", queue=QUEUE,
    soft_time_limit=3600, time_limit=3700,
)
def backfill_comment_classification() -> dict:
    return asyncio.run(backfill_comment_classification_now())


@celery_app.task(name="app.tasks.search_index.classify_comment", queue=QUEUE)
def classify_comment(timeline_id: int) -> str | None:
    return asyncio.run(classify_comment_now(timeline_id))


@celery_app.task(
    name="app.tasks.search_index.compute_duplicate_hints", queue=QUEUE,
    soft_time_limit=60, time_limit=90,
)
def compute_duplicate_hints(issue_id: int) -> dict:
    return asyncio.run(compute_duplicate_hints_now(issue_id))


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
