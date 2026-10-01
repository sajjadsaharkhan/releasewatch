# 03 — Tasks, Hotfix Placement, Project Kinds

> **v2.2:** this slice is implemented. The Urgent flag it introduced is **removed** and its `priority` is replaced by the shared scale — see [03a-data-model-refactor.md](03a-data-model-refactor.md). Read 03a as the current truth wherever this file mentions urgent or priority; the text below is kept as the record of what was built.

> **Depends on:** 02 · **PRD:** FR-01–05, FR-21, FR-22, BR-01–03, BR-07–09, BR-11, BR-12, BR-26, BR-27, BR-29; §8.1, §8.2; AC-24
> Backlog category and milestones are added later (08, 09). In this slice, placement is "a release, or none".

## Problem Statement

Everything in Releasewatch today is a bug filed against a release. `issues.release_id` is `NOT NULL`. Small bugs, hotfixes, development tasks, and infrastructure work have nowhere to live, so they end up in Telegram and personal notes. The organization wants every piece of technical work in one place.

## Solution

Add a **type** to work items (bug or task), with type-specific fields. Make the release optional so a bug can be fixed and shipped without one (the hotfix path). Add an optional **due date** (v2.2: the Urgent flag this slice added is removed in 03a). Give projects a **kind** (Product, Internal, General) so infrastructure and operations work has a home, and seed a General project. One creation form with a type selector files either type.

## User Stories

1. As a developer, I want to create a task from the same form I use for bugs, by switching a type selector, so that I don't have to learn a second form. (FR-01)
2. As a developer, I want switching type in the form to show and hide type-specific fields instantly, so that the form stays short.
3. As a developer, I want a task to start in To do, so that tasks skip triage. (FR-05, BR-12)
4. As a developer, I want every bug I file to start in New and appear in its project's triage queue, even if I file it myself, so that all bugs get one triage decision. (FR-04, BR-11)
5. As a developer, I want to set a task's priority from P1 to P4, so that tasks can be ranked like bug severity. (BR-09)
6. As a developer, I want bug-only fields (severity, reproduction steps, cURL, environment, release blocker, regression) hidden on tasks, so that tasks stay simple. (BR-08)
7. As a developer, I want an item's type to be fixed once it's created, so that history and fields never mix. (BR-07)
8. As a developer, I want to move a task through To do → In progress → In review → Done, or straight from In progress to Done when no review is needed. (BR-29)
9. As a developer, I want to cancel a task that is no longer needed, with reason "No longer needed", so that dropped work is recorded.
10. As a developer, I want to block and unblock a task like a bug, so that the board behaves the same for both types.
11. As a developer, I want to file a bug with no release, so that small fixes shipped directly to production are tracked. (BR-26)
12. As a QA engineer, I want to verify a bug that has no release and move it to Done, so that hotfixes are closed properly. (FR-21)
13. As a triager, I want to mark an item Urgent, so that the assignee knows it must be handled before anything else.
14. As an assignee, I want to be notified when an item assigned to me is marked Urgent.
15. As a team member, I want the Urgent flag to clear by itself when the item reaches Done or Cancelled, so that it never lingers. (FR-22, BR-27, AC-24)
16. As a PM, I want to set an optional due date on any item, so that time-bound work is visible.
17. As an admin, I want to set a project's kind to Product, Internal, or General, so that non-product work has a proper home. (§8.1)
18. As an admin, I want only Product projects to accept releases, so that Internal and General projects stay release-free. (BR-02)
19. As any tech user, I want a seeded General project available from day one, so that work with no obvious home can be filed immediately. (FR-02)
20. As a user, I want an item's release to always belong to the item's project, so that data can't cross projects. (BR-03)
21. As a user, I want to see keys like `BUG-123` and `TASK-124`, so that I can tell an item's type from its key.
22. As a user, I want old `issue-123` links to keep working, so that links in Telegram history don't break.
23. As a user, I want the All Issues list, search, and exports to include tasks, with a type filter, so that I can find any work item.
24. As a user, I want a type icon on every row and card, so that bugs and tasks can be told apart at a glance.

## Implementation Decisions

### Schema

