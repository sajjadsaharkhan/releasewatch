# 20 — Support verification and return requests

> **Depends on:** 19 · **PRD:** [v3.1](prd-v2.md) §7.3 (footnote ³), §8.2, §8.4, §8.10, FR-11, FR-13, FR-16, FR-17, FR-56, FR-59, FR-68, FR-69, BR-23, BR-30, BR-69–BR-71, §13; AC-12, AC-71, AC-86–AC-93 · **Cycle model:** [cycle-model.md](cycle-model.md) §3 (return request)
> **One session.**

## Problem Statement

Support's feedback after the Phase 2 release, against the code as it is:

1. **Support can't close a fix from To review.** `policy.decide` lets Support make exactly one move, `in_review → done`. A hotfix the developer sent to **To review** cannot be closed by Support, which tests hotfixes itself. After slice 19, Done also means "on production", so even In review → Done is the wrong move for a release item.
2. **Support can't reject a failed fix.** `Action.reject` is tech-only.
3. **A fixed bug that comes back has no direct path.** Recurrence is refused on Done (`recurrence_on_done`). Support has to file a new report and hope triage merges it. Triage either merges it, which brings the item back, or rejects it, which makes Support's report Cancelled. In the second case the original was done work, and Support simply misjudged it.

## Solution

- **Support verifies and rejects support-sourced items**, in every project, whoever filed them (BR-71):
  - To review / In review → **Verified**. In the Stream, → **Done** is also allowed, for work Support tested on production.
  - **Reject** from To review / In review, with a comment (reason `review`).
  - Nothing else. Support makes no other status move and has no Reject from Verified or Done.
- **Return request** (§8.10): on a **Done** item a Support user can see, **Problem is back** records a request with a comment. No item is created, the status stays Done, and the count is unchanged.
  - The request appears in the project's triage queue. A triager **confirms** it, which is the ordinary Reject from Done with the request's comment (`production` cycle), or **dismisses** it with a public comment, and the item stays Done.
  - Requesters are subscribed and told the outcome.

---

## User Stories

1. As Support, I want to verify a hotfix that is in To review or In review, so that I don't have to wait for QA on a report I tested myself.
2. As Support testing on production, I want to move a Stream hotfix straight to Done.
3. As Support, I want to reject a fix that didn't work, with a comment, so that it goes back to the developer.
4. As Support, I want **Problem is back** on a Done item, so that I can say a fixed problem has returned without filing a new report.
5. As a second Support user, I want to add my customer's details to the same pending request instead of creating another.
6. As a triage lead, I want pending return requests in my triage queue and a notification for each new one.
7. As a triager, I want to confirm a request, which sends the item back with a `production` cycle, or dismiss it with an explanation, which leaves the item Done.
8. As Support, I want to hear the decision, and to see "Return requested" in my reports list while it is pending.

## Implementation Decisions

### Policy (`app/policy.py`)

- Replace the Support special case (`transition("done")` from `in_review`) with one helper, `_support_status_move(actor, action, target)`. For a Support actor on a target with `source == "support"`, it allows:
  - `transition:verified` from `to_review` / `in_review`;
  - `transition:done` from `to_review` / `in_review` **only when the container is the Stream**. Add `container_kind` to `Target`. The workflow's `done_at_ship` would refuse a release item anyway; this keeps the control hidden.
  - `reject` from `to_review` / `in_review`.
- Everything else Support asks for stays denied with `hidden=True`. On a subscribed but non-support item (BR-30), Support makes no status move.
- New action `request_return`: Support only, on an item it can see whose status is `done`. Otherwise `409 not_done`, or hidden for tech roles.
- New action `decide_return_request`, `_T` (any tech role, like `triage`).
- `/verify` with `on_production` follows the same rule for Support.

### Data

- New table `return_requests`:
  - `id`, `issue_id` FK, `status` (`pending | confirmed | dismissed`), `requested_by_id`, `requested_at`;
  - `decided_by_id`, `decided_at`, `decision_comment_id` FK `issue_timeline` (null while pending);
  - `start_comment_id` FK `issue_timeline` — the first requester's comment;
  - `via_mcp_token_id` null, for parity; agents can't create one.
