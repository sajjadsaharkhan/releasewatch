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
The dedicated endpoint (`POST /issues/{id}/regression`, `IssueService.regress`) that sends a bug back to `in_progress`, incrementing `regression_count` and recording a `RegressionHistory` row when the bug has a release (silently skipped otherwise, since `regression_history.release_id` is NOT NULL until slice 06). Callable from any status.
_Avoid_: treating "regression" as a status a bug sits in, or "regression status" — Phase 1's `regression` status was removed; a regressed bug's status is `in_progress`, distinguished by the `is_regression` flag plus this action.

**Cancel reason**:
An optional reason (`user_error, expected_behavior, cannot_reproduce, duplicate, wont_fix, no_longer_needed`) recordable when an item is cancelled without being finished (`no_longer_needed` is task-only; the rest are bug-only). Not required — cancelling with no reason is allowed.
_Avoid_: "closed"/"closing" — Phase 1's `closed` status is gone. A finished bug is Done; an abandoned one is Cancelled, optionally with a reason.
