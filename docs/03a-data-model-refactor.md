# 03a — Data Model Refactor: types, priority, timestamps, enums

> **Depends on:** 03 (already implemented) · **Replaces parts of:** 02, 03 · **PRD:** §8.2, §9.2, FR-18, FR-22 (removed), FR-36/37/39/42/43, BR-08/09, BR-16, BR-17 (removed), BR-27 (removed), AC-16/24/36/43 · **Product doc:** [prd-v2.md](prd-v2.md) v2.2
> **Run this in two sessions.** Part 1 is behavioral and small; Part 2 is structural and large. The prompts are at the bottom.

## Problem Statement

Slices 02 and 03 are implemented on dev. Four problems came out of the review:

1. **Urgent was never asked for.** It was invented in the PRD as a third ordering tier and a triage outcome. Importance is already expressed by priority, and "do this first" by pinning in the personal queue. It is one more flag to set, clear, notify on, filter by, and order by, for nothing.
2. **Two importance scales.** Bugs have `severity` (blocker, critical, major, minor) and tasks have `priority` (1–4). Every list, card, filter, queue rule, and report has to know which one to read, and the two vocabularies show up side by side in the UI.
3. **One wide table.** `issues` carries bug-only columns (six environment and reproduction columns, regression counters), task-only columns, lifecycle timestamps, and derived durations. Type-specific columns are null for half the rows, and the derived `time_to_*_h` columns can disagree with the timestamps they were computed from.
4. **Enum values are written as strings all over the code**, in both the backend and the frontend, and sets such as "open statuses" are re-derived in each place that needs them.

## Solution

- Remove Urgent entirely.
- Replace `severity` and `priority` with one shared `priority` column: `critical | high | medium | low`, nullable until triage.
- Split `issues` into the shared table plus `issue_bugs` and `issue_tasks`, always one meta row per item.
- Move lifecycle timestamps into `issue_timestamps` (`issue_id, kind, occurred_at, actor_id`, one row per kind, last occurrence wins), drop `time_to_*_h`, and compute durations in one service.
- Add one enum module per side (`app/domain/enums.py`, `frontend/src/lib/domain.js`) holding every value, the named sets, and the predicates, with a parity test.

Phase 2 is not in production. The Phase 2 migrations are **rewritten** to land on the final shape in one step, and dev databases are rebuilt. The rewritten migrations still have to carry a **Phase 1 production database** forward, so every data mapping below must run against a production dump before this is considered done.

---

## Part 1 — Remove Urgent, unify priority

### User Stories

1. As a triager, I want one **Accept** outcome, so that there is one way to accept a bug. (PRD FR-18 v2.2)
2. As a triager, I want a bug fixed without a release to be a normal Accept with no release chosen, so that the hotfix path needs no special outcome. (FR-21)
3. As a developer, I want no urgent flag, notification, filter, card marker, or queue tier anywhere. (FR-22, BR-17, BR-27, AC-16, AC-24, AC-36 removed or rewritten)
4. As a developer, I want one importance field named **priority** with the same four values for bugs and tasks. (BR-08, BR-09)
5. As a triager, I want a New bug to have no priority until someone rates it, and priority to be required when I accept it. (BR-16)
6. As a developer, I want a new task to start at `medium`.
7. As a QA engineer, I want existing `blocker` bugs to become `critical` **and** to carry the release-blocker flag, so that no information is lost.
8. As a developer, I want my queue ordered pinned first, then everything else by the default rule. (FR-36, FR-39, BR-39)
9. As a developer, I want the default rule to read one field: priority, then due date, then recurrence count, then age. (FR-37)
10. As a developer, I want cards to show a priority icon and the markers that remain: pinned, recurrence > 1, due soon or overdue, technical debt. (FR-42, AC-43)
11. As the CTO, I want the workload page to count open and pinned items only. (FR-43)

### Implementation Decisions

- **Column:** rename `issues.severity` to `issues.priority`, `varchar(16)`, nullable. Values `critical | high | medium | low`. Drop `issues.is_urgent` and the old task `priority smallint` column.
- **Data mapping** (runs on a Phase 1 database):

  | before | priority | side effect |
  |---|---|---|
  | `blocker` | `critical` | `is_release_blocker = true` |
  | `critical` | `critical` | — |
  | `major` | `high` | — |
  | `minor` | `medium` | — |
  | `enhancement` | `low` | — |
  | task `priority` 1/2/3/4 | `critical`/`high`/`medium`/`low` | — |

- **Enum:** `IssueSeverity` becomes `Priority`. Keep no alias.
- **Workflow and services:** delete the urgent clearing rule from `transition()`, the `urgent_flagged` / `urgent_cleared` timeline events, the `InboxEventType.urgent` row from the notification matrix, and the `is_urgent` filter on `GET /issues`. Existing `urgent_*` timeline rows in dev are wiped with the database; a Phase 1 database has none.
- **Triage (06, not yet implemented):** the outcome list loses `accept_urgent`. `accept` requires `priority`, and both `assignee_id` and `release_id` stay optional.
- **Queue (10, not yet implemented):** two groups, pinned and rest. `default_key(item) = (priority_rank, due_date or +∞, -recurrence_count, created_at)` with `priority_rank` = 1..4 from the single field.
- **Policy (04, not yet implemented):** `set_urgent` and `set_severity` disappear; `set_priority` remains.
- **Frontend:** remove the urgent marker, filter, and any urgent copy. The severity badge becomes the priority badge, with one set of labels and colors for both types (`docs/design.md` §3 gets the new scale).

