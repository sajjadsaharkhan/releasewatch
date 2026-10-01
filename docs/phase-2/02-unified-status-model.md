# 02 — Unified Status Model

> **Depends on:** 01 · **PRD:** §9 (statuses, flags, transitions), BR-10, BR-13, BR-14, BR-24, BR-25, BR-28; AC-25, AC-26, AC-27
> **Bugs only in this slice.** Tasks arrive in 03 and reuse everything built here.
> **v2.2:** severity is replaced by the shared `priority` scale and the `time_to_*` columns move to `issue_timestamps` — see [03a](03a-data-model-refactor.md). Where this slice says severity, read priority.
> **v2.1:** a second path from Done back to In progress, the **merge regression**, is added by 06 (PRD BR-49). This slice only reserves the Workflow row.

## Problem Statement

Phase 1 bugs move through `new → triaged → in_progress → fixed → verified → closed`, with `regression` and `blocked` as statuses. "Needs clarification" is faked by setting `blocked` and reassigning the bug to its reporter. Nothing validates transitions: `PATCH /issues/{id}` accepts any status. Phase 2 needs one status set that bugs and tasks share, so that boards, the personal queue, and reports can mix both types, and it needs an enforced workflow so the new rules (verification, cancel reasons, regression only in releases) actually hold.

## Solution

Replace the Phase 1 status set with the unified set from PRD §9. Migrate existing rows. Introduce a single pure **Workflow** module that decides every transition. Every status change, whether from an action endpoint, a board drag, or PATCH, goes through `IssueService.transition()`, which asks Workflow first. Regression and release blocker stop being statuses and become flags. The UI renders only the transitions the API says are allowed.

## User Stories

1. As a developer, I want every bug to show one of: New, Needs info, To do, In progress, In review, Done, Blocked, Cancelled, so that the status vocabulary is the same everywhere.
2. As a developer, I want the board to show exactly five columns (To do, In progress, In review, Done, Blocked), so that bugs and, later, tasks share one board.
3. As a triager, I want New and Needs info bugs kept off boards, so that untriaged work does not look committed.
4. As a developer, I want to move a bug I'm working on from To do to In progress, so that others see I've started.
5. As a developer, I want to move a bug from In progress to In review when my fix is ready, so that QA knows to verify it.
6. As a QA engineer, I want to verify a bug in In review, moving it to Done, so that fixed work is closed.
7. As a QA engineer, I want to fail a verification, sending the bug back to In progress, so that incomplete fixes return to the developer.
8. As a developer, I want to be prevented from verifying a bug that I moved to In review myself, so that nobody signs off their own fix. (AC-27)
9. As a developer, I want the verify control shown disabled with the reason when I moved the bug to review, so that I understand why I can't click it.
10. As any tech user, I want to mark a bug Blocked from any board status except Done, so that stuck work is visible.
11. As any tech user, I want to unblock a bug back to the status it was in before, or to To do, so that the bug's progress isn't lost.
12. As a triager, I want to cancel a bug from New, Needs info, To do, or Blocked, with a required reason, so that closed-without-fix work always says why. (BR-13)
13. As a team member, I want cancel reasons limited to User error, Expected behavior, Cannot reproduce, Duplicate, and Won't fix, so that reasons can be reported on.
14. As a QA engineer, I want to flag a regression on a Done or In review bug in a release that has not shipped, sending it back to In progress with its regression count incremented, so that Phase 1 regression tracking continues. (BR-24, AC-25)
15. As a QA engineer, I want the regression action unavailable on bugs with no release or in a shipped release, so that regressions stay scoped to releases. (AC-26)
16. As a user, I want an invalid status change rejected with the list of allowed next statuses, so that I know what I can do. (BR-14)
17. As a user dragging a card to a column it can't go to, I want the drop refused and the card returned with a toast giving the reason, so that the board never shows a false state.
18. As a CTO, I want existing Phase 1 bugs migrated into the new statuses without losing history, so that dashboards and reports stay correct.
19. As a CTO, I want existing "needs clarification" bugs to appear as Needs info with their previous assignee restored, so that the old workaround disappears cleanly.
20. As a CTO, I want existing duplicate-closed bugs to appear as Cancelled with reason Duplicate, so that duplicates are no longer counted as fixed.
21. As a CTO, I want release reports, regression reports, the dashboard, and contributions to show the same numbers as before for unchanged meanings, so that the migration can be trusted.
22. As a user, I want one priority scale (Critical, High, Medium, Low) for both types. (v2.2; Phase 1 `blocker` becomes Critical plus the release-blocker flag, `enhancement` becomes Low — see 03a)
23. As a triager, I want priority to be empty on a New bug nobody has rated yet, so that the system doesn't pretend a default is a judgement.
24. As a user, I want the timeline to record every status change with from, to, actor, and reason, so that history stays complete.

