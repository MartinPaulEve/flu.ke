"""Import the Marcolphus plain-text discography from a .txt file.

Usage::

    manage.py import_marcolphus path/to/marcolphus.txt
    manage.py import_marcolphus path/to/marcolphus.txt --dry-run

The import is idempotent and add-only: it creates the releases, editions, tracks
and remixer credits that are missing, fills fields that are currently blank, and
never overwrites or deletes existing data. Every create and blank-fill is printed
so you can see exactly what changed; ``--dry-run`` prints the same without writing.
"""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.discography.marcolphus_ingest import import_marcolphus_releases
from apps.discography.parsers.marcolphus import parse_marcolphus


class Command(BaseCommand):
    help = "Import the Marcolphus discography from a .txt file (idempotent, add-only)."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to the Marcolphus discography .txt file.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"File not found: {path}")

        releases = parse_marcolphus(path.read_text(encoding="utf-8", errors="replace"))
        self.stdout.write(f"Parsed {len(releases)} releases from {path}.")

        stats = import_marcolphus_releases(releases, dry_run=options["dry_run"])

        prefix = "[dry-run] would " if options["dry_run"] else ""
        for change in stats.changes:
            self.stdout.write(f"  {prefix}{change.action} {change.entity}: {change.detail}")

        verb = "Would import" if options["dry_run"] else "Imported"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {stats.releases_created} releases, "
                f"{stats.editions_created} editions, {stats.tracks_created} tracks, "
                f"{stats.artists_created} artists, {stats.remixers_added} remixer credits, "
                f"{stats.featured_added} featured credits; filled {stats.fields_filled} "
                f"blank fields; skipped {stats.skipped}."
            )
        )
