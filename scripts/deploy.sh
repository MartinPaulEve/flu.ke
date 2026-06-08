#!/bin/sh
# Production redeploy for the Fluke site.
#
# Pull the latest code, build the new image, run the release tasks (migrations,
# collectstatic) once, then recreate the web container. The container start itself
# does NOT migrate — that keeps cold starts fast (e.g. scale-to-zero) — so the
# release step here is what applies migrations on deploy.
#
# Run it from anywhere on the server:  ./scripts/deploy.sh
set -e

cd "$(dirname "$0")/.."

COMPOSE="docker compose -f compose.prod.yaml --env-file .env.prod"

echo "==> Pulling latest code"
git pull --ff-only

echo "==> Building the new image"
$COMPOSE build web

echo "==> Running release tasks (migrations, collectstatic)"
$COMPOSE run --rm web release

echo "==> Starting the web container"
$COMPOSE up -d web

echo "==> Pruning dangling images"
docker image prune -f

echo "==> Done. Follow logs with: $COMPOSE logs -f web"