- `issues.type`: `bug | task`, non-null. The migration defaults existing rows to `bug`.
- `issues.release_id`: becomes nullable (D7). The FK `ON DELETE CASCADE` changes to `SET NULL`, so deleting a release never deletes work items.
- `issues.priority`: `SmallInteger` 1–4, nullable. Required for tasks, null for bugs.
- `issues.is_urgent`: bool, default false.
- `issues.due_date`: `Date`, nullable.
- `projects.kind`: `product | internal | general`. The migration defaults existing projects to `product`. The same migration inserts a General project (`slug='general'`, `kind='general'`, triage lead = the first active admin by id). If no admin exists, the migration still creates the project with a null triage lead, which slice 04 then flags.
- A database-level check that `release_id` is null or points to a release of the same project is **not** added. It is enforced in the service and covered by tests (BR-03).

### Workflow additions (task rows)

| From | To | Condition |
|---|---|---|
| todo | in_progress | — |
| in_progress | in_review | — |
| in_progress, in_review | done | — |
| in_review | in_progress | — |
| todo, in_progress, in_review | blocked | Records `blocked_from_status` |
| blocked | `blocked_from_status` or todo | — |
| any non-done | cancelled | `cancel_reason = no_longer_needed` |

Bug cancel reasons exclude `no_longer_needed`, and task cancel reasons are only `no_longer_needed`. Workflow enforces both.

### Service and API

- `IssueCreate` gains `type`, `priority`, `is_urgent`, and `due_date`. `release_id` becomes optional and `project_id` required. Today the project is derived from the release; now the release, when given, must match the project.
- Validation, all `422` with a field error:
  - A task with `severity`, bug-only fields, or no `priority`.
  - A bug with `priority`.
  - `release_id` on a non-product project (use `409 code: releases_not_allowed` rather than 422, because it is a domain rule).
  - A release from another project (409 `code: release_project_mismatch`).
- `type` is rejected on PATCH (409 `code: type_immutable`).
- `transition()` clears `is_urgent` on entering `done` or `cancelled`. It writes an `urgent_cleared` timeline event only when the flag was set.
- Setting `is_urgent` true writes an `urgent_flagged` timeline event and fans out a new `InboxEventType.urgent` to the assignee. Add a matrix row with only assignee set to true. Who may set it is restricted in 04 (PM, CTO, and Admin, plus the triage outcome). In this slice any tech user may.
- Filters on `GET /issues`: `type`, `is_urgent`, `has_release` (a boolean, for finding hotfixes), and `project_kind`.
- `IssueResponse` gains `type`, `key` (for example `BUG-123`), `priority`, `is_urgent`, and `due_date`.
- Project create and update accept `kind`. Changing a product project to another kind is refused while it has releases (409 `code: project_has_releases`).
- `GET /issues/by-number/{n}` is unchanged. The frontend parses `bug-`, `task-`, and `issue-` slugs.

### Frontend

- Rework `NewIssueModal` into a single work-item form with a Bug/Task segmented control at the top (`components/ui/Segmented`).
  - Shared fields: title, project, description, labels, assignee, due date, and urgent.
  - Bug fields: severity (optional at filing), release (optional, shown only for product projects), reproduction steps, cURL, environment, release blocker, and attachments.
  - Task fields: priority (required) and attachments.
- A type icon plus key on `IssueTable`, `IssueBoard` cards, search results, and the command palette. Add `TYPE` to `lib/constants.js` and document it in `docs/design.md` §3.
- A compact urgent marker on rows and cards (design in `docs/design.md`; the full card-signal rules land in 10).
- The project create and edit modals get a Kind select. The release UI hides itself for non-product projects.
- Update `issueMarkdown.js` export and the `IssuePage` slug parsing.

## Testing Decisions

- API tests cover each story. Named ACs: `test_ac_24_urgent_hotfix_verified_clears_urgent`, and un-skip `test_ac_26_...` from 02.
- Workflow task rows follow the table-driven pattern from 02.
- **Migration test:** existing rows become `type=bug`, projects become `kind=product`, the General project exists, and `downgrade` refuses to proceed (clear error) if any issue has a null `release_id`. The downgrade cannot invent releases, so it must fail loudly rather than corrupt data.
- Deleting a release leaves its items with `release_id = null` instead of deleting them.

## Out of Scope

- Backlog and backlog category (08). Milestones (09).
- Role-based limits on who may create tasks, set Urgent, or set due dates (04).
- Due-date notifications (10).

## Further Notes

- Tech-filed bugs go through triage (BR-11) even when the filer intends to fix them right away. This was confirmed during product review ("all bugs pass New and triage"). Do not add a skip-triage shortcut.
