"""Text utilities shared across apps."""

import re

from django.utils.text import slugify

DEFAULT_SLUG = "item"

# A track number is an optional side/disc prefix (e.g. "A", "B", "i-") followed by
# digits. We zero-pad the digits to at least two so bare "1".."9" become "01".."09".
_TRACK_NUMBER_RE = re.compile(r"^([A-Za-z]*-?)(\d+)$")


def normalize_track_number(value: str) -> str:
    """Zero-pad a track number's digits to at least two ("1" → "01", "A1" → "A01").

    Leaves an already-padded or multi-digit number unchanged ("10", "A12", "01"),
    preserves a side/disc prefix ("A1" → "A01", "i-1" → "i-01"), and returns any
    value that isn't a recognised track number (or is blank) untouched.
    """
    text = (value or "").strip()
    match = _TRACK_NUMBER_RE.match(text)
    if not match:
        return text
    prefix, digits = match.group(1), match.group(2)
    return f"{prefix}{digits.zfill(2)}"


def unique_slug(value, exists, *, max_length=50, separator="-"):
    """Return a URL slug for ``value`` that is unique per the ``exists`` predicate.

    ``exists`` is a callable ``(candidate_slug: str) -> bool`` returning True when a
    slug is already taken. The base slug is derived from ``value``; if taken, an
    integer suffix (``-2``, ``-3`` …) is appended, shortening the base so the whole
    stays within ``max_length``. Decoupling from the ORM via ``exists`` keeps this
    pure and unit-testable without a database.
    """
    base = slugify(value)[:max_length] or DEFAULT_SLUG
    candidate = base
    suffix = 1
    while exists(candidate):
        suffix += 1
        tail = f"{separator}{suffix}"
        candidate = f"{base[: max_length - len(tail)]}{tail}"
    return candidate
