# 14 — Similar-Item Suggestions and Triage Merge Hints

> **Depends on:** 13 (uses 05 support form, 06 Duplicate outcome with merge effects, 07 recurrence) · **Engine doc:** [prd-search-engine.md](prd-search-engine.md) FR-S08–S15; BR-S03, BR-S07–S12, BR-S21; AC-S07–S14; §8 Q3; Appendix A.4 (hints), A.5, A.7, A.9 · **PRD:** [v3](prd-v2.md) FR-12, BR-20, BR-49, BR-50
> **v3:** triage hints may point at tasks as well as bugs, and a merge into a Done candidate sends it back to To do with a new cycle (`release_qa` or `production`) instead of making it a regression. The merge itself is 06 as reworked by 08a Part 3.

## Problem Statement

Duplicates enter from three directions: Support re-reporting a known problem, the tech team filing something already filed, and a fixed bug returning in production. Support cannot see tech-filed items, so it cannot spot those duplicates. The triage lead has no hint that a New bug matches an existing one, so duplicates become separate work, and problems with work that is already done are never sent back for a fix.

## Solution

While Jev is enabled, three suggestion surfaces use stage-1 candidates plus Jev's same / related / unrelated judgment:
- **Support form:** open support reports in the chosen project that are the same problem, with **This is the same problem — record recurrence**, so no new report is created.
- **Tech create form:** same-problem and related items of any type in the project, for information only.
- **Triage queue:** for every bug entering New, up to three stored possible duplicates. **Merge into this** runs the Duplicate outcome with that original; merging into a Done original sends it back to To do with a new cycle (PRD BR-49). **Not a duplicate** dismisses the pair for good.

With Jev off, none of these surfaces exist.

## User Stories

### Support form
1. As a Support user, I want similar open reports in the chosen project to appear once I've typed a title and filled a template text field, so that I can spot a known problem before submitting. (FR-S09)
2. As a Support user, I want only reports describing the same problem, not every loosely related one, so that the panel is worth reading. (FR-S09)
3. As a Support user, I want **This is the same problem — record recurrence** to add my report's details and attachments to that item, count it once more, and subscribe me, without creating a new report. (FR-S10, BR-50, AC-S09)
4. As a Support user, I want a confirmation with a link to the item, and a cleared form, after recording. (FR-S11)
5. As a Support user, I want the panel never to show Done, Cancelled, non-support, or other-project items. (BR-S07, AC-S08)
6. As a Support user, I want to open a suggestion in a new tab without losing my draft.

### Tech create form
7. As a QA engineer or developer, I want a **Possibly the same** panel with same-problem and related items in the selected project while I write a bug or task, so that I check before filing. (FR-S08)
8. As a tech user, I want each suggestion labeled "Same problem" or "Related", with key, type, status, and title, and opened in a new tab. (FR-S08)
9. As a tech user, I want no merge button here, because triage merges. (FR-S08)

### Triage
10. As a triage lead, I want New bugs that match an existing bug marked **Possible duplicate** in the queue row, so that I see them before accepting. (FR-S12, FR-S13, AC-S10)
11. As a triage lead, I want each hint to name the candidate's key, title, and status, and say what merging will do ("stays In progress", "stays Cancelled", "Done → back to To do (release QA)", "Done → back to To do (production)"). (FR-S13, AC-S11)
12. As a triage lead, I want **Merge into this** to open the Duplicate outcome with the candidate preselected, so that merging is one confirmation. (FR-S14)
13. As a triage lead, I want **Not a duplicate** to hide that pair permanently, even after reindexing. (FR-S14, BR-S12, AC-S12)
14. As a triage lead, I want hints only while the item is New, so that they don't linger. (FR-S15, AC-S13)
15. As a triage lead, I want hints for duplicates between Support and QA reports even though Support never saw them. (BR-S09)
16. As a triage lead, I want hints recomputed when a New item's title or description changes.
17. As a Support user, I want never to see triage hints. (FR-S13)

### Off switch
18. As any user, I want all three surfaces absent while Jev is disabled, and stored hints hidden (not deleted), so that turning Jev back on restores them. (BR-S03, AC-S07)
19. As a user, I want a Jev timeout to show no panel rather than an error or a stale one. (BR-S02)

## Implementation Decisions

### Schema

- `duplicate_hints` and `duplicate_dismissals` as in Appendix A.4. Hints are replaced wholesale on each computation for an item. Dismissals are never deleted by jobs.

### Candidate generation (shared)

- `retrieval.same_problem_candidates(draft_text, project_id, allowed_filter, k=10)`: the `body` and `title` channels only (no talk, no keyword; S4), with the draft as the query, fused, and filtered by the consumer's candidate rule:
  - support: `source=support AND status NOT IN (done, cancelled)` (BR-S07)
  - tech form: `status <> cancelled`, any type (BR-S08)
  - triage: `status <> cancelled AND id <> self`, bugs and tasks (BR-S09, PRD BR-20)
- The draft text is built with the same `build_documents` body rule: title + description (+ the composed template block for Support).
- Then `JevClient.judge_same(draft, candidates)` (A.7).

### `POST /search/similar`

- Returns 204 when Jev is disabled or the call fails (the UI hides the panel on 204).
- `context=support`: only `verdict=same` with confidence ≥ `T_SAME`. `context=tech`: `same` ≥ `T_SAME` and `related` ≥ `T_RELATED`, same first. At most 5.
- Visibility is enforced with `visible_issues(actor)` before Jev sees anything.
- `T_SAME` starts at 0.7 and `T_RELATED` at 0.6 (PoC `bench_jev` policies). Final values come from the evaluation (Q3).

