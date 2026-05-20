# Releasewatch — Backend Technical Proposal

> **Stack:** FastAPI · PostgreSQL · Redis · S3 · Docker  
> **Version:** 1.0 · Delivery: Claude Code — Dockerized monorepo

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [System Architecture](#2-system-architecture)
3. [Docker & Infrastructure](#3-docker--infrastructure)
4. [Database Schema](#4-database-schema-postgresql)
5. [API Endpoints](#5-api-endpoints--apiv1)
6. [Core Services & Business Logic](#6-core-services--business-logic)
7. [Redis Usage Map](#7-redis-usage-map)
8. [Celery Background Tasks](#8-celery-background-tasks)
9. [Authentication & Security](#9-authentication--security)
10. [Product Feature Checklist](#10-product-feature-checklist)
11. [Build Instructions for Claude Code](#11-build-instructions-for-claude-code)
12. [Technology Decision Summary](#12-technology-decision-summary)

---

## 1. Executive Summary

Releasewatch is a release-scoped QA issue tracking system. This document defines the complete backend architecture, data models, API surface, infrastructure design, and build instructions required to implement it using Claude Code.

The stack is intentionally narrow and operationally simple:

- **FastAPI (Python 3.12)** — async HTTP API, background tasks, WebSocket for real-time events
- **PostgreSQL 16** — primary data store for all relational data (issues, releases, users, timelines)
- **Redis 7** — session caching, rate limiting, real-time event pub/sub, async task queues
- **AWS S3** — file attachments (screenshots, videos, logs, curl exports)
- **Telegram Bot API** — sole notification delivery channel (no email, no SMTP)
- **Docker Compose** — local development and production deployment

> **Architecture principle:** All heavy operations (file uploads, Telegram notifications, regression detection) run as background tasks, never blocking request/response cycles. The API layer is thin and fast; business logic lives in services, not routes.

---

## 2. System Architecture

### 2.1 High-Level Component Diagram

```
┌──────────────────────────────────────────────┐
│            Docker Compose Network            │
│                                              │
│   ┌──────────────┐   ┌──────────────┐       │
│   │  Next.js UI  │──▶│  FastAPI     │       │
│   │  (frontend)  │   │  :8000       │       │
│   └──────────────┘   └──────┬───────┘       │
│                             │               │
│              ┌──────────────┴──────┐        │
│              ▼                     ▼        │
│      ┌──────────────┐    ┌──────────────┐  │
│      │ PostgreSQL   │    │    Redis     │  │
│      │ :5432        │    │    :6379     │  │
│      └──────────────┘    └──────┬───────┘  │
│                                 │          │
│                         ┌───────▼───────┐  │
│                         │ Celery Worker │  │
│                         │ (background)  │  │
│                         └───────┬───────┘  │
└─────────────────────────────────┼──────────┘
                                  │
              ┌───────────────────┼────────────┐
              ▼                   ▼            ▼
       ┌─────────────┐   ┌──────────────┐  Telegram
       │  AWS S3     │   │  Telegram    │  Bot API
       │  (external) │   │  Bot API     │
       └─────────────┘   └──────────────┘
```

### 2.2 Request Flow

| Layer | Technology | Responsibility |
|---|---|---|
| API Gateway | FastAPI + Uvicorn | Route handling, auth middleware, request validation (Pydantic v2) |
| Business Logic | Python services | Issue state machine, regression detection, inbox fan-out |
| Data Layer | SQLAlchemy 2 (async) | ORM, migrations via Alembic, connection pooling via asyncpg |
| Cache / Queue | Redis 7 + Celery | Session cache, rate limit counters, notification task queue |
| File Storage | boto3 + S3 | Presigned URL generation, multipart upload, MIME validation |
| Notifications | python-telegram-bot | Async bot message delivery, user token pairing flow |
| Real-time | WebSocket + Redis pub/sub | Live inbox updates, dashboard event feed |

---

## 3. Docker & Infrastructure

### 3.1 Directory Structure

```
releasewatch/
├── docker-compose.yml          # Full stack orchestration
├── docker-compose.dev.yml      # Dev overrides (hot reload, ports exposed)
├── .env.example                # All config vars documented
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic/                # DB migrations
│   └── app/
│       ├── main.py             # FastAPI app factory
│       ├── config.py           # Settings (pydantic-settings)
│       ├── db/                 # Models, session, base
│       ├── api/                # Route handlers (thin)
│       │   └── v1/             # /api/v1/...
│       ├── services/           # Business logic
│       ├── tasks/              # Celery task definitions
│       ├── schemas/            # Pydantic request/response models
│       └── core/               # Auth, S3, Telegram, Redis clients
└── frontend/                   # Next.js (pre-built via Claude Design)
```

### 3.2 docker-compose.yml

```yaml
version: '3.9'
services:
  api:
    build: ./backend
    ports: ['8000:8000']
    env_file: .env
    depends_on: [postgres, redis]
    volumes: ['./backend:/app']   # remove in prod image

  worker:
    build: ./backend
    command: celery -A app.tasks.celery_app worker --loglevel=info
    env_file: .env
    depends_on: [postgres, redis]

  postgres:
    image: postgres:16-alpine
    volumes: ['postgres_data:/var/lib/postgresql/data']
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes: ['redis_data:/data']

volumes:
  postgres_data:
  redis_data:
```

> S3 is an external cloud service — no container needed. The `api` and `worker` services connect directly to your S3 bucket using the credentials in `.env`.

### 3.3 Environment Configuration (.env.example)

```bash
# ── App ──────────────────────────────────────────
SECRET_KEY=change-this-in-production
ENVIRONMENT=development   # development | production
ALLOWED_ORIGINS=http://localhost:3000

# ── PostgreSQL ────────────────────────────────────
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=releasewatch
POSTGRES_USER=rw_user
POSTGRES_PASSWORD=change-me

# ── Redis ─────────────────────────────────────────
REDIS_URL=redis://redis:6379/0
REDIS_CACHE_TTL=3600

# ── S3 (AWS) ──────────────────────────────────────
# S3_ENDPOINT_URL is intentionally omitted — boto3 defaults to AWS
S3_BUCKET_NAME=your-bucket-name
S3_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE
S3_SECRET_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
S3_REGION=us-east-1                 # match your bucket region
S3_PRESIGN_EXPIRY=3600              # presigned URL lifetime in seconds

# ── Telegram ──────────────────────────────────────
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
TELEGRAM_BOT_USERNAME=ReleasewatchBot

# ── JWT ───────────────────────────────────────────
JWT_ALGORITHM=HS256
JWT_ACCESS_EXPIRE_MINUTES=60
JWT_REFRESH_EXPIRE_DAYS=30
```

---

## 4. Database Schema (PostgreSQL)

All tables use UUID primary keys (`gen_random_uuid()`), `created_at`/`updated_at` timestamps, and soft deletes via `deleted_at`. Migrations managed by Alembic with sequential version IDs.

### users

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | gen_random_uuid() |
| email | VARCHAR(255) UNIQUE NOT NULL | Login identifier |
| name | VARCHAR(255) NOT NULL | Display name |
| role | ENUM('qa','developer','triage_lead','cto','admin') | System role |
| telegram_user_id | BIGINT UNIQUE | Null until user connects bot |
| telegram_handle | VARCHAR(64) | @username |
| telegram_connected_at | TIMESTAMPTZ | When /connect was sent |
| connect_token | VARCHAR(64) UNIQUE | Short-lived pairing token |
| connect_token_expires | TIMESTAMPTZ | Token TTL (15 min) |
| avatar_color | VARCHAR(7) | Hex color for initials avatar |
| is_active | BOOLEAN DEFAULT true | Deactivated users keep history |
| created_at | TIMESTAMPTZ DEFAULT now() | |

### projects

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| name | VARCHAR(255) NOT NULL | |
| slug | VARCHAR(100) UNIQUE NOT NULL | URL-safe identifier |
| description | TEXT | |
| default_labels | TEXT[] | Array of label strings |
| archived_at | TIMESTAMPTZ | Null = active |
| created_by | UUID FK users | |
| created_at | TIMESTAMPTZ | |

### releases

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK projects NOT NULL | |
| version | VARCHAR(50) NOT NULL | e.g. v2.4.1 |
| status | ENUM('draft','active','qa','archived') | |
| staging_url | VARCHAR(500) | |
| go_nogo_status | ENUM('pending','approved','blocked') | CTO gate |
| go_nogo_note | TEXT | Required when blocked |
| go_nogo_by | UUID FK users | |
| go_nogo_at | TIMESTAMPTZ | |
| created_by | UUID FK users | |
| created_at / updated_at | TIMESTAMPTZ | |

### issues

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| issue_number | SERIAL (per project) | BUG-042 display ID |
| project_id | UUID FK projects | |
| release_id | UUID FK releases | |
| title | VARCHAR(500) NOT NULL | |
| description | TEXT | Markdown |
| severity | ENUM('blocker','critical','major','minor','enhancement') | |
| status | ENUM('new','triaged','in_progress','fixed','verified','closed','regression') | |
| reporter_id | UUID FK users NOT NULL | Any role can report |
| assignee_id | UUID FK users | Nullable until triaged |
| labels | TEXT[] | Array of label strings |
| is_release_blocker | BOOLEAN DEFAULT false | Feeds CTO dashboard |
| is_regression | BOOLEAN DEFAULT false | |
| regression_count | SMALLINT DEFAULT 0 | How many times regressed |
| parent_issue_id | UUID FK issues | Duplicate-of link |
| environment_browser | VARCHAR(100) | |
| environment_os | VARCHAR(100) | |
| environment_build_hash | VARCHAR(100) | |
| environment_staging_url | VARCHAR(500) | |
| curl_command | TEXT | Raw cURL for reproduction |
| time_to_triage_h | NUMERIC(8,2) | Calculated on assignment |
| time_to_fix_h | NUMERIC(8,2) | Calculated on Fixed status |
| time_to_verify_h | NUMERIC(8,2) | Calculated on Verified status |
| filed_at | TIMESTAMPTZ NOT NULL DEFAULT now() | |
| triaged_at / fixed_at / verified_at / closed_at | TIMESTAMPTZ | Lifecycle timestamps |
| created_at / updated_at | TIMESTAMPTZ | |

### issue_reproduction_steps

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| issue_id | UUID FK issues NOT NULL | |
| step_order | SMALLINT NOT NULL | 1-based ordering |
| description | TEXT NOT NULL | Step text |
| expected_result | TEXT | |
| actual_result | TEXT | |

### issue_timeline (unified event + comment feed)

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| issue_id | UUID FK issues NOT NULL | |
| actor_id | UUID FK users NOT NULL | Who triggered the event |
| event_type | ENUM (see below) | Type determines rendering |
| body | TEXT | Comment text or system message |
| is_internal | BOOLEAN DEFAULT false | Hidden from QA role |
| meta | JSONB | Event-specific data |
| created_at | TIMESTAMPTZ DEFAULT now() | |

**`event_type` values:**

| Value | meta fields |
|---|---|
| `filed` | — |
| `status_changed` | `{from, to}` |
| `severity_changed` | `{from, to}` |
| `assigned` | `{from_user_id, to_user_id}` |
| `label_added` / `label_removed` | `{label}` |
| `blocker_flagged` / `blocker_cleared` | — |
| `comment` | body contains text; `is_internal` applies |
| `fixed` | `{mr_url, commit_hash, fix_note}` |
| `verified` | `{outcome: pass\|fail\|partial}` |
| `regression` | `{release_version, regression_number}` |
| `duplicate_linked` | `{duplicate_of_issue_id}` |

### issue_attachments

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| issue_id | UUID FK issues NOT NULL | |
| uploaded_by | UUID FK users NOT NULL | |
| file_name | VARCHAR(255) NOT NULL | Original filename |
| s3_key | VARCHAR(1000) NOT NULL | Path in S3 bucket |
| mime_type | VARCHAR(100) NOT NULL | image/png, video/mp4, etc. |
| file_size_bytes | BIGINT | |
| attachment_type | ENUM('screenshot','recording','log','curl_export','other') | |
| created_at | TIMESTAMPTZ | |

### inbox_items

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| user_id | UUID FK users NOT NULL | Recipient |
| issue_id | UUID FK issues NOT NULL | |
| timeline_id | UUID FK issue_timeline | The event that triggered this |
| event_type | ENUM('assigned','fix_ready','comment','mention','regression','blocker_filed') | |
| is_read | BOOLEAN DEFAULT false | |
| read_at | TIMESTAMPTZ | |
| created_at | TIMESTAMPTZ | |

> Index: `(user_id, is_read)` — fast unread count query for sidebar badge.

### regression_history

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| issue_id | UUID FK issues NOT NULL | |
| release_id | UUID FK releases NOT NULL | Which release it regressed in |
| regression_number | SMALLINT NOT NULL | 1st, 2nd, 3rd regression |
| detected_at | TIMESTAMPTZ NOT NULL | |
| detected_by | UUID FK users NOT NULL | Who reopened it |
| previous_fix_by | UUID FK users | Developer of the fix that didn't hold |
| previous_fix_timeline_id | UUID FK issue_timeline | |

---

## 5. API Endpoints `/api/v1`

### 5.1 Authentication

| Method | Path | Description |
|---|---|---|
| POST | `/auth/login` | Email + password → `access_token` + `refresh_token` (JWT) |
| POST | `/auth/refresh` | Rotate refresh token → new `access_token` |
| POST | `/auth/logout` | Revoke refresh token (add to Redis blocklist) |
| GET | `/auth/me` | Current user profile |
| GET | `/auth/telegram/token` | Get personal Telegram connect token (shown in Settings) |

### 5.2 Projects & Releases

| Method | Path | Description |
|---|---|---|
| GET | `/projects` | List all active projects (paginated) |
| POST | `/projects` | Create project (admin) |
| GET | `/projects/{slug}` | Project detail + active release summary |
| PATCH | `/projects/{slug}` | Update name, description, labels |
| DELETE | `/projects/{slug}` | Soft-archive project |
| GET | `/projects/{slug}/releases` | List releases for project |
| POST | `/projects/{slug}/releases` | Create new release |
| GET | `/projects/{slug}/releases/{version}` | Release detail with issue counts |
| PATCH | `/projects/{slug}/releases/{version}` | Update status/staging URL |
| POST | `/projects/{slug}/releases/{version}/go-nogo` | CTO approve/block release |

### 5.3 Issues

| Method | Path | Description |
|---|---|---|
| GET | `/issues` | List issues (filter: project, release, severity, status, assignee, reporter, label, is_blocker, has_regression, sort, page, size) |
| POST | `/issues` | File new issue — any authenticated user |
| GET | `/issues/{id}` | Issue detail (includes timeline, attachments, regression history) |
| PATCH | `/issues/{id}` | Update title, description, severity, status, assignee, labels, blocker flag, linked MR |
| DELETE | `/issues/{id}` | Soft delete (admin/reporter only) |
| POST | `/issues/{id}/triage` | Assign + set severity in one call (triage lead) |
| POST | `/issues/{id}/fix` | Mark as Fixed (assignee only) — triggers Telegram to reporter |
| POST | `/issues/{id}/verify` | Verify fix (pass/fail/partial) — reporter only |
| POST | `/issues/{id}/reopen` | Reopen; if previously verified → creates regression |
| POST | `/issues/{id}/duplicate` | Link as duplicate of another issue |

### 5.4 Timeline & Comments

| Method | Path | Description |
|---|---|---|
| GET | `/issues/{id}/timeline` | Paginated unified timeline (events + comments), oldest first |
| POST | `/issues/{id}/timeline` | Post comment (`body`, `is_internal`, `mention_user_ids[]`) |
| PATCH | `/issues/{id}/timeline/{event_id}` | Edit own comment (within 15-min window) |

### 5.5 Attachments

| Method | Path | Description |
|---|---|---|
| POST | `/issues/{id}/attachments/presign` | Request presigned S3 upload URL — returns `{upload_url, s3_key, attachment_id}` |
| POST | `/issues/{id}/attachments/confirm` | Confirm upload complete — triggers validation job (Celery) |
| GET | `/issues/{id}/attachments` | List attachments with presigned download URLs |
| DELETE | `/issues/{id}/attachments/{attachment_id}` | Remove attachment (reporter/admin) |

> **Presigned upload flow:** Client calls `/presign` → uploads directly to S3 (bypasses API server, no memory pressure) → calls `/confirm` → Celery worker validates MIME type, generates thumbnail for images, records final metadata. API server never touches file bytes.

### 5.6 Inbox

| Method | Path | Description |
|---|---|---|
| GET | `/inbox` | Current user's inbox items (filter: type, is_read, sort; paginated) |
| GET | `/inbox/unread-count` | Fast unread count for sidebar badge (cached in Redis, 30s TTL) |
| POST | `/inbox/read-all` | Mark all inbox items as read |
| POST | `/inbox/{item_id}/read` | Mark single inbox item as read |

### 5.7 Reports & Contributions

| Method | Path | Description |
|---|---|---|
| GET | `/reports/releases/{release_id}` | Full release report: metrics, charts, team breakdown |
| GET | `/reports/contributions` | Member contribution metrics (params: release_id, role, date_from, date_to) |
| GET | `/reports/contributions/time-to-fix` | MTTF by severity with percentiles |
| GET | `/reports/regressions` | Regression analysis: component fragility, recurrence timeline |
| GET | `/reports/dashboard` | CTO dashboard aggregates across all active releases |

### 5.8 Team & Settings

| Method | Path | Description |
|---|---|---|
| GET | `/team` | List all team members with Telegram connection status |
| POST | `/team/invite` | Invite user (name, role) — generates connect token |
| PATCH | `/team/{user_id}/role` | Change user role (admin) |
| PATCH | `/team/{user_id}/deactivate` | Deactivate user |
| GET | `/settings/notifications` | Get notification preference matrix |
| PUT | `/settings/notifications` | Save notification preferences |
| GET | `/settings/integrations/gitlab` | GitLab connection status |
| POST | `/settings/integrations/gitlab` | Save GitLab webhook config |

### 5.9 Telegram Bot Webhook

| Method | Path | Description |
|---|---|---|
| POST | `/telegram/webhook` | Receives Telegram Bot API updates. Handles: `/connect {token}` (pairs user account), `/start` (shows help), `/status {issue_id}` (quick issue lookup) |

### 5.10 WebSocket

| Scheme | Path | Description |
|---|---|---|
| WS | `/ws/dashboard` | Live dashboard events: new issues, status changes, blocker flags (all projects) |
| WS | `/ws/inbox` | Live inbox push: new inbox items for the authenticated user |

> WebSocket auth: pass JWT as query param `?token=...` on connect. Redis pub/sub channels: `rw:dashboard` and `rw:inbox:{user_id}`.

---

## 6. Core Services & Business Logic

### 6.1 IssueService

- **`create_issue()`** — validates release is active, generates `issue_number`, creates `filed` timeline event, publishes to `rw:dashboard`, enqueues Telegram notification to triage leads if severity is blocker/critical
- **`triage_issue()`** — sets assignee + severity atomically, records `assigned`/`severity_changed` timeline events, enqueues assignment notification to assignee
- **`mark_fixed()`** — sets status to `fixed`, calculates `time_to_fix_h`, creates `fixed` timeline event, enqueues "fix ready" Telegram notification to reporter, fans out inbox item to reporter
- **`verify_fix()`** — outcome `pass` → status=`verified` + calculate `time_to_verify_h`; `fail` → status=`regression` + call `RegressionService`; `partial` → status=`in_progress`
- **`reopen_issue()`** — if issue was previously verified, calls `RegressionService.record_regression()`; otherwise simple status revert

### 6.2 RegressionService

- **`record_regression(issue, release, detected_by)`** — increments `issue.regression_count`, sets `is_regression=true`, creates `regression_history` record, appends `regression` timeline event with `meta {release_version, regression_number}`, broadcasts to `rw:dashboard`
- **`get_component_fragility(project_id, n_releases)`** — aggregates `regression_history` by label across last N releases — feeds `/reports/regressions`
- **`get_recurrence_matrix(project_id)`** — builds release × issue grid with Fixed / Regression / Open / Absent states

### 6.3 InboxFanOutService

Called after every significant action. Determines recipients from the notification preferences matrix, creates `inbox_items` records, and pushes to `rw:inbox:{user_id}` Redis channel.

| Trigger | Inbox recipients |
|---|---|
| Issue filed (blocker/critical) | All triage leads + CTO |
| Issue assigned | Assignee only |
| Comment posted | @mentioned users + assignee + reporter |
| Issue fixed | Reporter only |
| Fix verified (pass) | Assignee only |
| Regression detected | Reporter + assignee + all triage leads + CTO |
| Release approved/blocked | All triage leads |

### 6.4 S3Service

- **`generate_presigned_upload(filename, mime_type, max_size_mb)`** — validates allowed MIME types (`image/png`, `image/jpeg`, `image/gif`, `video/mp4`, `video/webm`, `text/plain`, `application/pdf`), generates presigned PUT URL with 15-min expiry, enforces 50MB per-file limit
- **`generate_presigned_download(s3_key, expiry_seconds)`** — presigned GET URL, TTL from `S3_PRESIGN_EXPIRY` config
- **`delete_file(s3_key)`** — hard deletes from S3 (admin-only, on issue delete)
- **boto3 client config:** `endpoint_url` is omitted — boto3 routes directly to AWS. `S3_REGION` must match your bucket's region to avoid signature errors.
- **S3 key format:** `{project_slug}/{release_version}/{issue_number}/{attachment_id}/{filename}`

### 6.5 TelegramService

- **`send_notification(user_id, template, context)`** — looks up `telegram_user_id`, formats message from template, calls Bot API `sendMessage`; if `telegram_user_id` is null → logs "user not connected", no error thrown
- **`handle_connect_command(telegram_user_id, token)`** — validates `connect_token` against DB, checks expiry, links `telegram_user_id` to user, sends confirmation message
- **Message templates:** `issue_filed`, `assigned`, `fix_ready`, `fix_verified`, `regression`, `release_approved`, `release_blocked`, `mention`
- All Telegram calls run as Celery tasks — never block API requests

---

## 7. Redis Usage Map

| Key pattern | Type | TTL | Purpose |
|---|---|---|---|
| `session:{user_id}` | Hash | 60 min | JWT session data, refreshed on activity |
| `jwt:blocklist:{jti}` | String | Until exp | Revoked token JTIs |
| `inbox:unread:{user_id}` | String (int) | 30s | Cached unread count for sidebar badge |
| `ratelimit:{user_id}:{endpoint}` | String (int) | 1 min | Request rate limiting counter |
| `rw:dashboard` | Pub/Sub channel | — | Real-time dashboard events broadcast |
| `rw:inbox:{user_id}` | Pub/Sub channel | — | Real-time inbox push per user |
| `report:cache:{release_id}` | String (JSON) | 5 min | Cached report aggregate (invalidated on issue update) |
| `dashboard:cache:{project_ids_hash}` | String (JSON) | 60s | Dashboard metrics cache |

---

## 8. Celery Background Tasks

| Task | Trigger | Notes |
|---|---|---|
| `send_telegram_notification` | Any significant issue action | Retry 3× with exponential backoff; mark user as undeliverable after 3 failures |
| `validate_attachment` | After `/attachments/confirm` | Re-checks MIME type server-side (client can spoof Content-Type); generates image thumbnail via Pillow; stores thumbnail S3 key |
| `detect_regression_patterns` | Nightly cron (00:00 UTC) | Re-scores component fragility, updates regression counts, invalidates report caches |
| `calculate_time_metrics` | On status change to `fixed`/`verified` | Writes `time_to_fix_h`, `time_to_verify_h` back to issue row |
| `fan_out_inbox` | After every issue mutation | Creates `inbox_items` rows + Redis pub/sub push |
| `export_release_report` | On CSV export request | Generates CSV, uploads to S3, returns presigned download URL |
| `invalidate_report_cache` | On any issue update in a release | Deletes `report:cache:{release_id}` from Redis |

---

## 9. Authentication & Security

### 9.1 JWT Auth

- **Access tokens:** 60-minute expiry, signed with HS256 + `SECRET_KEY`
- **Refresh tokens:** 30-day expiry, stored in `HttpOnly` cookie, rotated on each refresh
- **Revocation:** `jti` (JWT ID) stored in Redis blocklist on logout
- **FastAPI dependency:** `get_current_user()` — validates token, loads user from DB, checks `is_active`

### 9.2 Role-Based Access (RBAC)

| Role | File issues | Triage | Mark fixed | Verify | Go/No-go | Admin |
|---|---|---|---|---|---|---|
| QA | ✓ | — | — | ✓ (own) | — | — |
| Developer | ✓ | — | ✓ (assigned) | — | — | — |
| Triage Lead | ✓ | ✓ | ✓ | ✓ | — | — |
| CTO | ✓ | — | — | — | ✓ | — |
| Admin | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

Implemented as FastAPI dependency: `require_role(*roles)`. Returns 403 with clear message on violation.

### 9.3 Security Hardening

- **CORS:** restricted to `ALLOWED_ORIGINS` from config
- **Rate limiting:** 100 req/min per user via Redis counter, 429 response with `Retry-After` header
- **File uploads:** server-side MIME revalidation in Celery, 50MB per file, 500MB per issue total
- **Input sanitization:** Pydantic v2 strict mode on all request bodies
- **SQL injection:** SQLAlchemy ORM only — no raw string interpolation
- **S3 presign:** 15-minute upload window; server controls key naming (client cannot path-traverse)
- **Telegram webhook:** validated via Bot API `secret_token` header

---

## 10. Product Feature Checklist

### 10.1 Issue Lifecycle

- Any authenticated user (QA / Developer / CTO) can file an issue
- Issues scoped to Project → Release (must select active release)
- Severity: `blocker` / `critical` / `major` / `minor` / `enhancement`
- Status machine: `new` → `triaged` → `in_progress` → `fixed` → `verified` → `closed`; any → `regression`
- Release-blocker flag — feeds CTO dashboard and WebSocket broadcast
- Reproduction steps (ordered list with expected/actual outcome per step)
- cURL command field (stored as TEXT, displayed as monospace code block)
- Environment metadata: browser, OS, build hash, staging URL
- Duplicate linking (`parent_issue_id`) with metric suppression for duplicates

### 10.2 File Attachments (S3)

- Screenshots: `image/png`, `image/jpeg`, `image/gif` — thumbnail generated server-side (Pillow)
- Screen recordings: `video/mp4`, `video/webm` — stored as-is
- Log files: `text/plain`, `application/pdf`
- Presigned direct upload (client → S3) — API server never handles file bytes
- Presigned download URLs served per-request (not stored in DB)
- S3 key structure: `{project_slug}/{release}/{issue_number}/{uuid}/{filename}`

### 10.3 Unified Issue Timeline

- Single chronological feed per issue — all events and comments in one view
- Event types: `filed`, `status_changed`, `severity_changed`, `assigned`, `label_added/removed`, `blocker_flagged`, `comment`, `internal_note`, `fixed`, `verified`, `regression`, `duplicate_linked`
- Internal notes: `is_internal=true` → hidden from QA role, visible to developer/triage_lead/cto/admin
- Comments: Markdown body, @mention support (stored as `mention_user_ids[]`, triggers inbox + Telegram)
- Comment edit window: 15 minutes, after which comments are immutable
- Full audit trail: every field change recorded — immutable, no delete

### 10.4 Regression Tracking

- Regression auto-detected when a verified issue is reopened
- `regression_history` records every recurrence with release context and previous fixer
- `issue.regression_count` incremented per regression
- Component fragility report: regression count aggregated by issue label across releases
- Recurrence matrix: release × issue grid — Fixed / Regression / Open / Absent
- Regression rate metric: `regressions / total_closed × 100` per release

### 10.5 Inbox & Notifications

- Personal inbox per user: all events where they are assignee, reporter, commenter, or mentioned
- `inbox_items` table: `is_read` flag, event type, linked timeline entry
- Unread count cached in Redis (30s TTL), pushed via WebSocket on new item
- Mark read: single item or mark-all — clears Redis cache
- **Telegram-only delivery:** all notifications sent via `@ReleasewatchBot`
- User connects Telegram via `/connect {token}` command to the bot
- `connect_token`: 15-minute TTL, one-time use, generated from Settings page
- If user has not connected Telegram: notification is skipped, warning shown in Settings

### 10.6 Contributions Report

- Reporter leaderboard: bugs filed per member, broken down by severity and role (QA / Dev / CTO)
- Solver leaderboard: bugs fixed per member, fix rate (fixed/assigned %), avg time-to-fix
- Regressions caused: fixed bugs that later regressed, attributed to the fixer
- Time-to-fix by severity: mean, median, fastest, slowest — for blocker / critical / major / minor
- Scatter chart data: per-issue fix time vs severity for outlier detection
- Filter by: release, date range, role, project
- All contribution queries run against pre-calculated fields (`time_to_fix_h` stored on issue row)

### 10.7 CTO Dashboard

- Real-time aggregates via WebSocket: open blockers, criticals, total open, regression rate
- Release health table: per-release signal derived from blocker count (🔴🟡🟢)
- Blocker live feed: all `is_release_blocker=true` issues across all active releases
- Activity feed: last 50 significant timeline events across all projects
- Go/No-go gate: CTO approve/block per release — requires note when blocking, timestamped and logged

### 10.8 GitLab Integration

- Webhook receives `push` and `merge_request` events from GitLab
- Issue linked to MR: when MR merges to configured target branch → issue status auto → `fixed`
- Webhook secret validated against stored config
- Self-hosted GitLab supported (configurable webhook URL)

---

## 11. Build Instructions for Claude Code

Pass these instructions to Claude Code as the project bootstrap prompt. Build phases in order — do not skip.

### Phase 1 — Project scaffold

1. Create the monorepo directory structure as specified in Section 3.1
2. Write `docker-compose.yml` and `docker-compose.dev.yml` as specified in Section 3.2
3. Write `.env.example` with all variables from Section 3.3
4. Create `backend/Dockerfile`: `python:3.12-slim`, install from `pyproject.toml`, run `uvicorn app.main:app --host 0.0.0.0 --port 8000`
5. Write `pyproject.toml` with dependencies: `fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pydantic[email]`, `pydantic-settings`, `redis[hiredis]`, `celery[redis]`, `boto3`, `python-telegram-bot`, `python-jose[cryptography]`, `passlib[bcrypt]`, `python-multipart`, `pillow`

### Phase 2 — Database models & migrations

1. Create SQLAlchemy async base in `app/db/base.py`
2. Implement all models from Section 4: `User`, `Project`, `Release`, `Issue`, `IssueReproductionStep`, `IssueTimeline`, `IssueAttachment`, `InboxItem`, `RegressionHistory`
3. All ENUMs as Python `Enum` classes, mapped to PostgreSQL native ENUMs
4. Initialize Alembic: `alembic init alembic`, configure `env.py` for async SQLAlchemy
5. Generate initial migration: `alembic revision --autogenerate -m 'initial schema'`
6. Write seed script (`scripts/seed.py`) using the mock team and issue data from the frontend PRD

### Phase 3 — Core services

1. `app/config.py` — pydantic-settings `Settings` class, reads all `.env` variables
2. `app/core/auth.py` — JWT create/verify, `get_current_user` dependency, `require_role` factory
3. `app/core/redis_client.py` — async Redis connection pool, pub/sub helpers
4. `app/core/s3.py` — `S3Service` with `generate_presigned_upload`, `generate_presigned_download`, `delete_file`
5. `app/core/telegram.py` — `TelegramService` with `send_notification`, `handle_connect_command`, all message templates
6. `app/tasks/celery_app.py` — Celery app configured with Redis broker
7. `app/tasks/notifications.py` — `send_telegram_notification` task with retry logic
8. `app/tasks/attachments.py` — `validate_attachment` task (Pillow thumbnail generation)
9. `app/tasks/inbox.py` — `fan_out_inbox` task
10. `app/tasks/reports.py` — `invalidate_report_cache` task

### Phase 4 — API routes

1. Implement all endpoints from Section 5, organized as `APIRouter` per resource under `app/api/v1/`
2. Each route: validate input with Pydantic schema → call service → return response schema
3. No business logic in route handlers — all logic in `services/`
4. WebSocket handlers for `/ws/dashboard` and `/ws/inbox` — validate JWT from query param, subscribe to Redis pub/sub
5. Telegram webhook at `/telegram/webhook` — validate secret, dispatch to `TelegramService`

### Phase 5 — Business logic services

1. `app/services/issue_service.py` — `IssueService`: `create`, `triage`, `fix`, `verify`, `reopen`, `duplicate`
2. `app/services/regression_service.py` — `RegressionService`: `record`, `get_component_fragility`, `get_recurrence_matrix`
3. `app/services/inbox_service.py` — `InboxFanOutService` per trigger table in Section 6.3
4. `app/services/report_service.py` — release report aggregates, contribution metrics, time-to-fix stats
5. `app/services/timeline_service.py` — `create_event()`, `list_timeline()`, `edit_comment()`

### Phase 6 — Developer experience

1. `Makefile` with targets: `make dev` (docker compose up), `make migrate`, `make seed`, `make test`, `make lint`
2. pytest setup: `conftest.py` with async test client, in-memory SQLite for unit tests, test fixtures for all models
3. `README.md`: quickstart (`clone → cp .env.example .env → make dev`), architecture diagram, API reference link
4. Health check endpoint: `GET /health` → `{status: ok, version, db: ok, redis: ok, s3: ok}`

---

## 12. Technology Decision Summary

| Decision | Choice | Reason |
|---|---|---|
| Web framework | FastAPI 0.111 | Async-native, Pydantic v2 built-in, WebSocket support, auto OpenAPI docs |
| ORM | SQLAlchemy 2 async + asyncpg | Async driver, Alembic migrations, no performance bottleneck |
| Database | PostgreSQL 16 | JSONB for event meta, native ENUMs, window functions for metrics queries |
| Cache / Queue broker | Redis 7 | Pub/sub for WebSocket fan-out, TTL-based cache, Celery broker |
| Task queue | Celery 5 | Proven async task runner; handles Telegram retries, file validation, cache invalidation |
| File storage | AWS S3 (boto3) | `S3_ENDPOINT_URL` omitted — boto3 routes to AWS natively; presigned uploads bypass API server; no container needed |
| Notifications | python-telegram-bot async | Sole notification channel per spec; async, retry-capable |
| Auth | JWT (HS256) + HttpOnly refresh cookie | Stateless access tokens; Redis blocklist for logout; no third-party auth dependency |
| Real-time | WebSocket + Redis pub/sub | No extra infra; scales to multi-worker via Redis channel fan-out |
| Containerization | Docker Compose | Single-command local dev; same file works for small production deployments |
| Migrations | Alembic | Auto-generate from SQLAlchemy models; sequential version IDs; reversible |
| Config management | pydantic-settings | Type-safe `.env` parsing; `Settings` singleton injected via FastAPI dependency |

---

> **Ready to build.** This document is the complete specification for Claude Code. Start with `claude` in the project root and reference this document section by section. Each phase builds on the previous — do not skip phases. The `.env.example`, `docker-compose.yml`, and Alembic migrations must exist before any service code is written. S3 connects as an external service — fill in your bucket name, access key, secret key, and region in `.env` and the app connects on first start.
