# 15 — MCP Connection and Tokens

> **Depends on:** 14 · **PRD:** [prd-mcp.md](prd-mcp.md) M2, FR-M01, FR-M38–FR-M45, BR-M02–M04, BR-M20–M24, AC-M02, AC-M04, AC-M36–M40, §8; Appendix A.1, A.2 · **Parent PRD:** [v3](prd-v2.md) §7.3, §13

## Problem Statement

Developers work with AI coding agents (Claude Code, Codex, ZCode), and those agents cannot reach Releasewatch. There is no credential an agent can hold: the only token Releasewatch trusts is the short-lived session JWT of the web app, and giving that to an agent would hand it every permission of the UI, including every status change. There is also no place where a developer can connect an agent, and no way for an administrator to see or stop agent access.

## Solution

Releasewatch gets an MCP server and the credentials to reach it, with one tool to prove the connection works:
- A tech user opens the **MCP** section of their own profile, creates a named **MCP token** with a lifetime of 30 days, 90 days (default), or 1 year, and sees its value **once**, together with a ready-to-copy configuration for Claude Code, Codex, and ZCode that already contains the base URL and the token.
- The agent connects to `/mcp` with that token. The first tool, `rw_context`, returns who the user is, the projects they can see, and whether Jev is enabled.
- The user sees their tokens (name, created, expires, last used, status) and can revoke any of them. Expired tokens cannot be renewed.
- The user gets a Telegram notice when a token is created and seven days before it expires.
- An Admin can switch MCP off for the whole installation, and can see and revoke every user's tokens.
- MCP tokens work only on `/mcp`; the web session JWT never works there.

## User Stories

1. As a developer, I want an MCP section on my own profile, so that I can connect my coding agent to Releasewatch without asking anyone. (FR-M38)
2. As a QA engineer, PM, CTO, or Admin, I want the same section, because MCP is for the whole tech team. (BR-M04)
3. As a Support user, I want no MCP section at all, because MCP is not for Support. (FR-M38, AC-M04)
4. As a developer, I want to name each token ("Claude Code — laptop"), so that I can tell my tokens apart. (FR-M40)
5. As a developer, I want to choose a lifetime of 30 days, 90 days, or 1 year, with 90 days preselected, so that every token expires. (FR-M40, BR-M20, AC-M37)
6. As a developer, I want no "never expires" option, so that leaked tokens die on their own. (BR-M20)
7. As a developer, I want to see the token value exactly once, right after I create it, so that it is never shown again to anyone. (FR-M41, BR-M21)
8. As a developer, I want a ready configuration for Claude Code, Codex, and ZCode with the base URL and my token already in it, with a copy button for each, so that connecting is one copy. (FR-M41)
9. As a developer, I want the guide to say when a client does not support MCP prompts or resources, so that I know what I will get. (FR-M41)
10. As a developer, I want to see the MCP base URL on the page, so that I can configure a client that is not listed.
11. As a developer, I want my tokens listed with name, created, expires, last used, and status (active, expired, revoked), so that I can see which ones are in use. (FR-M39)
12. As a developer, I want to revoke a token, so that a lost laptop cannot reach my work. (BR-M23)
13. As a developer, I want a revoked token rejected on its next request. (BR-M23, AC-M39)
14. As a developer, I want an expired token rejected and not renewable, so that values rotate; I create a new one instead. (FR-M42, AC-M39)
15. As a developer, I want a Telegram message when a token is created on my account, so that I notice a token I did not create. (§8, AC-M36)
16. As a developer, I want one Telegram message seven days before a token expires, so that my agent does not stop working by surprise. (§8, AC-M38)
17. As a developer, I want my agent's first call to tell it who I am, which projects I can see, and whether Jev is enabled, so that it can work without guessing. (FR-M01)
18. As a developer, I want my agent to see only what I can see, so that MCP never widens my access. (BR-M03)
19. As an Admin, I want an MCP tab in Settings with an Enabled switch, so that I can stop all agent access at once. (FR-M44)
20. As an Admin, I want every request refused with "MCP is disabled by the administrator" while MCP is off, so that agents report it clearly. (FR-M45, AC-M40)
21. As an Admin, I want tokens unchanged while MCP is off, so that switching it on again does not force everyone to reconnect. (FR-M45, AC-M40)
22. As an Admin, I want a list of every user's tokens (user, name, created, expires, last used, status), so that I can see who connected agents. (FR-M44)
23. As an Admin, I want to revoke any user's token. (FR-M44, BR-M23)
24. As an Admin, I want a deactivated user's tokens rejected without revoking them one by one. (BR-M22, AC-M39)
25. As a developer, I want the profile page to say MCP is disabled, with token creation unavailable, while it is off; my tokens stay listed and revocable. (FR-M43)
26. As any user, I want an MCP token refused by the web API, and my web session refused by the MCP server, so that an agent token can never reach the UI's status operations. (BR-M02, AC-M02)
27. As an Admin, I want tokens never deleted, so that agent content can always be traced to the token that created it. (BR-M24)

