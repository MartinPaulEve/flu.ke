"""Text utilities shared across apps."""

from django.utils.text import slugify

DEFAULT_SLUG = "item"


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
