# Locked resources & print-article metadata — design

**Date:** 2026-06-24
**App:** `apps/resources`
**Status:** approved design, pending implementation

## Summary

Two independent additions to the resources app:

1. **Locked resource files** — a `ResourceFile` can be marked *locked*: the file is
   still stored for archival purposes, but only staff (admins) can download it.
   Non-admins may see an optional preview image, and a freely downloadable *sample*
   is just a separate, unlocked file row.
2. **Print-article metadata** — optional flat fields on `Resource` (authors,
   publication title, date, page numbers, article URL, purchase URL) so resources
   that represent print articles (magazine interviews, journal pieces) carry the
   right metadata. Resources that aren't articles simply leave them blank.

The two features share no logic and can be built and reviewed independently.

## Feature 1 — Locked resource files

### Goals & constraints

- Genuine protection: a non-admin must not be able to download a locked file, even
  by guessing its URL.
- **No impact on existing files or the rest of the site.** Unlocked files (which is
  every file today) keep their current direct `/media/...` URLs served by nginx.
  No global rerouting, so no broken inbound links and no Python-streaming slowdown.
- Works with the deployed architecture: the site runs behind **Traefik**; a
  **separate nginx** fronts only the media directory. `X-Accel-Redirect`/`X-Sendfile`
  is therefore unavailable (the app's responses don't pass through that nginx), so
  locked downloads stream through the app. Acceptable because locked downloads are
  admin-only and rare.

### Storage separation

Protection is guaranteed by **filesystem location**, not nginx config:

- `MEDIA_ROOT` — public, fronted by nginx (unchanged).
- New `PRIVATE_MEDIA_ROOT` — a sibling directory **outside** the nginx-served media
  dir, readable only by the app. Configured via env, defaulting to a `private_media`
  dir alongside `media`.
- A module-level `private_storage = FileSystemStorage(location=PRIVATE_MEDIA_ROOT)`
  with no public base URL.

Because nginx never sees `PRIVATE_MEDIA_ROOT`, locked files cannot be fetched
directly regardless of nginx rules.

### Model changes — `ResourceFile`

- `is_locked = BooleanField(default=False)` — when true, download requires `is_staff`.
- `preview_image = ImageField(upload_to="resources/previews/", blank=True)` — optional
  preview shown to everyone (lives under the public `MEDIA_ROOT`, so it stays viewable).
- `locked_file = FileField(upload_to="resources/", storage=private_storage, blank=True)`
  — holds the bytes when locked. The existing public `file` field holds them when
  unlocked. Exactly one of `file` / `locked_file` is populated, kept in sync with
  `is_locked`.

A downloadable **sample** needs no new field: it's a separate, unlocked `ResourceFile`
row on the same resource.

### Move-on-toggle

`ResourceFile.save()` reconciles storage with lock state:

- Becoming locked (`is_locked` true, bytes still in public `file`): copy bytes from
  `file` into `locked_file` (private storage), then clear/delete `file`.
- Becoming unlocked (`is_locked` false, bytes in `locked_file`): reverse the move.
- No-op when already consistent or when the row is external-URL-only.

