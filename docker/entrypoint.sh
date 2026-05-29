#!/bin/sh
# Prepare the CMS on container start: apply migrations and (optionally) ensure an
# admin user, then run the given command (runserver by default).
set -e

echo "==> Applying database migrations"
python manage.py migrate --noinput

if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  echo "==> Ensuring superuser '${DJANGO_SUPERUSER_USERNAME}'"
  # createsuperuser --noinput reads DJANGO_SUPERUSER_* env; ignore "already exists".
  python manage.py createsuperuser --noinput 2>/dev/null || true
fi

exec "$@"
