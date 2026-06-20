# Semantic Search — Design Plan (v2)

> **What changed from v1 and why.** v1 used a single concatenated document → one
> vector, cosine search, a hardcoded `0.4` threshold, ivfflat index, and treated
> hybrid/lexical search as optional. Three problems with that:
> 1. **Uniform weighting** — concatenation embeds to a length-weighted average, so a
>    long comment thread drowns the title. Title/description carry more signal and
>    must be weighted higher.
> 2. **Score compression** — issues within one product share vocabulary and cluster
>    tightly (embedding anisotropy). Cosine scores collapse into a narrow high band,
>    so an **absolute threshold is fragile**. Relative top-K ranking survives this;
>    a fixed cutoff does not.
> 3. **Dense-only misses exact tokens** — a QA tracker is full of error codes, stack
>    traces, build hashes, browser/OS strings, `curl` commands. Lexical match wins on
>    those. Hybrid is **core, not optional**.
>
> The metric itself (cosine) is *not* the problem — cosine is monotonically equivalent
> to dot product on normalized vectors, so switching metrics buys nothing. The fix is
> **field-weighted multi-vector embedding + hybrid retrieval fused with RRF + top-K
> ranking (no fixed threshold) + HNSW index**, with an **optional LLM reranker**.

---

## Approach Summary

Still entirely on the **current stack**: PostgreSQL + `pgvector`, Celery worker, Redis,
the LLM config already in `system_settings`. No new services. The intelligence comes
from *how* we embed and *how* we retrieve, not from new infrastructure.

```
                    ┌──────────────────── INDEXING (Celery) ─────────────────────┐
  issue/comment ──▶ │ build field-grouped docs ─▶ embed each group ─▶ store rows  │
   change event     │   • core  = title + description + labels                    │
                    │   • repro = steps + env + curl                              │
                    │   • talk  = comment bodies                                  │
                    └────────────────────────────────────────────────────────────┘
                                          │
                    ┌──────────────────── QUERY (API) ───────────────────────────┐
   user query  ──▶  │ embed query                                                │
                    │   retriever A: dense vs core  (vector_cosine)              │
                    │   retriever B: dense vs talk  (vector_cosine)              │
                    │   retriever C: lexical FTS    (tsvector / ts_rank)         │
                    │            │                                                │
                    │            ▼  Reciprocal Rank Fusion (weighted)            │
                    │       fused candidate list (top ~50)                       │
                    │            │                                                │
                    │            ▼  [optional] LLM reranker on top ~20           │
                    │       final ranked results (top K)                         │
                    └────────────────────────────────────────────────────────────┘
```

---

## 1. Field weighting — the core fix

**Problem:** one concatenated vector averages everything, so weight ∝ text length, not
importance. A 2-word title and a 500-word comment thread end up roughly equal — or worse,
the title vanishes.

**Decision: multi-vector (field-grouped).** Embed *groups* of fields separately and
combine their rankings at query time. This gives explicit, tunable control instead of
accidental length-averaging.

### Field groups

| Group | Fields | Default query weight | Rationale |
|-------|--------|---------------------|-----------|
| `core` | `title`, `description`, `labels[]` | **0.55** | Highest-signal, human-curated summary |
| `repro` | `reproduction_steps[]`, `environment_*`, `curl_command` | **0.25** | Concrete repro detail; strong for "how it breaks" queries |
| `talk` | `IssueTimeline.body` where `event_type='comment'` | **0.20** | Discussion context; useful but noisy, must not dominate |

Within `core`, prepend `title` once more (light 2× boost) so the title still leads inside
its own group.

### Trade-off (stated honestly)

| | Multi-vector (chosen) | Weighted-single (fallback) |
|---|---|---|
| Weighting control | Explicit, per-group, tunable at query time | Crude (repeat title N×) |
| Embed cost | ~2–3× calls per issue | 1× |
| Storage | N rows per issue | 1 row |
| Query complexity | Fuse N retrievers | 1 lookup |
| Survives "comment drowns title" | **Yes** | Partially |

At this project's scale (one product's issues — hundreds to low thousands) embed cost is
negligible, so multi-vector's downside barely bites and its weighting control directly
answers the original complaint. **If** comment volume is consistently low, collapse to a
single `core`+`repro` vector and skip `talk` to halve cost — the schema below supports
both without change.

---

## 2. Storage — child table, HNSW, generated tsvector

