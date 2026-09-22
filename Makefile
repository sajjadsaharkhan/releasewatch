.PHONY: dev dev-build stop migrate migrate-down seed seed-admin test test-local lint format shell logs \
	e2e e2e-up e2e-down e2e-ui e2e-headed backend-dev-deps

# ── Local development ─────────────────────────────────────────────────────────

dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

dev-build:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build

stop:
	docker compose down

# ── Database ──────────────────────────────────────────────────────────────────

migrate:
	docker compose exec api alembic upgrade head

migrate-down:
	docker compose exec api alembic downgrade -1

migrate-new:
	@read -p "Migration message: " msg; \
	docker compose exec api alembic revision --autogenerate -m "$$msg"

seed:
	docker compose exec api python -m scripts.seed

seed-admin:
	docker compose exec api python -m scripts.create_admin

# ── Testing ───────────────────────────────────────────────────────────────────

# The api image only ships runtime deps (see backend/Dockerfile) — pytest/ruff
# live in the [dev] extra, installed into the running container on demand
# rather than shipped in the production image.
backend-dev-deps:
	docker compose exec api pip install --no-cache-dir -q -e ".[dev]"

test: backend-dev-deps
	docker compose exec api pytest -v

test-cov: backend-dev-deps
	docker compose exec api pytest --cov=app --cov-report=term-missing -v

# Runs against the compose Postgres/Redis (already up via `make dev`) from a
# local venv instead of inside the api container — same .env, but talking to
# the exposed host ports rather than the container-network hostnames.
test-local:
	cd backend && \
	set -a && . ../.env && set +a && \
	POSTGRES_HOST=localhost REDIS_URL=redis://localhost:6379/0 python -m pytest -v

# ── E2E (Playwright, e2e/) ─────────────────────────────────────────────────────

e2e-up:
	docker compose -f docker-compose.yml -f docker-compose.e2e.yml -p releasewatch-e2e up -d --build
	@echo "Waiting for the E2E stack to become healthy..."
	@for i in $$(seq 1 60); do \
		curl -sf http://localhost:8081/health > /dev/null && exit 0; \
		sleep 2; \
	done; \
	echo "E2E stack did not become healthy in time" && exit 1
	docker compose -f docker-compose.yml -f docker-compose.e2e.yml -p releasewatch-e2e exec -T api alembic upgrade head
	docker compose -f docker-compose.yml -f docker-compose.e2e.yml -p releasewatch-e2e exec -T api python -m scripts.seed_e2e

e2e-down:
	docker compose -f docker-compose.yml -f docker-compose.e2e.yml -p releasewatch-e2e down -v

e2e: e2e-up
	(cd e2e && npm ci && npx playwright test); \
	status=$$?; \
	$(MAKE) e2e-down; \
	exit $$status

e2e-ui: e2e-up
	cd e2e && npm ci && npx playwright test --ui

e2e-headed: e2e-up
	(cd e2e && npm ci && npx playwright test --headed); \
	status=$$?; \
	$(MAKE) e2e-down; \
	exit $$status

# ── Code quality ──────────────────────────────────────────────────────────────

lint: backend-dev-deps
	docker compose exec api ruff check app/ tests/
	cd frontend && npm run lint

format: backend-dev-deps
	docker compose exec api ruff format app/ tests/

# ── Utilities ─────────────────────────────────────────────────────────────────

shell:
	docker compose exec api python

logs:
	docker compose logs -f api worker

# ── Frontend (local, without Docker) ─────────────────────────────────────────

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build
