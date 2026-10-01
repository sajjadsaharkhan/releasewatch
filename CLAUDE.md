# Releasewatch

A release-scoped QA issue tracker for software teams.

> **Design & frontend conventions live in [`docs/design.md`](docs/design.md).** Read it
> before touching anything visual — design tokens, both themes, the severity/status/role
> color scales, type scale, spacing, the component inventory, motion, copy rules, and the
> current list of known drift. This file only summarises the frontend; `docs/design.md` is
> the authority on how it should look and behave.

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
| `#/releases`, `#/projects/:slug/releases` | ReleasesPage (per project) |
| `#/releases/:id` | ReleaseDetailPage |
| `#/projects/:slug/stream` | StreamPage |
| `#/regressions` | RegressionsPage |
| `#/release-reports` | ReleaseReportsPage |
| `#/contributions` | ContributionsPage |
| `#/support/new` | SupportReportPage (Support + Admin) |
| `#/support/reports` | SupportReportsPage |
| `#/u/:username` | ProfilePage |
| `#/team` | TeamPage |
| `#/settings` | SettingsPage |

### Component conventions

Summary only — the full rules (tokens, color semantics, type scale, spacing, radius,
motion, a11y, copy) are in [`docs/design.md`](docs/design.md).

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
supportApi, templatesApi
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
| `/api/v1/support` | `api/v1/support.py` |
| `/api/v1/projects/{id}/templates` | `api/v1/support_templates.py` |
| `/api/v1/settings` | `api/v1/settings.py` |
| `/api/v1/search`, `/api/v1/features`, `/api/v1/settings/search(/reindex, /jev, /jev/test)` | `api/v1/search.py` (engine in `app/search/`, Jev client `app/search/jev.py`) |
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
| `make test` | Run pytest suite (inside the api container) |
| `make test-local` | Run pytest from a local venv against the compose Postgres/Redis |
| `make e2e` | Bring up an isolated E2E stack, seed it, run the Playwright suite headless, tear down |
| `make e2e-ui` | Same, but keeps the stack up and opens Playwright UI mode |
| `make e2e-headed` | Same as `make e2e`, headed |
| `make lint` | ruff (backend) + eslint (frontend) |
| `make embeddings-fetch` | Download `BAAI/bge-m3` into the `embeddings_models` volume, once, online |
| `make shell` | Python REPL inside api container |
| `make logs` | Follow api + worker logs |

## Testing

Backend API tests (`backend/tests/`) drive the real FastAPI app in-process over HTTP
against a real Postgres, with Telegram sends recorded instead of sent and the
embedding/attachment-validation background jobs replaced by no-ops. E2E tests
(`e2e/`, Playwright) drive the real frontend against the full Docker stack for a
handful of key screens. See `docs/phase-2/01-test-harness.md` for the full design.

### Playwright MCP (dev aid, not a test layer)

`.mcp.json` registers `@playwright/mcp` for this repo. After building or changing a
screen, open it at `http://localhost:5173`, sign in with a seeded user, walk the
golden path, and check both light and dark themes before calling the work done.

MCP sessions are not repeatable and are not run in CI — they're a way to look at
what you just built, not a substitute for a `make e2e` scenario or an API test that
asserts a business rule. If a check is worth repeating, it belongs in one of those
two suites instead.

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
