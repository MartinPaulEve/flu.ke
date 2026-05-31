"""Surface the legacy album/live-set/remix archives as downloadable resources.

``import_media`` catalogued the archives under ``Files/`` but left them unpublished
and created duplicate records for a nested ``Files/Files/`` tree. It also never saw
two content archives that sit directly under ``public_html/``. This command finishes
the job in three idempotent, re-runnable steps:

1. Import the loose stragglers (``Fatal-Occupied.zip``, ``X-Files.zip``), published.
2. Dedupe archive resources that point at the same media file.
3. Publish every resource that has an archive file.

The 10 GB site-backup zips (``2bitpie.zip``) are never imported.
"""

from __future__ import annotations

import mimetypes
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.discography.media_import import file_kind_for, resource_kind_for, sha256_of
from apps.resources.models import Resource, ResourceFile

# Site backups, not content; these must never be copied or catalogued.
EXCLUDED_ARCHIVE_NAMES = frozenset({"2bitpie.zip"})


def prettify_title(filename: str) -> str:
    """Turn an archive filename into a human-readable title.

    Strips the extension and replaces ``_`` / ``-`` with spaces, collapsing the
    result. Falls back to the stem (or the raw name) for odd inputs so it never
    raises.
    """
    stem = Path(filename or "").stem
    cleaned = stem.replace("_", " ").replace("-", " ")
    return " ".join(cleaned.split())


class Command(BaseCommand):
    help = "Import loose archives, dedupe archive resources, and publish them."

    def add_arguments(self, parser):
        parser.add_argument(
            "--public-html",
            default=str(settings.INGEST_DIR / "public_html"),
            help="Path to the legacy public_html/ directory.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the plan without copying or writing anything.",
        )

    def handle(self, *args, **options):
        public_html = Path(options["public_html"])
        if not public_html.exists():
            raise CommandError(f"public_html directory not found: {public_html}")

        dry_run = options["dry_run"]
        media_root = Path(settings.MEDIA_ROOT)

        imported = self._import_stragglers(public_html, media_root, dry_run)
        removed = self._dedupe_archives(dry_run)
        published = self._publish_archives(dry_run)

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Imported {imported} loose archive(s); "
                f"removed {removed} duplicate resource(s); "
                f"published {published} archive resource(s)."
            )
        )

    # -- step 1: import stragglers -----------------------------------------

    def _import_stragglers(self, public_html, media_root, dry_run):
        """Import content archives sitting directly under ``public_html/``.

        Only top-level ``*.zip`` files are considered (the nested ``Files/`` tree
        belongs to ``import_media``). Site backups are excluded by name. Idempotent:
        a file already recorded by name or by checksum is skipped.
        """
        imported = 0
        for src in sorted(public_html.glob("*.zip")):
            name = src.name
            if name in EXCLUDED_ARCHIVE_NAMES:
                continue
            if ResourceFile.objects.filter(original_filename=name).exists():
                continue
            checksum = sha256_of(src)
            if checksum and ResourceFile.objects.filter(checksum=checksum).exists():
                continue
            if dry_run:
                self.stdout.write(f"[dry-run] would import straggler: {name}")
                imported += 1
                continue
            dest_rel = f"resources/{name}"
            dest = media_root / dest_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            if not dest.exists():
                shutil.copy2(src, dest)
            resource = Resource.objects.create(
                title=prettify_title(name),
                kind=resource_kind_for(name),
                description="Imported from the legacy media archive.",
                is_published=True,
            )
            ResourceFile.objects.create(
                resource=resource,
                file=dest_rel,
                original_filename=name,
                file_kind=file_kind_for(name),
                byte_size=src.stat().st_size,
                mime_type=mimetypes.guess_type(name)[0] or "",
                checksum=checksum,
            )
            imported += 1
        return imported

    # -- step 2: dedupe -----------------------------------------------------

    def _dedupe_archives(self, dry_run):
        """Collapse archive resources that point at the same media file.

        For each set of archive ResourceFiles sharing a ``file`` name, keep one
        record (preferring an ``original_filename`` that does NOT start with
        ``Files/``) and delete the redundant Resource(s) and ResourceFile(s). The
        shared file on disk is left untouched — the kept record still needs it.
        """
        groups: dict[str, list[ResourceFile]] = {}
        for rf in ResourceFile.objects.filter(file_kind="archive").select_related("resource"):
            groups.setdefault(rf.file.name, []).append(rf)

        removed = 0
        for members in groups.values():
            if len(members) < 2:
                continue
            keep = min(
                members,
                key=lambda rf: (rf.original_filename.startswith("Files/"), rf.id),
            )
            for rf in members:
                if rf.id == keep.id:
                    continue
                if dry_run:
                    self.stdout.write(
                        f"[dry-run] would remove duplicate: {rf.original_filename!r} "
                        f"(keeping {keep.original_filename!r})"
                    )
                    removed += 1
                    continue
                resource = rf.resource
                rf.delete()
                # Drop the now-orphaned Resource (it carried only this duplicate).
                if not resource.files.exists():
                    resource.delete()
                removed += 1
        return removed

    # -- step 3: publish ----------------------------------------------------

    def _publish_archives(self, dry_run):
        """Publish every Resource that has an archive file."""
        unpublished = Resource.objects.filter(
            files__file_kind="archive", is_published=False
        ).distinct()
        if dry_run:
            count = unpublished.count()
            for resource in unpublished:
                self.stdout.write(f"[dry-run] would publish: {resource.title!r}")
            return count
        return unpublished.update(is_published=True)
