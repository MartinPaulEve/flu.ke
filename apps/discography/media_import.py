"""Pure helpers for the media importer.

The discography import recorded the original ``Files/...`` URLs on each cover and
track. This module turns those URLs into matches against the on-disk media tree
and classifies leftover files into resources. Everything here is pure (no IO), so
it is unit-testable; the ``import_media`` command does the file copying.
"""

from __future__ import annotations

import hashlib
import re
from urllib.parse import unquote, urlsplit

_FILES_SPLIT_RE = re.compile(r"/Files/", re.IGNORECASE)

AUDIO_EXTS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg", ".wma"}
ARCHIVE_EXTS = {".zip", ".rar", ".7z", ".tar", ".gz"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".flv", ".mkv", ".webm", ".m4v"}

_FAN_HINTS = ("remix", "rmx", "bootleg", "mashup", "edit by", "re-edit", "rework")


def sha256_of(path, chunk_size: int = 1 << 20) -> str:
    """Return the hex sha256 of a file, read in chunks (large media-safe)."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def _ext(filename: str) -> str:
    name = filename.lower()
    dot = name.rfind(".")
    return name[dot:] if dot != -1 else ""


def file_kind_for(filename: str) -> str:
    """Classify a filename into a ResourceFile.file_kind by extension."""
    ext = _ext(filename)
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in ARCHIVE_EXTS:
        return "archive"
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    return "document"


def resource_kind_for(filename: str) -> str:
    """Heuristically classify a leftover file as 'fan' or 'official'."""
    low = filename.lower()
    return "fan" if any(hint in low for hint in _FAN_HINTS) else "official"


def _basename(url: str) -> str:
    return unquote(urlsplit(url).path).rsplit("/", 1)[-1]


def relpath_after_files(url: str) -> str | None:
    """Return the path portion after the last ``/Files/`` segment of a URL.

    e.g. ``http://x/Files/Covers/DLS/Front.jpg`` -> ``Covers/DLS/Front.jpg``.
    Returns None when the URL has no ``/Files/`` segment.
    """
    path = unquote(urlsplit(url).path)
    parts = _FILES_SPLIT_RE.split(path)
    if len(parts) < 2:
        return None
    return parts[-1].lstrip("/")


def match_source(url: str, relpaths: set[str], basename_index: dict[str, str]) -> str | None:
    """Resolve a source URL to an on-disk relpath.

    Prefers an exact ``/Files/``-relative path match; falls back to matching the
    basename (case-insensitively) via ``basename_index``. Returns None if neither
    matches.
    """
    rel = relpath_after_files(url)
    if rel and rel in relpaths:
        return rel
    return basename_index.get(_basename(url).lower())
