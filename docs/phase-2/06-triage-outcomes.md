# 06 — Triage Outcomes

> **Depends on:** 05 · **PRD:** FR-17–20, BR-16–21, **BR-49, BR-50 (v2.1)**; AC-14–22, **AC-49–54 (v2.1)**; §13 (To Support, To the triage lead)
> **v2.2:** there is no "Accept as urgent". There is one **Accept**, which requires `priority`; an accept with no release is the hotfix path (03a Part 1).
> **v2.1:** the Duplicate outcome is now a **merge**: it copies the duplicate's content to the original, and merging into a Done original makes it a regression. Possible-duplicate hints that open this outcome come in 14.

## Problem Statement

Triage today means "assign and set severity", plus a "needs clarification" workaround. There is no structured decision between fixing now, scheduling, asking for more information, marking a duplicate, or rejecting. Support never hears back unless someone remembers to reply in Telegram. Answered questions sit unnoticed.

## Solution

Each project's **triage queue** lists its New and Needs info bugs. A triager (any tech user) applies one of four **outcomes**: Accept, Needs info, Duplicate, or Reject. Each outcome has required inputs and a defined effect. A reply from the reporter or from Support on a Needs info item sends it back to New and notifies the triage lead. Support learns the result through three notifications only: Needs info, Cancelled, and Done. Those go to the item's **subscribers**: its reporter, plus (from 07) anyone who reported a recurrence and the reporters of duplicates merged into it.

## User Stories

1. As a triage lead, I want a triage queue per project listing New and Needs info bugs, oldest first, with source, reporter, recurrence count, and age, so that I work through reports fairly. (FR-17)
2. As a triage lead, I want to filter the queue to New only or Needs info only, so that I can focus.
3. As a developer who is not the triage lead, I want to triage any bug, so that the lead isn't a bottleneck. (AC-15)
4. As a triager, I want to **Accept** a bug into To do with a required priority, an optional assignee, and an optional release, so that it becomes planned work. (FR-18, BR-16, AC-16)
5. As a triager, I want an accept with no release to be the hotfix path, with no separate outcome for it. (FR-21, v2.2)
6. As an assignee, I want to be notified when a bug is accepted to me, so that I act on it.
7. As a triager, I want to choose **Needs info** only with a public comment saying what's missing, so that the reporter knows exactly what to send. (BR-18, AC-17)
8. As a Support reporter, I want a Telegram message when my report needs more information, with the triager's question, so that I can answer quickly.
9. As a Support reporter, I want my reply comment on a Needs info item to send it back to New and notify the triage lead, so that my answer is seen. (FR-19, BR-19, AC-18)
10. As a triager, I want any Support user's comment to count as a reply too, so that a colleague can answer on the reporter's behalf. (FR-19)
11. As a triager, I want a developer's comment on a Needs info item to leave its status unchanged, so that internal discussion doesn't bounce it back. (AC-19)
12. As a triager, I want to mark a bug a **Duplicate** of another bug in the same project, so that we work on one item. (FR-18, BR-20)
13. As a triager, I want marking a duplicate to cancel it with reason Duplicate, increase the original's recurrence count by one, and subscribe the duplicate's reporter to the original, so that the signal and the audience move to the original. (AC-20)
13a. As a triager, I want the duplicate's title and description added to the original as a public comment ("Merged from BUG-n"), so that nothing the reporter wrote is lost. (FR-18 v2.1, AC-49)
13b. As a triager, I want merging into a **Done** original to turn it into a regression: back to In progress, regression flag set, regression count +1, and a regression cycle recorded, so that a bug that came back after its fix is tracked as a regression. (BR-49, AC-50)
13c. As a QA engineer, I want that regression cycle recorded in the duplicate's release when the duplicate was filed in a release, and with no release otherwise, so that release reports and fragility analysis only count release regressions. (BR-49, BR-25, AC-50, AC-51)
13d. As a triager, I want merging into an In review, open, or Cancelled original to leave its status unchanged (a Cancelled original notifies its triage lead, as a recurrence does). (BR-49, AC-52, AC-53)
13e. As a Support reporter of the merged duplicate, I want the original's future Done notification, including after a regression cycle. (AC-54)
14. As a triager, I want to be stopped from pointing at an item that is itself a duplicate, with its original suggested instead, so that duplicate chains never form. (AC-21)
15. As a triager, I want to **Reject** a bug with a comment saying why, so that the reporter learns why. (FR-18; amended 2026-10-02: the structured reason was dropped — the comment is the reason)
16. As a Support reporter, I want a Telegram message when my report is cancelled, with the reason, so that I can tell the customer. (§13)
17. As a Support reporter, I want a Telegram message when my report is Done, so that I can tell the customer it's fixed. (§13)
18. As a Support reporter, I want no other status messages, so that the ones I get are worth reading. (§13)
19. As a triager, I want to move a New or Needs info bug to another project, so that misfiled reports reach the right team. (FR-20)
20. As a triage lead, I want to be notified when a bug is moved into my project's queue. (AC-22)
21. As a user, I want a cancelled bug never to be reopened, so that history stays clear; a new occurrence is reported again. (BR-21)
22. As a triage lead, I want Telegram notifications for: a new item in my queue, a reporter replied on Needs info, and an item moved into my project. (§13)
23. As a user, I want every triage outcome recorded on the timeline with its inputs, so that the decision is auditable.
24. As a tech reporter (QA or developer), I want to keep my current Phase 1 notifications, so that nothing I rely on disappears.

