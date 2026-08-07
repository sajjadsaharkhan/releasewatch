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
A team member's global capability level: `qa`, `developer`, `cto`, or `admin`. Stored on the local user and is always the source of truth. In Phase 1, any user provisioned via a provider is seeded as `developer` and an admin adjusts them in-app; reading provider groups to seed the role is deferred to a later phase. In-app role management always wins and is never overwritten by a provider.
_Avoid_: permission, group (a group is the provider-side concept, deferred past Phase 1)
