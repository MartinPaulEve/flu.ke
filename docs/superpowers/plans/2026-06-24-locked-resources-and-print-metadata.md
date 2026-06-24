# Locked Resources & Print-Article Metadata Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `ResourceFile`s be "locked" (stored but downloadable only by staff, with an optional public preview), and add optional print-article metadata fields to `Resource`.

**Architecture:** Locked files live in a private storage root (`PRIVATE_MEDIA_ROOT`) outside the nginx-served `MEDIA_ROOT`; a save-time hook moves bytes between public and private storage when `is_locked` toggles; an admin-only gated view streams locked files via `FileResponse`. Print metadata is flat optional fields on `Resource`, displayed only when populated, reusing the existing partial-date helpers.

**Tech Stack:** Django, Django REST Framework, pytest / pytest-django, uv.

## Global Constraints

- Use `uv` for all commands: `uv run pytest ...`, `uv run python manage.py ...`.
- TDD strictly: write the failing test, run it, watch it fail, then implement.
- Conventional commit messages. **Do not** credit Claude/any LLM or any person. No issue number was provided, so omit the footer.
- Run `uv run ruff check` (and fix) before every commit.
- Unlocked files and all existing files/URLs must be **unchanged** — no rerouting of non-locked downloads.
- Locked downloads stream through the app (no `X-Sendfile`/`X-Accel-Redirect`; the app sits behind Traefik, nginx only fronts media).
- Reuse existing helpers: `apps/resources/partial_date.py` (`parse_partial_date`, `format_partial_date`, `to_input_value`, `YEAR`/`MONTH`/`DAY`).

## File Structure

- `config/settings.py` — add `PRIVATE_MEDIA_ROOT` env default + setting.
- `apps/resources/storage.py` *(new)* — `PrivateMediaStorage` + `private_storage` instance.
- `apps/resources/models.py` — `ResourceFile` locking fields/logic; `Resource` print fields/helpers.
- `apps/resources/migrations/0008_*.py`, `0009_*.py` *(generated)*.
- `apps/frontend/views.py` — `resource_file_download` view.
- `apps/frontend/urls.py` — gated download route.
- `apps/resources/admin.py` — inline/list/fieldset updates.
- `apps/resources/forms.py` — partial-date handling for `article_date`.
- `templates/resources/resource_detail.html` — locked-file rendering + print-article block.
- `assets/css/main.css` — `.entry__lock`, `.entry__preview` styles.
- `tests/conftest.py` — private-media isolation fixture.
- `tests/test_resource_locking.py`, `tests/test_resource_print_metadata.py` *(new)*.

---

## FEATURE 1 — Locked resource files

### Task 1: Private storage root + settings + test isolation

**Files:**
- Modify: `config/settings.py:16-31` (env defaults), `config/settings.py:144-145` (media block)
- Create: `apps/resources/storage.py`
- Modify: `tests/conftest.py`
- Test: `tests/test_resource_locking.py`