`pgvector` extension + a child table keyed by `(issue_id, field_group)`. Keeping vectors
out of the `issues` row keeps the hot table lean and makes multi-vector natural.

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE issue_embeddings (
    id            bigserial PRIMARY KEY,
    issue_id      integer NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    project_id    integer NOT NULL,            -- denormalized for fast scoping
    field_group   text    NOT NULL,            -- 'core' | 'repro' | 'talk'
    embedding     vector(1536) NOT NULL,       -- dim from configured model (see §6)
    content_hash  text    NOT NULL,            -- skip re-embed when unchanged
    model         text    NOT NULL,            -- which model produced this vector
    updated_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (issue_id, field_group)
);

CREATE INDEX issue_embeddings_hnsw
    ON issue_embeddings USING hnsw (embedding vector_cosine_ops);

CREATE INDEX issue_embeddings_project ON issue_embeddings (project_id);

-- Lexical retriever C: generated tsvector on the issue itself
ALTER TABLE issues
    ADD COLUMN search_tsv tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title,'')),       'A') ||
        setweight(to_tsvector('english', coalesce(description,'')),  'B')
    ) STORED;

CREATE INDEX issues_search_tsv ON issues USING GIN (search_tsv);
```

**Why HNSW, not ivfflat `lists=100`:** ivfflat needs many rows per list to work; at a
single project's count the lists are nearly empty and recall craters for no latency win.
HNSW (pgvector ≥0.5) gives good recall out of the box. *Below ~10k rows an exact scan is
also fine* — HNSW is the forward-looking choice, not a present necessity. The `setweight`
A/B on the tsvector mirrors the same title-over-description priority in the lexical path.

`content_hash` (sha256 of the normalized group text + model name) lets the indexer skip
re-embedding a group whose text didn't actually change — editing a label shouldn't re-embed
the comment thread.

---

## 3. When to embed

| Trigger | Action |
|---------|--------|
| Issue created | Enqueue `embed_issue(issue_id)` immediately |
| `title`/`description`/`labels` changed | Enqueue with 10 s `countdown` (debounce); only `core` group re-embeds if its hash changed |
| Env / repro / curl changed | Enqueue; only `repro` re-embeds |
| Comment added/edited (`IssueTimeline`, `event_type=comment`) | Enqueue; only `talk` re-embeds |
| Admin reindex | Enqueue all issues missing rows or with stale `model` |
| Embedding model changed in settings | Full reindex (every vector is stale — different model/space) |

`content_hash` per group means each trigger only pays for the group that actually changed.
The task is idempotent, so debounced duplicates are harmless.

---

## 4. Indexing task (`tasks/search.py`)

```python
@celery_app.task(name="app.tasks.search.embed_issue",
                 bind=True, max_retries=3, default_retry_delay=10, queue="default")
def embed_issue(self, issue_id: int) -> None:
    try:
        asyncio.run(_embed_issue_async(issue_id))
    except EmbeddingConfigMissing:
        return                       # no LLM config yet → skip silently, retry on next edit
    except Exception as exc:
        raise self.retry(exc=exc)    # exponential backoff

async def _embed_issue_async(issue_id: int) -> None:
    cfg = await load_llm_config()                 # base_url, api_key, model, dimension
    issue = await load_issue_with_comments(issue_id)
    groups = build_field_groups(issue)            # {'core': str, 'repro': str, 'talk': str}
    for name, text in groups.items():
        if not text.strip():
            await delete_group(issue_id, name)    # group emptied → drop its row
            continue
        h = sha256(f"{cfg.model}:{normalize(text)}")
        if await hash_matches(issue_id, name, h):
            continue                              # unchanged → skip the API call
        vec = await embed(cfg, text)              # POST {base_url}/embeddings
        await upsert_embedding(issue_id, issue.project_id, name, vec, h, cfg.model)
    await invalidate_search_cache(issue.project_id)
