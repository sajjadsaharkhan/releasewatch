# Releasewatch Phase 2 — Product Requirements Document (v3.1)

> **Product:** Releasewatch
> **Phase:** 2 — Organization-wide work management
> **Status:** Draft for review — supersedes Phase 2 PRD v1, v2, v2.1, v2.2 and v3. The file keeps its name so that existing links from the slice specs stay valid.
> **Owner:** CTO
> **Companion documents:** [Cycle Model](cycle-model.md) · [Search & Ranking Engine](prd-search-engine.md) · [MCP](prd-mcp.md)

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
16. [Deferred to Phase 3 and Product Debt](#16-deferred-to-phase-3-and-product-debt)
17. [Open Points for Review](#17-open-points-for-review)
18. [Glossary](#18-glossary)

---

## 0. Changes

### v3.1

v3.1 comes from the first weeks of Phase 2 in production, from Support and QA feedback. It has two parts: new product decisions, and the decisions already made while building Phase 2 (slice 09a, [ADR 0004](../adr/0004-rejected-is-a-status.md), the free workflow, and the Support team rules in [CONTEXT.md](../../CONTEXT.md)), which this document now states as product rules.

**New decisions**

| Area | v3 (as built) | v3.1 |
|---|---|---|
| Done | Verified work. On production in the Stream; in a Release, on production only after ship | **Done always means on production.** A new status, **Verified**, sits between In review and Done: QA approved the work, it is not on production yet |
| Ship | Done items become on production; others go to the backlog | Every **Verified** item becomes **Done** automatically. Every other item goes to the backlog. Nobody changes statuses by hand at ship |
| Stream | Done when verified | Verified when QA approves. The person who deploys moves it to **Done**, one item or several at once (**On production**). Work already on production can go straight from review to Done |
| Done inside a Release | Reachable by any move | **Not reachable by a move.** Only ship makes a release item Done |
| Done item seen failing again | Recurrence refused; Support files a new report, triage merges it | Support presses **Problem is back**: a **return request** on the Done item. Triage confirms (the item is rejected, new `production` cycle) or dismisses (the item stays Done). No new item, no recurrence count |
| Merge | Recurrence +1 on a bug original, always | A merge into a **Done** item rejects it and does **not** change the count. A merge into **Verified** leaves it as it is and counts +1 |
| Reject | From To review, In review, Done | Also from **Verified**. From Verified the reason is `release_qa` ("caught before production"), in the Stream too |
| Support verifies | Only In review → Done | Support **verifies and rejects** support-sourced items, from To review or In review, in every project |
| Support notifications | Telegram message to Support subscribers, three events | Unchanged, plus the return-request decision, plus a **per-project Telegram group topic** that receives new reports, status changes and return-request decisions, without spam |
| My Work | Personal queue only | Two tabs: **My queue** and **To review** (every To review and In review item in every project, for QA) |
| Phase 1 reports | "Unchanged meaning" | **Product debt PD-1:** not reliable after Phase 2; first item of Phase 3 |
| Open point 8 | Done notification before ship | **Resolved:** Done is sent when the item is on production |

**Built decisions now stated in the PRD**

| Area | v3 text | Built, and now the rule |
|---|---|---|
| Statuses | No Returned or Rejected status; one In review | **To review** (delivered, waiting for QA) and **Rejected** (sent back, not yet picked up) are statuses (09a, ADR 0004). The returned marker is replaced by the Rejected status and a cycle badge |
| Reject | Three actions: Reject, Return from release QA, Problem on production | **One Reject action**; the server records where the problem was caught as the cycle's start reason |
| Workflow | Invalid transitions rejected; self-verification blocked | **Free workflow** (2026-09-22/23): any status may move to any status, except the gates in §9.3 |
| Cancel reason | Required | Optional |
| Go/no-go and ship | CTO, Admin, (ship) triage lead | PM added (2026-11-22 amendment) |
| Settings | Users, projects and search settings are Admin-only | CTO has everything Admin has in Settings (2026-10-05) |
| Support visibility | Support-sourced items only | Plus items a Support user is subscribed to (a report merged into an internal original). Support works as a team: every Support user sees every support report |

Removed: AC-12 (replaced), FR-59 and FR-60 (replaced by FR-59 Reject), FR-63 (replaced), the "Done, not shipped" branch of BR-49, AC-51 (replaced), BR-14 and BR-28 (replaced by the free workflow).
Changed: §1–§9, FR-11, FR-13–FR-19, FR-33, FR-35, FR-42, FR-47, FR-48, FR-50–FR-53, FR-55–FR-57, FR-61–FR-66, BR-13, BR-23, BR-24, BR-30, BR-38, BR-46, BR-47, BR-49, BR-50, BR-52, BR-54–BR-57, BR-59, BR-60, many ACs (marked), §13–§18.
Added: §8.10, §8.11, FR-67–FR-72, BR-67–BR-76, AC-79–AC-100, product debt PD-1.

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

**2026-11-22 amendment:** the Product Manager may record the release go/no-go and ship a release (§7.1, §7.3, FR-52, FR-53). Before this, both were CTO and Admin only, plus the project's triage lead for ship.

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

Phase 2 turns Releasewatch into the **single place where all technical work in the organization is recorded and followed up, from planning to production**: planned deliveries that ship together, the continuous flow of small tasks and fixes that ship one at a time, bugs reported by the support team, and technical debt. Every item, bug or task, passes one QA gate. It is **Verified** when QA approves it and **Done** only when it is on production, so anyone can tell what is on production and what is not. Every time work comes back it is recorded as a new cycle. Every person on the technical team gets one prioritized queue across all the projects they work on, and QA gets one list of everything waiting for review.

Phase 2 is an expansion of the same product — one data model, one interface, one notification channel (Telegram).

---

## 2. What Changed from v1

| Area | v1 | v3.1 |
|---|---|---|
| Scheduling | Gantt, CPM, dependencies, working calendar in Phase 2 | **Moved to Phase 3**, on Releases |
| Estimation | Estimate / remaining / actual, freeze rules | **Moved to Phase 3** |
| Milestones | Containers with scheduling and computed health | **Removed** (v3). Releases carry deadline, lifecycle and progress |
| Statuses | Two workflows mapped onto five columns | **One unified status set** for bugs and tasks, with To review, Rejected and Verified; Done means on production |
| Support reports | Not covered | **Support intake** via templates, per-project triage queue, Support verification, return requests, a per-project Telegram topic |
| Triage | Global Triage Lead role | **Per-project triage lead**; any tech user can triage |
| Technical debt | A backlog category | **A flag on tasks** with its own page, hidden from the default backlog |
| My Work | Unified-column board | **Personal board** with a prioritized cross-project queue, pins, queue history, list and Kanban views, and a **To review** tab |
| Out-of-release work | Implicit | **The Stream**: continuous delivery, one item at a time (v3) |
| Returning work | Regression status on release bugs | **One Reject action** and **cycles** with a start reason, for bugs and tasks; **return requests** from Support |
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

**"Done" hides where the work is** *(v3.1)*. A long release stays on staging for weeks while hotfixes go to production. Done meant "verified", so nobody could tell which items were on production and which were only on staging, and at ship nobody knew which statuses to change.

**Support cannot close its own loop** *(v3.1)*. Support tests hotfixes itself but could only close an item from In review. When a fixed bug came back, Support had no way to say so on the item. Only the person who filed a report heard about its progress, so a customer waited when that person was away.

**QA cannot see its work** *(v3.1)*. Work waiting for review is spread across projects, and the personal board shows only what is assigned to a person.

---

## 4. Goals & Non-Goals

### Goals

1. **Visibility** — the CTO can see who is working on what, across all projects.
2. **Nothing ownerless** — every request, report, and piece of work has a recorded owner and state.
3. **Personal prioritization** — each person has one ordered queue across projects, which the person and the CTO/Admin can shape.
4. **Structured support intake** — support reports arrive with the data needed to act on them, pass through triage, and Support can follow and close them as a team.
5. **Technical debt register** — debt is recorded once and remains findable without cluttering daily work.
6. **Delivery from planning to production** — continuous and planned delivery are both tracked, every item passes one QA gate, Done means on production, and every return is recorded with where it was caught.
7. **One place for QA** — everything waiting for review, in every project, on one page.

### Non-Goals

- Task management for non-technical departments (sales, finance, etc.). Only the technical team is assigned work.
- Integration with NEXT or any other company system. Releasewatch stays independent.
- Time tracking or timesheets.
- Individual performance scoring.
- Resource capacity planning.
- Bulk status changes, with one exception: moving several Verified Stream items to Done at once (**On production**, FR-67).
- Assigning a named reviewer to an item.
- Reports by customer (customer ID stays in the description, P2).

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
- **Verified** status; Done means on production
- One **Stream** per project and any number of **Releases** per project
- Release lifecycle, go/no-go, ship, progress, and overdue
- Per-project backlog
- One **Reject** action and cycles, for bugs and tasks
- Support role, support intake through per-project templates, Support verification of support-sourced items, and **return requests**
- Per-project triage queue with defined outcomes
- Recurrence counter for repeated reports of open items
- Merge of a returning report into its original (bug or task)
- Technical debt flag and Tech Debt page
- Personal board: prioritized queue, pins, queue history, list and Kanban views, and the **To review** tab
- Team overview for CTO/Admin
- Telegram notifications for all new events, including a per-project **Support channel**
- Search & Ranking Engine, similar-item suggestions, and optional Jev — see [prd-search-engine.md](prd-search-engine.md)
- MCP server for coding agents — see [prd-mcp.md](prd-mcp.md)

### Out of scope for Phase 2 — see [Section 16](#16-deferred-to-phase-3-and-product-debt)

Gantt, CPM, dependencies, working calendar, holidays, estimation fields, release health, and every new report (including cycle metrics). Repairing the Phase 1 reports is product debt PD-1.

---

## 7. Roles & Permissions

### 7.1 Roles

| Role | Description |
|---|---|
| **Support** | Reports bugs through templates. Sees all support-reported items, as a team. Verifies and rejects support-sourced items. Asks for a Done item to come back. Is never assigned work |
| **QA Engineer** | Files bugs and tasks, verifies and rejects delivered work |
| **Developer** | Files bugs and tasks, works assigned items, triages |
| **Product Manager** | Manages backlog and releases, release go/no-go and ship |
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
| View non-support items | —⁴ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Public comment | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Internal (tech-only) note | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Report recurrence (open or Cancelled bug) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Problem is back (return request on a Done item) | ✓ | — | — | — | — | — |
| Triage (including merge and return-request decisions) | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Be assigned work | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Change an item's status (free workflow, §9.3) | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Verify delivered work (To review / In review → Verified, or → Done in the Stream) | ✓³ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Reject (To review, In review, Verified, Done) | ✓³ | ✓ | ✓ | ✓ | ✓ | ✓ |
| On production (Verified → Done, Stream, one or several items) | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Flag / unflag technical debt | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Manage backlog and releases | — | — | ✓² | ✓ | ✓ | ✓ |
| Release go/no-go | — | — | — | ✓ | ✓ | ✓ |
| Ship a release | — | ✓² | ✓² | ✓ | ✓ | ✓ |
| Reorder / pin own queue | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| Reorder / pin anyone's queue | — | — | — | — | ✓ | ✓ |
| Use the To review tab | — | ✓ | ✓ | ✓ | ✓ | ✓ |
| View anyone's personal board and team overview | — | — | — | — | ✓ | ✓ |
| Manage templates and a project's Support channel | — | — | — | — | ✓ | ✓ |
| Manage users and projects | — | — | — | — | ✓ | ✓ |
| Manage search settings and Jev | — | — | — | — | ✓ | ✓ |

² Only as the project's triage lead.
³ Only on support-sourced items, in every project, whoever filed the report. Support's Reject applies to To review and In review only; a Done item is asked back with Problem is back.
⁴ Except items the Support user is subscribed to (a support report merged into an internal original).

Where a role lacks a capability, the control is shown disabled with a tooltip rather than hidden. The exception is Support: tech-only screens, internal notes, and tech-only actions are not shown to Support at all.

---

## 8. Domain Model

Product-level description of entities and attributes.

### 8.1 Project

Name · Key · Triage lead · Templates · Backlog categories · **Support channel** (optional, §8.11) · Stream (exactly one, created with the project) · Releases

There are no project kinds. Every project follows the same model (P2).

### 8.2 Work item

**Shared:** ID (`BUG-042`, `TASK-118`) · Type (Bug / Task, fixed at creation) · Title · Description (markdown) · Project · **Container** (the project's Stream or one of its Releases; empty = backlog) · Status · **Priority** (Critical, High, Medium, Low) · Reporter · Assignee · Labels · Due date (optional) · Attachments · Timeline (comments, internal notes, system events) · Lifecycle dates (filed, triaged, started, review requested, **verified**, **completed = on production**, cancelled) · **Cycles** (§8.9) · **Return requests** (§8.10) · Subscribers

**Bug only:** Source (Internal / Support) · Recurrence count · Release blocker flag · Reproduction steps · cURL · Environment · Cancel reason · Duplicate of (when cancelled as duplicate)

**Task only:** Technical debt flag

**Backlog:** Backlog category (the project's own categories; **Default** always exists) · Backlog rank

### 8.3 Support template

Project · Name · Active flag · Ordered fields. Each field has: Label · Type (short text, long text, number, date, date-time, single select, URL) · Required · Help text.

Template fields are not stored as item fields. On submission they are **composed into the item description** as a labeled, structured block.

### 8.4 Recurrence

Item · Reported by · Date · Comment (required). Each recurrence increments the item's recurrence count and adds a public comment to its timeline. A recurrence exists only on a bug that is open (any status except Done and Cancelled, **Verified included**) or Cancelled. A Done item takes a return request instead (§8.10).

### 8.5 Personal queue

One per assignable user. Ordered list of that user's open assigned items. Each entry may carry a **pin** (pinned by self or by CTO/Admin). An item that reaches Verified or Done leaves the queue and keeps a dormant position for its return (BR-61).

### 8.6 Queue history entry

User · Actor · Action (reorder, pin, unpin) · Item · Old position · New position · Date. Stored with the queue, **never** in the item timeline.

### 8.7 Containers: Stream and Release

A **container** is where an item is delivered from. Every project has exactly one Stream and any number of Releases.

**Stream** — Project · (nothing else). Created with the project. It cannot be renamed, edited, cancelled, archived, or deleted, and it is always open. Every item in the Stream ships on its own: **it is on production when someone moves it to Done** (FR-67). The Stream has no lifecycle, go/no-go, release blocker, container deadline, or progress. Items in it carry their own due dates.

**Release** — Project · Name (version) · Description · Lifecycle status (Planning, Development, QA, Released, Cancelled) · Code freeze date (optional; QA starts) · Target ship date (optional) · Go/No-go (decision, note, by, at) · Released at · Staging URL · Progress (computed: (Verified + Done) items ÷ non-cancelled items). Its items ship together: **at ship, every Verified item becomes Done**, on production at the ship time.

### 8.8 Milestone

*(Removed in v3.)*

### 8.9 Cycle

One pass of work on an item until it is delivered: picked up, worked, sent to review, verified. A cycle belongs to one item and one container. The first cycle starts when the item is placed in a container, and each later cycle starts because the work came back (a Reject). The cycle records **why it started** (`start_reason`: planned, review, release QA, production), who delivered its work, and its timing. The cycle is a ledger: what users see comes from the status. The full model is in [cycle-model.md](cycle-model.md).

### 8.10 Return request (v3.1)

Support's request that a **Done** item come back for another fix because the problem is seen again on production.

Item (a Done item the Support user can see) · Requested by · Date · Comment (required) · Attachments (optional) · Later additions (comment, user, date) · Outcome (Pending, Confirmed, Dismissed) · Decided by · Decision date · Decision comment (required when Dismissed).

A return request is not a work item: it has no key, no status, no backlog place and no search entry. It lives on its item, is listed in the project's triage queue while Pending, and is recorded in the item's timeline. An item has at most one Pending request.

### 8.11 Support channel (v3.1)

Per project, optional: Telegram chat ID · Topic ID (optional, for groups with topics) · Enabled flag. Managed by CTO and Admin, with **Send test message**. The bot must be a member of the chat. A project without an enabled Support channel posts nothing to any group.

---

## 9. Status Model

### 9.1 Unified statuses

One status set for both types. Bugs have two additional pre-board statuses.

| Group | Status | Bug | Task | Meaning |
|---|---|:-:|:-:|---|
| Triage | **New** | ✓ | — | Awaiting triage |
| Triage | **Needs info** | ✓ | — | Waiting on the reporter |
| Board | **To do** | ✓ | ✓ | Accepted or placed, not started |
| Board | **Rejected** | ✓ | ✓ | Delivered work sent back with a reason, not yet picked up |
| Board | **In progress** | ✓ | ✓ | Being worked on |
| Board | **To review** | ✓ | ✓ | The developer delivered; waiting for QA to pick it up |
| Board | **In review** | ✓ | ✓ | QA is checking it |
| Board | **Verified** | ✓ | ✓ | QA (or Support, for support-sourced items) approved it. **Not on production yet** |
| Board | **Done** | ✓ | ✓ | **On production** |
| Board | **Blocked** | ✓ | ✓ | Cannot proceed |
| Terminal | **Cancelled** | ✓ | ✓ | Closed without being done, with an optional reason |

**Kanban columns:** To do (Rejected cards on top, in their own style), In progress, To review, In review, Verified, Done, Blocked. New and Needs info live in the triage queue. Cancelled items appear in no board.

An item past its first cycle shows a small **cycle badge** (`↻ 2`) on every status.

### 9.2 Flags (not statuses)

| Flag | Applies to | Set by |
|---|---|---|
| Release blocker | Bugs in a Release (not the Stream) | QA, triage lead, PM, CTO, Admin |
| Technical debt | Tasks | Any tech user |

### 9.3 Transitions

The workflow is **free**: a tech user may move an item from any status to any other (tasks are never offered New or Needs info). There are only these gates:

| Gate | Rule |
|---|---|
| **Rejected** | Entered only by **Reject** (FR-59) or by a merge into a Done item (BR-49). Never by a status move |
| **Done in a Release** | Entered only by **ship** (FR-53). A status move to Done is refused for an item in a Release (v3.1) |
| **In progress** | Requires a container (BR-53) |
| **Support** | Moves only support-sourced items, and only To review / In review → Verified, or → Done in the Stream (BR-71) |

```
New ──triage──▶ To do ──▶ In progress ──▶ To review ──▶ In review ──▶ Verified ──▶ Done
 │  ▲            ▲            ▲                │              │           │           │
 ▼  │            │            └──── pick up ── Rejected ◀──── Reject ─────┴───────────┘
Needs info       │                                                (review / release QA / production)
                 └── Blocked, Cancelled: reachable from any open status
Stream only:  To review / In review ──▶ Done   (already on production)
Release only: Verified ──▶ Done          by ship only
```

- The intended path is To do → In progress → To review → In review → Verified → Done. To review may be skipped.
- In the Stream, work QA verifies on production goes straight from To review or In review to **Done**.
- **Every Reject lands in Rejected.** The assignee picks the item up by moving it to In progress.

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

**FR-11** Support sees a **Support reports** list containing every support-sourced item across all projects, with status, project, reporter (with a "Me" filter), recurrence count, last update, and a **Return requested** badge while a return request is Pending. Search by text and filter by project and status.

**FR-12** While Jev is enabled, the support form shows a **similar reports** panel with the project's open support reports that describe the same problem, and lets Support record a recurrence on one of them instead of filing a new report. Defined in [Search & Ranking Engine](prd-search-engine.md) (FR-S09–FR-S11). While Jev is disabled, the panel is not shown.

### 10.3 Recurrence and return requests

**FR-13** Any user can press **Report recurrence** on an open or Cancelled bug they can see. Open means any status except Done and Cancelled, **Verified included**. A comment is required; it is where new customer information goes.

**FR-14** Reporting a recurrence increments the recurrence count, adds the comment to the timeline, and subscribes the recurrence reporter to support notifications for that item.

**FR-15** On a Cancelled item, a recurrence notifies the project's triage lead. It does not reopen the item.

**FR-16** On a Done item, **Report recurrence is not offered**. A Support user sees **Problem is back** (FR-68); a tech user sees **Reject** (FR-59).

**FR-68** **Problem is back (v3.1).** On a **Done** item they can see, a Support user presses **Problem is back**. A comment is required; attachments are optional. It creates a **Pending return request** (§8.10). No new item is created, the item stays Done, and the recurrence count does not change. The requester is subscribed to the item. While a request is Pending, the button reads **Add to pending request**: it adds the user's comment and attachments to the same request and subscribes them.

**FR-69** **Deciding a return request (v3.1).** A Pending request is listed in the project's triage queue (FR-17), and the triage lead is notified. Any tech user who can triage decides:
- **Confirm:** the item is **rejected** with the request's comment as the reason, exactly as Reject from Done (FR-59): Rejected, a new cycle with reason `production`, and an item in a Released release moves to the Stream. The recurrence count does not change.
- **Dismiss:** a public comment explaining why is required. The request closes, the item stays **Done**, no cycle starts, and the recurrence count does not change.

The requesters are notified of either decision (§13).

### 10.4 Triage

**FR-17** Each project has a **Triage queue** with its New and Needs info bugs, oldest first, with source, reporter, recurrence count, and age, and its **Pending return requests**, oldest first, with the item, its status, the requesters and the comment.

**FR-18** Triage outcomes for a New or Needs info bug:

| Outcome | Result |
|---|---|
| **Accept** | Status To do. Choose placement: Backlog (with a category, Default if none), the Stream, or an open Release. Assignee optional. **Priority required** |
| **Needs info** | Status Needs info. A public comment stating what is missing is required |
| **Duplicate (merge)** | Status Cancelled (reason Duplicate). Choose the original item: a **bug or a task** in the same project. The duplicate's reporter is subscribed to the original, and the duplicate's title and description are added to the original as a public comment. The effect on the original depends on its status (BR-49) |
| **Reject** | Status Cancelled with reason: User error, Expected behavior, or Cannot reproduce |

Return-request outcomes are in FR-69.

**FR-19** When the reporter (or any Support user) comments publicly on an item in Needs info, the item returns to New and the triage lead is notified.

**FR-20** The triage lead can change the item's project during triage. The item moves to the new project's queue and that project's triage lead is notified.

### 10.5 Hotfix path

*(Removed in v3. Urgent work is an item in the Stream with a high priority or a pin.)*

### 10.6 Backlog

**FR-23** The backlog is a ranked list, not a board, of the items in a project that have no container and are not Done or Cancelled.

**FR-24** Technical-debt items are **hidden from the backlog by default**. A toggle "Show technical debt" reveals them.

**FR-25** Backlog supports grouping by category, drag ranking, multi-select, and bulk move to the Stream or an open Release. This is a placement change, not a status change. A Rejected item moved to the backlog becomes To do.

### 10.7 Technical debt

**FR-26** Any tech user can flag a task as technical debt at creation or later. No additional fields: affected components, risk, and approach go in the description.

**FR-27** The main navigation has a **Technical debt** page: a list of all flagged tasks with filters for project (multi-select), status, and assignee.

**FR-28** Each project page links to the Technical debt page pre-filtered to that project.

**FR-29** Once a technical-debt task is assigned or placed in the Stream or a Release, it appears on boards and in queues like any task. The flag remains.

### 10.8 Milestones

*(Removed in v3.)*

### 10.9 Personal board (My Work)

**FR-72** **Two tabs (v3.1).** My Work has two tabs, each with a counter: **My queue** (FR-33–FR-42) and **To review** (FR-73). QA opens on To review by default; every other tech role opens on My queue. Both tabs exist for every tech user.

**FR-33** **My queue** contains all the user's assigned items that are To do, Rejected, In progress, To review, In review, or Blocked, across all projects. Verified and Done items are not in the queue; the Kanban view shows them in their columns.

**FR-34** **List view:** a horizontal-card list. An "In progress" group on top, then the **queue** in queue order.

**FR-35** **Kanban view:** the seven board columns (§9.1). Within each column, cards follow queue order. Verified shows the user's Verified items. Done shows items put on production in the last 7 days.

**FR-36** Queue order is: pinned items (in their pin order), then all other items in manual or default order.

**FR-37** **Default order** for unpinned items: priority (Critical, High, Medium, Low; items with no priority last), then due date (earliest first, none last), then recurrence count (highest first), then age (oldest first).

**FR-38** The user can drag items to reorder their queue. A CTO or Admin can reorder any user's queue.

**FR-39** A newly assigned item is inserted by the default rule: it is placed directly above the first item that ranks lower under the default order, even if the queue has been manually ordered. A **rejected** item that left the queue is not new: it follows FR-64.

**FR-40** The user can pin up to **4** items. CTO or Admin can pin items in any user's queue, within the same limit. A pin set by CTO/Admin shows a lock and cannot be removed by the user.

**FR-41** Every reorder, pin, and unpin — by anyone — is recorded in the user's **Queue history**, visible to that user and to CTO/Admin. Queue history never appears in the item timeline.

**FR-42** Cards show only title, project chip, and a priority icon by default. Additional compact markers appear only when relevant: pinned, Rejected (status style), cycle badge, recurrence count > 1, due within 2 days or overdue, technical debt, and **Verified for 3 days or more** in the Stream (small age marker; hover shows the verification date). Hovering a card shows full details (all markers spelled out, age, container, reporter).

**FR-73** **To review (v3.1).** The To review tab lists **every item in To review or In review, in every project**, regardless of assignee. No reviewer is assigned. Rows are grouped by project, then by status (To review first, then In review), then ordered by priority and by the longest wait in that status; each row shows the waiting time and the assignee. Filters: project (multi-select), type, status. A row opens the item, where the viewer can move it to In review, verify it, or reject it. The tab updates when an item leaves review.

### 10.10 Team overview

**FR-43** CTO and Admin have a **Team** page listing each assignable user with their In progress items, top three queue items, and counts of open and pinned items. Selecting a user opens their personal board with reorder and pin controls.

### 10.11 Templates and Support channel administration

**FR-44** CTO and Admin manage templates per project: create, edit, reorder fields, activate, and deactivate.

**FR-45** Editing or deactivating a template affects only future submissions. Existing items keep their composed descriptions.

**FR-70** **Support channel settings (v3.1).** In each project's settings, CTO and Admin set the Support channel (§8.11): chat ID, optional topic ID, enabled. **Send test message** posts a test to that chat and topic and shows success or the error Telegram returned. Saving an enabled channel requires a successful test.

### 10.12 Stream

**FR-46** Every project has exactly one Stream, created with the project and shown as the project's first container. It cannot be renamed, edited, cancelled, archived, or deleted.

**FR-47** The Stream page has a seven-column Board and an Items table. The Done column shows, by default, items put on production in the **last 7 days**. A time picker changes the range: relative presets (last 7, 30, 90 days, or last *N* days) and an absolute range (from date to date). The range filters only the Done column; open columns, Verified included, always show everything.

**FR-48** An item in the Stream is on production when it reaches Done (FR-67).

**FR-67** **On production (v3.1).** In the Stream, the person who deploys moves Verified items to Done: one item by a status move, or **several selected Verified items at once** with **On production** on the Stream board and Items table. Each item records its own completion time and timeline event. This is the only multi-item status change in the product. Release items have no such action: they become Done at ship.

### 10.13 Releases

**FR-49** PM, CTO, Admin, and the project's triage lead create and edit releases: name (version), description, code freeze date, target ship date, staging URL.

**FR-50** Release lifecycle:

| From | To | How |
|---|---|---|
| Planning | Development | Manual |
| Development | QA | Manual (code freeze) |
| QA | Development | Manual (back to development) |
| QA | Released | **Ship** only (FR-53) |
| Planning, Development, QA | Cancelled | Manual, only when the release has no Verified or Done item (BR-55) |

Released and Cancelled are final.

**FR-51** The release page has a Board tab (seven columns), an Items table, and an Activity tab (lifecycle changes, date changes, items added or removed, go/no-go decisions, ship). It shows progress ((Verified + Done) ÷ non-cancelled items) and, when the target ship date has passed and the release is not Released or Cancelled, an **Overdue** marker.

**FR-52** The release page shows the open release blockers. The PM, CTO or Admin records **go** or **no-go** with an optional note.

**FR-53** **Ship.** PM, CTO, Admin, and the project's triage lead can ship a release in QA. Before confirming, a notice shows the go/no-go decision, the number of **Verified** items that go to production, and the items that do not, by status (for example "3 To do, 1 In progress, 1 In review"). Shipping does not require every item to be Verified. On confirmation:
- the release becomes Released and records the ship time;
- **every Verified item becomes Done**, on production at the ship time;
- every other item moves to the **backlog** with category **Default** and status **To do** (a Rejected item too), keeping its assignee and pins; its cycles are deleted (BR-62).

**FR-54** A Released release keeps its Board, Items, and Activity tabs read-only.

### 10.14 QA gate and Reject

**FR-55** Moving an item to To review or In review (whichever comes first in the cycle) delivers it to QA. The system records who delivered the work: the item's **assignee** at that moment, never the person who changed the status (BR-63).

**FR-56** **Verify.** Moving an item from To review or In review to **Verified** verifies it and records the verification time. In the Stream, moving it straight to **Done** means it was verified on production: both the verification and completion times are recorded at that moment.

**FR-57** *(Replaced by FR-59 in v3.1.)*

**FR-58** A backlog item cannot be moved to In progress. The control is disabled with the hint "Place this item in the Stream or a release first."

**FR-59** **Reject.** One action sends delivered work back, from **To review, In review, Verified, or Done**. A comment is required and is written as an ordinary public comment. The item becomes **Rejected**, a new cycle starts, and the assignee is notified with the comment. The server records where the problem was caught:

| Rejected from | Start reason | UI label |
|---|---|---|
| To review, In review | `review` | Rejected in review |
| Verified (Stream or Release) | `release_qa` | Caught before production |
| Done | `production` | Problem on production. An item in a Released release moves to the Stream first |

Support's Reject (support-sourced items) is offered on To review and In review only; on a Done item Support uses Problem is back (FR-68).

**FR-60** *(Replaced by FR-59 in v3.1.)*

**FR-61** Every Reject — direct, a confirmed return request (FR-69), or a merge into a Done item (BR-49) — acts on one item and records its reason comment on the timeline.

**FR-62** There are no bulk status changes anywhere in the product, except On production (FR-67).

**FR-63** **Rejected style and cycle badge.** A Rejected item shows a "Rejected" pill in the hue of its reason (review, before production, production) and, on board cards, a left accent in the same hue; hover shows the full label and the reason comment. Rejected cards sort above plain To do cards. Any item with cycle 2 or later shows a cycle badge (`↻ N`) on every status.

**FR-64** A rejected item that had left its assignee's queue (from Verified or Done) goes back to the **position it had before it left**, but never above the pinned items. An item rejected from To review or In review never left the queue, so it keeps its place.

**FR-65** A Reject notifies the assignee with where it was caught and the reason comment. Support is not notified of a Reject except through a return-request decision (§13).

**FR-66** An item's timeline shows its cycles: when each started and why, who delivered it, when it was verified, when it reached production.

### 10.15 Support channel

**FR-71** **Support channel posts (v3.1).** For a project with an enabled Support channel, the bot posts to its chat and topic about **support-sourced items of that project**: a new report, every status change, and every return-request event (requested, confirmed, dismissed). A post names the project, the item key and title, the old and new status, the reason or comment where one exists (Needs info, Cancelled, Reject from Done, return decisions), and mentions the reporter by Telegram username when one is linked. No internal note ever appears. To keep the topic readable:
- several changes to one item within **60 seconds** are one post, showing the first and the final status;
- **On production** for several items, and a **ship**, are **one post per project** listing the items;
- each event is posted once; there are no reminders or digests.

Posting is best-effort: a failed post is retried and logged, and never blocks or undoes the action.

---

## 11. Business Rules

### Placement

**BR-01** Every work item belongs to exactly one project. Project is never empty.

**BR-02** *(Removed in v3: there are no project kinds; see BR-51.)*

**BR-03** An item's container must belong to the item's project. An item is in at most one container.

**BR-04** An item with no container that is not Done or Cancelled is in the backlog. Backlog membership is never set explicitly.

**BR-05** Changing an item's project is allowed only when it has no container.

**BR-06** Every item has a backlog category of its own project; when none is chosen it is **Default**. Items moved to the backlog by a ship get **Default**.

### Type and status

**BR-07** Item type is fixed at creation.

**BR-08** Source, recurrence, release blocker, reproduction steps, cURL, and environment exist only on bugs.

**BR-09** The technical debt flag exists only on tasks. Priority is shared by both types.

**BR-10** New and Needs info exist only for bugs.

**BR-11** Every bug starts in New, regardless of who files it.

**BR-12** Tasks start in To do.

**BR-13** Cancelled may carry a reason. Bug reasons: User error, Expected behavior, Cannot reproduce, Duplicate, Won't fix. Task reason: No longer needed.

**BR-14** *(Replaced in v3.1.)* The workflow is free (§9.3). The only refused moves are the gates of §9.3; a refused move names the rule.

### Triage

**BR-15** Every project has exactly one triage lead. A project cannot be saved without one.

**BR-16** Priority must be set when a bug is accepted. A bug in New or Needs info may have no priority; a task is created with Medium.

**BR-17** *(removed in v2.2.)*

**BR-18** Needs info requires a public comment stating what is missing.

**BR-19** A reporter or Support comment on a Needs info item returns it to New.

**BR-20** A duplicate must reference an item (bug or task) in the same project that is not itself a cancelled duplicate.

**BR-21** Cancelled items are never reactivated. A recurrence after rejection must be reported again or recorded as a recurrence comment.

### Recurrence, merge, and Reject

**BR-22** A recurrence requires a comment and increments the recurrence count by exactly one. Recurrence exists only on bugs.

**BR-23** *(Changed in v3.1.)* Recurrence is not allowed on Done items. A problem seen again on a Done item is a **return**, not a recurrence: Support raises a return request (FR-68), the tech team rejects the item (FR-59), and a new report merged into a Done item rejects it (BR-49). None of these changes the recurrence count.

**BR-24** Work comes back only through **Reject** (FR-59): directly, by a confirmed return request (FR-69), or by a merge into a Done item (BR-49). Each starts a new cycle ([cycle-model.md](cycle-model.md)).

**BR-25** *(Removed in v3. See product debt PD-1.)*

**BR-49** **Merge effects by the original's status.** When a report is merged into an original (Duplicate outcome):
- **New, Needs info, To do, Rejected, In progress, To review, In review, Verified, Blocked:** the original's status does not change and no cycle starts; a bug original's recurrence count +1. A report about work whose fix is not on production yet is expected; a Verified item is rejected only by a person (FR-59).
- **Done:** the original is **rejected** (FR-59) with the merge comment as the reason: Rejected, a new `production` cycle, and an item in a Released release moves to the Stream. The recurrence count does not change.
- **Cancelled:** the original stays Cancelled, a bug original's recurrence count +1, and the triage lead is notified, as for a recurrence on a Cancelled item (FR-15).

**BR-50** Merge is one operation with one set of effects on the original: the merged report's content added as a public comment, the merged report's reporter subscribed, and BR-49's status effect. The Duplicate outcome in triage and a recurrence recorded from the similar reports panel (FR-12) both produce these effects; only the Duplicate outcome creates and cancels a second item.

### Delivery

**BR-26** An item reaches Verified or Done only inside a container (it cannot be started without one, BR-53).

**BR-27** *(removed in v2.2.)*

### Verification

**BR-28** *(Replaced in v3.1.)* Verification is the move from To review or In review to Verified (or to Done in the Stream). It is recorded once per cycle. There is no self-verification block (free workflow).

**BR-29** *(Replaced in v3.)* Bugs and tasks pass the same QA gate.

### Visibility

**BR-30** Support users see support-sourced items, plus items they are subscribed to, and only public comments on them. Every Support user sees every support report.

**BR-31** Internal notes are never shown to Support, in any view, notification, or Support channel post.

**BR-32** Support users cannot be assigned items.

### Templates

**BR-33** A project appears in the support form only if it has at least one active template.

**BR-34** Template field values are composed into the description at submission and are not stored or searchable as separate fields.

**BR-35** Template changes never alter existing items.

### Technical debt

**BR-36** Only tasks can be flagged as technical debt.

**BR-37** Technical-debt tasks are excluded from the default backlog view but not from boards, queues, or search once assigned or placed.

### Personal queue

**BR-38** A queue contains only the user's assigned items that are To do, Rejected, In progress, To review, In review, or Blocked.

**BR-39** Queue order is always: pinned, then the rest.

**BR-40** At most 4 pinned items per user, including locked pins.

**BR-41** A pin set by CTO/Admin can be removed only by CTO/Admin.

**BR-42** Only the queue owner and CTO/Admin can reorder or pin. Triage leads and PMs cannot.

**BR-43** When CTO/Admin reorders or pins in someone's queue, that user is notified.

**BR-44** Queue history is append-only and stored separately from item timelines.

**BR-45** When an item is unassigned or reassigned, it leaves the previous owner's queue (pins included) and enters the new owner's queue by the default rule.

**BR-46** When a pinned item reaches Verified, Done, or Cancelled, its pin is released.

### Releases

**BR-47** Release progress = (Verified + Done) items ÷ non-cancelled items.

**BR-48** Overdue is shown only when a target ship date exists, has passed, and the release is not Released or Cancelled.

### Containers, QA gate, and cycles

**BR-51** Every project has exactly one Stream, created with the project. The Stream cannot be edited, cancelled, archived, or deleted.

**BR-52** **On production.** An item is on production exactly when it is Done. A Verified item is not on production.

**BR-53** An item can move to In progress only when it has a container.

**BR-54** A Verified or Done item never changes container, except that a Reject from Done in a Released release moves it to the Stream (BR-57).

**BR-55** A release that has at least one Verified or Done item cannot be cancelled.

**BR-56** Shipping a release requires no condition on its items. It turns every Verified item into Done, and moves every other item to the backlog (category Default, status To do).

**BR-57** A Released release never holds an open item. An item rejected from Done in a Released release moves to the Stream.

**BR-58** The release blocker flag applies only to bugs in a Release.

**BR-59** Every Reject requires a comment, acts on one item, lands it in Rejected, and starts a new cycle.

**BR-60** There are no bulk status changes, except On production (BR-68).

**BR-61** An item that reached Verified or Done keeps a dormant queue position. If it is rejected back to the same assignee, it re-enters at that position, never above the pinned items (FR-64).

**BR-62** A cycle exists only while the item has a container. The first cycle starts when the item is placed in a container, with reason `planned`. Moving an item to the backlog deletes all of its cycles; placing it again starts from cycle 1. A Rejected item moved to the backlog becomes To do.

**BR-63** "Who delivered the work" is the item's assignee at the moment it first moved to To review or In review in the cycle. It is never the actor of the status change and never falls back to the actor.

**BR-64** The container of an open cycle follows the item. A Verified or Done item does not move (BR-54), so the container of delivered work is fixed.

**BR-65** The reason a cycle started is recorded when it starts and is never recomputed.

**BR-66** A backlog item is placed in a container before anyone can start it. Placement and starting are separate actions.

### Verified, return requests, Support, and review (v3.1)

**BR-67** Done means on production, always. Nothing is Done because it was verified.

**BR-68** In the Stream, Verified → Done is a manual move by the person who deploys, for one item or several at once. In a Release, Done is reached only by ship: a status move to Done of a release item is refused (`done_at_ship`).

**BR-69** A return request exists only on a Done item, and only a Support user who can see the item creates one. An item has at most one Pending request.

**BR-70** Confirming a return request rejects the item (FR-59). Dismissing it requires a public comment and changes nothing on the item. Neither changes the recurrence count, cancels anything, or creates an item.

**BR-71** Support may, on support-sourced items only, in every project: move To review or In review to Verified, or to Done in the Stream; and Reject from To review or In review. Support makes no other status move.

**BR-72** The Support channel posts only about support-sourced items, only for projects with an enabled channel, and never carries internal notes (BR-31). A post never blocks an action.

**BR-73** The To review tab lists items in To review or In review only, from every project. There is no reviewer assignment.

**BR-74** **Move to v3.1.** Every item that was Done inside a Release that is not Released becomes Verified, keeping its verification time. Every other Done item stays Done.

**BR-75** The Verified age marker (FR-42) appears only on Stream items, three days after verification.

**BR-76** Support's Done notification (§13) is sent when the item reaches Done, never at verification.

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

**AC-08** Given a Support user, then tasks and internally filed bugs they are not subscribed to never appear in their lists or search.

### Recurrence

**AC-09** Given an open bug, when a user presses Report recurrence without a comment, then the action is blocked.

**AC-10** Given an open bug with recurrence count 3, when a recurrence is reported, then the count is 4 and the comment appears in the timeline.

**AC-11** Given a Cancelled bug, when a recurrence is reported, then the count increments, the triage lead is notified, and the status stays Cancelled.

**AC-12** *(Changed in v3.1.)* Given a Done bug, then Report recurrence is not offered; a Support user sees Problem is back, and a tech user sees Reject.

**AC-13** Given two users report a recurrence at the same moment, then the count increases by two.

**AC-79** Given a Verified bug, when a user reports a recurrence, then the count increments, the comment is on the timeline, and the status stays Verified.

### Triage

**AC-14** Given a developer files a bug, then it is created in New and appears in the project's triage queue, not on boards.

**AC-15** Given a New bug, when any Developer (not the triage lead) accepts it, then the acceptance succeeds and the triage lead is not required to act.

**AC-16** Given Accept without a priority, then the action is blocked.

**AC-17** Given "Needs info" without a comment, then the action is blocked.

**AC-18** Given an item in Needs info, when its Support reporter comments, then the status becomes New and the triage lead is notified.

**AC-19** Given an item in Needs info, when a Developer comments, then the status does not change.

**AC-20** Given a triager marks bug A as duplicate of open bug B, then A is Cancelled with reason Duplicate, B's recurrence count increases by one, and A's reporter receives B's future support notifications.

**AC-21** Given a triager tries to mark A as duplicate of an item that is itself a duplicate, then the action is blocked and the original item is suggested.

**AC-22** Given a triager moves a New bug to another project, then it appears in the new project's queue and the new project's triage lead is notified.

**AC-23** Given a project whose triage lead user is deactivated, then the project is flagged in Admin settings and triage notifications go to Admin until a new lead is set.

### QA gate and Reject

**AC-24** *(Changed in v3.1.)* Given a bug accepted into the Stream and delivered, when QA moves it to Verified, then it is Verified and not on production; when the deployer moves it to Done, then it is on production and its Support subscribers receive the Done notification then.

**AC-25** *(Changed in v3.1.)* Given a Verified item in a Release in QA, when QA rejects it with a comment, then it is Rejected in the same release and its current cycle has reason `release_qa`.

**AC-26** *(Changed in v3.1.)* Given a Done task in the Stream, when a developer rejects it with a comment, then it is Rejected in the Stream and its current cycle has reason `production`.

**AC-27** *(Changed in v3.1.)* Given an item in To review, when QA moves it to In review and then to Verified, then the delivery was recorded at To review with the assignee, and the verification time is set once.

### Merge

**AC-49** Given B is In progress with recurrence count 2, when bug A is merged into B, then A is Cancelled (Duplicate), B's status is unchanged, B's recurrence count is 3, and B's timeline shows a public comment containing A's title and description.

**AC-50** *(Changed in v3.1.)* Given B is a Done bug in the Stream with recurrence count 2, when A is merged into B, then B is Rejected in the Stream, its current cycle has reason `production`, and its recurrence count is still 2.

**AC-51** *(Replaced in v3.1.)* Given B is a Verified item in Release R, when bug A is merged into B, then B stays Verified, no cycle starts, and (if B is a bug) its recurrence count increases by one.

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

**AC-39** *(Changed in v3.1.)* Given a pinned item reaches Verified, then its pin is released, the pin slot becomes free, and the item leaves the queue.

**AC-40** Given a PM or triage lead views another user's board, then reorder and pin controls are not available.

**AC-41** Given the Kanban view, then within each column, cards follow the same order as the list view.

**AC-42** Given an item was put on production 8 days ago, then it does not appear in the Done column.

### Card signals

**AC-43** Given an item with recurrence count 1, cycle 1, no due date, not pinned, not Rejected, and not technical debt, then its card shows only title, project chip, and priority icon.

**AC-44** Given an item overdue by one day, then the card shows a compact overdue marker, and hovering shows the date in full.

### Releases

**AC-45** *(Changed in v3.1.)* Given a release with 10 items, 2 cancelled and 4 Verified, then progress is 50%.

**AC-46** Given a release with no target ship date, then no Overdue marker ever appears.

### Visibility and permissions

**AC-47** Given a Support user, then no assignee picker lists Support users.

**AC-48** Given the Team page, when viewed by a Developer, then access is denied.

### Containers

**AC-55** Given a new project, then it has exactly one Stream, and the Stream cannot be renamed, cancelled, or deleted.

**AC-56** Given a task in the backlog, when a developer tries to move it to In progress, then the action is refused with the hint to place it first.

**AC-57** *(Changed in v3.1.)* Given an item in a Release that is In review, when a user tries to move it to Done, then the move is refused (`done_at_ship`) and Verified is offered.

**AC-58** *(Changed in v3.1.)* Given a Verified item in a Release in QA, when a PM tries to move it to the Stream or another release, then the move is refused.

**AC-59** *(Changed in v3.1.)* Given a release with one Verified item, when a PM tries to cancel it, then the action is refused.

**AC-60** *(Changed in v3.1.)* Given a release in QA with 5 Verified, 2 To do, 1 In progress, and 1 In review item, when the CTO opens Ship, then the notice says 5 items go to production, lists "2 To do, 1 In progress, 1 In review" as going to the backlog, and shows the go/no-go decision.

**AC-61** *(Changed in v3.1.)* Given the release in AC-60 is shipped, then it is Released; the 5 Verified items are Done with the ship time as completion, without anyone moving them; the other 4 items are in the backlog with category Default and status To do, keep their assignees, and have no cycles.

**AC-62** Given a release in Planning, then Ship is not available.

**AC-63** Given the Stream's Done column, then it shows items put on production in the last 7 days by default, and the time picker can show the last 30 days or a date range.

**AC-64** *(Changed in v3.1.)* Given a Released release, when a Done item in it is rejected, then the item is Rejected in the Stream and the release still has no open item.

**AC-65** Given a bug in the Stream, then the release blocker control is not available.

### Cycles

**AC-66** Given an item in In review, when QA rejects it without a comment, then the action is blocked.

**AC-67** *(Changed in v3.1.)* Given an item in In review, when QA rejects it with a comment, then it is Rejected, its current cycle has reason `review`, the comment is a public comment, its assignee is notified, and its card shows the Rejected style and `↻ 2`.

**AC-68** *(Changed in v3.1.)* Given a Rejected item, when the assignee moves it to In progress, then the Rejected style is gone and the cycle badge stays.

**AC-69** Given item X assigned to developer D, when the CTO moves X from In progress to To review, then the cycle records D, not the CTO, as the person who delivered the work.

**AC-70** Given an unassigned item, when an Admin moves it to In review, then the cycle records nobody as the person who delivered the work.

**AC-71** *(Changed in v3.1.)* Given a Done item in the Stream, when a Support user opens it, then Reject is not shown and **Problem is back** is shown.

**AC-72** Given a Done item in the Stream, when a developer presses Reject without a comment, then the action is blocked.

**AC-73** Given an item in the Stream with two cycles, when a PM moves it to the backlog, then it has no cycles; when it is placed in a release again, its current cycle is cycle 1 with reason `planned`.

**AC-74** *(Changed in v3.1.)* Given an item at position 3 of its assignee's queue that reaches Verified and is later rejected (from Verified or Done), then it re-enters the queue at position 3, or directly below the pins if fewer unpinned items now precede it.

**AC-75** *(Changed in v3.1.)* Given an item that was first in its assignee's queue when it reached Verified, and the assignee has since pinned 2 items, when the item is rejected, then it is placed directly below the 2 pins, never above them.

**AC-76** *(Changed in v3.1.)* Given any list or board, then no control changes the status of several items at once, except On production in the Stream (AC-81).

**AC-77** *(Changed in v3.1.)* Given bug A (Support) is merged into a Done task T in the Stream, then T is Rejected in the Stream with a `production` cycle, T has no recurrence count, and A's reporter is subscribed to T.

**AC-78** Given a bug filed by QA directly into Release R, then it has cycle 1 with reason `planned` while it is still New in the triage queue.

### Verified and On production (v3.1)

**AC-80** Given a Verified item in the Stream, when the deployer moves it to Done, then its completion time is now and its Support subscribers receive the Done notification now, not at verification.

**AC-81** Given three Verified items in the Stream, when a tech user selects them and presses On production, then all three are Done, each with its own timeline event, and the Support channel receives one post listing them.

**AC-82** Given a Stream item Verified 3 days ago, then its card shows the age marker and hover shows the verification date; given a Verified item in a Release, then it never shows the marker.

**AC-83** Given a Stream item in In review, when QA moves it straight to Done, then it is Done and both the verification and completion times are now.

**AC-84** Given a Verified item in a Release, when the release ships, then the item is Done and its Support subscribers receive the Done notification at ship time.

**AC-85** Given the move to v3.1, then a Done item in a Release that is not Released is Verified with its original verification time, and a Done item in the Stream or in a Released release is still Done.

### Return requests (v3.1)

**AC-86** Given a Done item a Support user can see, when they press Problem is back without a comment, then the action is blocked.

**AC-87** Given a Done support-sourced bug, when Support presses Problem is back with a comment, then a Pending return request exists, the item stays Done, the recurrence count is unchanged, no second item exists, the Support reports list shows Return requested, the item is in the project's triage queue, and the triage lead is notified.

**AC-88** Given a Pending request, when a second Support user opens the item, then the button reads Add to pending request; their comment joins the same request and they are subscribed.

**AC-89** Given a Pending request on a Done item in a Released release, when a triager confirms it, then the item is Rejected in the Stream with a `production` cycle whose reason comment is the request's comment, the recurrence count is unchanged, the assignee is notified, and the requesters are notified that it is going back for a fix.

**AC-90** Given a Pending request, when a triager dismisses it without a comment, then the action is blocked; with a comment, the request closes, the item stays Done, no cycle starts, and the requesters receive the comment.

### Support verification (v3.1)

**AC-91** Given a support-sourced bug in **To review** in any project, when any Support user moves it to Verified, then it is Verified; given it is in the Stream, Support may move it straight to Done instead.

**AC-92** Given a support-sourced bug in In review, when a Support user rejects it with a comment, then it is Rejected with a `review` cycle; without a comment, the action is blocked.

**AC-93** Given a Support user, then they cannot move a support-sourced item to any other status, cannot move a non-support item at all, and see no On production action.

### Support channel (v3.1)

**AC-94** Given a project with an enabled Support channel, when a Support user files a report, then one post appears in the configured chat and topic, naming the project, the item, and the reporter.

**AC-95** Given a support-sourced item moved To review → In review → Verified within 60 seconds, then the channel receives one post showing To review → Verified.

**AC-96** Given a project without an enabled Support channel, then nothing is posted to any group, and Support subscribers still receive their private messages (§13).

**AC-97** Given the chat is unreachable, when a status changes, then the change succeeds, the post is retried and logged, and no error is shown to the user.

**AC-98** Given an internal note on a support-sourced item, then no Support channel post contains it.

### To review (v3.1)

**AC-99** Given items in To review and In review in three projects, then a QA user's To review tab lists all of them grouped by project and status, ordered by priority and then by the longest wait, with a counter on the tab, and the tab opens by default for QA but not for a Developer.

**AC-100** Given an item in the To review tab reaches Verified or is rejected, then it leaves the tab and the counter decreases.

---

## 13. Notifications

Telegram is the only channel. There is no email.

### To Support subscribers (reporter, recurrence reporters, return-request requesters, reporters of merged duplicates)

| Event | Content |
|---|---|
| Needs info | What information is missing |
| Cancelled | Reason (or "merged into BUG-n") |
| Done | Item is fixed and **on production**. Sent when the item reaches Done, never at verification |
| Return request decided | Confirmed: the item is going back for a fix. Dismissed: the triager's comment |

Besides these, Support is notified only when @mentioned in a public comment on an item they can see. A Reject that does not come from a return request sends nothing to Support; its subscribers hear again when the item reaches Done.

### To the project's Support channel (group topic)

Only for a project with an enabled Support channel, and only about its support-sourced items: new reports, every status change, and every return-request event, with the grouping rules of FR-71.

### To the project's triage lead

- New item in the triage queue
- Reporter replied on a Needs info item (item returned to New)
- Recurrence reported on a Cancelled item, or a report merged into one
- A new Pending return request
- Item moved into their project during triage

### To the assignee

- Item assigned
- Item due within 24 hours / overdue
- CTO/Admin reordered their queue, pinned, or unpinned an item
- Item rejected (from review, before production, or production), with the reason comment

### To the CTO

- Release go/no-go events (Phase 1, unchanged)
- Release shipped
- Release passed its target ship date without being Released (once per date; a later date notifies again)

---

## 14. Reporting

**The Phase 1 reports are not reliable after Phase 2.** The release report, regressions and component fragility, time to fix, contributions, and the dashboard were built for the Phase 1 model. Cycles, To review, Rejected, Verified, the new meaning of Done, the Stream, and return requests changed the data they read. They stay available, but their numbers must not be used for decisions until they are repaired. This is product debt **PD-1** (§16), the first item of Phase 3.

Every new report is deferred to Phase 3 (§16), including support intake, technical debt, backlog flow, and every cycle metric.

---

## 15. Deliberate Limitations

These are conscious trade-offs, not gaps.

| Limitation | Reason |
|---|---|
| Template field values are not filterable or reportable | They live in the description (P1) |
| No triage deadline, and no auto-close for Needs info | May be added later |
| No resource capacity planning | Unchanged from v1 |
| Customer ID is not a core field, and nothing is reported by customer | Generality (P2); add it to templates when needed. No report by customer is needed now |
| Cancelled items are never reopened | Clear history; recurrence covers the signal |
| Similar-item suggestions exist only while Jev is enabled | Suggestions without a reliable same-problem judgment would be ignored (see the engine document) |
| No bulk status changes, except On production | A status change is a claim about the work, made one item at a time. On production records one deploy event |
| The workflow is free | The team moves work as it really moves; only the gates that keep statuses truthful are enforced (§9.3) |
| A Stream item stays Verified until someone moves it to Done | Only the person who deployed knows what is on production; the system does not guess. The 3-day age marker is the safety net |
| Moving an item to the backlog deletes its cycles, including a production return | When work is planned again, its earlier cycles are not relevant. The rare escaped item that is later moved to the backlog loses its escape record; revisited in Phase 3 |
| An item is in at most one container | Items that must ship together are one release; cross-release features are followed with labels |
| A return request is only for Done items | Open items take a recurrence; Cancelled items are never reopened |
| A dismissed return request leaves no item behind | Its comment and decision are in the item's timeline |
| No named reviewer | QA works as a team; To review is a shared list |
| Support verification can stand in for QA on support-sourced items | Support tests its own hotfixes; the move is recorded on the timeline |
| Support channel posting is best-effort | A failed post is retried and logged; it never blocks work |

---

## 16. Deferred to Phase 3 and Product Debt

### Product debt

**PD-1 — Phase 1 reports are not reliable.** Release report, regressions and component fragility, time to fix, contributions, and the dashboard must be re-specified and repaired against the Phase 2 model: cycles and their start reasons, To review, Rejected, Verified, the meaning of Done, Stream items, and return requests. Both the verification time and the completion (on production) time are recorded, so each report must state which one it uses. **Priority: the first item of Phase 3.** Until then, the report pages say that their numbers are not reliable.

### Scheduling and estimation (from v1), now on Releases

- Gantt view
- Critical Path Method scheduling (finish-to-start dependencies only, optional lag, no dependency reason field)
- Dependencies between items
- Working calendar and public holidays
- Estimation fields (original estimate, remaining, actual), the freeze rule (estimates freeze when a release leaves Planning), and the actual-hours completion prompt
- Computed release health with alerts
- Critical-path marker on cards

### Reports

- Support intake, technical debt, and backlog flow reports
- Cycle metrics: review rejects, pre-production catches, escapes, escape rate, first-pass rate, cycles per item, pickup wait (defined in [cycle-model.md](cycle-model.md) §5)
- Return requests: confirmed and dismissed
- Wait times: To review → In review, Verified → Done
- Component fragility redesign: whether task cycles and production returns count
- Whether any metric is shown per developer (the data exists; individual performance scoring is a non-goal)
- Estimate-accuracy and release-performance reports

### Cycles

- Keeping a production return when an escaped item is later moved to the backlog (today its cycles are deleted)

### Decisions carried into Phase 3

- The working calendar and holiday source are **organization settings** (P2). The current values become defaults: Saturday–Wednesday 8h, Thursday 4h, Friday non-working (44h/week); public holidays from an external API, read-only.
- **The personal queue outranks the critical path** (P4). The Gantt only *displays* when a critical-path item sits low in its assignee's queue; this has no effect on the calculation and adds no workflow.

---

## 17. Open Points for Review

Choices made in this document that were not explicitly discussed:

1. **Needs info auto-return (BR-19)** — a reporter's comment returns the item to New. Without this, answered items could stay in Needs info unnoticed.
2. **"Won't fix" cancel reason (BR-13)** — added for accepted bugs that are later abandoned.
3. **Team overview (FR-43)** — added to serve the goal "CTO sees who works on what."
4. **Deactivated triage lead (AC-23)** — triage notifications fall back to Admin until a new lead is set.
5. **Merge into an open or Verified item (BR-49)** — the original stays as it is. A new report while the fix is not on production is expected.
6. *(v3)* **In review means "QA is checking it".** Code review happens inside In progress (for example in the pull request), so that a code-review rejection is not counted as a QA reject.
7. *(v3)* **Who works the QA side.** *Resolved in v3.1* by the To review tab (FR-73).
8. *(v3)* **Support's Done notification for release items.** *Resolved in v3.1:* sent at ship (BR-76).
9. *(v3)* **Ship without go.** Shipping shows the go/no-go decision but does not require **go**.
10. *(v3)* **UI names of reject reasons.** `review` = Rejected in review, `release_qa` = Caught before production, `production` = Problem on production.
11. *(v3)* **Release lifecycle transitions (FR-50)** are proposed, including QA → Development.
12. *(v3.1)* **The name "Verified".** Chosen to read as "approved, not on production yet". Another label (for example "Ready for production") changes only the text.
13. *(v3.1)* **Done gate in Releases (BR-68).** The free workflow would let anyone move a release item to Done and bring back the "which items are on production?" problem. The gate is the one new workflow rule.
14. *(v3.1)* **"Already on production" without a tick.** Because the workflow is free, a verifier in the Stream moves the item straight to Done; no extra control is needed. This replaces the tick discussed during design.
15. *(v3.1)* **Support channel volume.** Every status change is posted, with 60-second grouping. If the topic is still noisy, the first thing to drop is the intermediate statuses (In progress, To review, In review, Blocked).
16. *(v3.1)* **Return request on a task.** A Support user can see a Done task only when subscribed to it (a report merged into it), so a return request can exist on a task; nothing about it is bug-specific.
17. *(v3.1)* **Companion documents updated with v3.1:** [cycle-model.md](cycle-model.md), [prd-search-engine.md](prd-search-engine.md) (merge-hint wording). [prd-mcp.md](prd-mcp.md) needs no rule change: agents still never change status, recurrence stays refused on Done and is now allowed on Verified. Slice specs and [CONTEXT.md](../../CONTEXT.md) are updated when v3.1 is built.

---

## 18. Glossary

| Term | Meaning |
|---|---|
| Work item | Any bug or task |
| Priority | The shared importance scale: Critical, High, Medium, Low |
| Container | Where an item is delivered from: the project's Stream or one of its Releases |
| Stream | The one always-open container per project; each item ships on its own |
| Release | A planned delivery; its items ship together when it is shipped |
| Ship | Releasing a Release: its Verified items become Done, its other items go to the backlog |
| To review | Delivered by the developer, waiting for QA |
| Verified | Approved by QA (or Support, for support-sourced items). Not on production yet |
| Done | On production |
| On production | The Stream action that moves several Verified items to Done at once |
| Rejected | Delivered work sent back with a reason, not yet picked up |
| Reject | The one action that sends work back from To review, In review, Verified or Done, and starts a new cycle |
| Cycle badge | `↻ N` on an item past its first cycle |
| Backlog | A project's items with no container that are not Done or Cancelled |
| Cycle | One pass of work on an item until delivered; see [cycle-model.md](cycle-model.md) |
| Start reason | Why a cycle started: planned, review, release QA (caught before production), production |
| Return request | Support's request that a Done item come back for a fix; confirmed or dismissed in triage |
| Support report | A bug submitted by Support through a template |
| Support channel | A project's Telegram chat and topic that receive updates about its support-sourced items |
| Template | A per-project set of fields Support must fill, composed into the description |
| Triage queue | A project's New and Needs info bugs and Pending return requests |
| Triage lead | The person notified of and responsible for a project's triage queue |
| Recurrence | A repeated report of an open (not Done) or Cancelled bug, with a required comment |
| Merge | Folding a duplicate report into its original (bug or task): content as comment, reporter subscribed, recurrence +1 on an open or Cancelled bug, a Reject on a Done item |
| To review tab | The My Work tab that lists every To review and In review item in every project |
| Technical debt | A task flagged as debt; hidden from the default backlog |
| Personal queue | One person's ordered list of open assigned items across all projects |
| Pin | A guaranteed top position in a queue; at most 4 per person |
| Queue history | Log of reorders and pins on a person's queue |
| Similar-item suggestion | An engine-proposed existing item that may describe the same problem |
| Product debt | A known gap that is recorded, owned, and scheduled, such as PD-1 |
