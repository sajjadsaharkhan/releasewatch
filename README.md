<p align="center">
  <img src="frontend/src/assets/logo.svg" alt="Releasewatch" width="120" />
</p>

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
| Frontend | http://localhost:8003 |
| API | http://localhost:8080 |
| API docs | http://localhost:8080/docs |

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
curl -X POST http://localhost:8080/api/v1/search/reindex \
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

## Production deployment

### Prerequisites on the server

- Docker Engine 24+ and Docker Compose v2
- A GitHub Personal Access Token (PAT) with `read:packages` scope to pull from GHCR

### First-time setup

```sh
# 1. Clone the repo (config files only — no source build on the server)
git clone git@github.com:sajjadsaharkhan/releasewatch.git
cd releasewatch

# 2. Create the env file
cp .env.production.example .env
# Edit .env — set SECRET_KEY, POSTGRES_PASSWORD, domain, S3, Telegram

# 3. Log in to GitHub Container Registry
echo "<YOUR_PAT>" | docker login ghcr.io -u <github-username> --password-stdin

# 4. Pull images and start the stack
IMAGE_TAG=latest ./deploy.sh

# 5. Create the first admin user
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  exec api python -m scripts.create_admin
```

### Subsequent deploys

```sh
# Deploy latest images (built by CI on every push to main)
./deploy.sh

# Deploy a specific commit
./deploy.sh abc1234
```

`deploy.sh` does the following in order:

1. Pulls the new `api` and `frontend` images from GHCR
2. Runs `alembic upgrade head` in a throwaway container (migrations before traffic switch)
3. Restarts all services with `docker compose up -d`
4. Polls `GET /health` for up to 30 seconds and exits non-zero if the API doesn't come up
5. Prunes dangling images

### Production checklist

- [ ] `SECRET_KEY` is a random 64-char string (`openssl rand -hex 32`)
- [ ] `ENVIRONMENT=production` in `.env`
- [ ] `ALLOWED_ORIGINS` matches your actual domain
- [ ] `POSTGRES_PASSWORD` is a strong password
- [ ] `.env` is **not** committed to git (it's in `.gitignore`)
- [ ] GHCR login configured on the server
- [ ] PostgreSQL and Redis ports are **not** exposed (handled by `docker-compose.prod.yml`)
- [ ] Daily database backups configured (`pg_dump` cron or managed DB)

---

## CI

GitHub Actions runs on every push and pull request to `main` / `develop`:

- **Frontend** — `npm ci` → `vite build` → uploads `dist/` artifact
- **Backend** — installs deps, runs migrations against a real PostgreSQL + Redis service, runs pytest
- **Docker** — builds both images (with layer cache) on pushes to `main` / `develop`