## Implementation Decisions

### Schema

One new table, `mcp_tokens`, in one Alembic revision with a working downgrade (PRD Appendix A.2):

```
mcp_tokens
  id                  serial PK
  user_id             FK users, NOT NULL, indexed
  name                varchar(64), NOT NULL
  token_hash          char(64), NOT NULL, UNIQUE      -- sha256 of the value
  token_prefix        varchar(12), NOT NULL           -- first characters, for the list
  created_at          timestamptz, NOT NULL
  expires_at          timestamptz, NOT NULL
  last_used_at        timestamptz
  revoked_at          timestamptz
  revoked_by_id       FK users
  expiry_notified_at  timestamptz
```

- The value is `rwm_` followed by 32 random bytes in base62. Only its sha256 is stored. bcrypt is not used: the value is random and high-entropy, and bcrypt would cost on every tool call.
- Status (active, expired, revoked) is derived from `revoked_at` and `expires_at`, never stored. Declare the status values and the lifetime choices once, in the backend and frontend enum modules, per the shared enum rule.
- Rows are never deleted. There is no delete endpoint.
- The kill switch is a `system_settings` row, category `mcp`, value `{enabled}`. Default: disabled on a new installation, so that an Admin turns it on deliberately. Read through a Redis cache with a 30-second TTL; writing the setting clears the cache.

### Token service

A `McpTokenService` owns every write to `mcp_tokens`: create (returns the plain value once), revoke (sets `revoked_at` and `revoked_by_id`), resolve (hash lookup, then the checks below), and touch (`last_used_at`, at most once a minute per token, using a Redis key with a 60-second TTL).

Resolve refuses, in this order, with these codes: MCP disabled (`mcp_disabled`), unknown hash (`token_invalid`), revoked (`token_invalid`), expired (`token_invalid`), owner inactive (`token_invalid`), owner not a tech role (`not_tech`). The message for `mcp_disabled` is exactly "MCP is disabled by the administrator".

