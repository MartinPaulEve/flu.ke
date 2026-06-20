"""Phase 2: enrich every Release from MusicBrainz (conservative auto-match).

For each local Release this searches MusicBrainz for a release-group by artist +
title, and on a *confident* match (normalised artist and title agree) pulls down
**all** of its editions and full tracklists via
:func:`apps.discography.musicbrainz.sync_editions_for_release` — Marcolphus only
lists Fluke-relevant tracks, so MusicBrainz fills in the rest. Blank (``???``)
catalogue numbers are filled from the MusicBrainz release of the same format.

Uncertain or absent matches are left untouched and listed in the report for
manual MBID assignment (via ``musicbrainz_import``). MusicBrainz's requirements
are honoured: a descriptive User-Agent and a 1 request/second rate limit.

Usage::

    manage.py enrich_from_musicbrainz
    manage.py enrich_from_musicbrainz --artist Fluke --limit 20
    manage.py enrich_from_musicbrainz --only-missing --dry-run
"""

import musicbrainzngs
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.discography.models import Release
from apps.discography.musicbrainz import sync_editions_for_release
from apps.discography.musicbrainz_search import find_release_group, resolve_catalogue_number


class Command(BaseCommand):
    help = "Enrich Releases from MusicBrainz by conservative artist+title auto-match."

    def add_arguments(self, parser):
        parser.add_argument("--artist", help="Limit to releases by this local artist name.")
        parser.add_argument("--slug", help="Limit to the single release with this slug.")
        parser.add_argument("--limit", type=int, default=0, help="Max releases to process.")
        parser.add_argument(
            "--only-missing",
            action="store_true",
            help="Skip releases that already have a MusicBrainz id.",
        )
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        mb = settings.MUSICBRAINZ
        if not mb.get("contact"):
            raise CommandError("Set MUSICBRAINZ_CONTACT before querying MusicBrainz.")
        musicbrainzngs.set_useragent(mb["app"], mb["version"], mb["contact"])
        musicbrainzngs.set_rate_limit(1.0, 1)  # MusicBrainz requires <= 1 req/sec

        releases = Release.objects.select_related("artist").order_by("year", "name")
        if options["artist"]:
            releases = releases.filter(artist__name=options["artist"])
        if options["slug"]:
            releases = releases.filter(slug=options["slug"])
        if options["only_missing"]:
            releases = releases.filter(mbid__isnull=True)
        if options["limit"]:
            releases = releases[: options["limit"]]

        dry_run = options["dry_run"]
        matched, unmatched = [], []
        for release in releases:
            mbid = self._search(release)
            if not mbid:
                unmatched.append(release)
                self.stdout.write(f"  no confident match: {release}")
                continue
            matched.append(release)
            if dry_run:
                self.stdout.write(f"  [dry-run] would sync {release} ← {mbid}")
                continue
            self._enrich(release, mbid)
            self.stdout.write(self.style.SUCCESS(f"  synced {release} ← {mbid}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"{'[dry-run] ' if dry_run else ''}Matched {len(matched)}, "
                f"{len(unmatched)} need review."
            )
        )

    def _search(self, release):
        """Return a confident release-group MBID for ``release``, or ``None``."""
        result = musicbrainzngs.search_release_groups(
            artist=release.artist.name, releasegroup=release.name, limit=10
        )
        return find_release_group(
            release.artist.name, release.name, result.get("release-group-list", [])
        )

    def _enrich(self, release, mbid):
        """Sync editions/tracks/covers for ``release`` and fill blank cat numbers."""
        mb_releases = self._fetch(mbid)
        if release.mbid is None:
            release.mbid = mbid
            release.save(update_fields=["mbid"])
        sync_editions_for_release(release, mb_releases)
        for edition in release.editions.filter(catalogue_number=""):
            catno = resolve_catalogue_number(edition.media, mb_releases)
            if catno:
                edition.catalogue_number = catno
                edition.save(update_fields=["catalogue_number"])

    def _fetch(self, mbid):
        """Fetch a release-group's releases with tracklists, labels, media, cover art."""
        includes = ["recordings", "labels", "media"]
        group = musicbrainzngs.get_release_group_by_id(mbid, includes=["releases"])[
            "release-group"
        ]
        releases = []
        for stub in group.get("release-list", []):
            full = musicbrainzngs.get_release_by_id(stub["id"], includes=includes)["release"]
            full["cover-art"] = self._fetch_cover_art(full["id"])
            releases.append(full)
        return releases

    def _fetch_cover_art(self, release_mbid):
        try:
            images = musicbrainzngs.get_image_list(release_mbid).get("images") or []
        except musicbrainzngs.ResponseError:
            return []
        return [
            {**image, "data": musicbrainzngs.get_image(release_mbid, image["id"])}
            for image in images
        ]