## Implementation Decisions

### Status set and flags

- `IssueStatus` becomes `new, needs_info, todo, in_progress, in_review, done, blocked, cancelled`. Column type is unchanged (`String(32)`).
- **Board statuses:** `todo, in_progress, in_review, done, blocked`. **Triage statuses:** `new, needs_info`. **Terminal:** `cancelled` (and `done`, apart from the regression path).
- New columns on `issues`:
  - `cancel_reason` — nullable string enum: `user_error, expected_behavior, cannot_reproduce, duplicate, wont_fix, no_longer_needed`. `no_longer_needed` is used by tasks from 03.
  - `blocked_from_status` — nullable. Set on entering `blocked` and cleared on leaving it.
  - `review_requested_by_id` — nullable FK to users. The user who moved the item to `in_review`. Cleared on leaving `in_review` backward.
  - `started_at`, `completed_at`, `cancelled_at` — timestamps.
- `is_regression`, `regression_count`, and `is_release_blocker` already exist and become the PRD's flags unchanged. `IssueStatus.regression` is removed.
- `severity` becomes nullable (D4) and, per 03a, is renamed to `priority` with the values `critical|high|medium|low`.

### Workflow module (pure)

The single source of transition rules. Inputs: item type, current status, target status, and a context of plain values (actor id, `review_requested_by_id`, `blocked_from_status`, has release, release shipped, and so on). Output: allowed, or refused with a `code` and the allowed set. It also exposes `allowed_targets(type, status, context)` for the API to return as `allowed_transitions`.

Bug transitions (tasks are added in 03):

| From | To | Condition |
|---|---|---|
| new | todo | Only through the triage accept outcome (endpoint in 06; the Phase 1 triage endpoint maps here in this slice) |
| new | needs_info | Only through the triage needs-info outcome (06; the Phase 1 needs-clarification endpoint maps here in this slice) |
| new, needs_info, todo, blocked | cancelled | `cancel_reason` required |
| needs_info | new | Reporter or Support comment (auto-return, wired in 06) or a triager |
| todo | in_progress | — |
| in_progress | in_review | Records `review_requested_by_id` |
| in_review | done | Verify pass. Actor ≠ `review_requested_by_id` (`code: self_verification`) |
| in_review | in_progress | Verify fail |
| todo, in_progress, in_review | blocked | Records `blocked_from_status` |
| blocked | `blocked_from_status` or todo | — |
| done, in_review | in_progress | **Regression action only.** Requires a release that has not shipped (release `status` not in `released, archived`) |
| done | in_progress | **Merge regression only** (v2.1): `reason == 'merge_regression'`, no release condition. Reachable only from 06's `MergeService`; `/transition` refuses it with `code: use_triage`. Add the row in 06 |

Every other pair is refused with `code: invalid_transition` and `allowed`.

### Service and API

- `IssueService.transition(db, issue, to, actor, *, reason=None, comment=None)` is the only code that writes `issue.status`. It calls Workflow, sets the timestamps above, keeps `IssueCycle` bookkeeping (`fixed_at` on entering `in_review`, `verified_at` on reaching `done` from `in_review`), writes a `status_changed` timeline event with `{from, to, reason}`, and fans out `status_changed`.
- New endpoint `POST /issues/{id}/transition` with body `{to, reason?, comment?}`, used by board drags and status menus.
- New endpoint `POST /issues/{id}/regression`, which calls `RegressionService.record_regression` and then `transition(..., to=in_progress)`. It replaces setting `status=regression`.
- `PATCH /issues/{id}`: a `status` field routes to `transition()`. It never assigns the column directly.
- The Phase 1 action endpoints (`/fix`, `/verify`, `/reopen`, `/triage`, `/needs-clarification`, `/duplicate`) become thin wrappers over `transition()` with the new statuses, so the current UI keeps working through this slice. `/reopen` maps to the regression action when the bug is in an unshipped release, and otherwise returns 409 `code: done_is_final`. `/triage` and `/needs-clarification` are replaced in 06.
- `IssueResponse` gains `allowed_transitions: list[str]`, `blocked_transitions`, and `cancel_reason`.
- Update report queries (`report_service.py`, `releases.py`, `users.py`) to the new statuses. "Open" means not `done` and not `cancelled`. "Fixed" means `in_review` or `done`. "Verified" means `done` reached from `in_review`, which is `verified_at` not null.

