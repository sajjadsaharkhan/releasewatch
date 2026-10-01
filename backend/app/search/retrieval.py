"""Stage-1 retrieval (slice 12, engine PRD Appendix A.8).

``search(db, actor, query, scope=…, filters=…, mode=…)``:

1. Normalize the query and embed it (Redis-cached 5 min per endpoint, model and query).
2. Four channels, each restricted to the scope, the filters, what the actor
   may see (``visibility_clause``, slice 04), and index rows of the model that
   embedded the query (BR-S16):
   ``body`` / ``title`` / ``talk`` — best cosine per item; ``talk`` skips
   internal notes for anyone who may not see them (BR-S06) — and ``keyword``,
   trigram ``word_similarity ≥ T_TRGM``, top 3 only.
3. Weighted reciprocal rank fusion.
4. Drop results whose best dense cosine is under ``T_FLOOR`` unless the
   (already gated) keyword channel found them.
5. Jev off (or failing): keep the top 20 in local order. Jev on, search page
   only: Jev reranks the top 15 and splits them at ``T_RELEVANT`` into
   ``results`` and ``less_relevant`` (slice 13).

Because visibility is applied inside every channel, an item reaches the
results only if a channel the actor may use matched it (AC-S05). When the
embedding service is down, only the keyword channel answers — search still
works, with lower quality (principle S1).
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field

from sqlalchemy import Select, and_, case, func, not_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.redis_client import get_redis_raw
from app.db.models.issue import Issue, IssueStatus, issue_key
from app.db.models.issue_timeline import IssueTimeline
from app.db.models.search import CommentLabel, SearchItem, SearchVector
from app.db.models.user import User
from app.search import embeddings, jev_settings
from app.search.constants import (
    CHANNEL_LIMIT,
    FUSION_WEIGHTS,
    HYDRATE_LIMIT,
    JEV_CANDIDATES,
    KEYWORD_TOP,
    PALETTE_LIMIT,
    QUERY_CACHE_TTL,
    RESULT_LIMIT,
    RRF_K,
    T_FLOOR,
    T_RELEVANT,
    T_TRGM,
)
from app.search.jev import JevItem
from app.search.normalize import fold, normalize, strip_markdown
from app.services.authz import sees_internal, visibility_clause

logger = logging.getLogger(__name__)

DENSE_CHANNELS = ("body", "title", "talk")
SNIPPET_CHARS = 200


@dataclass
class Filters:
    project_id: int | None = None
    types: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=list)


@dataclass
class Hit:
    issue_id: int
    score: float = 0.0
    #: Best cosine per dense channel, and the keyword similarity.
    sims: dict[str, float] = field(default_factory=dict)
    #: The comment that matched best, when the talk channel found the item.
    talk_timeline_id: int | None = None

    @property
    def best_dense(self) -> float:
        return max((self.sims[c] for c in DENSE_CHANNELS if c in self.sims), default=0.0)

    @property
    def matched_by_comment(self) -> bool:
        talk = self.sims.get("talk")
        return talk is not None and talk >= max(
            self.sims.get("body", 0.0), self.sims.get("title", 0.0)
        )


@dataclass
class Ranked:
    results: list[dict]
    less_relevant: list[dict] = field(default_factory=list)
    jev_used: bool = False

    def as_dict(self) -> dict:
        return {
            "results": self.results,
            "less_relevant": self.less_relevant,
            "jev_used": self.jev_used,
        }


# ── Query vector ─────────────────────────────────────────────────────────────


def _cache_key(endpoint: str, model: str, q: str) -> str:
    raw = f"{endpoint}\x00{model}\x00{q}"
    return "rw:search:qv:" + hashlib.sha256(raw.encode()).hexdigest()[:32]


async def _query_vector(db: AsyncSession, q: str) -> tuple[list[float] | None, str | None]:
    """``(vector, model)``; ``(None, last known model)`` when the service fails."""
    config = await embeddings.load_config(db)
    redis = await get_redis_raw()
    if config.embed_model:
        try:
            cached = await redis.get(_cache_key(config.endpoint, config.embed_model, q))
            if cached:
                return json.loads(cached), config.embed_model
        except Exception:  # noqa: BLE001 — a cache miss is never an error
            pass
    try:
        result = await embeddings.embed(config.endpoint, [q])
    except embeddings.EmbeddingError as exc:
        logger.warning("search: query embedding failed, keyword channel only: %s", exc)
        return None, config.embed_model
    if result.model != config.embed_model:
        # The service now serves another model behind the same endpoint. The
        # query only reads rows of the model that embedded it (BR-S16), so
        # nothing matches until the reindex this starts (once, guarded) lands.
        logger.warning(
            "search: endpoint now serves %s (index: %s); reindexing",
            result.model,
            config.embed_model,
        )
        from app.tasks.search_index import request_reindex_all

        request_reindex_all()
    vector = result.vectors[0]
    try:
        await redis.set(
            _cache_key(config.endpoint, result.model, q),
            json.dumps(vector),
            ex=QUERY_CACHE_TTL,
        )
    except Exception:  # noqa: BLE001
        pass
    return vector, result.model


# ── Channels ─────────────────────────────────────────────────────────────────


def _scoped(stmt: Select, actor: User, model: str, filters: Filters) -> Select:
    stmt = stmt.join(Issue, Issue.id == SearchItem.issue_id).where(
        Issue.deleted_at.is_(None),
        visibility_clause(actor),
        SearchItem.embed_model == model,
    )
    if filters.project_id is not None:
        stmt = stmt.where(SearchItem.project_id == filters.project_id)
    if filters.types:
        stmt = stmt.where(SearchItem.type.in_(filters.types))
    if filters.statuses:
        stmt = stmt.where(SearchItem.status.in_(filters.statuses))
    return stmt


async def _dense_channel(
    db: AsyncSession,
    kind: str,
    vector: list[float],
    model: str,
    actor: User,
    filters: Filters,
) -> list[tuple[int, int | None, float]]:
    sim = 1 - SearchVector.embedding.cosine_distance(vector)
    # Talk comments rank by their label weight (A.6: other_problem counts half);
    # the floor still judges the raw cosine — a weak label is not a weak match.
    rank = sim * _talk_weight_sql() if kind == "talk" else sim
    best = (
        select(
            SearchVector.issue_id, SearchVector.timeline_id,
            sim.label("sim"), rank.label("rank"),
        )
        .select_from(SearchVector)
        .join(
            SearchItem,
            and_(
                SearchItem.issue_id == SearchVector.issue_id,
                SearchItem.embed_model == SearchVector.embed_model,
            ),
        )
        .where(SearchVector.kind == kind)
        .distinct(SearchVector.issue_id)
        .order_by(SearchVector.issue_id, rank.desc())
    )
    if kind == "talk":
        best = best.outerjoin(CommentLabel, CommentLabel.timeline_id == SearchVector.timeline_id)
        if not sees_internal(actor):
            best = best.where(not_(SearchVector.is_internal))
    best = _scoped(best, actor, model, filters).subquery()
    rows = await db.execute(
        select(best.c.issue_id, best.c.timeline_id, best.c.sim)
        .order_by(best.c.rank.desc(), best.c.issue_id)
        .limit(CHANNEL_LIMIT)
    )
    return [(r.issue_id, r.timeline_id, float(r.sim)) for r in rows]


def _talk_weight_sql():
    """``comment_rules.talk_weight`` as SQL over ``comment_labels``. A talk row
    exists only for a used comment, so a missing label counts fully."""
    from app.search.comment_rules import (
        JEV_LABELS,
        LOW_CONFIDENCE,
        OTHER_PROBLEM,
        OTHER_PROBLEM_WEIGHT,
        RULE_KEPT,
        THIS_PROBLEM,
    )

    return case(
        (CommentLabel.label.is_(None), 1.0),
        (CommentLabel.label.in_([RULE_KEPT, THIS_PROBLEM]), 1.0),
        (and_(CommentLabel.label.in_(sorted(JEV_LABELS)), CommentLabel.confidence < LOW_CONFIDENCE), 1.0),
        (CommentLabel.label == OTHER_PROBLEM, OTHER_PROBLEM_WEIGHT),
        else_=0.0,
    )


async def _keyword_channel(
    db: AsyncSession,
    q: str,
    model: str,
    actor: User,
    filters: Filters,
) -> list[tuple[int, float]]:
    folded = fold(q)
    if not folded:
        return []
    ws = func.word_similarity(folded, SearchItem.keyword_text)
    stmt = _scoped(select(SearchItem.issue_id, ws.label("ws")), actor, model, filters)
    rows = await db.execute(
        stmt.where(ws >= T_TRGM).order_by(ws.desc(), SearchItem.issue_id).limit(KEYWORD_TOP)
    )
    return [(r.issue_id, float(r.ws)) for r in rows]


async def _current_model(db: AsyncSession) -> str | None:
    return (await embeddings.load_config(db)).embed_model


# ── Fusion ───────────────────────────────────────────────────────────────────


def fuse(channels: dict[str, list[tuple[int, float]]]) -> list[Hit]:
    """Weighted RRF over ranked ``(issue_id, similarity)`` lists. Pure."""
    hits: dict[int, Hit] = {}
    for channel, ranked in channels.items():
        weight = FUSION_WEIGHTS[channel]
        for rank, (issue_id, sim) in enumerate(ranked, start=1):
            hit = hits.setdefault(issue_id, Hit(issue_id))
            hit.score += weight / (RRF_K + rank)
            hit.sims[channel] = sim
    return sorted(hits.values(), key=lambda h: (-h.score, h.issue_id))


def apply_floor(hits: list[Hit], *, dense_available: bool) -> list[Hit]:
    """FR-S04: junk stays out. A keyword-channel hit is kept — it already passed
    ``T_TRGM`` — so an endpoint path or an error code is still found."""
    if not dense_available:
        return hits
    return [h for h in hits if h.best_dense >= T_FLOOR or "keyword" in h.sims]


async def _jev_rerank(
    db: AsyncSession, query: str, hits: list[Hit],
) -> tuple[list[Hit], list[Hit], bool]:
    """A.8 step 6: Jev judges the top ``JEV_CANDIDATES`` (already floored and
    visible to the actor) and only reorders and splits them (BR-S04). Any
    failure — off, no key, timeout, error, malformed — is the Jev-off result
    unchanged (BR-S02). The payload is the title and a description excerpt;
    comments, internal or not, never leave."""
    jev = await jev_settings.client(db)
    if jev is None or not hits:
        return hits, [], False
    top = hits[:JEV_CANDIDATES]
    rows = {
        i.id: i for i in (await db.execute(
            select(Issue.id, Issue.title, Issue.description, Issue.type)
            .where(Issue.id.in_([h.issue_id for h in top]))
        )).all()
    }
    items = [
        JevItem(
            id=h.issue_id, title=rows[h.issue_id].title,
            description=normalize(strip_markdown(rows[h.issue_id].description)),
            type=getattr(rows[h.issue_id].type, "value", rows[h.issue_id].type),
        )
        for h in top if h.issue_id in rows
    ]
    outcome, scores = await jev.rerank(query, items)
    if not outcome.ok:
        return hits, [], False
    judged = [h for h in top if h.issue_id in scores]
    ordered = sorted(judged, key=lambda h: -scores[h.issue_id])  # stable: ties keep fusion order
    results = [h for h in ordered if scores[h.issue_id] >= T_RELEVANT]
    less = [h for h in ordered if scores[h.issue_id] < T_RELEVANT]
    return results, less, True


# ── Hydration ────────────────────────────────────────────────────────────────


def _snippet(text: str | None) -> str | None:
    plain = normalize(strip_markdown(text))
    if not plain:
        return None
    return plain if len(plain) <= SNIPPET_CHARS else plain[:SNIPPET_CHARS].rstrip() + "…"


def _value(x):
    return getattr(x, "value", x)


async def _hydrate(
    db: AsyncSession,
    hits: list[Hit],
    *,
    comment_snippets: bool,
    matched: dict[int, list[str]],
) -> list[dict]:
    if not hits:
        return []
    ids = [h.issue_id for h in hits]
    issues = {
        i.id: i
        for i in (
            await db.execute(
                select(Issue).where(Issue.id.in_(ids)).options(selectinload(Issue.project))
            )
        )
        .scalars()
        .all()
    }
    comment_ids = [
        h.talk_timeline_id
        for h in hits
        if comment_snippets and h.matched_by_comment and h.talk_timeline_id
    ]
    comments = {}
    if comment_ids:
        comments = {
            c.id: c.body
            for c in (
                await db.execute(select(IssueTimeline).where(IssueTimeline.id.in_(comment_ids)))
            )
            .scalars()
            .all()
        }

    out = []
    for h in hits:
        issue = issues.get(h.issue_id)
        if issue is None:
            continue
        snippet, source = _snippet(issue.description), "description"
        if comment_snippets and h.matched_by_comment and h.talk_timeline_id in comments:
            snippet, source = _snippet(comments[h.talk_timeline_id]), "comment"
        status = _value(issue.status)
        out.append(
            {
                "issue_id": issue.id,
                "issue_number": issue.issue_number,
                "key": issue_key(issue.type, issue.issue_number),
                "type": _value(issue.type),
                "title": issue.title,
                "status": status,
                "priority": _value(issue.priority),
                "is_cancelled": status == IssueStatus.cancelled.value,
                "project": {
                    "id": issue.project.id,
                    "name": issue.project.name,
                    "slug": issue.project.slug,
                },
                "snippet": snippet,
                "snippet_source": source if snippet else None,
                "matched_via": matched.get(issue.id, []),
                "score": round(h.score, 6),
            }
        )
    return out


# ── Entry point ──────────────────────────────────────────────────────────────


async def search(
    db: AsyncSession,
    actor: User,
    query: str,
    *,
    filters: Filters,
    mode: str = "page",
) -> Ranked:
    q = normalize(query)
    if not q:
        return Ranked(results=[])

    vector, model = await _query_vector(db, q)
    if model is None:
        model = await _current_model(db)
    if model is None:
        return Ranked(results=[])  # nothing has ever been indexed

    channels: dict[str, list[tuple[int, float]]] = {}
    talk_best: dict[int, int | None] = {}
    if vector is not None:
        for kind in DENSE_CHANNELS:
            rows = await _dense_channel(db, kind, vector, model, actor, filters)
            channels[kind] = [(issue_id, sim) for issue_id, _, sim in rows]
            if kind == "talk":
                talk_best = {issue_id: tid for issue_id, tid, _ in rows}
    channels["keyword"] = await _keyword_channel(db, q, model, actor, filters)

    hits = fuse(channels)
    for h in hits:
        h.talk_timeline_id = talk_best.get(h.issue_id)
    hits = apply_floor(hits, dense_available=vector is not None)[:HYDRATE_LIMIT]

    less: list[Hit] = []
    jev_used = False
    if mode == "page":  # the palette never calls Jev (BR-S05)
        hits, less, jev_used = await _jev_rerank(db, query, hits)
    hits = hits[: PALETTE_LIMIT if mode == "palette" else RESULT_LIMIT]

    matched = {
        issue_id: [c for c, ranked in channels.items() if any(i == issue_id for i, _ in ranked)]
        for issue_id in {h.issue_id for h in hits + less}
    }
    comment_snippets = mode != "palette"
    return Ranked(
        results=await _hydrate(db, hits, comment_snippets=comment_snippets, matched=matched),
        less_relevant=await _hydrate(db, less, comment_snippets=comment_snippets, matched=matched),
        jev_used=jev_used,
    )
