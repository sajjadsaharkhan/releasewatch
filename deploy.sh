#!/usr/bin/env bash
# deploy.sh — pull latest images from GHCR and restart the production stack
#
# Usage:
#   ./deploy.sh                 # deploys latest tag
#   ./deploy.sh abc1234         # deploys a specific git SHA tag
#   IMAGE_TAG=abc1234 ./deploy.sh
#
# Requirements on the server:
#   - Docker + Docker Compose v2
#   - .env file present (copy from .env.production.example)
#   - Logged in to GHCR: docker login ghcr.io -u <github-user> -p <PAT>

set -euo pipefail

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
REGISTRY="ghcr.io/sajjadsaharkhan/releasewatch"

# ── Resolve image tag ─────────────────────────────────────────────────────────
IMAGE_TAG="${1:-${IMAGE_TAG:-latest}}"
export IMAGE_TAG

echo ""
echo "▶ Deploying Releasewatch — tag: ${IMAGE_TAG}"
echo ""

# ── Pull new images ───────────────────────────────────────────────────────────
echo "▶ Pulling images from GHCR..."
docker pull "${REGISTRY}/api:${IMAGE_TAG}"
docker pull "${REGISTRY}/frontend:${IMAGE_TAG}"

# ── Ensure postgres and redis are up before migrating ────────────────────────
echo "▶ Starting database services..."
$COMPOSE up -d --no-build postgres redis

echo "▶ Waiting for postgres to be healthy..."
for i in $(seq 1 30); do
  if $COMPOSE exec -T postgres pg_isready -U "${POSTGRES_USER:-rw_user}" -d "${POSTGRES_DB:-releasewatch}" > /dev/null 2>&1; then
    echo "▶ Postgres is ready ✓"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "✗ Postgres did not become healthy in 30 seconds"
    $COMPOSE logs --tail=20 postgres
    exit 1
  fi
  sleep 1
done

# ── Run database migrations ───────────────────────────────────────────────────
echo "▶ Running database migrations..."
$COMPOSE run --rm --no-deps api alembic upgrade head

# ── Start / restart all services ─────────────────────────────────────────────
echo "▶ Starting services..."
$COMPOSE up -d --no-build --remove-orphans

# ── Health check ──────────────────────────────────────────────────────────────
echo "▶ Waiting for API to become healthy..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
    echo "▶ API is healthy ✓"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo "✗ API did not become healthy in 30 seconds"
    $COMPOSE logs --tail=30 api
    exit 1
  fi
  sleep 1
done

# ── Remove dangling images ────────────────────────────────────────────────────
echo "▶ Pruning unused images..."
docker image prune -f

echo ""
echo "✓ Deployment complete — tag: ${IMAGE_TAG}"
echo ""
