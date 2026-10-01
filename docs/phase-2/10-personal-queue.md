# 10 — Personal Queue and Board

> **Depends on:** 09a · **PRD:** [v3](prd-v2.md) FR-33–42, FR-63, FR-64, BR-38–46, BR-61; AC-32–44, AC-74, AC-75; P3, P4; §13 (To the assignee)
> **v3:** a returned item goes back to its previous queue position, never above the pins (FR-64); cards gain the returned marker; containers replace release and milestone on the card.
> **09a:** the returned marker is gone — read it as the **Rejected** status plus the cycle badge; `returned` in the card fields becomes `status`, `reject_reason`, `cycle_number`. See 09a "Changes to Later Specs".

## Problem Statement

A developer with work in five projects sees five "top priority" items, one per project, and no answer to "what do I work on right now?". Project boards describe each project's intent. Nothing describes one person's execution order across projects. The CTO can't set that order either, short of messaging people.

## Solution

Every assignable user gets one **personal queue**: all their open assigned items across every project, in one order. The order has three groups:

1. **Pinned** items (at most 4). A pin set by a CTO or Admin is locked, and the owner can't remove it.
2. **The rest**, in manual order. A newly assigned item is inserted by a **default rule**: priority, then due date, then recurrence count, then age.

The owner, a CTO, and an Admin can reorder and pin. Every manual change is recorded in the owner's **queue history**, which is separate from item timelines. The owner is notified when someone else changes their queue. The **personal board** at `/my-work` shows the queue as a list or as a Kanban. Cards show only the title, the project, and a priority icon, plus compact markers that appear only when they matter.

## User Stories

1. As a developer, I want one list of every open item assigned to me across all projects, so that I don't have to visit five boards. (FR-33, BR-38)
2. As a developer, I want the list to exclude items that are Done, Cancelled, or still in triage (New, Needs info), so that it holds only committed work. (BR-38)
3. As a developer, I want my in-progress items grouped at the top of the list view, followed by my queue in order, so that I see what I'm doing and what's next. (FR-34)
4. As a developer, I want a Kanban view with the five board columns, where each column's cards follow my queue order, so that both views agree. (FR-35, AC-41)
5. As a developer, I want the Kanban Done column to show only items completed in the last 7 days, so that it doesn't grow forever. (FR-35, AC-42)
6. As a developer, I want my queue ordered pinned, then the rest, always. (FR-36, BR-39)
7. As a developer, I want to drag items to reorder my queue within a group, so that my manual order is kept. (FR-38)
8. As a developer, I want a drag from the rest into the pinned group refused, with an explanation that pinning is how an item is lifted, so that the two groups stay meaningful.
9. As a developer, I want a newly assigned item placed by the default rule even though I ordered my queue by hand, so that a new severe bug doesn't sink to the bottom. (FR-39, AC-35)
10. As a developer, I want a newly assigned Critical item placed below my pins and above every lower-priority item. (FR-39, AC-36)
11. As a developer, I want to pin up to 4 items, so that the things I committed to stay on top whatever arrives. (FR-40)
12. As a developer trying to pin a fifth item, I want to be refused with a message naming the limit. (AC-32)
13. As a CTO, I want to pin an item in anyone's queue, so that organization priorities win over project priorities. (FR-40)
14. As a developer, I want a pin set by the CTO shown with a lock, and I want to be unable to remove it. (FR-40, BR-41, AC-33)
15. As a CTO pinning into a queue that already has 4 pins, I want to be told the limit is reached and that I must unpin one first. (BR-40, AC-34)
16. As a CTO or Admin, I want to reorder anyone's queue. (FR-38, BR-42)
17. As a PM or triage lead, I want reorder and pin controls unavailable on other people's boards. (BR-42, AC-40)
18. As a developer, I want a notification when a CTO or Admin reorders my queue, pins an item, or unpins one, so that I don't keep working from an old order. (BR-43, AC-33)
19. As a developer, I want a queue history showing every reorder, pin, and unpin, with actor, item, and old and new positions, so that I can see who changed what. (FR-41, BR-44, AC-37)
20. As a developer, I want that history kept out of the item's timeline, so that item history stays about the item. (FR-41, AC-37)
21. As a CTO, I want to see anyone's queue history.
22. As a developer, I want an item reassigned away from me to leave my queue, releasing its pin, and to enter the new owner's queue by the default rule. (BR-45, AC-38)
23. As a developer, I want a pinned item that reaches Done or Cancelled to release its pin slot. (BR-46, AC-39)
24. As a developer, I want an item that comes back from Done (release QA or production) to re-enter my queue at the position it had before it left, but never above my pins, so that returned work doesn't jump the queue or sink. (FR-64, BR-61, AC-74, AC-75)
24a. As a developer, I want an item rejected from In review to keep its place in my queue, because it never left. (FR-64)
25. As a developer, I want cards to show only title, project chip, and priority icon by default. (FR-42, P3, AC-43)
26. As a developer, I want compact markers only when relevant: pinned (and locked), returned (with where it was caught and "returned N"), recurrence ×N when N > 1, due within 2 days or overdue, and technical debt. (FR-42, FR-63)
27. As a developer, I want hovering a card to show everything spelled out: markers (including the return reason comment), key, age, container (Stream or release name), reporter, and full due date. (FR-42, AC-44)
28. As an assignee, I want Telegram notifications when an item of mine is due within 24 hours and when it becomes overdue, once each. (§13)
29. As a user of the old My Issues page, I want its link to take me to My Work.
30. As a developer, I want a "Reported by me" link from My Work, since the old page had that tab.

