# 09 — Releases and Stream

> **Depends on:** 08a (all three parts) · **PRD:** [v3](prd-v2.md) §8.7, FR-46–FR-54, BR-47, BR-48, BR-51, BR-52, BR-55–BR-57, BR-62; AC-45, AC-46, AC-55, AC-59–AC-63; §13 (To the CTO)
> **v3:** this slice replaces **Milestones** (`09-milestones.md`, removed from the product). Gantt, CPM, dependencies, estimates, and computed release health are **Phase 3** (PRD §16). Don't build them, and don't add columns for them.

## Problem Statement

08a gave every project a Stream and mapped Phase 1 releases onto the v3 lifecycle values, but the Phase 1 release screens still start at QA. A release cannot be planned, has no progress or overdue signal, and shipping it says nothing about unfinished work. The Stream exists but has no page, so continuous work has no board.

## Solution

**Releases** get their full lifecycle: Planning → Development → QA → Released, or Cancelled. A release page shows a five-column board, an items table, an activity feed, progress by item count, an Overdue marker, open release blockers, and the go/no-go decision. **Ship** is one action with a notice that counts the unfinished items; confirming it marks the release Released and moves every item that is not Done to the backlog. A release with Done items cannot be cancelled. The **Stream page** is a board and items table whose Done column is limited by a time picker (last 7 days by default). The CTO is told once when a release passes its target ship date.

## User Stories

1. As a PM, I want to create a release with name (version), description, code freeze date, target ship date, and staging URL, starting in Planning. (FR-49)
2. As a PM, I want to move a release Planning → Development → QA, and QA back to Development, so that its state is explicit. (FR-50)
3. As a PM, I want Released reachable only through Ship. (FR-50)
4. As a PM, I want to cancel a release in Planning, Development, or QA only when it has no Done item. (BR-55, AC-59)
5. As a PM, I want cancelling a release to move its open items to the backlog like a ship does, so that nothing is lost.
6. As anyone, I want release progress shown as Done items divided by non-cancelled items. (BR-47, AC-45)
7. As anyone, I want an Overdue marker on a release whose target ship date has passed and which is not Released or Cancelled, and never on one without a target date. (FR-51, BR-48, AC-46)
8. As a CTO, I want one Telegram notification when a release passes its target ship date, and another if a later date also passes. (§13)
9. As a PM, I want a releases list per project showing lifecycle status, progress bar, target ship date, and the Overdue marker, sortable by date and progress. The Stream is not in this list.
10. As a PM, I want a release page with Board, Items, and Activity tabs. (FR-51)
11. As a PM, I want the Activity tab to show lifecycle changes, date changes, items added or removed, go/no-go decisions, and the ship. (FR-51)
12. As a CTO, I want the release page to list open release blockers and let me record go or no-go with a note. (FR-52)
13. As the CTO or the project's triage lead, I want to ship a release in QA. (FR-53, §7.3)
14. As a shipper, I want a notice before confirming that shows the go/no-go decision and the number of items that are not Done, by status. (FR-53, AC-60)
15. As a shipper, I want shipping to mark the release Released, and to move every item that is not Done to the backlog with category Default and status To do, keeping assignees and pins. (FR-53, BR-56, AC-61)
16. As a user, I want Ship unavailable on a release that is not in QA. (AC-62)
17. As a user, I want a Released release's pages read-only. (FR-54)
18. As a developer, I want a Stream page per project with a five-column board and an items table. (FR-47)
19. As a developer, I want the Stream's Done column to show the last 7 days by default, with a time picker for last 7, 30, 90, or N days, or a date range. (FR-47, AC-63)
20. As a user, I want the Stream shown first among a project's containers, with no edit, cancel, or delete controls. (FR-46, AC-55)

## Implementation Decisions

- **Schema:** `releases` already has `kind`, `status`, `code_freeze_date`, `target_date`, `released_at`, and the go/no-go columns (08a). Add:
  - `releases.overdue_notified_at` (timestamptz, nullable), cleared when `target_date` changes.
  - `release_events`: `id, release_id, actor_id, event_type (status_changed|dates_changed|item_added|item_removed|go_nogo|shipped|edited), meta JSONB, created_at`. It feeds the Activity tab and is separate from item timelines. Adding or removing an item also writes `release_changed` to the item's timeline, as today.
