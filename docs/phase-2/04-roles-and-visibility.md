# 04 — Roles and Visibility

> **Depends on:** 03 · **PRD:** §7 (roles, triage lead, permission matrix), FR-06, BR-15, BR-30–32; AC-07, AC-08, AC-23, AC-47
> The support-specific screens are built in 05. This slice makes the Support role safe to create.

## Problem Statement

Releasewatch has four roles: QA, Developer, CTO, and Admin. Everyone sees everything. Phase 2 adds people who must not see everything. Support staff will file reports, but they must never see internal notes, tasks, or internally filed bugs, and they must never be assigned work. A Project Manager role is also needed to manage backlog, releases, and milestones. Permission checks today are scattered `require_role(...)` calls with no single source of truth, and the UI hides or shows controls by guessing.

## Solution

Add `pm` and `support` roles. Introduce a pure **Policy** module that answers "can this user do this action on this item or project, and if not, why". Every route checks Policy. Every item response carries `allowed_actions` and `blocked_actions` from Policy, so the UI shows controls disabled with the Policy's reason instead of guessing. Enforce Support visibility in every read path: lists, detail, timeline, search, export, inbox, and WebSocket pushes. Make the project triage lead required, and flag projects whose lead is missing or deactivated.

## User Stories

1. As an admin, I want to give a user the Support role, so that support staff can use Releasewatch safely.
2. As an admin, I want to give a user the Project Manager role, so that someone can manage backlog, releases, and milestones without being CTO or admin.
3. As a Support user, I want to see only support-sourced items, so that I'm not exposed to internal engineering work. (BR-30, AC-08)
4. As a Support user, I want to see only public comments on those items, so that internal discussion stays internal. (BR-30, BR-31, AC-07)
5. As a Support user, I want internal notes excluded from counts, previews, search results, inbox items, and Telegram messages too, so that nothing leaks through side channels. (AC-07)
6. As a Support user opening a link to an item I may not see, I want a "not found" page, so that I learn nothing about its existence.
7. As a Support user, I want a navigation that shows only New report, Support reports, Inbox, and my profile, so that I'm not confronted with screens I can't use.
8. As a tech user, I want Support users never offered in any assignee picker, so that work can't be given to someone who can't do it. (BR-32, AC-47)
9. As a tech user, I want the API to refuse assigning an item to a Support user, so that the rule holds even outside the UI. (BR-32)
10. As a Support user, I want the tech-only "internal note" option absent from my comment box, so that I never try to post one.
11. As a tech user, I want internal notes and public comments in one chronological timeline, with internal notes visibly distinct, so that I read one history. (FR-06; the timeline already stores `is_internal`)
12. As a PM, I want to manage releases, backlog, and milestones in any project.
13. As a developer who is a project's triage lead, I want to manage that project's releases, backlog, and milestones, and no other project's. (§7.3 footnote ²)
14. As any tech user, I want to see a control I can't use shown disabled with a tooltip explaining why, so that I know the feature exists and what's stopping me. (§7.3)
15. As an admin, I want a project to require a triage lead on create and on edit, so that every project's triage queue has an owner. (BR-15)
16. As an admin, I want projects without an active triage lead flagged in Settings and on the project list, so that I fix them. (AC-23)
17. As an admin, I want triage notifications for a project without an active triage lead sent to all admins until a lead is set, so that no report goes unseen. (AC-23)
18. As an admin, I want deactivating a user who is a triage lead to warn me which projects will lose their lead.
19. As a CTO, I want the permission matrix in PRD §7.3 enforced exactly, so that roles mean what the PRD says.
20. As a Support user, I want real-time inbox pushes only for items I can see.

## Implementation Decisions

### Roles

- `UserRole` gains `pm` and `support`. `ROLE` in `lib/constants.js` gains labels and colors, documented in `docs/design.md` §3.
- **Tech roles** = `qa, developer, pm, cto, admin`. **Assignable** = tech roles. Support is neither.
- JIT-provisioned users (Keycloak/LDAP) are still created as `developer`, per `CONTEXT.md`. No change.

### Policy module (pure)

