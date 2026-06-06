# Migrating from SQLite to PostgreSQL

The Fluke site ships on **SQLite** — it is simple, fast for this read-mostly
workload, and trivial to back up (one file). Move to **PostgreSQL** when you need
higher write concurrency, a managed/replicated database, or to run several app
instances against one database.

Django is database-agnostic, so the move is mechanical: install the driver, point
`DATABASE_URL` at Postgres, create the schema with `migrate`, then load the data
you dumped from SQLite. **Nothing in the application code changes.** Uploaded
media lives on disk (not in the database), so it is copied separately.

> Do a full dry run against a throwaway Postgres (a local container is fine)
> before the real cutover, and keep the SQLite file as your rollback.

---

## 1. Install the PostgreSQL driver

A `postgres` extra is already defined in `pyproject.toml` (psycopg 3, which
Django 5.x prefers):

```bash
uv sync --extra postgres          # local
# or, ad hoc:  uv add "psycopg[binary]>=3.1"
```

For the Docker image, install it in the build by adding the extra to the prod
dependency install in `Dockerfile.prod` (e.g. `uv sync --extra prod --extra
postgres`), then rebuild.

No settings change is needed: `config/settings.py` reads the database from
`DATABASE_URL` via django-environ, and the SQLite-specific tuning in
`config/settings_production.py` is guarded by `"sqlite" in ENGINE`, so it is
skipped automatically for Postgres.

## 2. Provision the database

**Managed/external Postgres** (recommended for production): create a UTF-8
database and a role, and note the connection URL. Then skip to step 3.

```sql
CREATE ROLE fluke WITH LOGIN PASSWORD 'a-strong-password';
CREATE DATABASE fluke WITH OWNER fluke ENCODING 'UTF8' TEMPLATE template0;
```

**Self-hosted alongside the app (optional):** add a `db` service to
`compose.prod.yaml` and point the web service at it. Minimal sketch:

```yaml
services:
  db:
    image: postgres:17
    environment:
      POSTGRES_DB: fluke
      POSTGRES_USER: fluke
      POSTGRES_PASSWORD: "${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD in .env.prod}"
    volumes:
      - "${DATA_DIR:-../fluke-data}/postgres:/var/lib/postgresql/data"
    restart: unless-stopped

  web:
    # ...existing config...
    environment:
      DATABASE_URL: "postgres://fluke:${POSTGRES_PASSWORD}@db:5432/fluke"
    depends_on:
      - db
```

(As with the DB/media bind mounts, `chown` `$DATA_DIR/postgres` appropriately —
the official image runs as its own `postgres` user.)

## 3. Dump the data from SQLite

With the app **still on SQLite** (do not change `DATABASE_URL` yet):

```bash
uv run python manage.py dumpdata \
  --natural-foreign --natural-primary \
  --exclude contenttypes --exclude auth.permission \
  --exclude admin.logentry --exclude sessions.session \
  --indent 2 --output dump.json
```

- `--natural-foreign/--natural-primary` serialise content-type and other
  references by natural key, so they resolve cleanly in the fresh database.
- `contenttypes` and `auth.permission` are **recreated by `migrate`**, so they are
  excluded to avoid primary-key clashes. `admin.logentry` (admin history) and
  `sessions.session` (transient) are dropped — remove those `--exclude`s if you
  specifically want to keep them.

## 4. Create the schema and load the data

Point at Postgres and run migrations against the **empty** database, then load:

```bash
export DATABASE_URL='postgres://fluke:a-strong-password@HOST:5432/fluke'

uv run python manage.py migrate            # builds the schema (+ contenttypes/permissions)
uv run python manage.py loaddata dump.json # loads your content
```

Order matters: `migrate` first (empty DB → schema), then `loaddata`. `loaddata`
resets the Postgres sequences for the loaded models automatically, so new inserts
get correct IDs. If you ever see a duplicate-key error on a *new* insert
afterwards, reset sequences manually:

```bash
uv run python manage.py sqlsequencereset discography blog resources pages | uv run python manage.py dbshell
```

## 5. Copy the media

`dumpdata` stores only file *paths*, not the files. Copy the media tree to the
new host's `MEDIA_ROOT` (in Docker that is the bind-mounted `$DATA_DIR/media`):

```bash
rsync -a media/ user@newhost:/srv/fluke-data/media/
```

## 6. Verify, then cut over

```bash
uv run python manage.py check
uv run python manage.py shell -c "from apps.discography.models import Release, Edition, Track; print(Release.objects.count(), Edition.objects.count(), Track.objects.count())"
```

Confirm the counts match the SQLite database, browse the site (discography,
news, resources, a lyric page, the API at `/discography/api/`), and create a
test login. When satisfied, set `DATABASE_URL` permanently:

- **Docker:** put the `postgres://…` URL in `.env.prod` and redeploy
  (`./scripts/deploy.sh`). The entrypoint runs `migrate` on start, which is a
  no-op once the schema exists.
- **Local/other:** set `DATABASE_URL` in `.env`.

Keep the SQLite file (and `dump.json`) until you are confident — switching back is
just restoring `DATABASE_URL=sqlite:////data/db.sqlite3`.

---

## Notes

- **Encoding:** create the database as UTF-8 (`template0` + `ENCODING 'UTF8'`);
  lyrics and posts contain arbitrary Unicode.
- **URL scheme:** django-environ accepts both `postgres://` and `postgresql://`.
- **Backups change:** instead of copying one file, use `pg_dump`
  (`pg_dump "$DATABASE_URL" > fluke-$(date +%F).sql`) on a schedule.
- **Tests** stay on SQLite (`config.settings`) unless you set `DATABASE_URL` in
  the test environment — no change required.
