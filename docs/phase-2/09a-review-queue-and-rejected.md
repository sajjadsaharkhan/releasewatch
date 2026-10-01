# 09a — To review, Rejected, and one Reject action

> **Depends on:** 09 (implemented) · **Changes:** 08a Part 3 (returns, returned marker), [cycle-model.md](cycle-model.md) CY-05, CY-11 · **Decision:** [ADR 0004](../adr/0004-rejected-is-a-status.md)
> **One session.** Build it before slice 10: 10's queue and card markers read the statuses this slice adds.

## Problem Statement

08a built returns on top of cycles, and reading an item's state now takes three places:

1. **Reject is hidden inside a status move.** `POST /transition` from In review to To do *with a comment* is a Reject (new `review` cycle); the same move without a comment is a plain move. `/verify` with a failing note is a third way in. Done work goes back through a separate endpoint (`POST /returns`) and a separate dialog.
2. **"Came back" is computed, not visible.** An item that was rejected sits in To do, and only the returned marker says so — derived from the current cycle (`start_reason <> planned` and `submitted_at IS NULL`, CY-11). Anyone reading the board, a filter, or a report has to join cycles to know whether a To do item is new work or rejected work.
3. **Reject and Return are two names for one thing.** Both send delivered work back with a comment and start a new cycle. The only difference is where the problem was caught, which the server already decides.

There is also no way to tell "the developer says it's done" from "QA is looking at it": In review means both.

## Solution

- Two new statuses, for bugs and tasks:
  - **`to_review`** — "To review": the developer has delivered the work; it waits for QA. QA picks it up by moving it to In review.
  - **`rejected`** — "Rejected": delivered work was sent back with a reason. The developer picks it up by moving it to In progress.
- **One Reject action** replaces Reject, Return from release QA, and Problem on production. It is allowed from To review, In review, and Done, always takes a comment, and always lands the item in **Rejected**.
- **Cycles keep recording, but stop driving the UI.** Reject still closes the current cycle and opens the next one, and the server still classifies it (`review`, `release_qa`, `production`) for Phase 3 metrics (CY-09). What the user sees comes from the status, not from the cycle.
- **The reason is an ordinary comment.** Reject writes one public comment on the item; nothing renders it specially.
- **The returned marker goes away.** In its place, any item past its first cycle shows a small **cycle badge** (`↻ 2`).

---

## User Stories

1. As a developer, I want to move finished work to **To review**, so that QA sees it waiting and I can see it's out of my hands.
2. As QA, I want to move an item from To review to **In review** when I start checking it, so that nobody else picks up the same item.
3. As QA, I want one **Reject** action on To review, In review, and Done items, with a required comment, so that sending work back is the same everywhere.
4. As a developer, I want a rejected item to have the status **Rejected**, so that I can tell it from new work without hovering a marker.
5. As a developer, I want rejected items shown in the To do column, visually distinct and above plain To do cards, so that the board doesn't grow a column and rejected work gets picked up first.
6. As anyone, I want the reject reason to appear as a normal comment on the item, so that the discussion about it stays in one thread.
7. As a developer, I want a small cycle badge on items that are past their first cycle, so that I still know an item came back after I pick it up.
8. As a PM, I want a report merged into a Done item to reject it, the same as a manual Reject. (BR-49)
9. As a CTO, I want Phase 3 reports to still tell review rejects from release-QA catches and escapes, even though users see one action. (CY-09)

## Implementation Decisions

### Statuses

- Add `to_review` and `rejected` to `IssueStatus` (backend) and the status constants (frontend). `issues.status` is `String(32)`; no enum type to alter.
- Order everywhere: `new, needs_info, todo, rejected, in_progress, to_review, in_review, done, blocked, cancelled`.
- `BOARD_STATUSES` gains both. `BACKLOG_STATUSES` gains `to_review` but **not** `rejected` (a rejected item has no meaning without a cycle; see Backlog below). `OPEN_STATUSES` gains both. `FIXED_STATUSES` (Phase 1 "fixed") becomes `to_review, in_review, done`.
- Tasks get both statuses; neither is bug-only.

