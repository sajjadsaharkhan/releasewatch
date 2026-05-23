.PHONY: dev dev-build stop migrate migrate-down seed seed-admin test lint format shell logs

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

test:
	docker compose exec api pytest -v

test-cov:
	docker compose exec api pytest --cov=app --cov-report=term-missing -v

# ── Code quality ──────────────────────────────────────────────────────────────

lint:
	docker compose exec api ruff check app/
	cd frontend && npm run lint

format:
	docker compose exec api ruff format app/

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
