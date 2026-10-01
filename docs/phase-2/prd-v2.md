# Releasewatch Phase 2 — Product Requirements Document (v3)

> **Product:** Releasewatch
> **Phase:** 2 — Organization-wide work management
> **Status:** Draft for review — supersedes Phase 2 PRD v1, v2, v2.1 and v2.2. The file keeps its name so that existing links from the slice specs stay valid.
> **Owner:** CTO
> **Companion documents:** [Cycle Model](cycle-model.md) · [Search & Ranking Engine](prd-search-engine.md)

---

## Table of Contents

0. [Changes](#0-changes)
1. [Overview](#1-overview)
2. [What Changed from v1](#2-what-changed-from-v1)
3. [Problem Statement](#3-problem-statement)
4. [Goals & Non-Goals](#4-goals--non-goals)
5. [Product Principles](#5-product-principles)
6. [Scope](#6-scope)
7. [Roles & Permissions](#7-roles--permissions)
8. [Domain Model](#8-domain-model)
9. [Status Model](#9-status-model)
10. [Functional Requirements](#10-functional-requirements)
11. [Business Rules](#11-business-rules)
12. [Acceptance Criteria & Edge Cases](#12-acceptance-criteria--edge-cases)
13. [Notifications](#13-notifications)
14. [Reporting](#14-reporting)
15. [Deliberate Limitations](#15-deliberate-limitations)
16. [Deferred to Phase 3](#16-deferred-to-phase-3)
17. [Open Points for Review](#17-open-points-for-review)
18. [Glossary](#18-glossary)

---

## 0. Changes

### v3

Phase 1 started where QA started: a release already existed and its bugs were being tested. Phase 2 v3 moves Releasewatch back to the point where work is **planned**, and models how work actually reaches production: either continuously, one item at a time, or together as a planned delivery.

| Area | v2.2 | v3 |
|---|---|---|
| Milestones | Goal containers beside releases, with lifecycle, deadline and progress | **Removed.** A release already has a deadline, a lifecycle and a ship date |
| Containers | Release (Product projects only) and Milestone; an item could be in both | **Stream** (one per project, always open, each item ships on its own) and **Releases** (planned deliveries that ship together). An item is in at most one container |
| Project kinds | Product, Internal, General (seeded) | **Removed.** Every project has the same model: one Stream and any number of Releases |
| Hotfix | An Accept with no release; outside regression tracking | **Not a separate concept.** An urgent item is an item in the Stream with a high priority or a pin. It passes the same QA gate as everything else |
| QA gate | Bugs verified in In review; tasks could go In progress → Done directly | **One gate for bugs and tasks:** In progress → In review → Done by verification. A rejected item goes back to **To do** |
| Regression | A flag and a count on bugs; a direct action limited to unshipped releases; a merge path for Done bugs | **Cycles** for bugs and tasks. Every return opens a new cycle whose `start_reason` says where the problem was caught: review, release QA, or production. Defined in [cycle-model.md](cycle-model.md) |
| Returns from production | Only through a triage merge, only into bugs | Triage merge into a **bug or a task**, or a direct **Problem on production** action on a shipped item |
| Release lifecycle | Phase 1: active, released, blocked, archived | Planning → Development → QA → Released, or Cancelled. Shipping moves every item that is not Done to the backlog |
| Backlog | Items with no release and no milestone | Items with no container. A backlog item cannot be started; it is placed in the Stream or a Release first |
| Bulk status changes | Not specified | **None anywhere.** Placement can still be changed in bulk from the backlog |
| Phase 2 reports | Support intake, technical debt, backlog flow, hotfix volume | **Moved to Phase 3** with all cycle metrics. Phase 1 reports keep working with unchanged meaning |

Removed: FR-21, FR-22, FR-30–32, BR-02, BR-17, BR-24 (replaced), BR-25, BR-26 (replaced), BR-27, BR-29 (replaced), AC-16, AC-26 (replaced), §8.8, §8.9 (replaced), §10.5, §10.8 (replaced), §14 Phase 2 reports.
Changed: §1–§9, FR-02, FR-03, FR-05, FR-16, FR-18, FR-23, FR-25, FR-29, FR-35, FR-39, FR-42, BR-03–06, BR-13, BR-20, BR-23, BR-28, BR-45, BR-47–50, AC-24, AC-25, AC-35, AC-45, AC-46, AC-49–54, §13, §15–§18.
Added: FR-46–FR-66, BR-51–BR-66, AC-55–AC-78.

### v2.2

| Area | v2.1 | v2.2 |
|---|---|---|
| Urgent flag | A flag, a triage outcome ("Accept as urgent"), a queue tier, a card marker and a notification | **Removed everywhere.** Importance is priority; "do this first" is a pin in the personal queue |
| Importance | `severity` for bugs (Blocker/Critical/Major/Minor), `priority` 1–4 for tasks | **One `priority`** for both types: Critical, High, Medium, Low. Empty until triage for bugs; Medium by default for tasks |
| Release blocker | A flag | Unchanged, and it now carries what "Blocker severity" used to mean |

### v2.1

v2.1 added the Search & Ranking Engine (a separate document) and the merge of a returning bug into its original in triage. v3 keeps the merge and generalizes its effect into cycles.

---

## 1. Overview

Phase 1 made Releasewatch the place where release bugs are reported, triaged, fixed, verified, and tracked for regressions. It starts when QA starts, and it has been adopted across the organization.

Phase 2 turns Releasewatch into the **single place where all technical work in the organization is recorded and followed up, from planning to production**: planned deliveries that ship together, the continuous flow of small tasks and fixes that ship one at a time, bugs reported by the support team, and technical debt. Every item, bug or task, passes one QA gate, and every time work comes back it is recorded as a new cycle. Every person on the technical team gets one prioritized queue across all the projects they work on.

Phase 2 is an expansion of the same product — one data model, one interface, one notification channel (Telegram).

---

## 2. What Changed from v1

| Area | v1 | v3 |
|---|---|---|
| Scheduling | Gantt, CPM, dependencies, working calendar in Phase 2 | **Moved to Phase 3**, on Releases |
| Estimation | Estimate / remaining / actual, freeze rules | **Moved to Phase 3** |
| Milestones | Containers with scheduling and computed health | **Removed** (v3). Releases carry deadline, lifecycle and progress |
| Statuses | Two workflows mapped onto five columns | **One unified status set** and one QA gate for bugs and tasks |
| Support reports | Not covered | **Support intake** via templates, per-project triage queue |
| Triage | Global Triage Lead role | **Per-project triage lead**; any developer can triage |
| Technical debt | A backlog category | **A flag on tasks** with its own page, hidden from the default backlog |
| My Work | Unified-column board | **Personal board** with a prioritized cross-project queue, pins, and queue history |
| Out-of-release work | Implicit | **The Stream**: continuous delivery, one item at a time (v3) |
| Returning work | Regression status on release bugs | **Cycles** with a start reason, for bugs and tasks (v3) |
| Search | Phase 1 search | **Search & Ranking Engine** with optional Jev (v2.1) |

---

## 3. Problem Statement

**Delivery is not tracked before QA.** Releasewatch starts when a release enters QA. How the work was planned, who built it, and whether it was on time is recorded nowhere.

**Most work is not a release.** On most projects tasks arrive every day or two and go to production one at a time. Some work is a planned set of tasks that must ship together. Only the second kind has a home today.

**Small bugs and tasks** found by the technical team are tracked inconsistently because they do not belong to a big release.

**Support-reported bugs** arrive in a Telegram group. Follow-up is hard, reports often lack the data needed to investigate (for an online-class problem: the class time, the class, the affected user), and there is no structured decision on whether a report is fixed immediately, scheduled, or rejected.

**Rework is invisible.** When QA sends work back, or a fix fails on production, nothing records it except for bugs in a release.

**Technical debt** identified by the team or the CTO is not recorded anywhere, so it is forgotten by the time there is capacity to address it.

**Personal priority** is unclear. A developer with items in five projects sees five "top priority" items — one per project — and has no answer to "what do I work on right now?"

---

## 4. Goals & Non-Goals

### Goals

1. **Visibility** — the CTO can see who is working on what, across all projects.
2. **Nothing ownerless** — every request, report, and piece of work has a recorded owner and state.
3. **Personal prioritization** — each person has one ordered queue across projects, which the person and the CTO/Admin can shape.
4. **Structured support intake** — support reports arrive with the data needed to act on them and pass through triage.
5. **Technical debt register** — debt is recorded once and remains findable without cluttering daily work.
6. **Delivery from planning to production** — continuous and planned delivery are both tracked, every item passes one QA gate, and every return is recorded with where it was caught.

### Non-Goals

- Task management for non-technical departments (sales, finance, etc.). Only the technical team is assigned work.
- Integration with NEXT or any other company system. Releasewatch stays independent.
- Time tracking or timesheets.
- Individual performance scoring.
- Resource capacity planning.
- Bulk status changes.

---

## 5. Product Principles

**P1 — Simplicity over structure.** Releasewatch's advantage over Jira is simplicity. When a structured field and free text both serve the need, free text wins. Every added field, state, or setting must justify itself.

**P2 — General by design.** Releasewatch is installed for one organization, but nothing specific to this organization is hardcoded. Organization-specific concepts (customer ID, working calendar values) are configuration, not product. Every project follows the same model.

**P3 — Signals only when they matter.** Importance signals appear on a card only when there is a reason to look. A normal card is just its title.

**P4 — The person's queue is the execution order.** Project plans describe intent; a person's queue decides what they do next.

**P5 — Record what happened, where it happened.** Status is the current state; events such as a return are recorded once, at the moment they happen, with the facts of that moment. Nothing is recomputed later from a state that may have changed.

---

## 6. Scope

### In scope

- Unified work items (bugs and tasks) with one status set and one QA gate
- One **Stream** per project and any number of **Releases** per project
- Release lifecycle, go/no-go, ship, progress, and overdue
- Per-project backlog
- Cycles: rejects, release-QA returns, and returns from production, for bugs and tasks
- Support role and support intake through per-project templates
- Per-project triage queue with defined outcomes
- Recurrence counter for repeated reports
- Merge of a returning report into its original (bug or task)
- Technical debt flag and Tech Debt page
- Personal board: prioritized queue, pins, queue history, list and Kanban views
- Team overview for CTO/Admin
- Telegram notifications for all new events
- Search & Ranking Engine, similar-item suggestions, and optional Jev — see [prd-search-engine.md](prd-search-engine.md)

### Out of scope for Phase 2 — see [Section 16](#16-deferred-to-phase-3)

Gantt, CPM, dependencies, working calendar, holidays, estimation fields, release health, and every new report (including cycle metrics).

---

## 7. Roles & Permissions

### 7.1 Roles

| Role | Description |
|---|---|
| **Support** | Reports bugs through templates. Sees all support-reported items. Is never assigned work |
| **QA Engineer** | Files bugs and tasks, verifies and rejects delivered work |
| **Developer** | Files bugs and tasks, works assigned items, triages |
| **Project Manager** | Manages backlog and releases |
| **CTO** | Reads everything, release go/no-go and ship, shapes any person's queue |
| **Admin** | Everything, plus users, projects, templates, and search settings |

"Tech team" means every role except Support.

### 7.2 Project triage lead

**Triage lead** is a per-project designation, not a role. Each project has exactly one triage lead, chosen from QA, Developer, PM, CTO, or Admin users. The triage lead is notified of and responsible for the project's triage queue, and may manage and ship the project's releases. Any Developer, QA, PM, CTO, or Admin may perform triage; only the triage lead is notified.

### 7.3 Permission matrix

| Capability | Support | QA | Dev | PM | CTO | Admin |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| Submit a support report via template | ✓ | — | — | — | — | ✓ |
| File a bug or task directly | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| View support-reported items | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| View non-support items | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Public comment | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Internal (tech-only) note | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Report recurrence | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Triage (including merge) | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Be assigned work | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Move own items through workflow | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Verify delivered work (In review → Done) | — | ✓ | ✓¹ | ✓ | ✓ | ✓ |
| Reject delivered work (In review → To do) | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Return a Done item from release QA | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Report a problem on production | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Flag / unflag technical debt | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Manage backlog and releases | — | — | ✓² | ✓ | ✓ | ✓ |
| Release go/no-go | — | — | — | — | ✓ | ✓ |
| Ship a release | — | ✓² | ✓² | ✓² | ✓ | ✓ |
| Reorder / pin own queue | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Reorder / pin anyone's queue | — | — | — | — | ✓ | ✓ |
| View anyone's personal board and team overview | — | — | — | — | ✓ | ✓ |
| Manage templates | — | — | — | — | ✓ | ✓ |
| Manage users and projects | — | — | — | — | — | ✓ |
| Manage search settings and Jev | — | — | — | — | — | ✓ |

¹ A person cannot verify an item they sent to review themselves.
² Only as the project's triage lead.

Where a role lacks a capability, the control is shown disabled with a tooltip rather than hidden. The exception is Support: tech-only screens, internal notes, and tech-only actions are not shown to Support at all.

---

## 8. Domain Model

Product-level description of entities and attributes.

### 8.1 Project

Name · Key · Triage lead · Templates · Stream (exactly one, created with the project) · Releases

There are no project kinds. Every project follows the same model (P2).

### 8.2 Work item

**Shared:** ID (`BUG-042`, `TASK-118`) · Type (Bug / Task, fixed at creation) · Title · Description (markdown) · Project · **Container** (the project's Stream or one of its Releases; empty = backlog) · Status · **Priority** (Critical, High, Medium, Low) · Reporter · Assignee · Labels · Due date (optional) · Attachments · Timeline (comments, internal notes, system events) · Lifecycle dates (filed, triaged, started, review requested, verified, completed, cancelled) · **Cycles** (§8.9)

**Bug only:** Source (Internal / Support) · Recurrence count · Release blocker flag · Reproduction steps · cURL · Environment · Cancel reason · Duplicate of (when cancelled as duplicate)

**Task only:** Technical debt flag

**Backlog only:** Backlog category (Default, Feature request, Improvement, Future work) · Backlog rank

### 8.3 Support template

Project · Name · Active flag · Ordered fields. Each field has: Label · Type (short text, long text, number, date, date-time, single select, URL) · Required · Help text.

Template fields are not stored as item fields. On submission they are **composed into the item description** as a labeled, structured block.

### 8.4 Recurrence

Item · Reported by · Date · Comment (required). Each recurrence increments the item's recurrence count and adds a public comment to its timeline.

### 8.5 Personal queue

One per assignable user. Ordered list of that user's open assigned items. Each entry may carry a **pin** (pinned by self or by CTO/Admin).

### 8.6 Queue history entry

User · Actor · Action (reorder, pin, unpin) · Item · Old position · New position · Date. Stored with the queue, **never** in the item timeline.

### 8.7 Containers: Stream and Release

A **container** is where an item is delivered from. Every project has exactly one Stream and any number of Releases.

**Stream** — Project · (nothing else). Created with the project. It cannot be renamed, edited, cancelled, archived, or deleted, and it is always open. Every item in the Stream ships on its own: **Done in the Stream means on production.** The Stream has no lifecycle, go/no-go, release blocker, container deadline, or progress. Items in it carry their own due dates.

**Release** — Project · Name (version) · Description · Lifecycle status (Planning, Development, QA, Released, Cancelled) · Code freeze date (optional; QA starts) · Target ship date (optional) · Go/No-go (decision, note, by, at) · Released at · Staging URL · Progress (computed: Done items ÷ non-cancelled items). Its items ship together when the release is shipped: **a Done item in a Released release is on production.**

### 8.8 Milestone

*(Removed in v3.)*

### 8.9 Cycle

One pass of work on an item until it is delivered: picked up, worked, sent to review, verified. A cycle belongs to one item and one container. The first cycle starts when the item is placed in a container, and each later cycle starts because the work came back. The cycle records **why it started** (`start_reason`: planned, review, release QA, production), who delivered its work, and its timing. The full model is in [cycle-model.md](cycle-model.md).

---

## 9. Status Model

### 9.1 Unified statuses

One status set for both types. Bugs have two additional pre-board statuses.

| Group | Status | Bug | Task | Meaning |
|---|---|:-:|:-:|---|
| Triage | **New** | ✓ | — | Awaiting triage |
| Triage | **Needs info** | ✓ | — | Waiting on the reporter |
| Board | **To do** | ✓ | ✓ | Accepted or placed, not started |
| Board | **In progress** | ✓ | ✓ | Being worked on |
| Board | **In review** | ✓ | ✓ | Delivered to QA, waiting for verification |
| Board | **Done** | ✓ | ✓ | Verified. In the Stream: on production. In a Release: on production once the release is Released |
| Board | **Blocked** | ✓ | ✓ | Cannot proceed |
| Terminal | **Cancelled** | ✓ | ✓ | Closed without being done, always with a reason |

**Kanban columns** are the five Board statuses. New and Needs info live in the triage queue. Cancelled items appear in no board.

There is no Returned or Rejected status. An item that came back is in To do (and later In progress) with a **returned marker** (FR-63).

### 9.2 Flags (not statuses)

| Flag | Applies to | Set by |
|---|---|---|
| Release blocker | Bugs in a Release (not the Stream) | QA, triage lead, PM, CTO, Admin |
| Technical debt | Tasks | Any tech user |

The v2 Regression flag and count are replaced by cycles (§8.9).

### 9.3 Transitions

```
Bug:   New ──triage──▶ To do ──▶ In progress ──▶ In review ──▶ Done
        │   ▲           ▲ ▲                         │            │
        ▼   │           │ └──── reject (review) ────┘            │
     Needs info         └────── return (release QA / production) ┘
        │
        └──────────────▶ Cancelled (from New, Needs info, To do, Blocked)

Task:  To do ──▶ In progress ──▶ In review ──▶ Done     (same reject and return paths)
                     ▲   │
                     └── Blocked                (any non-Done ──▶ Cancelled)
```

- **In progress requires a container.** A backlog item is placed in the Stream or a Release first (BR-53).
- **In progress → Done directly is not allowed** for either type. Every item passes In review and verification.
- Any board status except Done may move to Blocked; Blocked returns to the status it came from or To do.
- **Every return goes to To do**, not In progress. The assignee picks the item up again by moving it to In progress.
- Done is final, except for the release-QA return (FR-59) and the production return (FR-60, BR-49).

---

## 10. Functional Requirements

### 10.1 Work items

**FR-01** Tech users create a bug or a task from one form with a type selector. The type cannot be changed later.

**FR-02** Every item belongs to exactly one project.

**FR-03** At creation the user chooses placement: Backlog, the project's Stream, or one of the project's open Releases.

**FR-04** Every bug, whether filed by the tech team or by support, is created in **New** and enters its project's triage queue.

**FR-05** Tasks are created in **To do** in the chosen placement. They do not pass through triage.

**FR-06** Item detail shows a single chronological timeline of public comments, internal notes, and system events. Internal notes are visually distinct and never shown to Support.

### 10.2 Support intake

**FR-07** Support opens **New report**, selects a project, then selects a template of that project.

**FR-08** The project list shows only projects with at least one active template.

**FR-09** The form renders the template's fields plus a required title, an optional free description, and attachments. Required fields must be filled before submission.

**FR-10** On submission, a bug is created in the chosen project with status New, source Support, no container, and a description composed of the template name, each field label and value in template order, then the free description.

**FR-11** Support sees a **Support reports** list containing every support-sourced item across all projects, with status, project, recurrence count, and last update. Search by text and filter by project and status.

**FR-12** While Jev is enabled, the support form shows a **similar reports** panel with the project's open support reports that describe the same problem, and lets Support record a recurrence on one of them instead of filing a new report. Defined in [Search & Ranking Engine](prd-search-engine.md) (FR-S09–FR-S11). While Jev is disabled, the panel is not shown.

### 10.3 Recurrence

**FR-13** Any user can press **Report recurrence** on an open or Cancelled bug. A comment is required; it is where new customer information goes.

**FR-14** Reporting a recurrence increments the recurrence count, adds the comment to the timeline, and subscribes the recurrence reporter to support notifications for that item.

**FR-15** On a Cancelled item, a recurrence notifies the project's triage lead. It does not reopen the item.

**FR-16** On a Done item, the button is disabled with the hint: "Fixed items can't take a recurrence. File a new report; triage will merge it into this item and send it back for a fix." A shortcut opens a new report with this item's ID prefilled in the description, so the triager sees the link even when no suggestion is shown.

### 10.4 Triage

**FR-17** Each project has a **Triage queue** listing its New and Needs info bugs, oldest first, with source, reporter, and recurrence count.

**FR-18** Triage outcomes:

| Outcome | Result |
|---|---|
| **Accept** | Status To do. Choose placement: Backlog (with a category), the Stream, or an open Release. Assignee optional. **Priority required** |
| **Needs info** | Status Needs info. A public comment stating what is missing is required |
| **Duplicate (merge)** | Status Cancelled (reason Duplicate). Choose the original item: a **bug or a task** in the same project. The duplicate's reporter is subscribed to the original, and the duplicate's title and description are added to the original as a public comment. When the original is a bug, its recurrence count increases by one. The effect on the original depends on its status (BR-49) |
| **Reject** | Status Cancelled with reason: User error, Expected behavior, or Cannot reproduce |

**FR-19** When the reporter (or any Support user) comments on an item in Needs info, the item returns to New and the triage lead is notified.

**FR-20** The triage lead can change the item's project during triage. The item moves to the new project's queue and that project's triage lead is notified.

### 10.5 Hotfix path

*(Removed in v3. FR-21 and FR-22 no longer exist. Urgent work is an item in the Stream with a high priority or a pin.)*

### 10.6 Backlog

**FR-23** The backlog is a ranked list, not a board, of the items in a project that have no container and are not Done or Cancelled.

**FR-24** Technical-debt items are **hidden from the backlog by default**. A toggle "Show technical debt" reveals them.

**FR-25** Backlog supports grouping by category, drag ranking, multi-select, and bulk move to the Stream or an open Release. This is a placement change, not a status change.

### 10.7 Technical debt

**FR-26** Any tech user can flag a task as technical debt at creation or later. No additional fields: affected components, risk, and approach go in the description.

**FR-27** The main navigation has a **Technical debt** page: a list of all flagged tasks with filters for project (multi-select), status, and assignee. Selecting one project gives the project view; several give a cross-project view.

**FR-28** Each project page links to the Technical debt page pre-filtered to that project.

**FR-29** Once a technical-debt task is assigned or placed in the Stream or a Release, it appears on boards and in queues like any task. The flag remains.

### 10.8 Milestones

*(Removed in v3. FR-30–FR-32 no longer exist. Their progress, overdue, and page requirements now apply to Releases: FR-50–FR-52.)*

### 10.9 Personal board (My Work)

**FR-33** Every assignable user has a personal board containing all their assigned items that are not Done or Cancelled, across all projects.

**FR-34** **List view:** a horizontal-card list. An "In progress" group on top, then the **queue** in queue order.

**FR-35** **Kanban view:** the five board columns. Within each column, cards follow queue order. The Done column shows items completed in the last 7 days.

**FR-36** Queue order is: pinned items (in their pin order), then all other items in manual or default order.

**FR-37** **Default order** for unpinned items: priority (Critical, High, Medium, Low; items with no priority last), then due date (earliest first, none last), then recurrence count (highest first), then age (oldest first).

**FR-38** The user can drag items to reorder their queue. A CTO or Admin can reorder any user's queue.

**FR-39** A newly assigned item is inserted by the default rule: it is placed directly above the first item that ranks lower under the default order, even if the queue has been manually ordered. A **returned** item is not new: it follows FR-64.

**FR-40** The user can pin up to **4** items. CTO or Admin can pin items in any user's queue, within the same limit. A pin set by CTO/Admin shows a lock and cannot be removed by the user.

**FR-41** Every reorder, pin, and unpin — by anyone — is recorded in the user's **Queue history**, visible to that user and to CTO/Admin. Queue history never appears in the item timeline.

**FR-42** Cards show only title, project chip, and a priority icon by default. Additional compact markers appear only when relevant: pinned, returned (FR-63), recurrence count > 1, due within 2 days or overdue, technical debt. Hovering a card shows full details (all markers spelled out, age, container, reporter).

### 10.10 Team overview

**FR-43** CTO and Admin have a **Team** page listing each assignable user with their In progress items, top three queue items, and counts of open and pinned items. Selecting a user opens their personal board with reorder and pin controls.

### 10.11 Templates administration

**FR-44** CTO and Admin manage templates per project: create, edit, reorder fields, activate, and deactivate.

**FR-45** Editing or deactivating a template affects only future submissions. Existing items keep their composed descriptions.

### 10.12 Stream

**FR-46** Every project has exactly one Stream, created with the project and shown as the project's first container. It cannot be renamed, edited, cancelled, archived, or deleted.

**FR-47** The Stream page has a five-column Board and an Items table. The Done column shows, by default, items completed in the **last 7 days**. A time picker changes the range: relative presets (last 7, 30, 90 days, or last *N* days) and an absolute range (from date to date). The range filters only the Done column; open columns always show everything.

**FR-48** An item in the Stream that reaches Done is on production at that moment.

### 10.13 Releases

**FR-49** PM, CTO, Admin, and the project's triage lead create and edit releases: name (version), description, code freeze date, target ship date, staging URL.

**FR-50** Release lifecycle:

| From | To | How |
|---|---|---|
| Planning | Development | Manual |
| Development | QA | Manual (code freeze) |
| QA | Development | Manual (back to development) |
| QA | Released | **Ship** only (FR-53) |
| Planning, Development, QA | Cancelled | Manual, only when the release has no Done item (BR-55) |

Released and Cancelled are final.

**FR-51** The release page has a Board tab (five columns), an Items table, and an Activity tab (lifecycle changes, date changes, items added or removed, go/no-go decisions, ship). It shows progress (Done ÷ non-cancelled items) and, when the target ship date has passed and the release is not Released or Cancelled, an **Overdue** marker.

**FR-52** The release page shows the open release blockers. The CTO or Admin records **go** or **no-go** with an optional note.

**FR-53** **Ship.** CTO, Admin, and the project's triage lead can ship a release in QA. Before confirming, a notice shows the go/no-go decision and the number of items that are not Done, by status (for example "3 To do, 1 In progress, 1 In review"). Shipping does not require every item to be Done. On confirmation:
- the release becomes Released and records the ship time;
- every Done item is on production;
- every item that is not Done moves to the **backlog** with category **Default** and status **To do**, keeping its assignee and pins; its cycles are deleted (BR-62).

**FR-54** A Released release keeps its Board, Items, and Activity tabs read-only.

### 10.14 QA gate and returns

**FR-55** Moving an item from In progress to In review delivers it to QA. The system records who delivered the work: the item's **assignee** at that moment, never the person who changed the status (BR-63).

**FR-56** **Verify:** In review → Done, by someone other than the person who sent it to review.

**FR-57** **Reject:** In review → To do, with a required comment explaining what is wrong. A new cycle starts with reason `review`.

**FR-58** A backlog item cannot be moved to In progress. The control is disabled with the hint "Place this item in the Stream or a release first."

**FR-59** **Return from release QA:** on a Done item in a Release that is not yet Released, a tech user can return it with a required comment. The item goes to To do in the same release, and a new cycle starts with reason `release_qa`.

**FR-60** **Problem on production:** on a shipped item (Done in the Stream, or Done in a Released release), every tech user sees **Problem on production**. A required comment explains the problem. The item goes to To do and a new cycle starts with reason `production`. If its container is a Released release, the item moves to the Stream. Support does not see this action; Support reports a new problem through a new report, which triage merges (BR-49).

**FR-61** Every return (FR-57, FR-59, FR-60, and a merge per BR-49) acts on one item at a time and records its reason comment on the timeline.

**FR-62** There are no bulk status changes anywhere in the product.

**FR-63** **Returned marker.** An item whose current cycle started with a return, and which has not yet been sent to In review again, shows a compact marker on rows and cards in To do and In progress: where it was caught (review, release QA, production) and the return number (for example "returned 2"). Hover shows the reason comment.

**FR-64** A returned item goes back to the **position it had in its assignee's queue before it left**, but never above the pinned items. An item rejected from In review never left the queue, so it keeps its place.

**FR-65** A return notifies the assignee with where it was caught and the reason comment.

**FR-66** An item's timeline shows its cycles: when each started and why, who delivered it, when it was verified.

---

## 11. Business Rules

### Placement

**BR-01** Every work item belongs to exactly one project. Project is never empty.

**BR-02** *(Removed in v3: there are no project kinds; see BR-51.)*

**BR-03** An item's container must belong to the item's project. An item is in at most one container.

**BR-04** An item with no container that is not Done or Cancelled is in the backlog. Backlog membership is never set explicitly.

**BR-05** Changing an item's project is allowed only when it has no container.

**BR-06** Backlog category is required for backlog items; technical-debt tasks are exempt. Items moved to the backlog by a ship get category **Default**.

### Type and status

**BR-07** Item type is fixed at creation.

**BR-08** Source, recurrence, release blocker, reproduction steps, cURL, and environment exist only on bugs.

**BR-09** The technical debt flag exists only on tasks. Priority is shared by both types.

**BR-10** New and Needs info exist only for bugs.

**BR-11** Every bug starts in New, regardless of who files it.

**BR-12** Tasks start in To do.

**BR-13** Cancelled always carries a reason. Bug reasons: User error, Expected behavior, Cannot reproduce, Duplicate, Won't fix. Task reason: No longer needed.

**BR-14** Invalid transitions are rejected and the allowed transitions are shown.

### Triage

**BR-15** Every project has exactly one triage lead. A project cannot be saved without one.

**BR-16** Priority must be set when a bug is accepted. A bug in New or Needs info may have no priority; a task is created with Medium.

**BR-17** *(removed in v2.2.)*

**BR-18** Needs info requires a public comment stating what is missing.

**BR-19** A reporter or Support comment on a Needs info item returns it to New.

**BR-20** A duplicate must reference an item (bug or task) in the same project that is not itself a cancelled duplicate.

**BR-21** Cancelled items are never reactivated. A recurrence after rejection must be reported again or recorded as a recurrence comment.

### Recurrence, merge, and returns

**BR-22** A recurrence requires a comment and increments the recurrence count by exactly one. Recurrence exists only on bugs.

**BR-23** Recurrence is not allowed on Done items. A problem with a Done item is reported as a new report and merged in triage (BR-49), or, by the tech team, with **Problem on production** (FR-60).

**BR-24** *(Replaced in v3.)* The direct regression action no longer exists. Work comes back through a reject (FR-57), a release-QA return (FR-59), a production return (FR-60), or a merge (BR-49). Each starts a new cycle ([cycle-model.md](cycle-model.md)).

**BR-25** *(Removed in v3. Component fragility is a Phase 1 report; its behavior is unchanged in Phase 2 and its redesign is in Phase 3.)*

**BR-49** **Merge effects by the original's status.** When a report is merged into an original (Duplicate outcome):
- **New, Needs info, To do, In progress, In review, Blocked:** the original's status does not change.
- **Done, not shipped** (in a Release that is not Released): the original returns to To do and a new cycle starts with reason `release_qa`.
- **Done, shipped** (in the Stream, or in a Released release): the original returns to To do and a new cycle starts with reason `production`. If its container is a Released release, it moves to the Stream.
- **Cancelled:** the original stays Cancelled and the triage lead is notified, as for a recurrence on a Cancelled item (FR-15).

**BR-50** Merge is one operation with one set of effects on the original: the merged report's content added as a public comment, the merged report's reporter subscribed, and, when the original is a bug, recurrence count +1. The Duplicate outcome in triage and a recurrence recorded from the similar reports panel (FR-12) both produce these effects; only the Duplicate outcome creates and cancels a second item.

### Delivery

**BR-26** *(Replaced in v3.)* An item reaches Done only inside a container (it cannot be started without one, BR-53).

**BR-27** *(removed in v2.2.)*

### Verification

**BR-28** Items go In review → Done only by verification. The person who moved the item to In review cannot verify it.

**BR-29** *(Replaced in v3.)* Tasks do not go In progress → Done directly. Bugs and tasks pass the same QA gate.

### Visibility

**BR-30** Support users see only support-sourced items, and only public comments on them.

**BR-31** Internal notes are never shown to Support, in any view or notification.

**BR-32** Support users cannot be assigned items.

### Templates

**BR-33** A project appears in the support form only if it has at least one active template.

**BR-34** Template field values are composed into the description at submission and are not stored or searchable as separate fields.

**BR-35** Template changes never alter existing items.

### Technical debt

**BR-36** Only tasks can be flagged as technical debt.

**BR-37** Technical-debt tasks are excluded from the default backlog view but not from boards, queues, or search once assigned or placed.

### Personal queue

**BR-38** A queue contains only the user's assigned items that are not Done or Cancelled.

**BR-39** Queue order is always: pinned, then the rest.

**BR-40** At most 4 pinned items per user, including locked pins.

**BR-41** A pin set by CTO/Admin can be removed only by CTO/Admin.

**BR-42** Only the queue owner and CTO/Admin can reorder or pin. Triage leads and PMs cannot.

**BR-43** When CTO/Admin reorders or pins in someone's queue, that user is notified.

**BR-44** Queue history is append-only and stored separately from item timelines.

**BR-45** When an item is unassigned or reassigned, it leaves the previous owner's queue (pins included) and enters the new owner's queue by the default rule.

**BR-46** When a pinned item reaches Done or Cancelled, its pin is released.

### Releases

**BR-47** Release progress = Done items ÷ non-cancelled items.

**BR-48** Overdue is shown only when a target ship date exists, has passed, and the release is not Released or Cancelled.

### Containers, QA gate, and cycles (v3)

**BR-51** Every project has exactly one Stream, created with the project. The Stream cannot be edited, cancelled, archived, or deleted.

**BR-52** **Shipped.** A Done item in the Stream is on production. A Done item in a Released release is on production.

**BR-53** An item can move to In progress only when it has a container.

**BR-54** A Done item never changes container.

**BR-55** A release that has at least one Done item cannot be cancelled.

**BR-56** Shipping a release requires no condition on its items. It moves every item that is not Done to the backlog (category Default, status To do).

**BR-57** A Released release never holds an open item. An item returned from production whose container is a Released release moves to the Stream.

**BR-58** The release blocker flag applies only to bugs in a Release.

**BR-59** Every return (reject, release-QA return, production return, merge into Done) requires a reason, acts on one item, and starts a new cycle.

**BR-60** There are no bulk status changes.

**BR-61** A returned item re-enters its assignee's queue at its previous position, never above the pinned items (FR-64).

**BR-62** A cycle exists only while the item has a container. The first cycle starts when the item is placed in a container, with reason `planned`. Moving an item to the backlog deletes all of its cycles; placing it again starts from cycle 1.

**BR-63** "Who delivered the work" is the item's assignee at the moment it moved to In review. It is never the actor of the status change and never falls back to the actor.

**BR-64** The container of an open cycle follows the item. A Done item does not move (BR-54), so the container of delivered work is fixed.

**BR-65** The reason a cycle started is recorded when it starts and is never recomputed.

**BR-66** A backlog item is placed in a container before anyone can start it. Placement and starting are separate actions.

---

## 12. Acceptance Criteria & Edge Cases

### Support intake

**AC-01** Given a project with no active template, when Support opens New report, then the project is not listed.

**AC-02** Given a template with a required date-time field left empty, when Support submits, then submission is blocked and the field is highlighted.

**AC-03** Given a completed submission, then a bug exists in the chosen project with status New, source Support, and a description listing each field label and value in template order followed by the free description.

**AC-04** Given an Admin edits a template's fields, then items submitted earlier keep their original description unchanged.

**AC-05** Given a template is deactivated while a Support user has the form open, when they submit, then they are told the template is no longer available and their entered values are preserved on screen.

**AC-06** Given a project's only active template is deactivated, then the project disappears from the support form; existing items in it remain visible to Support.

**AC-07** Given a Support user, when they view any support item, then no internal note appears in the timeline, counts, or previews.

**AC-08** Given a Support user, then tasks and internally filed bugs never appear in their lists or search.

### Recurrence

**AC-09** Given an open bug, when a user presses Report recurrence without a comment, then the action is blocked.

**AC-10** Given an open bug with recurrence count 3, when a recurrence is reported, then the count is 4 and the comment appears in the timeline.

**AC-11** Given a Cancelled bug, when a recurrence is reported, then the count increments, the triage lead is notified, and the status stays Cancelled.

**AC-12** Given a Done bug, then Report recurrence is disabled with guidance to file a new report that triage will merge, and the shortcut opens a report with the item's ID prefilled.

**AC-13** Given two users report a recurrence at the same moment, then the count increases by two.

### Triage

**AC-14** Given a developer files a bug, then it is created in New and appears in the project's triage queue, not on boards.

**AC-15** Given a New bug, when any Developer (not the triage lead) accepts it, then the acceptance succeeds and the triage lead is not required to act.

**AC-16** Given Accept without a priority, then the action is blocked.

**AC-17** Given "Needs info" without a comment, then the action is blocked.

**AC-18** Given an item in Needs info, when its Support reporter comments, then the status becomes New and the triage lead is notified.

**AC-19** Given an item in Needs info, when a Developer comments, then the status does not change.

**AC-20** Given a triager marks bug A as duplicate of bug B, then A is Cancelled with reason Duplicate, B's recurrence count increases by one, and A's reporter receives B's future support notifications.

**AC-21** Given a triager tries to mark A as duplicate of an item that is itself a duplicate, then the action is blocked and the original item is suggested.

**AC-22** Given a triager moves a New bug to another project, then it appears in the new project's queue and the new project's triage lead is notified.

**AC-23** Given a project whose triage lead user is deactivated, then the project is flagged in Admin settings and triage notifications go to Admin until a new lead is set.

### QA gate and returns

**AC-24** Given a bug accepted into the Stream, when it is verified, then it is Done and on production.

**AC-25** Given a Done bug in a Release in QA, when QA returns it from release QA with a comment, then it is To do in the same release and its current cycle has reason `release_qa`.

**AC-26** Given a Done task in the Stream, when a developer reports a problem on production with a comment, then it is To do in the Stream and its current cycle has reason `production`.

**AC-27** Given a developer moved an item to In review, when the same developer tries to verify it, then the action is disabled with an explanation.

### Merge

**AC-49** Given B is In progress with recurrence count 2, when bug A is merged into B, then A is Cancelled (Duplicate), B's status is unchanged, B's recurrence count is 3, and B's timeline shows a public comment containing A's title and description.

**AC-50** Given B is a Done item in the Stream, when A is merged into B, then B is To do in the Stream and its current cycle has reason `production`.

**AC-51** Given B is a Done item in Release R that is in QA, when A is merged into B, then B is To do in R and its current cycle has reason `release_qa`.

**AC-52** Given B is In review, when A is merged into B, then B stays In review and no cycle starts.

**AC-53** Given B is Cancelled, when A is merged into B, then B stays Cancelled, its recurrence count increments, and the triage lead is notified.

**AC-54** Given A's Support reporter, when A is merged into a Done B that later reaches Done again, then the reporter receives B's Done notification.

### Technical debt

**AC-28** Given a technical-debt task in the backlog, when the backlog opens with default settings, then the task is not listed; with "Show technical debt" enabled, it is.

**AC-29** Given the Technical debt page with two projects selected, then only flagged tasks from those two projects are listed.

**AC-30** Given a technical-debt task is assigned to a developer, then it appears in their queue with the technical debt marker.

**AC-31** Given a user tries to flag a bug as technical debt, then the control is not available.

### Personal queue

**AC-32** Given a user has 4 pins, when they try to pin a fifth, then the action is blocked with a message naming the limit.

**AC-33** Given the CTO pins an item in a user's queue, then the user sees a lock on it, cannot unpin it, and receives a notification.

**AC-34** Given a user's queue has 4 pins, 3 of them self-set, when the CTO tries to add a pin, then the CTO is told the limit is reached and must unpin one first.

**AC-35** Given a manually ordered queue, when a new High bug is assigned, then it is placed directly above the first item ranking lower than it by the default rule.

**AC-36** Given a queue with pins, when a Critical item is assigned, then it appears below all pins and above every lower-priority unpinned item.

**AC-37** Given the CTO reorders a user's queue, then the change appears in that user's Queue history with actor, item, and positions, and the item's own timeline shows nothing.

**AC-38** Given a pinned item is reassigned to another user, then the pin is released, the item leaves the first queue, and enters the second by the default rule.

**AC-39** Given a pinned item reaches Done, then its pin is released and the pin slot becomes free.

**AC-40** Given a PM or triage lead views another user's board, then reorder and pin controls are not available.

**AC-41** Given the Kanban view, then within each column, cards follow the same order as the list view.

**AC-42** Given an item was completed 8 days ago, then it does not appear in the Done column.

### Card signals

**AC-43** Given an item with recurrence count 1, no due date, not pinned, not returned, and not technical debt, then its card shows only title, project chip, and priority icon.

**AC-44** Given an item overdue by one day, then the card shows a compact overdue marker, and hovering shows the date in full.

### Releases

**AC-45** Given a release with 10 items, 2 cancelled and 4 done, then progress is 50%.

**AC-46** Given a release with no target ship date, then no Overdue marker ever appears.

### Visibility and permissions

**AC-47** Given a Support user, then no assignee picker lists Support users.

**AC-48** Given the Team page, when viewed by a Developer, then access is denied.

### Containers (v3)

**AC-55** Given a new project, then it has exactly one Stream, and the Stream cannot be renamed, cancelled, or deleted.

**AC-56** Given a task in the backlog, when a developer tries to move it to In progress, then the action is refused with the hint to place it first.

**AC-57** Given a task in In progress, when a developer tries to move it directly to Done, then the action is refused and In review is offered.

**AC-58** Given a Done item in a Release in QA, when a PM tries to move it to the Stream or another release, then the move is refused.

**AC-59** Given a release with one Done item, when a PM tries to cancel it, then the action is refused.

**AC-60** Given a release in QA with 5 Done, 2 To do, 1 In progress, and 1 In review item, when the CTO opens Ship, then the notice shows "2 To do, 1 In progress, 1 In review" and the go/no-go decision.

**AC-61** Given the release in AC-60 is shipped, then it is Released; the 5 Done items are on production; the other 4 items are in the backlog with category Default and status To do, keep their assignees, and have no cycles.

**AC-62** Given a release in Planning, then Ship is not available.

**AC-63** Given the Stream's Done column, then it shows items completed in the last 7 days by default, and the time picker can show the last 30 days or a date range.

**AC-64** Given a Released release, when a Done item in it gets a problem on production, then the item is To do in the Stream and the release still has no open item.

**AC-65** Given a bug in the Stream, then the release blocker control is not available.

### QA gate and cycles (v3)

**AC-66** Given an item in In review, when QA rejects it without a comment, then the action is blocked.

**AC-67** Given an item in In review, when QA rejects it with a comment, then it is To do, its current cycle has reason `review`, its assignee is notified with the comment, and its card shows "returned 1".

**AC-68** Given a returned item in To do, when the assignee moves it to In progress, then the returned marker is still shown; when they move it to In review, the marker disappears.

**AC-69** Given item X assigned to developer D, when the CTO moves X from In progress to In review, then the cycle records D, not the CTO, as the person who delivered the work.

**AC-70** Given an unassigned item, when an Admin moves it to In review, then the cycle records nobody as the person who delivered the work.

**AC-71** Given a Done item in the Stream, when a Support user opens it, then **Problem on production** is not shown.

**AC-72** Given a Done item in the Stream, when a developer presses Problem on production without a comment, then the action is blocked.

**AC-73** Given an item in the Stream with two cycles, when a PM moves it to the backlog, then it has no cycles; when it is placed in a release again, its current cycle is cycle 1 with reason `planned`.

**AC-74** Given an item at position 3 of its assignee's queue that reaches Done and later returns from production, then it re-enters the queue at position 3, or directly below the pins if fewer unpinned items now precede it.

**AC-75** Given an item that was first in its assignee's queue when it reached Done, and the assignee has since pinned 2 items, when the item returns, then it is placed directly below the 2 pins, never above them.

**AC-76** Given any list or board, then no control changes the status of several items at once.

**AC-77** Given bug A (Support) is merged into a Done task T in the Stream, then T is To do in the Stream with a `production` cycle, T has no recurrence count, and A's reporter is subscribed to T.

**AC-78** Given a bug filed by QA directly into Release R, then it has cycle 1 with reason `planned` while it is still New in the triage queue.

---

## 13. Notifications

Telegram is the only channel. There is no email.

### To Support (reporter, recurrence reporters, and reporters of merged duplicates)

| Event | Content |
|---|---|
| Needs info | What information is missing |
| Cancelled | Reason |
| Done | Item is fixed |

No other status changes are sent to Support. A return of a Done item sends nothing to Support; its subscribers hear again when it reaches Done.

### To the project's triage lead

- New item in the triage queue
- Reporter replied on a Needs info item (item returned to New)
- Recurrence reported on a Cancelled item, or a report merged into one
- Item moved into their project during triage

### To the assignee

- Item assigned
- Item due within 24 hours / overdue
- CTO/Admin reordered their queue, pinned, or unpinned an item
- Item returned (reject, release QA, or production), with the reason comment

### To the CTO

- Release go/no-go events (Phase 1, unchanged)
- Release passed its target ship date without being Released (once per date; a later date notifies again)

---

## 14. Reporting

Phase 1 reports remain available with **unchanged meaning**: release report, regressions and component fragility, time to fix, contributions, dashboard. Where their data moves (regressions now live in cycles), they are adapted so they produce the same numbers for Phase 1 data: fragility and regression counts read the cycles of **bugs** in **Releases** that started with `review` or `release_qa`, which is exactly what Phase 1 recorded.

Every new report is deferred to Phase 3 (§16), including support intake, technical debt, backlog flow, and every cycle metric.

---

## 15. Deliberate Limitations

These are conscious trade-offs, not gaps.

| Limitation | Reason |
|---|---|
| Template field values are not filterable or reportable | They live in the description (P1) |
| No triage deadline, and no auto-close for Needs info | May be added later |
| No resource capacity planning | Unchanged from v1 |
| Customer ID is not a core field | Generality (P2); add it to templates when needed |
| Cancelled items are never reopened | Clear history; recurrence covers the signal |
| Similar-item suggestions exist only while Jev is enabled | Suggestions without a reliable same-problem judgment would be ignored (see the engine document) |
| No bulk status changes | A status change is a claim about the work (verified, on production, rejected). It is made one item at a time |
| Moving an item to the backlog deletes its cycles, including a production return | When work is planned again, its earlier cycles are not relevant. The rare escaped item that is later moved to the backlog loses its escape record; revisited in Phase 3 |
| An item is in at most one container | Items that must ship together are one release; cross-release features are followed with labels |

---

## 16. Deferred to Phase 3

**Scheduling and estimation (from v1), now on Releases:**
- Gantt view
- Critical Path Method scheduling (finish-to-start dependencies only, optional lag, no dependency reason field)
- Dependencies between items
- Working calendar and public holidays
- Estimation fields (original estimate, remaining, actual), the freeze rule (estimates freeze when a release leaves Planning), and the actual-hours completion prompt
- Computed release health with alerts
- Critical-path marker on cards

**Reports:**
- Support intake, technical debt, and backlog flow reports
- Cycle metrics: review rejects, release-QA catches, escapes, escape rate, first-pass rate, cycles per item, pickup wait (defined in [cycle-model.md](cycle-model.md) §5)
- Component fragility redesign: whether task cycles and production returns count
- Whether any metric is shown per developer (the data exists; individual performance scoring is a non-goal)
- Estimate-accuracy and release-performance reports

**Cycles:**
- Keeping a production return when an escaped item is later moved to the backlog (today its cycles are deleted)

**Decisions carried into Phase 3:**
- The working calendar and holiday source are **organization settings** (P2). The current values become defaults: Saturday–Wednesday 8h, Thursday 4h, Friday non-working (44h/week); public holidays from an external API, read-only.
- **The personal queue outranks the critical path** (P4). The Gantt only *displays* when a critical-path item sits low in its assignee's queue; this has no effect on the calculation and adds no workflow.

---

## 17. Open Points for Review

Choices made in this document that were not explicitly discussed:

1. **Needs info auto-return (BR-19)** — a reporter's comment returns the item to New. Without this, answered items could stay in Needs info unnoticed.
2. **"Won't fix" cancel reason (BR-13)** — added for accepted bugs that are later abandoned.
3. **Team overview (FR-43)** — added to serve the goal "CTO sees who works on what."
4. **Deactivated triage lead (AC-23)** — triage notifications fall back to Admin until a new lead is set.
5. **Merge into an In review item (BR-49)** — the original stays In review. A new report while the fix awaits verification is expected (the fix is not deployed yet). If verification shows the fix does not work, QA rejects it as usual.
6. *(v3)* **In review means "delivered to QA".** If the team also does code review before QA, it happens inside In progress (for example in the pull request), so that a code-review rejection is not counted as a QA reject.
7. *(v3)* **Who works the QA side.** QA is not per person (the item's assignee stays the developer). A per-project view of items in In review may be needed so that QA work is visible.
8. *(v3)* **Support's Done notification for items in a Release** is sent when the item is verified, before the release ships. Sending it at ship time instead would match "fixed on production".
9. *(v3)* **Ship without go.** Shipping shows the go/no-go decision but does not require **go**.
10. *(v3)* **UI names of return reasons.** Proposed: `review` = Reject, `release_qa` = Regression, `production` = Escape.
11. *(v3)* **Release lifecycle transitions (FR-50)** are proposed, including QA → Development.

---

## 18. Glossary

| Term | Meaning |
|---|---|
| Work item | Any bug or task |
| Priority | The shared importance scale: Critical, High, Medium, Low |
| Container | Where an item is delivered from: the project's Stream or one of its Releases |
| Stream | The one always-open container per project; each item ships on its own when Done |
| Release | A planned delivery; its items ship together when it is shipped |
| Ship | Releasing a Release: its Done items are on production, its other items go to the backlog |
| Backlog | A project's items with no container that are not Done or Cancelled |
| Cycle | One pass of work on an item until delivered; see [cycle-model.md](cycle-model.md) |
| Start reason | Why a cycle started: planned, review, release QA, or production |
| Return | Work coming back: a reject, a release-QA return, a production return, or a merge into a Done item. Starts a new cycle |
| Returned marker | The card marker on an item whose current cycle started with a return and which has not been sent to review again |
| Support report | A bug submitted by Support through a template |
| Template | A per-project set of fields Support must fill, composed into the description |
| Triage queue | A project's New and Needs info bugs |
| Triage lead | The person notified of and responsible for a project's triage queue |
| Recurrence | A repeated report of an existing open or cancelled bug, with a required comment |
| Merge | Folding a duplicate report into its original (bug or task): content as comment, reporter subscribed, recurrence +1 for bugs |
| Technical debt | A task flagged as debt; hidden from the default backlog |
| Personal queue | One person's ordered list of open assigned items across all projects |
| Pin | A guaranteed top position in a queue; at most 4 per person |
| Queue history | Log of reorders and pins on a person's queue |
| Similar-item suggestion | An engine-proposed existing item that may describe the same problem |
