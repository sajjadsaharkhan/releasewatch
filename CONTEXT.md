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
A team member's global capability level: `support`, `qa`, `developer`, `product_manager`, `cto`, or `admin`. Everyone but `support` is a **tech role**. Only tech roles can be assigned work. What each role may do is PRD §7.3, enforced by `backend/app/policy.py`. Support sees only support-sourced items and never internal notes. Support's only status moves are **Support verification** (BR-71) — Reject from To review / In review, and Verified (or Done in the Stream) — and **Problem is back** on a Done item. Stored on the local user and is always the source of truth. In Phase 1, any user provisioned via a provider is seeded as `developer` and an admin adjusts them in-app; reading provider groups to seed the role is deferred to a later phase. In-app role management always wins and is never overwritten by a provider.
_Avoid_: permission, group (a group is the provider-side concept, deferred past Phase 1)

### Issue lifecycle

**Work item**:
The product term for a single trackable unit of work. Implemented as the existing `Issue` model and `issues` table — kept as-is rather than renamed, since renaming would churn every file without changing behavior. Every work item is currently a bug; tasks arrive in Phase 2 slice 03 on the same table via a `type` column.
_Avoid_: "issue" as the product-facing word (say "bug" or "work item"); "issue" stays correct as the implementation name in code, routes, and table names.

**Flow status**:
The unified status a work item carries through its lifecycle, in this order: `new, needs_info, todo, rejected, in_progress, to_review, in_review, verified, done, blocked, cancelled`. Replaces Phase 1's status set (`new, triaged, in_progress, fixed, verified, closed, regression, blocked`). `is_release_blocker` is a flag on the work item, not a status; work that came back is a new **cycle**, not a status either. **Done means on production** (v3.1, BR-67); QA's approval is **Verified**.
_Avoid_: `triaged`, `fixed`, `closed`, `regression` as statuses — none of those exist anymore. Phase 1's `verified` was a timestamp-flavoured status that v3 dropped; v3.1 brings the name back with a new meaning (see **Verified**). "Fixed" (Phase 1 reports) now means `to_review`, `in_review`, `verified` or `done` (`FIXED_STATUSES`).

**Verified** (v3.1, slice 19):
QA approved the work; it is **not on production yet** (BR-67). A status for bugs and tasks, between In review and Done (`IssueStatus.verified`, label "Verified", emerald a step lighter than Done, icon `badge-check`). `POST /issues/{id}/verify` with `outcome: pass` moves an In review item here; `verified_at` (item and cycle) is written on the first move into it and never overwritten. Verified is **open** (a recurrence is allowed, a merge only counts), leaves the personal queue like Done (dormant entry), blocks a release cancel, never changes container (`delivered_item_immobile`), and can be **Rejected** with reason `release_qa` ("Caught before production") in any container. In a Release, every Verified item becomes Done at **ship**; in the Stream, the person who deploys moves it to Done (**On production**). Support's "fixed" notice (`support_done`) is sent at Done, never at Verified (BR-76); Support still hears the ordinary status change.
_Avoid_: "approved" or "released" as the status name; treating it as Done in any report or filter.

**On production** (v3.1, FR-67):
Verified → Done for Stream items, by the person who deploys: one item by a status move, or several at once with `POST /issues/bulk-production {issue_ids}` (1–100, Policy action `mark_production`, tech roles only), the only multi-item status change (BR-60, BR-68). All or nothing: every id must be a Verified item of a Stream the caller can see, else 409 `not_verified_in_stream` with the offending `issue_ids`. Each item goes through `IssueService.transition` with reason `on_production`, so every per-item effect is the ordinary one; one request writes one `batch_id` into each `status_changed` meta (the Support channel groups by it, slice 21). `/verify` with `on_production: true` on a Stream item goes straight to Done.
_Avoid_: "deploy" as the action's name, "bulk status change".

**Done gate** (`done_at_ship`, v3.1):
The one workflow rule beside `use_reject`: an item whose container is a Release never moves to Done by a status move — 409 `done_at_ship` — and `allowed_transitions` lists `verified` instead. Only **ship** writes Done there (`via_ship` in the transition context, the one bypass). The Stream and the backlog are unaffected. The container kind reaches the pure module as `container_kind` in its context.

**Delivered statuses**:
`DELIVERED_STATUSES = (verified, done)` — work that is finished from the team's side. Drives the container lock, the release-cancel refusal and the queue's dormant entries. Not the same as `FIXED_STATUSES` (which includes To review and In review) or `OPEN_STATUSES` (which includes Verified).

