"""Import the discography from the archived snapshot (``discography.html``)."""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.discography.ingest import import_releases
from apps.discography.parsers.snapshot import parse_discography


class Command(BaseCommand):
    help = "Import the discography by parsing the archived discography.html snapshot."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default=str(settings.INGEST_DIR / "discography.html"),
            help="Path to the discography.html snapshot.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and report counts without writing to the database.",
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"Snapshot not found: {path}")

        releases = parse_discography(path.read_text(encoding="utf-8", errors="replace"))
        self.stdout.write(f"Parsed {len(releases)} releases from {path}.")

        if options["dry_run"]:
            editions = sum(len(r.editions) for r in releases)
            tracks = sum(len(e.tracks) for r in releases for e in r.editions)
            self.stdout.write(f"[dry-run] {editions} editions, {tracks} tracks. No changes made.")
            return

        stats = import_releases(releases)
        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {stats.releases} releases, {stats.editions} editions, "
                f"{stats.tracks} tracks, {stats.artists} artists, "
                f"{stats.covers} covers, {stats.lyrics} lyrics."
            )
        )
