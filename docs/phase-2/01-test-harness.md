# 01 — Test Harness

> **Depends on:** nothing · **Blocks:** every other slice
> **PRD:** none. This slice exists so every later slice can be built test-first.

## Problem Statement

Releasewatch has no automated tests. `pyproject.toml` points pytest at `backend/tests/`, but that directory does not exist. The frontend has no test tooling. CI checks only that migrations apply and that the frontend builds. Phase 2 rewrites the status model, which every page and report depends on. Without tests, each slice risks silently breaking Phase 1 behavior that the organization relies on today.

## Solution

Build two test layers at the highest seams the code offers, plus one developer aid:

1. **API tests (backend).** pytest drives the real FastAPI app over HTTP, in-process, against a real PostgreSQL (pgvector image). Two fakes stand in at the system's edges: a **Telegram outbox recorder** and a **no-op for background jobs** (embeddings, attachment validation). Tests observe only what a client can observe: HTTP responses, the recipient's inbox (`GET /inbox`), and the recorded Telegram sends.
2. **E2E tests (browser).** Playwright Test drives the real frontend against the full Docker stack for three key screens: the support form, the triage queue, and the personal board. The scenarios are added in slices 05, 06, and 10. This slice builds the harness and one smoke test.
3. **Playwright MCP (developer aid, not a test layer).** Configured for Claude Code so it can open the running app, click through a screen it just built, and take screenshots while working. MCP sessions are not repeatable, not in CI, and never replace the Playwright suite.

## User Stories

1. As a developer, I want `make test` to run the backend suite against a disposable database, so that I can run it at any time without touching my dev data.
2. As a developer, I want each test to start from an empty database, so that tests never depend on each other or on seed data.
3. As a developer, I want the schema built by running the real Alembic migrations, so that tests also prove the migrations work.
4. As a developer, I want a one-line way to get an authenticated HTTP client for a user of any role, so that permission tests are short.
5. As a developer, I want small factory helpers (user, project, release, issue) that go through the API wherever an endpoint exists, so that tests exercise the same paths as real clients.
6. As a developer, I want every Telegram send recorded rather than sent, so that I can assert who was notified, with which template, without a bot.
7. As a developer, I want embedding and attachment-validation jobs replaced by no-ops, so that tests never load a model or call S3.
8. As a developer, I want Redis publish failures to stay non-fatal in tests, so that the suite does not need Redis to be healthy.
9. As a developer, I want a controllable clock for scheduled jobs (due dates, overdue milestones), so that time-based rules can be tested deterministically.
10. As a developer, I want characterization tests for the Phase 1 flows that Phase 2 must keep (file bug, triage, fix, verify, regression, internal comments, release report counts), so that slice 02 can prove it changed statuses without changing behavior.
11. As a developer, I want `make e2e` to bring up an isolated stack, seed known users per role, and run the Playwright suite headless, so that browser tests are one command.
12. As a developer, I want each E2E test to create its own data through the API, so that browser tests stay independent and fast.
13. As a developer, I want to log in once per role and reuse the browser storage state, so that E2E tests do not repeat the login screen.
14. As a developer, I want to run E2E headed or in Playwright's UI mode locally, so that I can watch a failing test.
15. As a developer on macOS, I want to optionally point Playwright at a Chromium-based browser I already have installed, so that I can reproduce issues in my daily browser.
16. As Claude Code, I want the Playwright MCP server available in this repo, so that I can visually check a screen I just built before finishing a slice.
17. As a maintainer, I want CI to run the API suite on every PR that touches the backend, so that regressions are caught before merge.
18. As a maintainer, I want CI to run the E2E suite on PRs that touch either half, with traces uploaded on failure, so that browser failures can be diagnosed without re-running locally.

## Implementation Decisions

### Backend API tests