## Implementation Decisions

### Subscribers

- New table `issue_subscribers`: `issue_id, user_id, reason (reporter | recurrence | duplicate), created_at`. Unique `(issue_id, user_id)`; the first reason wins.
- The reporter is subscribed when the item is created. Backfill existing items with their reporter.
- **Support-audience events** are `needs_info`, `cancelled`, and `done`. They are three new `InboxEventType`s: `support_needs_info`, `support_cancelled`, and `support_done`. Their audience is subscribers with role `support`. Add matrix rows with a new relationship key `subscriber: true`, and extend the matrix loader and settings UI for that key.
- **Support users receive only those three events.** `fan_out` drops Support-role recipients from every other trigger, including `comment`, `mention`, and `status_changed`. This single rule guarantees Support never gets internal content by notification (BR-31).
- Tech reporters keep the Phase 1 matrix unchanged.

### Outcomes

`POST /issues/{id}/triage` replaces the Phase 1 triage and needs-clarification endpoints. Delete those, and the frontend calls that use them. The body is a tagged union on `outcome`:

| outcome | Required | Optional | Effect |
|---|---|---|---|
| `accept` | `priority` | `assignee_id`, `release_id` (omitted = hotfix path) | → todo |
| `needs_info` | `comment` | — | Public comment, → needs_info, notify subscribers |
| `duplicate` | `duplicate_of_id` | `comment` | → cancelled(duplicate), `parent_issue_id` set, original `recurrence_count += 1`, subscribe the duplicate's subscribers to the original with reason `duplicate`, add the merge comment to the original, then apply **merge effects** (below) |
| `reject` | `comment` (required) | — | → cancelled, no `cancel_reason` (amended 2026-10-02; the comment is posted publicly and is what Support is told) |

- Allowed only from `new` or `needs_info`. Otherwise 409 `code: not_in_triage`.
- Policy action `triage`: tech roles.
- `duplicate_of_id` must be in the same project (`code: duplicate_cross_project`), must not be the item itself, and must not itself have `cancel_reason = duplicate` (`code: duplicate_of_duplicate`, response includes `suggested_id` = its `parent_issue_id`).
- `recurrence_count` is incremented with an atomic `UPDATE ... SET recurrence_count = recurrence_count + 1`, never read-modify-write.
- The Workflow row `new → todo` becomes reachable **only** through this endpoint. `/transition` refuses it with `code: use_triage`.

### Merge effects (v2.1, BR-49/BR-50)

One service function, `MergeService.merge_into(original, *, content_md, reporter_id, attachments, source_release_id, actor)`, owns the effects on the original. It is used by the `duplicate` outcome here and by recurrence (07), so the rules are written once:
1. `recurrence_count += 1` (atomic UPDATE).
2. A public timeline comment on the original. For a merge, this is "Merged from <key>" plus the duplicate's title and description as a quote; for a recurrence, it is the recurrence comment (07). Attachments listed are re-linked to the original.
3. Subscribe the reporter (reason `duplicate` or `recurrence`).
4. Status effect by the original's status:

