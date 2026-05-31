# Deploying with Docker (production)

This is the production deployment for the Fluke CMS / live site. It runs the app
with **gunicorn** under `config.settings_production` (`DEBUG=False`), behind a
**Traefik** reverse proxy, which in turn sits behind **Pangolin**.

Files:

- `Dockerfile.prod` — the production image (gunicorn, not runserver).
- `compose.prod.yaml` — the Traefik + web stack.
- `docker/entrypoint.prod.sh` — migrate, collectstatic, optional admin, then exec gunicorn.
- `.env.prod.example` — the environment template (copy to `.env.prod`).

## Topology

```
Internet ──HTTPS──> Pangolin ──HTTP──> Traefik :80 ──HTTP──> web :8000 (gunicorn)
           (TLS terminated here)                              WhiteNoise serves /static/
```

**Pangolin terminates SSL** and forwards plain HTTP, so this stack only needs an
HTTP listener — there is no `:443` and no certresolver. Point Pangolin at the
**`traefik` service on port 80**.

Traefik's `web` entrypoint is configured with
`--entrypoints.web.forwardedHeaders.insecure=true`, so it trusts and passes
through Pangolin's `X-Forwarded-Proto` / `X-Forwarded-For` / `X-Forwarded-Host`
headers. That is what lets `config.settings_production`'s
`SECURE_PROXY_SSL_HEADER` see the original request as HTTPS — so secure cookies
are set and there is no redirect loop, even though the hop into the stack is
plain HTTP.

## Quick start

```sh
cp .env.prod.example .env.prod        # then edit — see "Environment" below
docker compose -f compose.prod.yaml --env-file .env.prod up -d --build
```

The image runs `migrate` and `collectstatic` on start (the entrypoint), then
launches gunicorn:

```
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 \
    --access-logfile - --error-logfile -
```

Logs go to stdout/stderr — `docker compose -f compose.prod.yaml logs -f web`.

Create the admin user with a one-off run (keeps the password out of the
long-running service environment):

```sh
docker compose -f compose.prod.yaml run --rm \
  -e DJANGO_SUPERUSER_USERNAME=admin \
  -e DJANGO_SUPERUSER_EMAIL=martin@eve.gd \
  -e DJANGO_SUPERUSER_PASSWORD='a-strong-password' \
  web true
```

## Seeding your existing data (first deploy)

The production DB lives on the `sqlite-data` volume, not in the repo, so on the
first deploy you copy your prepopulated `db.sqlite3` (and `media/`) into the
volumes. Take a clean copy of the DB first (this checkpoints the WAL), then load
it via a one-off container that mounts your local files alongside the volume:

```sh
# 1. A consistent snapshot of your local DB (run where you edit it):
sqlite3 db.sqlite3 ".backup 'seed.sqlite3'"

# 2. Copy it onto the /data volume (runs as the app user, which owns /data):
docker compose -f compose.prod.yaml run --rm --no-deps \
  -v "$PWD/seed.sqlite3:/seed/db.sqlite3:ro" \
  web sh -c "cp /seed/db.sqlite3 /data/db.sqlite3"

# 3. Media (~GBs) — copy your tree onto the media volume:
docker compose -f compose.prod.yaml run --rm --no-deps \
  -v "$PWD/media:/seed/media:ro" \
  web sh -c "cp -a /seed/media/. /app/media/"
```

Then `up -d` as usual — the entrypoint's `migrate` is a no-op on an
already-migrated DB. (For the large media tree, `rsync` straight into the
volume's host path, or `docker cp`, is faster than a copy container.)

## Environment

All secrets/config come from the environment (`.env.prod`), never from the image.
Required values use compose's `${VAR:?...}` form, so the stack refuses to start if
they are missing.

| Variable | Required | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | yes | `python -c "import secrets; print(secrets.token_urlsafe(50))"`. Use a fresh key, not the dev one. |
| `SITE_BASE_URL` | yes | `https://fluke.eve.gd` for the test deploy; `https://flu.ke` for production. |
| `DATABASE_URL` | no (default) | Defaults to `sqlite:////data/db.sqlite3` — the persistent volume. |
| `SITE_NAME` | no | Defaults to `Fluke`. |
| `DJANGO_ALLOWED_HOSTS` | no | Defaults to `fluke.eve.gd,flu.ke`. Django host check. |
| `CSRF_TRUSTED_ORIGINS` | no | Defaults to `https://fluke.eve.gd,https://flu.ke`. |
| `MUSICBRAINZ_CONTACT` | no | Descriptive contact for the MusicBrainz User-Agent. |
| `UID` / `GID` | no | Build args; match the host owner of the volume files (default 1000). |

`DATABASE_URL` is the database secret: it is read from the environment by
`config.settings_production` (via django-environ) and is never written into the
image. The default points at the SQLite file on the `/data` volume.

## Routing

The `web` service publishes **no host ports** (`expose: ["8000"]`) — only Traefik
reaches it on the shared `web` network. The Traefik labels route both hosts:

```
traefik.http.routers.fluke.rule=Host(`fluke.eve.gd`) || Host(`flu.ke`)
traefik.http.routers.fluke.entrypoints=web
traefik.http.services.fluke.loadbalancer.server.port=8000
```

Test deploy first against **fluke.eve.gd**, then switch `SITE_BASE_URL` (and, if
you narrow them, `DJANGO_ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS`) to **flu.ke**
for the production cutover. The router already accepts both hostnames.

## Volumes

Two named volumes hold all persistent state (the image is disposable):

- **`sqlite-data` → `/data`** — the SQLite database and its `-wal`/`-shm`
  sidecar files. `DATABASE_URL=sqlite:////data/db.sqlite3` keeps everything on
  this volume so it survives rebuilds.
- **`media` → `/app/media`** — uploaded media, kept separate from the image.

Rebuilding (`up -d --build`) replaces the container but leaves both volumes
intact.

## SQLite specifics & backup

SQLite is the production database — a single-writer site does not need more, and
backups stay trivially simple, which is the whole reason for the choice. The DB
runs in WAL mode (so `db.sqlite3-wal` / `db.sqlite3-shm` appear next to it on the
volume).

Back it up with SQLite's online backup, which is safe while the app is running:

```sh
docker compose -f compose.prod.yaml exec web \
  sqlite3 /data/db.sqlite3 ".backup '/data/backup.sqlite3'"
# then copy /data/backup.sqlite3 off the host (it lands on the sqlite-data volume)
```

Alternatively, stop the stack and copy the whole `sqlite-data` volume.

## Media & future work

Media lives on its own `media` volume and is currently served by Django (the
app exposes it). For the large media tree, putting a dedicated static/media file
server in front of the app is a sensible future optimization — it would offload
those bytes from gunicorn. WhiteNoise already serves the app/admin static files
(`/static/`) from within the image, so no extra server is needed for those.
