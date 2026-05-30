"""Clean imported post bodies.

Strips WordPress social-share / "Related posts" cruft and remaps legacy
``…/Files/…`` image and file URLs to local media. A referenced file is reused
from the existing media library when present, otherwise copied from the Ingest
archive into ``media/posts/…`` (skipped, with a report, if media isn't writable).
Idempotent; supports --dry-run.
"""

import os
import re
import shutil
from pathlib import Path
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.blog.body_clean import clean_body_html
from apps.blog.models import Post

_FILES_RE = re.compile(r"/Files/(.+)$", re.I)


def _index(root: Path):
    """basename(lower) -> relpath, for every file under root."""
    index = {}
    if root.exists():
        for dirpath, _dirs, names in os.walk(root):
            for name in names:
                rel = os.path.relpath(os.path.join(dirpath, name), root)
                index.setdefault(name.lower(), rel)
    return index


class Command(BaseCommand):
    help = "Strip share/related cruft and remap legacy Files/ URLs in post bodies."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        media_root = Path(settings.MEDIA_ROOT)
        ingest_files = Path(settings.INGEST_DIR) / "public_html" / "Files"
        media_index = _index(media_root)
        ingest_index = _index(ingest_files)
        media_writable = media_root.exists() and os.access(media_root, os.W_OK)
        skipped = set()

        def resolver(url):
            match = _FILES_RE.search(unquote(urlsplit(url).path))
            if not match:
                return None
            rel = match.group(1)
            base = rel.rsplit("/", 1)[-1].lower()
            # 1. Reuse a file already in the media library.
            if base in media_index:
                return settings.MEDIA_URL + media_index[base]
            # 2. Otherwise copy it from the Ingest archive into media/posts/.
            src_rel = rel if (ingest_files / rel).is_file() else ingest_index.get(base)
            if not src_rel:
                return None
            dest_rel = f"posts/{src_rel}"
            if not media_writable:
                skipped.add(url)
                return None
            if not dry_run:
                dest = media_root / dest_rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    shutil.copy2(ingest_files / src_rel, dest)
                media_index[base] = dest_rel
            return settings.MEDIA_URL + dest_rel

        changed = total_removed = total_remapped = 0
        for post in Post.objects.exclude(body=""):
            cleaned, removed, remapped = clean_body_html(post.body, resolver)
            if cleaned != post.body:
                changed += 1
                total_removed += removed
                total_remapped += remapped
                if not dry_run:
                    Post.objects.filter(pk=post.pk).update(body=cleaned)

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Cleaned {changed} posts: removed {total_removed} share/related "
                f"blocks, remapped {total_remapped} Files/ URLs."
            )
        )
        if skipped:
            self.stdout.write(
                f"  {len(skipped)} URLs need files copied into media/, but media/ is not "
                f"writable. Fix permissions (e.g. `sudo chown -R $(id -u):$(id -g) media`) "
                f"and re-run to remap them."
            )