This keeps a file's physical location always matching its lock state, so a file
locked *after* upload stops being publicly reachable (its old public URL 404s — by
design; that's what makes the lock meaningful).

### Download access

- New gated view: `GET /resources/file/<pk>/download/` (name `resource-file-download`).
  - Locked **and** requester is not `is_staff` → **HTTP 404** (don't reveal existence).
  - Locked **and** staff → `FileResponse` streaming `locked_file` (correct content
    type / `Content-Disposition: attachment`); external-URL locked file → redirect.
  - **Unlocked** file → redirect (302) to the public `file.url` (or external URL).
    The view stays correct if ever hit for an unlocked file, but templates won't
    normally use it for those.
- Unlocked, hosted files are **not** linked through this view by templates/API —
  they keep using the direct public `file.url`. Only locked files are *linked* via
  the gated URL.
- `ResourceFile` gains a helper (e.g. `download_url`) that returns the gated URL when
  locked and the direct public URL when not, so templates have one thing to call.

### Template behaviour (`resource_detail.html`)

For each file:

- Unlocked → unchanged (direct download link).
- Locked, staff viewer → normal download link (via gated URL) plus a "🔒 locked"
  indicator.
- Locked, non-staff viewer → show `preview_image` if present, plus a short
  "Archived — not publicly downloadable" note; **no** download link.

### Admin

- Add `is_locked`, `preview_image` to the `ResourceFileInline` fields.
- Optionally surface `is_locked` in `ResourceFileAdmin.list_display` / `list_filter`.
- Toggling `is_locked` and saving triggers the move-on-toggle logic above.

## Feature 2 — Print-article metadata

### Model changes — `Resource`

All optional (`blank=True`, dates `null=True`), grouped in a new "Print article"
admin fieldset. Reuses existing `title` (article title) and `description`/`snippet`
(summary) — no duplicates introduced.

- `article_authors = CharField(max_length=300, blank=True)` — free text, e.g.
  "Jane Smith, John Doe".
- `publication_title = CharField(max_length=200, blank=True)` — magazine / journal name.
- `article_date = DateField(null=True, blank=True)` plus
  `article_date_precision = CharField(choices=[year/month/day], default=day)` —
  reusing the existing partial-date pattern (`apps/resources/partial_date.py`), since
  issues are often known only to month/year.
- `page_numbers = CharField(max_length=50, blank=True)` — e.g. "pp. 34–37".
- `article_url = URLField(blank=True)` — link to the article online.
- `purchase_url = URLField(blank=True)` — where to buy the issue.

### Display (`resource_detail.html`)

A "Print article" block renders **only when at least one** print field is populated
(helper property `has_print_metadata` on `Resource`). Within it, each line renders
only if its field is set. `article_date` is formatted via the partial-date precision
(reusing the existing formatting helper) so a month-precision date shows "Jun 2005",
not "1 Jun 2005".

### Admin

- New "Print article" `fieldset` on `ResourceAdmin` with the fields above.
- `article_date` + `article_date_precision` handled through the same partial-date
  form-field approach already used for `recorded_date` in `ResourceAdminForm`.

## Migrations

- `0008_resourcefile_locking` — `is_locked`, `preview_image`, `locked_file` on
  `ResourceFile`.
- `0009_resource_print_metadata` — the six print fields on `Resource`.

Both are additive (new nullable/blank fields); no data migration needed. Existing
rows default to unlocked with empty print metadata.

## Settings

- Add `PRIVATE_MEDIA_ROOT` (env-driven, default `BASE_DIR / "private_media"`).
- No change to `STORAGES`, `MEDIA_ROOT`, `MEDIA_URL`, or the dev `/media/` serve route
  (private files live outside it, so it can't reach them).

## Testing (TDD, red→green)

Written first as failing tests, then implemented:

**Locked files**
- `is_locked` defaults to `False`; existing/unlocked files keep direct `file.url`.
- Gated view: anonymous/non-staff GET of a locked file → 404; staff GET → 200 with
  file bytes and an attachment disposition.
- Gated view for an unlocked file → 302 redirect to its public `file.url`; the
  unlocked file's direct URL is unchanged and still served by nginx.
- Move-on-toggle: locking moves bytes into `PRIVATE_MEDIA_ROOT` and the public path no
  longer exists; unlocking reverses it. (Uses the `_isolate_media` tmp dirs; a private
  tmp root is set up similarly in a fixture.)
- External-URL locked file → staff redirect, non-staff 404.
- Template: locked file renders preview + notice and **no** link for anon; renders a
  link for staff.

**Print metadata**
- Fields persist and are blank by default.
- `has_print_metadata` is false when all blank, true when any set.
- Detail page shows the print block only when populated; hidden when empty.
- Partial-date formatting: month-precision `article_date` renders without a day.

Content/wording assertions are avoided where they'd ossify copy; tests target
behaviour (status codes, presence/absence of a download link, field persistence,
formatting form).

## Out of scope (YAGNI)

- Per-user (non-staff) download grants / tokenised links.
- Multiple structured article URLs (one `article_url` + `purchase_url` suffices).
- Linking print authors to the discography `Artist` vocabulary.
- Migrating existing files into private storage (nothing is locked yet).
