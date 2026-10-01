# Releasewatch Phase 2 — Search & Ranking Engine

> **Product:** Releasewatch
> **Phase:** 2 — last part (after the work-management slices)
> **Status:** Draft for review
> **Owner:** CTO
> **Parent document:** [Phase 2 PRD v3](prd-v2.md). Rule numbers without an `S` (FR-12, BR-49…) refer to it. Cycles and returns: [cycle-model.md](cycle-model.md).
> **v3:** merge targets may be bugs or tasks, and a merge into a Done item sends it back to To do with a new cycle instead of making it a regression.
> **Implementation slices:** [12](12-search-engine-core.md), [13](13-jev-integration.md), [14](14-similar-item-suggestions.md)

---

## 1. Overview

Releasewatch needs to find items by meaning, not just by words. Reports are written in Persian, English, and a mix of the two, with English technical words written in Persian script (`ری‌اکشن` for *reaction*), typos, and missing half-spaces. The same problem arrives from Support, QA, and developers in different words. Today's search cannot match `عدم ثبت ری‌اکشن در چت با تایپ گروه` with `مشکل در reaction در group chat`.

This document defines one **search and ranking engine** that serves every place in Releasewatch that needs "find the items that mean this":

| Consumer | What it answers |
|---|---|
| Search page | "Which items is the user looking for?" |
| Command palette | Same, while typing |
| Tech create form | "Does this already exist?" (informational) |
| Support form | "Is this already reported? Then record a recurrence instead" |
| Triage queue | "Is this new bug a duplicate, or a problem with work that is already done?" |
| Comment indexing | "Does this comment say something about the problem?" |

