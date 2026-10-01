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
The unified status a work item carries through its lifecycle: `new, needs_info, todo, in_progress, in_review, done, blocked, cancelled`. Replaces Phase 1's status set (`new, triaged, in_progress, fixed, verified, closed, regression, blocked`). `is_release_blocker` is a flag on the work item, not a status; work that came back is a new **cycle**, not a status either.
_Avoid_: `triaged`, `fixed`, `verified`, `closed`, `regression` as statuses — none of those exist anymore. "Fixed" now means `in_review` or `done`; "Verified" means `done` reached from `in_review` (`verified_at` is set).

**Priority**:
The one importance scale shared by bugs and tasks: `critical, high, medium, low` (`issues.priority`, the `Priority` enum). A New or Needs info bug may have none (shown as "Unrated"); accepting a bug requires one; a task is created at `medium`. Phase 1's `severity` was migrated into it: blocker → critical plus the release-blocker flag, critical → critical, major → high, minor → medium, enhancement → low.
_Avoid_: "severity" (the Phase 1 bug-only scale, gone), P1–P4 (the slice-03 task scale, gone), "urgent" (the Urgent flag was removed; "do this first" is a pin in the personal queue).

**Workflow**:
The pure module (`app/workflow.py`) that is the single place status-transition legality is decided. Takes plain values in (item type, current status, target status, a context dict) and returns plain values out — no database or HTTP access. `IssueService.transition()` is the only code that asks it and writes `issue.status`. As of 2026-09-22 for bugs and 2026-09-23 for tasks, by product decision, it allows every status to move to every other status (tasks are never offered the bug-only `new`/`needs_info`) — no reason required, no self-verification block, no release gate — so today it always says yes; the module exists so that if a rule is reintroduced later, it's written once here rather than scattered across callers. The API still exposes its verdict per item as `allowed_transitions` / `blocked_transitions` (currently: every other status, nothing blocked) so the frontend never hardcodes the status list.
_Avoid_: writing transition logic in a route or another service — even permissive, Workflow is the one place that decision lives. Not to be confused with Policy (slice 04), which will own *who* may act, not *what* moves are legal.

**Reject**:
The one way to send work back so it starts its next **cycle** (09a, ADR 0004; replaced 08a's Reject / Return from release QA / Problem on production). `POST /issues/{id}/reject {comment}` from **To review**, **In review** or **Done** (409 `not_rejectable` elsewhere); the comment is required (422 `reason_required`) and is written as an ordinary public comment. The item lands in **Rejected** and its assignee gets `item_returned` (never Support). The server records where the problem was caught as the new cycle's `start_reason`: `review` from To review / In review; from Done, `release_qa` in a Release that hasn't shipped, else `production` (a Released release's item moves to the Stream). A merge into a Done item is the same Reject (`MergeService`). Policy action `reject` (every tech role). `/returns` and `/reopen` are aliases for Done items only (409 `not_done`). `/transition` never enters Rejected (409 `use_reject`), and `/verify` with `outcome: fail` is refused the same way.
_Avoid_: "return", "send back", "regression" as separate actions — users see one Reject; reports split by `start_reason`. "Bulk" rejects — there is no way to change several items' status at once.

**Rejected**:
The status of delivered work that was sent back with a reason and not yet picked up (09a). Entered only by Reject; left freely (the developer picks it up by moving it to In progress). Shown on top of the To do column, in the reason's hue (`IssueResponse.reject_reason`, `reject_comment_id`). Moving a Rejected item to the backlog (or shipping its release) makes it To do, since its cycles are deleted.

**To review**:
The developer has delivered the work; it waits for QA, who picks it up by moving it to **In review** (09a). The first move into To review or In review, whichever comes first, is the cycle's delivery (`submitted_at`, `delivered_by_id`).

