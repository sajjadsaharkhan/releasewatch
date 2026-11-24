# 19 — Backend ⇄ frontend contract

Source of truth for the two parallel sessions. Spec: [19-verified-and-production.md](19-verified-and-production.md).
If either side needs to change a line here, stop and tell the coordinator; do not diverge.

## Status value

`"verified"` (label "Verified"). Order: `new, needs_info, todo, rejected, in_progress, to_review, in_review, verified, done, blocked, cancelled`.
Frontend `constants.js`: `STATUS.verified`, `BOARD_STATUSES`, `FIXED_STATUSES`, `OPEN_STATUSES` gain it; add `DELIVERED_STATUSES = ['verified','done']`.
`BACKLOG_STATUSES` does not include it.

## Cycle reason

`release_qa` → label "Caught before production" (added to backend labels and frontend `CYCLE_REASON`).
Timeline `status_changed` event `reason` values added: `ship`, `on_production`.

## Endpoints

### `POST /issues/{id}/transition` (existing)
- Release item, `to: "done"` → `409 {"code":"done_at_ship"}`.
- `allowed_transitions` on `IssueResponse`: for a release item it lists `verified`, never `done`. Stream items list both.
- Moving a `verified`/`done` item to another container or the backlog → `409 {"code":"delivered_item_immobile"}` (replaces `done_item_immobile`; the frontend must handle both codes while migrating).

### `POST /issues/{id}/verify` (existing)
Request body gains optional `on_production: bool` (default false).
`outcome: "pass"` → status `verified`; with `on_production: true` on a Stream item → `done`; on a release item → `409 done_at_ship`.

### `POST /issues/bulk-production` (new)
Request: `{ "issue_ids": ["<uuid>", ...] }` (1–100).
200: `{ "issues": [IssueResponse...], "batch_id": "<uuid>" }`.
409: `{ "code": "not_verified_in_stream", "issue_ids": ["<uuid>", ...] }` (offending ids; nothing changed).
403 for Support. `allowed_actions` gains `mark_production` (tech roles) on `IssueResponse`.
Frontend: `issuesApi.bulkProduction(issueIds) => api.post('/issues/bulk-production', { issue_ids })`.

### `GET /releases/{id}/ship-preview` (existing, shape changes)
```json
{ "to_production": 3,
  "to_backlog": { "todo": 2, "in_review": 1, "rejected": 1 },
  "total_to_backlog": 4,
  "go_nogo": { ...unchanged } }
```
`POST /releases/{id}/ship` response unchanged; the `shipped` release event meta gains `to_production`.

### Release progress
`progress` counts `verified` + `done` over non-cancelled. Release cancel with any Verified/Done item → `409 release_has_done_items` (code unchanged).

### Reject
`allowed_actions` contains `reject` for `verified` items. Reason from Verified = `release_qa` in any container.

## Frontend-only items (no API change)
Board columns, On production selection bar, Verified age marker (client computes from `verified_at`; confirm the field exists on `IssueResponse`, else backend adds `verified_at: datetime|null` — **backend must expose it**), ship dialog, My Work "Delivered" tab, PD-1 report notice, `docs/design.md` §3.

## Ownership
- Backend session: `backend/**`, `CONTEXT.md`, Alembic revision, backend tests.
- Frontend session: `frontend/**`, `e2e/**`, `docs/design.md`.
- Neither touches the other's files.

## Update (backend commit 94b02ca)
A release item's `blocked_transitions` now includes `{"to":"done","code":"done_at_ship","detail":"Done when the release ships."}` for tech roles. The frontend uses it for the disabled Done option and its tooltip instead of deriving the gate client-side. Stream items and Support get no such entry. API on :8080 is restarted.
