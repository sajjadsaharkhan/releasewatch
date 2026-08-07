# Plan: Optional Keycloak (OIDC) + LDAP/AD Authentication

**Status:** Proposed — Phase 1
**Author:** Sajjad Saharkhan
**Date:** 2026-08-05
**Related:** `CONTEXT.md` (Identity & Auth glossary)

---

## 1. Goal

Add **optional, pluggable external authentication** to Releasewatch (RW) so users can sign in via:

- **Keycloak** (OIDC, redirect flow), and
- **direct LDAP / Active Directory** (username + password bind).

Both are **opt-in and additive**. RW must remain **fully usable with local accounts only** when neither provider is configured. Nothing about the existing app — issues, projects, inbox, timeline, telegram, all FKs to `users.id` — changes shape.

## 2. Non-goals (Phase 1)

- Reading provider groups to assign roles (Keycloak group claims / AD `memberOf`). **Deferred to Phase 2.** In Phase 1 every federated user is provisioned as `developer` and an admin adjusts them in-app.
- Deploying/operating Keycloak or AD (already exist in the user's cloud/infra — config-only integration).
- Admin-toggleable enable/disable from the UI (Phase 2 nicety; secrets stay in env regardless).
- SCIM / push provisioning, user deprovisioning sync, MFA policy management (owned by Keycloak/AD).

---

## 3. Locked decisions (with rationale)

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | **Optional, pluggable providers**; local username/password is the always-available built-in. A provider is "enabled" iff its env config is present. | RW must run standalone; providers are additive like GitLab/Grafana. |
| D2 | **Generic `user_identities` table** `(provider, provider_subject) → user_id`. No `keycloak_id` column on `users`. | Keeps `users` vendor-neutral; supports local + keycloak + ldap + future providers with no schema churn. |
| D3 | **RW mints its own JWT; it is the only token the frontend ever sends.** Provider tokens never reach RW API endpoints. `get_current_user` / `require_role` / all routes unchanged. | Consistency across providers; app core stays provider-agnostic and identical to standalone mode. |
| D4 | **Keycloak = backend-centric Authorization Code + PKCE.** Login button → RW redirects to Keycloak → callback to RW → RW validates, provisions, mints RW token, hands to frontend. | Most secure (client secret + code exchange server-side); frontend needs no OIDC SDK and stays identical to local login. |
| D5 | **LDAP = direct AD bind**, shares the username/password form. **LDAP first, then local fallback.** LDAP *bind-reject* → try local; LDAP *server-unavailable* → also try local (never lock out local admins). | Centralize on the directory when up, but keep local recovery path. |
| D6 | **JIT provisioning; Phase-1 role = `developer`** for all federated users; in-app role is always the source of truth and never overwritten by a provider. | Simplest correct behavior; role management stays in RW. |
| D7 | **Silent refresh via RW refresh token, re-checked against Keycloak.** RW stores the Keycloak refresh token server-side (Redis); each RW refresh confirms the Keycloak session is still valid before re-minting. Revoked in Keycloak → RW refresh fails → re-login. | Silent renewal without redirect, while honoring Keycloak revocation/disable. |
| D8 | **Provider config + secrets live in env / `config.py`**, not the DB/frontend. `/auth/providers` exposes only booleans. | Blast radius, bootstrap/lockout safety, secret-at-rest, same tier as `SECRET_KEY`/`S3_*`. |
| D9 | **Frontend shows the "Sign in with Keycloak" button only when `/auth/providers` reports `keycloak: true`.** LDAP is transparent (same form). | Provider availability is deployment-driven; no secrets sent to the client. |

---

## 4. Domain vocabulary

See `CONTEXT.md` → **Identity & Auth**: *Local account, Identity Provider, External Identity, provider_subject, JIT provisioning, Releasewatch token, Role*. This plan uses those terms exactly.

---

## 5. Configuration (env / `config.py`)

All keys optional. **A provider is enabled iff its required keys are set.** Add computed `keycloak_enabled` / `ldap_enabled` properties to `Settings`.

### 5.1 New settings in `backend/app/config.py`

```python
# ── Keycloak (OIDC) — enabled when issuer + client id + client secret set ──
KEYCLOAK_ISSUER: str = Field("", description="Realm base, e.g. https://kc.example.com/realms/rw")
KEYCLOAK_CLIENT_ID: str = Field("", description="Confidential client id")
KEYCLOAK_CLIENT_SECRET: str = Field("", description="Confidential client secret")
KEYCLOAK_REDIRECT_URI: str = Field("", description="RW backend callback, must be whitelisted in KC")
KEYCLOAK_SCOPES: str = Field("openid profile email", description="OIDC scopes")

# ── LDAP / Active Directory — enabled when server URI + bind template set ──
LDAP_SERVER_URI: str = Field("", description="e.g. ldaps://ad.corp.local:636")
LDAP_BIND_DN_TEMPLATE: str = Field("", description="Direct UPN bind, e.g. {username}@corp.local")
LDAP_USER_BASE_DN: str = Field("", description="Search base (only for search-then-bind)")
LDAP_USER_FILTER: str = Field("(userPrincipalName={username})", description="User search filter")
LDAP_SERVICE_BIND_DN: str = Field("", description="Service account DN (only for search-then-bind)")
LDAP_SERVICE_PASSWORD: str = Field("", description="Service account password")
LDAP_USE_TLS: bool = Field(True, description="Require TLS/LDAPS")
LDAP_ATTR_NAME: str = Field("displayName", description="AD attribute for display name")
LDAP_ATTR_EMAIL: str = Field("mail", description="AD attribute for email")

# ── Federation defaults ──
FEDERATED_DEFAULT_ROLE: str = Field("developer", description="Role seeded for JIT-provisioned users")
```

```python
@computed_field
@property
def keycloak_enabled(self) -> bool:
    return bool(self.KEYCLOAK_ISSUER and self.KEYCLOAK_CLIENT_ID and self.KEYCLOAK_CLIENT_SECRET)

@computed_field
@property
def ldap_enabled(self) -> bool:
    return bool(self.LDAP_SERVER_URI and (self.LDAP_BIND_DN_TEMPLATE or self.LDAP_USER_BASE_DN))
```

### 5.2 `.env.example` additions

Document every key above (blank values). Enabling a provider = fill its keys; disabling = leave blank. Real values go in the dev `.env` and the prod secret manager.

**AD note:** prefer **direct UPN bind** (`LDAP_BIND_DN_TEMPLATE={username}@corp.local`) — no service account secret needed, the user's own password is verified live by the bind. Only set `LDAP_SERVICE_*` + `LDAP_USER_BASE_DN` if you must search-then-bind.

### 5.3 New Python dependencies (`backend/pyproject.toml`)

- `authlib` — OIDC discovery, PKCE, token exchange, JWKS ID-token validation.
- `ldap3` — LDAP/AD bind. Sync library → call via `starlette.concurrency.run_in_threadpool` to keep it off the event loop.

---

## 6. Data model

### 6.1 New model — `backend/app/db/models/user_identity.py`

```python
class UserIdentity(Base):
    __tablename__ = "user_identities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)          # 'keycloak' | 'ldap'
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False) # KC sub UUID / AD objectGUID or UPN
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default="now()"
    )
    __table_args__ = (UniqueConstraint("provider", "provider_subject", name="uq_identity_provider_subject"),)
```

### 6.2 Changes to `backend/app/db/models/user.py`

- `hashed_password` → **nullable** (federated-only users may have no local password).
- Add relationship: `identities = relationship("UserIdentity", cascade="all, delete-orphan")`.

### 6.3 Migration

`make migrate-new` → creates `user_identities`, makes `users.hashed_password` nullable. Review the generated file, then `make migrate`.

> **Backward compatible:** existing local users are untouched; no forced migration into Keycloak/AD.

---

## 7. Backend components

### 7.1 Provider abstraction — `backend/app/services/auth_providers/`

```
auth_providers/
├── __init__.py
├── base.py     # ExternalPrincipal dataclass + AuthProvider protocol
├── oidc.py     # KeycloakOIDCProvider
└── ldap.py     # LdapProvider
```

`base.py`:
```python
@dataclass
class ExternalPrincipal:
    provider: str
    subject: str          # stable provider id → provider_subject
    username: str         # used for local-user matching (D2: "same username")
    name: str | None
    email: str | None
    provider_refresh_token: str | None = None   # OIDC only, for D7
```

### 7.2 `oidc.py` — Keycloak

- Lazy Authlib client built from `KEYCLOAK_ISSUER` via OIDC discovery (`/.well-known/openid-configuration`).
- `build_authorize_redirect(request)` → generates PKCE verifier + `state` + `nonce`, stashes them (signed cookie **or** short-TTL Redis key), returns the Keycloak authorize URL.
- `handle_callback(code, state, ...)` → validate `state`, exchange code (+ PKCE verifier) for tokens, validate the **ID token** against JWKS + `nonce`, return `ExternalPrincipal` (subject = `sub`, username = `preferred_username`, plus `provider_refresh_token`).

### 7.3 `ldap.py` — Active Directory

- `authenticate(username, password) -> ExternalPrincipal | None`:
  - Direct bind: `ldap3` bind with `LDAP_BIND_DN_TEMPLATE.format(username=username)` + password over TLS.
  - (Optional) search-then-bind if `LDAP_SERVICE_*` set: service-bind → search `LDAP_USER_FILTER` under `LDAP_USER_BASE_DN` → bind as found DN.
  - Success → read `LDAP_ATTR_NAME` / `LDAP_ATTR_EMAIL`; subject = `objectGUID` (fallback UPN); return principal.
  - **Bind rejected** (bad creds / user not found) → return `None` (caller falls back to local).
  - **Server unavailable / TLS error** → raise `LdapUnavailable`; caller logs and falls back to local (D5). Run under `run_in_threadpool`.

### 7.4 Identity service — `backend/app/services/identity_service.py`

`async def resolve_or_provision(db, principal) -> User`:
1. `SELECT` `user_identities` by `(provider, subject)` → if found, return its `User`.
2. Else `SELECT` `User` by `username == principal.username` → if found, **auto-link** (insert `user_identities` row) and return it. *(Matches D2 "same username everywhere". Caveat: trusts the directory's username as authoritative for that person — acceptable for a single corporate directory.)*
3. Else **JIT-create** `User` (`role=settings.FEDERATED_DEFAULT_ROLE`, `hashed_password=None`, name/email/avatar_color from claims) + `user_identities` row.
4. Return the `User`. Caller mints RW tokens exactly as today (`create_access_token` / `create_refresh_token`).

### 7.5 Redis — Keycloak refresh token store (D7)

- On Keycloak login/callback, store the Keycloak refresh token in Redis keyed by the RW refresh token's `jti` (add a `jti` claim to RW refresh tokens): `rw:kc_refresh:{jti} → <kc_refresh_token>`, TTL = RW refresh lifetime.
- On RW `/auth/refresh`: if a Redis entry exists for this `jti`, call Keycloak's token endpoint with the stored KC refresh token → on success, rotate/store the new KC refresh token under the new RW `jti` and mint new RW tokens; on failure → `401` (session revoked/disabled). Local/LDAP users have no Redis entry → plain existing refresh path.
- On logout: delete the Redis entry (+ optional RP-initiated end-session redirect to Keycloak).

### 7.6 Endpoints — `backend/app/api/v1/auth.py` + `backend/app/schemas/auth.py`

| Method + path | Change | Behavior |
|---|---|---|
| `GET /auth/providers` | **new, public** | `{ "local": true, "keycloak": settings.keycloak_enabled, "ldap": settings.ldap_enabled }`. No secrets. |
| `POST /auth/login` | **modified** | If `ldap_enabled`: try `LdapProvider.authenticate`. Success → `resolve_or_provision` → mint RW tokens. Bind-reject or `LdapUnavailable` → fall through to existing local bcrypt check. |
| `GET /auth/keycloak/login` | **new** | Guard on `keycloak_enabled` (else 404). Redirect to Keycloak authorize URL (PKCE + state + nonce). |
| `GET /auth/keycloak/callback` | **new** | Exchange + validate; `resolve_or_provision`; store KC refresh token in Redis; mint RW tokens; **302** to `FRONTEND_URL#/auth/callback` with tokens in the URL fragment. |
| `POST /auth/refresh` | **modified** | If RW refresh `jti` has a Redis KC entry → re-validate against Keycloak before re-minting (D7). Else existing path. |
| `POST /auth/logout` | **modified** | Existing RW blacklist + delete Redis KC entry (+ optional KC end-session). |
| `get_current_user`, `require_role`, all other routes | **unchanged** | Provider-agnostic (D3). |

> **Token delivery via fragment**: the callback returns tokens in the URL `#fragment` (not query) so they never hit server logs; the SPA reads and immediately strips them. (If you prefer, a short-lived one-time "handoff code" the SPA exchanges for tokens is a hardening option — noted, not Phase 1.)

---

## 8. Frontend

| File | Change |
|---|---|
| `frontend/src/lib/api.js` | Add `authApi.getProviders()` → `GET /auth/providers`. `login()` unchanged (LDAP is transparent). Refresh interceptor unchanged (still uses RW refresh token). |
| `frontend/src/pages/LoginPage.jsx` | On mount, call `getProviders()`. If `keycloak` → render **"Sign in with Keycloak"** button that does a full-page redirect to the backend `GET /auth/keycloak/login`. Local form stays as-is and is always shown. |
| `frontend/src/pages/AuthCallbackPage.jsx` | **New.** Reads `access`/`refresh` from `location.hash` fragment, writes `rw:token` / `rw:refresh_token` to `localStorage`, clears the fragment, redirects to `#/dashboard`. On error/missing tokens → `#/login`. |
| `frontend/src/App.jsx` | Add public route `path="/auth/callback"` → `AuthCallbackPage` (inside `PublicRoute`). |

No other frontend changes — post-login, everything uses the RW token exactly as today.

---

## 9. Security considerations

- **PKCE + `state` + `nonce`** on the OIDC flow (CSRF + code-injection + replay protection).
- **LDAPS/TLS required** for AD binds; never send credentials in cleartext; run binds in a threadpool.
- **Never log** passwords, client secrets, or tokens. Mask on any diagnostics.
- **Tokens in URL fragment**, not query string; SPA strips them immediately (§7.6).
- **Auto-link-by-username caveat** (§7.4): safe for one trusted corporate directory; revisit before federating any untrusted/second source.
- **Local recovery path preserved** (D5): a directory outage or Keycloak downtime never blocks local-admin login.
- **Secrets in env/secret-manager only** (D8), same tier as `SECRET_KEY`.

---

## 10. Testing

- **Unit:** `identity_service.resolve_or_provision` — all three branches (linked / username-match auto-link / JIT create). LDAP bind-reject vs. unavailable. Group→role *not* applied (Phase-1 default role).
- **Config:** `keycloak_enabled` / `ldap_enabled` truth tables; providers endpoint output.
- **Integration:** `POST /auth/login` LDAP-first-then-local ordering + fallback on unavailability; `/auth/refresh` KC re-check success + revoked→401; local user refresh unaffected.
- **OIDC:** mock Keycloak discovery/JWKS; callback happy path + bad `state`/`nonce` rejection.
- **Standalone regression:** with no provider env set, all auth behaves exactly as before.

---

## 11. Rollout checklist

1. Add deps (`authlib`, `ldap3`), config keys, `.env.example` docs.
2. Model + migration (`user_identities`, nullable `hashed_password`).
3. Provider abstraction + OIDC + LDAP providers.
4. Identity service + Redis KC-refresh store (+ `jti` on RW refresh tokens).
5. Endpoints (`/auth/providers`, KC login/callback, modified login/refresh/logout).
6. Frontend (providers fetch, KC button, callback route).
7. Tests + standalone regression.
8. Configure dev `.env` against the cloud Keycloak realm + AD; verify both flows; verify standalone mode with vars blank.

---

## 12. Phase 2 (deferred)

- Read Keycloak group claims / AD `memberOf`; configurable **group → role map**; optional sync-on-login (with in-app override policy).
- Optional admin **enable/disable toggle** in `system_settings` that *gates* env-configured providers (secrets stay in env).
- Optional one-time handoff-code token delivery instead of URL fragment.
- Deprovisioning sync / periodic reconciliation.

---

## 13. File-change summary

**Backend**
- `app/config.py` — provider settings + `*_enabled` props *(edit)*
- `app/db/models/user_identity.py` — new model *(new)*
- `app/db/models/user.py` — nullable password + relationship *(edit)*
- `alembic/versions/xxxx_*.py` — migration *(generated)*
- `app/services/auth_providers/{base,oidc,ldap}.py` — providers *(new)*
- `app/services/identity_service.py` — resolve/provision *(new)*
- `app/core/auth.py` — add `jti` to refresh tokens; Redis KC-refresh helpers *(edit)*
- `app/api/v1/auth.py` — providers/KC login/callback + modified login/refresh/logout *(edit)*
- `app/schemas/auth.py` — providers response + KC schemas *(edit)*
- `pyproject.toml` — `authlib`, `ldap3` *(edit)*
- `.env.example` — documented keys *(edit)*

**Frontend**
- `src/lib/api.js` — `getProviders()` *(edit)*
- `src/pages/LoginPage.jsx` — Keycloak button *(edit)*
- `src/pages/AuthCallbackPage.jsx` — token handoff *(new)*
- `src/App.jsx` — `/auth/callback` route *(edit)*
