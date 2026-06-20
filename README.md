# Releasewatch

A release-scoped QA issue tracker for software teams. Collect, triage, and track bugs against specific releases — with semantic search, Telegram notifications, and real-time updates.

---

## Features

- **Release-scoped issues** — bugs and regressions are always tied to a release, so nothing gets lost between cycles
- **Semantic search** — multilingual vector search (Persian + English) powered by a local ONNX embedding model; no external API required
- **Inbox & fan-out** — every relevant event is fanned out to team members' inboxes with real-time WebSocket updates
- **Telegram bot** — receive notifications and interact with issues directly from Telegram
- **Regression detection** — automatic pattern detection across releases
- **Release reports** — contribution metrics and regression KPIs per release
- **File attachments** — presigned S3/MinIO uploads; the server never handles file bytes
- **Dark mode** — full dark/light theme support

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite 5, Tailwind CSS 3, React Router v6 |
| Backend | FastAPI 0.111, SQLAlchemy 2 async, Alembic |
| Database | PostgreSQL 16 + pgvector |
| Cache / broker | Redis 7 |
| Task queue | Celery 5 |
| Embeddings | fastembed + ONNX (`paraphrase-multilingual-MiniLM-L12-v2`) |
| Storage | AWS S3 or MinIO |
| Notifications | python-telegram-bot |

---

## Quick start

### Prerequisites

- Docker and Docker Compose
- An S3 bucket or MinIO instance (optional — attachments won't work without it)
- A Telegram bot token (optional — notifications won't work without it)

### 1. Clone and configure

```sh
git clone git@github.com:sajjadsaharkhan/releasewatch.git
cd releasewatch
cp .env.example .env
```

Edit `.env` and set at minimum:

```env
SECRET_KEY=<random 64-char string>
POSTGRES_PASSWORD=<strong password>
```

### 2. Start the stack

```sh
docker compose up -d
```

This starts: `api`, `worker`, `beat`, `frontend`, `postgres`, `redis`.

### 3. Run migrations and seed data

```sh
make migrate      # apply all Alembic migrations
make seed         # populate with sample data
make seed-admin   # create an admin user
```

### 4. Open the app

| Service | URL |
|---|---|
| Frontend | http://localhost:8080 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |

---

## Development

Run the stack with hot reload (source is volume-mounted):

```sh
make dev
```

### Frontend only (without Docker)

```sh
make frontend-install   # npm install
make frontend-dev       # Vite dev server on :5173
```

### Useful Makefile targets

| Target | Description |
|---|---|
| `make dev` | Start full stack with hot reload |
| `make migrate` | Run pending Alembic migrations |
| `make migrate-new` | Generate a migration from model changes |
| `make test` | Run pytest suite |
| `make logs` | Follow api + worker logs |
| `make shell` | Python REPL inside the api container |

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | yes | JWT signing secret (min 32 chars) |
| `POSTGRES_PASSWORD` | yes | PostgreSQL password |
| `REDIS_URL` | yes | Redis connection URL |
| `S3_BUCKET_NAME` | no | S3 or MinIO bucket for attachments |
| `S3_ENDPOINT_URL` | no | Set for MinIO; leave empty for AWS S3 |
| `TELEGRAM_BOT_TOKEN` | no | Telegram bot token for notifications |
| `JWT_ACCESS_EXPIRE_MINUTES` | no | Access token lifetime (default: 60) |

See `.env.example` for the full list with comments.

---

## Semantic search

Search is powered by a local embedding model (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions) bundled inside the Docker image — no external API or network call required at query time.

Issues are indexed across three field groups:

- **core** — title (double-weighted) + description + labels
- **repro** — environment, reproduction steps, curl commands
- **talk** — one embedding per comment (not aggregated)

Per-comment indexing means a single comment mentioning a keyword like `roadmap` is found even if other comments in the same issue are unrelated.

Reindex all issues after seeding or importing data:

```sh
curl -X POST http://localhost:8000/api/v1/search/reindex \
  -H "Authorization: Bearer <token>"
```

---

## Project structure

```
releasewatch/
├── docker-compose.yml          # Production stack
├── docker-compose.dev.yml      # Dev overrides (hot reload + volume mounts)
├── .env.example                # All env vars documented
├── Makefile
├── frontend/                   # React 18 + Vite app
│   └── src/
│       ├── pages/              # One file per route
│       ├── components/         # ui/, layout/, common/, issues/
│       ├── context/            # AppContext — global state
│       └── lib/                # api.js, cn.js, markdown.js
└── backend/
    └── app/
        ├── api/v1/             # Thin route handlers
        ├── services/           # Business logic
        ├── tasks/              # Celery tasks
        ├── db/models/          # SQLAlchemy models
        └── schemas/            # Pydantic v2 schemas
```

---

## CI

GitHub Actions runs on every push and pull request to `main` / `develop`:

- **Frontend** — `npm ci` → `vite build` → uploads `dist/` artifact
- **Backend** — installs deps, runs migrations against a real PostgreSQL + Redis service, runs pytest
- **Docker** — builds both images (with layer cache) on pushes to `main` / `develop`