### Record recurrence from the support panel

- The UI composes the report exactly as `compose_report` (05) would, then calls the existing `POST /issues/{id}/recurrences` with `{comment: <composed markdown>, pending_attachments: [...]}`. Extend 07's endpoint to accept `pending_attachments` and attach them to the item (same pre-upload flow as 05). No other change to 07's semantics.
- If the template's required fields are not filled, the button is disabled with "Fill the required fields first". The same completeness applies as for submitting.

### Triage hints

- `compute_duplicate_hints(issue_id)` job (A.5). Triggers: `filed` for bugs, `project_changed` during triage, and title or description edits while `status=new`. Only when Jev is enabled. Keep up to 3 `same` with confidence ≥ `T_SAME`, excluding dismissed pairs.
- `GET /issues/{id}/duplicate-hints`: tech only (Policy `view_duplicate_hints`). Returns `[]` unless `status=new` and Jev is enabled. Each hint includes `candidate {key, type, title, status, container}` and `merge_effect ∈ {unchanged, stays_cancelled, returns_release_qa, returns_production}`, computed from the candidate's status and whether it is shipped, per BR-49. Compute it with the same function 08a's `MergeService` uses to pick the reason, so the hint and the merge never disagree.
- `POST /issues/{id}/duplicate-hints/{candidate_id}/dismiss`: inserts into `duplicate_dismissals` and deletes the hint.
- Triage queue list endpoint (06): add `possible_duplicates_count` per row, 0 while Jev is disabled.
- **Merge into this** opens 06's Duplicate outcome form with `duplicate_of_id` preset. The merge itself, including the BR-49 return, is 06's `triage` endpoint as reworked by 08a Part 3. Nothing new here.

### Frontend

- `NewIssueModal` (03's work-item form): a side panel (below on narrow screens), shown only when `features.jev_enabled`. Debounce 800 ms after changes to title or description, and cancel in-flight requests on new input. Rows: badge "Same problem" or "Related", type icon + key, status, title, open in new tab. Show nothing (not an empty state) when there are no suggestions.
- Support form (05): the **Similar reports** panel in the same place 05 reserved, shown only when `features.jev_enabled` and the title plus one template text field are filled. Each row has the record-recurrence button, which opens a confirm dialog showing the composed content that will be added.
- Triage queue: a compact "Possible duplicate" marker on rows with `possible_duplicates_count > 0` (P3: nothing otherwise). The detail pane shows the hints with the merge-effect sentence and the two actions.
- Item page (tech users, New only): the same hints block under the title.

### Evaluation harness

- Add `stage2 --part similar`: runs `drafts.json` through `same_problem_candidates` + `judge_same` for each context's filter, with a `T_SAME` sweep. It reports precision, recall, and F1 per draft kind (duplicate, recurrence, hard_negative, novel) and the policy "show top-3 without Jev" as reference. Check the report into `docs/specs/phase-2/eval/stage2-similar-<date>.md`. Q3 gates.

## Testing Decisions

- Uses the fake Jev (13) and the fake embedding endpoint (12).
- Named ACs:
  - `test_ac_s07_no_panels_or_hints_when_jev_disabled`
  - `test_ac_s08_support_candidates_open_support_same_project_only`
  - `test_ac_s09_support_records_recurrence_from_panel`
  - `test_ac_s10_new_bug_gets_possible_duplicate_hint`
  - `test_ac_s11_hint_on_done_candidate_says_return_and_merge_returns` (runs 06's merge; asserts PRD AC-50 and AC-51 effects, one Stream candidate and one unshipped-release candidate)
  - `test_ac_s12_dismissed_pair_never_returns_after_reindex`
  - `test_ac_s13_hint_hidden_after_leaving_new`
  - `test_ac_s14_cancelled_never_suggested`
- `POST /search/similar` returns 204 on each Jev failure mode.
- A Support user calling `/search/similar` with `context=tech` gets 403. Hints endpoints return 403 to Support users on items they can see, and 404 on items they can't (04's rule).
- Turning Jev off hides hints; turning it on again shows the same hints without recomputation.
- **E2E (extends key screens):**
  - `support-report.spec.ts`: with the fake Jev scripted to answer `same` for a seeded open support report, the panel appears after typing, **record recurrence** confirms, and the seeded report's recurrence count increases while no new report appears in Support reports.
  - `triage.spec.ts`: a new bug filed through the API gets a hint (compute job run eagerly in E2E), and the lead merges from the hint into a Done bug in the Stream. The bug shows To do with the returned marker (production).
  - The E2E stack sets a fake Jev endpoint via env (`JEV_BASE_URL`, test-only) served by a tiny scripted server in `e2e/`.

## Out of Scope

- Auto-merge, auto-link, or any action without a click (BR-S11).
- Cross-project suggestions.
- Suggestions while Jev is off (S3).
- Changing the merge rules; they are in 06.

## Amendment 2026-10-02 — dismissals are kept as training data

`duplicate_dismissals` now also stores, at the moment of "Not a duplicate": Jev's `confidence` and `jev_model`, when the hint was computed, and a snapshot of both items' title and description plus the candidate's status. They are labelled negatives for tuning `T_SAME` or training a similarity model later (a merge into the candidate is the matching positive). Rows dismissed earlier, or without a stored hint, have these columns null; re-dismissing keeps the first snapshot. The snapshot holds production text — treat exports accordingly.
