# Fluke — CMS & live fan site (flu.ke)

A Django 5.2 content-management system and public website for the **Fluke** fan
archive at [flu.ke](https://flu.ke). Fluke is an electronic band that has also
recorded as **2 Bit Pie**, **Lucky Monkeys**, **Syntax**, **Yuki** and **Fatal**.

Content is written privately in the Django admin; the public site is rendered
**live** by the same Django app. There is **no static build step** — pages are
served straight from the database by `apps.frontend`, so anything you change in
the admin appears on the site immediately. The project is managed with
[uv](https://docs.astral.sh/uv/).

## What it provides

- **Public site** — landing page, news/blog, discography, lyrics, fan/official
  resources and arbitrary CMS pages, served live by `apps.frontend`
  (views + URLs). Plus `sitemap.xml`, an Atom-style `feed.xml` and `robots.txt`.
- **Read-only discography REST API** under `/discography/api/` (Django REST
  Framework): artists, release types, releases, editions, tracks, lyrics and
  cover art. Interactive docs via Swagger UI at `/discography/api/docs/`, ReDoc
  at `/discography/api/redoc/`, and the raw OpenAPI schema at
  `/discography/api/schema/` (drf-spectacular).
- **Admin** at `/admin/` for private editing, with a self-hosted TinyMCE
  rich-text editor.

## Architecture

The database is **SQLite** in both development and production. (There is no
MySQL.) Production applies SQLite tuning for a concurrent web workload — WAL
journaling, `synchronous=NORMAL`, a busy timeout and `IMMEDIATE` transactions —
in `config.settings_production`.

Django apps:

| App | Responsibility |
|---|---|
| `apps.core` | Shared helpers: SEO/Open Graph, text utilities, the site context processor, base admin. |
| `apps.pages` | Arbitrary CMS pages (the `/<slug>/` catch-all). |
| `apps.blog` | News/blog posts, categories, OG-image generation. |
| `apps.resources` | Official and fan resources (downloads, links), grouped by kind. |
| `apps.discography` | Artists, release types, releases, editions, tracks, lyrics, cover art; the import/MusicBrainz logic. |
| `apps.importers` | One-off recovery of content from the archived old site (Wayback Machine helpers). |
| `apps.frontend` | The live public site — views, URLs, feed and sitemaps. |
| `apps.api` | The read-only DRF discography API and its OpenAPI docs. |

Settings live in `config/settings.py` (base) and `config/settings_production.py`
(production overrides). The URL root is `config/urls.py`.

## Local development

```bash
uv sync
cp .env.example .env                       # then edit DJANGO_SECRET_KEY etc.
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver          # public site at /, admin at /admin/
```

The public site is then at <http://127.0.0.1:8000/> and the admin at
<http://127.0.0.1:8000/admin/>. Edits in the admin show up on the site
immediately — there is no separate build or publish step.

### Docker (development)

A single-container dev option is provided via `compose.yaml` (service name
`cms`). It bind-mounts the repo, runs `runserver`, applies migrations on first
start, and binds to loopback only so it is never exposed on your LAN.

```bash
cp .env.example .env
# DJANGO_SECRET_KEY is required — Compose refuses to start without it. Generate one:
uv run python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"

docker compose up --build                  # admin at http://localhost:8000/admin/
docker compose exec cms python manage.py createsuperuser
```

`db.sqlite3`, `media/` and `Ingest/` persist on the host (the repo is mounted at
`/app`). Set `CMS_PORT` in `.env` if port 8000 is already taken on your machine.

## Testing and linting

This is a test-driven project.

```bash
uv run pytest             # run the test suite (config: tests/, settings config.settings)
uv run ruff check .       # lint
```

## Content import (one-off)

The site was reconstructed from an archived snapshot of the old site, kept in
`Ingest/` (only needed when running these imports). All commands are idempotent
and re-runnable; run them with `uv run python manage.py <command>` (or
`docker compose exec cms python manage.py <command>` in the Docker dev container).

| Command | App | What it does |
|---|---|---|
| `import_discography` | discography | Parses the archived `discography.html` snapshot and creates artists, releases, editions and tracks (and lyric stubs). Supports `--file` and `--dry-run`. |
| `import_media` | discography | Matches the legacy `Files/` media tree to covers and tracks, copies the files under `MEDIA_ROOT` and wires up the FileFields; leftover audio/archive/video become catalogued resources. Supports `--dry-run` to preview the mapping (the full copy is roughly 10 GB). |
| `import_lyrics` | discography | Backfills empty lyric bodies for imported songs by recovering the archived lyric pages from the Web Archive. Skips lyrics that already have a body unless `--force`; rate-limited and polite. |
| `import_blog` | importers | Best-effort recovery of blog posts from the Wayback Machine (CDX API). Never overwrites hand-edited posts; complete recoveries are published, partial ones left as drafts. |
| `import_loose_archives` | resources | Surfaces the legacy album/live-set/remix archives as published, downloadable resources, dedupes archive resources pointing at the same file, and excludes the large site-backup zips. |

A `musicbrainz_sync` command (discography) can enrich the discography from
MusicBrainz by artist MBID. It is built for future use — the archived snapshot
remains the primary source — and requires `MUSICBRAINZ_CONTACT` to be set (it
honours MusicBrainz's descriptive User-Agent and 1 request/second rate limit).

## Production deployment

Production runs the app with **gunicorn** under `config.settings_production`
(`DEBUG=False`) inside Docker, behind a **Traefik** reverse proxy, which in turn
sits behind **Pangolin** (Pangolin terminates TLS and forwards plain HTTP). The
database is **SQLite** on a host bind-mount (`$DATA_DIR`), and uploaded media
lives alongside it. The host-published Traefik port is configurable via
`TRAEFIK_HTTP_PORT` (default **8001**); point Pangolin there.

```bash
cp .env.prod.example .env.prod             # then edit — see the deploy guide
docker compose -f compose.prod.yaml --env-file .env.prod up -d --build
```

The full step-by-step (topology, first-deploy data seeding, volumes/ownership,
SQLite backup) is in **[docs/deploy-docker.md](docs/deploy-docker.md)** —
the canonical reference; this section is just an overview.

## Configuration

Settings are read from the environment / a `.env` file via django-environ;
secrets are never hard-coded. Copy `.env.example` (development) or
`.env.prod.example` (production) and fill in the values.

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | dev fallback; **required** in production | Django secret key. Production refuses to boot with the insecure dev default. |
| `DJANGO_DEBUG` | `False` (`True` for local editing) | Debug mode. Forced off in `config.settings_production`. |
| `DJANGO_ALLOWED_HOSTS` | `127.0.0.1,localhost` | Comma-separated allowed hosts. |
| `DJANGO_SECURE` | `False` | Enables the HTTPS/HSTS/secure-cookie hardening in the base settings. |
| `CSRF_TRUSTED_ORIGINS` | _(empty)_ | Comma-separated trusted CSRF origins. |
| `DATABASE_URL` | `sqlite:///db.sqlite3` | Database URL (SQLite everywhere). |
| `SITE_BASE_URL` | `https://flu.ke` | Canonical origin for absolute URLs, OG images, sitemap and feed. |
| `SITE_NAME` | `Fluke` | Site name used in templates and feeds. |
| `MEDIA_ROOT` | `media` | Directory holding uploaded media. |
| `MEDIA_URL` | `/media/` | URL prefix for media. |
| `MUSICBRAINZ_APP` | `flukecms` | MusicBrainz client app name. |
| `MUSICBRAINZ_VERSION` | `1.0` | MusicBrainz client version. |
| `MUSICBRAINZ_CONTACT` | _(empty)_ | Contact email for the MusicBrainz User-Agent; required by `musicbrainz_sync`. |

Production additionally uses `DATA_DIR`, `TRAEFIK_HTTP_PORT` and optional
`UID`/`GID` build args — see [docs/deploy-docker.md](docs/deploy-docker.md).

## Licence

The project's own code is licensed under the **MIT Licence** — see
[`LICENSE`](LICENSE).

The bundled fonts under `assets/fonts/` are third-party and licensed separately
under the **SIL Open Font License 1.1** — see
[`assets/fonts/README.md`](assets/fonts/README.md). Imported band content (the
discography, archived posts and media) belongs to its respective rights holders;
this is a fan archive.
</content>
</invoke>
