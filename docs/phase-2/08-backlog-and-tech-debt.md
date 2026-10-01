# 08 — Backlog and Technical Debt

> **Depends on:** 07 · **PRD:** FR-23–29, BR-04–06, BR-36, BR-37; AC-28–31
> The backlog predicate gains "and no milestone" in 09.

## Problem Statement

Accepted work that isn't committed to a release sits nowhere visible, so it gets forgotten between releases. Technical debt spotted by the team or the CTO isn't recorded at all, so it's lost by the time there is capacity for it. Putting debt in the same pile as ordinary backlog work would bury the backlog in items nobody has committed to.

## Solution

Each project gets a **backlog**: a ranked list, not a board, of its open items that belong to no release (and, after 09, no milestone). Membership is derived, never set. Backlog items need a category (Feature request, Improvement, Future work), and the list supports drag ranking, grouping, multi-select, and bulk move to a release. Tasks can be flagged **technical debt**. Flagged tasks are hidden from the backlog by default and listed on their own **Technical debt** page, with a multi-select project filter. The flag adds no fields.

## User Stories

1. As a PM, I want a backlog page per project listing open items with no release, so that nothing uncommitted is lost. (FR-23, BR-04)
2. As a PM, I want the backlog shown as a ranked list rather than a board, so that its order means priority. (FR-23)
3. As a PM, I want to drag items to rank them, so that the top of the backlog is what we pull next. (FR-25)
4. As a PM, I want items grouped by category with counts, collapsible, and a toggle to a flat ranked view. (FR-25)
5. As a user placing an item in the backlog, I want a category to be required, so that the backlog stays sorted. (BR-06)
6. As a user, I want the category requirement waived for technical-debt tasks, because the flag already says what they are. (BR-06)
7. As a triager, I want to accept a bug into the backlog by choosing no release, and be asked for its category, so that triage completes placement in one step.
8. As a PM, I want to multi-select backlog items and move them to a release in one action, so that release planning is quick. (FR-25)
9. As a PM, I want an item removed from a release to return to the backlog with its previous category and rank, so that demoting doesn't lose my ordering.
10. As a PM, I want Done and Cancelled items never to appear in the backlog. (BR-04)
11. As a user, I want backlog membership to follow from placement, with no explicit "add to backlog" switch, so that it can't drift out of sync. (BR-04)
12. As a tech user, I want to flag a task as technical debt when I create it or later, so that debt is recorded where the work lives. (FR-26)
13. As a tech user, I want no extra fields for debt; components, risk, and approach go in the description, so that recording debt takes seconds. (FR-26)
14. As a user, I want the technical-debt flag unavailable on bugs, so that debt is always a task. (BR-36, AC-31)
15. As a PM, I want technical-debt tasks hidden from the backlog by default, with a "Show technical debt" toggle, so that debt doesn't bury committed work. (FR-24, AC-28)
16. As a CTO, I want a Technical debt page in the main navigation listing all flagged tasks, so that I can review debt when there is capacity. (FR-27)
17. As a CTO, I want to filter that page by project (multi-select), status, and assignee, so that I can view one project or several. (FR-27, AC-29)
18. As a user on a project page, I want a link to the Technical debt page pre-filtered to that project. (FR-28)
19. As a developer, I want a technical-debt task that is assigned or placed in a release to appear on boards and in queues like any task, still showing its debt marker. (FR-29, BR-37, AC-30)
20. As a user, I want the Technical debt page's filters kept in the URL, so that I can share a filtered view.
21. As a user, I want an item's project change blocked while it has a release, so that placement stays consistent. (BR-05)

## Implementation Decisions

- **Schema:**
  - `issues.backlog_category`: `feature_request | improvement | future_work`, nullable.
  - `issues.backlog_rank`: `double precision`, nullable.
  - `issues.is_tech_debt`: bool, default false.
- **Derived membership:** a single query helper, `backlog_items(project_id, include_tech_debt=False)`. The predicate is: not `done`, not `cancelled`, `release_id` null (and, from 09, `milestone_id` null), and status is a board status. New and Needs info are in triage, not backlog. Every backlog read uses this helper. There is no stored "in backlog" column.
- **Category rule:** enforced in the service whenever an item *becomes* a backlog member (created with no release, accepted with no release, removed from a release). Missing category → 422, unless `is_tech_debt`. The category is kept when the item leaves the backlog, so demotion restores it (story 9).
- **Ranking:**
  - Midpoint insertion between neighbours. `PUT /projects/{id}/backlog/order` takes `{issue_id, before_id?, after_id?}`.
  - A new backlog member gets `max(rank) + 1024`.
  - When the gap between neighbours drops below `1e-6`, renumber that project's backlog in one statement.
  - A rank is kept when the item leaves the backlog, so it returns to its prior position.
- **Endpoints:**
  - `GET /projects/{id}/backlog?include_tech_debt=&group_by=category`
  - `PUT .../backlog/order`
  - `POST /issues/bulk-move` with `{issue_ids, release_id}`. It is all-or-nothing, with per-item errors listed in a 409.
  - `GET /tech-debt?project_id=1,2&status=&assignee_id=`
  - Policy `manage_backlog` (PM, CTO, Admin, and developer as the project's triage lead) guards reorder and bulk-move.
  - Policy `flag_tech_debt` allows all tech roles, on tasks only (409 `code: tech_debt_task_only`).
- **Triage accept** (06) gains `backlog_category`, required when there is no `release_id` and the item is not tech debt. (Bugs can't be tech debt, so for triage it is required whenever there is no release.)
- **Frontend:**
  - A per-project `/projects/:slug/backlog` page. Grouped list with `@dnd-kit/sortable`. Each row shows key, type icon, title, category badge, priority, age, and assignee. Checkbox multi-select with a sticky bulk bar. A "Show technical debt" switch. Empty state copy per `docs/design.md` §11.
  - Hygiene hint in the header: "N items · M untouched for over 6 months". This is display only, based on `updated_at`.
  - Sidebar: add Backlog under Issues, and a Technical debt entry in the main nav.
  - A `/tech-debt` page: a list with a `MultiSelectFilterDropdown` (existing) for projects, plus status and assignee filters. The state lives in URL search params.
  - A tech-debt marker on rows and cards (compact; see 10 for card rules).
  - A tech-debt toggle in the create form (task only) and in the item sidebar.

## Testing Decisions

- Named ACs: `test_ac_28_tech_debt_hidden_from_backlog_by_default`, `test_ac_29_tech_debt_page_multi_project_filter`, `test_ac_30_assigned_tech_debt_in_queue_with_marker` (asserts the item's `is_tech_debt` in the assignee's listing now; re-asserted against the queue endpoint in 10), and `test_ac_31_tech_debt_flag_rejected_on_bug`.
- Backlog membership through the API:
  - Created with no release → member.
  - Moved to a release → not a member.
  - Removed from the release → member again with the same rank and category.
  - Done → not a member.
  - New (untriaged) → not a member.
- Rank tests: insert between two items, move to top, move to bottom, and renumbering when the gap collapses (force it with a tight loop of 60 inserts at the same spot).
- Bulk move is atomic: one invalid item (a different project's release) leaves all items unchanged.

## Out of Scope

- Milestone placement and bulk move to a milestone (09).
- A backlog Kanban. The backlog is a list, deliberately.
- Tech-debt reports (11).

## Further Notes

- "Technical debt" is no longer a backlog category. It is a flag (PRD §17 point 3).
