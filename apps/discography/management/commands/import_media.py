"""Relocate the legacy media tree into ``media/`` and wire it to the discography.

Matches the original ``Files/...`` URLs recorded on covers and tracks to on-disk
files, copies them under ``MEDIA_ROOT`` and sets the FileFields. Unmatched audio,
archive and video files become catalogued resources. Idempotent and re-runnable.
"""

import mimetypes
import os
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.discography.media_import import (
    file_kind_for,
    match_source,
    resource_kind_for,
    sha256_of,
)
from apps.discography.models import CoverImage, Track
from apps.resources.models import Resource, ResourceFile

# Only these kinds of leftover files are catalogued as resources; loose images and
# documents are usually duplicates/scraps and would only add noise.
RESOURCE_KINDS_TO_IMPORT = {"audio", "archive", "video"}


class Command(BaseCommand):
    help = "Import the legacy media tree (Files/) and link it to the discography."

    def add_arguments(self, parser):
        parser.add_argument(
            "--files-dir",
            default=str(settings.INGEST_DIR / "public_html" / "Files"),
            help="Path to the legacy Files/ directory.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the planned mapping without copying or writing.",
        )
        parser.add_argument(
            "--hardlink",
            action="store_true",
            help="Hardlink instead of copy (same filesystem only; faster, no extra disk).",
        )

    def handle(self, *args, **options):
        files_dir = Path(options["files_dir"])
        if not files_dir.exists():
            raise CommandError(f"Files directory not found: {files_dir}")

        dry_run = options["dry_run"]
        hardlink = options["hardlink"]
        media_root = Path(settings.MEDIA_ROOT)

        relpaths, abs_by_rel, basename_index = self._index(files_dir)
        used: set[str] = set()

        covers = self._link_covers(relpaths, abs_by_rel, basename_index, media_root, dry_run,
                                   hardlink, used)
        samples = self._link_samples(relpaths, abs_by_rel, basename_index, media_root, dry_run,
                                     hardlink, used)
        resources, skipped = self._catalogue_leftovers(
            sorted(relpaths - used), abs_by_rel, media_root, dry_run, hardlink
        )

        prefix = "[dry-run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Linked {covers} covers and {samples} track samples; "
                f"catalogued {resources} resources; skipped {skipped} other files."
            )
        )

    # -- helpers ------------------------------------------------------------

    def _index(self, files_dir):
        relpaths: set[str] = set()
        abs_by_rel: dict[str, Path] = {}
        basename_index: dict[str, str] = {}
        for path in files_dir.rglob("*"):
            if path.is_file():
                rel = path.relative_to(files_dir).as_posix()
                relpaths.add(rel)
                abs_by_rel[rel] = path
                basename_index.setdefault(path.name.lower(), rel)
        return relpaths, abs_by_rel, basename_index

    def _place(self, src, media_root, dest_rel, hardlink):
        dest = Path(media_root) / dest_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            return
        if hardlink:
            try:
                os.link(src, dest)
                return
            except OSError:
                pass
        shutil.copy2(src, dest)

    def _link_covers(self, relpaths, abs_by_rel, basename_index, media_root, dry_run, hardlink, used):
        count = 0
        for cover in CoverImage.objects.exclude(source_url="").select_related(
            "edition__release"
        ):
            rel = match_source(cover.source_url, relpaths, basename_index)
            if not rel:
                continue
            used.add(rel)
            if cover.image:
                continue
            dest_rel = f"covers/{cover.edition.release.slug}/{Path(rel).name}"
            if not dry_run:
                self._place(abs_by_rel[rel], media_root, dest_rel, hardlink)
                cover.image.name = dest_rel
                cover.save(update_fields=["image"])
            count += 1
        return count

    def _link_samples(self, relpaths, abs_by_rel, basename_index, media_root, dry_run, hardlink, used):
        count = 0
        for track in Track.objects.exclude(sample_source_url=""):
            rel = match_source(track.sample_source_url, relpaths, basename_index)
            if not rel:
                continue
            used.add(rel)
            if track.sample:
                continue
            dest_rel = f"samples/{Path(rel).name}"
            if not dry_run:
                self._place(abs_by_rel[rel], media_root, dest_rel, hardlink)
                track.sample.name = dest_rel
                track.save(update_fields=["sample"])
            count += 1
        return count

    def _catalogue_leftovers(self, leftover_rels, abs_by_rel, media_root, dry_run, hardlink):
        created = 0
        skipped = 0
        for rel in leftover_rels:
            name = Path(rel).name
            kind = file_kind_for(name)
            if kind not in RESOURCE_KINDS_TO_IMPORT:
                skipped += 1
                continue
            if ResourceFile.objects.filter(original_filename=rel).exists():
                continue
            if dry_run:
                created += 1
                continue
            src = abs_by_rel[rel]
            dest_rel = f"resources/{name}"
            self._place(src, media_root, dest_rel, hardlink)
            resource = Resource.objects.create(
                title=Path(name).stem,
                kind=resource_kind_for(name),
                description="Imported from the legacy media archive.",
                is_published=False,
            )
            ResourceFile.objects.create(
                resource=resource,
                file=dest_rel,
                original_filename=rel,
                file_kind=kind,
                byte_size=src.stat().st_size,
                mime_type=mimetypes.guess_type(name)[0] or "",
                checksum=sha256_of(src),
            )
            created += 1
        return created, skipped
