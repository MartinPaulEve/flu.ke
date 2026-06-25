# Enabling locked (private) resource files in Docker

Locked resource files are stored **outside** the public `media/` directory, in a
private location the web server never serves (`PRIVATE_MEDIA_ROOT`, which defaults
to `/app/private_media` inside the container). Only the gated, staff-only download
view streams them.

If that directory isn't mounted and owned correctly, uploading a locked file fails
with a **permission error (HTTP 500)** — the container's non-root app user can't
write to it. This guide adds the private dir to an existing Docker setup, mirroring
how `media` is already handled.

## Background: why the 500 happens

- A bind mount keeps the **host directory's** ownership (unlike named volumes, which
  inherit the image's ownership).
- The container runs as a **non-root** user (UID/GID `1000:1000` by default, set at
  build time).
- So if `private_media` is missing or owned by `root`, the app can't write locked
  files there → `PermissionError: [Errno 13] Permission denied` → 500.

The fix is to create the host directory, give it the **same owner** the container
runs as, and bind-mount it at `/app/private_media`.

## Steps

### 1. Add the volume mount

In your `docker-compose.yml`, find the service that runs the Fluke app and the
`media` line in its `volumes:` list. Add a sibling line for the private dir:

```yaml
      - "${DATA_DIR:-/home/www-runner/fluke-data}/media:/app/media"
      - "${DATA_DIR:-/home/www-runner/fluke-data}/private_media:/app/private_media"
```

- The **left side** is the host path (next to your existing `media` dir).
- The **right side must be exactly `/app/private_media`** — that's where the app
  writes locked files. `PRIVATE_MEDIA_ROOT` defaults to this path, so you do **not**
  need to set any environment variable.

### 2. Create the host directory with the same owner as `media`

This is what actually fixes the 500. The safest approach copies whatever owner your
working `media` dir already uses, so you don't have to look up the UID:

```sh
mkdir -p /home/www-runner/fluke-data/private_media
sudo chown --reference=/home/www-runner/fluke-data/media \
           /home/www-runner/fluke-data/private_media
```

If you'd rather set it explicitly, it's the same UID/GID the image was built with
(default `1000:1000`):

```sh
sudo chown -R 1000:1000 /home/www-runner/fluke-data/private_media
```

### 3. Recreate the container

So the new mount takes effect:

```sh
docker compose up -d        # add -f <file> if your compose file isn't the default name
```

A rebuild (`--build`) is **not** required for a bind mount — the host directory's
ownership is what governs, so step 2 is the real fix.

## Verify

Compare the owners inside the container — `media` and `private_media` should match:

```sh
docker compose exec <your-service-name> ls -ld /app/media /app/private_media
```

Then upload a locked file in the admin. It should succeed, and the file will land
at `/home/www-runner/fluke-data/private_media/resources/…` on the host and persist
across rebuilds.

## Troubleshooting

- **Still a 500 on locked upload?** Re-check ownership: the container user must own
  (or be able to write to) the host `private_media` dir. Run the `ls -ld` check
  above; if `private_media`'s owner differs from `media`'s, re-run step 2.
- **`media` uploads also fail?** Then the underlying owner is wrong for `media` too
  — fix that first (same `chown` to the container UID/GID), then `private_media`
  with `--reference` will inherit the correct owner.
- **Locked files vanish after a rebuild?** The mount is missing — confirm the volume
  line from step 1 is present and the container was recreated.
