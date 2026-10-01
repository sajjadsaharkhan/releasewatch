# 11 — Team Overview

> **Depends on:** 10 · **PRD:** [v3](prd-v2.md) FR-43, AC-48; Goal 1 (CTO visibility)
> **v3:** the four Phase 2 reports this slice used to add (Support intake, Technical debt, Backlog flow, Hotfix volume) are **deferred to Phase 3** with every other new report (PRD §14, §16). "Hotfix" is no longer a term. Phase 1 reports are untouched here; 08a Part 2 already moved them onto cycles with unchanged numbers.

## Problem Statement

The CTO can't see who is working on what across projects without opening each person's board.

## Solution

Add a **Workload** view on the Team page, for CTO and Admin only. It shows each assignable user's in-progress items, top three queue items, and counts, and it links to their personal board with reorder and pin controls.

## User Stories

1. As a CTO, I want a Workload view listing every active assignable user, so that I see the whole technical team at once. (FR-43)
2. As a CTO, I want each person's In progress items shown, so that I see what they're doing right now. (FR-43)
3. As a CTO, I want each person's top three queue items shown, so that I see what's next for them. (FR-43)
4. As a CTO, I want counts of open and pinned items per person, so that overload is visible at a glance. (FR-43)
5. As a CTO, I want to open a person's board from the Workload view with reorder and pin controls, so that I can act immediately. (FR-43)
6. As a CTO, I want to filter the Workload view by role and by project involvement.
7. As a developer, PM, or QA engineer, I want the Workload view unavailable to me, and the API to refuse it, so that it stays a management tool. (AC-48)
8. As anyone, I want the existing Team member directory to keep working as it does today. (D9)

## Implementation Decisions

- **Workload:**
  - `GET /team/workload` (Policy `view_team_overview`: CTO and Admin) returns for each active assignable user `{user, in_progress: [WorkItemCard], next: [WorkItemCard ×≤3], counts: {open, pinned}}`.
  - It is computed from `queue_entries` and `issues` in a fixed number of queries, never one query per user. Assert the query count in a test against a 20-user fixture.
  - Frontend: a "Workload" tab on `TeamPage`, visible only when Policy allows it. It has a row per person, and clicking a row opens `/u/:username/work` (10).

## Testing Decisions

- `test_ac_48_workload_denied_to_developer` (also PM and QA).
- Workload content: a fixture of three users with pinned and in-progress items; assert the counts and the top three in queue order.
- A query-count guard for workload.
- Workload counts ignore dormant queue entries (10).

## Out of Scope

- Individual performance scoring (PRD non-goal). The copy on Workload must not rank people.
- Every new report, including support intake, technical debt, backlog flow, and cycle metrics (Phase 3, PRD §16).

## Further Notes

- This is the last Phase 2 slice. After it, remove the "Where the specs differ from the PRD" table from `00-README.md` into a short "Decisions" section of `CONTEXT.md`, so the decisions outlive the specs.
