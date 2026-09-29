# Releasewatch

A release-scoped QA issue tracker for software teams.

## Language

### Identity & Auth

**Local account**:
A user whose credentials (username + bcrypt password) are stored and verified by Releasewatch itself. The built-in, always-available way to sign in; the app is fully usable with local accounts only.
_Avoid_: internal user, native login

**Identity Provider**:
An optional, external system that authenticates a user on Releasewatch's behalf (e.g. Keycloak via OIDC, or LDAP). Turning one on never removes local accounts — providers are additive and optional.
_Avoid_: IdP (spell it out), SSO (that's the flow, not the system), auth backend

**External Identity**:
A durable link between one local `users` row and one identity at a provider, keyed by `(provider, provider_subject)`. Lives in its own `user_identities` table so the `users` table stays vendor-neutral. One user may hold several (e.g. local + keycloak).
_Avoid_: keycloak_id, social account, federated user

**provider_subject**:
The stable, opaque identifier a provider uses for a user (Keycloak's `sub` UUID; an LDAP entry's uid/DN). The thing we link on — not the username, which can change.

**JIT provisioning**:
Creating (or updating) the local `users` row automatically the first time an external identity signs in, from the provider's claims — instead of an admin pre-creating it.
_Avoid_: auto-import, sync-on-login (that's the role step)

**Releasewatch token**:
The application's own JWT that the frontend sends on every API request. The only token the API trusts. External providers authenticate the *initial* login and silent re-mint; their tokens never reach Releasewatch endpoints.
_Avoid_: app token, session token, access token (ambiguous with the provider's)

**Role**:
A team member's global capability level: `support`, `qa`, `developer`, `pm`, `cto`, or `admin`. Everyone but `support` is a **tech role**. Only tech roles can be assigned work. What each role may do is PRD §7.3, enforced by `backend/app/policy.py`. Support sees only support-sourced items and never internal notes. Stored on the local user and is always the source of truth. In Phase 1, any user provisioned via a provider is seeded as `developer` and an admin adjusts them in-app; reading provider groups to seed the role is deferred to a later phase. In-app role management always wins and is never overwritten by a provider.
_Avoid_: permission, group (a group is the provider-side concept, deferred past Phase 1)

### Issue lifecycle

**Work item**:
The product term for a single trackable unit of work. Implemented as the existing `Issue` model and `issues` table — kept as-is rather than renamed, since renaming would churn every file without changing behavior. Every work item is currently a bug; tasks arrive in Phase 2 slice 03 on the same table via a `type` column.
_Avoid_: "issue" as the product-facing word (say "bug" or "work item"); "issue" stays correct as the implementation name in code, routes, and table names.

**Flow status**:
The unified status a work item carries through its lifecycle: `new, needs_info, todo, in_progress, in_review, done, blocked, cancelled`. Replaces Phase 1's status set (`new, triaged, in_progress, fixed, verified, closed, regression, blocked`). `is_regression` and `is_release_blocker` are flags on the work item, not statuses — a bug can be `in_progress` and `is_regression=true` at the same time.
_Avoid_: `triaged`, `fixed`, `verified`, `closed`, `regression` as statuses — none of those exist anymore. "Fixed" now means `in_review` or `done`; "Verified" means `done` reached from `in_review` (`verified_at` is set).

**Priority**:
The one importance scale shared by bugs and tasks: `critical, high, medium, low` (`issues.priority`, the `Priority` enum). A New or Needs info bug may have none (shown as "Unrated"); accepting a bug requires one; a task is created at `medium`. Phase 1's `severity` was migrated into it: blocker → critical plus the release-blocker flag, critical → critical, major → high, minor → medium, enhancement → low.
_Avoid_: "severity" (the Phase 1 bug-only scale, gone), P1–P4 (the slice-03 task scale, gone), "urgent" (the Urgent flag was removed; "do this first" is a pin in the personal queue).

**Workflow**:
The pure module (`app/workflow.py`) that is the single place status-transition legality is decided. Takes plain values in (item type, current status, target status, a context dict) and returns plain values out — no database or HTTP access. `IssueService.transition()` is the only code that asks it and writes `issue.status`. As of 2026-09-22 for bugs and 2026-09-23 for tasks, by product decision, it allows every status to move to every other status (tasks are never offered the bug-only `new`/`needs_info`) — no reason required, no self-verification block, no release gate — so today it always says yes; the module exists so that if a rule is reintroduced later, it's written once here rather than scattered across callers. The API still exposes its verdict per item as `allowed_transitions` / `blocked_transitions` (currently: every other status, nothing blocked) so the frontend never hardcodes the status list.
_Avoid_: writing transition logic in a route or another service — even permissive, Workflow is the one place that decision lives. Not to be confused with Policy (slice 04), which will own *who* may act, not *what* moves are legal.

**Regression action**:
The dedicated endpoint (`POST /issues/{id}/regression`, `IssueService.regress`) that sends a bug back to `in_progress`, incrementing `regression_count` and recording a regression cycle (`source=action`) when the bug has a release (skipped otherwise — the direct action only records release regressions). Callable from any status. The other way a bug becomes a regression is a **merge regression**.
_Avoid_: treating "regression" as a status a bug sits in, or "regression status" — Phase 1's `regression` status was removed; a regressed bug's status is `in_progress`, distinguished by the `is_regression` flag plus this action.

**Source**:
Who filed a work item: `internal` (a tech user, through New issue) or `support` (a Support user, through a support template). Stored as `issues.source`, fixed at creation. Support sees `support` items plus items they're a **subscriber** of (BR-30, widened 2026-09-24 so a report merged into an internal original stays readable) — that visibility rule is `authz.support_visibility_clause` and `policy._can_view`. Support-sourced items carry a teal "Support" badge in the triage queue and issue rows.
_Avoid_: "customer bug", "ticket" — a support report is an ordinary bug with `source=support`.

**Support template**:
A per-project form (`support_templates` + ordered `support_template_fields`) that CTO and Admin define so Support is asked for the right information. A project is reportable while it has at least one active template — there is no separate toggle. Templates are deactivated, never deleted. Field types: short text, long text, number, date, date-time, single select, link.
_Avoid_: "form" alone (ambiguous with any UI form); "custom fields" — template values are never stored as columns.

**Support report**:
A bug filed through `POST /support/reports` from a support template. The field values are validated and composed (`app/support_report.py`) into the bug's description, in template order, with user text escaped; that description is the record (BR-34), so editing or deactivating a template never changes an existing report (BR-35). A raw copy of the values goes into the `filed` timeline event's meta for forensics only. Status starts at `new`, priority empty, `recurrence_count` 1.
_Avoid_: reading template values back from anywhere but the description.

**Cancel reason**:
An optional reason (`user_error, expected_behavior, cannot_reproduce, duplicate, wont_fix, no_longer_needed`) recordable when an item is cancelled without being finished (`no_longer_needed` is task-only; the rest are bug-only). Not required — cancelling with no reason is allowed.
_Avoid_: "closed"/"closing" — Phase 1's `closed` status is gone. A finished bug is Done; an abandoned one is Cancelled, optionally with a reason.

### Containers (08a)

**Container**:
Where a work item is placed: its project's **Stream**, one of its **Releases**, or none — the **backlog**. Stored as one column, `issues.release_id` (a row of `releases`; null is the backlog). Every placement path — create, triage Accept, PATCH, bulk move — goes through `container_service.resolve`: the container must be the item's project's (`release_project_mismatch`) and, if a Release, not Released or Cancelled (`release_closed`). A Done item never changes container (`done_item_immobile`, BR-54). The UI has one picker for it, `ContainerPicker` (Backlog / Stream / open releases).
_Avoid_: "hotfix" (not a concept in v3 — urgent work is an item in the Stream), "milestone" and "project kind" (both removed).

**Stream**:
The one always-open container every project has (`releases.kind = stream`, BR-51), created with the project by an ORM hook, with no lifecycle status. Each item in it ships on its own when Done. It can't be renamed, cancelled, archived, go/no-go'd or deleted (409 `stream_immutable`, FR-46). Phase 1 release screens — release lists, the release switcher, dashboard, reports — never show it (`kind = release` only); `ProjectResponse.stream_id` and `IssueResponse.container_kind` expose it.

**Release** (container):
A container whose items ship together (`releases.kind = release`). Lifecycle `planning → development → qa → released`, or `cancelled` (PRD v3 §8.7); `code_freeze_date`, `target_date` (target ship date) and `released_at`. "Blocked" is not a status — a blocked release is one in QA with a no-go decision. The release-blocker flag exists only on a bug in a Release (`release_blocker_release_only`, BR-58); moving the bug out clears it with a `blocker_cleared` event.
_Avoid_: `active`, `blocked`, `archived` as release statuses (Phase 1 values, gone).

### Triage (slice 06)

**Triage queue**:
A project's New and Needs info bugs, oldest first, with source, reporter, recurrence count, and age (FR-17). The Triage page's New and Needs info tabs. Tasks never enter it.
_Avoid_: "unassigned issues" — the queue is about the decision, not the assignee.

**Triage outcome**:
The one decision a triager (any tech role) applies to a queued bug through `POST /issues/{id}/triage` (`TriageService`): **Accept** (priority required; assignee, container and backlog category optional — the container is the Stream, an open release, or none, which puts the bug in the backlog, in Default unless another category is picked) → To do; **Needs info** (a public comment saying what's missing) → Needs info; **Duplicate** (a merge) → Cancelled, reason Duplicate; **Reject** (user error, expected behavior, or cannot reproduce) → Cancelled. Each writes one `triaged` timeline event with its inputs. Only New and Needs info bugs can be triaged (`not_in_triage`). A public reply by the reporter or any Support user sends a Needs info bug back to New and tells the triage lead (FR-19).
_Avoid_: "triaged" as a status (gone since slice 02), "needs clarification" (the Phase 1 name).

**Subscriber**:
A user on an item's `issue_subscribers` list — its reporter (on create), reporters of duplicates merged into it, and recurrence reporters (reason `recurrence`). The first reason wins. Support subscribers receive the item's three Support notices — Needs info, Cancelled, Done (`support_needs_info`, `support_cancelled`, `support_done`; a Cancelled that is a merge says "merged into BUG-n"). Besides those, Support is notified only when @mentioned in a public comment on an item they can see (2026-09-24); `fan_out` drops Support from every other event, and internal notes never reach them (BR-31). A Support subscriber may view the item. Support works as a team: every Support user sees every support report, and the Support reports list names the reporter with a "Me" filter.
_Avoid_: "watcher", "follower".

**Merge**:
Folding one report into an original (BR-50), owned by `MergeService.merge_into`: the original's `recurrence_count` +1 (atomic UPDATE), the merged content added as a public comment ("Merged from BUG-n … Reported by @reporter" — a tech reporter gets the mention notice, a Support reporter only their Support notice), and the merged report's reporter subscribed. The Duplicate outcome merges and cancels the duplicate; recurrence (07) merges without a second item. The original must be a bug in the same project that isn't itself a duplicate (`duplicate_of_duplicate` suggests its original).
_Avoid_: "link duplicate" (Phase 1's endpoint, removed).

**Recurrence**:
One more occurrence of an open or Cancelled bug, recorded with `POST /issues/{id}/recurrences` instead of a second report (FR-13, slice 07). Any role, on a bug they can see; a comment (the new customer's details) is required. It goes through `MergeService.merge_into`: `recurrence_count` +1, a public `recurrence` timeline event with the comment as body, the reporter subscribed, and an `issue_recurrences` row (for reports over time — merges aren't recorded there). On a Cancelled bug the triage lead gets `recurrence_on_cancelled` and the bug stays Cancelled; on an open bug the assignee and reporter get the ordinary `comment` notice. A Done bug refuses it (409 `recurrence_on_done`, BR-23): a returning problem is filed as a new report and merged in triage, where it becomes a merge regression. Tasks refuse it (`recurrence_bug_only`). `recurrence_count` starts at 1 — the original report is one occurrence.
_Avoid_: "+1", "bump", "duplicate report".

**Merge regression**:
A merge into a Done original (BR-49): a regression cycle is recorded (`source=merge`, in the duplicate's release, or with none), the original moves to In progress with the regression flag set and count +1, and its assignee gets the regression notice. Support hears nothing until it's Done again. Merges into Cancelled originals leave them Cancelled and notify the triage lead; any other status is unchanged.

**Regression cycle**:
One `regression_history` row — the record that a fixed bug came back. `source` is `action` (the regression action) or `merge`. `release_id` is null only for a merge regression whose duplicate had no release; release reports and fragility analysis select by release, so those cycles stay out of them (BR-25).


### Backlog (slice 08)

**Backlog**:
A project's open work that isn't placed yet: items with no **container** whose status is a board status other than Done (To do, In progress, In review, Blocked) — never New/Needs info (triage) or Done/Cancelled (BR-04). Membership is derived by `backlog_clause` / `backlog_items()` in `BacklogService`, never stored. Shown as a ranked list, not a board: grouped by the project's backlog categories in their order (collapsible, with counts; every technical-debt task groups under Technical debt, last, whatever its category) or flat in rank order, drag to rank, multi-select and bulk move to the Stream or an open release (`POST /issues/bulk-move`, all or nothing; a Done item fails it with `done_item_immobile`). Ranking and bulk move need `manage_backlog` (PM, CTO, Admin, and a developer who is the project's triage lead). The header's "untouched for over 6 months" count is display only (`updated_at`; re-ranking doesn't count as touching).
_Avoid_: "icebox", "parking lot", an "add to backlog" action — placement decides membership.

**Backlog category**:
One of a project's own categories (`backlog_categories`, 2026-09-28) — a name, an icon and a colour from curated sets. Every project has a fixed **Default** (created with the project; never renamed, restyled, moved or deleted; always first). Every item — bug or task — always has exactly one category of its own project (`issues.backlog_category_id`, NOT NULL, composite FK with `project_id`); nothing chosen means Default, so the UI never requires a pick. CTO and Admin manage the rest in Settings → Backlog categories: names unique per project ignoring case (≤ 40 chars), at most 20 per project, ordered by drag — the grouped backlog follows that order. Deleting a category moves all its items to Default (a timeline entry each, no notification). An item moved to another project lands in that project's Default. Technical debt is not a category.
_Avoid_: "tag" or "label" (labels are a separate, cross-project thing); "uncategorized" (there is no such state).

**Backlog rank**:
An item's position in its project's backlog (`issues.backlog_rank`, a float). A new member goes to the bottom (max + 1024); a drag places it midway between its new neighbours; when a gap would fall below 1e-6 the project is renumbered in one statement. Kept when the item leaves, so it returns to where it was.

**Technical debt**:
A flag on a task (`issues.is_tech_debt`, BR-36) — never on a bug (409 `tech_debt_task_only`). Any tech role sets it at creation or later; it adds no fields (components, risk and approach go in the description). Debt tasks are hidden from the backlog unless "Show technical debt" is on, and are listed on the Technical debt page (`GET /tech-debt`, filterable by several projects, status and assignee). Once assigned or placed in a release a debt task shows on boards and in queues like any task, with its marker (BR-37).
_Avoid_: "debt" as a backlog category (it was one before PRD v2.1).