## Implementation Decisions

### Queue ordering module (pure)

- `default_key(item) = (rank, due_date or +∞, -recurrence_count, created_at)`. `rank` is 1–4 from the shared priority (critical=1, high=2, medium=3, low=4; no priority sorts last).
- `group(item, entry) = pinned if entry.pinned else rest`.
- `insertion_index(new_item, rest_items_in_manual_order)` returns the index of the first item whose `default_key` is greater than the new item's, or the end. This implements FR-39 literally: "placed directly above the first item that ranks lower".
- A new pin is appended to the end of the pin group.
- `move(entries, issue_id, before_id | after_id)` refuses cross-group moves with `code: queue_group_boundary`.
- The module returns new positions. It never touches the database.

### Schema

- `queue_entries`: `user_id, issue_id (unique), position double precision, is_pinned, pinned_by_id, pin_locked, pinned_at, left_at`. Position is meaningful within the entry's group. The group itself is derived from `is_pinned`. `left_at` marks a **dormant** entry: an item that reached Done keeps its entry and position so that a return can restore it (FR-64). Dormant entries are excluded from every queue read, from pin counts, and from positions shown to users.
- `queue_history`: `id, user_id, actor_id, action (reorder|pin|unpin), issue_id, old_index, new_index, created_at`. Indexes are 1-based absolute positions in the full queue. Append-only: there is no update or delete endpoint (BR-44).
- `issues.due_soon_notified_at` and `issues.overdue_notified_at`, both reset when `due_date` changes.
- **Backfill** in the migration: for every assignable user, build the queue from their current open board-status items in default order.

### Queue maintenance

- `QueueService.sync(db, issue, previous_assignee_id)` is called from `IssueService` after any change to assignee, status, or priority. There is exactly one call site per mutation path, all inside the service layer. It:
  - Removes the entry from the old owner's queue (releasing the pin) when the assignee changes, the item leaves board statuses, or it is cancelled.
  - When the item reaches **done**: releases the pin (BR-46), keeps the entry's rest-group `position`, and sets `left_at` (dormant). A pinned entry is unpinned and given the top position of the rest group, so that if it returns it lands directly below the pins, as close to its old place as the rule allows.
  - When a **return** moves the item from done to todo (08a Part 3) and the assignee is unchanged: clears `left_at`, so the entry comes back at its old position in the rest group, which is always below the pins (FR-64, BR-61). If the assignee changed while it was Done, or no dormant entry exists, insert by the default rule.
  - A reject (in_review → todo) changes nothing: the item never left the queue.
  - Inserts the entry into the new owner's queue by the rules above.
  - Reinserts an unpinned entry by the default rule when its priority changes. Pinned entries stay pinned and keep their position.
- Automatic insertions and removals are **not** written to queue history. History records human actions only.

### API

- `GET /users/{id}/queue` (`me` accepted) returns `{groups: {pinned: [...], rest: [...]}, pin_limit: 4, pins_used, can_reorder, can_pin}`. Each entry is `{issue: WorkItemCard, pinned, pin_locked, pinned_by}`.
- `GET /users/{id}/board?done_days=7` returns five columns. Columns 1–4 are in queue order. Done lists items completed within `done_days`, most recent first.
- `POST /users/{id}/queue/move` with `{issue_id, before_id?, after_id?}`.
- `POST /users/{id}/queue/pins` with `{issue_id}`, and `DELETE /users/{id}/queue/pins/{issue_id}`.
  - Codes: `pin_limit_reached` (the message names the limit), `pin_locked` (owner removing a locked pin), `not_in_queue`.