**Interfaces:**
- Produces: `apps.resources.storage.private_storage` — a `FileSystemStorage` whose location is `settings.PRIVATE_MEDIA_ROOT`, read live (so tests can override it). `settings.PRIVATE_MEDIA_ROOT` (a `Path`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_resource_locking.py`:

```python
"""Locked resource files: stored for archival, downloadable only by staff."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = pytest.mark.django_db


def test_private_storage_location_follows_setting(settings, tmp_path):
    from apps.resources.storage import private_storage

    settings.PRIVATE_MEDIA_ROOT = str(tmp_path / "priv")
    name = private_storage.save("resources/x.bin", SimpleUploadedFile("x.bin", b"hi"))

    assert private_storage.path(name).startswith(str(tmp_path / "priv"))
    assert (tmp_path / "priv" / name).read_bytes() == b"hi"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_resource_locking.py::test_private_storage_location_follows_setting -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'apps.resources.storage'`.

- [ ] **Step 3: Add the setting**

In `config/settings.py`, add to the `environ.Env(...)` defaults block (near `MEDIA_ROOT=(str, "media"),`):

```python
    PRIVATE_MEDIA_ROOT=(str, "private_media"),
```

In the media block (after `MEDIA_ROOT = BASE_DIR / env("MEDIA_ROOT")`):

```python
# Locked resource files live here — OUTSIDE MEDIA_ROOT, so the media web server
# never serves them. They are reachable only through the gated download view.
PRIVATE_MEDIA_ROOT = BASE_DIR / env("PRIVATE_MEDIA_ROOT")
```

- [ ] **Step 4: Create the storage**

Create `apps/resources/storage.py`:

```python
"""Storage for locked resource files, kept outside the nginx-served MEDIA_ROOT.

Locked files live under ``settings.PRIVATE_MEDIA_ROOT`` — a directory the public
web server never sees — so they can only be fetched through the gated download
view, never by a direct URL. Location and base_url are read live (not cached via
the parent's ``cached_property``) so tests can point them at a throwaway dir.
"""

import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class PrivateMediaStorage(FileSystemStorage):
    @property
    def base_location(self):
        return settings.PRIVATE_MEDIA_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        # No public URL: these files are streamed, never linked directly.
        return None


private_storage = PrivateMediaStorage()
```

- [ ] **Step 5: Add the test-isolation fixture**

In `tests/conftest.py`, add after the `_isolate_media` fixture:

```python
@pytest.fixture(autouse=True)
def _isolate_private_media(tmp_path_factory, settings):
    """Point PRIVATE_MEDIA_ROOT at a throwaway dir so locked-file tests never
    write into the repo."""
    settings.PRIVATE_MEDIA_ROOT = str(tmp_path_factory.mktemp("private_media"))
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_resource_locking.py::test_private_storage_location_follows_setting -v`
Expected: PASS.

- [ ] **Step 7: Lint & commit**

```bash
uv run ruff check apps/resources/storage.py config/settings.py tests/
git add apps/resources/storage.py config/settings.py tests/conftest.py tests/test_resource_locking.py
git commit -m "feat(resources): add private storage root for locked files"
```

---

### Task 2: ResourceFile locking fields + move-on-toggle

**Files:**
- Modify: `apps/resources/models.py` (`ResourceFile`, ~lines 356-422)
- Create: `apps/resources/migrations/0008_resourcefile_locking.py` *(generated)*
- Test: `tests/test_resource_locking.py`

**Interfaces:**
- Consumes: `apps.resources.storage.private_storage` (Task 1).
- Produces: `ResourceFile.is_locked: bool`, `ResourceFile.preview_image: ImageField`,
  `ResourceFile.locked_file: FileField` (private storage). `is_external` now also
  considers `locked_file`. `display_byte_size` considers `locked_file`. `save()`
  moves bytes between `file` (public) and `locked_file` (private) to match `is_locked`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_resource_locking.py`:

```python
from apps.resources.models import Resource, ResourceFile


def _resource():
    return Resource.objects.create(title="Mag Interview", kind="official", is_published=True)


def test_is_locked_defaults_false():
    f = ResourceFile(resource=_resource(), file=SimpleUploadedFile("a.mp3", b"x"))
    assert f.is_locked is False


def test_locking_moves_bytes_into_private_storage(settings):
    rf = ResourceFile.objects.create(
        resource=_resource(),
        file=SimpleUploadedFile("set.flac", b"AUDIO"),
        file_kind="audio",
    )
    public_path = rf.file.path
    assert rf.file and not rf.locked_file

    rf.is_locked = True
    rf.save()
    rf.refresh_from_db()

    assert rf.locked_file and not rf.file
    assert rf.locked_file.read() == b"AUDIO"
    assert rf.locked_file.path.startswith(str(settings.PRIVATE_MEDIA_ROOT))
    import os
    assert not os.path.exists(public_path)


def test_unlocking_moves_bytes_back_to_public_storage(settings):
    rf = ResourceFile.objects.create(
        resource=_resource(),
        file=SimpleUploadedFile("set.flac", b"AUDIO"),
        is_locked=True,
    )
    assert rf.locked_file and not rf.file

    rf.is_locked = False
    rf.save()
    rf.refresh_from_db()

    assert rf.file and not rf.locked_file
    assert rf.file.read() == b"AUDIO"
    assert str(settings.MEDIA_ROOT) in rf.file.path


def test_locked_external_link_has_no_bytes_to_move():
    rf = ResourceFile.objects.create(
        resource=_resource(),
        external_url="https://example.com/x.zip",
        is_locked=True,
    )
    assert rf.is_external is True
    assert not rf.file and not rf.locked_file
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_resource_locking.py -v`
Expected: FAIL — `ResourceFile` has no `is_locked` / `locked_file`.

- [ ] **Step 3: Add imports to models.py**

In `apps/resources/models.py`, extend the imports near the top:

```python
import os

from django.core.files.base import ContentFile
from django.urls import reverse
```

(Add `import os` at the top with other stdlib imports; add the `ContentFile` and
`reverse` imports alongside the existing `from django.db import models` block.)

Also import the private storage:

```python
from apps.resources.storage import private_storage
```

- [ ] **Step 4: Add fields to ResourceFile**

In `class ResourceFile`, after the `file` / `external_url` fields add:

```python
    is_locked = models.BooleanField(
        default=False,
        help_text="Archived: stored but downloadable only by staff. The file is "
        "moved to private storage and is not publicly reachable.",
    )
    locked_file = models.FileField(
        upload_to="resources/",
        storage=private_storage,
        blank=True,
        help_text="Internal: holds the bytes while locked. Managed automatically.",
    )
    preview_image = models.ImageField(
        upload_to="resources/previews/",
        blank=True,
        help_text="Optional public preview shown for a locked file.",
    )
```

- [ ] **Step 5: Update `is_external` and `display_byte_size`, add move-on-toggle `save`**

Replace the `is_external` property body and `display_byte_size`, and add `save`:

```python
    @property
    def is_external(self) -> bool:
        """True when this is a remote link rather than stored bytes (public or private)."""
        return not self.file and not self.locked_file and bool(self.external_url)

    @property
    def stored_file(self):
        """The field holding the uploaded bytes, whichever side they're on."""
        return self.locked_file if self.locked_file else self.file
```

Update `display_byte_size` to use `stored_file`:

```python
    @property
    def display_byte_size(self):
        if self.byte_size:
            return self.byte_size
        try:
            return self.stored_file.size or None
        except (ValueError, OSError):
            return None
```

Add the move logic and `save` to `ResourceFile`:

```python
    def _reconcile_lock_storage(self):
        """Keep the bytes on the side that matches ``is_locked``.

        Idempotent: only acts when a move is actually needed. External-URL rows
        have no bytes and are left alone.
        """
        if self.is_locked and self.file:
            data = self.file.read()
            name = os.path.basename(self.file.name)
            self.locked_file.save(name, ContentFile(data), save=False)
            self.file.delete(save=False)
        elif not self.is_locked and self.locked_file:
            data = self.locked_file.read()
            name = os.path.basename(self.locked_file.name)
            self.file.save(name, ContentFile(data), save=False)
            self.locked_file.delete(save=False)

    def save(self, *args, **kwargs):
        self._reconcile_lock_storage()
        super().save(*args, **kwargs)
```

- [ ] **Step 6: Generate the migration**

Run: `uv run python manage.py makemigrations resources -n resourcefile_locking`
Expected: creates `apps/resources/migrations/0008_resourcefile_locking.py` adding
`is_locked`, `locked_file`, `preview_image`.

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_resource_locking.py -v`
Expected: PASS (all locking model tests).

- [ ] **Step 8: Lint & commit**

```bash
uv run ruff check apps/resources/ tests/
git add apps/resources/models.py apps/resources/migrations/0008_resourcefile_locking.py tests/test_resource_locking.py
git commit -m "feat(resources): store locked files in private storage with move-on-toggle"
```

---

### Task 3: Gated download view, URL, and `download_url`

**Files:**
- Modify: `apps/frontend/views.py` (add view), `apps/frontend/urls.py` (add route)
- Modify: `apps/resources/models.py` (`ResourceFile.download_url`)
- Test: `tests/test_resource_locking.py`

**Interfaces:**
- Consumes: `ResourceFile.is_locked`, `.locked_file`, `.is_external`, `.display_name`.
- Produces: URL name `resource_file_download` (`/resources/file/<int:pk>/download/`).
  `ResourceFile.download_url` returns that gated URL when locked, else the direct
  public URL (unchanged for unlocked files).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_resource_locking.py`:

```python
from django.contrib.auth import get_user_model
from django.urls import reverse


def _staff_client(client):
    user = get_user_model().objects.create_user("ed", password="x", is_staff=True)
    client.force_login(user)
    return client


def test_locked_download_404_for_anonymous(client):
    rf = ResourceFile.objects.create(
        resource=_resource(), file=SimpleUploadedFile("s.flac", b"AUDIO"), is_locked=True
    )
    resp = client.get(reverse("resource_file_download", args=[rf.pk]))
    assert resp.status_code == 404


def test_locked_download_streams_for_staff(client):
    rf = ResourceFile.objects.create(
        resource=_resource(), file=SimpleUploadedFile("s.flac", b"AUDIO"), is_locked=True
    )
    resp = _staff_client(client).get(reverse("resource_file_download", args=[rf.pk]))
    assert resp.status_code == 200
    assert b"".join(resp.streaming_content) == b"AUDIO"


def test_download_url_is_gated_when_locked(client):
    rf = ResourceFile.objects.create(
        resource=_resource(), file=SimpleUploadedFile("s.flac", b"AUDIO"), is_locked=True
    )
    assert rf.download_url == reverse("resource_file_download", args=[rf.pk])


def test_download_url_unchanged_when_unlocked():
    rf = ResourceFile.objects.create(
        resource=_resource(), file=SimpleUploadedFile("s.flac", b"AUDIO")
    )
    assert rf.download_url == rf.file.url


def test_gated_view_redirects_unlocked_to_public_url(client):
    rf = ResourceFile.objects.create(
        resource=_resource(), file=SimpleUploadedFile("s.flac", b"AUDIO")
    )
    resp = client.get(reverse("resource_file_download", args=[rf.pk]))
    assert resp.status_code == 302
    assert resp["Location"] == rf.file.url
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_resource_locking.py -k download -v`
Expected: FAIL — `NoReverseMatch` for `resource_file_download`.

- [ ] **Step 3: Update `download_url`**

In `apps/resources/models.py`, replace `ResourceFile.download_url`:

```python
    @property
    def download_url(self) -> str:
        """Where the file can be fetched. Locked files go through the gated view;
        unlocked files keep their direct public URL (unchanged)."""
        if self.is_locked:
            return reverse("resource_file_download", args=[self.pk])
        return self.file.url if self.file else self.external_url
```

- [ ] **Step 4: Add the view**

In `apps/frontend/views.py`, add the import near the top (with the other django imports):

```python
from django.http import FileResponse, Http404
from django.shortcuts import redirect
```

(If `redirect`/`Http404` are already imported, don't duplicate.) Add the view
(near `resource_detail`):

```python
def resource_file_download(request, pk):
    """Serve a resource file. Locked files require staff and are streamed from
    private storage; unlocked files just redirect to their public URL."""
    rf = get_object_or_404(ResourceFile, pk=pk)
    if rf.is_locked and not request.user.is_staff:
        raise Http404
    if rf.is_external:
        return redirect(rf.external_url)
    if rf.is_locked:
        return FileResponse(
            rf.locked_file.open("rb"), as_attachment=True, filename=rf.display_name
        )
    return redirect(rf.file.url)
```

Add `ResourceFile` to the existing resources import:

```python
from apps.resources.models import KIND_FAN, KIND_OFFICIAL, Resource, ResourceFile
```

- [ ] **Step 5: Register the URL**

In `apps/frontend/urls.py`, add **before** the `resources/<slug:kind>/<slug:slug>/` route:

```python
    path(
        "resources/file/<int:pk>/download/",
        views.resource_file_download,
        name="resource_file_download",
    ),
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_resource_locking.py -v`
Expected: PASS (all locking tests).

- [ ] **Step 7: Lint & commit**

```bash
uv run ruff check apps/frontend/ apps/resources/ tests/
git add apps/frontend/views.py apps/frontend/urls.py apps/resources/models.py tests/test_resource_locking.py
git commit -m "feat(resources): gated download view for locked files"
```

---

### Task 4: Detail-page rendering for locked files

**Files:**
- Modify: `templates/resources/resource_detail.html` (files loop, ~lines 24-37)
- Modify: `assets/css/main.css` (append small styles)
- Test: `tests/test_resource_locking.py`

**Interfaces:**
- Consumes: `f.is_locked`, `f.download_url`, `f.preview_image`, `request.user.is_staff`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_resource_locking.py`:

```python
def test_detail_hides_link_and_shows_notice_for_locked_anon(client):
    r = _resource()
    ResourceFile.objects.create(
        resource=r, file=SimpleUploadedFile("s.flac", b"AUDIO"), is_locked=True
    )
    html = client.get(r.get_absolute_url()).content.decode()
    assert reverse("resource_file_download", args=[r.files.first().pk]) not in html
    assert "Archived" in html


def test_detail_shows_link_for_locked_staff(client):
    r = _resource()
    rf = ResourceFile.objects.create(
        resource=r, file=SimpleUploadedFile("s.flac", b"AUDIO"), is_locked=True
    )
    html = _staff_client(client).get(r.get_absolute_url()).content.decode()
    assert reverse("resource_file_download", args=[rf.pk]) in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_resource_locking.py -k detail -v`
Expected: FAIL — anon page still renders the download link (no locked handling yet).

- [ ] **Step 3: Update the files loop**

In `templates/resources/resource_detail.html`, replace the `<li class="entry">…</li>`
block inside the files loop with:

```html
        <li class="entry">
          <span class="entry__index">{{ forloop.counter|stringformat:"02d" }}</span>
          {% if f.is_locked and not request.user.is_staff %}
            <span class="entry__title">{{ f.display_name }} <span class="entry__lock">🔒 Archived — not publicly available</span></span>
            <span class="entry__meta">{{ f.get_file_kind_display }}</span>
          {% else %}
            <span class="entry__title"><a href="{{ f.download_url }}"{% if f.is_external %} rel="noopener" target="_blank"{% else %} download{% endif %}>{{ f.display_name }}</a>{% if f.is_locked %} <span class="entry__lock">🔒</span>{% endif %}{% with size=f.display_byte_size %}{% if size %} <span class="entry__size">({{ size|filesizeformat }})</span>{% endif %}{% endwith %}</span>
            <span class="entry__meta">{% if f.is_external %}{{ f.get_file_kind_display }} ↗{% else %}{{ f.get_file_kind_display }}{% endif %}</span>
          {% endif %}
          {% if f.is_locked and f.preview_image %}<img class="entry__preview" src="{{ f.preview_image.url }}" alt="" loading="lazy">{% endif %}
        </li>
```

- [ ] **Step 4: Add CSS**

Append to `assets/css/main.css`:

```css
.entry__lock { color: var(--accent-text); font-size: 0.85em; }
.entry__preview { display: block; max-width: 320px; margin-top: 0.5rem; border-radius: 4px; }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_resource_locking.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add templates/resources/resource_detail.html assets/css/main.css tests/test_resource_locking.py
git commit -m "feat(resources): show locked files as archived with preview on detail page"
```

---

### Task 5: Admin surfacing for locking

**Files:**
- Modify: `apps/resources/admin.py` (`ResourceFileInline` ~lines 12-20, `ResourceFileAdmin` ~lines 22-56)
- Test: `tests/test_resource_locking.py`

**Interfaces:**
- Consumes: `ResourceFile.is_locked`, `.preview_image`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_resource_locking.py`:

```python
def test_admin_inline_exposes_locking_fields():
    from apps.resources.admin import ResourceFileInline

    assert "is_locked" in ResourceFileInline.fields
    assert "preview_image" in ResourceFileInline.fields
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_resource_locking.py -k admin_inline -v`
Expected: FAIL — `is_locked` not in inline fields.

- [ ] **Step 3: Update the admin**

In `apps/resources/admin.py`, update `ResourceFileInline.fields` to include the new
fields:

```python
    fields = (
        "file", "external_url", "is_locked", "preview_image", "file_kind",
        "original_filename", "byte_size", "duration", "display_order",
    )
```

In `ResourceFileAdmin`, add locking to the list view:

```python
    list_display = ("__str__", "resource", "file_kind", "is_locked", "byte_size")
    list_filter = ("file_kind", "is_locked")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_resource_locking.py -k admin_inline -v`
Expected: PASS.

- [ ] **Step 5: Lint & commit**

```bash
uv run ruff check apps/resources/admin.py
git add apps/resources/admin.py tests/test_resource_locking.py
git commit -m "feat(resources): surface lock controls in the admin"
```

---

## FEATURE 2 — Print-article metadata

### Task 6: Print metadata fields on Resource

**Files:**
- Modify: `apps/resources/models.py` (`Resource`, add fields + helpers near line 248 / property block)
- Create: `apps/resources/migrations/0009_resource_print_metadata.py` *(generated)*
- Test: `tests/test_resource_print_metadata.py`

**Interfaces:**
- Produces: `Resource.article_authors`, `.publication_title`, `.article_date`,
  `.article_date_precision`, `.page_numbers`, `.article_url`, `.purchase_url`;
  `Resource.has_print_metadata: bool`; `Resource.article_date_display: str`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_resource_print_metadata.py`:

```python
"""Optional print-article metadata on resources (magazine/journal interviews)."""

import datetime

import pytest

from apps.resources.models import Resource

pytestmark = pytest.mark.django_db


def test_print_fields_blank_by_default():
    r = Resource.objects.create(title="Just a file", kind="official")
    assert r.article_authors == ""
    assert r.publication_title == ""
    assert r.article_date is None
    assert r.has_print_metadata is False


def test_has_print_metadata_true_when_any_field_set():
    r = Resource.objects.create(title="Interview", publication_title="Mixmag")
    assert r.has_print_metadata is True


def test_article_date_display_respects_month_precision():
    r = Resource.objects.create(
        title="Interview",
        article_date=datetime.date(2005, 6, 1),
        article_date_precision="month",
    )
    assert r.article_date_display == "Jun 2005"
    assert "1" not in r.article_date_display.replace("2005", "")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_resource_print_metadata.py -v`
Expected: FAIL — `Resource` has no `article_authors`.

- [ ] **Step 3: Add the fields**

In `apps/resources/models.py`, in `class Resource`, after `external_url` and before
`is_published`, add:

```python
    # --- Print-article metadata (magazine / journal interviews etc.) --------
    # All optional; populated only for resources that represent a print article.
    article_authors = models.CharField(
        max_length=300, blank=True, help_text="Article author(s), free text."
    )
    publication_title = models.CharField(
        max_length=200, blank=True, help_text="Magazine or journal title."
    )
    article_date = models.DateField(null=True, blank=True)
    article_date_precision = models.CharField(
        max_length=5,
        choices=[(YEAR, "Year"), (MONTH, "Month"), (DAY, "Day")],
        default=DAY,
    )
    page_numbers = models.CharField(
        max_length=50, blank=True, help_text='e.g. "pp. 34–37".'
    )
    article_url = models.URLField(blank=True, help_text="Link to the article online.")
    purchase_url = models.URLField(blank=True, help_text="Where to buy the issue.")
```

- [ ] **Step 4: Add the helper properties**

In `class Resource`, near the other `@property` definitions (e.g. after
`recorded_display`), add:

```python
    @property
    def has_print_metadata(self) -> bool:
        """True when any print-article field is populated."""
        return any(
            [
                self.article_authors,
                self.publication_title,
                self.article_date,
                self.page_numbers,
                self.article_url,
                self.purchase_url,
            ]
        )

    @property
    def article_date_display(self) -> str:
        """The article date shown only as precisely as it's known."""
        return format_partial_date(self.article_date, self.article_date_precision)
```

- [ ] **Step 5: Generate the migration**

Run: `uv run python manage.py makemigrations resources -n resource_print_metadata`
Expected: creates `apps/resources/migrations/0009_resource_print_metadata.py`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_resource_print_metadata.py -v`
Expected: PASS.

- [ ] **Step 7: Lint & commit**

```bash
uv run ruff check apps/resources/ tests/
git add apps/resources/models.py apps/resources/migrations/0009_resource_print_metadata.py tests/test_resource_print_metadata.py
git commit -m "feat(resources): add optional print-article metadata fields"
```

---

### Task 7: Admin form + fieldset for print metadata

**Files:**
- Modify: `apps/resources/forms.py` (`ResourceAdminForm`)
- Modify: `apps/resources/admin.py` (`ResourceAdmin.fieldsets`)
- Test: `tests/test_resource_print_metadata.py`

**Interfaces:**
- Consumes: `parse_partial_date`, `to_input_value`; `Resource.article_date` / `.article_date_precision`.
- Produces: a single `article_date_input` admin field that reads/writes the
  date+precision pair (mirroring the existing `recorded` field).

- [ ] **Step 1: Write the failing test**

Append to `tests/test_resource_print_metadata.py`:

```python
def test_admin_form_parses_partial_article_date():
    from apps.resources.forms import ResourceAdminForm

    form = ResourceAdminForm(
        data={
            "title": "Interview",
            "kind": "official",
            "slug": "interview",
            "recorded": "",
            "article_date_input": "2005-06",
            "recorded_precision": "day",
        }
    )
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    assert obj.article_date == datetime.date(2005, 6, 1)
    assert obj.article_date_precision == "month"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_resource_print_metadata.py -k admin_form -v`
Expected: FAIL — no `article_date_input` field.

- [ ] **Step 3: Update the form**

In `apps/resources/forms.py`, extend `ResourceAdminForm`. Add the field declaration
beside `recorded`:

```python
    article_date_input = forms.CharField(
        required=False,
        label="Article date",
        help_text="Year, year-month or full date — e.g. 2005, 2005-06.",
    )
```

Extend `Meta.exclude`:

```python
        exclude = (
            "recorded_date",
            "recorded_precision",
            "article_date",
            "article_date_precision",
        )
```

In `__init__`, after the existing `recorded` initial, add:

```python
            self.fields["article_date_input"].initial = to_input_value(
                self.instance.article_date, self.instance.article_date_precision
            )
```

Add a clean method:

```python
    def clean_article_date_input(self):
        text = self.cleaned_data.get("article_date_input", "")
        try:
            self._article_date = parse_partial_date(text)
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return text
```

In `save`, after the `recorded` assignment, add:

```python
        a_date, a_precision = getattr(self, "_article_date", (None, "day"))
        self.instance.article_date = a_date
        self.instance.article_date_precision = a_precision
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_resource_print_metadata.py -k admin_form -v`
Expected: PASS.

- [ ] **Step 5: Add the admin fieldset**

In `apps/resources/admin.py`, add a new fieldset to `ResourceAdmin.fieldsets`, after
the `"Metadata"` fieldset:

```python
        (
            "Print article",
            {
                "classes": ("collapse",),
                "fields": (
                    "article_authors",
                    "publication_title",
                    "article_date_input",
                    "page_numbers",
                    "article_url",
                    "purchase_url",
                ),
            },
        ),
```

- [ ] **Step 6: Run the full resources test suite**

Run: `uv run pytest tests/test_resource_print_metadata.py tests/test_resources_models.py -v`
Expected: PASS.

- [ ] **Step 7: Lint & commit**

```bash
uv run ruff check apps/resources/
git add apps/resources/forms.py apps/resources/admin.py tests/test_resource_print_metadata.py
git commit -m "feat(resources): admin editing for print-article metadata"
```

---

### Task 8: Detail-page print-article block

**Files:**
- Modify: `templates/resources/resource_detail.html` (add block before related-post section)
- Test: `tests/test_resource_print_metadata.py`

**Interfaces:**
- Consumes: `resource.has_print_metadata`, the print fields, `resource.article_date_display`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_resource_print_metadata.py`:

```python
def test_detail_shows_print_block_when_populated(client):
    r = Resource.objects.create(
        title="Interview",
        kind="official",
        is_published=True,
        publication_title="Mixmag",
        article_authors="Jane Smith",
        page_numbers="pp. 34–37",
    )
    html = client.get(r.get_absolute_url()).content.decode()
    assert "Mixmag" in html
    assert "Jane Smith" in html
    assert "pp. 34" in html


def test_detail_hides_print_block_when_empty(client):
    r = Resource.objects.create(title="Plain", kind="official", is_published=True)
    html = client.get(r.get_absolute_url()).content.decode()
    assert "Print article" not in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_resource_print_metadata.py -k detail -v`
Expected: FAIL — print fields not rendered.

- [ ] **Step 3: Add the template block**

In `templates/resources/resource_detail.html`, add **before** the
`{% if resource.related_post … %}` section:

```html
  {% if resource.has_print_metadata %}
    <section class="print-article" aria-labelledby="print-article-title" style="margin-top:2.5rem">
      <h2 id="print-article-title">Print article</h2>
      <ul class="resource-meta">
        {% if resource.article_authors %}<li><span class="resource-meta__label">Author</span> {{ resource.article_authors }}</li>{% endif %}
        {% if resource.publication_title %}<li><span class="resource-meta__label">Publication</span> {{ resource.publication_title }}</li>{% endif %}
        {% if resource.article_date %}<li><span class="resource-meta__label">Date</span> <time datetime="{{ resource.article_date|date:'Y-m-d' }}">{{ resource.article_date_display }}</time></li>{% endif %}
        {% if resource.page_numbers %}<li><span class="resource-meta__label">Pages</span> {{ resource.page_numbers }}</li>{% endif %}
        {% if resource.article_url %}<li><span class="resource-meta__label">Article</span> <a href="{{ resource.article_url }}" rel="noopener">Read online ↗</a></li>{% endif %}
        {% if resource.purchase_url %}<li><span class="resource-meta__label">Purchase</span> <a href="{{ resource.purchase_url }}" rel="noopener">Buy issue ↗</a></li>{% endif %}
      </ul>
    </section>
  {% endif %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_resource_print_metadata.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/resources/resource_detail.html tests/test_resource_print_metadata.py
git commit -m "feat(resources): render print-article metadata on detail page"
```

---

### Task 9: Full-suite verification

- [ ] **Step 1: Run the whole test suite**

Run: `uv run pytest`
Expected: all tests pass (including pre-existing `test_resource_files.py`,
`test_resources_models.py`).

- [ ] **Step 2: Check for missing migrations**

Run: `uv run python manage.py makemigrations --check --dry-run`
Expected: "No changes detected".

- [ ] **Step 3: Lint the whole change**

Run: `uv run ruff check .`
Expected: no errors.

- [ ] **Step 4: Final commit (if anything outstanding)**

```bash
git add -A
git commit -m "test(resources): verify locked files and print metadata end to end"
```

---

## Self-Review notes

- **Spec coverage:** locked storage separation (Task 1), model + move-on-toggle
  (Task 2), gated view/access control (Task 3), template states + preview (Task 4),
  admin (Task 5); print fields (Task 6), admin form/fieldset (Task 7), detail block
  (Task 8), full verification (Task 9). All spec sections mapped.
- **Unlocked files untouched:** `download_url` only changes behaviour when
  `is_locked` (Task 3, Step 3); the gated view redirects unlocked files to their
  existing public URL.
- **Type consistency:** URL name `resource_file_download` used identically in the
  model property, the URL conf, and every test. `article_date_input` used in form
  field, `Meta.exclude` complement, admin fieldset, and tests.
- **API note:** the read-only API's `download_url` will return the gated URL for
  locked files; anonymous fetches 404 (acceptable, consistent). No serializer
  change needed.