### Testing Decisions

- Update the Phase 1 characterization tests to the new priority values. Their assertions on behavior must not change.
- New: `test_priority_required_on_accept`, `test_task_defaults_to_medium_priority`, `test_new_bug_has_no_priority`.
- Migration test: a Phase 1 fixture with one bug per old severity, upgraded, then asserted against the mapping table above, including the release-blocker side effect.
- Delete every urgent test. Grep for `urgent` in `backend/` and `frontend/src/` must return nothing but unrelated prose.

---

## Part 2 — Table split, timestamps, enum modules, seed

### User Stories

1. As a developer, I want `issues` to hold only fields shared by both types, so that the table stops being half-null. (§8.2)
2. As a developer, I want bug-only fields in `issue_bugs` and task-only fields in `issue_tasks`, linked by `issue_id`.
3. As a developer, I want exactly one meta row per item, created in the same transaction as the item, so that no code has to handle a missing row.
4. As a developer, I want the API response shape unchanged, so that the frontend does not move with the storage.
5. As a developer, I want lifecycle timestamps in `issue_timestamps` as rows, not columns, so that adding an event is data, not a migration.
6. As a developer, I want one row per `(issue_id, kind)` holding the latest occurrence, with the full history staying in `issue_timeline`.
7. As a report reader, I want the same numbers as before, computed from the timestamps instead of stored duration columns. (Phase 1 characterization tests)
8. As a developer, I want the duration logic in one service with its own tests, so that "time to fix" means the same thing everywhere.
9. As a developer, I want one module per side listing every enum value, the named sets, and the predicates, and no status or type string written anywhere else.
10. As a reviewer, I want CI to fail when the two modules disagree.
11. As a developer, I want `make seed` to produce both types across all statuses, in Persian and English, so that every screen has something to show.

### Implementation Decisions

#### Tables

```
issues            id, issue_number, type, project_id, release_id, milestone_id,
                  title, description, status, cancel_reason, blocked_from_status,
                  priority, labels, due_date, backlog_category, backlog_rank,
                  reporter_id, assignee_id, review_requested_by_id,
                  created_at, updated_at, deleted_at, deleted_by_id
issue_bugs        issue_id PK/FK, source, recurrence_count, is_release_blocker,
                  is_regression, regression_count, parent_issue_id,
                  reproduction_steps, curl_command,
                  environment_name, environment_browser, environment_os,
                  environment_build_hash, environment_staging_url
issue_tasks       issue_id PK/FK   (is_tech_debt arrives in 08)
issue_timestamps  id, issue_id FK, kind, occurred_at, actor_id
                  UNIQUE (issue_id, kind); index (issue_id)
```

- `backlog_category` and `backlog_rank` are **shared** (BR-04 puts any type in the backlog); slice 08 fills them.
- `deleted_at` and `deleted_by_id` stay on `issues`: soft delete is a property of the record and every list filters on it.
- `created_at` and `updated_at` stay on `issues`.
- `search_tsv` is untouched here; slice 12 drops it.

#### Timestamps

| kind | written when |
|---|---|
| `filed` | item created |
| `triaged` | bug leaves triage by any outcome |
| `started` | entering In progress |
| `review_requested` | entering In review |
| `verified` | In review → Done (bugs) |
| `completed` | entering Done (both types) |
| `cancelled` | entering Cancelled |

- Written by `IssueService.transition()` and `create()` through one helper, `TimestampService.record(issue, kind, actor, now)`, which upserts on `(issue_id, kind)`. Nothing else writes the table.
- `now` comes from the `get_now` dependency (slice 01), never `datetime.now()`.
- Drop `filed_at`, `triaged_at`, `fixed_at`, `verified_at`, `closed_at`, `started_at`, `completed_at`, `cancelled_at`, and `time_to_triage_h`, `time_to_fix_h`, `time_to_verify_h`. Migrate existing values into rows first: `fixed_at → review_requested`, `verified_at → verified` and `completed`, `closed_at → completed` when `verified_at` is null.
- **Durations** live in `app/services/duration_service.py`: `time_to_triage = triaged - filed`, `time_to_fix = completed - triaged`, `time_to_verify = verified - review_requested`, returned in hours, `None` when either end is missing. Every report, the dashboard, contributions, and the profile page call it. No SQL in any other module subtracts two timestamps.

#### ORM

- `Issue.bug` and `Issue.task`: `relationship(uselist=False, lazy="joined", cascade="all, delete-orphan")`. List endpoints that need only shared fields use `lazy="noload"` explicitly on the query.
- `IssueService.create()` creates the item and its one meta row in the same transaction, from a `type`-keyed factory. There is one place that decides which meta class to build.
- Responses stay flat: `IssueResponse` reads through the relationship, so the JSON does not change. Add a serializer test proving the shape is byte-identical for one bug and one task.

