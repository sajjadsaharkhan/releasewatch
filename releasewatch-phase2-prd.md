# Releasewatch Phase 2 — Product Requirements Document

> **Status: SUPERSEDED.** The current source of truth is
> [`docs/phase2/roadmap.md`](docs/phase2/roadmap.md), which breaks this document into four
> releases and fifteen feature PRDs. The problem this program solves is stated in
> [`docs/phase2-problem-statement.md`](docs/phase2-problem-statement.md).
>
> This file is kept as the record of the thinking that produced the roadmap. Read it for
> context, not for requirements.
>
> **Three decisions in the roadmap diverge materially from what follows:**
>
> 1. **Effort is optional everywhere.** This document assumes an estimate on every item and
>    builds critical path, float, health thresholds, and a working calendar on that assumption.
>    In the roadmap, effort is optional and any analysis needing it excludes unestimated work
>    rather than inventing a value. See [ADR-0001](docs/adr/0001-effort-is-optional.md).
> 2. **There is one milestone concept.** A deadline is optional and time-based planning is an
>    opt-in mode, not a second kind of milestone.
> 3. **Dependencies are Gantt artefacts**, authored where a schedule is defined, not properties
>    of a work item. See [ADR-0002](docs/adr/0002-dependencies-are-gantt-artefacts.md).
>
> Also changed: Severity becomes **Priority** (Urgent/High/Medium/Low) on all work; `enhancement`
> moves to Kind. Releases get progress and risk but never a Gantt
> ([ADR-0003](docs/adr/0003-releases-get-risk-not-schedules.md)). There is no global "project
> manager" role — planning authority follows milestone ownership.

> **Product:** Releasewatch — release, task, and milestone management
> **Phase:** 2 — Task management, Backlog, Milestones, Dependency scheduling
> **Status:** Superseded by `docs/phase2/roadmap.md`
> **Owner:** CTO

---

## Table of Contents

