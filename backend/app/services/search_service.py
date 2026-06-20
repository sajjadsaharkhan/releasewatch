"""SearchService — semantic + hybrid search over issues.

Retrieval pipeline:
  1. Build field-grouped embedding documents (core / repro / talk)
  2. Run two dense retrievers (core, talk) + one lexical retriever (tsvector)
  3. Fuse rankings with Reciprocal Rank Fusion (weighted)
  4. Optionally re-rank top-20 with the configured LLM
  5. Return hydrated results with matched_via signal for debuggability

When the LLM config is not set, falls back to pure lexical search.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# RRF query weights: core dense / talk dense / lexical
_WEIGHTS_CORE = 0.55
_WEIGHTS_TALK = 0.20
_WEIGHTS_LEX = 0.40
_RRF_K = 60
_CANDIDATE_LIMIT = 50  # each retriever fetches this many before fusion
_RERANK_LIMIT = 20     # top-N sent to optional LLM reranker
_SNIPPET_LEN = 200


# ── Config loading ────────────────────────────────────────────────────────────

_LOCAL_MODEL_DEFAULT = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_LOCAL_DIM_DEFAULT = 384

# e5 family requires query:/passage: prefixes for best quality
_E5_MODELS = {"intfloat/multilingual-e5-large"}


class EmbeddingConfigMissing(Exception):
    """Raised when embedding cannot proceed due to missing LLM settings."""


async def _load_llm_config(db: AsyncSession) -> dict[str, Any]:
    """Return the embedding config dict from system_settings.

    provider='local'  — uses fastembed ONNX model, no external API needed.
    provider='api'    — uses the configured OpenAI-compatible endpoint.
    """
    result = await db.execute(
        text("SELECT value FROM system_settings WHERE category='llm' AND key='config' AND is_active=true LIMIT 1")
    )
    row = result.scalar_one_or_none()
    cfg = row if isinstance(row, dict) else (json.loads(row) if isinstance(row, str) else {})

    provider = cfg.get("embeddingProvider") or cfg.get("embedding_provider") or "local"

    if provider == "local":
        local_model = cfg.get("localModel") or cfg.get("local_model") or _LOCAL_MODEL_DEFAULT
        return {
            "provider": "local",
            "model": local_model,
            "dimension": _LOCAL_DIM_DEFAULT,
            "rerank_enabled": bool(cfg.get("rerankEnabled") or cfg.get("rerank_enabled", False)),
        }

    # API provider — requires full credentials
    base_url = cfg.get("baseUrl") or cfg.get("base_url", "")
    api_key = cfg.get("apiKey") or cfg.get("api_key", "")
    model = cfg.get("embeddingModel") or cfg.get("embedding_model", "")

    if not (base_url and api_key and model):
        raise EmbeddingConfigMissing("LLM base_url / api_key / embedding_model not configured")

    return {
        "provider": "api",
        "base_url": base_url.rstrip("/"),
        "api_key": api_key,
        "model": model,
        "dimension": int(cfg.get("embeddingDimension") or cfg.get("embedding_dimension") or 1536),
        "rerank_enabled": bool(cfg.get("rerankEnabled") or cfg.get("rerank_enabled", False)),
    }


# ── Document building ─────────────────────────────────────────────────────────

def _normalize(text_: str) -> str:
    """Strip markdown syntax and collapse whitespace."""
    t = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text_)   # [link](url) → link
    t = re.sub(r'```[\s\S]*?```', ' ', t)                 # fenced code blocks
    t = re.sub(r'`[^`]+`', ' ', t)                        # inline code
    t = re.sub(r'[*_#>~\-]+', ' ', t)                    # markdown punctuation
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def build_field_groups(issue: Any, comment_bodies: list[str]) -> dict[str, str | list[str]]:
    """Return {group_name: text_or_list} for each non-empty group.

    "talk" is returned as a list of individual comment texts so each comment
    is embedded separately, giving precise per-comment retrieval.
    """
    core: list[str] = [f"Title: {issue.title}", f"Title: {issue.title}"]  # double-weight
    if issue.description:
        core.append(f"Description: {_normalize(issue.description)}")
    if issue.labels:
        core.append(f"Labels: {', '.join(issue.labels)}")

    repro: list[str] = []
    env_parts = [
        v for v in [issue.environment_name, issue.environment_browser, issue.environment_os]
        if v
    ]
    if env_parts:
        repro.append(f"Environment: {' / '.join(env_parts)}")
    if issue.reproduction_steps:
        for i, step in enumerate(issue.reproduction_steps or [], 1):
            if not isinstance(step, dict):
                continue
            parts = [p for p in [
                step.get("description"),
                f"expected: {step['expected_result']}" if step.get("expected_result") else None,
                f"actual: {step['actual_result']}"   if step.get("actual_result") else None,
            ] if p and len(p.strip()) >= 15]
            if parts:
                repro.append(f"Step {i}: {' / '.join(parts)}")
    if issue.curl_command:
        repro.append(f"curl: {issue.curl_command}")

    comments = [_normalize(b) for b in comment_bodies if b and len(b.strip()) >= 20]

    result: dict[str, str | list[str]] = {}
    core_text = " ".join(core)
    if len(core_text.strip()) >= 30:
        result["core"] = core_text
    repro_text = " ".join(repro)
    if len(repro_text.strip()) >= 30:
        result["repro"] = repro_text
    if comments:
        result["talk"] = comments  # list — one embedding per comment
    return result


def content_hash(model: str, text_: str) -> str:
    """Stable hash of (model, normalized text) to detect unchanged groups."""
    payload = f"{model}:{_normalize(text_)}"
    return hashlib.sha256(payload.encode()).hexdigest()[:32]


# ── Local ONNX embedding (fastembed) ─────────────────────────────────────────

_fastembed_instance: Any = None
_fastembed_lock = asyncio.Lock()


async def _embed_local(model_name: str, texts: list[str], prefix: str = "") -> list[list[float]]:
    """Embed texts using a local fastembed ONNX model — no external API call."""
    global _fastembed_instance
    loop = asyncio.get_event_loop()

    async with _fastembed_lock:
        if _fastembed_instance is None:
            from fastembed import TextEmbedding
            _fastembed_instance = await loop.run_in_executor(
                None, lambda: TextEmbedding(model_name)
            )

    prefixed = [f"{prefix}{t}" if prefix else t for t in texts]
    model = _fastembed_instance
    embeddings = await loop.run_in_executor(None, lambda: list(model.embed(prefixed)))
    return [v.tolist() for v in embeddings]


# ── Embedding API (external OpenAI-compatible) ────────────────────────────────

async def embed_texts(cfg: dict, texts: list[str], is_query: bool = False) -> list[list[float]]:
    """Embed texts via local ONNX model or external API depending on provider."""
    if cfg.get("provider") == "local":
        prefix = ("query: " if is_query else "passage: ") if cfg["model"] in _E5_MODELS else ""
        return await _embed_local(cfg["model"], texts, prefix=prefix)

    # External OpenAI-compatible API
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    payload: dict[str, Any] = {"model": cfg["model"], "input": texts}
    # Honor dimensions param when specified (OpenAI v3 truncation)
    if cfg.get("dimension") and cfg["dimension"] != 1536:
        payload["dimensions"] = cfg["dimension"]

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{cfg['base_url']}/embeddings",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()

    data = resp.json()
    return [item["embedding"] for item in sorted(data["data"], key=lambda x: x["index"])]


# ── Database helpers ──────────────────────────────────────────────────────────

async def upsert_embedding(
    db: AsyncSession,
    issue_id: int,
    project_id: int,
    group: str,
    vector: list[float],
    chash: str,
    model: str,
) -> None:
    vec_str = f"[{','.join(str(v) for v in vector)}]"
    await db.execute(
        text("""
            INSERT INTO issue_embeddings (issue_id, project_id, field_group, embedding, content_hash, model, updated_at)
            VALUES (:issue_id, :project_id, :group, CAST(:vec AS vector), :hash, :model, now())
            ON CONFLICT (issue_id, field_group, content_hash)
            DO UPDATE SET
                embedding    = EXCLUDED.embedding,
                model        = EXCLUDED.model,
                updated_at   = now()
        """),
        {
            "issue_id": issue_id,
            "project_id": project_id,
            "group": group,
            "vec": vec_str,
            "hash": chash,
            "model": model,
        },
    )


async def get_hash(db: AsyncSession, issue_id: int, group: str) -> str | None:
    result = await db.execute(
        text("SELECT content_hash FROM issue_embeddings WHERE issue_id=:i AND field_group=:g"),
        {"i": issue_id, "g": group},
    )
    return result.scalar_one_or_none()


async def delete_group(db: AsyncSession, issue_id: int, group: str) -> None:
    await db.execute(
        text("DELETE FROM issue_embeddings WHERE issue_id=:i AND field_group=:g"),
        {"i": issue_id, "g": group},
    )


# ── RRF fusion ────────────────────────────────────────────────────────────────

def rrf_fuse(
    rankings: list[list[int]],
    weights: list[float],
    k: int = _RRF_K,
) -> list[tuple[int, float]]:
    """Weighted Reciprocal Rank Fusion over multiple ranked lists of issue IDs."""
    scores: dict[int, float] = {}
    for issue_ids, weight in zip(rankings, weights):
        for rank, issue_id in enumerate(issue_ids):
            scores[issue_id] = scores.get(issue_id, 0.0) + weight / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# ── Retrievers ────────────────────────────────────────────────────────────────

_COSINE_DISTANCE_THRESHOLD = 0.55  # cosine distance; 0=identical, 2=opposite

async def dense_search(
    db: AsyncSession,
    qvec: list[float],
    project_id: int,
    group: str,
    limit: int = _CANDIDATE_LIMIT,
) -> list[int]:
    """Return issue_ids ordered by cosine similarity against one field group.

    Only returns rows whose cosine distance is below the threshold so that
    irrelevant / garbage queries produce no dense hits.
    """
    vec_str = f"[{','.join(str(v) for v in qvec)}]"
    result = await db.execute(
        text("""
            WITH best AS (
                SELECT issue_id,
                       MIN(embedding <=> CAST(:vec AS vector)) AS dist
                FROM issue_embeddings
                WHERE project_id = :pid AND field_group = :grp
                GROUP BY issue_id
            )
            SELECT issue_id FROM best
            WHERE dist < :thresh
            ORDER BY dist
            LIMIT :lim
        """),
        {"pid": project_id, "grp": group, "vec": vec_str, "lim": limit, "thresh": _COSINE_DISTANCE_THRESHOLD},
    )
    return [row[0] for row in result.fetchall()]


async def lexical_search(
    db: AsyncSession,
    query: str,
    project_id: int,
    limit: int = _CANDIDATE_LIMIT,
) -> list[int]:
    """Return issue_ids ordered by full-text rank (tsvector on title + description)."""
    result = await db.execute(
        text("""
            SELECT id
            FROM issues
            WHERE project_id = :pid
              AND search_tsv @@ websearch_to_tsquery('english', :q)
            ORDER BY ts_rank(search_tsv, websearch_to_tsquery('english', :q)) DESC
            LIMIT :lim
        """),
        {"pid": project_id, "q": query, "lim": limit},
    )
    return [row[0] for row in result.fetchall()]


# ── Optional LLM reranker ─────────────────────────────────────────────────────

async def llm_rerank(
    cfg: dict,
    query: str,
    candidates: list[dict],
) -> list[dict]:
    """Re-rank top candidates using the configured LLM (chat completions).

    Each candidate gets a 0-1 relevance score; sorted descending.
    Falls back to original order on any error.
    """
    if not candidates:
        return candidates

    docs = "\n".join(
        f"{i+1}. [{c['issue_number']}] {c['title']}: {(c.get('snippet') or '')[:100]}"
        for i, c in enumerate(candidates)
    )
    prompt = (
        f"Rate the relevance of each issue to the query: \"{query}\"\n\n"
        f"{docs}\n\n"
        "Respond with a JSON array of {\"rank\": <1-based index>, \"score\": <0.0-1.0>} "
        "objects, one per issue, sorted by score descending. Only JSON, no prose."
    )

    try:
        headers = {
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{cfg['base_url']}/chat/completions",
                headers=headers,
                json={
                    "model": cfg["model"],
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0,
                },
            )
            resp.raise_for_status()

        content = resp.json()["choices"][0]["message"]["content"].strip()
        # Strip markdown code fence if present
        content = re.sub(r"^```[a-z]*\n?", "", content)
        content = re.sub(r"\n?```$", "", content)
        scores = json.loads(content)
        rank_map = {item["rank"]: item["score"] for item in scores}
        reranked = sorted(
            [(candidates[i - 1], rank_map.get(i, 0.0)) for i in range(1, len(candidates) + 1)],
            key=lambda x: x[1],
            reverse=True,
        )
        for cand, score in reranked:
            cand["score"] = round(score, 4)
        return [c for c, _ in reranked]
    except Exception:
        logger.exception("LLM reranker failed; returning original order")
        return candidates


# ── Hydration ─────────────────────────────────────────────────────────────────

async def hydrate(
    db: AsyncSession,
    ranked: list[tuple[int, float]],
    matched_via: dict[int, list[str]],
) -> list[dict]:
    """Load issue metadata for ranked IDs and return response dicts."""
    if not ranked:
        return []

    ids = [r[0] for r in ranked]
    score_map = dict(ranked)

    result = await db.execute(
        text("""
            SELECT i.id, i.issue_number, i.title, i.severity, i.status,
                   i.description,
                   u.name AS assignee_name
            FROM issues i
            LEFT JOIN users u ON u.id = i.assignee_id
            WHERE i.id = ANY(:ids)
        """),
        {"ids": ids},
    )
    rows = {row[0]: row for row in result.fetchall()}

    out: list[dict] = []
    for issue_id, rrf_score in ranked:
        row = rows.get(issue_id)
        if row is None:
            continue
        desc = row[5] or ""
        snippet = _normalize(desc)[:_SNIPPET_LEN] + ("…" if len(desc) > _SNIPPET_LEN else "")
        out.append({
            "issue_id": row[0],
            "issue_number": row[1],
            "title": row[2],
            "severity": row[3],
            "status": row[4],
            "score": round(rrf_score, 4),
            "snippet": snippet,
            "matched_via": matched_via.get(issue_id, []),
            "assignee": row[6],
        })
    return out


# ── Query-vector cache ────────────────────────────────────────────────────────

_QVEC_TTL = 300  # 5 minutes — query embeddings are stable within a session


async def _cached_embed(cfg: dict, query: str) -> list[float]:
    """Return the query embedding, using Redis to skip repeat API calls."""
    from app.core.redis_client import get_redis_raw

    key = "qvec:{}:{}".format(
        cfg["model"],
        hashlib.sha256(query.lower().encode()).hexdigest()[:20],
    )
    try:
        r = await get_redis_raw()
        cached = await r.get(key)
        if cached is not None:
            return json.loads(cached)
    except Exception:
        pass  # Redis unavailable — fall through to API

    vecs = await embed_texts(cfg, [query], is_query=True)
    vec = vecs[0]

    try:
        r = await get_redis_raw()
        await r.set(key, json.dumps(vec), ex=_QVEC_TTL)
    except Exception:
        pass

    return vec


# ── Public search entry-point ─────────────────────────────────────────────────


async def search(
    db: AsyncSession,
    query: str,
    project_id: int,
    limit: int = 20,
) -> dict:
    """Run hybrid semantic search and return a results dict.

    Falls back to pure lexical search when LLM config is not set.
    """
    query = query.strip()
    if not query:
        return {"query": query, "results": [], "total": 0}

    matched_via: dict[int, list[str]] = {}

    try:
        cfg = await _load_llm_config(db)

        # Embed the query — check Redis cache first (TTL 5 min)
        qvec = await _cached_embed(cfg, query)

        # Three retrievers in parallel
        core_ids, talk_ids, lex_ids = await asyncio.gather(
            dense_search(db, qvec, project_id, "core"),
            dense_search(db, qvec, project_id, "talk"),
            lexical_search(db, query, project_id),
        )

        # If no retriever found anything, return empty immediately
        if not core_ids and not talk_ids and not lex_ids:
            return {"query": query, "results": [], "total": 0}

        # Track matched_via
        for rank, iid in enumerate(core_ids[:limit]):
            matched_via.setdefault(iid, []).append("core")
        for rank, iid in enumerate(talk_ids[:limit]):
            matched_via.setdefault(iid, []).append("talk")
        for rank, iid in enumerate(lex_ids[:limit]):
            matched_via.setdefault(iid, []).append("lexical")

        ranked = rrf_fuse(
            [core_ids, talk_ids, lex_ids],
            [_WEIGHTS_CORE, _WEIGHTS_TALK, _WEIGHTS_LEX],
        )[:limit * 2]  # over-fetch before optional rerank

        results = await hydrate(db, ranked, matched_via)

        # Optional LLM reranker
        if cfg.get("rerank_enabled") and results:
            results = await llm_rerank(cfg, query, results[:_RERANK_LIMIT])

        results = results[:limit]

    except EmbeddingConfigMissing:
        # Graceful degradation: lexical search only
        lex_ids = await lexical_search(db, query, project_id, limit=limit)
        for iid in lex_ids:
            matched_via[iid] = ["lexical"]
        ranked_lex = [(iid, 1.0 / (i + 1)) for i, iid in enumerate(lex_ids)]
        results = await hydrate(db, ranked_lex, matched_via)

    return {"query": query, "results": results, "total": len(results)}
