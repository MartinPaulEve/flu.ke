# Post OG Cover Image Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Composite a blog `Post`'s `cover_image` into its auto-generated Open Graph card (image right, text left), exactly like the discography `Release` cards.

**Architecture:** The OG rendering engine (`apps/core/og.py`) and the save-time hook (`SeoFieldsMixin.ensure_og_image()` → `og_card()`) already support cover compositing and already run on `Post.save()`. The only change is overriding `og_card()` on `Post` to return the published-date subtitle and the cover bytes — mirroring `Release.og_card()` / `Release._og_cover_bytes()`.

**Tech Stack:** Django, Pillow (PIL), pytest / pytest-django, uv.

## Global Constraints

- Use `uv` for all commands: `uv run pytest ...`.
- TDD strictly (red→green): write failing tests, run them, watch them fail for the right reason, then implement.
- Conventional commit message. **Do not** credit Claude/any LLM or any person. No issue number was provided, so omit the footer.
- Run `uv run ruff check` (and fix) before committing.
- **No new model fields, no migration, no template changes.** `og_image` is already emitted into the meta tags.
- Subtitle format is the published date via `django.template.defaultfilters.date` with format string `"j F Y"` (e.g. `"25 June 2026"`); empty string when `published_at` is `None`.
- A missing/unreadable cover file must fall back to `None` (text-only card) and must never raise during save.
- Crop behaviour is unchanged — the engine centre-crops the cover to a square (parity with discography); do not add letterboxing.

## File Structure

- `apps/blog/models.py` — add `og_card()` and `_og_cover_bytes()` to the `Post` class, and one import.
- `tests/test_post_og_cover.py` *(new)* — behaviour tests for the cover card.
- `tests/test_post_og_autogen.py` *(unchanged)* — existing autogen tests must keep passing.

---

### Task 1: Post.og_card() composites the cover image

**Files:**
- Modify: `apps/blog/models.py` (imports near top; add two methods to `class Post`, which starts at line 51 — put the methods next to the existing `save()` around line 129)
- Test: `tests/test_post_og_cover.py` *(create)*

**Interfaces:**
- Consumes (already exist):
  - `SeoFieldsMixin.resolved_og_title() -> str`
  - `SeoFieldsMixin.ensure_og_image() -> bool` (called by `Post.save()`, renders via `apps.core.og.render_og_image(title, subtitle, *, cover=bytes|None)`)
  - `Post.cover_image` (`ImageField`, `upload_to="blog/"`), `Post.published_at` (`DateTimeField`, nullable)
- Produces:
  - `Post.og_card() -> tuple[str, str, bytes | None]` returning `(resolved_og_title, published_date_subtitle_or_empty, cover_bytes_or_None)`
  - `Post._og_cover_bytes() -> bytes | None`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_post_og_cover.py`:

```python
"""A blog Post with a cover_image composites it into its OG card."""

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.defaultfilters import date as date_filter
from django.utils import timezone
from PIL import Image

from apps.blog.models import Post

pytestmark = pytest.mark.django_db


def _solid_png(color=(0, 120, 200), size=(600, 600)):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def _cover_upload():
    return SimpleUploadedFile("cover.png", _solid_png(), content_type="image/png")


def test_og_card_has_published_date_subtitle_and_cover_bytes():
    when = timezone.now()
    post = Post.objects.create(
        title="Atom Bomb reissue",
        is_published=True,
        published_at=when,
        cover_image=_cover_upload(),
    )
    title, subtitle, cover = post.og_card()

    assert title == post.resolved_og_title()
    assert subtitle == date_filter(when, "j F Y")
    assert isinstance(cover, bytes) and len(cover) > 0


def test_og_card_blank_subtitle_and_no_cover_when_unpublished_and_coverless():
    post = Post.objects.create(title="Draft, no cover")
    title, subtitle, cover = post.og_card()

    assert title == post.resolved_og_title()
    assert subtitle == ""
    assert cover is None


