# 08a — Rework for PRD v3: Containers, Cycles, QA Gate

> **Depends on:** 08 (already implemented) · **Replaces parts of:** 02, 03, 03a, 04, 06, 07, 08 · **PRD:** [v3](prd-v2.md) §0, §7.3, §8.1, §8.2, §8.7, §8.9, §9, FR-03, FR-05, FR-16, FR-18, FR-23, FR-25, FR-55–FR-66, BR-03–06, BR-20, BR-22–24, BR-26, BR-28, BR-29, BR-49, BR-50, BR-51–BR-66; AC-24–27, AC-49–54, AC-55–58, AC-64–78 · **Model:** [cycle-model.md](cycle-model.md)
> **Run this in three sessions**, in order. The prompts are at the bottom. Slice 09 (Releases and Stream) comes after all three.

## Problem Statement

Slices 01–08 are implemented on dev. The product review that followed (PRD v3) changed the model underneath them:

1. **Milestones and project kinds are gone.** Every project has one **Stream** (always open, each item ships on its own) and any number of **Releases**. 03 built project kinds and a seeded General project; 03a added `issues.milestone_id`.
2. **Hotfix is not a concept.** 03 and 06 built "accept with no release" as the hotfix path; 08 then turned "no release" into the backlog. In v3, urgent work is an item in the Stream.
3. **One QA gate for bugs and tasks.** 03 allowed tasks `in_progress → done`. 02 sent a failed verification back to In progress. In v3 every item passes In review, and every return goes to **To do**.
4. **Regressions become cycles.** 02 built a release-only regression action and 06 a merge regression, both writing `regression_history` and bug-only counters. In v3, every return (reject, release QA, production, merge into Done) starts a new **cycle** with a `start_reason`, for bugs and tasks. Phase 1's `record_regression` also credits the fix to whoever changed the status, not to the person who did the work.
5. **Backlog items cannot be started.** Placement comes first.

## Solution

- **Part 1 — Containers.** Remove project kinds and `milestone_id`. Add `releases.kind` and create one Stream per project. Map release statuses to the v3 lifecycle values. Placement everywhere means Backlog, Stream, or a Release. Done items never move.
- **Part 2 — Cycles.** Rebuild `issue_cycles` per the cycle model in place of `regression_history`, drop the regression counters, add `issues.current_cycle_id`, and route every cycle change through one `CycleService`. Phase 1 reports read cycles and keep their numbers.
- **Part 3 — QA gate and returns.** Change the Workflow rows, replace the regression action with returns, rewrite `MergeService` status effects, allow merges into tasks, add the returned marker and notification, and forbid bulk status changes.

Phase 2 is not in production and was mid-development when v3 was decided. **No data migration is part of this slice.** Rewrite the Phase 2 migrations so they land directly on the v3 shape (as 03a did), rebuild dev databases with `make db-reset`, and rewrite the seed. Every Alembic revision still needs a working `downgrade`.

---

## Part 1 — Containers

### User Stories

1. As an admin, I want every project to follow one model with no kind to choose, so that projects are configured the same way. (§8.1, BR-02 removed)
2. As a user, I want every project to have exactly one Stream, created with the project, so that continuous work always has a home. (BR-51, AC-55)
3. As a user, I want the Stream to be impossible to rename, cancel, archive, or delete. (FR-46)
4. As a user filing an item or accepting a bug, I want to choose Backlog, Stream, or an open Release, so that placement is one decision. (FR-03, FR-18)
5. As a PM, I want to bulk-move backlog items to the Stream or a Release. (FR-25)
6. As a user, I want a Done item to be impossible to move to another container, so that "on production" never changes after the fact. (BR-54, AC-58)
7. As a user, I want the release blocker flag available only on bugs in a Release, not in the Stream. (BR-58, AC-65)
8. As a CTO, I want Phase 1 release lists, the release switcher, and reports to show releases only, never the Stream, so that Phase 1 screens keep their meaning.

### Implementation Decisions

- **Projects:** drop `projects.kind`, `ProjectKind` from both enum modules, the `project_kind` and `has_release` filters on `GET /issues` (replaced by `container=backlog|stream|<release_id>`), the Kind select in the project modals, and the codes `releases_not_allowed` and `project_has_releases`. The General project that 03 seeded stays as an ordinary project in dev databases if it exists; it is no longer seeded.
- **`releases.kind`**: `stream | release`, non-null, default `release`. Add `ReleaseKind` to both enum modules.
  - Unique partial index: one `kind = stream` row per project.
  - `ProjectService.create` creates the Stream in the same transaction as the project.
  - Any edit, status change, archive, or delete of a Stream returns 409 `code: stream_immutable`.
