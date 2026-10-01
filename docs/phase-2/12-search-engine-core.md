# 12 — Search Engine Core (local)

> **Depends on:** 11 (uses 04 visibility, 03 types) · **Engine doc:** [prd-search-engine.md](prd-search-engine.md) FR-S01–S07, FR-S16 (rule part), FR-S17, FR-S19; BR-S04–S06, BR-S10, BR-S13–S17, BR-S20; AC-S01, AC-S05, AC-S06, AC-S15, AC-S16, AC-S18, AC-S21, AC-S22; §8 Q1, Q2; Appendix A.1–A.6, A.8 (Jev-off path), A.9–A.13
> Jev is added in 13. Suggestions are added in 14. This slice ships a complete, local-only search.

## Problem Statement

Phase 1 search cannot match the same problem written in Persian, English, and mixed text, fails on one-word queries and transliterated technical words, truncates long descriptions at 128 tokens, and uses an English-only keyword index. Several of its parts never worked: the LLM reranker cannot run with the local provider, changing the local model never re-embeds, the `repro` field group is stored but never searched, and a Phase 1 migration left the vector column and its constraints inconsistent with the code. Phase 2 needs one engine that search and, later, duplicate detection can rely on.

## Solution

Replace the Phase 1 search with the engine's stage 1. Items are normalized and indexed into engine-owned tables as `title`, `body`, and `talk` vectors, embedded by `BAAI/bge-m3` running in a bundled text-embeddings-inference service, plus a folded keyword text in a trigram index. Search fuses four channels (body, title, talk, gated keyword) with weighted reciprocal rank fusion, applies visibility, and drops results below a similarity floor. Comments reach the index only if a rule keeps them. The command palette and search page use the same endpoint. A harness evaluates the engine against the Phase 1 baseline on the dataset from `search-eval-dataset-spec.md`.

## User Stories

1. As a tech user, I want searching `مشکل در reaction در group chat` to find a bug titled `ری‌اکشن روی پیام‌های گروه ذخیره نمی‌شود`, so that language and spelling don't hide existing work. (FR-S07, AC-S01)
2. As a user, I want a one-word query such as `ری‌اکشن` to return the items about that feature, so that quick lookups work.
3. As a user, I want typos and missing half-spaces tolerated (`ثبتنام زبان اموز`), so that I don't have to type carefully.
4. As a user, I want search to cover the current project by default, with a switch for all projects I can see, so that results start focused. (FR-S01)
5. As a user, I want to filter results by type and status. (FR-S01)
6. As a user, I want each result to show key, type, title, status, project, and a snippet, so that I can pick the right one without opening it. (FR-S02)
7. As a user, I want a snippet taken from the comment that matched when the match came from a comment, so that I see why it was returned. (FR-S02)
8. As a Support user, I want only support items I can see, and never a match or snippet from an internal note. (BR-S06, AC-S05)
9. As a user, I want cancelled items to be findable and marked cancelled. (FR-S06, AC-S06)
10. As a user, I want junk results left out when nothing really matches, so that an empty page means "not reported yet". (FR-S04)
11. As a user, I want the command palette to show results as I type, and Enter to open the full search page with the same query. (FR-S05)
12. As an engineer, I want an endpoint path or error code in a description (`/api/v1/chat/reactions`, `413`) to be findable, so that technical lookups work. (A.3 keyword text)
13. As an engineer, I want comments such as "I agree, do it when you have time" kept out of the index, so that they don't pull unrelated items into results. (FR-S16, AC-S16)
14. As an engineer, I want an edited title or description reflected in search within about a minute, without re-embedding the item's comments. (BR-S17, AC-S15)
15. As an admin, I want Settings → Search to show the embedding endpoint, the active model, and index progress, with a **Reindex all** button. (FR-S17)
16. As an admin, I want changing the embedding endpoint or model to start a full reindex and never mix vectors of two models. (FR-S19, BR-S16, AC-S18)
17. As an admin, I want only Admin to reach Search settings. (AC-S21)
18. As an operator, I want the embedding model to run locally in the compose stack without downloading at startup, so that search works without internet access to Hugging Face.
19. As an operator, I want a fresh install and an upgraded Phase 1 install to end with the same schema, with the old search objects gone. (AC-S22)
20. As the CTO, I want an evaluation report comparing the engine to today's search on real issues, so that I know it is better before release. (§8 Q1, Q2)