1. [Overview](#1-overview)
2. [Problem Statement](#2-problem-statement)
3. [Goals & Success Metrics](#3-goals--success-metrics)
4. [Scope](#4-scope)
5. [Users & Personas](#5-users--personas)
6. [Domain Model](#6-domain-model)
7. [Roles & Permissions](#7-roles--permissions)
8. [Functional Requirements](#8-functional-requirements)
9. [Business Rules](#9-business-rules)
10. [Edge Cases](#10-edge-cases)
11. [Notifications](#11-notifications)
12. [Reporting](#12-reporting)
13. [Non-Functional Requirements](#13-non-functional-requirements)
14. [Rollout Plan](#14-rollout-plan)
15. [Assumptions & Open Questions](#15-assumptions--open-questions)
16. [Glossary](#16-glossary)

---

## 1. Overview

Releasewatch Phase 1 solved release-scoped QA issue tracking: bugs found during release testing, triaged, assigned, fixed, verified, and closed, with regression tracking and a CTO health dashboard.

Phase 2 extends the product into unified work management. It adds development tasks alongside bugs, a per-project backlog for uncommitted work, goal-oriented milestones with measurable progress, and deadline-driven scheduling with dependency management and a Gantt view.

The two phases share one data model, one notification channel, and one interface. Phase 2 is an expansion, not a separate module.

---

## 2. Problem Statement

The team currently manages three categories of work in three different places, and one of them is nowhere at all.

**Release bugs** live in Releasewatch and are well managed.

**Development tasks** live in individual conversations, direct messages, and personal notes. A task assigned verbally is invisible to everyone except the two people in the conversation. There is no single place a team member can see everything assigned to them.

**Future work** — technical debt, requested features, deferred improvements — has no home at all. When a release closes and a bug is judged "not for this release," it disappears. The same issue is rediscovered months later by a different QA engineer.

Layered on top of this is a planning problem. Organizational goals exist but are not measurable. Leadership cannot answer:

- What percentage of the work required to achieve this goal is complete?
- How much remains?
- Which tasks are on the critical path?
- What is blocking what?
- Will we hit the committed date, and if not, by how much will we miss?

Deadlines are therefore set by intuition and missed without warning. The first signal that a goal is late is the day it becomes late.

---

## 3. Goals & Success Metrics

### Primary goals

**G1 — Nothing is lost.** Every piece of work, whether a release bug, a development task, or a deferred idea, has a durable, findable home.

**G2 — Everyone sees their own work in one place.** A team member working across four projects opens one screen and sees everything assigned to them.

**G3 — Goals become measurable.** Every milestone reports a progress percentage, a projected finish date, and a health signal derived from real data.

**G4 — Deadline risk is visible early.** Schedule slippage is surfaced days or weeks before the deadline, not on the day it is missed.

**G5 — The system stays simple.** No sprints, no story points, no velocity charts, no resource allocation solver, no capacity planning. Kanban flow plus dependency-based scheduling only.

### Success metrics

| Metric | Baseline | Target after 1 quarter |
|---|---|---|
| Work items tracked in-system versus managed informally | ~40% (bugs only) | > 90% |
| Team members using My Work as their daily screen | 0 | > 80% |
| Milestones with a hard deadline and full estimates | 0 | > 60% of active milestones |
| Median lead time from deadline-risk detection to deadline | n/a (detected at breach) | > 10 working days |
| Backlog items older than 6 months with no review | unknown | < 20% |
| Estimate accuracy (actual versus original, team-wide) | unmeasured | measured and trending |

Note on the last row: the goal in the first quarter is measurement, not accuracy. A team that discovers it estimates at 55% accuracy has gained something valuable. Improvement targets follow once a baseline exists.

---

## 4. Scope

### In scope

- Tasks as a second work item type with their own workflow
- Per-project backlog with categories, ranking, and hygiene signals
- Milestones with goals, lifecycle, owners, optional deadlines, and computed health
- Finish-to-start dependencies between items within a milestone
- Automatic critical path identification and float calculation
- Gantt timeline view honouring the company working calendar and public holidays
- Three-field estimation model: estimate, remaining, actual
- Estimate variance and accuracy reporting
- A unified personal work view spanning all projects
- A General project for work with no natural project home
- Telegram notifications for all new event types

### Out of scope for Phase 2

| Excluded | Rationale |
|---|---|
| Resource capacity and allocation | Sequencing is expressed manually through dependencies. Deliberate simplicity decision |
| Dependency types beyond finish-to-start | Finish-to-start covers the overwhelming majority of real constraints |
| Cross-milestone scheduling dependencies | Scheduling is milestone-scoped. Cross-boundary links exist but carry no schedule effect |
| Sub-tasks, epics, or any work item hierarchy | Flat structure. Milestones provide the only grouping |
| Sprints, story points, velocity | The team runs Kanban, not Scrum |
| Time tracking or timesheets | Only three estimation fields, all self-reported |
| Baseline snapshots and schedule variance over time | Deferred to Phase 3 |
| Recurring tasks | No current need |
| Converting a bug into a task or vice versa | Create a new item instead |
| Email notifications | Telegram is the sole channel |

---

## 5. Users & Personas

**Sajjad — CTO.** Needs strategic visibility. Wants to know which milestones are at risk, whether release quality is improving, and where time is being lost. Reads dashboards weekly, not daily. Does not manage individual tasks.

**Reza — Project Manager.** Owns milestones and deadlines. Sets estimates, creates dependencies, manages the backlog, and manually sequences work when one person has several parallel tasks. The heaviest user of the Gantt view.

**Ali — Developer.** Works across several projects simultaneously. Needs one screen showing everything assigned to him, ordered sensibly. Updates remaining hours as work progresses. Rarely opens a Gantt.

**Maryam — QA Engineer.** Files bugs during release testing, verifies fixes, and occasionally files tasks for tooling improvements. Lives in the release board and her personal inbox.

**Kamran — Triage Lead.** Routes incoming bugs to the right developer, assigns severity, and decides what belongs in this release versus the backlog.

---

## 6. Domain Model

### Hierarchy

```
Project
├── Release            (shipping event, has a ship date)
├── Milestone          (goal, has optional hard deadline)
└── Work Item          (Bug or Task)
        ├── may belong to a Release
        ├── may belong to a Milestone
        ├── may belong to both
        └── may belong to neither → it is in the Backlog
```

**Releases and Milestones are siblings.** Neither contains the other. They are parallel organizing axes over the same pool of work items. A task can simultaneously be part of the "Wallet redesign" milestone and shipped in release v2.4.1.

### Entities and their attributes

**Project** — name, key, description, general-project flag, default labels, archived state.

**Release** — version, ship date, status, staging URL, go/no-go decision, decision note, decision maker, decision timestamp.

**Milestone** — key, name, goal statement, lifecycle status, owner, start date, optional hard deadline, scheduling-enabled flag, computed projected finish, computed slack, computed health, computed progress percentage.

**Work Item (shared)** — item ID, type, title, description, project, optional release, optional milestone, status, reporter, assignee, labels, priority, attachments, activity timeline, created date, started date, completed date.

**Work Item (bug only)** — severity, release-blocker flag, regression flag, regression count, reproduction steps, cURL command, environment details, verifier, verification date.

**Work Item (task and scheduling)** — estimate hours, remaining hours, actual hours, due date, computed start, computed finish, computed float, critical-path flag.

**Work Item (backlog only)** — backlog category, backlog rank.

**Dependency** — predecessor item, successor item, optional lag hours. Finish-to-start only.

**Working Calendar** — hours per weekday, synced public holidays, optional company-specific closures.

---

## 7. Roles & Permissions

| Capability | QA | Dev | Triage Lead | PM | CTO | Admin |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| File bug or task | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Comment, attach files | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Update remaining hours on own assigned item | ✓ | ✓ | ✓ | ✓ | — | ✓ |
| Update remaining hours on any item | — | — | ✓ | ✓ | — | ✓ |
| Mark bug fixed | — | ✓ | ✓ | ✓ | — | ✓ |
| Verify bug fix | ✓ | — | ✓ | ✓ | — | ✓ |
| Mark task done | — | ✓ | ✓ | ✓ | — | ✓ |
| Triage, assign, set severity | — | — | ✓ | ✓ | — | ✓ |
| Manage backlog (categorize, rank, promote) | — | — | ✓ | ✓ | — | ✓ |
| Create and edit milestones | — | — | ✓ | ✓ | — | ✓ |
| Set estimates | — | — | — | ✓ | — | ✓ |
| Set hard deadlines | — | — | — | ✓ | — | ✓ |
| Enable milestone scheduling | — | — | — | ✓ | — | ✓ |
| Create and delete dependencies | — | — | ✓ | ✓ | — | ✓ |
| Release go/no-go decision | — | — | — | — | ✓ | ✓ |
| View all projects and reports | — | — | — | — | ✓ | ✓ |
| Manage users, projects, calendar | — | — | — | — | — | ✓ |

Where a role lacks a capability, the control is shown disabled with an explanatory tooltip rather than hidden. Hidden controls create confusion about whether a feature exists.

---

## 8. Functional Requirements

### 8.1 Work items

**FR-1** Users can create a work item of type Bug or Task from a single form with a type selector.

**FR-2** Every work item belongs to exactly one project. Work with no natural home is filed under the seeded General project.

**FR-3** At creation the user chooses placement: Backlog, Release, or Milestone. A release and a milestone may both be chosen.

**FR-4** Bugs follow the Phase 1 workflow: New → Triaged → In progress → Ready for QA → Verified → Closed, with a Regression path from Ready for QA or Verified back to In progress.

**FR-5** Tasks follow a separate workflow: To do → In progress → In review → Done, with a Blocked state and a Cancelled terminal state.

**FR-6** Boards that mix bugs and tasks display five unified columns: To do, In progress, In review, Done, Blocked. Each type's statuses map onto these columns.

**FR-7** Moving a card between unified columns applies the correct status for that card's type.

**FR-8** Work items carry three estimation fields: estimate hours (planning baseline), remaining hours (live), and actual hours (captured at completion).

**FR-9** On completion the system prompts for actual hours, pre-filled with the estimate. The prompt is skippable.

**FR-10** The item detail view displays computed scheduling values — start, finish, float, critical-path flag — as read-only, visually distinct from editable fields.

### 8.2 Backlog

**FR-11** Each project has a backlog containing all its work items that belong to neither a release nor a milestone and are not completed.

**FR-12** Backlog items carry a required category: Technical debt, Feature request, Improvement, or Future work.

**FR-13** The backlog is presented as a ranked list, not a board. Users reorder by dragging.

**FR-14** Users can group the backlog by category or view it as a flat ranked list.

**FR-15** Users can promote one or many items from the backlog into a release or milestone in a single action.

**FR-16** Promotion does not change an item's status. A promoted item retains its workflow state.

**FR-17** The backlog displays hygiene signals: an age badge on items older than 90 days, and a header statistic reporting how many items have been untouched for over six months.

**FR-18** A "Stale" filter surfaces only items untouched for over six months.

### 8.3 Milestones

**FR-19** Users can create milestones within a project. Each has a key, name, goal statement, owner, and lifecycle status.

**FR-20** Milestone lifecycle: Draft → Planned → In progress → Completed, with On hold and Cancelled as alternative states. Lifecycle status is set manually.

**FR-21** Milestones may optionally have a start date and a hard deadline.

**FR-22** Milestone progress is calculated from estimated hours, not item count. When estimates are incomplete the system falls back to a count-based percentage and labels which method was used.

**FR-23** Milestone health is computed automatically and is never user-editable. Values: On track, At risk, Critical, Overdue, or Not tracked when no deadline exists.

**FR-24** Lifecycle status and health are displayed as visually distinct badges and never merged.

**FR-25** A milestone detail view offers a Board tab, an Items table, an Activity timeline, and — when scheduling is enabled — a Gantt tab.

### 8.4 Scheduling and dependencies

**FR-26** A milestone owner can enable scheduling, which activates dependency management, critical path calculation, and the Gantt view.

**FR-27** Scheduling can only be enabled when the milestone has a start date and every non-cancelled item in it has an estimate.

**FR-28** When enablement is blocked, the system lists exactly which items lack estimates and offers inline entry.

**FR-29** Users can create finish-to-start dependencies between items in the same milestone, optionally with a lag in hours.

**FR-30** The system prevents dependency cycles and, when one is attempted, displays the chain that would close the loop.

**FR-31** The system automatically identifies the critical path and calculates float for every item.

**FR-32** All schedule calculations honour the company working calendar and public holidays.

**FR-33** The Gantt view displays bars split across non-working days, the critical path highlighted, float shown as a trailing indicator, a hard deadline marker, and dependency connectors.

**FR-34** Schedule recalculation is automatic and triggered by any change to estimates, remaining hours, dependencies, item membership, milestone dates, or the working calendar.

### 8.5 Personal work view

**FR-35** Every user has a My Work view showing all items assigned to them across every project, release, and milestone.

**FR-36** My Work uses the five unified columns and offers a list alternative.

**FR-37** Every card in My Work displays a project chip and a container chip (release or milestone, or "Backlog").

**FR-38** My Work shows a summary strip: total assigned, due this week, overdue, and on critical path.

### 8.6 Working calendar

**FR-39** The system maintains a company working calendar defining hours available per weekday. Default: Saturday through Wednesday 8 hours, Thursday 4 hours, Friday non-working — 44 hours per week.

**FR-40** Public holidays are fetched automatically from an external national holidays service. Administrators do not enter or maintain them.

**FR-41** The holidays list is read-only in the interface, displays dates in both Jalali and Gregorian, and shows a last-synced timestamp with a manual refresh control.

**FR-42** Administrators may separately define company-specific non-working days, clearly distinguished from the synced national list.

**FR-43** Changing the working week or refreshing holidays recalculates every scheduled milestone. The system warns how many milestones will be affected before applying.

---

## 9. Business Rules

Numbered for reference in test cases and acceptance criteria.

### Placement and hierarchy

**BR-01** Every work item belongs to exactly one project at all times. Project cannot be null.

**BR-02** Work with no natural project home belongs to the seeded General project.

**BR-03** The General project supports milestones and a backlog but cannot have releases.

**BR-04** A work item may belong to a release, a milestone, both, or neither.

**BR-05** A work item belonging to neither a release nor a milestone, and not completed, is by definition in its project's backlog. Backlog membership is never set explicitly.

**BR-06** A work item's release and milestone must belong to the same project as the item.

**BR-07** Changing an item's project is only permitted when the item has no release, no milestone, and no dependencies.

### Type and workflow

**BR-08** A work item's type is fixed at creation and can never be changed. Converting a bug to a task means creating a new task and closing the bug.

**BR-09** Bug-specific fields (severity, release blocker, reproduction steps, cURL, environment) are unavailable on tasks.

**BR-10** Severity is required on bugs and absent on tasks.

**BR-11** Only bugs can be flagged as release blockers.

**BR-12** Only bugs pass through Ready for QA and Verified. Only bugs can be flagged as regressions.

**BR-13** Status transitions are constrained per type. Invalid transitions are rejected with the allowed set displayed.

### Backlog

**BR-14** Backlog category is required whenever an item is in the backlog.

**BR-15** Promoting an item out of the backlog is a placement change only. It never alters the item's status.

**BR-16** An item demoted back to the backlog retains its previous category and returns to its prior rank position.

**BR-17** Completed items never appear in the backlog regardless of their placement.

**BR-18** Backlog rank is unique within a project and is maintained by drag-ordering.

### Estimation

**BR-19** Estimate hours is the planning baseline and freezes when the parent milestone leaves Draft status.

**BR-20** Changing a frozen estimate requires a written reason, is recorded as a re-baseline event in the activity timeline, and is surfaced in variance reporting.

**BR-21** Remaining hours defaults to the estimate when an estimate is set, and to null otherwise.

**BR-22** Remaining hours may be updated freely by the assignee and by triage leads, project managers, and admins.

**BR-23** Every change to remaining hours is recorded in the activity timeline with old and new values.

**BR-24** Reaching a Done or Verified status sets remaining hours to zero automatically.

**BR-25** Actual hours is captured once at completion. It is optional but prompted every time.

**BR-26** Estimate variance is only calculated for items with both an estimate and an actual.

### Milestones

**BR-27** A milestone key is unique within its project. The same key may exist in different projects.

**BR-28** A milestone goal statement is required before the milestone can leave Draft.

**BR-29** A milestone must have an owner at all times.

**BR-30** Milestone health only exists when a hard deadline is set. Without one, health reads Not tracked and no health alerts are produced.

**BR-31** Milestone health is computed by the system and can never be set manually.

**BR-32** A milestone On hold freezes its health at the last computed value and suppresses health alerts until resumed.

**BR-33** A Cancelled milestone is excluded from all progress, health, and reporting calculations.

**BR-34** Marking a milestone Completed while non-cancelled items remain open requires confirmation and a reason, recorded in the timeline.

**BR-35** Milestone progress is calculated from estimated hours. When any active item lacks an estimate, the system uses item count and labels the method.

**BR-36** Cancelled items are excluded from milestone progress calculations.

### Scheduling

**BR-37** Scheduling can only be enabled when the milestone has a start date and every non-cancelled item has an estimate.

**BR-38** While scheduling is enabled, adding an item without an estimate to the milestone is rejected.

**BR-39** While scheduling is enabled, clearing an item's estimate is rejected.

**BR-40** Dependencies used for scheduling must connect two items in the same milestone.

**BR-41** Dependencies are finish-to-start only. No other dependency type exists.

**BR-42** A dependency may not create a cycle in the dependency graph.

**BR-43** An item may not depend on itself.

**BR-44** Duplicate dependencies between the same pair of items are rejected.

**BR-45** Computed values — start date, finish date, float, and critical-path flag — are system-owned and never user-editable.

**BR-46** Schedule duration is calculated from remaining hours, not estimate hours, so the timeline self-corrects as work progresses.

**BR-47** Completed items contribute zero duration but still anchor their successors at their recorded finish.

**BR-48** An item is on the critical path when its float is zero or negative.

**BR-49** When multiple dependency paths have equal length, all of them are marked critical.

### Calendar

**BR-50** All schedule arithmetic uses working hours from the company calendar. No calculation uses raw calendar days.

**BR-51** A public holiday overrides the weekday hours for that date, reducing available hours to zero.

**BR-52** A holiday falling on an already non-working day has no additional effect.

**BR-53** Public holidays are read-only and sourced from the external service. The product never asks an administrator to enter them.

**BR-54** Company-specific non-working days are maintained separately and are additive to the synced national list.

**BR-55** A change to the working week or holiday list triggers recalculation of every affected scheduled milestone.

---

## 10. Edge Cases

Each case states the situation and the required behaviour.

### Work items

**EC-01 — Item completed then reopened.**
Reopening restores the item to In progress. Remaining hours resets to the actual hours if recorded, otherwise to the original estimate. Actual hours is cleared and will be prompted again at the next completion. The reopen is recorded in the timeline. If the item is in a scheduled milestone, the schedule recalculates.

**EC-02 — Estimate of zero hours.**
Permitted. The item appears on the Gantt as a zero-duration milestone marker (a diamond, not a bar) and can still anchor dependencies. Useful for checkpoints.

**EC-03 — Very large estimate.**
An estimate above 80 hours triggers a soft warning at entry: "This is over two working weeks. Consider splitting it." The user may proceed. No hard limit.

**EC-04 — Remaining hours exceeds original estimate.**
Permitted and expected. The Gantt bar renders at the remaining length and displays both values, making drift visible. The variance report flags the item. No block, no warning dialog — over-run is information, not an error.

**EC-05 — Remaining set to zero while status is not Done.**
The item contributes zero duration to the schedule but remains open on the board. The Gantt shows a zero-length marker with a "no time remaining but not complete" indicator. This is a legitimate state for work that is finished but awaiting review.

**EC-06 — Item unassigned while in a scheduled milestone.**
Permitted. Scheduling is resource-blind, so an unassigned item schedules identically to an assigned one. The Gantt row shows an empty avatar slot.

**EC-07 — Item reassigned mid-flight.**
Permitted at any status. The schedule is unaffected. The new assignee receives a notification; the previous assignee receives a notice that the item has moved away from them.

**EC-08 — Bug regresses while inside a milestone.**
The bug returns to In progress, remaining hours resets to the original estimate (a regression means the work must be redone), regression count increments, and the milestone schedule recalculates. Milestone progress decreases, which is correct and should not be hidden.

**EC-09 — Item is deleted while acting as a dependency predecessor.**
Deletion is blocked. The system reports which items depend on it and requires those dependencies to be removed first.

**EC-10 — Item cancelled while on the critical path.**
Cancellation is permitted. Its dependencies are automatically removed, successors are re-linked to the cancelled item's predecessors where a chain existed, and the schedule recalculates. The critical path may shift. A notification goes to the milestone owner.

**EC-11 — Item moved to a different project.**
Blocked unless the item has no release, no milestone, and no dependencies. The error explains which of the three is blocking.

### Backlog

**EC-12 — Bulk promotion where some items lack estimates, into a scheduled milestone.**
The operation is rejected as a whole rather than partially applied. The system lists which items lack estimates and offers inline entry, then re-attempts. Partial application would leave the milestone in a state where scheduling is silently broken.

**EC-13 — Item demoted from a milestone back to the backlog while it has dependencies.**
The system warns that dependencies will be removed and requires confirmation. On confirm, dependencies are deleted and the milestone reschedules.

**EC-14 — Backlog item completed without ever being promoted.**
Permitted. Someone fixed a small piece of technical debt directly. The item leaves the backlog because completed items are excluded, and appears in reporting attributed to no release and no milestone.

**EC-15 — Two users reorder the backlog simultaneously.**
Last write wins on the specific item moved. Other items retain their positions. The second user's view refreshes to show the resulting order. No lock, no conflict dialog — reordering is low-stakes and a conflict prompt would be more disruptive than the conflict.

**EC-16 — Backlog item promoted, then demoted, then promoted again.**
Category and rank persist through the whole cycle. The item returns to its original backlog position each time.

**EC-17 — Backlog grows beyond 500 items in one project.**
The list paginates and the header displays a prominent hygiene prompt: "This backlog has grown large. Consider a grooming session." The quarterly digest escalates in tone.

### Milestones

**EC-18 — Milestone with zero items.**
Progress reads 0% with the label "No items yet." Health is Not tracked regardless of whether a deadline exists, because there is nothing to schedule. Scheduling cannot be enabled.

**EC-19 — Milestone where every item is cancelled.**
Progress reads "No active items." The milestone can be marked Completed or Cancelled. Health is suppressed.

**EC-20 — Hard deadline set to a date in the past.**
Permitted with a warning at entry. Health immediately computes as Overdue. This is a legitimate case when recording a deadline that was already missed.

**EC-21 — Hard deadline removed after being set.**
Health changes to Not tracked, existing health alerts stop, and no "recovered" notification is sent. The change is recorded in the timeline with the actor, because silently removing a deadline is a significant governance event.

**EC-22 — Start date set later than the hard deadline.**
Blocked at entry with a clear error. This is always a data entry mistake.

**EC-23 — Milestone start date is in the past.**
The scheduler anchors to today rather than the historical start date, so projected dates remain meaningful. The Gantt displays the original start date as a faded marker for reference.

**EC-24 — Milestone put On hold, then resumed after its deadline has passed.**
On resume, health recalculates immediately and will read Overdue. A notification goes to the owner and CTO on resume. Health does not silently remain at its frozen value.

**EC-25 — Milestone owner is deactivated.**
The milestone remains valid but is flagged in the milestones list as "Owner inactive." Health alerts route to the project's admins until a new owner is assigned. Reassignment is prompted on next view by an admin or PM.

**EC-26 — Milestone deleted while containing items.**
Deletion requires confirmation. All items return to the backlog with their categories preserved where previously set, or defaulted to Future work where not. All dependencies among them are removed. Items already completed are unaffected and simply lose their milestone association.

**EC-27 — Milestone marked Completed while items remain open.**
Requires a confirmation dialog with a mandatory reason. On confirm, open items return to the backlog rather than being force-closed. The reason is recorded in the timeline and appears in the milestone report.

**EC-28 — Two milestones in the same project given the same key.**
Blocked. Keys are unique per project. The same key in a different project is permitted.

**EC-29 — Estimates set while a milestone is in Draft, then the milestone moves to Planned.**
All estimates freeze at that moment. Subsequent changes require a reason and count as re-baselines.

### Scheduling and dependencies

**EC-30 — Every item in a scheduled milestone is complete.**
Projected finish equals the finish date of the last completed item. The critical path is empty. Progress reads 100%. Health computes normally and will read On track or Overdue depending on whether the finish preceded the deadline. The Gantt renders historical bars.

**EC-31 — A milestone with a single item and no dependencies.**
That item is the critical path. Float equals the slack against the deadline.

**EC-32 — Disconnected dependency sub-graphs within one milestone.**
Fully supported. Each chain schedules independently from the milestone start. The critical path is the longest chain. Shorter chains carry float.

**EC-33 — Two dependency paths of exactly equal length.**
Both are marked critical. Every item on both paths is highlighted.

**EC-34 — A dependency cycle is attempted.**
Rejected before creation. The system displays the ordered chain of item titles that would form the loop, so the user can see exactly where the conflict lies.

**EC-35 — A dependency is created where the predecessor is already complete.**
Permitted. The predecessor's recorded finish date anchors the successor, which may therefore be able to start immediately.

**EC-36 — A very deep dependency chain, for example twenty levels.**
Supported. The Gantt scrolls. A soft warning appears above eight levels suggesting the milestone may be too large to manage as one unit.

**EC-37 — A public holiday is added retroactively in the middle of an active scheduled milestone.**
All affected bars shift right on the next recalculation. If the shift pushes the projected finish past the deadline, health degrades and the owner is notified with a reason: "Schedule changed due to a calendar update."

**EC-38 — The working week configuration is changed.**
Every scheduled milestone recalculates. Before applying, the system reports how many milestones will change and how many will change health state. Requires confirmation.

**EC-39 — Remaining hours on a critical path item increases.**
The projected finish moves later. If health degrades, the owner and CTO are notified with the specific item named. This is the earliest available signal of deadline risk and must not be suppressed or batched away.

**EC-40 — An item in progress has not had its remaining hours updated in over two weeks.**
The item is flagged as stale on the Gantt and in the milestone view. The assignee receives a gentle reminder. Schedule accuracy depends entirely on remaining hours being current, so staleness is a first-class signal.

**EC-41 — A dependency is attempted between items in different milestones.**
Rejected with an explanation, and the system offers to create an informational "related work" link instead, which carries no schedule effect.

**EC-42 — Scheduling is disabled on a milestone that has dependencies.**
Dependencies are retained but become informational. Computed dates, float, and critical-path flags are cleared. Re-enabling scheduling recalculates from scratch. A confirmation explains this.

### Calendar and holidays

**EC-43 — The holidays service is unavailable during a scheduled sync.**
The last successfully synced data continues to be used. A warning banner appears on the calendar settings screen showing the last successful sync time. Scheduling continues to function. Retry follows a backoff schedule. After 72 hours without a successful sync, admins are notified.

**EC-44 — The holidays service returns a newly announced holiday in the near future.**
Treated as a normal calendar change. Affected milestones recalculate and health changes are notified with the reason attributed to the calendar update.

**EC-45 — A holiday falls on Friday, already a non-working day.**
No additional effect. Available hours for that date were already zero. The holiday still displays in the calendar list for completeness.

**EC-46 — A holiday falls on Thursday, a half day.**
The holiday overrides. Available hours become zero, not four.

**EC-47 — A multi-day holiday period such as Nowruz.**
Each day arrives as a separate entry. The Gantt renders the whole span as one continuous non-working block.

**EC-48 — A company-specific closure coincides with a public holiday.**
No double counting. Available hours are zero. Both entries display in the calendar list, with the source of each indicated.

### Permissions

**EC-49 — A developer attempts to set an estimate.**
The field is visible but disabled with a tooltip: "Estimates are set by the project manager."

**EC-50 — A QA engineer files a task rather than a bug.**
Fully permitted. All roles can file both types.

**EC-51 — A user updates remaining hours on an item not assigned to them.**
Blocked for QA and developer roles. Permitted for triage leads, project managers, and admins.

**EC-52 — The CTO attempts to edit a work item.**
Blocked. The CTO role is read-only except for the release go/no-go decision. The interface makes this visible rather than failing on submit.

### Notifications

**EC-53 — A notification is due for a user who has not connected Telegram.**
The notification is skipped silently for the recipient. The user's profile and the team settings screen show an unconnected warning. No error is raised and no fallback channel is used.

**EC-54 — Milestone health oscillates between At risk and On track repeatedly.**
Health notifications are edge-triggered and additionally debounced: no more than one health notification per milestone per six hours. Oscillation is a signal of a milestone sitting exactly on a threshold and should not produce message spam.

**EC-55 — A bulk operation triggers many notifications at once.**
Notifications from a single bulk action are batched into one message per recipient summarising the change, rather than one message per item.

**EC-56 — A due-soon notification is scheduled for an item that has since been completed.**
Suppressed at send time. The check happens at delivery, not at scheduling.

**EC-57 — An item is reassigned.**
The new assignee receives an assignment notification. The previous assignee receives a brief notice. If the item is reassigned twice within a short window, only the final state generates messages.

### Migration from Phase 1

**EC-58 — Existing bugs after migration.**
All become type Bug with no estimate, no milestone, and no backlog category. They remain in their existing releases exactly as before. Nothing about the Phase 1 experience changes.

**EC-59 — An existing bug is added to a scheduled milestone.**
Blocked until an estimate is provided, consistent with BR-38. The inline estimate entry flow handles this.

**EC-60 — An existing closed bug is moved to the backlog.**
Not possible. Completed items are excluded from the backlog by definition. To track follow-up work, a new task should be created and linked as related.

---

## 11. Notifications

Telegram is the only delivery channel. There is no email in the product.

### Phase 2 events

| Event | Recipients | Trigger |
|---|---|---|
| Task assigned | Assignee | Assignment or reassignment |
| Task unassigned | Previous assignee | Reassignment away |
| Task blocked | Assignee, milestone owner | Status becomes Blocked |
| Task due soon | Assignee | 24 hours before due date, daily sweep |
| Task overdue | Assignee, milestone owner | Due date passed while incomplete |
| Remaining hours stale | Assignee | Item in progress, remaining unchanged 14 days |
| Critical path slip | Milestone owner, CTO | Remaining hours increases on a critical item |
| Milestone health degraded | Milestone owner | Health moves to a worse state |
| Milestone overdue | Milestone owner, CTO | Health becomes Overdue |
| Milestone completed | Owner, CTO, all assignees | Status becomes Completed |
| Calendar change impact | Owners of affected milestones | Working week or holidays changed the schedule |
| Backlog item promoted | New assignee | Item moved from backlog into a container |
| Backlog digest | Project leads | Quarterly, oldest and stalest items |

### Delivery rules

Health notifications are edge-triggered — sent on transition, never on recalculation. Additional debounce of six hours per milestone prevents threshold oscillation from producing spam. Bulk actions produce one summary message per recipient. Scheduled notifications re-check their condition at delivery time. Users without a connected Telegram account are skipped silently.

---

## 12. Reporting

### Milestone performance

Milestones grouped by health across a project. Deadline performance: delivered on time versus late, trended by quarter. Average slack at completion.

### Estimate accuracy

Planned versus actual hours, aggregated per milestone, per assignee, and team-wide. Presented as a trend over time rather than per item, because single-item variance is noise.

Framing matters here. A team estimating at 60% accuracy is not working badly — it is estimating badly, which is a separate and fixable problem. Report copy should reflect that, and the metric should never appear in a per-person ranking format.

### Backlog flow

Items added to the backlog versus promoted out, per month. Age distribution. Composition by category, which answers "how much technical debt is this project carrying."

### Cross-phase view

Bugs versus tasks completed per release cycle. Where a team's time actually goes: fixing defects, delivering planned work, or paying down debt.

---

## 13. Non-Functional Requirements

**NFR-1** Schedule recalculation for a milestone of up to 200 items completes within two seconds.

**NFR-2** Recalculation is debounced so that bulk edits do not trigger repeated recomputation.

**NFR-3** The Gantt view renders a 200-item milestone without perceptible lag and supports smooth horizontal scrolling across a twelve-month span.

**NFR-4** My Work loads within one second for a user with up to 200 assigned items across all projects.

**NFR-5** Public holidays sync daily. A failed sync degrades gracefully to the last known good data.

**NFR-6** All dates display in Jalali in the interface with Gregorian available on hover or in a secondary line, consistent with the rest of the platform.

**NFR-7** All schedule computation is deterministic. The same inputs always produce the same output.

**NFR-8** Every state change to a work item or milestone is recorded in an immutable activity timeline with actor and timestamp.

---

## 14. Rollout Plan

**Stage 1 — Foundation.** Tasks as a work item type, task workflow, unified board columns, My Work view, and the General project. The team can immediately stop managing tasks in direct messages.

**Stage 2 — Backlog.** Per-project backlog with categories, ranking, promotion, and hygiene signals. Nothing gets lost between releases.

**Stage 3 — Milestones without scheduling.** Milestones with goals, lifecycle, owners, progress, and boards. Goals become measurable before dates are introduced.

**Stage 4 — Scheduling and Gantt.** Estimates, dependencies, critical path, working calendar, holiday sync, health, and the Gantt view. The heaviest stage and the one most dependent on the earlier ones being adopted.

**Stage 5 — Reporting.** Milestone performance, estimate accuracy, backlog flow.

Staging matters here. Introducing the Gantt before the team is habitually filing tasks in the system would produce an empty and misleading chart. Each stage should be adopted before the next is enabled.

---

## 15. Assumptions & Open Questions

### Assumptions

The team runs Kanban and does not want sprints, story points, or velocity. Sequencing of one person's parallel work is expressed manually by the project manager through dependencies rather than by a capacity model. Estimates are provided by the project manager, not negotiated by the team. The national holidays service is reliable enough for daily sync with graceful degradation. Most milestones will not use scheduling; it is reserved for genuinely deadline-critical work.

### Open questions

**Q1** — Should completed milestones remain visible in the milestones list by default, or move to an archive view after a period?

**Q2** — When a release ships, should its unfinished items automatically return to the backlog, remain attached to the shipped release, or prompt for a decision? Phase 1 has no defined behaviour here and Phase 2 makes it more visible.

**Q3** — Should the backlog be shared across projects for a "global" grooming view, or strictly per project? Currently specified as per project.

**Q4** — Should there be a soft warning when a milestone accumulates more items than a suggested threshold, in the same spirit as the deep dependency chain warning?

**Q5** — Should estimate accuracy be visible to individual contributors for their own work, or restricted to project managers and above?

---

## 16. Glossary

**Actual hours** — the hours a completed item really took, captured at completion.

**Backlog** — work items in a project belonging to neither a release nor a milestone and not completed.

**Bug** — a work item representing a defect, passing through QA verification.

**Critical path** — the chain of dependent items determining the earliest possible milestone finish. Items on it have zero or negative float.

**Estimate hours** — the original planned duration, frozen when the milestone leaves Draft.

**Float** — spare working hours an item has before it begins delaying the milestone.

**Hard deadline** — a milestone's committed completion date, set by its owner.

**Health** — an automatically computed signal of whether a milestone will meet its deadline.

**Lifecycle status** — a milestone's manually set state, distinct from health.

**Milestone** — a goal with a set of work items that deliver it.

**Projected finish** — the computed earliest completion date for a milestone.

**Release** — a shipping event with a version and a ship date.

**Remaining hours** — live hours left on an item, updated by the assignee, driving the schedule.

**Slack** — working hours between a milestone's projected finish and its hard deadline.

**Task** — a work item representing planned development work, with no QA verification step.

**Work item** — the umbrella term covering both bugs and tasks.