- **Release status values** become `planning | development | qa | released | cancelled` (`ReleaseStatus` in both enum modules), replacing `active | released | blocked | archived`. `blocked` is no longer a status: a blocked release is a release in QA with a **no-go** decision (`go_nogo_status` is unchanged). Add `releases.code_freeze_date` (date, nullable) and `releases.released_at` (timestamptz, nullable). `target_date` keeps its column and becomes the target ship date. The lifecycle transitions, ship, cancel, progress, and overdue are built in **09**; until then, keep the existing release status controls working with the new values.
- **Drop `issues.milestone_id`** (03a) and every reference to milestones in code, enum modules, seeds, and tests.
- **Placement stays one column.** `issues.release_id` is the container id: a Stream row, a Release row, or null for the backlog. `IssueCreate`, triage `accept`, `PATCH /issues/{id}`, and `POST /issues/bulk-move` accept any container of the item's project. A Release in `released` or `cancelled` is refused (`code: release_closed`).
- **Done items never move:** any change to `release_id` on a `done` item returns 409 `code: done_item_immobile`, including bulk move (the whole request fails, per 08).
- **Release blocker:** setting it on a bug whose container is not `kind = release` returns 409 `code: release_blocker_release_only`. Moving a bug with the flag out of a Release clears the flag and writes a timeline event.
- **Backlog:** the predicate from 08 loses its milestone clause and is otherwise unchanged (`release_id is null`, board status, not done or cancelled). `backlog_category` includes `default` (already in the code); items moved to the backlog by ship (09) get `default`.
- **Phase 1 release screens:** every release list, `ReleaseSwitcher`, `ReleasesPage`, dashboard, go/no-go, and every report query filters `kind = release`. The Stream appears only in placement pickers here; its page is built in 09.
- **Policy (04):** remove `manage_milestones` and the project kind from the target snapshot.
- **Frontend:** one container picker component (Backlog / Stream / open releases) used by the create form, triage accept, the item sidebar, and the backlog bulk bar. Remove the milestone picker and chip if any exist, and the project Kind select.
- **Seed:** rewrite `seed.py` for the v3 shape: each project with its Stream and one or two releases in different lifecycle states, items in the Stream, in releases, and in the backlog.

### Testing Decisions

- `test_ac_55_project_has_one_immutable_stream`
- `test_ac_58_done_item_cannot_change_container`
- `test_ac_65_release_blocker_unavailable_in_stream`
- A project create creates exactly one Stream; a second Stream insert fails.
- Placement: create, accept, PATCH, and bulk move each accept the Stream and an open Release, refuse a released or cancelled Release, and refuse another project's container.
- `make db-reset` builds the v3 schema from an empty database; `upgrade head` then `downgrade -1` runs clean.
- Phase 1 characterization tests keep their numbers; release lists and reports never include the Stream.

---

## Part 2 — Cycles

### User Stories

1. As a CTO, I want every return of work recorded as a cycle with where it was caught, for bugs and tasks. (§8.9, cycle model)
2. As a developer, I want the fix I did credited to me even when the CTO or an admin moved the status. (BR-63, AC-69)
3. As a developer, I want an unassigned item's delivery credited to nobody rather than to whoever moved it. (AC-70)
4. As a PM, I want an item moved to the backlog to lose its cycles, so that re-planned work starts clean. (BR-62, AC-73)
5. As a CTO, I want Phase 1 release, regression, fragility, dashboard, and contributions numbers unchanged after the move to cycles. (PRD §14)
6. As a user, I want the item page to show the item's cycles: when each started and why, who delivered it, when it was verified. (FR-66)

### Implementation Decisions

