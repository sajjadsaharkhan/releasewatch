# Releasewatch

A release-scoped QA issue tracker for software teams.

## Monorepo Structure

```
releasewatch/
├── docker-compose.yml          # Production stack
├── docker-compose.dev.yml      # Dev overrides (hot reload)
├── .env.example                # All env vars documented
├── Makefile                    # Common dev tasks
├── frontend/                   # React 18 + Vite app
├── backend/                    # FastAPI + PostgreSQL + Redis
└── design-prototype/           # Original CDN-based design prototype (reference only)
```

## Quick Start

```sh
cp .env.example .env          # fill in your values
make dev                      # docker compose up with hot reload
make migrate                  # run alembic migrations
make seed                     # populate with sample data
```

## Frontend (`frontend/`)

React 18 + Vite 5 + Tailwind CSS 3. Hash-based routing via React Router v6.

### Running locally (without Docker)

```sh
make frontend-install   # npm install
make frontend-dev       # vite dev server on :5173
```

### Source layout

```
frontend/src/
├── main.jsx              # ReactDOM.createRoot entry
├── App.jsx               # Router, keyboard shortcuts, global providers
├── context/
│   └── AppContext.jsx    # Global state: theme, active project/release, modals
├── hooks/
│   ├── useApp.js         # Re-export of useApp from context
│   ├── useToast.js       # Toast notification hook
│   └── useTweaks.js      # Design tweaks (localStorage-persisted)
├── lib/
│   ├── cn.js             # clsx + tailwind-merge utility
│   ├── api.js            # Axios instance + all API functions by resource
│   ├── relTime.js        # Relative time formatting ("3h ago")
│   └── markdown.js       # Inline + block markdown → JSX parser
├── data/
│   └── mockData.js       # Mock data (replaces API calls during dev)
├── components/
│   ├── ui/               # shadcn-style primitives (Button, Card, Badge, Dialog, …)
│   ├── layout/           # AppShell, Sidebar, Topbar, NavItem
│   ├── common/           # CommandPalette, IssueTable, IssueBoard, MetricCard, …
│   ├── issues/           # IssueDetail, IssueTimeline, CommentComposer, NewIssueModal, …
│   └── dev/              # TweaksPanel (floating design-tweaks panel)
└── pages/                # One file per route
    ├── DashboardPage.jsx
    ├── InboxPage.jsx
    ├── IssuesPage.jsx
    ├── IssuePage.jsx       # /issue/:id — single issue detail
    ├── TriagePage.jsx
    ├── ReleasesPage.jsx
    ├── RegressionsPage.jsx
    ├── ReleaseReportsPage.jsx
    ├── ContributionsPage.jsx
    ├── ProfilePage.jsx     # /u/:username
    ├── TeamPage.jsx
    └── SettingsPage.jsx
```

### Routes

| Hash | Page component |
|------|---------------|
| `#/dashboard` | DashboardPage |
| `#/inbox` | InboxPage |
| `#/issues` | IssuesPage |
| `#/issue/:id` | IssuePage |
| `#/triage` | TriagePage |
| `#/releases` | ReleasesPage |
| `#/regressions` | RegressionsPage |
| `#/release-reports` | ReleaseReportsPage |
| `#/contributions` | ContributionsPage |
| `#/u/:username` | ProfilePage |
| `#/team` | TeamPage |
| `#/settings` | SettingsPage |

### Component conventions

- **Named exports** for all components except pages (pages use `export default`)
- **Barrel `index.js`** in each component folder — import from the folder, not the file
- **`cn()` utility** from `lib/cn.js` — always use for Tailwind class merging
- **`<Icon name="kebab-case" size={16} />`** wraps `lucide-react`
- **Tone system** on Badge/Button/MetricCard: `"default" | "blue" | "green" | "amber" | "red"`
- **Dark mode** via `dark:` Tailwind variants; toggled with `document.documentElement.classList`

### API layer

All API calls go through `src/lib/api.js`. Export shape:

