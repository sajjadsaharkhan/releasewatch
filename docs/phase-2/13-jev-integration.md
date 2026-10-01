# 13 — Jev Integration

> **Depends on:** 12 · **Engine doc:** [prd-search-engine.md](prd-search-engine.md) FR-S03, FR-S16 (Jev part), FR-S18; BR-S01–S03, BR-S05, BR-S14, BR-S18, BR-S19; AC-S02–S04, AC-S17, AC-S19, AC-S20; §8 Q4, Q5; Appendix A.6, A.7, A.8 (step 6), A.10, A.12, A.13 (stage2 search part)

## Problem Statement

Local ranking puts plausible-but-wrong items near the top and cannot say "nothing here really matches". For a query about reactions in group chat, the PoC's stage 1 ranked "reaction counter in private chat" first. Comments are filtered only by length and a word list, so long process discussions and comments about other problems still enter the index. Jev can judge each candidate in one parallel call of about 0.4–1 s and return calibrated scores, but it is an external dependency. It must be optional, and turning it off, or losing it, must not break anything.

## Solution

Add Jev behind one global switch, managed by Admin in Settings with an encrypted API key, a pinned model, and a connection test. A single `JevClient` owns every call, with a hard timeout and one fallback rule: any failure means Jev-off behavior for that request. With Jev on, the search page sends the top 15 local candidates to Jev, orders them by Jev's score, and moves results under the relevance threshold into a collapsed section. The command palette never calls Jev. Comment classification uses Jev for new comments, and switching Jev on reclassifies the comments previously handled by the rule.

## User Stories

1. As an admin, I want to paste a Jev API key, choose the model (default `jev-1.13.0`), and press **Test connection**, so that I know it works before turning it on. (FR-S18)
2. As an admin, I want the Enabled switch to refuse to turn on until a test with the saved key succeeds. (AC-S19)
3. As an admin, I want the key never shown again after saving, only masked, and never returned by any API. (BR-S18, AC-S20)
4. As an admin, I want one switch for the whole installation, so that there is one place to look when behavior changes. (BR-S01)
5. As a user, I want search results ordered by how well they answer my query when Jev is on. (FR-S03)
6. As a user, I want weak matches moved into a collapsed "Less relevant results (n)" section instead of hidden, so that I can still check them. (FR-S03, AC-S03)
7. As a user, I want "No close matches" when nothing reaches the threshold, with the collapsed section below it. (FR-S03)
8. As a user, I want search to keep working with local ordering when Jev is slow or down, without an error. (BR-S02, AC-S02)
9. As a user typing in the command palette, I want instant results that never wait for Jev. (BR-S05, AC-S04)
10. As an engineer, I want comments about another problem to stay searchable at lower weight, and process or acknowledgement comments left out, so that results reflect the problem. (FR-S16)
11. As an admin, I want switching Jev on to reclassify only the comments the rule handled, once, and switching it off to keep Jev's earlier classifications. (BR-S14, AC-S17)
12. As an operator, I want every Jev failure logged with its cause (timeout, 401, 429, 5xx), without the payload, so that I can see Jev's health.
13. As the CTO, I want the evaluation to set the relevance threshold and to report no-match behavior and comment-classification accuracy. (§8 Q4, Q5)

## Implementation Decisions

### Settings

- `system_settings` category `jev`: `{enabled, api_key_encrypted, model, last_test_ok_at, last_test_key_fingerprint}` (A.10). Encrypt with Fernet, using a key derived from `SECRET_KEY` with HKDF and a fixed info string. The API accepts `api_key` on PUT and returns only `{has_key: bool, key_last4}`.
- `PUT /settings/search/jev`: `enabled=true` requires `last_test_ok_at` set **and** `last_test_key_fingerprint` equal to the current key's fingerprint. Otherwise it returns 409 `code: jev_test_required`. Saving a new key clears `enabled` and the test stamp.
- `POST /settings/search/jev/test`: one Noul call (`state: "ping"`, question "Is the state a greeting?"). It returns `{ok, latency_ms, model}` from the response's `model` field, and stores the stamp on success.
- `GET /features` → `{jev_enabled}` = `enabled && has_key`. Cache it for 30 s in-process and bust the cache on PUT.

### Client

- `app/search/jev.py`: `JevClient` with `rerank(query, items)`, `judge_same(draft, items)` (used in 14), and `classify_comment(issue, text)`. Payloads exactly as in Appendix A.7. Port the request shaping from `poc/semantic-search/rwsearch/jev.py`.
- Base URL: `settings.JEV_BASE_URL` (env only, default `https://api.typesafe.ai`), so tests and E2E can point to a fake. It is not an Admin setting.
- Timeouts: 1.5 s total on the request path, 10 s in jobs. At most 20 questions per call; above that, split and `asyncio.gather`. Request path: **no retry**. Jobs: up to 4 retries with exponential backoff on 429/5xx/timeout.
- Result type: `JevOutcome(ok: bool, answers | None, reason)`. Callers branch on `ok` only. There is no exception path to the user (BR-S02).
- Log `jev_call` with `purpose, n_questions, latency_ms, ok, reason, model`. Never log the state or the instructions.