## Implementation Decisions

### Infrastructure

- `docker-compose.yml`: add service `embeddings` with image `ghcr.io/huggingface/text-embeddings-inference:cpu-<pinned>` and args `--model-id BAAI/bge-m3 --max-batch-tokens 16384`. Mount volume `embeddings_models:/data`. Set `HF_HUB_OFFLINE=1` in prod, with a healthcheck on `/health`. Add a `make embeddings-fetch` target that fills the volume once, online. `api` and `worker` depend on it being healthy. Dev/E2E overlays can point the endpoint to the fake (below).
- Celery: a new queue `search`, consumed by the existing worker (`-Q default,celery,attachments,search`).
- Remove `fastembed` from `pyproject.toml`. Keep `pgvector`.

### Schema (one revision, plus a cleanup revision)

- `CREATE EXTENSION IF NOT EXISTS pg_trgm`.
- Create `search_items`, `search_vectors`, and `comment_labels` exactly as in Appendix A.4. `duplicate_hints` and `duplicate_dismissals` come in 14.
- Cleanup revision: `DROP TABLE IF EXISTS issue_embeddings CASCADE`; drop `issues.search_tsv` and `ix_issues_search_tsv` if present; delete `system_settings` rows with category `llm` after copying an `api` provider's `baseUrl` into the new `search.embedding_endpoint` (for a `local` provider, use the default). Make every step tolerant of what `7f60b302c290` did or did not apply.
- Downgrade recreates nothing from Phase 1 search. It drops the engine tables, and the revision's docstring says so. This is the one sanctioned non-reversible data effect: the index is derived data.

### Modules

- `app/search/normalize.py`: pure functions (A.2). Port from `poc/semantic-search/rwsearch/normalize.py` (`normalize`, `fold`), without the bridge.
- `app/search/documents.py`: pure `build_documents(item, comments, labels) -> {title, body_chunks[], talk[], keyword_text}` (A.3). Chunk with the embedding service's tokenizer count, approximated as 1 token ≈ 4 characters for Persian and English. cURL: keep URL paths only.
- `app/search/embeddings.py`: an OpenAI-compatible client (`httpx`), batching up to 32 texts, 10 s timeout. It is the only code that knows the endpoint.
- `app/search/comment_rules.py`: pure `rule_label(text) -> rule_kept | rule_dropped` (A.6).
- `app/search/retrieval.py`: `search(actor, query, scope, filters, mode) -> Ranked`. It runs the four channels (A.8), fusion, visibility through `visible_issues(actor)`, and the floor. The Jev hook is a no-op until 13.
- `app/search/constants.py`: `FUSION_WEIGHTS`, `RRF_K`, `T_FLOOR`, `T_TRGM`, `CHANNEL_LIMIT`, each commented with the evaluation run that set it. Start with the A.8 initial values.
- `app/tasks/search_index.py`: `index_item`, `classify_comment` (rule only in this slice), `reindex_all` (A.5). Debounce with `apply_async(countdown=10)` and a Redis `SETNX` guard per item.
- Triggers: `IssueService` and `TimelineService` enqueue after commit on the A.5 events. Use a single helper, `search_index.enqueue(issue_id)`, so call sites stay one line.

### Talk channel and visibility

- `talk` rows carry `is_internal`. For Support actors, the talk channel query adds `NOT is_internal`, and snippet selection uses the same filter. An item is returned only if at least one allowed channel matched (AC-S05).

### API