### Workflow

The workflow stays free (08a decision): any status to any status, **except**:

- **Nothing enters `rejected` through `/transition`.** 409 `code: use_reject`. `allowed_transitions` never lists `rejected`. The only ways in are `POST /reject` and a merge into a Done item.
- Leaving `rejected` is free. Moving it by drag to To do is allowed and is just a move; the cycle stays as it is.
- `/transition` from In review to To do is **always a plain move** now. The "with a comment it's a reject" overload is removed, and so is the reject branch of `/verify` (a failing verification returns 409 `code: use_reject`; the UI no longer offers it).

### Reject

- `POST /issues/{id}/reject` `{comment}`. Policy action `reject` = what `return_item` is today, extended to To review/In review (tech roles; Support never).
- Allowed from `to_review`, `in_review`, `done`. Anything else → 409 `code: not_rejectable`. Empty comment → 422.
- Effects, in one transaction:
  1. Write the comment as an ordinary public comment (`event_type = comment`, no `meta.return_reason`).
  2. Move the item to `rejected`, writing a status-change timeline event with `reason = reject` (the timeline renders it as "rejected this item").
  3. Classify, as today: from To review / In review → `review`; from Done in a Release that isn't Released → `release_qa`; from Done otherwise → `production`, and a Done item in a Released release moves to the Stream first (CY-03).
  4. `CycleService.start_return(...)` with that reason and `comment_id` = the comment's id. The cycle keeps `start_comment_id`; it is data, not display.
  5. Notify the assignee (`item_returned`, CY-12, unchanged payload).
- `POST /issues/{id}/returns` and `POST /issues/{id}/reopen` stay as thin aliases of `/reject` (Done items only, as today), so Phase 1 callers keep working. The frontend calls only `/reject`.
- **Merge into Done (BR-49)** goes through the same service method, landing in `rejected`. A merge into anything else still starts no cycle.

### Cycle timestamps (CY-05 changes)

- `submitted_at` and `delivered_by_id` are written on the **first move into `to_review` or `in_review`** in the cycle, whichever comes first (the free workflow allows skipping To review). Same rule as today otherwise: the assignee at that moment, never the actor.
- `verified_at` is written when the item moves to Done from `to_review` or `in_review`.
- No new timestamp for "QA picked it up". It can be added when a metric needs it.

### Backlog and ship

- Moving a `rejected` item to the backlog (PM move, bulk move, or shipping its release) sets its status to `todo` in the same step and writes a timeline event. Its cycles are deleted as today (CY-14).
- A `rejected` item moving between open containers keeps `rejected`; its cycle follows it (CY-01).

### API response

- Remove `IssueResponse.returned` (the marker) and `return_reason`.
- Add `cycle_number: int | None` — the current cycle's number, null in the backlog.
- Add `reject_reason: str | None` — the current cycle's `start_reason` while the status is `rejected`, else null. Add `reject_comment_id: int | None` alongside it for the hover card.
- `allowed_actions` gains `reject`, loses `return_item`.

### Data migration

One Alembic revision with a working downgrade:

- **Up:** an item becomes `rejected` when it is `todo`, its current cycle has `start_reason <> 'planned'`, and `picked_up_at IS NULL` (returned and not yet picked up). Items already In progress keep their status; they get the cycle badge.
- **Down:** `rejected → todo`, `to_review → in_review`.
- Existing reject comments keep their `meta.return_reason`; the timeline just stops rendering it specially.

### Frontend

