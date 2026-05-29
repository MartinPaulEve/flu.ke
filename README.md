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

## Build & deploy the static site
```bash
uv run python manage.py build_site        # writes dist/
./scripts/deploy.sh                        # rsync / object-storage sync
```
