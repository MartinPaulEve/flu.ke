# Backing up the database

The site runs on **SQLite** in production (a single-writer site needs nothing
more, and it makes backups trivial). There are two things to back up:

| What | Production path (host) | Notes |
| --- | --- | --- |
| The database | `$DATA_DIR/db/db.sqlite3` (+ `-wal`, `-shm`) | One file. Runs in WAL mode. |
| Uploaded media | `$DATA_DIR/media/` | Covers, samples, resource files, blog images, generated OG cards. |

`$DATA_DIR` is the host data directory bind-mounted into the container (default a
sibling of the repo, e.g. `/srv/fluke-data`; see
[docs/deploy-docker.md](docs/deploy-docker.md)). Locally (no Docker) the database
is `db.sqlite3` in the repo root and media is `media/`.

> **Don't just `cp` the live `.sqlite3` file.** In WAL mode a plain copy taken
> mid-write can be inconsistent (the latest commits live in the `-wal` file).
> Use SQLite's online backup, which produces a single consistent snapshot and is
> safe while the app is running.

## Recommended: SQLite online backup

This is safe with the app running — it checkpoints the WAL into the copy.

```sh
# On the host (sqlite3 installed there):
DATA_DIR=/srv/fluke-data                 # adjust to your deployment
STAMP=$(date +%F-%H%M)
mkdir -p /backups

sqlite3 "$DATA_DIR/db/db.sqlite3" ".backup '/backups/fluke-db-$STAMP.sqlite3'"
rsync -a --delete "$DATA_DIR/media/" "/backups/media/"

# Optional: compress the DB snapshot
gzip -f "/backups/fluke-db-$STAMP.sqlite3"
```

The result is one self-contained `.sqlite3` (or `.sqlite3.gz`) file plus a media
mirror. Copy them somewhere off the box (see [Off-site](#off-site--retention)).

### If `sqlite3` isn't installed on the host

Run the backup inside the container using Python's built-in SQLite backup API
(no extra packages needed), writing into the mounted `/data` dir so the snapshot
lands on the host at `$DATA_DIR/db/`:

```sh
docker compose -f compose.prod.yaml exec -T web python - <<'PY'
import sqlite3, datetime
stamp = datetime.datetime.now().strftime("%F-%H%M")
src = sqlite3.connect("/data/db.sqlite3")
dst = sqlite3.connect(f"/data/backup-{stamp}.sqlite3")
with dst:
    src.backup(dst)
dst.close(); src.close()
print(f"wrote /data/backup-{stamp}.sqlite3")
PY
# -> appears on the host at $DATA_DIR/db/backup-<stamp>.sqlite3; move it off-box.
```

## Restoring

The snapshot is a complete database — restoring is just putting it in place.

```sh
DATA_DIR=/srv/fluke-data

# 1. Stop the app so nothing is writing:
docker compose -f compose.prod.yaml down

# 2. Replace the DB. Remove any stale WAL/SHM so they can't override the restore:
rm -f "$DATA_DIR/db/db.sqlite3-wal" "$DATA_DIR/db/db.sqlite3-shm"
gunzip -c /backups/fluke-db-YYYY-MM-DD-HHMM.sqlite3.gz > "$DATA_DIR/db/db.sqlite3"
#   (or: cp /backups/fluke-db-... "$DATA_DIR/db/db.sqlite3" if not gzipped)

# 3. Restore media:
rsync -a --delete /backups/media/ "$DATA_DIR/media/"

# 4. The container runs as UID/GID 1000 — give the files back to it:
sudo chown -R 1000:1000 "$DATA_DIR/db" "$DATA_DIR/media"

# 5. Start again:
docker compose -f compose.prod.yaml up -d
```

If the restored DB came from an **older app version**, apply any newer
migrations afterwards: `docker compose -f compose.prod.yaml exec web python manage.py migrate`.

## Portable / logical backup (optional)

A file copy is the fastest, most faithful backup. For a human-readable, engine
-independent export (e.g. to inspect, diff, or move to a different database) use
Django's `dumpdata`:

```sh
docker compose -f compose.prod.yaml exec -T web python manage.py dumpdata \
  --natural-primary --natural-foreign --indent 2 \
  -e contenttypes -e auth.permission -e sessions \
  > /backups/fluke-data-$(date +%F).json
```

Restore into a freshly migrated database with `manage.py loaddata fluke-data-….json`.
Note this captures database rows only — **uploaded media is not included**, so
still back up `$DATA_DIR/media/` separately.

## Automating it

A daily cron entry on the host, keeping 14 days and mirroring media:

```cron
# m h  dom mon dow   command
15 3 * * *  DATA_DIR=/srv/fluke-data; \
  sqlite3 "$DATA_DIR/db/db.sqlite3" ".backup '/backups/fluke-db-$(date +\%F).sqlite3'" && \
  gzip -f "/backups/fluke-db-$(date +\%F).sqlite3" && \
  rsync -a --delete "$DATA_DIR/media/" /backups/media/ && \
  find /backups -name 'fluke-db-*.sqlite3.gz' -mtime +14 -delete
```

(`%` is escaped as `\%` in crontab.)

## Off-site & retention

Local snapshots protect against mistakes, not against losing the machine. Push
`/backups` somewhere off the host — for example:

```sh
rclone sync /backups remote:fluke-backups      # or: aws s3 sync /backups s3://…
```

## Verifying a backup

A backup you haven't restored is a guess. Periodically check one:

```sh
# Integrity of the snapshot file:
sqlite3 /backups/fluke-db-YYYY-MM-DD.sqlite3 "PRAGMA integrity_check;"   # -> ok

# Or do a full dry restore into a throwaway dir and start the stack against it.
```
