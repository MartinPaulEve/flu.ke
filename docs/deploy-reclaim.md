# Hosting the CMS on Reclaim Hosting (cPanel)

This keeps the **static site generator** approach but runs the CMS on the server
instead of your laptop. Two "sites" on the one cPanel account:

```
cms.flu.ke   ──►  Django CMS (cPanel "Python App" / Passenger)   ← you log in here
                       │  build_site / "Publish now"
                       ▼
flu.ke       ──►  document root = the generated static site (plain files)
                  flu.ke/media/  = the media library (served as static files)
```

Editing happens privately at `cms.flu.ke/admin/`; **Publish** regenerates the
static files in `flu.ke`'s document root. The public site runs no application.

---

## 0. What changed vs. running it locally

- `DEBUG=False` in production, so the CMS now serves its **own** admin CSS/JS via
  **WhiteNoise** (already wired in). Run `collectstatic` on deploy.
- It is internet-facing, so set a real `SECRET_KEY`, `DJANGO_SECURE=True`
  (HTTPS redirect, secure cookies, HSTS), `DJANGO_ALLOWED_HOSTS=cms.flu.ke`, and
  `CSRF_TRUSTED_ORIGINS=https://cms.flu.ke`.
- A `passenger_wsgi.py` (the cPanel entry point) and a `requirements.txt` (Reclaim
  uses `pip`, not `uv`) are included.
- The CMS runs on **SQLite** by default, which is fine for a single editor. If you
  ever need MySQL/MariaDB instead, see [docs/mysql-migration.md](mysql-migration.md)
  — it covers the optional driver, utf8mb4, dumping/loading the data, copying the
  media tree, and a local Docker dry-run. Only `DATABASE_URL` changes; SQLite stays
  the default.

---

## 1. Create the two domains in cPanel

1. **Subdomain** `cms.flu.ke` — note its document root (e.g. `~/cms.flu.ke`); the
   Python App will manage it.
2. **Main site** `flu.ke` — its document root is where the static site is published
   (the primary domain is usually `~/public_html`; an addon/subdomain has its own).
3. Run **AutoSSL** (cPanel → SSL/TLS Status) so both have Let's Encrypt certificates.

## 2. Get the code onto the server

Use **cPanel → Git™ Version Control** (clone your repo) or upload the project.
You do **not** need to upload `Ingest/` unless you intend to run the importers on
the server (it's large — see §7). Put the project somewhere like `~/cms_app`.

## 3. Create the Python App

cPanel → **Setup Python App** → *Create Application*:

- **Python version:** 3.12 (or the newest available).
- **Application root:** `cms_app` (where the code lives).
- **Application URL:** `cms.flu.ke`.
- **Application startup file:** `passenger_wsgi.py`  ·  **Entry point:** `application`.

Create it. cPanel shows a command to enter the app's virtualenv, e.g.:
```bash
source /home/<user>/virtualenv/cms_app/3.12/bin/activate && cd ~/cms_app
```

## 4. Install dependencies

In that virtualenv:
```bash
pip install -r requirements.txt
```

## 5. Configure environment variables

In the Python App screen, add these (or put them in `~/cms_app/.env`):

| Variable | Value |
|----------|-------|
| `DJANGO_SECRET_KEY` | a long random string — `python -c "import secrets;print(secrets.token_urlsafe(50))"` |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_SECURE` | `True` |
| `DJANGO_ALLOWED_HOSTS` | `cms.flu.ke` |
| `CSRF_TRUSTED_ORIGINS` | `https://cms.flu.ke` |
| `SITE_BASE_URL` | `https://flu.ke` |
| `SITE_NAME` | `Fluke` |
| `BUILD_DIR` | `/home/<user>/public_html` *(the **flu.ke** document root, absolute)* |
| `MEDIA_ROOT` | `/home/<user>/public_html/media` *(media served by the public site)* |
| `MEDIA_URL` | `https://flu.ke/media/` *(absolute, so admin image previews resolve)* |
| `DATABASE_URL` | `sqlite:////home/<user>/cms_app/db.sqlite3` *(note the 4 slashes; keep it **outside** any document root)* |
| `MUSICBRAINZ_CONTACT` | your email (only needed for `musicbrainz_sync`) |

> **Do not** point `BUILD_DIR` at a directory you also keep other files in, and
> never run `build_site --clean` against a shared document root — it deletes the
> target first. Use a document root dedicated to the generated site.

## 6. Initialise and publish

From the virtualenv (cPanel **Terminal** or SSH):
```bash
python manage.py migrate
python manage.py collectstatic --noinput     # admin CSS/JS (served by WhiteNoise)
python manage.py createsuperuser              # your admin login
python manage.py build_site                   # generate the static site into BUILD_DIR
```
Then **Restart** the app (the Python App screen, or `touch ~/cms_app/tmp/restart.txt`).

Visit `https://cms.flu.ke/admin/`, log in, and check `https://flu.ke/`.

## 7. Importing the old content (optional, one-off)

If you want the discography/media/blog imported on the server, upload `Ingest/`
to `~/cms_app/Ingest` and run (in the virtualenv):
```bash
python manage.py import_discography
python manage.py import_media          # copies the media into MEDIA_ROOT (public /media)
python manage.py import_blog           # network: Wayback recovery
python manage.py build_site
```
You can delete `Ingest/` afterwards.

## 8. Day-to-day: editing and publishing

- Edit in the admin. The **Build state** screen has an **"Unpublished changes"**
  banner and a **Publish now** button that rebuilds the static site. Because media
  lives inside `BUILD_DIR`, publishing only re-renders HTML (it does not recopy the
  media library), so it's fast.
- Prefer the command line for big jobs: `python manage.py build_site` (or schedule
  it with **cPanel → Cron jobs**, calling the venv's python).

## 9. Lock down the admin (recommended)

The admin login is public. In addition to a strong password + HTTPS:

- Restrict it to your IP with an `.htaccess` in the app's `public` directory:
  ```apache
  <RequireAny>
    Require ip 203.0.113.0/24      # your office/home IP(s)
  </RequireAny>
  ```
- Or add cPanel **Directory Privacy** (HTTP Basic Auth) in front of the app.

## Disk / media note

"Host everything on the site" means the full media library (~10 GB) lives under
`flu.ke/media`. Check your Reclaim plan's disk quota. If it's tight, host the large
audio/archives on object storage (Cloudflare R2 / Backblaze B2) and link to them
from the resources instead — set `MEDIA_URL` to that bucket and keep only small
assets locally.

## Updating the deployed code

```bash
git pull                       # or re-upload
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
# restart the app, then Publish (or run build_site)
```