| Original status | Effect |
|---|---|
| `new`, `needs_info`, `todo`, `in_progress`, `in_review`, `blocked` | none |
| `done` | **merge regression**: `RegressionService.record_regression(original, release=source_release (may be None), detected_by=actor, source='merge')`, then `transition(original, to=in_progress, reason='merge_regression')`. Sets `is_regression`, increments `regression_count`, and fans out the Phase 1 regression notification to the assignee |
| `cancelled` | none; fan out `recurrence_on_cancelled` to the triage lead (07's event) |

- Only the `duplicate` outcome can reach the `done` row. Recurrence refuses Done (07, BR-23).
- `source_release_id` is the duplicate's `release_id`, which is null for support reports and most New bugs.
- Schema: `regression_history.release_id` becomes **nullable**, and a `source` column (`action | merge`, default `action`) is added. Fragility analysis (`RegressionService.get_component_fragility`) and release reports already select by release, so cycles without a release are excluded with no further change. Add a test that proves it (BR-25).
- Workflow: add the row `done → in_progress` with guard `reason == 'merge_regression'` and **no release condition**, reachable only from `MergeService`. `/transition` refuses it with `code: use_triage` (see 02).
- The whole merge runs in one transaction with the duplicate's cancellation.
- Backlog category and milestone placement on accept are added by 08 and 09.

### Needs info auto-return

- In the comment-create path (`POST /issues/{id}/timeline`): if the item is `needs_info`, the comment is public, and the author is the reporter or has role `support`, then call `transition(..., to=new)` in the same transaction. Fan out the new event `needs_info_replied` to the triage lead.

### Move project during triage

- `POST /issues/{id}/move` with `{project_id}`. Allowed in `new` or `needs_info` with no release (BR-05). It writes a `project_changed` timeline event and notifies the new project's triage lead with the new `moved_into_project` event, which falls back to admins as defined in 04.

### Notifications summary (this slice)

| Event | Audience |
|---|---|
| `filed` (existing) | Triage lead (fallback admins) |
| `needs_info_replied` | Triage lead |
| `moved_into_project` | New project's triage lead |
| `support_needs_info`, `support_cancelled`, `support_done` | Support subscribers |
| `assigned` (existing) | Assignee |

Telegram templates: add `support_needs_info` (includes the comment body), `support_cancelled` (includes the human-readable reason), and `support_done`. Link each to the item. Write copy per `docs/design.md` §11.

### Frontend

- Rework `TriagePage`: a per-project queue with New and Needs info tabs. Each row shows source, age, and recurrence count. A detail pane has four outcome buttons, and each opens a small form with exactly the required inputs (priority select, assignee picker, release picker, comment box, duplicate search-picker restricted to the same project, a required reject comment). Add a "Move to project" action.
- On 409 `duplicate_of_duplicate`, offer "Use <suggested key> instead".
- Needs info items show the triager's question pinned at the top of the item page for Support.

## Testing Decisions

- API tests for each outcome's happy path and each refusal code.
- Named ACs:
  - `test_ac_14_dev_filed_bug_enters_triage_not_board`
  - `test_ac_15_non_lead_developer_can_accept`
  - `test_ac_16_accept_requires_priority`
  - `test_ac_17_needs_info_requires_comment`
  - `test_ac_18_support_reply_returns_to_new_and_notifies_lead`
  - `test_ac_19_developer_comment_keeps_needs_info`
  - `test_ac_20_duplicate_cancels_increments_and_subscribes`
  - `test_ac_21_duplicate_of_duplicate_blocked_with_suggestion`
  - `test_ac_22_move_project_notifies_new_lead`
  - `test_ac_49_merge_into_open_copies_content_keeps_status`
  - `test_ac_50_merge_into_done_without_release_records_releaseless_regression` (also asserts release report and fragility numbers unchanged)
  - `test_ac_51_merge_into_done_uses_duplicate_release_for_cycle`
  - `test_ac_52_merge_into_in_review_keeps_status`
  - `test_ac_53_merge_into_cancelled_stays_cancelled_notifies_lead`
  - `test_ac_54_merged_support_reporter_gets_done_after_regression_cycle`
- **Notification tests** assert through the recipient's `GET /inbox` and the Telegram recorder:
  - A Support subscriber gets exactly the three events across a full lifecycle (filed → needs info → replied → accepted → in progress → in review → done), and nothing else, not even comments or mentions.
  - A tech reporter's Phase 1 notifications are unchanged.
- Concurrency: two duplicate outcomes pointing at the same original at once leave `recurrence_count` up by two (the same guard as AC-13 in 07).
- **E2E (key screen 2)** — `e2e/tests/triage.spec.ts`:
  1. The triage lead opens the queue and sees the Support report created through the API.
  2. The lead chooses Needs info, which requires a comment; the item moves to the Needs info tab.
  3. The Support user (second context) sees the question on the report and replies.
  4. The item returns to New in the lead's queue.
  5. The lead accepts it with a priority and an assignee.
  6. The item leaves the queue and appears on the project board in To do.

## Out of Scope

- The recurrence button (07).
- Backlog category and milestone on accept (08, 09).
- Triage SLAs or auto-close for Needs info (a deliberate limitation, PRD §15).

## Further Notes

- v2.1 changed BR-23/BR-24: a returning fixed bug is merged here, not filed as a new bug with a free-text link. The direct regression action from 02 stays release-only (AC-26).
- The PRD offers `wont_fix` as a bug cancel reason (BR-13). It is not a triage outcome. It is used via `/transition` to cancel accepted bugs from To do or Blocked.