- Partial unique index on `(issue_id) WHERE status = 'pending'` (BR-69: one pending request per item).
- `return_request_entries`: `id`, `request_id` FK, `user_id`, `comment_id` FK `issue_timeline`, `created_at`. One row per press, the first included. Attachments ride on the comment, through the existing pending-attachments flow.
- `status`, and the new `TimelineEventType` values, are declared once in the enum modules: `return_requested`, `return_request_added`, `return_confirmed`, `return_dismissed`.

### Service: `ReturnRequestService` (the only writer)

- `request(db, issue, actor, body, pending_attachments)`:
  1. Lock the issue row (`merge_service.lock_original`).
  2. Write a **public comment** with the body. Attachments go through the pending-attachments flow, as recurrence (07) does.
  3. If a pending request exists, add an entry and write `return_request_added`. Otherwise create the request and write `return_requested`.
  4. Subscribe the actor (reason `return_request`).
  5. Fan out `return_requested` to the triage lead, the first time only.
- `confirm(db, request, actor)`: the request must be pending (`409 request_closed`) and the item still `done`. If the item is no longer Done, close the request as `confirmed` with no effect and say so in the response, `"item_already_returned": true`. Otherwise call `IssueService.reject_with(issue, actor, comment_event=<request's first comment>, move_reason="return_request")`. That is the ordinary Reject from Done: `production` cycle, the Released → Stream move, and `item_returned` to the assignee. The recurrence count does not change. Mark the request `confirmed` and write `return_confirmed`.
- `dismiss(db, request, actor, comment)`: an empty comment → 422 `reason_required`. Write a public comment, mark the request `dismissed`, and write `return_dismissed`. Nothing else changes.
- Both decisions fan out `support_return_decided` to the request's entry users, with `outcome` and, for dismiss, the comment.
- A Reject, a merge into Done, or a cancel of the item while a request is pending closes it as `confirmed`, with `decided_by` set to that actor and no extra notice. The item came back anyway. A merge or Reject already notifies through its own path.

### API

- `POST /issues/{id}/return-requests {comment, pending_attachments?}` → 201 with the request. 409 `not_done` when the item isn't Done; 403 for tech roles.
- `GET /issues/{id}/return-requests` returns the item's requests, newest first. Support sees its own and every Support user's entries (public comments only).
- `POST /return-requests/{rid}/confirm` and `POST /return-requests/{rid}/dismiss {comment}` take policy `decide_return_request` on the item.
- **Triage queue:** the Triage page reads New / Needs info through `GET /issues` with filters, and a return request is not an issue. Add `GET /projects/{id}/return-requests?status=pending` (policy `triage`). It returns pending requests oldest first, each with the item card (key, title, status Done, container, assignee), the requesters, the first comment, and the entry count. The sidebar triage counter adds its `total`.
- `IssueResponse` gains `pending_return_request: {id, requested_at, entries} | null`, and `allowed_actions` gains `request_return` / `decide_return_request`.
- Support reports list: `return_requested: bool` per row.

### Recurrence

- `recurrence_on_done` stays. Its detail text becomes: "This item is Done. Use Problem is back to ask for it to come back."
- The FR-16 "file a new report with this ID prefilled" shortcut is removed.

### Notifications (`InboxEventType`, `DEFAULT_NOTIFICATION_MATRIX`)

- `return_requested` → the project's triage lead (admins while there is none, AC-23). Telegram on by default.
- `support_return_decided` → Support entry users. It is added to `SUPPORT_EVENTS` / `SUPPORT_RECEIVABLE` so `fan_out` doesn't drop Support.
- Templates: "BUG-42 — Problem is back, requested by @x" for the triage lead. For Support: "BUG-42 is going back for a fix", or "BUG-42 stays Done: <comment>".

### Frontend

