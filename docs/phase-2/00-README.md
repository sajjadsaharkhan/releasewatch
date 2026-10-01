# Phase 2 — Implementation Specs

These specs turn [`prd-v2.md`](prd-v2.md) (**v3**), its companion [`cycle-model.md`](cycle-model.md), and [`prd-search-engine.md`](prd-search-engine.md) into work Claude Code can carry out in this repo. Each numbered file is **one vertical slice**: schema, API, UI, and tests together. Each slice is sized for one Claude Code session and ends with the app shippable.

The PRD is the product authority. When a spec and the PRD disagree, the spec wins, because the spec has been checked against the code. Every such difference is listed in the **Decisions** section of [`CONTEXT.md`](../../CONTEXT.md).

---

## Order

Slices must be built in order. Each one depends on everything above it.

| # | Slice | Depends on | PRD coverage |
|---|---|---|---|
| 01 | [Test harness](01-test-harness.md) | — | none (enabler) |
| 02 | [Unified status model](02-unified-status-model.md) | 01 | §9, BR-13/14, BR-24, BR-25, BR-28 (v2.2 rows; reworked by 08a) |
| 03 | [Tasks, hotfix placement, project kinds](03-tasks-and-placement.md) | 02 | FR-01–05, BR-01, BR-03, BR-07–09, BR-11/12 (hotfix and project kinds removed by 08a) |
| 03a | [Data model refactor](03a-data-model-refactor.md) | 03 | §8.2, §9.2, FR-18, FR-36/37/39/42/43, BR-08/09/16, AC-16/24/36/43; removes Urgent |
| 04 | [Roles and visibility](04-roles-and-visibility.md) | 03 | §7, BR-15, BR-30–32, AC-07/08, AC-23, AC-47 |
| 05 | [Support intake](05-support-intake.md) | 04 | FR-07–11, FR-44/45, BR-33–35, AC-01–06 |
| 06 | [Triage outcomes](06-triage-outcomes.md) | 05 | FR-17–20, BR-16–21, BR-49/50, AC-14–22, AC-49–54, §13 support/triage-lead notifications |
| 07 | [Recurrence](07-recurrence.md) | 06 | FR-13–16, BR-22/23, BR-50, AC-09–13 |
| 08 | [Backlog and technical debt](08-backlog-and-tech-debt.md) | 07 | FR-23–29, BR-04–06, BR-36/37, AC-28–31 |
| 08a | [Rework for v3: containers, cycles, QA gate](08a-release-stream-cycles.md) | 08 | §8.1, §8.2, §8.7, §8.9, §9, FR-03, FR-16, FR-18, FR-25, FR-55–66, BR-20, BR-22–29, BR-49–66; AC-24–27, AC-49–58, AC-64–78 — **three sessions** |
| 09 | [Releases and Stream](09-releases-and-stream.md) | 08a | FR-46–54, BR-47/48, BR-51/52, BR-55–57; AC-45/46, AC-55, AC-59–63 |
| 09a | [To review, Rejected, one Reject action](09a-review-queue-and-rejected.md) | 09 | Changes 08a Part 3, CY-05, CY-11 ([ADR 0004](../adr/0004-rejected-is-a-status.md)) |
| 10 | [Personal queue and board](10-personal-queue.md) | 09a | FR-33–42, FR-63/64, BR-38–46, BR-61, AC-32–44, AC-74/75, §13 assignee notifications |
| 11 | [Team overview](11-team-overview.md) | 10 | FR-43, AC-48 |
| 12 | [Search engine core (local)](12-search-engine-core.md) | 11 | Engine FR-S01–07, FR-S16/17/19; AC-S01, S05, S06, S15, S16, S18, S21, S22; Q1, Q2 |
| 13 | [Jev integration](13-jev-integration.md) | 12 | Engine FR-S03, FR-S16/18; AC-S02–S04, S17, S19, S20; Q4, Q5 |
| 14 | [Similar-item suggestions and triage merge hints](14-similar-item-suggestions.md) | 13 | PRD FR-12; Engine FR-S08–S15; AC-S07–S14; Q3 |

Slices 12–14 are the Search & Ranking Engine part. Before starting 12, build the evaluation dataset with [search-eval-dataset-spec.md](search-eval-dataset-spec.md) (an agent with read access to a database snapshot). Slices 12–14 each check an evaluation report into `eval/`.

## How to run a slice in Claude Code

Start a fresh session for each slice. Use this prompt:

```
Implement docs/specs/phase-2/NN-<name>.md.
Read docs/specs/phase-2/00-README.md first, then the slice spec, then the PRD sections it cites.
Work test-first at the seams defined in 01-test-harness.md: write the failing API tests for each
user story, make them pass, then build the UI. Run `make test` (and `make e2e` when the slice lists
E2E scenarios) before finishing. Update CONTEXT.md with any glossary terms the slice introduces.
Do not start the next slice.
```

Before you mark a slice done:

- [ ] Every user story in the slice has at least one passing test at the API seam.
- [ ] Every PRD acceptance criterion the slice cites has a test named after it (for example `test_ac_16_accept_as_urgent_requires_assignee`, or `test_ac_s03_…` for engine criteria).
- [ ] Alembic `upgrade head` and `downgrade -1` both run cleanly on a database seeded by `make seed`.
- [ ] The UI follows `docs/design.md`. Loading, empty, and error states all exist.
- [ ] `make lint` passes.

---

## Shared decisions (apply to every slice)

### Vocabulary: code names vs. product names

The PRD's **work item** is the existing `Issue` model and `issues` table. **Do not rename** the model, the table, or the `/api/v1/issues` routes. Renaming would churn every file without changing any behavior. Phase 2 adds a `type` column (`bug` | `task`) to the same table. In code and in `CONTEXT.md`, "issue" stays the implementation name. In UI copy, use the PRD terms: "work item", "bug", and "task".

### Keys

The global `issue_number_seq` stays. The display key comes from the type: `BUG-123` or `TASK-124`. The two types share one number space, so a number is never reused. The route `/issue/:slug` accepts `issue-123`, `bug-123`, and `task-123` (case-insensitive), so old links keep working.

### Enums

`role`, `status`, `type`, `priority`, and `cancel_reason` are stored as `String`, not as native Postgres enums. Adding a value means changing the Python enum and writing a data migration. No `ALTER TYPE` is needed.

### No hardcoded enum values (from 03a)

Every enum value — status, type, priority, cancel reason, timestamp kind, release kind, release status, cycle start reason, backlog category, role — is declared **once per side**:

- backend: `app/domain/enums.py` — the enums, the named sets (`TRIAGE_STATUSES`, `BOARD_STATUSES`, `OPEN_STATUSES`, `FINAL_STATUSES`, `CANCELLABLE_FROM`) and the predicates (`is_open`, `is_final`, `is_board`, `can_cancel`, `requires_priority`)
- frontend: `src/lib/domain.js` — the same values, sets and predicates, plus labels and colors; `lib/constants.js` re-exports it

No other file writes one of these values as a literal, and no other file re-derives a set with a comparison such as `status not in ("done", "cancelled")`. Ask the module. A pytest parity test compares the two modules and fails on divergence, and a grep guard fails on literals outside them (migrations, seeds, tests and `mockData.js` are exempt).

### Where rules live

Phase 1 already puts domain logic in services and keeps routes thin. Phase 2 adds three **pure modules**. Each takes plain values in and returns plain values out, with no database or HTTP access. Services call them, and they are the only place their rule may be written:

| Module | Owns | Introduced in |
|---|---|---|
| Workflow | Allowed status transitions per type, and the reason a transition is refused | 02 |
| Policy | Who can do what to which item or project, with a reason (drives disabled-control tooltips) | 04 |
| Release lifecycle | Allowed release status changes, and why one is refused | 09 |
| Queue ordering | Default order, insertion point, pin grouping, dormant entries | 10 |
| Search text | Normalization, document building, comment rules (`app/search/normalize.py`, `documents.py`, `comment_rules.py`) | 12 |

Services that own one rule each, so it is written once: `MergeService.merge_into` (effects on an original for a merge or a recurrence, PRD BR-49/50; 06, reworked in 08a), `CycleService` (every write to `issue_cycles` and `issues.current_cycle_id`; 08a), `ReleaseService.ship` (ship effects; 09), and `JevClient` (every Jev call, its timeout, and the fallback; 13).

### No bulk status changes (v3)

No endpoint and no screen changes the status of several items at once (PRD FR-62, BR-60). Bulk actions change placement only (`POST /issues/bulk-move`).

API responses for an item include `allowed_transitions` and `allowed_actions`, both computed from these modules. **The frontend never re-derives a permission or transition rule.** It only renders what the API returns.

### Errors

A domain rule violation returns `409` with this body:

```json
{ "detail": "human-readable reason", "code": "snake_case_rule_id", "allowed": ["..."] }
```