The engine runs in two stages:
1. **Stage 1 (local, always on):** a local embedding model plus a trigram keyword index. It is fast, has no external dependency, and always produces results.
2. **Stage 2 ([Jev](https://docs.typesafe.ai), optional):** an external decision model that judges the stage-1 candidates. It reranks with an absolute relevance cut-off and decides "same problem / related / unrelated". **Jev is behind one feature flag.** When it is off or unavailable, Releasewatch works entirely locally.

---

## 2. Goals & Non-Goals

### Goals

1. Search finds the right item across Persian, English, mixed, and transliterated text, with typos.
2. Duplicate reports are caught where they enter: in the support form, and in triage for everything else.
3. A problem that returns after its fix is recognized in triage and merged into its original (bug or task), which goes back for a fix with a new cycle (PRD BR-49).
4. The system keeps working, with reduced quality, when Jev is off or unreachable.
5. Quality is measured on real issues before release, against today's search.

### Non-Goals

- Automatic merging, linking, or status changes. Every suggestion is confirmed by a person.
- Cross-project duplicate suggestions. A duplicate across two projects is two items.
- Logging search queries.
- A local reranker model. Reconsider only if evaluation shows stage 1 alone is not good enough.
- Per-feature or per-project Jev switches.
- Using Jev for text generation. Jev only returns decisions.

---

## 3. Principles

**S1 — Local first.** Search must always answer from local components. Jev may reorder and cut the local candidates. It never adds an item that stage 1 did not find.

**S2 — One switch, one fallback.** Jev off, unreachable, erroring, or timing out all behave exactly the same: the Jev-off behavior. Users never see an error because of Jev.

**S3 — No suggestion without a judgment.** Similar-item suggestions only exist when Jev can say "this is the same problem". Similarity alone produces too many plausible-but-wrong suggestions, and people learn to ignore them.

**S4 — Duplicates are judged on the problem statement only.** Title, description, and reproduction steps decide "same problem". Comments often discuss other problems, process, or agreement, so they help search but never duplicate detection.

**S5 — Derived data lives apart.** Everything the engine computes is stored in its own tables and can be rebuilt from the items and timelines. The only exception is triage dismissals, which record a human decision.

---

## 4. Behavior by consumer

| Consumer | Jev enabled | Jev disabled or unavailable |
|---|---|---|
| Search page | Local candidates reranked by Jev. Results under the relevance threshold go into a collapsed "Less relevant" section | Local ranking with a minimum-similarity floor |
| Command palette | Local only | Local only |
| Tech create form | "Possibly the same" panel (informational) | No panel |
| Support form | Similar open reports with **Record recurrence** | No panel |
| Triage queue | "Possible duplicate" hints on New bugs | No hints (stored hints are hidden) |
| Comment indexing | Jev classifies each comment | Rule-based filter |

---

## 5. Functional Requirements

### Search

**FR-S01** The search page searches the current project by default, with a switch for all projects the user can see. Filters: type, status.

**FR-S02** Each result shows key, type, title, status, project, and a snippet. The snippet comes from the description, or from the matching comment when the match came from a comment the user is allowed to see.

**FR-S03** With Jev enabled, results Jev scores at or above the relevance threshold are listed first in Jev's order. The rest appear in a collapsed **Less relevant results (n)** section. If no result reaches the threshold, the page says "No close matches" above the collapsed section.

**FR-S04** With Jev disabled or unavailable, results are listed in local ranking order. Results below a minimum similarity are not shown. There is no collapsed section.

**FR-S05** The command palette shows local results as the user types, in the current project, and never calls Jev. Pressing Enter opens the search page with the same query.

**FR-S06** Cancelled items can be found by search and are marked as cancelled.

**FR-S07** Search matches across languages and spellings: Persian ↔ English, transliterated technical words, missing or extra half-spaces, Persian/Arabic letter and digit variants, and small typos.

### Tech create form

**FR-S08** With Jev enabled, the create form (bug or task) shows a **Possibly the same** panel once the title is filled. It updates after typing pauses (about 800 ms) as the title or description changes. It lists items of any type in the selected project, excluding Cancelled ones, that Jev judges the **same problem** or **related**, labeled as such, with key, type, status, and title. Items open in a new tab. The panel has no merge action; triage handles merging.

### Support form

**FR-S09** With Jev enabled, the support form shows a **Similar reports** panel once the title and at least one template text field are filled. It updates after typing pauses (about 800 ms). It lists only **open support reports in the chosen project** (not Done, not Cancelled) that Jev judges the **same problem**.

**FR-S10** Each suggestion has **This is the same problem — record recurrence**. It records a recurrence on that item (PRD FR-13/FR-14) with the form's composed content (title, template block, free description) as the required comment, and adds the form's attachments to the item. No new report is created. The Support user is subscribed to the item.

**FR-S11** After recording, the form is cleared and shows a confirmation with a link to the item.

### Triage hints

**FR-S12** With Jev enabled, every bug that enters **New** is checked in the background against the project's items (bugs of any source, and tasks) in any status except Cancelled. Up to three items that Jev judges the **same problem** at or above the confidence threshold are stored as **possible duplicates**.

**FR-S13** Possible duplicates appear in the triage queue row as a compact marker and on the item page, for tech users only. Each shows the candidate's key, title, and status, and what a merge will do: "stays In progress" (or its current status), "stays Cancelled", "Done → back to To do (release QA)", or "Done → back to To do (production)" (PRD BR-49).

**FR-S14** Each possible duplicate offers **Merge into this**, which opens the Duplicate triage outcome with that item preselected, and **Not a duplicate**, which dismisses that pair.

**FR-S15** Hints are shown only while the item is New.

### Comment indexing

**FR-S16** Each comment is classified to decide whether it is used for search: *about this problem*, *about another problem*, *process*, or *acknowledgement*. Jev classifies when enabled. Otherwise a rule keeps comments that are long enough and are not a bare acknowledgement.

### Settings (Admin)

**FR-S17** Settings → **Search** shows the embedding endpoint (default: the bundled local service), the active embedding model, index progress (indexed / total, last run), and a **Reindex all** button.

**FR-S18** Settings → **Search → Jev** has: an Enabled switch, an API key (write-only, shown masked once saved), the Jev model (default `jev-1.13.0`), and **Test connection**. Jev can be enabled only after a successful test with the saved key.

**FR-S19** Changing the embedding endpoint or model starts a full reindex. Progress is shown in Settings.

---

## 6. Business Rules

**BR-S01** There is exactly one Jev switch, global to the installation.

**BR-S02** When Jev is disabled, unreachable, returns an error, or does not answer within the timeout, the request is served with the Jev-disabled behavior of §4. The user sees no error.

**BR-S03** Similar-item panels and triage hints are never shown while Jev is disabled. Hints computed earlier are kept but hidden.

**BR-S04** Jev only reorders, cuts, or labels stage-1 candidates. It never introduces an item.

**BR-S05** The command palette never calls Jev.

**BR-S06** Every result and suggestion obeys item visibility (PRD BR-30). For Support users, only public comments can match or supply a snippet. An item that matches a Support user's query only through an internal note is not returned.

**BR-S07** Support-form candidates: same project, source Support, status not Done and not Cancelled.

**BR-S08** Tech-form candidates: same project, any type, status not Cancelled.

**BR-S09** Triage-hint candidates: same project, items of any type (bugs of any source, and tasks), status not Cancelled. Hints are computed only for bugs in New.

**BR-S10** Cancelled items are never suggested. They remain searchable.

**BR-S11** Suggestions never act on their own. Merging, recording a recurrence, and dismissing are always explicit user actions.

**BR-S12** Dismissing a possible duplicate applies to that pair of items, permanently, and survives reindexing.

**BR-S13** "Same problem" judgments use only title, description, and reproduction steps. A comment is used for search only when classified *about this problem* or *about another problem* (Jev), or kept by the rule (Jev off).

**BR-S14** A comment's classification records its source (`jev` or `rule`). Enabling Jev reclassifies, once, the comments whose source is `rule`. Disabling Jev keeps existing Jev classifications; only new comments use the rule.

**BR-S15** Engine data (vectors, keyword text, comment classifications, possible duplicates, dismissals, index state) is stored in engine tables, never in item or timeline tables.

**BR-S16** Vectors from different embedding models are never compared. Changing the model requires a full reindex.

**BR-S17** An item is reindexed when its title, description, reproduction steps, type, status, source, or project changes, and when one of its comments is added, edited, or deleted. Content that has not changed is not re-embedded.

**BR-S18** Only Admin manages search settings. The Jev API key is encrypted at rest and never returned by the API.

**BR-S19** Relevance and confidence thresholds are fixed in code, set from the evaluation (§8). They are not user settings.

**BR-S20** Search queries are not logged.

**BR-S21** Merge effects follow PRD BR-49 and BR-50. Recording a recurrence from the support panel and merging from a triage hint go through the same operations as their manual equivalents.

---

## 7. Acceptance Criteria

### Search

**AC-S01** Given Jev is disabled, when a user searches `مشکل در reaction در group chat`, then an item titled `ری‌اکشن روی پیام‌های گروه ذخیره نمی‌شود` is in the top five, and no "Less relevant" section is shown.

**AC-S02** Given Jev is enabled but does not answer within the timeout, when a user searches, then results are returned in local order with no error.

**AC-S03** Given Jev is enabled, when a candidate is scored below the relevance threshold, then it appears only inside the collapsed "Less relevant" section.

**AC-S04** Given Jev is enabled, when a user types in the command palette, then Jev receives no request.

**AC-S05** Given a Support user, when their query matches a non-support item, or matches a support item only through an internal note, then that item is not returned.

**AC-S06** Given a cancelled item, when a user searches its title, then it is returned and marked cancelled.

### Suggestions

**AC-S07** Given Jev is disabled, then the tech create form and the support form show no similar-item panel, and the triage queue shows no possible-duplicate marker.

**AC-S08** Given the support form in project P, then its panel never lists Done, Cancelled, non-support, or other-project items.

**AC-S09** Given a Support user records a recurrence from the panel, then no new item exists, the chosen item's recurrence count increased by one, its timeline has a public comment with the form's composed content, the form's attachments are on the item, and the Support user is subscribed to it.

**AC-S10** Given Jev is enabled and a same-problem bug exists in the project, when a new bug is filed, then the triage queue row shows a possible-duplicate marker naming that bug.

**AC-S11** Given a possible duplicate whose candidate is Done, then the hint says the candidate will go back to To do (production or release QA), and "Merge into this" produces the result of PRD AC-50 or AC-51.

**AC-S12** Given a dismissed pair, then it is never suggested again for that item, including after a full reindex.

**AC-S13** Given an item with a possible duplicate, when the item leaves New, then the marker is no longer shown.

**AC-S14** Given a Cancelled bug that matches a new report, then it is never suggested.

### Indexing

**AC-S15** Given an item's title is edited, then its title and body vectors are recomputed, and its comment vectors are not.

**AC-S16** Given Jev is disabled, when a comment `موافقم، هر وقت فرصت داشتید انجامش بدید` is added, then it is classified by the rule as not used for search.

**AC-S17** Given comments classified while Jev was disabled, when Jev is enabled, then those comments are reclassified by Jev once, and comments already classified by Jev are not.

**AC-S18** Given Admin changes the embedding model, then a full reindex starts, and search compares only vectors of the new model.

### Settings and migration

**AC-S19** Given no successful Test connection with the saved key, then the Jev switch cannot be turned on.

**AC-S20** Given any API response, then the Jev API key is never included.

**AC-S21** Given a non-Admin user, then Search settings are not accessible.

**AC-S22** Given an empty database, when migrations run to head, then the engine tables exist and the Phase 1 search objects (`issue_embeddings`, `issues.search_tsv`) do not. Given a Phase 1 database, when migrations run to head, then those objects are removed and a reindex can populate the engine tables.

---

## 8. Quality Acceptance

Measured with the evaluation dataset built per [search-eval-dataset-spec.md](search-eval-dataset-spec.md): synthetic queries and drafts written about **real issues** from a read-only snapshot, labeled without using the engine itself. The **baseline** is today's Phase 1 search (MiniLM embeddings, run by the same harness).

| # | Measure | Gate |
|---|---|---|
| Q1 | Search Recall@5, stage 1 only (Jev off) | ≥ baseline + 10 points |
| Q2 | Stage-1 latency p95 (query embedding + retrieval), production hardware, full corpus | < 300 ms |
| Q3 | "Same problem" precision on duplicate + hard-negative drafts (Jev on) | ≥ 0.80 |
| Q4 | Results shown above the relevance threshold on no-match queries (Jev on) | ≤ 1 on average |
| Q5 | Comment classification accuracy per label | Reported, not gated |

Thresholds used by BR-S19 are chosen on this dataset so that Q3 and Q4 hold, and then fixed in code.

---

## 9. Deliberate Limitations

| Limitation | Reason |
|---|---|
| No similar-item suggestions while Jev is off | S3: suggestions without a same-problem judgment get ignored |
| Support never sees duplicates of non-support items | Visibility (BR-30). Those duplicates are caught in triage |
| Duplicates across projects are not suggested | A cross-project duplicate is two pieces of work |
| No search analytics | Queries are not logged (BR-S20) |
| Search can be incomplete during a full reindex | Simplicity; progress is shown in Settings |
| Titles, descriptions, and comments are sent to the Jev API when Jev is enabled | Accepted by the owner; Jev is optional |

---

## Appendix A — Technical design

This appendix is for the implementing sessions. The slices ([12](12-search-engine-core.md), [13](13-jev-integration.md), [14](14-similar-item-suggestions.md)) turn it into work. The PoC in `poc/semantic-search/` is the reference implementation of the algorithms and the benchmark.

### A.1 Components

```
                ┌──────────── api (FastAPI) ────────────┐
query / draft ─▶│ normalize → embed(query) → retrieve   │──▶ results
                │            │              │  ▲        │
                │            ▼              ▼  │        │
                │   embeddings service   Postgres       │
                │   (TEI, bge-m3, CPU)   pgvector +     │
                │                        pg_trgm        │
                │ optional: Jev (HTTPS, 1.5 s timeout)  │
                └───────────────────────────────────────┘
worker (Celery, queue "search"): index_item · classify_comment · compute_duplicate_hints · reindex_all · backfill_comment_classification
```

- **Embeddings service:** a new `embeddings` service in `docker-compose.yml`, running Hugging Face `text-embeddings-inference` (CPU image, pinned tag) with `BAAI/bge-m3`. The model files live on a volume, prefetched at build or deploy time, and the service runs with `HF_HUB_OFFLINE=1`, so it never downloads at startup. It exposes the OpenAI-compatible `POST /v1/embeddings`. The app talks to it through the **embedding endpoint** setting (default `http://embeddings:80/v1`), so any OpenAI-compatible endpoint can replace it.
- **Postgres:** `pgvector` (already installed) and `pg_trgm` (new extension).
- **Jev:** `POST https://api.typesafe.ai/v1/systemone`, model pinned in settings.

Why bge-m3: in the PoC benchmark on mixed Persian/English issue data it reached Recall@5 = 1.00 in every difficulty category, including transliteration, with no preprocessing. Query embedding took 67 / 93 ms (p50 / p95) on 4 CPU threads. The Phase 1 model (MiniLM) scored 0.91, truncates at 128 tokens, and failed single-word queries. Q1 and Q2 re-check this on production data and hardware.

### A.2 Normalization

Applied identically to indexed text and queries (PoC `rwsearch/normalize.py`):

- NFC; Arabic → Persian letters (`ي→ی`, `ك→ک`, `ة→ه`, …); Persian and Arabic digits → ASCII; remove diacritics, tatweel, ZWJ, and direction marks; collapse repeated ZWNJ; trim whitespace.
- The keyword index additionally folds: no ZWNJ, `آ→ا`, lowercase.
- Markdown is stripped from descriptions and comments: links → text, code blocks and inline code removed, `@mentions` removed.

The PoC's Persian↔English bridge (glossary and phonetic matching) is **not** used with bge-m3. It gave no gain on dense retrieval. Keep it in the PoC for smaller models.

### A.3 What gets indexed

Per item, derived from the item and its timeline:

| Kind | Text | Used by |
|---|---|---|
| `title` | normalized title | search |
| `body` | title + description + reproduction steps (description / expected / actual), normalized. No field labels. Chunked when longer than ~500 tokens (≈400-token chunks, 50-token overlap), one row per chunk | search; the **only** input for same-problem candidates (S4) |
| `talk` | one row per comment that passes classification (A.6) | search only, low weight |
| keyword text | title + description + URL paths from the cURL command (host, headers, and body dropped, so no secrets) + labels, folded | trigram channel |

Not indexed: system timeline events, people, dates, priority, environment, project name (a filter, not text), and cURL headers.

### A.4 Tables (engine-owned)

```
search_items          issue_id PK/FK, project_id, type, status, source, is_cancelled,
                      keyword_text, keyword_hash, embed_model, indexed_at
                      GIN (keyword_text gin_trgm_ops)
search_vectors        id, issue_id FK, kind (title|body|talk), chunk_no, timeline_id FK NULL,
                      is_internal bool, content_hash, embed_model, embedding vector(1024)
                      HNSW (embedding vector_cosine_ops); index (issue_id, kind)
comment_labels        timeline_id PK/FK, issue_id, label (this_problem|other_problem|process|ack|rule_kept|rule_dropped),
                      source (jev|rule), confidence NULL, content_hash, jev_model NULL, classified_at
duplicate_hints       id, issue_id FK, candidate_id FK, confidence, jev_model, computed_at
                      UNIQUE (issue_id, candidate_id)
duplicate_dismissals  issue_id FK, candidate_id FK, dismissed_by_id, dismissed_at
                      PK (issue_id, candidate_id)
```

Status, type, source, and project are copied into `search_items` so retrieval filters without joining into item tables. They are refreshed by `index_item`. Visibility is still applied through `visible_issues(actor)` (slice 04) when results are returned.

### A.5 Index jobs and triggers

| Job | Trigger | Work |
|---|---|---|
| `index_item(issue_id)` | item create/update of an indexed field, comment add/edit/delete, project move, status change. Debounced 10 s per item | Rebuild the keyword row; recompute changed `title`/`body` vectors (hash compare); sync `talk` vectors with current classifications; delete rows for deleted comments |
| `classify_comment(timeline_id)` | comment add/edit | Rule, or Jev when enabled (A.7); store in `comment_labels`; enqueue `index_item` |
| `compute_duplicate_hints(issue_id)` | a bug enters New, or its title/description changes while New, and Jev is enabled | Stage 1 with the body as the query over the BR-S09 candidates → Jev judge → keep up to 3 `same` with confidence ≥ `T_SAME` that are not dismissed |
| `reindex_all()` | Admin button, model/endpoint change | Enqueue `index_item` for every item in batches; progress in Redis |
| `backfill_comment_classification()` | Jev switched on | Reclassify `comment_labels` rows with `source = rule` |

Jobs are idempotent. The embedding service calls are batched (up to 32 texts). Jev calls in background jobs retry with backoff on 429/5xx; request-path calls never retry.

### A.6 Comment classification

- **Rule (Jev off):** drop if, after stripping mentions and markdown, the text is shorter than 20 characters or matches the acknowledgement list (`موافقم`, `اوکی`, `ok`, `مرسی`, `ممنون`, `انجام شد`, `done`, `👍`, …, kept in code). Otherwise `rule_kept`.
- **Jev on:** `rule_dropped` comments stay dropped without a Jev call. Others are classified with the A.7 question. Used for search: `this_problem`, `other_problem` (weight × 0.5), `rule_kept`. Confidence < 0.6 counts as used.
- Internal notes are classified and indexed like any comment, with `is_internal = true`. BR-S06 is enforced at query time.

### A.7 Jev contracts

All calls: `POST /v1/systemone`, the model from settings, a 1.5 s timeout on the request path and 10 s in background jobs, and at most 20 questions per call (split and run in parallel above that). Payloads use structured `instructions` so candidate data never mixes into the state.

**Search rerank** (Noul per candidate):
```json
{"state": "<raw query>",
 "questions": {"c_<id>": {"type": "noul", "instructions": {
   "issue": {"title": "…", "description": "<first 400 chars>"},
   "question": "The state is a search query typed into a software issue tracker. Does `issue` describe the problem the user is searching for? Wording and language (Persian/English, transliterated words) may differ."}}}}
```

**Same-problem judge** (Choice per candidate; create forms and triage hints):
```json
{"state": {"new_report": {"title": "…", "description": "…"}},
 "questions": {"c_<id>": {"type": "choice",
   "instructions": {"existing_issue": {"title": "…", "description": "<first 600 chars>", "type": "bug|task"},
                    "question": "The state is a new report being written. How does `existing_issue` relate to it? Wording and language may differ."},
   "criteria": {"same": "Same underlying problem: same feature and the same faulty behaviour",
                "related": "Same feature or area, but a different faulty behaviour, platform or condition",
                "unrelated": "A different feature or problem"}}}}
```

**Comment classification** (Choice):
```json
{"state": {"issue": {"title": "…", "description": "<first 600 chars>"}, "comment": "…"},
 "questions": {"kind": {"type": "choice",
   "instructions": "What does `comment` contribute to understanding the problem described in `issue`?",
   "criteria": {"this_problem": "Adds technical detail about this issue's problem: symptom, cause, reproduction, scope, error, or fix",
                "other_problem": "Mainly discusses a different, related problem or another project",
                "process": "Coordination, planning, assignment, product or priority decisions, no technical content",
                "ack": "Agreement, thanks, acknowledgement or status ping"}}}}
```

The Jev API reads English instructions best. Keep instructions in English; the state stays in the original language (validated on Persian in the PoC: accuracy on Persian state matched English).

### A.8 Retrieval

1. Normalize the query and embed it through the embedding endpoint (cached in Redis for 5 minutes by `(model, normalized query)`).
2. Candidate channels, each limited to 50, restricted to the scope (project or all visible projects) and to `search_items` rows with the current `embed_model`:
   - `body`: best cosine per item over its body chunks
   - `title`: cosine
   - `talk`: best cosine over used comments, excluding `is_internal` rows for Support
   - `keyword`: trigram `word_similarity(query, keyword_text) ≥ T_TRGM`, top 3 only. Ungated trigram ranks every Persian document and swamps the fusion, as the PoC showed.
3. Weighted reciprocal rank fusion (k = 60). Initial weights: body 1.0, title 0.6, talk 0.3, keyword 0.4. They are tuned on the evaluation set and fixed.
4. Apply visibility and filters. Hydrate the top 30.
5. **Jev off:** drop results whose best dense cosine is below `T_FLOOR`, and return the top 20.
6. **Jev on, search page:** send the top 15 to the Jev rerank. Order by Jev score (ties by fusion order) and split at `T_RELEVANT`.

Constants (`T_FLOOR`, `T_TRGM`, `T_RELEVANT`, `T_SAME`, the fusion weights) live in one module with a comment naming the evaluation run that set them.

### A.9 API

| Method | Path | Notes |
|---|---|---|
| GET | `/search?q=&scope=project\|all&project_id=&type=&status=&mode=page\|palette` | `mode=palette` never calls Jev. Response: `{results[], less_relevant[], jev_used: bool}` |
| POST | `/search/similar` | `{context: tech\|support, project_id, title, description, template_values?}`. Returns 204 when Jev is disabled. Response: `{items[{issue, verdict, confidence}]}` |
| GET | `/issues/{id}/duplicate-hints` | Tech only. Empty while Jev is disabled or the item is not New |
| POST | `/issues/{id}/duplicate-hints/{candidate_id}/dismiss` | Tech only |
| GET | `/features` | `{jev_enabled: bool}` for all users; the UI shows panels from this |
| GET/PUT | `/settings/search` | Admin. Embedding endpoint, index status |
| PUT | `/settings/search/jev` | Admin. `{enabled, api_key?, model}`. `enabled=true` requires a successful test with the stored key |
| POST | `/settings/search/jev/test` | Admin. One tiny Noul call; returns latency and the model version answered |
| POST | `/settings/search/reindex` | Admin |

The support panel's **record recurrence** calls the existing `POST /issues/{id}/recurrences` (slice 07) with the composed content and the pending attachment ids. No new endpoint.

### A.10 Settings storage

`system_settings` category `search`: `{embedding_endpoint, embed_model}`. Category `jev`: `{enabled, api_key_encrypted, model, last_test_ok_at}`. The key is encrypted with Fernet using a key derived from the app secret, and write-only in the API. The Phase 1 `llm` settings category and its UI section are removed. The embedding endpoint value migrates from it when present.

### A.11 Migration

One revision set in slice 12:
- `CREATE EXTENSION IF NOT EXISTS pg_trgm`; create the A.4 tables.
- Drop `issue_embeddings` (with its constraints and indexes, in whatever state migration `7f60b302c290` left them) and `issues.search_tsv` with its index.
- Remove the Phase 1 search code (`search_service.py` hybrid/rerank, `tasks/search.py`, `scripts/eval_search.py`) and the `llm` settings.
- After deploy, Admin runs **Reindex all** (also triggered automatically when `search_items` is empty at worker start).

This replaces the Phase 1 search entirely, so the Phase 1 search defects found during the PoC disappear with it: the rerank that never runs, e5 prefixes, model-change reindex, the unused `repro` group, and the migration that altered the vector column and constraints. AC-S22 checks the result.

### A.12 Test seams

Following slice 01: HTTP API tests against real Postgres.
- **Fake embedding endpoint:** an in-process ASGI app mounted as the embedding endpoint in tests. It returns deterministic vectors (character-trigram hashing into 1024 dims, L2-normalized), so tests are stable and need no model.
- **Fake Jev:** a recorder that takes scripted answers per question key or a default rule, records every request, and can simulate timeout, 429, and 5xx. AC-S02 and AC-S04 assert on it.
- Quality (§8) is **not** tested in CI. It is an evaluation run with the real model and real Jev, reported in the slice's PR.

### A.13 Evaluation harness

`backend/scripts/search_eval/` (ported from `poc/semantic-search/bench_*.py`) runs against the engine's own retrieval code with the dataset from `search-eval-dataset-spec.md`:
- `stage1`: Recall@1/5/10, MRR, nDCG@10 per difficulty category, plus latency, for the engine and for the Phase 1 baseline (MiniLM with the Phase 1 document construction).
- `stage2`: Jev rerank ranking metrics and threshold sweep (`T_RELEVANT`); same-problem precision/recall per draft kind and threshold sweep (`T_SAME`); no-match false positives.
- `comments`: confusion matrix for the classification.
Output: a Markdown report checked into `docs/specs/phase-2/eval/` with the constants it recommends.
