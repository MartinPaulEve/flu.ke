"""Render routes to files and sync media/static into the build directory."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


def output_path_for(url_path: str) -> str:
    """Map a URL path to its static output file, relative to the build root.

    ``/`` -> ``index.html``; ``/news/`` -> ``news/index.html``; a path with a file
    extension (``/sitemap.xml``) maps to itself so it is served verbatim.
    """
    path = url_path.strip("/")
    if not path:
        return "index.html"
    last_segment = path.rsplit("/", 1)[-1]
    if "." in last_segment:
        return path
    return f"{path}/index.html"


def fingerprint(template: str, context_keys, html: str) -> str:
    """Stable content hash for a rendered route, used for incremental rebuilds."""
    digest = hashlib.sha256()
    digest.update(template.encode("utf-8"))
    digest.update("|".join(sorted(context_keys)).encode("utf-8"))
    digest.update(html.encode("utf-8"))
    return digest.hexdigest()


def sync_tree(src: Path, dest: Path) -> int:
    """Copy ``src`` into ``dest`` incrementally, skipping files unchanged by size+mtime.

    Returns the number of files copied. Used for both the media and static trees so
    republishing a ~10 GB media library only writes what actually changed.
    """
    src, dest = Path(src), Path(dest)
    if not src.exists():
        return 0
    copied = 0
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        target = dest / path.relative_to(src)
        if target.exists():
            s, t = path.stat(), target.stat()
            if s.st_size == t.st_size and int(s.st_mtime) <= int(t.st_mtime):
                continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied += 1
    return copied


def load_manifest(path: Path) -> dict:
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else {}


def save_manifest(path: Path, data: dict) -> None:
    Path(path).write_text(json.dumps(data, sort_keys=True))
