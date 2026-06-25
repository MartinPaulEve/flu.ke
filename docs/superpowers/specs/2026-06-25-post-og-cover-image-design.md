# Post OG cards with cover image — design

**Date:** 2026-06-25
**App:** `apps/blog` (with shared plumbing in `apps/core`)
**Status:** approved design, pending implementation

## Summary

When a blog `Post` has a `cover_image`, its auto-generated Open Graph (social
share) image should composite that cover as a full-height square on the right,
with the post's title (and a published-date subtitle) laid out on the left —
exactly the layout the discography `Release` cards already use.

Posts without a cover keep their current text-only card (no regression).

## Why it's small

The image-rendering engine already does all the hard work:

- `apps/core/og.py` `render_og_image(title, subtitle, *, cover=...)` already
  composites a centre-cropped square cover on the right and lays the text out in
  the remaining left-hand space, falling back to a text-only card when `cover` is
  `None` or unreadable.
- `apps/core/models.py` `SeoFieldsMixin.ensure_og_image()` already calls the
  model's `og_card()` on save and renders/attaches the result; `Post.save()`
  already calls `ensure_og_image()`.
- `apps/discography/models.py` `Release.og_card()` / `_og_cover_bytes()` is the
  exact pattern to mirror.

The only gap: `Post` does not override `og_card()`, so it currently falls back to
`SeoFieldsMixin`'s default `(title, "", None)` — a text-only card. We add the
override.

## Change

### `apps/blog/models.py` — `Post`

Add two methods (mirroring `Release`):

```python
def og_card(self):
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

- `date_filter` is `django.template.defaultfilters.date` (locale-aware, no
  platform `strftime` quirks). Format `"j F Y"` → e.g. `"25 June 2026"`.
- **Subtitle**: the published date, or `""` for an unpublished / date-less post.
- **Cover**: the post's `cover_image` bytes, or `None`. A missing/unreadable file
  is swallowed and falls back to `None` (text-only card) — never raises during a
  save.

### Behaviour from the existing engine (unchanged, relied upon)

- `None` cover → existing text-only card. No regression for coverless posts.
- The cover is centre-cropped to a square panel on the right, with the thin red
  accent seam — **identical to discography**. Landscape covers lose their left and
  right edges to the square crop; this is the accepted, intentional parity with the
  discography cards.
- The card stays within the 300 KB OG size cap (the engine compresses).

## Out of scope (YAGNI)

- No new model fields, no migration.
- No template changes — `og_image` is already emitted into the `<meta>` tags.
- No change to crop strategy (no letterboxing for landscape covers) — the brief is
  to mirror discography, which centre-crops to a square.
- No automatic regeneration of existing cards (see operational note).

## Operational note (not code)

`ensure_og_image()` only generates when `og_image` is **blank**, so:

- Existing posts already carry a text-only `og_image` and will **not** pick up
  their cover automatically.
- Adding/Changing a cover on an existing post will **not** auto-refresh its card.

Both are the established behaviour for every OG field today. To roll covers onto
existing posts, run `python manage.py regenerate_og` (regenerates all) or use the
admin per-object "Regenerate OG image" action / the bulk changelist action. This
is an operator step, deliberately not automated here.

## Testing (TDD, red→green)

Behaviour-focused (not asserting exact pixels or copy):

1. **`og_card()` with a cover + published date** returns
   `(title, "<date string>", <non-empty bytes>)`. The date string is the
   published date formatted (e.g. contains the year and month name).
2. **`og_card()` unpublished and coverless** returns `(title, "", None)`.
3. **Cover changes the rendered card**: a `Post` with a `cover_image` produces
   different OG image bytes than the same post without one (mirrors
   `test_cover_card_differs_from_plain_card` in `tests/test_og.py`) — i.e. the
   cover is actually composited.
4. **Unreadable/missing cover file** → `_og_cover_bytes()` returns `None` and
   saving the post still succeeds with a (text-only) card, no exception.
5. **Existing autogen still holds**: saving a `Post` still produces a `.jpg`
   `og_image` (the existing `tests/test_post_og_autogen.py` cases keep passing).

Tests use the established style: `@pytest.mark.django_db`, create `Post`
instances directly, attach a cover via `SimpleUploadedFile` with real image bytes
(a tiny solid PNG, as `tests/test_og.py` does), and assert on `og_card()` return
values and on `og_image` presence / byte differences. New cases live in
`tests/test_post_og_autogen.py` (or a sibling `tests/test_post_og_cover.py`).