- `GET /search` per Appendix A.9, replacing the Phase 1 handler and its Redis result cache. Keep the query-vector cache. `mode=palette` limits to 8 results and skips the snippet from comments. The response already includes `less_relevant: []` and `jev_used: false`, so 13 changes only the values.
- `GET /features` → `{jev_enabled: false}` for now.
- `GET/PUT /settings/search` and `POST /settings/search/reindex` (Admin). The index status comes from counts plus a Redis progress key written by `reindex_all`.
- On worker start, if `search_items` is empty and items exist, enqueue `reindex_all`.

### Frontend

- `SearchPage`: scope switch (project / all), type and status filters, result rows per FR-S02 with a cancelled marker, and empty state text "No matches". Keep the layout per `docs/design.md`. The collapsed "Less relevant" section is built now but renders only when the response has items (13).
- `CommandPalette`: call `/search?mode=palette`. Enter navigates to `/search?q=…`.
- Settings: replace the LLM section with **Search**: endpoint field, model (read-only, reported by the service), index progress, **Reindex all** with confirmation.

### Evaluation harness

- `backend/scripts/search_eval/` per Appendix A.13, `stage1` only in this slice. Port `poc/semantic-search/bench_embed.py`. It loads `corpus/issues.json`, `corpus/comments.json`, and `queries.json` from a dataset directory, builds documents with the **engine's own** `documents.py`, embeds through the configured endpoint, and scores with the engine's own `retrieval` functions against an in-memory or temporary Postgres index. Baseline: MiniLM with the Phase 1 document construction (title twice + description), run through the same code path with a different model and document builder.
- The PR for this slice includes the report in `docs/specs/phase-2/eval/stage1-<date>.md`, and meets Q1 and Q2 or explains the gap.

## Testing Decisions

- The fake embedding endpoint (Appendix A.12) replaces the slice-01 embedding no-op: an in-process ASGI app registered as the embedding endpoint in the test settings. Deterministic char-trigram hashing into 1024 dimensions. Tests assert behavior (inclusion, exclusion, ordering for obvious cases), never model quality.
- Named ACs:
  - `test_ac_s01_cross_script_query_finds_item` (uses the fake's shared trigrams: pick fixture titles so the expected item is findable by construction)
  - `test_ac_s05_support_never_matches_through_internal_notes`
  - `test_ac_s06_cancelled_item_searchable_and_marked`
  - `test_ac_s15_title_edit_reembeds_title_body_not_talk` (the fake records embedded texts)
  - `test_ac_s16_ack_comment_not_indexed`
  - `test_ac_s18_model_change_triggers_reindex_and_isolates_models`
  - `test_ac_s21_search_settings_admin_only`
  - `test_ac_s22_migration_from_phase1_and_fresh` (a migration test: stamp at the pre-12 head with Phase 1 search objects present, upgrade, and inspect the schema; also upgrade an empty database)
- Index jobs are called directly (the scheduled-job seam from 01) with the fake endpoint. Assert through `GET /search`.
- A leak test extending 04's suite: Support search with a matching internal note, a matching non-support item, and a matching task all present returns none of them.
- Pure-function tests for `normalize`, `fold`, `build_documents` (chunking, cURL path extraction, no labels in body), and `rule_label`. These are the only unit tests; they are pure modules like Workflow and Policy.
- **E2E:** extend the smoke test. A tech user types in the command palette and sees the seeded item, then presses Enter and lands on the search page with results. Use the fake endpoint in `docker-compose.e2e.yml`.

## Out of Scope

- Jev: reranking, the relevance split, comment classification by Jev, and settings (13).
- Similar-item panels and triage hints (14).
- The PoC's Persian↔English bridge (not needed with bge-m3, per A.2).
- Search analytics or query logging (BR-S20).

## Further Notes

- The fake embedding endpoint makes cross-script matching a property of the fixture text, not of the model. Quality claims come only from the evaluation report.
- If production CPU cannot meet Q2 with bge-m3, the fallback decided in advance is `intfloat/multilingual-e5-base` (768 dims; `query: ` / `passage: ` prefixes). That requires a vector-dimension migration and is a separate decision recorded in the evaluation report.
