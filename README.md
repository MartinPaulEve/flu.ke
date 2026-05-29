# Fluke — fan site & CMS (flu.ke)

A statically-generated fan hub for the electronic band **Fluke** (aliases: 2 Bit Pie,
Lucky Monkeys, Syntax, Yuki, Fatal). Content is edited privately in a Django CMS and
rendered to static HTML + media for public hosting, so the public site has no live
application or database to attack.

## Stack
- Django 5.x, managed with [uv](https://docs.astral.sh/uv/)
- Secrets via `.env` (django-environ) — copy `.env.example` to `.env`
- Static export via `manage.py build_site` → `dist/`

## Sections
Blog/News · Official Resources · Fan Remixes & Resources · Discography · arbitrary CMS pages

## Running the CMS with Docker (recommended)

The CMS — the private editing tool where you write posts, manage the discography
and generate the static site — runs as a single container (service name `cms`).
It is **not** the public website: the public site is the static files in `dist/`,
which you deploy separately (see [Deploy](#deploy)).

### Prerequisites
- Docker Engine + the Compose plugin (`docker compose version`).
- This repository checked out. The legacy archive (`Ingest/`) only needs to be
  present if you intend to run the one-off content imports.

### 1. First-time setup
```bash
cp .env.example .env
# Generate a secret key and put it in .env as DJANGO_SECRET_KEY=...
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```
`DJANGO_SECRET_KEY` is **required** — Compose refuses to start without it. Edit
`.env` and paste the generated value.

### 2. Start the CMS
```bash
docker compose up --build          # foreground (Ctrl-C to stop)
# or detached:
docker compose up --build -d
```
The first run builds the image and applies migrations automatically. The admin is
then available at **http://localhost:8000/admin/** — bound to loopback only, so it
is never exposed on your network.

### 3. Create your admin login
```bash
docker compose exec cms python manage.py createsuperuser
```

### Everyday commands
Run any management command inside the container with `docker compose exec cms …`
(the server must be running) or `docker compose run --rm cms …` (one-off, no server
needed):
```bash
docker compose logs -f cms                                 # follow server logs
docker compose exec cms python manage.py build_site        # generate the static site -> ./dist
docker compose exec cms python manage.py shell             # Django shell
docker compose restart cms                                 # restart the server
docker compose down                                        # stop and remove the container
```

### One-off content import (from the archived old site in `Ingest/`)
```bash
docker compose exec cms python manage.py import_discography
docker compose exec cms python manage.py import_media --dry-run   # preview the mapping
docker compose exec cms python manage.py import_media             # ~10 GB; copies into ./media
docker compose exec cms python manage.py import_blog              # best-effort, via the Wayback Machine
```

### Generate and preview the static site
`build_site` writes to `./dist` on your host (the bind mount makes it appear
outside the container). You can also click **Publish now** on the admin's
*Build state* screen, which runs the same build. Preview the output with any static
server, e.g.:
```bash
docker compose exec cms python manage.py build_site
python3 -m http.server -d dist 8080        # preview at http://localhost:8080
```

### What persists
The repository is bind-mounted into the container at `/app`, so these live on your
host and survive `docker compose down`:

| Path | Contents |
|------|----------|
| `db.sqlite3` | the CMS database (content, build state) |
| `media/` | imported/uploaded media (covers, samples, resource files) |
| `dist/` | the generated static site — this is what you deploy |
| `Ingest/` | the read source for the import commands |

The Python virtualenv lives inside the image (at `/opt/venv`) plus a `venv-cache`
named volume, so it is isolated from your host.

### Configuration
Compose reads `.env` for these (all optional except the secret key):

| Variable | Default | Purpose |
|----------|---------|---------|
| `DJANGO_SECRET_KEY` | *(required)* | Django secret key |
| `DJANGO_DEBUG` | `True` | On for local editing (serves static/media). Loopback-only. |
| `SITE_NAME` | `Fluke` | Site name used in templates/feeds |
| `SITE_BASE_URL` | `https://flu.ke` | Absolute URL base for OG tags, sitemap, feed |
| `MUSICBRAINZ_CONTACT` | *(empty)* | Contact email required by `musicbrainz_sync` |

### Maintenance
- **Changed dependencies** (`pyproject.toml` / `uv.lock`): rebuild the image with
  `docker compose build` — dependencies are baked in at build time.
- **Run the test suite** in the container: `docker compose run --rm cms uv run pytest`.
- **Full cleanup** (also removes the cached venv volume): `docker compose down -v`.
  Your host `db.sqlite3`, `media/` and `dist/` are untouched.

### Troubleshooting
- *`required variable DJANGO_SECRET_KEY is missing a value`* — set `DJANGO_SECRET_KEY`
  in `.env` (see step 1).
- *Port 8000 already in use* — stop the other process, or change the published port
  in `compose.yaml` (`"127.0.0.1:8001:8000"`).
- *Admin CSS missing / 400 errors* — ensure `DJANGO_DEBUG=True` (the default) so
  runserver serves static files.

## Quick start (without Docker)
```bash
uv sync
cp .env.example .env            # then edit DJANGO_SECRET_KEY etc.
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver   # editing CMS (admin) at /admin/
```

## Tests
```bash
uv run pytest
```

## Content import (one-off, from the archived old site under `Ingest/`)
```bash
uv run python manage.py import_discography
uv run python manage.py import_media --dry-run    # then without --dry-run
uv run python manage.py import_blog               # best-effort from the Wayback Machine
```

## Build & preview the static site
```bash
uv run python manage.py build_site         # writes dist/ (incremental; --full / --clean)
uv run python -m http.server -d dist 8000  # preview at http://localhost:8000
```
You can also publish from the admin: the **Build state** screen shows an
"Unpublished changes" banner and a **Publish now** button that rebuilds `dist/`.

## Deploy

**Option A — edit locally, push the static output.** The public site is just the
files in `dist/`. Configure `DEPLOY_*` in `.env`, then:
```bash
bash scripts/deploy.sh
```
Targets: `rsync` (to an nginx box — see `scripts/nginx-flu.ke.conf` for MIME types
and cache headers), `s3` (S3 / Cloudflare R2 / Backblaze B2), or `rclone`. The host
must serve large files, since the full ~10 GB media library is part of the output —
use object storage or a plain web server, not a size-limited PaaS.

**Option B — run the CMS on a web server (e.g. Reclaim Hosting / cPanel).** Host the
Django CMS on a subdomain (`cms.flu.ke`) that generates straight into the document
root of `flu.ke`. The CMS serves its own admin static via WhiteNoise; set
`DJANGO_DEBUG=False`, `DJANGO_SECURE=True`, and the build/media paths via env. Full
step-by-step: **[docs/deploy-reclaim.md](docs/deploy-reclaim.md)**.