**Cycle badge**:
`↻ N` on any item whose `cycle_number ≥ 2`, on every status — how a developer still sees that picked-up work came back. Replaced 08a's returned marker.

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
The one always-open container every project has (`releases.kind = stream`, BR-51), created with the project by an ORM hook, with no lifecycle status. Each item in it ships on its own when Done. It can't be renamed, cancelled, archived, go/no-go'd or deleted (409 `stream_immutable`, FR-46). Release lists, dashboard and reports never show it (`kind = release` only); it has its own page, `/projects/:slug/stream` (slice 09) — a board whose Done column shows the last 7 days by default — and the release switcher lists it first as a link to that page. `ProjectResponse.stream_id` and `IssueResponse.container_kind` expose it.

**Release** (container):
A container whose items ship together (`releases.kind = release`). Lifecycle `planning → development → qa → released`, or `cancelled` (PRD v3 §8.7); `code_freeze_date`, `target_date` (target ship date) and `released_at`. "Blocked" is not a status — a blocked release is one in QA with a no-go decision. The release-blocker flag exists only on a bug in a Release (`release_blocker_release_only`, BR-58); moving the bug out clears it with a `blocker_cleared` event.
_Avoid_: `active`, `blocked`, `archived` as release statuses (Phase 1 values, gone).