- **Board** columns: To do (with Rejected cards), In progress, To review, In review, Done, Blocked. Rejected cards sort above plain To do cards.
- **Rejected card/row style:** a status pill "Rejected" in the reason's hue and icon from `CYCLE_REASON` (amber `undo-2` review, orange `rotate-ccw` release QA, red `flame` production), and a left accent in the same hue on board cards. Hover or focus (250 ms) opens the popover the marker has today: full label ("Rejected in review", "Returned from release QA", "Problem on production") and the reason comment, fetched lazily by `reject_comment_id`.
- **Cycle badge** (`<CycleBadge item compact?>` in `components/common`): shown when `cycle_number ≥ 2`, on every status. Lucide `repeat` icon + the number, zinc, tooltip "Cycle 2". It replaces `ReturnedMarker` in `IssueTable` rows and board cards. Delete `ReturnedMarker`.
- **Reject dialog:** `SendBackDialog` becomes `RejectDialog`. One title ("Reject"), one destructive button, comment required. The sidebar shows **Reject** on To review, In review, and Done items when `allowed_actions` has `reject`. The Done-item button labels ("Return from release QA", "Problem on production") are gone.
- **Status control:** never lists Rejected (it isn't in `allowed_transitions`).
- **To review** status: label "To review", hue amber, icon `clock`, and In review keeps amber `eye`. Record both new statuses and the badge in `docs/design.md` §3, and replace the "no Returned status" paragraph.
- Check both themes in the browser before finishing.

## Testing Decisions

Test through the API, as 08a did.

- `reject` from To review, In review, and Done lands in `rejected`, writes one plain public comment, starts cycle N+1 with the right `start_reason` (`review` / `release_qa` / `production`), and notifies the assignee.
- `reject` from To do, In progress, Blocked, Rejected → 409 `not_rejectable`; empty comment → 422; Support → 403.
- `/transition` to `rejected` → 409 `use_reject`; `allowed_transitions` never contains it.
- `/transition` In review → To do with a comment is a plain move: no cycle, status `todo`.
- Done in a Released release → Reject → item in the Stream, status `rejected`, reason `production`.
- Merge into a Done item → `rejected`.
- `submitted_at`/`delivered_by_id` set on the first of To review / In review; not overwritten by the second. `verified_at` set on Done from either.
- Moving a rejected item to the backlog, and shipping a release that holds one, leaves it `todo` with no cycles.
- `/returns` and `/reopen` still work (aliases).
- Migration: up/down on a fixture with a returned-not-picked-up item, a returned-in-progress item, and an item in review.
- Phase 1 report numbers (`tests/phase2/test_cycle_reports.py`) unchanged.
- Update 08a tests that assert the transition-with-comment reject, the `/verify` fail path, `returned`, or `return_reason`; they describe replaced behavior.
- E2E: reject an In review item from the item page, see it Rejected in the To do column, pick it up, see the cycle badge.

## Out of Scope

- New Phase 3 metrics for the To review wait. The data (`submitted_at`, the move to In review in the timeline) is enough to add one later.
- Workflow gates. Everything except entering `rejected` stays free.
- Changing what `start_reason` values exist.

## Changes to Later Specs

- **10 (personal queue):** read "returned marker" as "Rejected status plus cycle badge". AC-74/75 and CY-13 are unchanged in meaning: a rejected-from-Done item re-enters at its old position; a reject from To review/In review never left the queue. `returned` in the card signal fields becomes `status`, `reject_reason`, and `cycle_number`.

## Prompt

```
Implement docs/phase-2/09a-review-queue-and-rejected.md (to_review and rejected statuses,
one Reject action, cycle badge replaces the returned marker).
Read docs/phase-2/00-README.md, then 09a, then ADR 0004 and cycle-model.md. Slice 09 is
committed; read the 08a returns code (IssueService.reject / send_back_done, CycleService,
SendBackDialog, ReturnedMarker) before changing it. The workflow stays free except that
nothing enters rejected through /transition. Work test-first at the API seam. Run
`make test` and `make lint` before finishing, and check the board and item page in both
themes.
```
