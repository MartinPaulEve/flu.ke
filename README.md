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

## Quick start
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
The public site is just the files in `dist/`. Configure `DEPLOY_*` in `.env`, then:
```bash
bash scripts/deploy.sh
```
Targets: `rsync` (to an nginx box — see `scripts/nginx-flu.ke.conf` for MIME types
and cache headers), `s3` (S3 / Cloudflare R2 / Backblaze B2), or `rclone`. The host
must serve large files, since the full ~10 GB media library is part of the output —
use object storage or a plain web server, not a size-limited PaaS.