Include `allowed` only when it is meaningful (for example, allowed transitions). Validation failures stay `422`. An item the caller may not see returns `404`, never `403`.

### Notifications

Every notification goes through `InboxFanOutService.fan_out`. It creates `InboxItem` rows, and those rows drive Telegram delivery through the notification matrix. New notification events are added as new `InboxEventType` values with a row in `DEFAULT_NOTIFICATION_MATRIX`. Nothing sends Telegram messages directly. There is still no email.

### Migrations

Use one Alembic revision per slice, or a few if a data migration must run separately. Each revision needs a working `downgrade`. Data migrations must be idempotent and must leave Phase 1 reports producing the same numbers where the meaning has not changed.

---

## Where the specs differ from the PRD

The decisions table (D1–D16) moved to the **Decisions** section of [`CONTEXT.md`](../../CONTEXT.md) after slice 11, so it outlives these specs.

## Glossary additions (put in `CONTEXT.md`)

Add each slice's terms in that slice's session, using the existing `CONTEXT.md` format (term, definition, `_Avoid_`). The full list: work item, bug, task, display key, flow status, workflow, triage queue, triage outcome, support report, support template, subscriber, recurrence, merge, container, stream, release lifecycle, ship, cycle, start reason, return, returned marker, technical debt, backlog, personal queue, pin, locked pin, dormant queue entry, queue history, policy, search engine, stage 1, stage 2, Jev, similar-item suggestion, possible duplicate, comment label.

_Avoid_ (removed in v3): milestone, hotfix, regression cycle, merge regression, project kind.

---

## v3 changes (for slices already built)

PRD v3 removed milestones and project kinds, introduced the Stream, made one QA gate for bugs and tasks, replaced regressions with cycles, and moved every new report to Phase 3. The product reasoning is in [prd-v2.md](prd-v2.md) §0 and [cycle-model.md](cycle-model.md).

Slices 01–08 are implemented and their texts are left unchanged. **Every v3 change to the code they built is in one new slice, [08a](08a-release-stream-cycles.md)**, run as three sessions (prompts at its bottom) before starting 09. Phase 2 has not shipped, so 08a rewrites migrations and rebuilds dev databases; there is no data migration. Slices 09–14 were written for v3 and need no delta.

## v2.1 changes (for slices already built)

If a slice below was implemented before v2.1, run a short follow-up session with this prompt before starting the next slice: *"Apply the v2.1 changes to slice NN as described in docs/specs/phase-2/00-README.md → v2.1 changes, with tests."*

| Slice | Change |
|---|---|
| 02 | Reserve the `done → in_progress` (`merge_regression`) Workflow row, reachable only from 06. Rephrase the no-release regression test to cover the direct action only. **v2.2:** severity becomes `priority`; the `time_to_*` columns move in 03a. |
| 05 | Remove `GET /support/similar` and the title-match panel (moved to 14, Jev-only). Keep the panel's space in the layout. |
| 06 | Duplicate outcome = merge: add the merge comment and `MergeService` with BR-49 status effects; `regression_history.release_id` nullable + `source`; ACs 49–54. |
| 07 | New Done guidance text (FR-16); recurrence goes through `MergeService`; accept `pending_attachments`; remove the similar-panel entry point (14). |
| 12–14 | New. |

### v2.2 changes (Urgent removed, priority unified, storage refactor)

All of this is specified in [03a-data-model-refactor.md](03a-data-model-refactor.md), which carries the two prompts. Slices not yet built already contain the updated text.

| Slice | Change |
|---|---|
| 02 | `severity` → `priority` (`critical/high/medium/low`, nullable); the `time_to_*` and lifecycle columns move to `issue_timestamps` + `DurationService` |
| 03 | **Implemented already** — run 03a Part 1 and Part 2 against it: drop `is_urgent`, unify priority, split the tables, add the enum modules, rewrite the seed |
| 04 | Policy actions: `set_urgent` and `set_severity` gone, `set_priority` stays |
| 05 | New support reports are created with `priority = null` |
| 06 | No `accept_urgent` outcome; `accept` requires `priority`; an accept with no release is the hotfix path |
| 08 | Backlog rows show priority; `backlog_category` and `backlog_rank` are shared columns on `issues` |
| 10 | Two queue groups (pinned, rest); default order reads the single `priority`; no urgent marker |
| 11 | Workload counts are open and pinned only |
| 12 | `search_items` copies `priority` with the other filter columns; priority is not indexed as text |