### Data migration (one revision, idempotent)

| Old | New | Notes |
|---|---|---|
| new | new | — |
| triaged | todo | — |
| in_progress | in_progress | — |
| fixed | in_review | `review_requested_by_id` = actor of the latest `fixed` timeline event |
| verified | done | `completed_at` = `verified_at` |
| closed, `parent_issue_id` null | done | `completed_at` = `closed_at` |
| closed, `parent_issue_id` set | cancelled | `cancel_reason = duplicate`, `cancelled_at` = `closed_at` |
| regression | in_progress | `is_regression` is already true |
| blocked, latest status-affecting event is `needs_clarification` | needs_info | `assignee_id` restored from that event's `meta.prev_assignee_id`, or null |
| blocked, otherwise | blocked | `blocked_from_status = in_progress` |
| severity `enhancement` | priority `low` (03a) | — |

`downgrade` reverses the mapping where it can. `needs_info` goes back to `blocked`, and `in_review` goes back to `fixed`.

### Frontend

- Rewrite `STATUS` and `OPEN_STATUSES` in `lib/constants.js` for the eight statuses, following `docs/design.md` §3 (status colors). Add them to the design doc's status table in the same change.
- `IssueBoard` renders the five board columns. A drop calls `/transition`. On 409 it reverts the card and shows the API's `detail`.
- `IssueSidebar` and `IssueHeader` render actions from `allowed_transitions`. `IssueResponse` also carries `blocked_transitions: [{to, code, detail}]` for targets that are normally reachable from the current status but refused for this actor or item (for example, `done` refused with `self_verification`). The UI shows those disabled, with `detail` as the tooltip. Slice 04 generalizes this into `allowed_actions` and `blocked_actions` from Policy.
- A cancel dialog with a required reason select.
- Update every file that references old statuses (see the list in the repo search: `IssueBoard`, `IssueMainContent`, `IssueSidebar`, `RegressionTimeline`, `useIssueDetail`, `mockData`, `ContributionsPage`, `DashboardPage`, `ProfilePage`, `ReleaseDetailPage`, `SettingsPage`).
- Seed scripts (`seed.py`, `seed_persian.py`) use the new statuses.

## Testing Decisions

- **Workflow is tested only through the API.** For each row of the table, write one test for the allowed path and one test that the nearest disallowed target returns 409 with the right `code` and `allowed`. Table-driven tests (`pytest.mark.parametrize`) are fine.
- Named AC tests: `test_ac_25_regression_on_done_bug_in_unshipped_release`, `test_ac_26_regression_unavailable_without_release`, `test_ac_27_reviewer_cannot_verify_own_fix`. The AC-26 bug with no release can only be created after 03. Write it here with `pytest.mark.skip(reason="needs slice 03")` and un-skip it in 03.
- `PATCH` with `status` obeys the same rules (regression test for D8).
- **Migration test:** build a Phase 1-shaped dataset at the previous head covering one row per old status plus the duplicate and needs-clarification cases, upgrade, then assert the mapping through the API. Then downgrade and assert that the old statuses return.
- The characterization suite from 01 must pass after its status names are mapped. Its asserted counts must not change.
- **Prior art:** `tests/phase1/` from slice 01.

## Out of Scope

- Tasks and their statuses (03).
- Triage outcomes (accept with placement, duplicate with recurrence, reject reasons UI) (06).
- Priority handling beyond nullability (03, 03a).
- Permission differences between roles for transitions (04). In this slice any authenticated tech user may perform any allowed transition, which matches Phase 1.

## Further Notes

- `Done` is final except through the regression action and, from 06, the merge regression (PRD v2.1 BR-49).
- `closed_at`, `fixed_at`, `verified_at` and the `time_to_*` columns move to `issue_timestamps` and `DurationService` in 03a. Until that refactor lands they stay, because Phase 1 reports and `IssueCycle` depend on them.
- New and Needs info are bug-only statuses (BR-10). Workflow never offers them to tasks; the task rows arrive in 03.
- Component fragility analysis (`RegressionService`) keeps reading only `regression_history`, which is written only by the regression action on release bugs. Hotfixes therefore stay outside it with no extra code (BR-25). Add a test that the **direct regression action** never produces a `regression_history` row for a bug with no release. (From 06, a merge regression can write a row with a null release; fragility and release reports ignore it.)
