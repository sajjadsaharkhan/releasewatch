# 19 — Verified, and Done means on production

> **Depends on:** 18 (implemented) · **PRD:** [v3.1](prd-v2.md) §0 v3.1, §8.7, §9, FR-35, FR-42, FR-47, FR-48, FR-50–FR-53, FR-56, FR-59, FR-62, FR-64, FR-67, BR-38, BR-46, BR-47, BR-49, BR-52, BR-54–BR-57, BR-60, BR-61, BR-67, BR-68, BR-74–BR-76, §14 (PD-1); AC-24, AC-25, AC-39, AC-42, AC-45, AC-50, AC-51, AC-57–AC-61, AC-63, AC-74–AC-76, AC-79–AC-85 · **Cycle model:** [cycle-model.md](cycle-model.md) §1, §3, CY-07a, CY-08, CY-13
> **Two sessions.** Part 1 is the backend (status, gates, ship, Reject, queue, notifications, migration). Part 2 is the frontend. Build it before 20: Support verification and return requests read the statuses this slice adds.

## Problem Statement

Done means two things today. In the Stream it means "on production". In a Release it means "verified on staging", and the item reaches production only when the release ships. When a release stays in QA for weeks and hotfixes go out through the Stream meanwhile, nobody can tell from a status which items are on production. At ship nobody knows which statuses to change, and Support receives "fixed" (`support_done`) for release items that are still on staging (PRD §17 point 8).

The free workflow also lets anyone drag a release item to Done, so even a careful team cannot keep Done truthful.

## Solution

- A new status **`verified`** — "Verified": QA approved the work; it is not on production yet. For bugs and tasks.
- **Done always means on production** (BR-67):
  - **Stream:** the person who deploys moves Verified items to Done — one by a status move, or several at once with **On production** (`POST /issues/bulk-production`), the only multi-item status change (BR-68). Work verified on production may go from To review / In review straight to Done.
  - **Release:** only **ship** makes an item Done. A status move to Done of a release item is refused (`409 done_at_ship`).
- **Ship** turns every Verified item into Done; every other item goes to the backlog as today.
- **Reject** is also allowed from Verified, with reason `release_qa` ("caught before production") in any container.
- **Queue:** Verified leaves the queue like Done (dormant entry, pin released).
- **Support's Done notice** (`support_done`) goes out when the item reaches Done, never at Verified.
- **Data move:** every Done item in a Release that isn't Released becomes Verified (BR-74).
- **Phase 1 reports** show a "not reliable" notice (PD-1). No report logic changes.

---

## User Stories

1. As QA, I want to move an item I approved to **Verified**, so that "approved" and "on production" are different states.
2. As the person who deploys the Stream, I want to select the Verified items I just deployed and press **On production**, so that they become Done together, each with its own record.
3. As QA checking a hotfix on production, I want to move a Stream item straight from In review to Done, so that I don't need two moves.
4. As a PM, I want a release item to become Done only when the release ships, so that Done in a release always means it is on production.
5. As a PM shipping a release, I want every Verified item to become Done without touching it, and the notice to tell me how many go to production and how many go to the backlog.
6. As QA, I want to reject a Verified item when release QA finds a problem, so that it comes back with a new cycle marked "caught before production".
7. As a developer, I want a Verified item to leave my queue like Done, and to come back to its old place if it is rejected.
8. As Support, I want the "fixed" notice only when the fix is on production.
9. As a deployer, I want Stream items that have waited in Verified for 3 days to carry a small marker, so that I don't forget to mark them.
10. As a CTO, I want the Phase 1 report pages to say their numbers are not reliable until Phase 3 repairs them.

## Implementation Decisions

### Status