**Release lifecycle** (slice 09):
The allowed release status changes, owned by the pure module `app/release_lifecycle.py` (FR-50): Planning → Development → QA, QA → Development, Planning/Development/QA → Cancelled only while no item is Done (`release_has_done_items`, BR-55), and QA → Released only through **ship** (`use_ship`, `ship_only_from_qa`). Released and Cancelled are final (`release_final`) and read-only. `ReleaseResponse.allowed_transitions` / `allowed_actions` carry what the caller may do; the UI renders them. **Progress** is Done ÷ non-cancelled items (BR-47) and **Overdue** is a passed target ship date on a release that isn't Released or Cancelled (BR-48) — both computed on read, never stored. Changes to a release are recorded as **release events** (`release_events`, the Activity tab), separate from item timelines.
_Avoid_: "blocked release" as a status; "overdue" as a status (it's a marker).

**Ship** (slice 09):
The one action that makes a release Released (`ReleaseService.ship`, FR-53): CTO, Admin, or the project's triage lead (`ship_release`), only from QA. It stamps `released_at`, moves every item that isn't Done or Cancelled to the backlog as To do in category Default — assignee kept, cycles deleted (BR-56, BR-62) — and sends `release_shipped` to the items' assignees and the CTOs. Go/no-go is shown in the ship notice but isn't required. **Cancel** moves open items the same way. A release that passes its target ship date sends `release_overdue` to active CTOs once per date (a daily Celery beat job); these two are release-only notifications (`inbox_items.issue_id` null, `release_id` set).
_Avoid_: "release" as a verb for this action; "deploy".

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
Folding one report into an original (BR-50), owned by `MergeService.merge_into`: the original's `recurrence_count` +1 (atomic UPDATE), the merged content added as a public comment ("Merged from BUG-n … Reported by @reporter" — a tech reporter gets the mention notice, a Support reporter only their Support notice), and the merged report's reporter subscribed. The Duplicate outcome merges and cancels the duplicate; recurrence (07) merges without a second item. The original must be a bug or a task in the same project that isn't itself a duplicate (`duplicate_of_duplicate` suggests its original).
_Avoid_: "link duplicate" (Phase 1's endpoint, removed).

**Recurrence**:
One more occurrence of an open or Cancelled bug, recorded with `POST /issues/{id}/recurrences` instead of a second report (FR-13, slice 07). Any role, on a bug they can see; a comment (the new customer's details) is required. It goes through `MergeService.merge_into`: `recurrence_count` +1, a public `recurrence` timeline event with the comment as body, the reporter subscribed, and an `issue_recurrences` row (for reports over time — merges aren't recorded there). On a Cancelled bug the triage lead gets `recurrence_on_cancelled` and the bug stays Cancelled; on an open bug the assignee and reporter get the ordinary `comment` notice. A Done bug refuses it (409 `recurrence_on_done`, BR-23): a returning problem is filed as a new report and merged in triage, where it becomes a return. Tasks refuse it (`recurrence_bug_only`). `recurrence_count` starts at 1 — the original report is one occurrence.
_Avoid_: "+1", "bump", "duplicate report".

**Merge into Done**:
A merge into a Done original (BR-49) is a **Reject**: the original goes to Rejected and its next **cycle** starts (`release_qa` in a Release that hasn't shipped, else `production`, moving to the Stream out of a Released release) with the merge comment as its reason and the merged report as `start_merged_issue_id`; its assignee gets `item_returned`. The original may be a bug or a task (BR-20); only a bug's `recurrence_count` grows. Support hears nothing until it's Done again. Merges into Cancelled originals leave them Cancelled and notify the triage lead; any other status is unchanged.

**Cycle**:
One pass of work on an item until it is delivered — picked up, worked, sent to To review or In review, verified (`issue_cycles`, docs/phase-2/cycle-model.md). A cycle belongs to one item and one container and exists only while the item has a container: cycle 1 starts when the item is placed (created in one, accepted into one, moved in from the backlog) with `start_reason = planned` — a bug filed straight into a release has it while still in triage. Every later cycle starts because the work came back: `review` (rejected in review), `release_qa` (a Done item in a Release that hasn't shipped), `production` (shipped work). Moving an item to the backlog deletes its cycles. `issues.current_cycle_id` points at the current one (null exactly when the item has no container). `delivered_by_id` is the assignee when the work first went to To review or In review — never the actor. `CycleService` is the only writer. Phase 1 reports count cycles with `start_reason in (review, release_qa)` of bugs in Releases (`cycle_metrics`), which is exactly what Phase 1 recorded as regressions, so their numbers are unchanged.
_Avoid_: "regression cycle", `regression_history`, `is_regression`, `regression_count` (all removed); summing reasons into one "regressions" number in new reports (CY-09).

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
### Personal queue (slice 10)

**Personal queue**:
One person's execution order across every project (`queue_entries`, FR-33): all their open assigned items — To do, Rejected, In progress, To review, In review, Blocked; never New/Needs info (triage), Done or Cancelled (BR-38). Two groups, always in this order: **pinned**, then the **rest** in manual order. A newly queued item (assigned, accepted, or back in a board status) enters the rest by the **default rule** — directly above the first item that ranks lower by priority, then due date (none last), then how often it was reported, then age — even when the owner ordered the rest by hand (FR-39). A priority change re-places an unpinned item by the same rule. The owner, a CTO and an Admin can reorder and pin (Policy `view_queue`, `reorder_queue`, `pin`); a drag never crosses the pin boundary (409 `queue_group_boundary`). `QueueService` is the only writer; the ordering rules are the pure `app/queue_order.py`. Shown at `/my-work` (and `/u/:username/work` for CTO/Admin) as a list — In progress, Pinned, Queue — or a Kanban whose columns follow queue order.
_Avoid_: "My Issues" (the page it replaced), "priority" for queue position — priority is the item's, position is the person's.

**Pin**:
Lifts an item into the pinned group, at its end (FR-40). At most 4 per queue (409 `pin_limit_reached`, the message names the limit). A pin set by a CTO or Admin on someone else's queue is a **locked pin** (`pin_locked`): the owner can't remove it (409 `pin_locked`); a CTO or Admin pinning their own queue doesn't lock it. Reassigning, cancelling, or completing an item releases its pin (BR-45, BR-46). Unpinning re-places the item by the default rule.
_Avoid_: "urgent", "star", "favourite".

**Dormant queue entry**:
The entry of an item that reached Done (`queue_entries.left_at` set). It keeps its rest-group position — a pinned one first moves to the top of the rest — so when the item comes back from Done to the same assignee (a Reject from release QA or production) it returns to where it was, never above the pins (FR-64, BR-61). Hidden from every queue read, from pin counts and from positions. A reject from To review / In review changes nothing: the item never left. An item reassigned while Done loses its entry and returns by the default rule.

**Queue history**:
The owner's append-only record of human queue changes — reorder, pin, unpin — with actor, item, and 1-based positions in the full queue before and after (`queue_history`, FR-41, BR-44). Automatic insertions and removals aren't recorded. Kept out of item timelines. When the actor isn't the owner, the owner gets a `queue_changed` notification (BR-43). Readable by the owner, CTOs and Admins.

**Workload**:
The Team page's CTO/Admin view of everyone's queue at once (`GET /team/workload`, Policy `view_team_overview`, FR-43). One row per active assignable person, in name order: their In progress items, the next three queue items that aren't In progress, and counts of open and pinned items — dormant entries never count. Filterable by role and by project ("working in": people with open queued work there). A row opens the person's board at `/u/:username/work`, where reorder and pin live. It describes; it never ranks or scores people (PRD non-goal).
_Avoid_: "team overview" for the view itself (that's the Policy action), "load", "capacity", "utilisation" — nothing here measures people.

## Decisions

Where Phase 2 deliberately departs from the PRD. Each came up while checking the PRD against the code and was decided before building, so the code follows the decision, not the PRD. Moved here from the Phase 2 specs' README after slice 11 so the decisions outlive the specs. Later product overrides (the free workflow, 2026-09-22/23) are noted where they changed a row.

| # | PRD says | Code before Phase 2 | Decision |
|---|---|---|---|
| D1 | "Global Triage Lead role" in v1 | Triage lead is already per project (`projects.triage_lead_id`, nullable) | Keep the column. Make it required on create and update (slice 04). Existing projects without a lead are flagged, and their notifications fall back to admins. |
| D2 | Roles include Project Manager and Support | Roles are `qa`, `developer`, `cto`, `admin` | Add `pm` and `support` (slice 04). |
| D3 | IDs like `BUG-042` | Display is `issue-123`, global sequence | Type-prefixed keys (`BUG-123`, `TASK-124`) over the same global sequence (slice 03). |
| D4 | Severity is required when a bug is accepted | `severity` is non-null with default `minor` | Make it nullable, then rename it to `priority` with the shared scale in 03a. Null for New and Needs info bugs nobody has rated; required when leaving triage (02, enforced in 06). |
| D5 | Severity has four levels | Five levels, including `enhancement` | A data migration maps `enhancement` to `minor` (slice 02). |
| D6 | Needs info is a status | "Needs clarification" sets status `blocked` and reassigns the item to the reporter | Needs info becomes a real status. The migration moves those rows to `needs_info` and restores the previous assignee (slice 02). |
| D7 | Bugs may have no release | `issues.release_id` is `NOT NULL` | Make it nullable (slice 03). **v3:** `release_id` is the item's container — a Stream row or a Release row (`releases.kind`) — and null means backlog (08a). |
| D8 | Invalid transitions are rejected | `PATCH /issues/{id}` accepts any `status` | Every status change goes through Workflow, including PATCH (slice 02). **Override:** Workflow now allows any move for bugs and tasks; only entering Rejected is gated (see Workflow above, 09a). |
| D9 | The Team page is for CTO/Admin | `/team` is a member directory for everyone | Keep the directory. Add a **Workload** view that only CTO and Admin can open (slice 11). |
| D10 | My Work | `/my-issues` page | Replaced by `/my-work`. `/my-issues` redirects (slice 10). |
| D11 | Search & Ranking Engine replaces Phase 1 search | `search_service.py` (hybrid + LLM rerank), `issue_embeddings`, `issues.search_tsv`, `llm` settings; migration `7f60b302c290` altered the vector column and constraints | Removed and replaced by engine tables and the `embeddings` service (slice 12). The migration tolerates whatever state `7f60b302c290` left. |
| D12 | A merge into a Done bug records a regression cycle, possibly without a release (BR-49) | `regression_history.release_id` is `NOT NULL` | Made nullable with `source` in 06. **v3:** `regression_history` is replaced by `issue_cycles` with a `start_reason`, and every cycle has a container (08a Part 2). |
| D13 | One `issues` table with type-specific and derived columns | Bug-only, task-only, lifecycle and duration columns all live on `issues` | Split into `issues` + `issue_bugs` + `issue_tasks` + `issue_timestamps`; `time_to_*_h` are computed by `DurationService` (03a Part 2). The API response shape does not change. |
| D16 | The fix belongs to whoever did the work (v3 BR-63) | `record_regression` credits the actor of the last `fixed` event | Replaced by `delivered_by_id`, a snapshot of the assignee at In review (08a Part 2). |
