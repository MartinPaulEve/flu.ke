# Fluke — fan site & CMS (flu.ke)

A fan hub for the electronic band **Fluke** (aliases: 2 Bit Pie, Lucky Monkeys,
Syntax, Yuki, Fatal). Content is edited privately in the Django admin, and the
public site is served live by the same Django app (`apps.frontend` for the pages,
`apps.api` for the read-only discography API).

## Stack
- Django 5.x, managed with [uv](https://docs.astral.sh/uv/)
- Secrets via `.env` (django-environ) — copy `.env.example` to `.env`
- Public site served live by `apps.frontend`; read-only REST API under `apps.api`

## Sections
Blog/News · Official Resources · Fan Remixes & Resources · Discography · arbitrary CMS pages

## Running the CMS with Docker (recommended)

The CMS — the private editing tool where you write posts and manage the
discography — runs as a single container (service name `cms`). This image is for
local editing; the public site is served live by Django in production (see
[Deploy](#deploy)).

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

### Preview the site
The CMS serves the public site live alongside the admin. With the container
running, browse the pages at **http://localhost:8000/** and edit content via the
admin at **http://localhost:8000/admin/** — changes are reflected immediately.

### What persists
The repository is bind-mounted into the container at `/app`, so these live on your
host and survive `docker compose down`:

| Path | Contents |
|------|----------|
| `db.sqlite3` | the CMS database (content) |
| `media/` | imported/uploaded media (covers, samples, resource files) |
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
  Your host `db.sqlite3` and `media/` are untouched.

### File ownership
The container runs as a non-root user matching your host UID/GID (default 1000), so
files it writes into the working tree (`db.sqlite3`, `media/`) are owned by you. If
your host user isn't 1000, build with `UID=$(id -u) GID=$(id -g) docker compose build`.

### Troubleshooting
- *`required variable DJANGO_SECRET_KEY is missing a value`* — set `DJANGO_SECRET_KEY`
  in `.env` (see step 1).
- *Port 8000 already in use* — set `CMS_PORT` in `.env` (e.g. `CMS_PORT=8800`) and
  restart; the admin is then at `http://localhost:8800/admin/`.
- *Admin CSS missing / 400 errors* — ensure `DJANGO_DEBUG=True` (the default) so
  runserver serves static files.

## Quick start (without Docker)
```bash
uv sync
cp .env.example .env            # then edit DJANGO_SECRET_KEY etc.
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver   # public site at /, admin at /admin/
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

## Preview the site
The same `runserver` (or the Docker `cms` container) serves the public site live at
**http://localhost:8000/**, with the admin at **/admin/**. Content edited in the
admin is reflected immediately — there is no separate build step.

## Deploy

The public site is served live by Django (`apps.frontend` + `apps.api`) in
production. Deploy with Docker — full step-by-step:
**[docs/deploy-docker.md](docs/deploy-docker.md)**.

## Licence

The project's own code is licensed under the **MIT Licence** — see
[`LICENSE`](LICENSE).

The bundled fonts under `assets/fonts/` are third-party and licensed separately
under the **SIL Open Font License 1.1** — see
[`assets/fonts/README.md`](assets/fonts/README.md). Imported band content (the
discography, archived posts and media) belongs to its respective rights holders;
this is a fan archive.
