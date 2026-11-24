# 22 — To review tab in My Work

> **Depends on:** 19 · **PRD:** [v3.1](prd-v2.md) §7.3, FR-72, FR-73, BR-73; AC-99, AC-100
> **One session.** Independent of 20 and 21, so it can be built in parallel with them after 19.

## Problem Statement

My Work (slice 10) shows a person's **assigned** items. QA is rarely the assignee: the developer stays the assignee through review (CY-06). So work waiting for QA, To review and In review, is invisible in QA's own page. QA has to open every project's board to find it.

## Solution

- My Work gets two top-level tabs with counters: **My queue** (today's page, unchanged) and **To review**.
- **To review** lists every item in **To review** or **In review**, in **every project**, regardless of assignee. No reviewer is assigned (BR-73).
- QA lands on To review; everyone else lands on My queue. The last tab a user chose is remembered.

---

## User Stories

1. As QA, I want one list of everything waiting for review across all projects, so that I don't have to open every board.
2. As QA, I want it grouped by project and status, ordered by priority and by how long it has waited, so that I pick the right item next.
3. As QA, I want to filter by project, type and status.
4. As QA, I want to open an item from the list and pick it up (To review → In review), verify it, or reject it.
5. As QA, I want my own assigned work in the same page, on the other tab.
6. As a developer, I want the To review tab too, for when I review someone else's work.

## Implementation Decisions

### API

- `GET /review-queue?project_ids=&type=&status=to_review|in_review` (policy `view_review_queue`, tech roles; Support → 403).
- It returns items in `REVIEW_STATUSES` (`to_review, in_review`) that the caller can see, not deleted, in non-archived projects. Each row carries:
  - key, type, title, project chip, priority, assignee, container (Stream or release version), status;
  - `waiting_since`, the time of the move into the current status, read from the timeline / `issue_timestamps`, never stored anew;
  - `cycle_number`.
- Order: project name, then status (`to_review` first), then priority (Critical → Low, unrated last), then `waiting_since` ascending.
- `counts: {to_review, in_review, total}` for the tab counter, unaffected by filters except project.
- No pagination below 500 rows. Above that it returns the first 500 and `truncated: true`. A team this size never reaches it.
- Real-time: the existing `rw:inbox:{user_id}` push already refreshes My Work. The tab refetches on the same `issue_updated` signal.

### Default tab

- `users` has no preferences column today. Add `ui_prefs JSONB NOT NULL DEFAULT '{}'` (one migration with a downgrade), written through `PATCH /auth/me/ui-prefs`. It stores `my_work_tab: 'queue' | 'review'`. Later UI preferences go in the same column.
- With no stored value, QA gets `review` and everyone else gets `queue`.
- The URL `?mode=review` wins over the stored value and updates it.

### Frontend (`MyWorkPage.jsx`)

- A page-level **Segmented** control above the current Tabs: "My queue · n" | "To review · n". The existing filter tabs (All, In progress, Overdue, Blockers, Delivered) and the List | Board switch belong to My queue only.
- **To review mode:**
  - a list of project groups (collapsible, with counts), sub-grouped "To review" then "In review";
  - rows reuse `IssueTable` row styles: key, title, priority icon, assignee avatar, container chip, cycle badge, and "waiting 2d" in zinc, amber after 2 days, as the overdue marker does;
  - filters: a project multi-select, type, and status chips.
  - **Empty state:** "Nothing waiting for review".
- Row click opens the item. The item page's existing controls do the work: the status move to In review, Verify, Reject. Nothing in the list changes a status; there are no row actions, so there is no bulk path (BR-60).
- `CTO/Admin` viewing `/u/:username/work` see only My queue. To review is not per person.
- Check both themes; loading, empty and error states.

## Testing Decisions

- `test_ac_99_*`: items in To review and In review across three projects are all listed for QA, grouped and ordered as specified. The counter matches. An item in To do, Verified or Done is never listed.
- An item assigned to the QA user themselves is listed too (there is no self-verification block).
- Support → 403. A Developer gets the same list.
- Filters by project, type and status. Counts follow the project filter only.
- `waiting_since` is the time of the latest move into the current status (a To review → In review move resets it).
- `test_ac_100_*`: after Verify or Reject, the item is gone from the next response.
- Default tab: QA without a preference → `review`; Developer → `queue`; the `?mode=` override persists.
- E2E: as QA, open My Work, land on To review, open an item, move it to In review, verify it, and see it leave the list.

## Out of Scope

- Assigning or claiming a reviewer. The move to In review is the claim, and the timeline shows who did it.
- Review metrics (Phase 3: the To review → In review wait).

## Changes to Later Specs

- **MCP:** no new tool. `rw_board` already shows review columns per project.
- **CONTEXT.md:** add **To review tab** and **Review queue**. Update **Personal queue** (My Work has two modes).

## Prompt

```
Implement docs/phase-2/22-review-tab.md.
Read docs/phase-2/00-README.md, then 22, then PRD v3.1 FR-72/73. Slice 19 is committed.
Read MyWorkPage.jsx and the queue API (slice 10) before changing them; My queue must not
change. Work test-first at the API seam. Run `make test`, `make lint`, `make e2e`, and check
both modes of My Work in both themes. Update CONTEXT.md.
```