#### Enum modules

- `backend/app/domain/enums.py`: `IssueType`, `IssueStatus`, `Priority`, `CancelReason`, `TimestampKind`, `ProjectKind`, `Role`; the sets `TRIAGE_STATUSES`, `BOARD_STATUSES`, `OPEN_STATUSES`, `FINAL_STATUSES`, `CANCELLABLE_FROM`; and the predicates `is_open(status)`, `is_final(status)`, `is_board(status)`, `can_cancel(status)`, `requires_priority(status)`. Workflow, Policy, services, and routes import from here. No module writes a literal `"in_progress"`.
- `frontend/src/lib/domain.js`: the same values, sets, predicates, plus the display labels and colors. `lib/constants.js` re-exports from it so existing imports keep working. No component writes a status string.
- **Parity test** `backend/tests/test_enum_parity.py`: reads `frontend/src/lib/domain.js`, extracts the arrays with a regex, and compares sets with the Python enums. It fails with a message naming the missing value and the side it is missing from.
- A grep guard in the same test: no file under `backend/app/` or `frontend/src/` outside the two modules contains a quoted status or priority value. Allow a short exception list (migrations, seeds, tests, `mockData.js`).

#### Migrations

- Rewrite the Phase 2 revisions (from slice 02 onward) so a Phase 1 database reaches the final shape through them, and squash where that makes the chain simpler. Every revision keeps a working `downgrade`, except that dropped derived columns come back empty.
- Order inside the chain: statuses → priority (Part 1) → tables and timestamps (Part 2).
- Dev databases are rebuilt: `make db-reset` (drop, create, `upgrade head`, `seed`). Add the target if it does not exist.
- **Before merging:** restore a production dump into a scratch database, run `alembic upgrade head`, and check row counts per table, the priority mapping, and one report's numbers before and after. Write the result in the PR.

#### Seed

`backend/scripts/seed.py` is rewritten. It wipes first, so it is idempotent:
- one user per role that exists at this point (qa, developer, cto, admin)
- two Product projects with a release each, one Internal project, one General project, each with a triage lead
- bugs: several New with no priority, some across the board statuses, one Done with a regression, one Cancelled with a reason, one hotfix with no release
- tasks: across the board statuses, several in the backlog with no release or milestone, each priority represented
- consistent `issue_timestamps` rows for every item's history
- public comments and internal notes on several items
- titles and descriptions mixed Persian and English, so search and RTL layout have real data

### Testing Decisions

- Migration tests on a Phase 1 fixture: every dropped column's data appears in `issue_timestamps`; row counts match; the priority mapping holds; `upgrade head` then `downgrade -1` runs clean.
- `DurationService` unit tests: missing ends, a regression that re-enters In progress (latest occurrence wins), and equality with the Phase 1 values for a fixed fixture.
- Serializer test: one bug and one task produce exactly the pre-refactor JSON.
- `test_enum_parity` and the literal-grep guard.
- Phase 1 characterization tests keep passing with no assertion changes beyond the priority rename.
- A query test proving a list endpoint does not join the meta tables when it does not need them (assert on the emitted SQL with `sqlalchemy` event capture).

---

## Out of Scope

- Nested API responses (`{bug: {...}}`). Deliberately not done; the storage split must not reach the API.
- Any new behavior. This is a refactor plus one removal.
- `search_tsv`, `issue_embeddings`, and the search engine (slice 12).
- Polymorphic ORM inheritance.

## Further Notes

- Slices 04–14 were written before this refactor. Their updated texts are already in this folder; if a slice was implemented before the update, apply its delta from the v2.2 table in [00-README.md](00-README.md).
- Keeping `verified` and `completed` as separate kinds is deliberate: Phase 1 reports need "time to verify" separately, and tasks never get `verified`.

---

## Prompts

**Session 1 — Part 1:**

```
Implement Part 1 of docs/specs/phase-2/03a-data-model-refactor.md (remove Urgent, unify
severity and priority).
Read docs/specs/phase-2/00-README.md first, then 03a, then the PRD sections it cites.
The code already implements slices 01–03; read it before changing it and keep the existing
patterns. Work test-first at the seams from 01-test-harness.md: update or write the failing
tests, make them pass, then the UI. Rewrite the Phase 2 migrations rather than adding new
ones; dev data may be dropped. Run `make test` and `make lint` before finishing. Do not
start Part 2.
```

**Session 2 — Part 2:**

```
Implement Part 2 of docs/specs/phase-2/03a-data-model-refactor.md (split issues into
issue_bugs / issue_tasks, move lifecycle timestamps into issue_timestamps, add the enum
modules with the parity test, rewrite the seed).
Read docs/specs/phase-2/00-README.md first, then 03a. Part 1 must already be merged.
The API response shape must not change: prove it with a serializer test before you start
moving columns. Rewrite the Phase 2 migrations to land on the final shape; dev data may be
dropped, but the migrations must also carry a Phase 1 production database forward, so test
them against a restored production dump and report the result. Run `make test` and
`make lint` before finishing.
```