def test_cover_changes_the_generated_card():
    when = timezone.now()
    with_cover = Post.objects.create(
        title="Same Title", published_at=when, cover_image=_cover_upload()
    )
    without_cover = Post.objects.create(title="Same Title", published_at=when)

    with with_cover.og_image.open("rb") as fh:
        a = fh.read()
    with without_cover.og_image.open("rb") as fh:
        b = fh.read()
    assert a != b  # the cover is actually composited


def test_unreadable_cover_falls_back_to_none_without_crashing():
    post = Post.objects.create(title="Broken cover", cover_image=_cover_upload())
    # Point the field at a file that doesn't exist on disk.
    post.cover_image.name = "blog/does-not-exist.png"

    assert post._og_cover_bytes() is None
    assert post.og_card()[2] is None
    post.save()  # must not raise; falls back to a text-only card
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_post_og_cover.py -v`
Expected: FAIL — `AttributeError: 'Post' object has no attribute 'og_card'` is wrong (it inherits the mixin default), so the real failures are assertion errors: `test_og_card_has_published_date_subtitle_and_cover_bytes` fails (default `og_card` returns `("...", "", None)`, so `subtitle == ""` not the date and `cover is None` not bytes) and `test_cover_changes_the_generated_card` fails (both cards identical). The two negative-path tests may already pass against the default — that's fine; the two positive ones prove the feature is missing.

- [ ] **Step 3: Add the import**

In `apps/blog/models.py`, add this import alongside the existing Django imports near the top (after `from django.db import models`):

```python
from django.template.defaultfilters import date as date_filter
```

- [ ] **Step 4: Add the two methods to `Post`**

In `apps/blog/models.py`, inside `class Post`, add these methods (place them just above the existing `def save(self, *args, **kwargs):` near line 129):

```python
    def og_card(self):
        """Title on the left, published-date subtitle, and the cover on the right.

        Mirrors the discography Release card. No cover (or an unreadable one) falls
        back to the engine's text-only card.
        """
        subtitle = date_filter(self.published_at, "j F Y") if self.published_at else ""
        return (self.resolved_og_title(), subtitle, self._og_cover_bytes())

    def _og_cover_bytes(self):
        """Cover image bytes for the OG card, or None when there's no usable cover."""
        if not self.cover_image:
            return None
        try:
            with self.cover_image.open("rb") as fh:
                return fh.read()
        except (FileNotFoundError, OSError, ValueError):
            return None
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/test_post_og_cover.py -v`
Expected: PASS (all four tests).

- [ ] **Step 6: Run the existing OG tests to confirm no regression**

Run: `uv run pytest tests/test_post_og_autogen.py tests/test_og.py tests/test_seo_og_autogen.py -v`
Expected: PASS (existing autogen + engine + SEO autogen tests unaffected).

- [ ] **Step 7: Lint & commit**

```bash
uv run ruff check apps/blog/models.py tests/test_post_og_cover.py
git add apps/blog/models.py tests/test_post_og_cover.py
git commit -m "feat(blog): composite post cover image into its OG card"
```

---

### Task 2: Full-suite verification

- [ ] **Step 1: Run the whole test suite**

Run: `uv run pytest`
Expected: all tests pass (baseline was 700; expect 704 with the four new cases).

- [ ] **Step 2: Confirm no model changes leaked into a migration**

Run: `uv run python manage.py makemigrations --check --dry-run`
Expected: "No changes detected" (this feature adds no fields).

- [ ] **Step 3: Lint the whole change**

Run: `uv run ruff check .`
Expected: no errors.

---

## Self-Review notes

- **Spec coverage:** `og_card()` + `_og_cover_bytes()` (Task 1, Step 4); published-date subtitle `"j F Y"` (Step 4 + test 1); coverless/unpublished → `("title", "", None)` (test 2); cover actually composited (test 3); unreadable cover → `None`, no crash (test 4); existing autogen preserved (Task 1 Step 6 / Task 2); no migration (Task 2 Step 2). All spec points mapped.
- **No placeholders:** every step has concrete code/commands.
- **Type consistency:** `og_card() -> (str, str, bytes | None)` and `_og_cover_bytes() -> bytes | None` are used identically in the methods and the tests; `date_filter` is the imported `django.template.defaultfilters.date`.
- **YAGNI:** no new fields, no template/admin changes, no crop changes — exactly the spec's scope.
