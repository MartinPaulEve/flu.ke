"""Enrich the discography from MusicBrainz (idempotent, by MBID).

Built for future use: the archived snapshot remains the primary source while MB
coverage of Fluke's editions is incomplete. Honours MusicBrainz's requirements —
a descriptive User-Agent and a 1 request/second rate limit.
"""

import musicbrainzngs
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.discography.models import Artist, ReleaseType
from apps.discography.musicbrainz import sync_release_groups


class Command(BaseCommand):
    help = "Sync an artist's releases from MusicBrainz into the discography (by MBID)."

    def add_arguments(self, parser):
        parser.add_argument("--artist-mbid", required=True, help="MusicBrainz artist id.")
        parser.add_argument("--artist", default="Fluke", help="Local artist to attach to.")
        parser.add_argument("--release-type", default="Albums")
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        mb = settings.MUSICBRAINZ
        if not mb.get("contact"):
            raise CommandError("Set MUSICBRAINZ_CONTACT before querying MusicBrainz.")
        musicbrainzngs.set_useragent(mb["app"], mb["version"], mb["contact"])
        musicbrainzngs.set_rate_limit(1.0, 1)  # MusicBrainz requires <= 1 req/sec

        groups = self._fetch(options["artist_mbid"], options["limit"])
        self.stdout.write(f"Fetched {len(groups)} release groups from MusicBrainz.")

        artist, _ = Artist.objects.get_or_create(name=options["artist"])
        release_type, _ = ReleaseType.objects.get_or_create(name=options["release_type"])
        stats = sync_release_groups(artist, release_type, groups, dry_run=options["dry_run"])

        prefix = "[dry-run] " if options["dry_run"] else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}{stats.releases} releases, {stats.editions} editions, "
                f"{stats.tracks} tracks synced."
            )
        )

    def _fetch(self, artist_mbid, limit):
        """Fetch release-groups and their releases/recordings (rate-limited)."""
        browsed = musicbrainzngs.browse_release_groups(artist=artist_mbid, limit=limit)
        detailed = []
        for stub in browsed.get("release-group-list", []):
            group = musicbrainzngs.get_release_group_by_id(stub["id"], includes=["releases"])[
                "release-group"
            ]
            releases = []
            for release_stub in group.get("release-list", []):
                full = musicbrainzngs.get_release_by_id(
                    release_stub["id"], includes=["recordings", "labels", "media"]
                )["release"]
                releases.append(full)
            group["release-list"] = releases
            detailed.append(group)
        return detailed