- **Location:** `backend/tests/`, matching the existing `testpaths`. Dev dependencies already include pytest, pytest-asyncio (`asyncio_mode = "auto"`), pytest-cov, and factory-boy. Add `respx` only if a test needs to fake outbound HTTP; the fakes below should make that unnecessary.
- **Database:** a separate database named `<POSTGRES_DB>_test` on the same Postgres server (the compose `postgres` service locally, a pgvector service container in CI). A session-scoped fixture creates it if missing, enables `vector`, and runs `alembic upgrade head` once. Settings are overridden through environment variables **before** `app` is imported, because `config.settings` is a module-level singleton.
- **Isolation: truncate, not rollback.** After each test, `TRUNCATE` every table except `alembic_version`, with `RESTART IDENTITY CASCADE`. Rollback-based isolation is rejected because `get_db` commits and some code paths open their own sessions. Tests must not assert absolute `issue_number` values, since `issue_number_seq` is not reset.
- **HTTP client:** `httpx.AsyncClient` with `ASGITransport(app=app)`, base URL `http://test/api/v1`. `get_db` is not overridden: the app runs its normal session against the test database.
- **Auth helper:** `client_for(user)` mints a Releasewatch token with the existing `create_access_token`. It does not call `/auth/login`, except in one test that covers login itself.
- **Fakes at the edges (autouse):**
  - *Telegram outbox recorder:* replaces `send_telegram_notification.apply_async` with a recorder that captures `(chat_id, template_name, context)`. It is exposed as a `telegram` fixture with helpers such as `telegram.sent_to(user)`. Recipients need a linked `TelegramIntegration` for a send to be recorded, so provide a `link_telegram(user)` helper.
  - *Background jobs:* `embed_issue.apply_async` and `validate_attachment.apply_async` become no-ops that record their calls. (Slice 12 replaces the Phase 1 embedding job and adds a deterministic fake embedding endpoint; slice 13 adds a fake Jev. Both follow the same "fake at the edge" rule.)
  - *Redis:* leave `publish` as is (it already swallows errors). CI provides a Redis service anyway.
- **Clock:** add a `get_now` FastAPI dependency that returns the current UTC time. Phase 2 code that stamps or compares time (`transition()` timestamps, due states, overdue checks, the Done-column window) takes `now` from it and never calls `datetime.now()` directly. Tests override it through `app.dependency_overrides` with a `clock` fixture (`clock.set(...)`, `clock.advance(days=8)`). Phase 1 code keeps its own `datetime.now()` calls; convert them only where a Phase 2 slice touches that code.
- **Scheduled jobs seam:** Celery beat tasks are tested by calling the task's async body directly, with `now` passed in. Each new scheduled job must take `now` as a parameter, defaulting to the real time. This is the only sanctioned seam below HTTP.
- **Observations allowed in tests:** HTTP responses, `GET /inbox` as the recipient, and the Telegram recorder. Tests do not query ORM models to assert results. The one exception is migration tests, which by nature inspect rows.
- **Characterization suite:** `tests/phase1/` covers today's behavior: file bug (with a release) → triage → fix → verify pass/fail → reopen, regression recording and `regression_count`, internal comments hidden where `include_internal=False`, duplicate linking, and `GET /reports/releases/{id}` counts for a known fixture. Slice 02 is allowed to change these tests only by mapping old status names to new ones. The behavior asserted must stay the same.
- **Commands:** `make test` (already defined) runs `docker compose exec api pytest -v`. Add `make test-local` for running with a local venv against the compose Postgres.

### E2E tests

