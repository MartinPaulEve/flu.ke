#!/bin/sh
# Prepare the CMS on container start: apply migrations and (optionally) ensure an
# admin user, then run the given command (runserver by default).
set -e

echo "==> Applying database migrations"
python manage.py migrate --noinput

# Only when an operator explicitly supplies both (e.g. a one-shot
# `docker compose run -e DJANGO_SUPERUSER_PASSWORD=... cms`). Skips cleanly if the
# user already exists; any other failure is shown and aborts (set -e), rather than
# being silently swallowed.
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  if python manage.py shell -c "import os, sys; from django.contrib.auth import get_user_model as g; sys.exit(0 if g().objects.filter(username=os.environ['DJANGO_SUPERUSER_USERNAME']).exists() else 1)"; then
    echo "==> Superuser '${DJANGO_SUPERUSER_USERNAME}' already exists; skipping"
  else
    echo "==> Creating superuser '${DJANGO_SUPERUSER_USERNAME}'"
    python manage.py createsuperuser --noinput
  fi
fi

exec "$@"
