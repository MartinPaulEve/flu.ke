"""Import a MusicBrainz release-group's editions (and tracks) onto a local Release.

Point at a MusicBrainz release-group (or release) URL/id and the local Release to
attach the data to, identified by slug:

    manage.py musicbrainz_import the-fruit \\
        https://musicbrainz.org/release-group/0838c153-c193-3fcc-93db-189d9ef592d9

Every release in the group is imported as an Edition — with its tracklist, track
lengths, format, catalogue number and label — using the MusicBrainz **API** (the
musicbrainzngs client; no HTML scraping). Idempotent: Editions match by release
MBID and Tracks by recording MBID, so re-running updates rather than duplicates.
MusicBrainz's requirements are honoured (descriptive User-Agent, ≤ 1 req/sec).
"""

import musicbrainzngs
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.discography.models import Release
from apps.discography.musicbrainz import parse_mbid, sync_editions_for_release


class Command(BaseCommand):
    help = "Import MusicBrainz editions/tracks onto a Release: <slug> <release-group URL or id>."

    def add_arguments(self, parser):
        parser.add_argument("slug", help="Slug of the local Release to import the editions into.")
        parser.add_argument(
            "musicbrainz", help="MusicBrainz release-group (or release) URL or MBID."
        )
        parser.add_argument("--dry-run", action="store_true", help="Report without saving.")

    def handle(self, *args, **options):
        try:
            release = Release.objects.get(slug=options["slug"])
        except Release.DoesNotExist:
            raise CommandError(f"No Release with slug {options['slug']!r}.") from None

        try:
            entity_type, mbid = parse_mbid(options["musicbrainz"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        mb = settings.MUSICBRAINZ
        if not mb.get("contact"):
            raise CommandError("Set MUSICBRAINZ_CONTACT before querying MusicBrainz.")
        musicbrainzngs.set_useragent(mb["app"], mb["version"], mb["contact"])
        musicbrainzngs.set_rate_limit(1.0, 1)  # MusicBrainz requires <= 1 req/sec

        mb_releases = self._fetch(entity_type, mbid)
        self.stdout.write(f"Fetched {len(mb_releases)} edition(s) from MusicBrainz.")

        stats = sync_editions_for_release(release, mb_releases, dry_run=options["dry_run"])
        prefix = "[dry-run] " if options["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}Imported {stats.editions} edition(s) and {stats.tracks} track(s) "
                f"into “{release.name}”."
            )
        )

    def _fetch(self, entity_type, mbid):
        """Fetch the release(s) with tracklists, formats and labels (rate-limited)."""
        includes = ["recordings", "labels", "media"]
        if entity_type == "release":
            return [musicbrainzngs.get_release_by_id(mbid, includes=includes)["release"]]
        group = musicbrainzngs.get_release_group_by_id(mbid, includes=["releases"])["release-group"]
        releases = []
        for stub in group.get("release-list", []):
            releases.append(
                musicbrainzngs.get_release_by_id(stub["id"], includes=includes)["release"]
            )
        return releases