Policy gains two actions: `use_mcp` (every tech role) and `manage_mcp_tokens` (Admin, for other users' tokens).

### REST API (for the UI)

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/me/mcp` | tech users | `{enabled, base_url, clients: [...], tokens: [...]}`; tokens never include the value or the hash |
| POST | `/me/mcp/tokens` | tech users | `{name, lifetime_days ∈ {30, 90, 365}}` → `{token: {...}, value, configs: {claude_code, codex, zcode}}`; 409 `mcp_disabled` while off |
| POST | `/me/mcp/tokens/{id}/revoke` | owner | 404 for another user's token |
| GET | `/settings/mcp` | Admin | `{enabled, tokens: [...with user]}` |
| PUT | `/settings/mcp` | Admin | `{enabled}` |
| POST | `/settings/mcp/tokens/{id}/revoke` | Admin | |

`base_url` is the public app URL plus `/mcp`, from configuration. The client configurations are rendered on the server from one template per client, so the UI never assembles them. The list of clients (Claude Code, Codex, ZCode) and whether each supports prompts and resources is product content, declared once in the backend.

### MCP endpoint

- The MCP Python SDK serves the endpoint over **streamable HTTP**, stateless, mounted at `/mcp` in the same FastAPI app. Add the SDK as a backend dependency.
- An MCP auth dependency reads `Authorization: Bearer rwm_…` and resolves it through `McpTokenService`. On success it yields the owner `User` and the token id for the rest of the request.
- The existing `get_current_user` must refuse any bearer value that starts with `rwm_` before trying to decode it as a JWT, with 401. The MCP auth dependency must refuse any value that does not start with `rwm_`. This makes BR-M02 a property of the two dependencies, not of which tools exist.
- MCP tools are thin adapters: validate input, call a service, map domain errors to tool errors with the stable codes of PRD Appendix A.8. Tool errors are returned as MCP tool errors with `{code, message}`, never as HTTP errors once the session is authenticated.
- This slice registers one tool, **`rw_context`**: `{user: {name, username, role}, projects: [{key, name}], jev_enabled}`. Projects are those the user can see, from the same visibility rule the web app uses.

### Notifications

- Two new `InboxEventType` values: `mcp_token_created` and `mcp_token_expiring`, each with a row in `DEFAULT_NOTIFICATION_MATRIX` (Telegram on for the owner).
- They are about a user, not an item or a release. Add a user-scoped fan-out next to `fan_out_release` (same pattern: `issue_id` and `release_id` null, one recipient), so that everything still goes through `InboxFanOutService`.
- A new daily beat task finds tokens that are active, expire within 7 days, and have `expiry_notified_at` null; it fans out `mcp_token_expiring` and sets `expiry_notified_at`. Its body takes `now` as a parameter (the scheduled-jobs seam).
- Message text: "MCP token "<name>" was created on your account. It expires on <date>. If this wasn't you, revoke it in your profile." and "MCP token "<name>" expires on <date>."

### Frontend

- Profile page (own profile only, tech roles only): an **MCP** section with the status line, base URL, token list, Create token dialog, and Revoke confirmation.
- After creation, a one-time panel shows the value and a tab per client with its configuration and a copy button. Closing the panel discards the value from memory. The panel says the value will not be shown again.
- Settings: an **MCP** tab (Admin) with the Enabled switch and the all-tokens table with Revoke.
- Follow `docs/design.md`; loading, empty, and error states for both screens.

## Testing Decisions

- Test external behavior at the highest seam: the `/api/v1` HTTP seam for token management, and `/mcp` driven by an in-process MCP client (streamable HTTP over the app's ASGI transport) for the endpoint. Add an `mcp_client_for(user, token)` fixture next to `client_for`, and an `mcp_token` factory.
- Prior art: `client_for` and the role tests of 04 (visibility), the Telegram outbox fixture (`telegram.sent_to(user)`) for notices, and the scheduled-job tests of 09/10 (`notify_overdue`, `notify_due_items` called with `now`).
- Tests named after the PRD criteria: `test_ac_m02_*` (both directions of BR-M02), `test_ac_m04_*`, `test_ac_m36_*`, `test_ac_m37_*`, `test_ac_m38_*`, `test_ac_m39_*` (expired, revoked, deactivated owner each), `test_ac_m40_*`.
- Also: the value is returned only by create; no list response contains `value` or `token_hash`; another user's token returns 404 on revoke; `last_used_at` changes at most once a minute; `rw_context` lists only visible projects for a Developer and every project for an Admin.
- No E2E scenario is required. Check the profile section and the Settings tab in both themes with Playwright MCP.

## Out of Scope

- Every other tool, prompt, and resource (slices 16–18).
- Agent content marks (`via_mcp_token_id` columns, slice 17).
- OAuth or any connection flow other than personal tokens.
- Token renewal, tokens without expiry, and token deletion.
- Rate limiting of MCP requests.
- Showing the token name or client anywhere outside the profile and the Admin list.

## Further Notes

- Add to `CONTEXT.md`: **MCP token**, **MCP server**, **kill switch** (with _Avoid_: API key, PAT, personal access token).
- The token prefix `rwm_` also lets secret scanners recognize leaked values; consider registering the pattern later.