- **Tooling:** Playwright Test (`@playwright/test`) in a new top-level `e2e/` package with its own `package.json`, TypeScript, and the bundled Chromium. It is kept out of `frontend/` so the app image does not ship test dependencies.
- **Stack:** `docker-compose.e2e.yml` overlays the production compose file with its own database name, a fixed `SECRET_KEY`, and Telegram disabled (no bot token, so sends are skipped). It serves the built frontend. `make e2e` brings it up, waits for `/health`, runs migrations, runs the seed, runs `npx playwright test`, and tears everything down. `make e2e-ui` keeps the stack up and opens Playwright UI mode.
- **Seed:** add `backend/scripts/seed_e2e.py`. It wipes the E2E database and creates one active user per role with known passwords, including `product_manager` and `support` once slice 04 adds them. It also creates one product project with a triage lead. Later slices extend the seed only with what their scenarios need, such as a support template (05).
- **Auth:** `globalSetup` logs in through the real UI once per role and saves `e2e/.auth/<role>.json`, which is gitignored. Each test declares its role with `test.use({ storageState })`. The frontend stores `rw:token` and `rw:refresh_token` in localStorage, and the storage state captures both.
- **Test data:** each test creates what it needs through the API, using Playwright's `request` fixture with the role's token, then uses the browser only for the behavior under test.
- **Selectors:** prefer `getByRole` and `getByLabel`. Add `data-testid` only where an element has no accessible name. A test that needs a test ID is a hint that the component is missing a label.
- **Browser choice:** the default is bundled Chromium, headless in CI and headed via `make e2e-headed`. Setting `E2E_BROWSER_PATH` switches `launchOptions.executablePath` to a local Chromium-based browser for manual reproduction only. CI always uses bundled Chromium.
- **Artifacts:** `trace: 'retain-on-failure'`, screenshots on failure, and an HTML report. CI uploads `e2e/playwright-report` and `e2e/test-results`.
- **This slice's only E2E test:** a smoke test in which each seeded role logs in and the dashboard renders without console errors.

### Playwright MCP

- Add a project-scoped `.mcp.json` that registers `@playwright/mcp` (run with `npx`, headless off, isolated profile) so Claude Code gets it automatically in this repo.
- Add a short section to `CLAUDE.md` covering when to use it: after building or changing a screen, open it at `http://localhost:5173`, sign in with a seeded user, walk the golden path, and check both themes. It must not be used to replace an E2E scenario or to verify business rules. Rules are proven by API tests.

### CI

- Add a `backend-tests` job that reuses the existing `pgvector/pgvector:pg16` service, adds a `redis:7` service, and runs `uv pip install --system -e ".[dev]"` then `pytest --cov=app`.
- Add an `e2e` job that runs when `frontend` or `backend` changed. It builds with compose, runs `make e2e`, and uploads artifacts on failure.
- The `docker` publish job gains both new jobs in `needs`.

## Testing Decisions

- **A good test** states a user-visible outcome: a response body, an inbox item, a Telegram send, or something rendered on screen. It survives any refactor that keeps that outcome. Tests never assert on internal method calls, ORM state (except in migration tests), or CSS classes.
- **Test names** follow `test_<behavior>`, or `test_ac_<nn>_<behavior>` when they prove a PRD acceptance criterion, so PRD coverage is searchable.
- **Prior art:** none in this repo. `backend/scripts/test_mention_inbox.py` is a manual script, not a test. It shows the fan-out behavior worth asserting, and should be deleted once `tests/phase1/test_mentions.py` covers it.
- **This slice's own tests:** the characterization suite and the E2E smoke test. The harness is proven by those tests passing twice in a row in the same run (isolation) and in CI.

## Out of Scope

- Unit tests for React components. The frontend is covered by E2E on key screens only (decided with the user).
- Visual regression and screenshot diffing.
- Load or performance testing.
- Testing the Telegram bot's inbound command handlers (`/status`, `/start`). They are unchanged in Phase 2.

## Further Notes

- The embedding model (`fastembed` until slice 12, then the `embeddings` service) is heavy. If a test ever loads it, the no-op fake is not installed early enough. Fix the fixture order rather than marking the test slow.
- Existing `__pycache__` directories and `backend/celerybeat-schedule` are committed. Add them to `.gitignore` and remove them in this slice so test runs do not create noisy diffs.
