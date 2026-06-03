#!/bin/sh
# Production redeploy for the Fluke site.
#
# Pull the latest code, rebuild the image and recreate the web container (the old
# container keeps serving until the new one is ready, so downtime is just the
# few-second swap — no full `down`), then drop the now-dangling old image layers.
#
# Run it from anywhere on the server:  ./scripts/deploy.sh
set -e

cd "$(dirname "$0")/.."

COMPOSE="docker compose -f compose.prod.yaml --env-file .env.prod"

echo "==> Pulling latest code"
git pull --ff-only

echo "==> Rebuilding and recreating the web container"
$COMPOSE up -d --build

echo "==> Pruning dangling images"
docker image prune -f

echo "==> Done. Follow logs with: $COMPOSE logs -f web"