- **Lifecycle module** (pure, beside Workflow, separate from it): the FR-50 table. `qa → released` is reachable only from `ReleaseService.ship`. `→ cancelled` is refused with `code: release_has_done_items` when any item is Done. Released and Cancelled are final. Streams are refused with `stream_immutable` (08a).
- **Ship** — `POST /releases/{id}/ship` with `{confirm: true}`; `GET /releases/{id}/ship-preview` returns `{go_nogo, not_done: {todo, in_progress, in_review, blocked}}`. In one transaction:
  1. status `released`, `released_at = now` (from `get_now`), a `shipped` release event;
  2. every item not `done` or `cancelled`: status `todo` through `IssueService.transition` with reason `ship`, `release_id = null`, `backlog_category = default`, and `CycleService.on_moved_to_backlog` (08a). Assignee and queue entry (and pin) stay;
  3. fan out `release_shipped` to the release's item assignees and the CTO.
  Go/no-go is shown in the preview but not required (PRD §17.9).
- **Cancel** — `POST /releases/{id}/cancel`: refused if any item is Done; otherwise open items move to the backlog exactly as in ship step 2.
- **Policy (04):** `manage_releases` (PM, CTO, Admin, triage lead) for create, edit, and lifecycle; `ship_release` (CTO, Admin, the project's triage lead of any tech role); `go_nogo` (CTO, Admin).
- **Progress:** computed in the query, not stored: `done_count / nullif(total − cancelled_count, 0)`, `null` with no non-cancelled items. The response includes counts by board status.
- **Overdue:** computed on read: `target_date < today (server time zone) and status not in (released, cancelled)`.
- **Scheduled job:** `notify_overdue_releases(now)`, daily from Celery beat. For each overdue release with `overdue_notified_at` null, fan out `release_overdue` to active CTOs and set `overdue_notified_at`. Moving the date later clears it. Following 01, the job takes `now`.
  - `fan_out` is issue-centric. Add a release-scoped variant that creates `InboxItem` rows with a nullable `issue_id` and a new nullable `release_id`. `inbox_items.issue_id` becomes nullable; the inbox UI and Telegram templates handle rows without an issue.
- **Endpoints:** `GET/POST /projects/{id}/releases` (releases only), `GET /projects/{id}/stream`, `GET/PATCH /releases/{id}`, `POST /releases/{id}/status`, `POST /releases/{id}/go-nogo`, `GET /releases/{id}/ship-preview`, `POST /releases/{id}/ship`, `POST /releases/{id}/cancel`, `GET /releases/{id}/items`, `GET /releases/{id}/activity`, `GET /releases/{id}/board?done_from=&done_to=` (the Stream uses the same board endpoint; `done_from` defaults to 7 days before now for the Stream and is unbounded for releases).
- **Frontend:**
  - `/projects/:slug/stream` and `/projects/:slug/releases` (list), `/releases/:id` (tabs). Rework the Phase 1 `ReleasesPage` and `ReleaseDetailPage` into these; keep the go/no-go panel.
  - The Stream board's Done column has a time picker: relative presets (7d, 30d, 90d, "last N days") and an absolute range, in the style of a log-search time picker. The range lives in the URL.
  - Ship dialog built from the preview: go/no-go badge, the not-done counts, and a confirm button whose label says what will move ("Ship and move 4 items to the backlog").
  - Lifecycle badge and Overdue marker are visually distinct (Overdue is a red outlined marker, not a status badge). Document both in `docs/design.md`.
  - `ReleaseSwitcher` lists the Stream first, then open releases, then closed ones.

## Testing Decisions

- Named ACs: `test_ac_45_progress_excludes_cancelled`, `test_ac_46_no_overdue_without_target_date`, `test_ac_59_release_with_done_item_cannot_be_cancelled`, `test_ac_60_ship_preview_counts_not_done_by_status`, `test_ac_61_ship_moves_open_items_to_backlog_default_without_cycles`, `test_ac_62_ship_only_from_qa`, `test_ac_63_stream_done_column_default_7_days_and_range`.
- Lifecycle transition table: every allowed and refused path, including a Stream.
- Ship keeps assignee and pin: a pinned In progress item is in the backlog after ship, still assigned and pinned, with status To do.
- Overdue job: notifies CTOs once for the same `now`; moving the date later and slipping again notifies again; Released and Cancelled releases are never notified.
- The inbox renders a release-only item (API shape test: `issue` null, `release` present).
- Phase 1 characterization tests and report numbers are unchanged.

## Out of Scope

- Everything in PRD §16: Gantt, CPM, dependencies, working calendar, holidays, estimate fields, computed health, critical-path markers, and every new report.
- Requiring go before ship (PRD §17.9).