```js
authApi, issuesApi, inboxApi, reportsApi, teamApi
projectsApi, timelineApi, attachmentsApi, settingsApi
```

Falls back to `mockData.js` when the API is unreachable.

## Backend (`backend/`)

FastAPI 0.111 + SQLAlchemy 2 async + Alembic. See `releasewatch-technical-proposal.md` in `design-prototype/` for the full spec.

### Source layout

```
backend/
├── Dockerfile
├── pyproject.toml
├── alembic.ini
├── alembic/
│   └── versions/           # Migration files (generated, do not hand-edit)
├── scripts/
│   └── seed.py             # Dev data seeder
└── app/
    ├── main.py             # FastAPI app factory + /health endpoint
    ├── config.py           # pydantic-settings Settings singleton
    ├── db/
    │   ├── base.py         # DeclarativeBase + TimestampMixin
    │   ├── session.py      # Async engine + get_db() dependency
    │   └── models/         # One file per table (User, Issue, Release, …)
    ├── api/v1/             # Thin route handlers (one file per resource)
    ├── services/           # Business logic (IssueService, RegressionService, …)
    ├── tasks/              # Celery task definitions
    ├── schemas/            # Pydantic v2 request/response models
    └── core/               # auth.py, redis_client.py, s3.py, telegram.py
```

### API endpoints summary

| Prefix | Router file |
|--------|------------|
| `/api/v1/auth` | `api/v1/auth.py` |
| `/api/v1/projects` | `api/v1/projects.py` |
| `/api/v1/releases` | `api/v1/releases.py` |
| `/api/v1/issues` | `api/v1/issues.py` |
| `/api/v1/issues/{id}/timeline` | `api/v1/timeline.py` |
| `/api/v1/issues/{id}/attachments` | `api/v1/attachments.py` |
| `/api/v1/inbox` | `api/v1/inbox.py` |
| `/api/v1/reports` | `api/v1/reports.py` |
| `/api/v1/team` | `api/v1/team.py` |
| `/api/v1/settings` | `api/v1/settings.py` |
| `/api/v1/telegram/webhook` | `api/v1/telegram.py` |
| `/ws/dashboard`, `/ws/inbox` | `api/v1/ws.py` |
| `GET /health` | `main.py` |

### Architecture principles

- **Thin routes** — route handlers validate input and call a service. No business logic in routes.
- **Services** own state transitions: `IssueService`, `RegressionService`, `InboxFanOutService`, `ReportService`, `TimelineService`
- **Background tasks** via Celery: Telegram notifications, attachment validation, inbox fan-out, report cache invalidation
- **Presigned S3 uploads** — client uploads directly to S3, API server never handles file bytes
- **WebSockets** backed by Redis pub/sub channels: `rw:dashboard` and `rw:inbox:{user_id}`

### Makefile targets

| Target | Action |
|--------|--------|
| `make dev` | Start full stack with hot reload |
| `make migrate` | Run pending Alembic migrations |
| `make migrate-new` | Generate a new migration from model changes |
| `make seed` | Populate DB with sample data |
| `make test` | Run pytest suite |
| `make lint` | ruff (backend) + eslint (frontend) |
| `make shell` | Python REPL inside api container |
| `make logs` | Follow api + worker logs |

## CDN Dependencies (frontend Vite build)

| Library | Version |
|---------|---------|
| React | 18.3.1 |
| React Router DOM | 6.26 |
| Recharts | 2.12.7 |
| Lucide React | 0.453.0 |
| Tailwind CSS | 3.4 |
| Axios | 1.7 |

## Design Prototype

The original self-contained CDN prototype lives in `design-prototype/`. It opens directly as `design-prototype/index.html` — no build step. Use it as a visual reference; the `frontend/` is the canonical implementation.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

## IMPORTANT: Token Efficiency

**Always** run `graphify query "<question>"` before using Grep/Glob/Read on this codebase.
The graph is at graphify-out/graph.json (222 files, 1657 nodes).
Direct file searching without consulting the graph first is wasteful and forbidden.