```

`normalize()` strips markdown, collapses whitespace, lowercases for hashing. Long groups
truncate to the model's token limit (`talk` truncates first since it's lowest priority).

---

## 5. Query — hybrid retrieval + RRF (+ optional rerank)

### Why RRF instead of a linear `0.7·vec + 0.3·text` blend

Vector cosine scores and `ts_rank` lexical scores live on **different, non-comparable
scales** — and (point 2 above) the vector scores are compressed into a narrow band.
Linearly mixing them means whichever scale happens to be wider dominates arbitrarily.
**Reciprocal Rank Fusion** ignores raw scores and fuses *positions*:

```
RRF(doc) = Σ_retriever  weight_r / (k + rank_r(doc))        k = 60 (standard)
```

Each retriever contributes by *where* it ranked a doc, not by an incomparable score. This
is robust to score compression and needs no normalization.

### Flow

```python
async def search(q: str, project_id: int, limit: int = 20):
    qvec = await embed_query(q)                          # same model as indexing

    # Three retrievers, each returns a ranked list of issue_ids (top ~50)
    A = await dense_search(qvec, project_id, group='core')   # vector vs core
    B = await dense_search(qvec, project_id, group='talk')   # vector vs comments
    C = await lexical_search(q, project_id)                  # tsvector / ts_rank

    fused = rrf_fuse(
        rankings=[A, B, C],
        weights=[0.55, 0.20, 0.40],   # lexical weighted high: exact tokens matter here
        k=60,
    )                                                    # → issue_ids by fused rank

    top = fused[:limit]
    if llm_rerank_enabled:                               # optional precision pass
        top = await llm_rerank(q, top[:20])              # reuse configured LLM

    return hydrate(top)                                  # join issue metadata + snippet
```

`repro` can be a 4th dense retriever or folded into `core`; start with the three above and
add it if repro-specific queries underperform in evaluation (§8).

### Dense retriever (per group)

```sql
SELECT issue_id
FROM issue_embeddings
WHERE project_id = $1 AND field_group = $2
ORDER BY embedding <=> $qvec        -- cosine distance; HNSW-accelerated
LIMIT 50;
```

### Lexical retriever

```sql
SELECT id AS issue_id
FROM issues
WHERE project_id = $1
  AND search_tsv @@ websearch_to_tsquery('english', $2)
ORDER BY ts_rank(search_tsv, websearch_to_tsquery('english', $2)) DESC
LIMIT 50;
```

`websearch_to_tsquery` accepts natural typed queries (quoted phrases, `-` exclusion) for
free.

### No fixed threshold

Return the top-K, ranked. If a cutoff is ever needed (e.g. "show nothing for nonsense
queries"), derive it from the RRF score distribution on real data (§8) — **never** the
hardcoded `0.4` from v1, which the score-compression problem makes meaningless.

### Optional LLM reranker

Top ~20 candidates → ask the already-configured LLM to score relevance to the query
(0–1) and reorder. Highest precision, no new infra, honors "no new tools." Behind a
settings flag (`embedding.rerank_enabled`) — off by default; costs one LLM call per search.

---

## 6. The dimension problem (must resolve, not imply)

`vector(N)` fixes `N` at migration time, but `embedding_model` is configurable and models
have different dims (`text-embedding-3-small`=1536, `-large`=3072). v1 left this implied;
it would break on a model switch.

**Resolution — pin + managed reindex:**

- Store `embedding_dimension` as a setting (in `LLMConfig`, see §7). The migration creates
  `vector(1536)` as the default.
- Changing the **model/dimension** is an explicit, admin-gated operation that:
  1. `ALTER TABLE issue_embeddings ALTER COLUMN embedding TYPE vector(<new_dim>)` after
     truncating the table (vectors of the old dim are meaningless in the new space anyway),
  2. recreates the HNSW index,
  3. kicks a **full reindex** of all issues.
- For OpenAI v3 models, the API's `dimensions` truncation param *can* pin output to a fixed
  N — but arbitrary OpenAI-compatible endpoints may ignore it, so we don't rely on it; we
  treat dim as authoritative from settings and validate the returned vector length, failing
  loudly on mismatch.

The `model` column on each embedding row makes "which rows are stale after a model change"
a trivial query.

---

## 7. Settings integration

`LLMConfig` already carries `base_url`, `api_key`, `embedding_model`. Add:

```python
class LLMConfig(BaseModel):
    base_url: str          = Field(default="", alias="baseUrl")
    api_key: str           = Field(default="", alias="apiKey")
    embedding_model: str   = Field(default="", alias="embeddingModel")
    embedding_dimension: int = Field(default=1536, alias="embeddingDimension")
    rerank_enabled: bool   = Field(default=False, alias="rerankEnabled")