**Priority**:
The one importance scale shared by bugs and tasks: `critical, high, medium, low` (`issues.priority`, the `Priority` enum). A New or Needs info bug may have none (shown as "Unrated"); accepting a bug requires one; a task is created at `medium`. Phase 1's `severity` was migrated into it: blocker → critical plus the release-blocker flag, critical → critical, major → high, minor → medium, enhancement → low.
_Avoid_: "severity" (the Phase 1 bug-only scale, gone), P1–P4 (the slice-03 task scale, gone), "urgent" (the Urgent flag was removed; "do this first" is a pin in the personal queue).

**Workflow**:
The pure module (`app/workflow.py`) that is the single place status-transition legality is decided. Takes plain values in (item type, current status, target status, a context dict) and returns plain values out — no database or HTTP access. `IssueService.transition()` is the only code that asks it and writes `issue.status`. As of 2026-09-22 for bugs and 2026-09-23 for tasks, by product decision, it allows every status to move to every other status (tasks are never offered the bug-only `new`/`needs_info`) — no reason required, no self-verification block — so it almost always says yes; the two exceptions are gates that keep statuses truthful: nothing enters Rejected but Reject, and nothing in a Release becomes Done but ship (**Done gate**). The module exists so that if a rule is reintroduced later, it's written once here rather than scattered across callers. The API still exposes its verdict per item as `allowed_transitions` / `blocked_transitions` (currently: every other status, nothing blocked) so the frontend never hardcodes the status list.
_Avoid_: writing transition logic in a route or another service — even permissive, Workflow is the one place that decision lives. Not to be confused with Policy (slice 04), which will own *who* may act, not *what* moves are legal.