- **Schema** exactly as [cycle-model.md §6](cycle-model.md#6-data-model):
  - `issue_cycles`: add `release_id` (not null), `start_reason`, `start_comment_id`, `start_merged_issue_id`, `start_by_id`, `delivered_by_id`, `picked_up_at`, `submitted_at`, `closed_at`; rename `cycle_start_at` to `started_at`; drop `regression_history_id`, `triaged_at`, `fixed_at` (→ `submitted_at`), and the per-cycle `time_to_*_h` columns (durations come from `DurationService`, 03a).
  - `issues.current_cycle_id`: nullable FK. Invariant: null exactly when `release_id` is null. Enforce it in the service and cover it with tests; a check constraint is optional.
  - Drop `issue_bugs.is_regression`, `issue_bugs.regression_count`, and the table `regression_history`.
  - `CycleStartReason` (`planned | review | release_qa | production`) in both enum modules.
- **`CycleService`** is the only writer of `issue_cycles` and `issues.current_cycle_id`. `IssueService` calls it; nothing else does.
  - `on_placed(issue, actor)`: the item gets a container and has no current cycle → start cycle 1 with `planned`. Called from create (with a container), triage accept (with a container), and any move from the backlog into a container.
  - `on_container_changed(issue)`: container → container while the cycle is open → update the current cycle's `release_id`.
  - `on_moved_to_backlog(issue)`: delete all of the item's cycles and clear `current_cycle_id` (clear the pointer first, then delete).
  - `on_status(issue, from, to, actor, now)`: first `in_progress` in the cycle sets `picked_up_at`; `in_review` sets `submitted_at` and snapshots `delivered_by_id = issue.assignee_id` (never the actor); `done` from `in_review` sets `verified_at`; `cancelled` sets `closed_at`.
  - `start_return(issue, reason, actor, comment_id, merged_issue_id=None)`: close the current cycle, insert cycle N+1 with the reason, move `current_cycle_id`. Used by Part 3.
  - Reassignment keeps updating `issue_cycles.assignee_id` as in Phase 1; attribution reads only `delivered_by_id`.
- **Until Part 3 lands**, the existing regression action and merge regression call `start_return` with `review` (from In review) or `release_qa` (from Done), so the app stays shippable between sessions.
- **Delete `RegressionService.record_regression`** and its actor-based `previous_fix_by_id`. "Whose work came back" is `delivered_by_id` of cycle N − 1.
- **Phase 1 reports** (`report_service.py`, `RegressionService.get_component_fragility`, release report, `get_regressions`, dashboard, contributions, `schemas/report.py`, `tasks/reports.py`, `telegram/handlers.py`): read `issue_cycles` where `start_reason in (review, release_qa)`, the item is a bug, and the cycle's container has `kind = release`. That is exactly the set Phase 1 recorded, so the numbers do not change. Fragility attributes a cycle to the container of cycle N − 1.
- **API:** `GET /issues/{id}/cycles` returns the cycle list. `IssueResponse` replaces `is_regression` / `regression_count` with `cycle_count` and `returned: null | {reason, number, comment_id}` (computed from the current cycle: `start_reason <> planned` and `submitted_at is null`; `number = cycle_no − 1`). Keep list endpoints to one PK join for this.
- **Frontend:** `RegressionTimeline` becomes a cycle history on the item page. Remove regression badges and counters; the returned marker is Part 3.
- **Migrations:** rewrite the Phase 2 revisions so `issue_cycles` is created in its v3 shape and `regression_history`, `is_regression`, and `regression_count` never reach head. No data is carried over; dev databases are rebuilt.

### Testing Decisions

- `test_ac_69_delivered_by_is_assignee_not_actor`
- `test_ac_70_unassigned_delivery_has_no_author`
- `test_ac_73_backlog_move_deletes_cycles_and_replacement_restarts_at_one`
- `test_ac_78_bug_filed_into_release_has_planned_cycle_in_triage`
- Placement from the backlog starts cycle 1 `planned`; a move Stream → Release updates the open cycle's container; a Done item's cycle container never changes.
- Invariant test over every mutation path: `current_cycle_id is null` ⇔ `release_id is null`.
- Report fixture test: a fixed fixture with rejects in review and returns from release QA in releases, plus returns in the Stream and task cycles; every Phase 1 report returns the numbers it returned for the equivalent Phase 1 regressions, and Stream or task cycles do not change them.
- The Phase 1 characterization suite passes with only field-name changes (`regression_count` read from cycles).

---

## Part 3 — QA gate and returns

### User Stories

1. As a developer, I want a backlog item's In progress control disabled with "Place this item in the Stream or a release first." (FR-58, BR-53, AC-56)
2. As a developer, I want every task to pass In review like a bug, with no direct In progress → Done. (BR-29, AC-57)
3. As a QA engineer, I want to **reject** delivered work with a required comment, sending it to To do. (FR-57, AC-66, AC-67)
4. As a tech user, I want to **return from release QA** a Done item in a Release that has not shipped, with a required comment. (FR-59, AC-25)
5. As a tech user, I want **Problem on production** on a shipped item, with a required comment, sending it to To do and, if its release is Released, to the Stream. (FR-60, AC-26, AC-64, AC-72)
6. As a Support user, I want no Problem on production control; I report a new problem and triage merges it. (AC-71)
7. As a triager, I want to merge a report into a **task** as well as a bug. (FR-18, BR-20, AC-77)
8. As a triager, I want a merge into a Done item to send it back to To do with the right reason, and a merge into any other status to leave it alone. (BR-49, AC-49–54)
9. As an assignee, I want a returned item marked on rows and cards until I send it to review again, with the reason on hover. (FR-63, AC-67, AC-68)
10. As an assignee, I want a notification with the reason comment when my item is returned. (FR-65)
11. As a user, I want no screen or endpoint that changes the status of several items at once. (FR-62, BR-60, AC-76)

### Implementation Decisions

- **Workflow rows** (replacing the 02 and 03 rows where they conflict; the same for both types unless noted):

  | From | To | Condition |
  |---|---|---|
  | todo | in_progress | Item has a container (`code: needs_container`) |
  | in_progress | in_review | — |
  | in_review | done | Verify. Actor ≠ `review_requested_by_id` (`code: self_verification`, Policy) |
  | in_review | todo | **Reject.** `comment` required (`code: reason_required`). Starts cycle `review` |
  | done | todo | **Return only**, via `POST /issues/{id}/returns` or `MergeService`. `/transition` refuses it with `code: use_return` |
  | todo, in_progress, in_review | blocked | Records `blocked_from_status` |
  | blocked | `blocked_from_status` or todo | — |
  | bug: new, needs_info, todo, blocked · task: any non-done | cancelled | Reason rules from 02 and 03 |

  Removed rows: task `in_progress → done`; `in_review → in_progress` (verify fail); the regression action `done, in_review → in_progress`; the merge regression `done → in_progress`.
- **Returns endpoint:** `POST /issues/{id}/returns` with `{comment}` (non-empty; 422 otherwise). The server decides the reason, never the client:
  - container `kind = release` and release not `released` → `release_qa`, item stays in the release;
  - otherwise (Stream, or Released release) → `production`; if the container is a Released release, move the item to the Stream (`on_container_changed`).

  Then `transition(done → todo)` and `CycleService.start_return`. Only from `done`; otherwise 409 `code: not_done`.
- **Reject** goes through `POST /issues/{id}/transition {to: todo, comment}` from `in_review`; it writes the comment as a public timeline comment, then `start_return(review, comment_id)`.
- **Remove** `POST /issues/{id}/regression`. Phase 1 wrappers: `/verify` with a fail result maps to reject (comment required); `/reopen` maps to `/returns`.
- **Policy (04):** `transition:todo` from `in_review` (reject) for QA, Developer, PM, CTO, Admin; new action `return_item` for the same roles, never Support; remove the "Regression action" flag row. Support never receives `return_item` in `allowed_actions`.
- **MergeService (06)**, status effects by the original's status (BR-49):

  | Original | Effect |
  |---|---|
  | new, needs_info, todo, in_progress, in_review, blocked | none |
  | done, not shipped | `done → todo`, `start_return(release_qa, comment_id, merged_issue_id)` |
  | done, shipped | `done → todo`, `start_return(production, …)`; if the container is a Released release, move to the Stream |
  | cancelled | none; `recurrence_on_cancelled` to the triage lead |

  - `recurrence_count += 1` only when the original is a bug.
  - The Duplicate outcome's `duplicate_of_id` may be a bug or a task in the same project (BR-20). `duplicate_of_duplicate` still applies.
  - Drop the `source_release_id` parameter.
- **Recurrence (07):** unchanged (bugs only, refused on Done). Update the FR-16 text: "Fixed items can't take a recurrence. File a new report; triage will merge it into this item and send it back for a fix."
- **Notifications:** new `InboxEventType.item_returned` to the assignee, meta `{reason, cycle_no, comment_id}`, replacing the Phase 1 regression notification. Telegram template names where it was caught and quotes the comment. Support receives nothing for a return (06's rule already drops Support from other events).
- **Bulk status:** remove any endpoint or UI that changes status for several items. `POST /issues/bulk-move` stays; it changes placement only.
- **Timestamps (03a):** tasks now receive `review_requested` and `verified` too. `DurationService` is unchanged.
- **Frontend:**
  - Reject dialog (comment required) wherever verify is offered; Return from release QA and Problem on production dialogs (comment required) on Done items, driven by `allowed_actions` and `blocked_actions`.
  - Returned marker on `IssueTable` rows and `IssueBoard` cards: reason, "returned N", reason comment on hover. `WorkItemCard` (10) adopts it.
  - The disabled In progress control on backlog items with the FR-58 hint.
  - Update `docs/design.md` §3 with the marker.

### Testing Decisions

- Named ACs: `test_ac_24_stream_bug_verified_is_done`, `test_ac_25_return_from_release_qa`, `test_ac_26_problem_on_production_in_stream`, `test_ac_27_reviewer_cannot_verify_own_work`, `test_ac_49`…`test_ac_54` rewritten per PRD v3, `test_ac_56_backlog_item_cannot_start`, `test_ac_57_task_cannot_skip_review`, `test_ac_64_production_return_moves_to_stream`, `test_ac_66_reject_requires_comment`, `test_ac_67_reject_returns_to_todo_with_marker_and_notification`, `test_ac_68_marker_lasts_until_in_review`, `test_ac_71_support_has_no_production_action`, `test_ac_72_production_return_requires_comment`, `test_ac_76_no_bulk_status_endpoint`, `test_ac_77_merge_into_done_task_in_stream`.
- The returns endpoint decides the reason server-side: the same request on a Done item in an unshipped Release yields `release_qa`, on the Stream `production`.
- Workflow table tests from 02 and 03 are rewritten for the new rows; every removed row has a refusal test.
- Phase 1 characterization tests: a failed verification now lands in `todo` instead of `in_progress`. This is the only allowed assertion change; report numbers stay the same.

---

## Out of Scope

- Release lifecycle transitions, ship, cancel, go/no-go UI, release page, progress, overdue, and the Stream page (09).
- The personal queue rule for returned items (10).
- Every new report (Phase 3).

## Further Notes

- Slices 09–14 were rewritten for v3 and need no delta. For 02–08, this slice is the delta; their own texts are kept as the record of what was built.
- The hotfix report planned in 11 is dropped. "Hotfix" is no longer a term.

---

## Prompts

**Session 1 — Part 1:**

```
Implement Part 1 of docs/specs/phase-2/08a-release-stream-cycles.md (containers: remove
project kinds and milestone_id, add releases.kind with one Stream per project, map release
statuses, placement = backlog / stream / release, Done items never move).
Read docs/specs/phase-2/00-README.md first, then 08a, then PRD v3 (prd-v2.md) sections it
cites. The code implements slices 01–08; read it before changing it and keep its patterns.
Work test-first at the seams from 01-test-harness.md. Rewrite the Phase 2 migrations to land
on the v3 shape; there is no data migration, and dev databases are rebuilt with
`make db-reset`. Run `make test` and `make lint` before finishing. Do not start Part 2.
```

**Session 2 — Part 2:**

```
Implement Part 2 of docs/specs/phase-2/08a-release-stream-cycles.md (cycles: rebuild
issue_cycles per cycle-model.md §6 in place of regression_history, add
issues.current_cycle_id and CycleService, port Phase 1 reports to cycles).
Read docs/specs/phase-2/00-README.md, then 08a, then cycle-model.md. Part 1 must already be
merged. Before changing any report, capture the Phase 1 report numbers for a fixed fixture
and prove they are unchanged afterwards. Rewrite the migrations; there is no data
migration. Run `make test` and `make lint` before finishing. Do not start Part 3.
```

**Session 3 — Part 3:**

```
Implement Part 3 of docs/specs/phase-2/08a-release-stream-cycles.md (QA gate and returns:
new Workflow rows, the returns endpoint, reject with comment, MergeService effects for Done
items and task targets, the returned marker, the item_returned notification, no bulk status
changes).
Read docs/specs/phase-2/00-README.md, then 08a, then PRD v3 §9, §10.14 and BR-49. Parts 1
and 2 must already be merged. Work test-first at the API seam; every PRD acceptance
criterion cited in Part 3 needs a test named after it. Run `make test`, `make e2e`, and
`make lint` before finishing.
```