```

SettingsPage already has an LLM section — add dimension + a "LLM reranker" toggle, and a
"Reindex now" button wired to the admin endpoint.

---

## 8. Measure before you tune (Phase 0 — do this first)

We're guessing about cluster tightness; **measure it on the seed data** before picking any
weight or threshold:

1. Embed all seeded issues (run the indexer once).
2. Script: compute pairwise cosine distribution across `core` vectors.
   - If similarities are nearly all **> 0.85**, dense-only is weak → hybrid is mandatory
     (it already is here) and RRF weights should lean lexical.
   - If spread is healthy, dense carries more weight.
3. Hand-label ~15 query→expected-issue pairs from the seed set. Use them to tune RRF
   weights and decide whether the LLM reranker earns its cost (precision@5 lift vs latency).

~20-line script, gates every magic number in this plan. Output saved to
`backend/scripts/eval_search.py`.

---

## 9. API endpoint

```
GET /api/v1/search?q=<query>&project_id=<id>&limit=20
```

```json
{
  "query": "safari login redirect loop",
  "results": [
    { "issue_id": 42, "issue_number": 137, "title": "Safari auth redirect loop",
      "severity": "critical", "status": "open", "score": 0.91,
      "matched_via": ["core", "lexical"], "snippet": "...redirect loop on Safari 17..." }
  ],
  "total": 5
}
```

`matched_via` (which retrievers surfaced the hit) is cheap to expose and great for
debugging relevance. Cache in Redis: `search:{project_id}:{sha256(q)}`, TTL 60 s,
pattern-invalidated on any issue change in that project.

---

## 10. Files to create / modify

| File | Change |
|------|--------|
| `alembic/versions/xxx_add_issue_embeddings.py` | New — pgvector ext, `issue_embeddings` table, HNSW index, `issues.search_tsv` + GIN |
| `backend/app/db/models/issue_embedding.py` | New — `IssueEmbedding` ORM model |
| `backend/app/tasks/search.py` | New — `embed_issue` task + field-group builder |
| `backend/app/services/search_service.py` | New — doc builder, query embed, 3 retrievers, RRF, optional rerank |
| `backend/app/api/v1/search.py` | New — `GET /search` |
| `backend/app/api/v1/admin.py` (or settings) | New — `POST /admin/search/reindex` |
| `backend/app/main.py` | Register search router |
| `backend/app/schemas/settings.py` | `LLMConfig`: add `embedding_dimension`, `rerank_enabled` |
| `backend/app/api/v1/settings.py` | Return/accept new fields; reindex trigger on model change |
| `backend/app/services/issue_service.py` | Enqueue `embed_issue` on create/update |
| `backend/app/services/timeline_service.py` | Enqueue `embed_issue` on comment add/edit |
| `backend/scripts/eval_search.py` | New — Phase-0 distribution + precision eval |
| `frontend/src/lib/api.js` | `searchApi.query(q, projectId)` |
| `frontend/src/components/layout/*` (search bar) | Wire input → API, show results + `matched_via` |
| `frontend/src/pages/SettingsPage.jsx` | Dimension field, reranker toggle, reindex button |

---

## 11. Dependencies

```toml
# pyproject.toml
pgvector = ">=0.3"     # SQLAlchemy/asyncpg vector type + ops
# httpx already present — used for embedding + rerank API calls
```

```yaml
# docker-compose.yml — pgvector-enabled Postgres (drop-in)
services:
  db:
    image: pgvector/pgvector:pg16
```

---

## 12. Phased rollout

| Phase | Scope | Outcome |
|-------|-------|---------|
| **0** | `eval_search.py` on seed data | Know cluster tightness; calibrate weights — no guessing |
| **1** | Migration + model + indexing task | Field-grouped embeddings generated for new/edited issues |
| **2** | `search_service` (dense×2 + lexical + RRF) + `/search` + search bar | Hybrid semantic search live, top-K ranked, no fragile threshold |
| **3** | Admin reindex + backfill + model-change handling | All existing issues indexed; safe model/dimension switching |
| **4** | LLM reranker (flagged) + tune RRF weights from Phase-0 labels | Precision pass where it pays |

---

## TL;DR of the redesign

- **Field-weighted multi-vector** (`core` 0.55 / `repro` 0.25 / `talk` 0.20) replaces the
  uniform composite → title stops being drowned by comments.
- **Hybrid (vector + Postgres FTS) fused with RRF** replaces dense-only + linear blend →
  exact tokens (error codes, hashes, curl) are first-class, and RRF survives score
  compression.
- **Top-K ranking** replaces the hardcoded `0.4` threshold → robust to tight clustering.
- **HNSW** replaces `ivfflat lists=100` → real recall at this scale.
- **Pinned dimension + managed reindex** resolves the configurable-model vs fixed-`vector(N)`
  conflict.
- **Optional LLM reranker** on top-20, reusing the configured LLM → precision with no new infra.
- **Measure first** (Phase 0) → every weight/threshold comes from data, not vibes.
- Cosine stays — the metric was never the problem; *what we embed and how we fuse* was.
