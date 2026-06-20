#!/usr/bin/env bash
# deploy.sh — pull latest images from GHCR and restart the production stack
#
# Usage:
#   ./deploy.sh                        # deploy latest tag, pull images
#   ./deploy.sh abc1234                # deploy specific git SHA tag
#   ./deploy.sh --no-pull              # restart with already-downloaded images
#   ./deploy.sh abc1234 --no-pull      # specific tag, skip pull
#   IMAGE_TAG=abc1234 ./deploy.sh
#
# Requirements on the server:
#   - Docker + Docker Compose v2
#   - .env file present (copy from .env.production.example)
#   - Logged in to GHCR: docker login ghcr.io -u <github-user> -p <PAT>

set -euo pipefail

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
REGISTRY="ghcr.io/sajjadsaharkhan/releasewatch"

# ── Parse arguments ───────────────────────────────────────────────────────────
NO_PULL=false
for arg in "$@"; do
  case "$arg" in
    --no-pull) NO_PULL=true ;;
    --*)       echo "Unknown flag: $arg"; exit 1 ;;
    *)         IMAGE_TAG="$arg" ;;
  esac
done
IMAGE_TAG="${IMAGE_TAG:-latest}"
export IMAGE_TAG

echo ""
echo "▶ Deploying Releasewatch — tag: ${IMAGE_TAG}${NO_PULL:+ (no-pull)}"
echo ""

# ── Pull new images ───────────────────────────────────────────────────────────
if [ "$NO_PULL" = false ]; then
  echo "▶ Pulling images from GHCR..."
  docker pull "${REGISTRY}/api:${IMAGE_TAG}"
  docker pull "${REGISTRY}/frontend:${IMAGE_TAG}"
else
  echo "▶ Skipping image pull (--no-pull)"
fi

# ── Stop old app containers (keep postgres + redis running for zero downtime) ─
echo "▶ Stopping old app containers..."
$COMPOSE stop api worker beat frontend 2>/dev/null || true

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
  if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
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
echo "  API:      http://localhost:8080"
echo "  Frontend: http://localhost:80"
echo ""