**Reject**:
The one way to send work back so it starts its next **cycle** (09a, ADR 0004; replaced 08a's Reject / Return from release QA / Problem on production). `POST /issues/{id}/reject {comment}` from **To review**, **In review**, **Verified** or **Done** (409 `not_rejectable` elsewhere); the comment is required (422 `reason_required`) and is written as an ordinary public comment. The item lands in **Rejected** and its assignee gets `item_returned` (never Support). The server records where the problem was caught as the new cycle's `start_reason`: `review` from To review / In review; `release_qa` ("Caught before production") from Verified, in any container, which the item keeps; `production` from Done (a Released release's item moves to the Stream). A merge into a Done item is the same Reject (`MergeService`). Policy action `reject` (every tech role). `/returns` and `/reopen` are aliases for Done items only (409 `not_done`). `/transition` never enters Rejected (409 `use_reject`), and `/verify` with `outcome: fail` is refused the same way.
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
Where a work item is placed: its project's **Stream**, one of its **Releases**, or none — the **backlog**. Stored as one column, `issues.release_id` (a row of `releases`; null is the backlog). Every placement path — create, triage Accept, PATCH, bulk move — goes through `container_service.resolve`: the container must be the item's project's (`release_project_mismatch`) and, if a Release, not Released or Cancelled (`release_closed`). A Verified or Done item never changes container (`delivered_item_immobile`, BR-54; it replaced `done_item_immobile`). The UI has one picker for it, `ContainerPicker` (Backlog / Stream / open releases).
_Avoid_: "hotfix" (not a concept in v3 — urgent work is an item in the Stream), "milestone" and "project kind" (both removed).

**Stream**:
The one always-open container every project has (`releases.kind = stream`, BR-51), created with the project by an ORM hook, with no lifecycle status. Each item in it ships on its own when Done. It can't be renamed, cancelled, archived, go/no-go'd or deleted (409 `stream_immutable`, FR-46). Release lists, dashboard and reports never show it (`kind = release` only); it has its own page, `/projects/:slug/stream` (slice 09) — a board whose Done column shows the last 7 days by default — and the release switcher lists it first as a link to that page. `ProjectResponse.stream_id` and `IssueResponse.container_kind` expose it.

**Release** (container):
A container whose items ship together (`releases.kind = release`). Lifecycle `planning → development → qa → released`, or `cancelled` (PRD v3 §8.7); `code_freeze_date`, `target_date` (target ship date) and `released_at`. "Blocked" is not a status — a blocked release is one in QA with a no-go decision. The release-blocker flag exists only on a bug in a Release (`release_blocker_release_only`, BR-58); moving the bug out clears it with a `blocker_cleared` event.
_Avoid_: `active`, `blocked`, `archived` as release statuses (Phase 1 values, gone).

**Release lifecycle** (slice 09):
The allowed release status changes, owned by the pure module `app/release_lifecycle.py` (FR-50): Planning → Development → QA, QA → Development, Planning/Development/QA → Cancelled only while no item is Verified or Done (`release_has_done_items`, BR-55), and QA → Released only through **ship** (`use_ship`, `ship_only_from_qa`). Released and Cancelled are final (`release_final`) and read-only. `ReleaseResponse.allowed_transitions` / `allowed_actions` carry what the caller may do; the UI renders them. **Progress** is (Verified + Done) ÷ non-cancelled items (BR-47) and **Overdue** is a passed target ship date on a release that isn't Released or Cancelled (BR-48) — both computed on read, never stored. Changes to a release are recorded as **release events** (`release_events`, the Activity tab), separate from item timelines.
_Avoid_: "blocked release" as a status; "overdue" as a status (it's a marker).

**Ship** (slice 09):
The one action that makes a release Released (`ReleaseService.ship`, FR-53): CTO, Admin, or the project's triage lead (`ship_release`), only from QA. In one transaction it stamps `released_at`, turns every **Verified** item into **Done** (`completed_at` = `released_at`, one `status_changed` event with reason `ship` and one `support_done` each — the only place Done is written in a Release, BR-67), moves every other item that isn't Done or Cancelled to the backlog as To do in category Default — assignee kept, cycles deleted (BR-56, BR-62) — and sends `release_shipped` to the items' assignees and the CTOs. `GET /releases/{id}/ship-preview` returns `to_production`, `to_backlog` (by status, only statuses with an item), `total_to_backlog` and the go/no-go; the `shipped` release event records `to_production`. Go/no-go is shown in the ship notice but isn't required. **Cancel** moves open items the same way. A release that passes its target ship date sends `release_overdue` to active CTOs once per date (a daily Celery beat job); these two are release-only notifications (`inbox_items.issue_id` null, `release_id` set).
_Avoid_: "release" as a verb for this action; "deploy".

### Triage (slice 06)

**Triage queue**:
A project's New and Needs info bugs, oldest first, with source, reporter, recurrence count, and age (FR-17). The Triage page's New and Needs info tabs. Tasks never enter it. A third tab, **Return requests**, lists the project's Pending **return requests** (they aren't items, so they come from `GET /projects/{id}/return-requests`, or `GET /return-requests` for all projects); its count joins New in the sidebar's triage badge.
_Avoid_: "unassigned issues" — the queue is about the decision, not the assignee.

**Triage outcome**:
The one decision a triager (any tech role) applies to a queued bug through `POST /issues/{id}/triage` (`TriageService`): **Accept** (priority required; assignee, container and backlog category optional — the container is the Stream, an open release, or none, which puts the bug in the backlog, in Default unless another category is picked) → To do; **Needs info** (a public comment saying what's missing) → Needs info; **Duplicate** (a merge) → Cancelled, reason Duplicate; **Reject** (user error, expected behavior, or cannot reproduce) → Cancelled. Each writes one `triaged` timeline event with its inputs. Only New and Needs info bugs can be triaged (`not_in_triage`). A public reply by the reporter or any Support user sends a Needs info bug back to New and tells the triage lead (FR-19).
_Avoid_: "triaged" as a status (gone since slice 02), "needs clarification" (the Phase 1 name).

**Subscriber**:
A user on an item's `issue_subscribers` list — its reporter (on create), reporters of duplicates merged into it, recurrence reporters (reason `recurrence`), and return-request requesters (reason `return_request`). The first reason wins. Support subscribers receive the item's three Support notices — Needs info, Cancelled, Done (`support_needs_info`, `support_cancelled`, `support_done`; a Cancelled that is a merge says "merged into BUG-n") and, as a requester, `support_return_decided`. Besides those, Support is notified only when @mentioned in a public comment on an item they can see (2026-09-24); `fan_out` drops Support from every other event, and internal notes never reach them (BR-31). A Support subscriber may view the item. Support works as a team: every Support user sees every support report, and the Support reports list names the reporter with a "Me" filter.
_Avoid_: "watcher", "follower".

**Merge**:
Folding one report into an original (BR-50), owned by `MergeService.merge_into`: the original's `recurrence_count` +1 (atomic UPDATE — except into a Done original, where the merge is a Reject and the count does not change, v3.1), the merged content added as a public comment ("Merged from BUG-n … Reported by @reporter" — a tech reporter gets the mention notice, a Support reporter only their Support notice), and the merged report's reporter subscribed. The Duplicate outcome merges and cancels the duplicate; recurrence (07) merges without a second item. The original must be a bug or a task in the same project that isn't itself a duplicate (`duplicate_of_duplicate` suggests its original).
_Avoid_: "link duplicate" (Phase 1's endpoint, removed).

**Recurrence**:
One more occurrence of an open or Cancelled bug, recorded with `POST /issues/{id}/recurrences` instead of a second report (FR-13, slice 07). Any role, on a bug they can see; a comment (the new customer's details) is required. It goes through `MergeService.merge_into`: `recurrence_count` +1, a public `recurrence` timeline event with the comment as body, the reporter subscribed, and an `issue_recurrences` row (for reports over time — merges aren't recorded there). On a Cancelled bug the triage lead gets `recurrence_on_cancelled` and the bug stays Cancelled; on an open bug the assignee and reporter get the ordinary `comment` notice. A Done bug refuses it (409 `recurrence_on_done`, BR-23): "This item is Done. Use Problem is back to ask for it to come back." — Support raises a **return request** instead; a Verified bug takes it (it isn't on production yet, AC-79): a returning problem on a Done item is a **return request**, or a new report that triage merges into it (a **Merge into Done**). Tasks refuse it (`recurrence_bug_only`). `recurrence_count` starts at 1 — the original report is one occurrence.
_Avoid_: "+1", "bump", "duplicate report".

**Return request** (v3.1, slice 20, §8.10):
Support's request that a **Done** item come back for another fix. Not a work item: no key, no status, no search entry. It hangs off the item (`return_requests`, one row per request; `return_request_entries`, one per press of Problem is back) and is written on the timeline as `return_requested`, `return_request_added`, `return_confirmed`, `return_dismissed`. An item has at most one **Pending** request (BR-69; a partial unique index backs the service's row lock). `ReturnRequestService` is its only writer. Pressing it posts a public comment, subscribes the requester (reason `return_request`) and tells the triage lead once (`return_requested`); the item stays Done and `recurrence_count` is untouched. A tech user who can triage **confirms** it — the ordinary Reject from Done (`IssueService.reject_with`, `production` cycle with the first comment as its reason, a Released release's item moves to the Stream, the assignee gets `item_returned`) — or **dismisses** it with a required public comment (the item stays Done). Both tell the requesters (`support_return_decided`, to the people who pressed it — not every subscriber). A request is closed as Confirmed, without a notice, when its item leaves Done by any other path (a Reject, a merge into it, a cancel); a confirm that finds the item already out of Done closes it with `item_already_returned`.
_Avoid_: "reopen request", "regression report", "recurrence on a Done item".

**Problem is back**:
The Support action that creates or adds to a **return request** (`POST /issues/{id}/return-requests`, policy `request_return`: Support only, on a Done item it can see — a subscribed non-support item included). With a Pending request the button reads **Add to pending request** and the press becomes another entry of the same request.

**Support verification** (v3.1, BR-71):
What Support may do to what it filed: on a **support-sourced** item in To review or In review, move it to Verified (to Done instead when the item is in the Stream — "tested on production"), or Reject it with a comment (reason `review`); nothing else. No Reject from Verified or Done, no On production, no move on a non-support item it only subscribes to. `policy._support_status_move` is the one place the rule is written; it reads the item's container, so routes load the release with the item (`authorize_issue`). Verifying from To review goes through `POST /issues/{id}/transition` (or a status-only `PATCH`), since `/verify` is for In review.

**Merge into Done**:
A merge into a Done original (BR-49) is a **Reject**: the original goes to Rejected and its next **cycle** starts (always `production`, moving to the Stream out of a Released release) with the merge comment as its reason and the merged report as `start_merged_issue_id`; its assignee gets `item_returned`. The original may be a bug or a task (BR-20); **`recurrence_count` does not change** (BR-50, v3.1). Support hears nothing until it's Done again. Merges into Cancelled originals leave them Cancelled and notify the triage lead; any other status — **Verified included** — is unchanged: no status change, no cycle, count +1. The duplicate hint's merge effect (`merge_effect`) is `returns_production` for Done, `stays_cancelled`, else `unchanged`; `returns_release_qa` is no longer produced.

**Cycle**:
One pass of work on an item until it is delivered — picked up, worked, sent to To review or In review, verified (`issue_cycles`, docs/phase-2/cycle-model.md). A cycle belongs to one item and one container and exists only while the item has a container: cycle 1 starts when the item is placed (created in one, accepted into one, moved in from the backlog) with `start_reason = planned` — a bug filed straight into a release has it while still in triage. Every later cycle starts because the work came back: `review` (rejected in review), `release_qa` (a Reject from Verified, in a Release or the Stream — "Caught before production"), `production` (a Reject from Done, a confirmed return request, or a merge into a Done item — an escape). Moving an item to the backlog deletes its cycles. `issues.current_cycle_id` points at the current one (null exactly when the item has no container). `delivered_by_id` is the assignee when the work first went to To review or In review — never the actor. `CycleService` is the only writer. Phase 1 reports count cycles with `start_reason in (review, release_qa)` of bugs in Releases (`cycle_metrics`), which is exactly what Phase 1 recorded as regressions, so their numbers are unchanged.
_Avoid_: "regression cycle", `regression_history`, `is_regression`, `regression_count` (all removed); summing reasons into one "regressions" number in new reports (CY-09).

### Backlog (slice 08)

**Backlog**:
A project's open work that isn't placed yet: items with no **container** whose status is a board status other than Verified or Done (To do, In progress, In review, Blocked) — never New/Needs info (triage) or Verified/Done/Cancelled (BR-04). Membership is derived by `backlog_clause` / `backlog_items()` in `BacklogService`, never stored. Shown as a ranked list, not a board: grouped by the project's backlog categories in their order (collapsible, with counts; every technical-debt task groups under Technical debt, last, whatever its category) or flat in rank order, drag to rank, multi-select and bulk move to the Stream or an open release (`POST /issues/bulk-move`, all or nothing; a Verified or Done item fails it with `delivered_item_immobile`). Ranking and bulk move need `manage_backlog` (PM, CTO, Admin, and a developer who is the project's triage lead). The header's "untouched for over 6 months" count is display only (`updated_at`; re-ranking doesn't count as touching).
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
One person's execution order across every project (`queue_entries`, FR-33): all their open assigned items — To do, Rejected, In progress, To review, In review, Blocked; never New/Needs info (triage), Verified, Done or Cancelled (BR-38). The Kanban's Verified column lists their Verified items, unbounded; its Done column the last range. Two groups, always in this order: **pinned**, then the **rest** in manual order. A newly queued item (assigned, accepted, or back in a board status) enters the rest by the **default rule** — directly above the first item that ranks lower by priority, then due date (none last), then how often it was reported, then age — even when the owner ordered the rest by hand (FR-39). A priority change re-places an unpinned item by the same rule. The owner, a CTO and an Admin can reorder and pin (Policy `view_queue`, `reorder_queue`, `pin`); a drag never crosses the pin boundary (409 `queue_group_boundary`). `QueueService` is the only writer; the ordering rules are the pure `app/queue_order.py`. Shown at `/my-work` (and `/u/:username/work` for CTO/Admin) as a list — In progress, Pinned, Queue — or a Kanban whose columns follow queue order.
_Avoid_: "My Issues" (the page it replaced), "priority" for queue position — priority is the item's, position is the person's.

**To review tab** (slice 22, FR-72/73):
My Work has two modes: **My queue** (the personal queue above) and **To review**. QA opens on To review, every other tech role on My queue; `?mode=review|queue` picks one for that visit and is never stored. To review is not per person, so `/u/:username/work` shows My queue only. Support never sees it.
_Avoid_: "review inbox", "reviewer assignment" — nobody is assigned; the move to In review is the claim (BR-73).

**Review queue** (slice 22):
`GET /review-queue` (Policy `view_review_queue`, tech roles; Support 403): every visible item in To review or In review, in every non-archived project, whoever it is assigned to. Ordered by project name, then status (To review first), then priority, then longest wait. `waiting_since` is the latest move into the item's current status, read from the timeline and never stored. `counts` follow the project filter only; the list is cut at 500 rows (`truncated`). Read-only: it has no row actions, so there is no bulk path (BR-60). Built by `ReviewQueueService`.

**Pin**:
Lifts an item into the pinned group, at its end (FR-40). At most 4 per queue (409 `pin_limit_reached`, the message names the limit). A pin set by a CTO or Admin on someone else's queue is a **locked pin** (`pin_locked`): the owner can't remove it (409 `pin_locked`); a CTO or Admin pinning their own queue doesn't lock it. Reassigning, cancelling, or completing an item releases its pin (BR-45, BR-46). Unpinning re-places the item by the default rule.
_Avoid_: "urgent", "star", "favourite".

**Dormant queue entry**:
The entry of an item that reached Verified or Done (`queue_entries.left_at` set; `DELIVERED_STATUSES`). It keeps its rest-group position — a pinned one first moves to the top of the rest — so when the item comes back to the same assignee (a Reject from Verified or Done) it returns to where it was, never above the pins (FR-64, BR-61). Verified → Done leaves the dormant entry as it is. Hidden from every queue read, from pin counts and from positions. A reject from To review / In review changes nothing: the item never left. An item reassigned while Done loses its entry and returns by the default rule.

**Queue history**:
The owner's append-only record of human queue changes — reorder, pin, unpin — with actor, item, and 1-based positions in the full queue before and after (`queue_history`, FR-41, BR-44). Automatic insertions and removals aren't recorded. Kept out of item timelines. When the actor isn't the owner, the owner gets a `queue_changed` notification (BR-43). Readable by the owner, CTOs and Admins.

**Workload**:
The Team page's CTO/Admin view of everyone's queue at once (`GET /team/workload`, Policy `view_team_overview`, FR-43). One row per active assignable person, in name order: their In progress items, the next three queue items that aren't In progress, and counts of open and pinned items — dormant entries never count. Filterable by role and by project ("working in": people with open queued work there). A row opens the person's board at `/u/:username/work`, where reorder and pin live. It describes; it never ranks or scores people (PRD non-goal).
_Avoid_: "team overview" for the view itself (that's the Policy action), "load", "capacity", "utilisation" — nothing here measures people.

### Search (slice 12)

**Search engine**:
The one engine behind every "find the items that mean this" question — the search page and command palette now, similar-item suggestions and triage hints from slice 14 (`app/search/`, engine PRD). It reads items and timelines and writes only its own tables (`search_items`, `search_vectors`, `comment_labels`), all derived and rebuilt by **Reindex all** — never item or timeline columns. Results obey item visibility; for Support, only public comments can match or give a snippet (BR-S06).
_Avoid_: "semantic search" for the whole thing (it is dense vectors *and* a keyword channel), "LLM search".

**Stage 1**:
The local, always-on half of the engine: the query is normalized and embedded by the `embeddings` service (TEI + `BAAI/bge-m3`), then four channels — body, title, talk, and a gated trigram keyword channel — are fused by weighted reciprocal rank fusion, and results under a similarity floor are dropped (`app/search/retrieval.py`; constants in `app/search/constants.py`, fixed in code, set by an evaluation run). Vectors of two embedding models are never compared: changing the endpoint or model reindexes everything. **Stage 2** is Jev (slice 13), which may only reorder and cut stage-1 candidates.
_Avoid_: "the reranker" for stage 1 — nothing in stage 1 reranks.

**Jev**:
TypeSafe's external decision model, stage 2 of the search engine (slice 13). One global switch (Admin, Settings → Search → Jev) with an encrypted, write-only API key and a pinned model; it can be switched on only after a passing **Test connection** with the saved key. With Jev on, the search page sends the top 15 stage-1 candidates for a relevance score, orders by it, and moves those under `T_RELEVANT` into a collapsed "Less relevant results" section; new comments are classified by Jev instead of the rule, and switching Jev on reclassifies the rule's comments once. Jev only reorders, cuts or labels — it never adds an item. Off, unreachable, slow or failing all mean the Jev-off behaviour, with no error (`JevClient` returns an outcome, never raises). The command palette never calls Jev. Users never see the name.
_Avoid_: "the AI", "LLM" — Jev returns decisions, never generated text.

**Comment label**:
Whether a comment is used for search, and who decided (`comment_labels.label` + `source`). Without Jev the rule decides (`app/search/comment_rules.py`): `rule_kept`, or `rule_dropped` for short comments and bare agreement or thanks ("موافقم، هر وقت فرصت داشتید انجامش بدید"). Only used comments become **talk** vectors; comments never reach the body text, so they never decide "same problem" (principle S4). Internal notes are labelled and indexed like any comment, with `is_internal`, and filtered at query time.
With Jev on, Jev labels new comments `this_problem` (weight 1), `other_problem` (weight 0.5), `process` or `ack` (not used); a Jev label under 0.6 confidence counts as used. `rule_dropped` comments never reach Jev. A Jev label stays when Jev is switched off (BR-S14).
_Avoid_: "comment classification" for the rule alone.

**Duplicate hint**:
A stored possible duplicate of a New bug (`duplicate_hints`, slice 14): what `compute_duplicate_hints` found — stage-1 body/title candidates of the project, Jev judging each `same`/`related`/`unrelated`, at most three `same` verdicts at `T_SAME`. Tech-only, shown in the triage queue and on the item page while the item is New; each hint says what merging will do, computed with the merge's own reason function so hint and merge never disagree. A **dismissal** ("Not a duplicate", `duplicate_dismissals`) outlives every recomputation. With Jev off, stored hints are hidden, not deleted. The form panels (Support's **Similar reports** with record-recurrence, the create form's **Possibly the same**) are the live, un-stored version of the same judgment.
_Avoid_: "AI-detected duplicate" — stage 1 narrows, Jev decides, a human merges.

### MCP (slice 15)

**MCP server**:
The `/mcp` endpoint coding agents (Claude Code, Codex, ZCode) connect to, in the same FastAPI app (`app/mcp_server/`): the MCP Python SDK over stateless streamable HTTP, a thin adapter that calls services like a route does. Every request acts as the token's owner and sees exactly what that user sees in the UI (BR-M03); it exposes only its own tools, never the REST status operations. Slice 15 added `rw_context`; slice 16 the read tools (`rw_my_queue`, `rw_get_item`, `rw_get_attachment`, `rw_search`, `rw_find_similar`, `rw_triage_queue`, `rw_board`, `rw_tech_debt`) and the resource `rw://item/{key}`; slice 17 the write tools (`rw_upload_prepare`, `rw_file_bug`, `rw_file_tech_debt`, `rw_add_note`, `rw_attach`, `rw_fill_field`, `rw_report_recurrence`); slice 18 `rw_update_own`, `rw_delete_own`, the three MCP prompts and the resource `rw://standards/writing` — none changes status, placement, labels, flags, assignee or priority after filing, or a queue (BR-M01). Tools take display keys (`BUG-42`), project keys and release versions, never ids (except `attachment_id`), and answer with JSON plus a Markdown rendering of it.
_Avoid_: "API", "integration", "bot" — it is a separate entry point with its own credential.

**Significant timeline event**:
What `rw_get_item` shows by default (slice 16): comments and internal notes, plus filed, triaged, status changes (a Reject is one, its comment beside it), recurrences, duplicate links, and the Phase 1 `regression`/`reopened` events. Priority, label, assignment, due-date and field edits appear only with `full_timeline`. Declared once as `SIGNIFICANT_TIMELINE_EVENTS` next to `TimelineEventType`.
_Avoid_: "important events", "the short timeline".

**MCP duplicate candidates**:
What `rw_find_similar` returns for a draft, across every project the user can see, never Cancelled. With Jev on: Jev's `same`/`related` verdicts, as in the tech create form. With Jev off or failing: the stage-1 candidates above `T_FLOOR`, at most five, **with no verdict** — the agent judges them and the developer confirms (BR-M17). This is the one exception to BR-S03, and it is MCP-only (`similar.local_candidates`): the web panels and triage hints stay hidden with Jev off.
_Avoid_: "duplicates" for the Jev-off list — nothing has judged them.

**MCP token**:
The credential an agent holds: `rwm_` + 43 base62 characters, accepted only by the MCP server — `get_current_user` refuses any `rwm_` bearer, and the MCP server refuses anything else (BR-M02). Named by its owner, it lives 30 days, 90 days or 1 year and is never renewed; the value is shown once and stored only as its sha256 (`mcp_tokens`). Its status — active, expired, revoked — is derived, never stored; rows are never deleted, but revoked tokens drop out of both lists (D19). Only tech users hold tokens, and a deactivated owner's tokens stop working without being revoked.
_Avoid_: "API key", "PAT", "personal access token", "secret".

**Agent content**:
An item, timeline entry or attachment created through the MCP server (slice 17). It records the token it came through (`via_mcp_token_id`, set once by the three writers that read the agent context — `TimelineService.create_event`, `IssueService.create`, `AttachmentService.add` — and never changed); responses expose only `via_agent`. Side effects of an agent action (the `subscribed` event on filing, the status move of a recurrence) are agent content too. Independent of `source`: an agent-filed bug is source Internal and agent content.
_Avoid_: "AI label", "bot", "source" (`source` already means internal/support).

**Agent badge**:
The `AgentBadge` pill ("Agent", `square-terminal`) next to the owner's name on agent content: the item page, triage, backlog and Technical debt rows, timeline entries, attachments, and the card's hover details (never the card face). It says nothing else — no client, device, model or token. Not a label: removing labels or editing the item keeps it.
_Avoid_: "AI badge", "bot tag".

**Origin filter**:
All · Agent · People on the triage queue, the backlog and the Technical debt page (`origin=agent|people` on `/issues`, `/projects/{id}/backlog`, `/tech-debt`) — for reviewing or cleaning up what agents filed. There is no limit on how much an agent can file; cleanup relies on this filter.
_Avoid_: "source filter".

**File anyway**:
`file_anyway=true` on `rw_file_bug` / `rw_file_tech_debt`. Every filing runs the duplicate check first; when it finds candidates, nothing is filed and the call fails with `duplicates_found` and the candidates — the agent asks the developer, and passes `file_anyway` only after they decide to file.
_Avoid_: "force", "skip duplicate check" — the check always runs.

**Pending upload**:
A file an agent is uploading: `rw_upload_prepare` presigns S3 (multipart above the large-file threshold) and keeps `{owner, s3_key, name, type, size}` in Redis under an `upload_id` for one hour. A filing or `rw_attach` consumes it — its owner only, once, and only once the file is in S3 (`unknown_upload` otherwise). The API never receives the bytes.
_Avoid_: "draft attachment", "pre-upload" (that's the web form's flow, with no server record).

**Kill switch**:
Settings → MCP → **Enabled** (`system_settings` category `mcp`; off on a new installation). Off, every MCP request is refused with "MCP is disabled by the administrator" and no token can be created; tokens are left untouched and work again when it is switched back on.
_Avoid_: "maintenance mode", "MCP off" as a token state — tokens have no such state.

**Last writer**:
Who changed a piece of content last, read from the record that changed it (prd-mcp.md A.5): the latest `title_changed` / `description_changed` / `steps_changed` / `environment_changed` / `curl_changed` event, else `filed`; for a note, its edit stamp (`meta.edited_by` + `meta.edited_via_mcp_token_id`, written by `TimelineService.edit_comment`) else its author and token; for an attachment, its uploader and token. A UI change makes a person the last writer, with no token. There are no ownership columns.
_Avoid_: "author" or "creator" for this — a person's edit of an agent note changes the last writer, not the author.

**Agent ownership**:
The pure module `app/agent_ownership.py` (slice 18), beside Workflow and Policy, and the only place the last-writer rule is written: an agent may edit or delete a piece only while its last writer is the same user through MCP, with any of their tokens, active or not (BR-M07). Fields also only while the bug is not Done or Cancelled (`item_closed`); title and description also only on an item the agent filed, while the bug is New or the task is in the backlog (`item_triaged`, BR-M14); otherwise `not_owner`. `app/services/agent_ownership_loader.py` gathers the records for one item; `rw_update_own`, `rw_delete_own` and `rw_get_item`'s `you_can_edit` all use it, so the flags and the tools agree. The UI rules do not change: the owner already edits and deletes their own notes and attachments (FR-M28).
_Avoid_: "permission" — Policy decides what a user may do; Agent ownership only what their agent may still undo.

**Agent Writing Standard**:
How an agent writes in Releasewatch: English in ASD-STE100 unless the developer explicitly asks for another language (BR-M18), the templates for bugs, technical debt, notes and recurrences, the evidence table (Source, Locator, Time range), attachment and length rules. Product content, the same for every installation: one file, `backend/app/mcp_server/content/agent-writing-standard.md` (linked from `docs/phase-2/`), served as `rw://standards/writing`, embedded by `rw-work` and `rw-report`, and summarized in every write tool's description. The server enforces only its §9 checks; the rest is guidance.
_Avoid_: "style guide", "template" for the whole standard.

**MCP prompt**:
One of the three working methods the MCP server ships (`app/mcp_server/prompts.py`, text in `content/`): `rw-next` (load the next queue item), `rw-work` with `key` (load one item; PR note), `rw-report` (gather evidence, draft, show, check duplicates, file). Each ends with the same boundaries: never change status or placement; ask before filing, an assignee, a priority, a recurrence, or `file_anyway`.
_Avoid_: "slash command" for the server side — clients may show them as `/rw-next`.

## Decisions

Where Phase 2 deliberately departs from the PRD. Each came up while checking the PRD against the code and was decided before building, so the code follows the decision, not the PRD. Moved here from the Phase 2 specs' README after slice 11 so the decisions outlive the specs. Later product overrides (the free workflow, 2026-09-22/23) are noted where they changed a row.

| # | PRD says | Code before Phase 2 | Decision |
|---|---|---|---|
| D1 | "Global Triage Lead role" in v1 | Triage lead is already per project (`projects.triage_lead_id`, nullable) | Keep the column. Make it required on create and update (slice 04). Existing projects without a lead are flagged, and their notifications fall back to admins. |
| D2 | Roles include Product Manager and Support | Roles are `qa`, `developer`, `cto`, `admin` | Add `product_manager` and `support` (slice 04). |
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
| D17 | Settings → MCP (the switch and every user's tokens) is Admin-only (prd-mcp.md FR-M44) | CTO has everything Admin has in Settings (2026-10-05) | `manage_mcp_tokens` is CTO and Admin, like `manage_search` (slice 15). |
| D18 | `rw_context` lists "the projects the user can see" (FR-M01) | Tech roles see every project; there is no per-project membership | Every non-archived project for every tech user; archived ones are left out because an agent can't work in them (slice 15). |
| D19 | The token lists show every token with its status, revoked included (FR-M39, FR-M44) | — | Revoked tokens are left out of Profile → MCP and Settings → MCP (2026-10-15 product decision); expired ones stay listed. The rows are kept (BR-M24) (slice 15). |
| D20 | A `verified` inbox event is emitted on the move into Verified (spec 19, Notifications) | `InboxEventType.verified` still exists but was retired from the notification matrix (`resolve_matrix` drops it); nothing emits it | Not revived (2026-11-24). The move into Verified is an ordinary `status_changed` to the assignee, the reporter and subscribers; Support gets the same status-change notice, and its "fixed" notice (`support_done`) waits for Done (slice 19). |
| D21 | `ship-preview` is a count of not-Done items | `{not_done, total_not_done, done}` | `{to_production, to_backlog, total_to_backlog, go_nogo}`; `to_backlog` lists only statuses that have an item (slice 19, contract 19-contract.md). |
| D22 | The triage queue lists a project's Pending return requests (FR-69, spec 20) | The Triage page reads items only, and the page also runs across all projects | Added `GET /return-requests?status=pending` (any tech role) beside `GET /projects/{id}/return-requests`, so the all-projects view and the sidebar badge need one call. A Support user's verify / reject goes through the existing `transition` / `reject` routes; `/verify` stays In review only. |