- Add `verified` to `IssueStatus` (`backend/app/db/models/issue.py`) and to the frontend status constants (`frontend/src/lib/constants.js`). `issues.status` is `String(32)`; no enum type to alter. The parity test and grep guard (03a) must pass.
- Order everywhere: `new, needs_info, todo, rejected, in_progress, to_review, in_review, verified, done, blocked, cancelled`.
- Named sets:
  - `BOARD_STATUSES` gains `verified`.
  - `BACKLOG_STATUSES` excludes `verified`. A backlog item has no cycle and can't have been verified. Moving a Verified item to the backlog is refused like Done (`done_item_immobile`), which becomes `delivered_item_immobile` for both.
  - `OPEN_STATUSES` keeps `verified` (it isn't Done or Cancelled), so recurrence is allowed on it (AC-79) and the similar-reports panel lists it.
  - `FIXED_STATUSES` (Phase 1 "fixed") becomes `to_review, in_review, verified, done`. `REJECTABLE_STATUSES` follows it.
  - New `DELIVERED_STATUSES = (verified, done)`, used by the container lock, release cancel and queue rules below.
  - `queue_service.QUEUE_STATUSES` excludes `verified` and `done`.
- Label "Verified". Hue: emerald, a lighter step than Done. Lucide icon `badge-check`, where Done keeps `check-circle-2`. Record both in `docs/design.md` §3.

### Workflow (`app/workflow.py`)

The workflow stays free (CONTEXT: Workflow). It gets one new gate beside `use_reject`:

- **`done_at_ship`:** `to = done` while the item's container is a Release (`kind = release`) → refused. `allowed_targets` never lists `done` for such an item; it lists `verified`. The container kind is passed in the context dict, as the module takes no database access.
- In the Stream and in the backlog, `done` stays reachable from any status. The backlog case is already refused elsewhere: a backlog item can't be Done (BR-04).
- `ReleaseService.ship` writes Done through `IssueService.transition(..., _internal_context={"via_ship": True})`, the only bypass of the gate, in the same way `via_reject` bypasses `use_reject`.

### `/verify`

- `POST /issues/{id}/verify` `outcome: pass` moves to `verified` (it moved to `done`). New optional `on_production: bool`. When it is true and the item is in the Stream, the move is to `done`; on a release item, `on_production` is refused with 409 `done_at_ship`. `fail` stays refused (`use_reject`, 09a). `partial` is unchanged.

### Timestamps and cycles (CY-05, CY-07a)

- `verified_at` (cycle) and the `verified` lifecycle timestamp are written on the **first** move into `verified` in the cycle. They are also written on a move from `to_review`/`in_review` straight to `done` (Stream), and are never overwritten.
- The `completed` lifecycle timestamp is written when the item reaches `done`: by a move, by On production, or at ship (= `released_at`).
- `DurationService`: "time to fix" keeps reading `verified`. Nothing else changes (PD-1 covers the reports).

### Reject (`IssueService.reject_with`)

- `_reject_denial` and `REJECTABLE_STATUSES` include `verified`.
- Classification, replacing the from-Done branch:
  - from `to_review` / `in_review` → `review`;
  - from `verified` → `release_qa`, in any container, and the item stays in its container;
  - from `done` → `production`, and an item in a Released release moves to the Stream (unchanged).
- `cycle_service.return_reason_for_done` is no longer needed. After the data move, no Done item sits in an unshipped release. Delete it and its call sites.
- Reason labels (`issue_service` `CYCLE_REASON` labels and the frontend `CYCLE_REASON`): `release_qa` → "Caught before production".

### Merge (`MergeService.merge_into`, BR-49/50)

- Into `done`: Reject as today, but **`recurrence_count` does not change** (BR-50 v3.1). Move the `+1` after the status branch, and skip it on the Done branch.
- Into `verified`: no status change, no cycle, count +1, the same as for any open status.
- `duplicate_hints` "what merging will do" uses the same function, so the hint text becomes "Done → Rejected (production)" or "stays Verified" (engine FR-S13).

### Ship (`ReleaseService.ship`, `ship_preview`)

- `ship_preview` returns `{to_production: <verified count>, to_backlog: {status: n}, total_to_backlog, go_nogo}`. `SHIP_NOTICE_STATUSES` adds `rejected` and drops nothing; `verified` is counted separately.
- `ship`, in one transaction: for every `verified` item → `done` via the `via_ship` path, with `completed` = `released_at`, one `status_changed` timeline event each (`reason = ship`), and `support_done` fan-out per item. Then `_move_open_items_to_backlog` as today, for everything not Verified, Done or Cancelled. The `shipped` release event meta gains `to_production`.
- `progress(counts)` = (`verified` + `done`) ÷ non-cancelled (BR-47). `has_done_items` → `has_delivered_items` (Verified or Done) for cancel (BR-55, `release_has_done_items` keeps its code).

### On production (Stream, FR-67)

- `POST /issues/bulk-production {issue_ids: [...]}`. Policy action `mark_production` (tech roles; Support never).
- All or nothing: every id must be a `verified` item in a Stream the caller can see, else `409 not_verified_in_stream` with the offending ids. At most 100 ids.
- Each item goes through `IssueService.transition(to=done)` with `reason = on_production` on its timeline event, so every per-item effect (timestamps, queue, `support_done`, search reindex) is the ordinary one.
- One request creates one Support-channel batch key (`batch_id` in the event meta) for slice 21 to group by; nothing reads it yet.

### Queue (`QueueService.sync`, CY-13)

- Today `current == done` makes the entry dormant. Make it `current in DELIVERED_STATUSES` (pin released, `left_at` set).
- A Reject from `verified` or `done` wakes the dormant entry at its position (unchanged code path; it now also triggers from Verified).
- Verified → Done leaves the dormant entry as it is.

### Notifications

- `support_done` stays tied to the move into `done`. `SUPPORT_NOTICE_STATUSES` is unchanged. Because Verified is not Done, Support no longer hears "fixed" at verification. The existing Support `status_changed` notice (2026-10-14) now also covers "→ Verified".
- `verified` inbox event: emitted on the move into `verified` (it was emitted at Done-from-review), to reporter + assignee as today.
- The ship fan-out (`release_shipped`) is unchanged. The per-item `support_done` messages are additional.

### Container lock (BR-54)

- `container_service.resolve` refuses to move a `verified` or `done` item (`delivered_item_immobile`). The only move is the Reject-from-Done → Stream move (unchanged).

### Data migration

One Alembic revision with a working downgrade:

- **Up:** `UPDATE issues SET status = 'verified'` where `status = 'done'` and the container is `kind = release` with status not `released`. Keep their `verified` timestamps; clear their `completed` timestamp. Mark their queue entries dormant if not already. Write no timeline events (it is a data move, not an action), and log the count.
- **Down:** `verified → done`, setting `completed` = `verified`.
- Idempotent.

### Frontend (Part 2)

- **Board columns** (Stream, release, Kanban My Work): To do (Rejected on top), In progress, To review, In review, **Verified**, Done, Blocked. A release board's Done column is empty until ship. Leave it visible with the empty text "Done after ship".
- **Stream board and Items table:** a multi-select on Verified cards/rows (checkbox on hover, shift-click range), and a bar "n selected · **On production**" (primary button) that calls `bulk-production`. A confirm dialog lists the keys. Errors name the refused items. This is not a generic bulk-status control: the bar appears only when the selection is Verified Stream items.
- **Status control:** release items never list Done (it isn't in `allowed_transitions`). The tooltip on the disabled option reads "Done when the release ships".
- **Verified age marker (FR-42, BR-75):** a Stream item `verified` for 3 days or more shows a small `clock-alert` marker (zinc) on cards and rows. Hover shows "Verified n days ago — not on production yet". Never on release items.
- **Ship dialog:** two lines, "n items go to production" and "m items go to the backlog (2 To do, 1 In review, …)", plus the go/no-go badge.
- **Reject dialog:** offered on Verified items (`allowed_actions` has `reject`). The pill label for `release_qa` is "Caught before production".
- **My Work:** the `Done` tab filter becomes "Delivered", showing Verified and the Done range. The board view gets the Verified column.
- **Phase 1 report pages** (Dashboard report cards, Regressions, Release reports, Contributions): a slim amber notice at the top, "These numbers are not reliable since Phase 2 and will be rebuilt (PD-1)." It cannot be dismissed. Text only, no logic change.
- Check both themes in the browser before finishing.

## Testing Decisions

Test through the API (01 seams), named after the PRD ACs where they apply.

- `test_ac_24_*`: Stream item In review → Verified, not Done; → Done by a move; `support_done` sent at Done, not at Verified.
- `test_ac_57_*`: release item → Done by `/transition` → 409 `done_at_ship`; `allowed_transitions` has no `done` and has `verified`.
- `test_ac_83_*`: Stream In review → Done directly sets both `verified` and `completed`.
- `test_ac_25_*`: Reject from Verified in a release → Rejected, same release, cycle `release_qa`. The same from Verified in the Stream → `release_qa`.
- `test_ac_50_*`: merge into Done → Rejected, `production`, **count unchanged**. `test_ac_51_*`: merge into Verified → unchanged status, no cycle, count +1.
- `test_ac_45_*`: progress counts Verified. `test_ac_59_*`: cancel is refused with one Verified item.
- `test_ac_58_*`: moving a Verified item to another container → 409 `delivered_item_immobile`.
- `test_ac_60_61_*`: ship preview numbers; ship makes Verified items Done with `completed = released_at`, one `support_done` each, and moves the rest to the backlog as To do (Rejected too).
- `test_ac_81_*`: `bulk-production` with three Verified Stream items → three Done, three timeline events with `on_production`, one shared `batch_id`. A mix with a release item or a non-Verified item → 409, nothing changed. Support → 403.
- `test_ac_39_*`, `test_ac_74_*`, `test_ac_75_*`: Verified releases the pin and goes dormant; Reject from Verified/Done restores the position below pins.
- `test_ac_79_*`: recurrence on Verified is allowed.
- `test_ac_85_*`: migration up/down on a fixture with Done in an unshipped release, Done in a Released release, and Done in the Stream.
- `tests/phase2/test_cycle_reports.py`: Phase 1 reports must still run. Update the expected numbers where Verified changed them, and say so in the PR. They are product debt now, not a regression guard.
- E2E: verify a Stream item, select two Verified items, press On production, see them in Done; ship a release with a Verified item and see it Done.

## Out of Scope

- Support verification and return requests (slice 20).
- The Support channel (slice 21). This slice only writes `batch_id`.
- The To review tab (slice 22).
- Repairing any Phase 1 report (PD-1, Phase 3).
- A Verified → Done wait metric (Phase 3).

## Changes to Later Specs

- **MCP (`rw_board`, `rw_get_item`, `rw_my_queue`):** status lists come from the constants, so Verified appears without code changes. Check that `rw_board` groups it, and that `rw_report_recurrence` accepts Verified (FR-M19 unchanged in meaning).
- **CONTEXT.md:** add **Verified**, **On production**, the **Done gate** (`done_at_ship`), and **Delivered statuses**. Update **Flow status**, **Reject**, **Ship**, **Merge into Done**, **Dormant queue entry** and **Cycle**.

## Prompt

```
Part 1 — Implement docs/phase-2/19-verified-and-production.md, backend only.
Read docs/phase-2/00-README.md, then 19, then PRD v3.1 §9 and BR-67–BR-76, and
cycle-model.md §3. Read the 09a code (IssueService.reject_with, MergeService.merge_into,
ReleaseService.ship, QueueService.sync, workflow.py, policy.py) before changing it.
Work test-first at the API seam. Run `make test` and `make lint`. Update CONTEXT.md.

Part 2 — Implement the frontend part of 19 (board columns, On production selection bar,
Done gate in the status control, Verified age marker, ship dialog, report notice).
Read docs/design.md first. Check every changed screen in both themes. Run `make e2e`.
```