### Search (A.8 step 6)

- In `retrieval.search`: when `mode=page` and `jev_enabled`, send the top 15 fused candidates (after visibility) to `rerank`. On `ok`, order by score (ties keep fusion order), return `results` = score ≥ `T_RELEVANT` and `less_relevant` = the rest, with `jev_used: true`. On failure, return the Jev-off path unchanged with `jev_used: false`.
- The floor `T_FLOOR` still applies before Jev, so Jev never sees junk candidates.
- Candidate payload per item: title and the first 400 characters of the normalized description. Never send internal notes (they aren't part of the payload at all).
- `T_RELEVANT` goes in `constants.py`. Start at 0.5 (the PoC demo: same-problem items scored 0.91–0.94, related 0.52–0.70, junk ≤ 0.44). Set the final value from the evaluation.

### Comment classification (A.6)

- `classify_comment`: `rule_dropped` stays dropped with no call. Otherwise, with Jev enabled, call `classify_comment`. Store `label, source='jev', confidence, jev_model`. On failure, store the rule result with `source='rule'` so the backfill picks it up later.
- Weights in the talk channel: `this_problem` 1.0, `other_problem` 0.5, `rule_kept` 1.0; confidence < 0.6 counts as used (1.0). Apply the weight to the talk channel's per-item score before fusion.
- `backfill_comment_classification`: enqueued when `enabled` flips to true. It iterates `comment_labels` where `source='rule'` and `label='rule_kept'` in batches of 100, reclassifies them, and re-enqueues `index_item` for affected items. Progress is shown in Settings. It is idempotent; running it twice changes nothing the second time.

### Frontend

- Settings → Search → **Jev** panel: Enabled switch (disabled with the tooltip "Test the connection first" until allowed), API key field (write-only; shows `•••• 1a2b` when set), model field, **Test connection** with a result line (latency, model), backfill progress when running. Copy per `docs/design.md`.
- SearchPage: render `less_relevant` as a collapsed section under the results, and "No close matches" when `results` is empty but `less_relevant` is not. No Jev branding in the user-facing UI; users see "Less relevant results".

### Evaluation harness

- Add `stage2 --part search` and `--part comments` (A.13): Jev rerank metrics, a `T_RELEVANT` sweep with no-match false positives (Q4), and the comment confusion matrix (Q5). Port from `poc/semantic-search/bench_jev.py`. Check the report into `docs/specs/phase-2/eval/stage2-search-<date>.md`, and set `T_RELEVANT` from it.

## Testing Decisions

- Fake Jev (Appendix A.12): an autouse fixture `jev` that replaces the transport of `JevClient`. `jev.script(key_prefix → answer)`, `jev.default(rule)`, `jev.fail(mode)` with `timeout | http_429 | http_500 | http_401`, and `jev.calls` for assertions. Tests enable Jev through the settings API with a key and a passing fake test.
- Named ACs:
  - `test_ac_s02_jev_timeout_falls_back_to_local_order`
  - `test_ac_s03_below_threshold_goes_to_less_relevant`
  - `test_ac_s04_palette_never_calls_jev`
  - `test_ac_s17_enabling_jev_backfills_only_rule_labels`
  - `test_ac_s19_cannot_enable_without_successful_test`
  - `test_ac_s20_api_never_returns_key`
- Each failure mode (timeout, 401, 429, 500, malformed body) on the search path returns 200 with `jev_used: false`.
- Saving a new key disables Jev and requires a new test.
- A Support user's search sends Jev only items visible to them (assert on `jev.calls`).
- Disabling Jev keeps `source='jev'` labels; new comments get `source='rule'`.
- **E2E:** none new. SearchPage's collapsed section is covered by an API test plus a component-level check through Playwright MCP during development (not a CI test).

## Out of Scope

- Similar-item panels and triage hints (14), although `judge_same` is implemented here so 14 only wires it.
- Per-feature switches, per-project switches, or threshold settings in the UI (BR-S01, BR-S19).
- Showing Jev scores to users.

## Further Notes

- Jev returns calibrated probabilities, but calibration was measured on English. The PoC's Persian test (fa state, en questions) matched English accuracy, which is why the questions stay in English (A.7). Re-check this in the stage-2 evaluation on real data.
- Pin the model (`jev-1.13.0`), not `jev-latest`, so thresholds stay valid. Changing the model in Settings is an explicit Admin action. Re-run the evaluation before doing it.
