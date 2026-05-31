#!/bin/sh
# Production container start-up. Apply migrations, refresh the collected static
# files (WhiteNoise serves them), optionally ensure an admin user, then hand off
# to the given command (gunicorn by default — see Dockerfile.prod CMD).
#
# Runs under DJANGO_SETTINGS_MODULE=config.settings_production (set in the image),
# with DEBUG=False. Secrets (DJANGO_SECRET_KEY, DATABASE_URL, …) come from the
# environment — never baked into the image.
set -e

echo "==> Applying database migrations"
python manage.py migrate --noinput

# Idempotent: also done at build time, but re-run here so a mounted/empty
# STATIC_ROOT (e.g. after a volume change) is always populated for WhiteNoise.
echo "==> Collecting static files"
python manage.py collectstatic --noinput

# Optional one-shot admin creation. Only when an operator explicitly supplies
# BOTH variables (e.g. a single `docker compose -f compose.prod.yaml run \
# -e DJANGO_SUPERUSER_USERNAME=admin -e DJANGO_SUPERUSER_PASSWORD=… web`).
# A password is NEVER baked into the image — it must come from the environment
# at run time. Skips cleanly if the user already exists; any other failure
# aborts (set -e) rather than being silently swallowed.
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  if python manage.py shell -c "import os, sys; from django.contrib.auth import get_user_model as g; sys.exit(0 if g().objects.filter(username=os.environ['DJANGO_SUPERUSER_USERNAME']).exists() else 1)"; then
    echo "==> Superuser '${DJANGO_SUPERUSER_USERNAME}' already exists; skipping"
  else
    echo "==> Creating superuser '${DJANGO_SUPERUSER_USERNAME}'"
    python manage.py createsuperuser --noinput
  fi
fi

exec "$@"