- `GET /users/{id}/queue/history?page=`.
- Policy: `view_queue` for the owner, CTO, and Admin; `reorder_queue` and `pin` for the same set. A pin by a CTO or Admin on someone else's queue sets `pin_locked = true`. A CTO or Admin pinning their own queue does not lock it.
- **Notifications:** a new `InboxEventType.queue_changed` goes to the owner when actor ≠ owner. Meta: `{action, old_index, new_index}`. Add a matrix row with only assignee true.
- `WorkItemCard` is a slim item schema shared by queue, board, and list responses:
  - Default fields: `id, key, type, title, project{slug,name,color}, status, priority`.
  - Signal fields: `recurrence_count, due_date, due_state (none|soon|overdue), is_tech_debt, pinned, pin_locked, returned (null | {reason, number})`.
  - Hover fields: `container {kind, name}` (null for backlog), `reporter`, `created_at`, and the return comment when `returned` is set (fetched lazily).
  - `due_state` is computed server-side: `soon` means within 2 days, `overdue` means past the due date.

### Scheduled job

- `notify_due_items(now)` runs hourly from beat. It sends one `due_soon` notification per item when the due date is within 24 hours, and one `overdue` notification when it has passed. It uses the two `*_notified_at` columns. The audience is the assignee.

### Frontend

- `/my-work` replaces `MyIssuesPage`. Add a redirect route from `/my-issues`, and update the sidebar label to "My Work".
- A List/Kanban segmented toggle, remembered per user in `useTweaks`-style localStorage (UI preference only, not data).
- **List view:** an "In progress" group, then Pinned and Queue sections. Drag within a section with `@dnd-kit/sortable`. A pin toggle on each row, with a lock icon (and tooltip) on locked pins.
- **Kanban view:** reuse the `IssueBoard` columns with `WorkItemCard`. Drag between columns performs a status transition (02). Drag within a column is not a reorder in Kanban; reordering happens in the list view. This keeps the two views' ordering consistent.
- `WorkItemCard` component in `components/common/`. Its marker rules come from the API fields above. Hover uses the existing `Popover`/`UserHoverCard` pattern. Document the markers in `docs/design.md` §3, and in §14 if any existing card deviates.
- A queue history drawer, opened from a "History" button on the board.
- CTO and Admin open anyone's board at `/u/:username/work`. They see the same UI, with controls enabled per `can_reorder` and `can_pin`.
- Adopt `WorkItemCard` on the Stream board and release boards as well, so cards look the same everywhere (P3).

## Testing Decisions

- **API tests (ordering is proven through `GET /users/{id}/queue`):**
  - `test_ac_32_fifth_pin_refused_names_limit`
  - `test_ac_33_cto_pin_locked_owner_cannot_unpin_and_is_notified`
  - `test_ac_34_cto_pin_refused_at_limit`
  - `test_ac_35_new_high_bug_inserted_above_first_lower_ranked`
  - `test_ac_36_new_critical_below_pins_above_lower_priority`
  - `test_ac_37_cto_reorder_in_history_not_in_timeline`
  - `test_ac_38_reassign_releases_pin_and_reinserts`
  - `test_ac_39_done_releases_pin`
  - `test_ac_40_pm_and_triage_lead_cannot_reorder_or_pin`
  - `test_ac_42_done_column_excludes_items_older_than_7_days` (complete the item with the `clock` fixture set 8 days back, then read the board at the real time, per 01)
  - `test_ac_43_card_default_fields_only` (asserts the signal fields are empty or false for a plain item)
  - `test_ac_44_overdue_due_state`
- Ordering edge cases:
  - Ties on every key fall back to age.
  - A null due date sorts after any date.
  - A task with P2 ranks above a bug with Major (rank 2 vs 3).
  - A pinned item whose priority changes stays pinned, in place.
  - Unpinning an item reinserts it by the default rule.
- `test_ac_74_returned_item_restores_previous_position` and `test_ac_75_returned_item_never_above_pins` (Done → return → the entry comes back at its old position; with pins added meanwhile it is directly below them).
- A reject from In review leaves the queue order unchanged.
- A dormant entry never appears in `GET /users/{id}/queue`, in the board, or in the workload counts (11), and does not count toward the pin limit.
- Ship (09) keeps an assigned item's entry and pin even though the item moves to the backlog.
- Due job: exactly one `due_soon` and one `overdue` per item. Changing the due date resets both.
- **E2E (key screen 3)** — `e2e/tests/personal-board.spec.ts`:
  1. The developer sees three seeded items in default order.
  2. They drag the third above the first in the list view; after a reload the order persists.
  3. They pin an item; it moves to Pinned.
  4. The CTO (second context) opens `/u/<dev>/work` and pins another item.
  5. The developer's board shows it locked, and its unpin control is disabled with a tooltip.
  6. The History drawer lists the CTO's pin.
  7. The Kanban view shows the same relative order within To do.
  8. Hovering a card shows its key and due date.

## Out of Scope

- Capacity or effort awareness in the queue (PRD non-goal).
- Showing queue position on the Gantt (Phase 3, per PRD §16).
- Team-wide views (11).

## Further Notes

- AC-41 ("Kanban cards follow list order") holds by construction, because both views read queue order from the same endpoint. Keep an API test that asserts `board` column order equals queue order filtered by status.
