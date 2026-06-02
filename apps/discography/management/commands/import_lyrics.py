"""Recover lyric bodies for imported songs from the Web Archive.

The discography snapshot carried only ``[Lyrics]`` *links* (to the old
``discography.2bitpie.net/lyrics/<title>/`` pages), so ``import_discography``
created :class:`~apps.discography.models.Lyric` rows with titles but empty
bodies. This command locates the archived page for each empty lyric and
backfills its words (and source note) using the pure parser in
:mod:`apps.discography.parsers.lyrics`. It is idempotent (skips lyrics that
already have a body unless ``--force``) and polite (a short delay between
archive requests).
"""

from __future__ import annotations

import time
from urllib.parse import unquote, urlsplit

import requests
from django.core.management.base import BaseCommand

from apps.discography.models import Lyric
from apps.discography.parsers.lyrics import parse_lyric_page

CDX_URL = (
    "https://web.archive.org/cdx/search/cdx"
    "?url=discography.2bitpie.net/lyrics/*"
    "&output=json&collapse=urlkey&fl=original,timestamp,statuscode"
)
RAW_SNAPSHOT = "https://web.archive.org/web/{timestamp}id_/{url}"
USER_AGENT = "fluke.fm-lyric-recovery/1.0 (Fluke fan archive; content recovery)"


def title_from_lyric_url(url: str) -> str:
    """Return the song title encoded in a ``/lyrics/<title>/`` URL.

    Mirrors how the snapshot importer derived the lyric title, so the recovered
    pages line up with the existing :class:`Lyric` rows (``%20`` -> space, etc.).
    """
    segment = urlsplit(url).path.rstrip("/").rsplit("/lyrics/", 1)[-1]
    return unquote(segment).strip()


class Command(BaseCommand):
    help = "Backfill empty lyric bodies from the Web Archive."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Re-fetch even lyrics that already have a body.",
        )
        parser.add_argument(
            "--delay",
            type=float,
            default=0.5,
            help="Seconds to wait between archive requests (politeness).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Process at most this many lyrics (0 = all).",
        )

    def handle(self, *args, **options):
        session = requests.Session()
        session.headers["User-Agent"] = USER_AGENT

        index = self._build_index(session)
        self.stdout.write(f"Archive index: {len(index)} lyric pages.")

        targets = Lyric.objects.all() if options["force"] else Lyric.objects.filter(lyrics="")
        targets = targets.order_by("title")
        if options["limit"]:
            targets = targets[: options["limit"]]

        recovered = no_page = empty = 0
        for lyric in targets:
            capture = index.get(lyric.title.lower())
            if capture is None:
                no_page += 1
                self.stderr.write(f"  no archive page for {lyric.title!r}")
                continue

            original, timestamp = capture
            try:
                resp = session.get(
                    RAW_SNAPSHOT.format(timestamp=timestamp, url=original), timeout=60
                )
                resp.raise_for_status()
            except requests.RequestException as exc:
                no_page += 1
                self.stderr.write(f"  fetch failed for {lyric.title!r}: {exc}")
                continue

            parsed = parse_lyric_page(resp.text)
            if not parsed.lyrics:
                empty += 1
                self.stderr.write(f"  empty body parsed for {lyric.title!r}")
                continue

            lyric.lyrics = parsed.lyrics
            if parsed.comments and not lyric.comments:
                lyric.comments = parsed.comments
            lyric.save(update_fields=["lyrics", "comments", "modified"])
            recovered += 1
            self.stdout.write(f"  recovered {lyric.title!r} ({len(parsed.lyrics)} chars)")
            time.sleep(options["delay"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Done: recovered {recovered}, no-page {no_page}, empty {empty}."
            )
        )

    def _build_index(self, session):
        """Map lowercased song title -> (original_url, best_timestamp) from CDX."""
        rows = session.get(CDX_URL, timeout=60).json()
        index = {}
        for original, timestamp, status in rows[1:]:  # row 0 is the CDX header
            if status != "200":
                continue
            index[title_from_lyric_url(original).lower()] = (original, timestamp)
        return index
