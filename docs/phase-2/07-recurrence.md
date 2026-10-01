# 07 — Recurrence

> **Depends on:** 06 · **PRD:** FR-13–16, BR-22, BR-23 (v2.1), BR-50; §8.4; AC-09–13
> **v2.1:** the Done guidance changed (a returning bug is merged in triage as a regression), recurrence effects go through 06's `MergeService`, and the similar-reports panel entry point moved to 14.

## Problem Statement

When the same problem hits five customers, Support posts five messages or files five reports. Engineers either see noise or miss how widespread the problem is. How many times a problem was reported is the strongest priority signal Support can give, and today it is lost.

## Solution

A **Report recurrence** action on any open or Cancelled bug. It requires a comment, which is where the new customer's details go. It increments the bug's recurrence count, adds the comment to the timeline, and subscribes the person who reported it to the bug's Support notifications. On a Cancelled bug it alerts the triage lead without reopening the bug. On a Done bug it is unavailable: a problem that returns after a fix is filed as a new report and merged into the original in triage, where it becomes a regression (06).

## User Stories

1. As a Support user, I want a Report recurrence button on a bug I can see, so that I record another occurrence instead of filing a duplicate. (FR-13)
2. As a tech user, I want the same button, so that occurrences I hear about are counted too. (FR-13)
3. As a reporter of a recurrence, I want a comment to be required, so that the new customer's details are always captured. (FR-13, BR-22, AC-09)
4. As an engineer, I want the recurrence count to go up by exactly one per recurrence, so that the number means "times reported". (BR-22, AC-10)
5. As an engineer, I want the recurrence comment shown on the timeline, marked as a recurrence, so that I can read each occurrence's details. (FR-14, AC-10)
6. As a Support user who reported a recurrence, I want to receive that bug's Support notifications (Needs info, Cancelled, Done), so that I can update my customer too. (FR-14)
7. As a triage lead, I want to be notified when a recurrence is reported on a Cancelled bug, so that I can reconsider a rejection. (FR-15, AC-11)
8. As a triage lead, I want a recurrence on a Cancelled bug to leave it Cancelled, so that nothing reopens without a decision. (FR-15, BR-21, AC-11)
9. As a Support user on a Done bug, I want the button disabled with "Fixed items can't take a recurrence. File a new report; triage will merge it into this item as a regression.", so that I know what to do. (FR-16, BR-23, AC-12)
10. As a Support user, I want a shortcut from that disabled state to a new report with the previous key already written into the description, so that the triager sees the link even without a suggestion. (FR-16)
11. As two Support users reporting at the same moment, I want both occurrences counted, so that the count is never wrong. (AC-13)
12. As a Support user, I want the recurrence button reachable from the Support reports list, so that I can record a recurrence without opening the item. (The similar-reports panel entry point is added in 14.)
13. As a triager, I want the triage queue to show the recurrence count, so that often-reported problems stand out.

## Implementation Decisions

- New table `issue_recurrences`: `id, issue_id FK, reported_by_id FK, timeline_id FK, created_at`. It exists so reports in 11 can count recurrences over time. The count shown in the UI is still `issues.recurrence_count`.
- `POST /issues/{id}/recurrences` with body `{comment}` (non-empty after trimming; 422 otherwise). Policy action `report_recurrence` is allowed for all roles, including Support, on visible bugs. Tasks return 409 `code: recurrence_bug_only`, and Done bugs return 409 `code: recurrence_on_done` with the FR-16 text as `detail`.
- In one transaction, through 06's `MergeService.merge_into` (BR-50), so recurrence and merge share one implementation:
  1. An atomic `UPDATE issues SET recurrence_count = recurrence_count + 1 WHERE id = :id RETURNING recurrence_count`.
  2. A public timeline event of new type `recurrence`, with the comment as body.
  3. Insert the recurrence row (recurrence only; merges are counted from `duplicate` cancellations).
  4. Subscribe the reporter with reason `recurrence` (no-op if already subscribed).
  5. If the bug is Cancelled, fan out the new `recurrence_on_cancelled` event to the triage lead (fallback admins).
- The request body also accepts `pending_attachments[]` (used by 14's support panel), linked to the item through the pre-upload flow from 05.
- **Build order:** 06 is built before 07, so 06 creates `MergeService` with the recurrence count, comment, subscription, and status-effect steps, and defines the `recurrence_on_cancelled` event. 07 adds the `recurrence` timeline type, the `issue_recurrences` table, and the endpoint.
- On open bugs, the recurrence comment goes to the assignee and reporter through the normal `comment` fan-out. Support recipients are still filtered, per 06.
- `allowed_actions` / `blocked_actions` include `report_recurrence`, so the UI takes the disabled state and its text from the API.
- Frontend:
  - A Report recurrence button and dialog (comment required) on the item page, Support reports rows, and similar-report panel entries.
  - A `recurrence` timeline entry style.
  - A "New report referencing this" link that opens `/support/new` with `?ref=<key>`, which prefills the free description with `Previously reported as <key>.` Tech users get the same link to the work-item form.

## Testing Decisions

- Named ACs: `test_ac_09_recurrence_requires_comment`, `test_ac_10_recurrence_increments_and_adds_timeline_comment`, `test_ac_11_recurrence_on_cancelled_notifies_lead_stays_cancelled`, `test_ac_12_recurrence_blocked_on_done_with_guidance`, and `test_ac_13_concurrent_recurrences_both_counted`. For AC-13, fire two requests concurrently with `asyncio.gather` over two clients.
- A subscription test: a Support user reports a recurrence, the bug later reaches Done, and that user gets `support_done`.
- A visibility test: a Support user cannot report a recurrence on a non-support bug (404).

## Out of Scope

- Merging a returning bug into its Done original (06).

## Further Notes

- `recurrence_count` starts at 1, because the original report counts as one occurrence. Card signals in 10 show the count only when it is greater than 1.