- **Item page, Support:**
  - On a support-sourced item in To review / In review, Support sees **Verify** (a primary button). In the Stream it opens a small menu: "Verified" or "Done — tested on production". Support also sees **Reject**, which opens the existing `RejectDialog`.
  - On a Done item, Support sees **Problem is back**, which opens a dialog with a required comment and attachments. With a pending request, the button reads **Add to pending request**, and a banner on the item shows "Return requested · n reports · waiting for triage".
  - Support never sees any other status control.
- **Item page, tech:**
  - A pending request shows the same banner with **Confirm** and **Dismiss**. Dismiss requires a comment. The timeline renders the four new event types, with requester names and a link to each comment.
- **Triage page:** no separate tab (changed after the first build, decided with the user 2026-11-24). Pending return requests lead the **New** tab, above the ordinary rows, in a group headed "Came back from production · n", because a fixed item that came back is urgent. Each is a red-outlined card with a solid red icon tile, the item key, a "Problem is back" pill, the title and the first report; a footer strip holds the requesters, the report count and "Done 2d ago in Stream", and a **waiting** chip that is amber for the first 4 hours and solid red after. The first return is selected by default. The detail pane has Confirm and Dismiss. **A pending return request counts as one waiting decision, like a New bug:** the New tab's counter and the sidebar triage badge are New bugs plus pending requests (one per item, however many Support users pressed).
- **Support reports list:** a "Return requested" amber badge on the row, and a filter chip.
- Check both themes.

## Testing Decisions

- `test_ac_91_*`: Support moves a support-sourced item from To review → Verified, from In review → Verified, and in the Stream from In review → Done. On a release item, → Done is refused.
- `test_ac_92_*`: Support Reject from In review with a comment → Rejected, `review`; without a comment → 422.
- `test_ac_93_*`: Support → In progress, → Blocked, Reject from Verified/Done, any move on a non-support or subscribed-internal item: all refused. No `mark_production`.
- `test_ac_86_*`, `test_ac_87_*`: a request needs a comment. It keeps the item Done with the count unchanged, creates no item, shows up in the triage queue, and notifies the triage lead once.
- `test_ac_88_*`: a second Support user's press adds an entry to the same request and subscribes them. The triage lead is not notified again.
- `test_ac_89_*`: confirm on an item in a Released release → Rejected in the Stream, `production` cycle with the first comment as the reason, count unchanged, the assignee gets `item_returned`, and requesters get `support_return_decided`.
- `test_ac_90_*`: dismiss without a comment → 422. With a comment, the item stays Done, no cycle starts, and requesters receive the comment.
- A request on a Done **task** the Support user is subscribed to works the same way.
- A tech Reject of an item with a pending request closes the request as `confirmed`.
- Partial unique index: two concurrent first presses → one request, two entries.
- `test_ac_12_*` / `test_ac_71_*`: on a Done bug, recurrence is refused with the new text, and Support's `allowed_actions` has `request_return`, not `reject`.
- E2E: Support presses Problem is back on a Done bug, a triager sees it at the top of the New tab and confirms it, and the bug is Rejected. The triage badge and the New tab count pending requests with New bugs.

## Out of Scope

- The Support channel posts for these events (slice 21 reads the timeline events added here).
- MCP tools for return requests. Agents never act for Support (BR-M04).
- Auto-closing stale requests.

## Changes to Later Specs

- **CONTEXT.md:** add **Return request**, **Problem is back**, and **Support verification**. Update **Role**, **Subscriber** (new reason `return_request`), **Recurrence** (Done text), and the **Triage queue** (return requests lead the New tab and count in the triage badge).
- **prd-search-engine:** no change. Requests are not indexed; their comments are ordinary public comments and are indexed as such.

## Prompt

```
Implement docs/phase-2/20-support-verify-and-return-requests.md.
Read docs/phase-2/00-README.md, then 20, then PRD v3.1 §7.3, §8.10, FR-68/69, BR-69–71,
and §13. Slice 19 is committed. Read policy.py (the Support special case), MergeService,
IssueService.reject_with, the recurrence service (07) and TriagePage before changing them.
Work test-first at the API seam. Run `make test`, `make lint`, `make e2e`. Check the item
page, Triage page and Support reports list in both themes. Update CONTEXT.md.
```
