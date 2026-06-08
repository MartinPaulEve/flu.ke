#!/bin/sh
# Production container start-up.
#
# Release tasks (migrations, collectstatic, optional admin) are NOT run on every
# start — that would slow every cold start (e.g. a scale-to-zero wake-up). Run
# them once per deploy with a one-shot:
#
#     docker compose run --rm web release
#
# (or set RUN_RELEASE_TASKS=1 for a single normal start). A plain start just execs
# the command (gunicorn), so boots are fast.
#
# Runs under DJANGO_SETTINGS_MODULE=config.settings_production (set in the image),
# DEBUG=False. Secrets (DJANGO_SECRET_KEY, DATABASE_URL, …) come from the
# environment — never baked into the image.
set -e

run_release_tasks() {
  echo "==> Applying database migrations"
  python manage.py migrate --noinput

  # Idempotent: also done at build time, but re-run here so a mounted/empty
  # STATIC_ROOT (e.g. after a volume change) is always populated for WhiteNoise.
  echo "==> Collecting static files"
  python manage.py collectstatic --noinput

  # Optional one-shot admin creation. Only when an operator explicitly supplies
  # BOTH variables. A password is NEVER baked into the image. Skips cleanly if the
  # user already exists; any other failure aborts (set -e).
  if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    if python manage.py shell -c "import os, sys; from django.contrib.auth import get_user_model as g; sys.exit(0 if g().objects.filter(username=os.environ['DJANGO_SUPERUSER_USERNAME']).exists() else 1)"; then
      echo "==> Superuser '${DJANGO_SUPERUSER_USERNAME}' already exists; skipping"
    else
      echo "==> Creating superuser '${DJANGO_SUPERUSER_USERNAME}'"
      python manage.py createsuperuser --noinput
    fi
  fi
}

# Deploy one-shot:  docker compose run --rm web release
if [ "$1" = "release" ]; then
  run_release_tasks
  exit 0
fi

# Opt-in on a normal start (e.g. a deploy via `up` rather than `run`).
case "${RUN_RELEASE_TASKS:-}" in
  1 | true | TRUE | yes) run_release_tasks ;;
esac

# Fast path: just run the given command (gunicorn) — no migrations on boot.
exec "$@"
