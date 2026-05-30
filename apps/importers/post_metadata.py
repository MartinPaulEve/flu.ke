"""Helpers for backfilling post metadata from an external list."""

from __future__ import annotations

from urllib.parse import urlsplit


def normalize_path(url: str) -> str:
    """Return a URL's path, lower-cased and without a trailing slash.

    Lets entries match posts regardless of scheme/host (http vs https,
    www vs not), since the recovered ``source_url`` and the supplied URL share
    the same path (e.g. ``/2015/07/18/some-post``).
    """
    return urlsplit(url or "").path.rstrip("/").lower()
