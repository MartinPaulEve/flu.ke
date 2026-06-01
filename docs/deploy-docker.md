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
HTTP listener — there is no `:443` and no certresolver. Traefik's internal
entrypoint stays `:80`, but the **host-published** port is configurable via
`TRAEFIK_HTTP_PORT` (default **8001**). Point Pangolin at the **host on
`TRAEFIK_HTTP_PORT`**.

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

The production data lives in the host `$DATA_DIR` directory (bind-mounted into
the container), not in the repo, so on the first deploy you copy your
prepopulated `db.sqlite3` (and `media/`) straight into that directory — no
helper container needed. Create and chown the dirs first (bind mounts keep the
host's ownership, so they must be owned by the container UID/GID), take a clean
snapshot of the DB into place (this checkpoints the WAL), and copy the media:

```sh
# 1. Create the data dirs and give them to the container user (1000:1000):
mkdir -p "$DATA_DIR"/db "$DATA_DIR"/media && sudo chown -R 1000:1000 "$DATA_DIR"

# 2. A consistent snapshot of your local DB straight into place:
sqlite3 db.sqlite3 ".backup '$DATA_DIR/db/db.sqlite3'"

# 3. Media (~GBs) — copy your tree into the media dir:
rsync -a media/ "$DATA_DIR/media/"

# 4. Re-assert ownership after copying (root may have written some files):
sudo chown -R 1000:1000 "$DATA_DIR"
```

Then `up -d` as usual — the entrypoint's `migrate` is a no-op on an
already-migrated DB.

## Environment

All secrets/config come from the environment (`.env.prod`), never from the image.
Required values use compose's `${VAR:?...}` form, so the stack refuses to start if
they are missing.

| Variable | Required | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | yes | `python -c "import secrets; print(secrets.token_urlsafe(50))"`. Use a fresh key, not the dev one. |
| `SITE_BASE_URL` | yes | `https://fluke.eve.gd` for the test deploy; `https://flu.ke` for production. |
| `DATABASE_URL` | no (default) | Defaults to `sqlite:////data/db.sqlite3` — `/data` is the bind-mounted `$DATA_DIR/db`. |
| `DATA_DIR` | no (default) | Host directory for the bind-mounted DB + media. Must live **outside the repo**. Defaults to `../fluke-data` (a sibling of the repo); recommend an absolute path like `/srv/fluke-data`. Create and `chown` it to the container UID/GID before the first `up` (see Volumes). |
| `TRAEFIK_HTTP_PORT` | no (default) | Host port published to Traefik's `:80` entrypoint. Defaults to `8001`. Point Pangolin here. |
| `SITE_NAME` | no | Defaults to `Fluke`. |
| `DJANGO_ALLOWED_HOSTS` | no | Defaults to `fluke.eve.gd,flu.ke`. Django host check. |
| `CSRF_TRUSTED_ORIGINS` | no | Defaults to `https://fluke.eve.gd,https://flu.ke`. |
| `MUSICBRAINZ_CONTACT` | no | Descriptive contact for the MusicBrainz User-Agent. |
| `UID` / `GID` | no | Build args; match the host owner of the `$DATA_DIR` files (default 1000). |

`DATABASE_URL` is the database secret: it is read from the environment by
`config.settings_production` (via django-environ) and is never written into the
image. The default points at the SQLite file under `/data`, which is the
bind-mounted `$DATA_DIR/db` host directory.

## Routing

The `web` service publishes **no host ports** (`expose: ["8000"]`) — only Traefik
reaches it on the shared `web` network. Traefik itself publishes its `:80`
entrypoint on the host at `TRAEFIK_HTTP_PORT` (default **8001**); point Pangolin
at the host on that port. The Traefik labels route both hosts:

```
traefik.http.routers.fluke.rule=Host(`fluke.eve.gd`) || Host(`flu.ke`)
traefik.http.routers.fluke.entrypoints=web
traefik.http.services.fluke.loadbalancer.server.port=8000
```

Test deploy first against **fluke.eve.gd**, then switch `SITE_BASE_URL` (and, if
you narrow them, `DJANGO_ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS`) to **flu.ke**
for the production cutover. The router already accepts both hostnames.

## Volumes

All persistent state lives in **host bind mounts** of `$DATA_DIR` — a directory
**outside the git checkout** (the image is disposable). `$DATA_DIR` defaults to
`../fluke-data`, a sibling of the repo (so a repo at `/srv/fluke` defaults its
data to `/srv/fluke-data`); set it to an absolute path like `/srv/fluke-data` in
`.env.prod`.

- **`$DATA_DIR/db` → `/data`** — the SQLite database and its `-wal`/`-shm`
  sidecar files. `DATABASE_URL=sqlite:////data/db.sqlite3` keeps everything in
  this directory so it survives rebuilds.
- **`$DATA_DIR/media` → `/app/media`** — uploaded media, kept separate from the
  image.

Rebuilding (`up -d --build`) replaces the container but leaves `$DATA_DIR`
intact.

**Ownership (critical).** Unlike named volumes — which seed their ownership from
the image — bind-mounted host directories keep the **host directory's real
ownership**. The container runs as the non-root app user (UID/GID **1000** by
default, set via the build args). So you **must create the directories and
`chown` them to that UID/GID before the first `up`**, otherwise Docker
auto-creates them as `root` and `migrate` cannot write the database:

```sh
mkdir -p "$DATA_DIR"/db "$DATA_DIR"/media
sudo chown -R 1000:1000 "$DATA_DIR"     # match the UID/GID the image was built with
```

If you build with a non-default `UID`/`GID`, `chown` to those values instead.

## SQLite specifics & backup

SQLite is the production database — a single-writer site does not need more, and
backups stay trivially simple, which is the whole reason for the choice. The DB
runs in WAL mode (so `db.sqlite3-wal` / `db.sqlite3-shm` appear next to it on the
volume).

Because the data is a plain host directory now, back it up with ordinary
host-file operations. SQLite's online backup is safe while the app is running:

```sh
# Consistent DB snapshot (checkpoints the WAL) straight from the host dir:
sqlite3 "$DATA_DIR/db/db.sqlite3" ".backup '/backups/db-$(date +%F).sqlite3'"
# Media:
rsync -a "$DATA_DIR/media/" /backups/media/
```

Alternatively, stop the stack and copy the whole `$DATA_DIR` directory.

## Media & future work

Media lives in its own `$DATA_DIR/media` host directory and is currently served
by Django (the app exposes it). For the large media tree, putting a dedicated
static/media file
server in front of the app is a sensible future optimization — it would offload
those bytes from gunicorn. WhiteNoise already serves the app/admin static files
(`/static/`) from within the image, so no extra server is needed for those.