- Signature shape: `decide(actor, action, target) -> Allowed | Denied(code, detail)`. `actor` is a plain `(id, role)`. `target` is a plain snapshot: item fields such as source, type, status, and assignee, plus the project's `triage_lead_id` and kind.
- **Actions** are a closed enum mirroring §7.3 and later slices:
  - `view_item`, `comment_public`, `comment_internal`, `create_item`, `transition:<to>`, `assign`, `set_priority`, `set_due_date`, `flag_tech_debt` (08), `triage` (06), `report_recurrence` (07), `submit_support_report` (05), `manage_templates` (05), `manage_backlog` / `manage_releases` / `manage_milestones` (08/09), `view_queue` / `reorder_queue` / `pin` (10), `view_team_overview` (11), `go_nogo`, `manage_users`, `manage_projects`.
- The §7.3 matrix is transcribed as one data table inside Policy, and matrix tests assert against it. The flag rules from PRD §9.2 go in the same table:
  - Release blocker: QA, the project's triage lead, PM, CTO, and Admin.
  - Regression action: QA, the project's triage lead, PM, and Admin.
  - Technical debt: any tech role. Rules that depend on the item go in small predicate functions next to it:
  - Support can view only `source=support` items. `source` arrives in 05; until then, Support views nothing.
  - "Manage releases, backlog, and milestones" for a developer only when `actor.id == project.triage_lead_id`.
  - Self-verification, which moves from the Workflow context into Policy's `transition:done` predicate. Workflow keeps pure status rules.
  - The Support-is-not-assignable check for the assignee target.
- **Composition:** `IssueService.transition()` checks Policy (can this actor attempt it) and then Workflow (is the move legal). The response's `allowed_actions` and `blocked_actions` are built by running Policy over every action relevant to the item, combined with `allowed_transitions` from Workflow.
- `require_role(...)` stays for coarse admin-only routes. Item-level routes switch to a `authorize(action, target)` dependency backed by Policy.

### Visibility enforcement (Support)

A single query helper, `visible_issues(actor)`, returns the base `select(Issue)` filtered for the actor. It is used by **every** read path: `GET /issues`, `/issues/{id}`, `/issues/by-number/*`, `/issues/export`, `/search` (both keyword and semantic), `/reports/*` (Support gets 403 on reports), `/inbox` (items for invisible issues are never created, and existing ones are filtered), and the WebSocket inbox push (skipped for Support on invisible items). The timeline for Support uses `include_internal=False`, and comment counts are computed the same way. Telegram templates for Support recipients never include internal content, because Support only ever receives public events (formalized in 06).

### Triage lead

- Project create and update require `triage_lead_id` pointing to an active tech-role user (422 otherwise). Existing null leads are allowed to remain but are flagged.
- `ProjectResponse` gains `needs_triage_lead: bool`, which is true when the lead is null or inactive.
- `_triage_recipients()` falls back to all active admins when `needs_triage_lead` is true.
- `PATCH /team/{id}/deactivate` responds with `affected_projects` so the UI can warn about them first. `GET /team/{id}/deactivation-impact` is available for the confirmation dialog.

### Frontend

- `useApp().user.role` drives a role-specific sidebar. Support gets a minimal nav (the routes arrive in 05). Tech roles get today's nav plus what later slices add.
- A shared `<ActionButton action="..." item={item}>` renders enabled, disabled with a tooltip from `blocked_actions`, or nothing for Support-invisible actions. Existing issue action buttons migrate to it.
- The assignee picker (`UserMentionSelector` and similar) requests `GET /team?assignable=true`.
- A Settings → Projects banner and a project-list badge appear when `needs_triage_lead` is set.

## Testing Decisions

- **Permission matrix test:** one parametrized API test per row of §7.3 × role. Each case makes the smallest request that exercises the capability and expects success or 403/404. This is the only large table test in Phase 2, and it is worth it.
- **Leak tests (Support)** for every read path listed above, each with an internal note and a non-support item present: `test_ac_07_support_never_sees_internal_notes`, `test_ac_08_support_never_sees_tasks_or_internal_bugs`, plus search, export, inbox, and WebSocket push.
- `test_ac_47_support_not_assignable` covers both the picker endpoint and the assign attempt.
- `test_ac_23_deactivated_triage_lead_flags_project_and_notifies_admins`.
- A `transition:done` self-verification refusal still returns `code: self_verification` after moving into Policy (a regression guard for 02).

## Out of Scope

- The Support screens themselves (05).
- Project membership or per-project roles. Every tech user sees every project, as in Phase 1.
- Reading identity-provider groups to set roles (still deferred, per `CONTEXT.md`).

## Further Notes

- Returning 404 rather than 403 for invisible items is deliberate. It keeps Support from probing numbers.
