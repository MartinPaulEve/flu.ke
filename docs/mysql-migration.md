# Migrating the CMS from SQLite to MySQL

The Fluke CMS ships on **SQLite** (`db.sqlite3`), which suits a single editor and
the static-generation workflow. This runbook moves the data to **MySQL / MariaDB**
when you outgrow that — without changing the default. SQLite stays the default in
`config/settings.py`; MySQL is selected purely by pointing `DATABASE_URL` at it.

Everything here is reversible: keep the SQLite file until you have verified the
MySQL copy.

---

## What's already wired up

- **Driver (optional):** `mysqlclient` is declared as an optional extra in
  `pyproject.toml` (`[project.optional-dependencies].mysql`). It is **not** in the
  base environment because it needs system build headers and isn't used with
  SQLite. Install it only on the MySQL host (§2).
- **utf8mb4 automatically:** `config/settings.py` detects a MySQL engine and sets
  the connection `charset` to `utf8mb4` (full Unicode for lyrics and post bodies),
  plus a utf8mb4 test database. No-op on SQLite.
- **Local dry-run service:** `compose.yaml` has an optional `db` (MariaDB 11)
  service behind the `mysql` profile, so it never starts with a plain
  `docker compose up` (§7).

## Requirements

- **MySQL 5.7+ or MariaDB 10.2+.** The schema has unique `VARCHAR(200)` slug
  indexes; these rely on the large index-prefix default (`innodb_large_prefix`,
  on by default in those versions) so a 200-char utf8mb4 column can be uniquely
  indexed. Older servers will reject the index.
- System build headers for the driver: `default-libmysqlclient-dev`
  (Debian/Ubuntu) or `mysql-devel` (RHEL), plus a C compiler and `pkg-config`.

---

## 1. Create the database as utf8mb4

On the MySQL/MariaDB server:

```sql
CREATE DATABASE fluke CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'fluke'@'%' IDENTIFIED BY 'a-strong-password';
GRANT ALL PRIVILEGES ON fluke.* TO 'fluke'@'%';
FLUSH PRIVILEGES;
```

Creating the database as utf8mb4 means the tables Django creates inherit it.

## 2. Install the driver

On the MySQL host (with the build headers above installed):

```bash
uv sync --extra mysql
```

This adds `mysqlclient` to the environment. (Resolution is already pinned in
`uv.lock`.)

## 3. Dump the data from SQLite

Run this **against the current SQLite database** (i.e. with `DATABASE_URL` still
pointing at SQLite, or unset so the default applies). Natural keys make the dump
portable across databases, and we exclude tables that `migrate` re-creates on the
target:

```bash
uv run python manage.py dumpdata --natural-foreign --natural-primary \
  --exclude contenttypes --exclude auth.permission \
  --exclude admin.logentry --exclude sessions.session \
  --indent 2 -o dump.json
```

- `--natural-foreign --natural-primary` — reference rows by natural key instead of
  by integer PK, so foreign keys still line up after the import.
- `--exclude contenttypes --exclude auth.permission` — `migrate` creates these on
  the target; dumping them causes duplicate-key clashes on load.
- `--exclude admin.logentry --exclude sessions.session` — disposable history /
  session rows; no need to carry them over.

## 4. Load into MySQL

Point `DATABASE_URL` at the new database, create the schema, then load the dump:

```bash
export DATABASE_URL="mysql://fluke:a-strong-password@HOST:3306/fluke"

uv run python manage.py migrate        # creates schema + contenttype/permission rows
uv run python manage.py loaddata dump.json
```

`migrate` builds the schema and the `contenttypes` / `auth.permission` rows we
excluded from the dump; `loaddata` then brings in all the real content.

- **AUTO_INCREMENT self-corrects.** On InnoDB the table's `AUTO_INCREMENT` counter
  advances past the highest inserted id automatically after `loaddata`, so there
  is **no** sequence-reset step (unlike Postgres' `sqlsequencereset`).

## 5. Copy the media tree separately

`dumpdata` stores only the **file paths** for covers, audio samples, OG images and
resource files — **not** the files themselves. The `media/` tree is ~10 GB and
must be copied independently of the database dump:

```bash
rsync -a media/ user@host:/path/to/media/
```

Make sure the destination matches the target's `MEDIA_ROOT` (see
`docs/deploy-docker.md` for how media is mounted on the host).

## 6. Point the live host at MySQL

Set `DATABASE_URL=mysql://fluke:...@HOST:3306/fluke` in the host's environment /
`.env` (see `.env.example`). utf8mb4 is applied automatically. Restart the app
(for cPanel/Passenger: `touch tmp/restart.txt`), then run the verification in §8.

---

## 7. Local Docker dry-run (do this first)

Rehearse the whole move locally against the optional `db` service before touching
the live host. Set `MYSQL_DATABASE`, `MYSQL_USER`, `MYSQL_PASSWORD` and
`MYSQL_ROOT_PASSWORD` in `.env` (see `.env.example`), then:

```bash
# 1. Start the dry-run MySQL (behind the `mysql` profile; SQLite stays the default).
docker compose --profile mysql up -d db        # or: docker compose up -d db

# 2. Dump from the SQLite copy (cms still uses SQLite by default).
docker compose run --rm cms python manage.py dumpdata --natural-foreign \
  --natural-primary --exclude contenttypes --exclude auth.permission \
  --exclude admin.logentry --exclude sessions.session --indent 2 -o dump.json

# 3. Migrate + load against the db service (host `db` inside the compose network).
DB_URL="mysql://${MYSQL_USER}:${MYSQL_PASSWORD}@db:3306/${MYSQL_DATABASE}"
docker compose run --rm -e DATABASE_URL="$DB_URL" cms python manage.py migrate
docker compose run --rm -e DATABASE_URL="$DB_URL" cms python manage.py loaddata dump.json

# 4. Run the test suite against MySQL (creates a utf8mb4 test database).
docker compose run --rm -e DATABASE_URL="$DB_URL" cms python -m pytest

# 5. Browse the site / admin against MySQL.
docker compose run --rm -e DATABASE_URL="$DB_URL" -p 127.0.0.1:8000:8000 \
  cms python manage.py runserver 0.0.0.0:8000
```

The `db` service stores its data in the `mysql-data` named volume and is bound to
loopback only. Tear it down with `docker compose --profile mysql down` (add `-v`
to also drop the volume and start fresh).

## 8. Verification checklist

After loading (locally in §7, and again on the live host):

- **Row counts match.** Compare a few key models between the old SQLite database
  and the new MySQL one, e.g.:
  ```bash
  uv run python manage.py shell -c "from apps.discography.models import Release; print(Release.objects.count())"
  ```
  Run the same against SQLite (`DATABASE_URL=sqlite:///db.sqlite3`) and confirm the
  numbers agree across the main content models (releases, tracks, blog posts,
  resources, pages).
- **Spot-check a page.** Load a release/discography page and a blog post in the
  browser; confirm Unicode (smart quotes, accented names, emoji in lyrics) renders
  correctly — this proves utf8mb4 took effect.
- **Spot-check the API.** Hit a read-only API endpoint, e.g.
  `GET /discography/api/` (the discography REST API), and confirm it returns the
  expected JSON.
- **Media resolves.** Confirm a cover image and a resource file load (these come
  from the separately-rsynced `media/` tree, not the database).
- **Tests pass** against MySQL (`pytest`), as run in §7 step 4.

Once verified on the live host, keep the SQLite file as a backup until you're
confident, then archive it.
```
