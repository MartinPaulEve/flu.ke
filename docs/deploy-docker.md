# Deploying with Docker (production)

This is the production deployment for the Fluke CMS / live site. It runs the app
with **gunicorn** under `config.settings_production` (`DEBUG=False`). TLS and
routing are handled by a **separate, shared Traefik** instance that discovers this
container via Docker labels — this stack runs only gunicorn.

Files:

- `Dockerfile.prod` — the production image (gunicorn, not runserver).
- `compose.prod.yaml` — the gunicorn (`web`) service, labelled for a shared Traefik.
- `docker/entrypoint.prod.sh` — migrate, collectstatic, optional admin, then exec gunicorn.
- `.env.prod.example` — the environment template (copy to `.env.prod`).

## Topology

```
Internet ──HTTPS──> (shared) Traefik ──HTTP──> fluke-web :8000 (gunicorn)
                    (TLS terminated there)      WhiteNoise serves /static/
```

A **shared Traefik instance** (the one running your other sites) terminates TLS and
routes to this container. It discovers the container through the Docker labels on
the `web` service and reaches it over a **shared Docker network** — so this stack
publishes **no host ports**. Traefik forwards `X-Forwarded-Proto=https`, which
`config.settings_production`'s `SECURE_PROXY_SSL_HEADER` reads (secure cookies,
correct absolute URLs, no redirect loop).

**To wire it to your Traefik**, set these in `.env.prod` (or edit the labels):

- **`TRAEFIK_NETWORK`** — the Docker network your Traefik watches. It must already
  exist (created by the Traefik stack); this compose joins it as `external`.
- **`TRAEFIK_ENTRYPOINT`** — the HTTPS entrypoint name (default `websecure`).

TLS is terminated by the shared Traefik at that entrypoint, so this stack carries
**no** `tls`/`certresolver` labels. The labels route `fluke.fm` + `www.fluke.fm`,
and **301-redirect `www` to the apex** (`fluke.fm`); extend the `Host(...)` rule
(and `DJANGO_ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS`) to add more hostnames.

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

## Redeploying

To ship new code, just **pull and rebuild** — there is no `down` step (that only
adds downtime). `up -d --build` builds the new image while the old container
keeps serving, then swaps it in:

```sh
git pull
docker compose -f compose.prod.yaml --env-file .env.prod up -d --build
```

The entrypoint re-runs `migrate` and `collectstatic` automatically on the new
container, so that single command is the whole deploy. `scripts/deploy.sh` wraps
it (pull → build → recreate → prune old image layers) into `./scripts/deploy.sh`.
The code is baked into the image (immutable build), so a `git pull` is only
reflected after the rebuild — by design.

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
| `SITE_BASE_URL` | yes | The canonical origin, `https://fluke.fm`. |
| `TRAEFIK_NETWORK` | no (default) | The shared Docker network your Traefik watches (must already exist). Defaults to `traefik`. |
| `TRAEFIK_ENTRYPOINT` | no (default) | Your Traefik's HTTPS entrypoint name. Defaults to `websecure`. |
| `DATABASE_URL` | no (default) | Defaults to `sqlite:////data/db.sqlite3` — `/data` is the bind-mounted `$DATA_DIR/db`. |
| `DATA_DIR` | no (default) | Host directory for the bind-mounted DB + media. Must live **outside the repo**. Defaults to `../fluke-data` (a sibling of the repo); recommend an absolute path like `/srv/fluke-data`. Create and `chown` it to the container UID/GID before the first `up` (see Volumes). |
| `SITE_NAME` | no | Defaults to `Fluke`. |
| `DJANGO_ALLOWED_HOSTS` | no | Defaults to `fluke.fm,www.fluke.fm`. Django host check. |
| `CSRF_TRUSTED_ORIGINS` | no | Defaults to `https://fluke.fm,https://www.fluke.fm`. |
| `MUSICBRAINZ_CONTACT` | no | Descriptive contact for the MusicBrainz User-Agent. |
| `UID` / `GID` | no | Build args; match the host owner of the `$DATA_DIR` files (default 1000). |

`DATABASE_URL` is the database secret: it is read from the environment by
`config.settings_production` (via django-environ) and is never written into the
image. The default points at the SQLite file under `/data`, which is the
bind-mounted `$DATA_DIR/db` host directory.

## Routing

The `web` service publishes **no host ports** (`expose: ["8000"]`); the shared
Traefik reaches it over the **shared Docker network** (`TRAEFIK_NETWORK`, joined
as `external`) and routes by these labels:

```
traefik.enable=true
traefik.docker.network=${TRAEFIK_NETWORK:-traefik}
traefik.http.routers.fluke.rule=Host(`fluke.fm`) || Host(`www.fluke.fm`)
traefik.http.routers.fluke.entrypoints=${TRAEFIK_ENTRYPOINT:-websecure}
traefik.http.routers.fluke.middlewares=fluke-www
traefik.http.middlewares.fluke-www.redirectregex.regex=^https?://www\.fluke\.fm/(.*)
traefik.http.middlewares.fluke-www.redirectregex.replacement=https://fluke.fm/${1}
traefik.http.middlewares.fluke-www.redirectregex.permanent=true
traefik.http.services.fluke.loadbalancer.server.port=8000
```

There are no `tls`/`certresolver` labels — the shared Traefik terminates TLS at
its entrypoint. The `fluke-www` middleware 301-redirects `www.fluke.fm` to the
apex, preserving the path (in `compose.prod.yaml` the `${1}` is written `$${1}`
to survive compose's variable interpolation).

To add another hostname, extend the `Host(...)` rule (and `DJANGO_ALLOWED_HOSTS`
/ `CSRF_TRUSTED_ORIGINS`). The shared Traefik handles certificates, so nothing
cert-related lives in this stack.

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
