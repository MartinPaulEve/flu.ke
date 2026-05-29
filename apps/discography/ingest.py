"""Idempotent upsert of parsed snapshot data into the discography models.

Kept separate from the management command so it can be unit-tested directly with
:class:`~apps.discography.parsers.snapshot.ParsedRelease` structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.db import transaction

from apps.discography.models import (
    Artist,
    CoverImage,
    Edition,
    Lyric,
    Release,
    ReleaseType,
    Track,
)

PRIMARY_ARTIST = "Fluke"

# Display order for the known discography sections; unknown sections sort last.
SECTION_ORDER = {
    "Albums": 1,
    "Live Albums": 2,
    "Best Ofs": 3,
    "Singles": 4,
}


@dataclass
class ImportStats:
    releases: int = 0
    editions: int = 0
    tracks: int = 0
    artists: int = 0
    covers: int = 0
    lyrics: int = 0
    extras: dict = field(default_factory=dict)


def _release_artist(name: str, fluke: Artist) -> Artist:
    """Get/create a release artist, marking it an alias of Fluke unless it is Fluke."""
    artist, _ = Artist.objects.get_or_create(name=name.strip())
    if artist.pk != fluke.pk and (not artist.is_alias or artist.primary_artist_id != fluke.pk):
        artist.is_alias = True
        artist.primary_artist = fluke
        artist.save(update_fields=["is_alias", "primary_artist"])
    return artist


@transaction.atomic
def import_releases(parsed_releases) -> ImportStats:
    """Create/update discography records from parsed releases. Idempotent."""
    stats = ImportStats()
    fluke, _ = Artist.objects.get_or_create(name=PRIMARY_ARTIST)

    for parsed in parsed_releases:
        section = parsed.section or "Other"
        rtype, _ = ReleaseType.objects.get_or_create(
            name=section, defaults={"display_order": SECTION_ORDER.get(section, 99)}
        )
        artist = _release_artist(parsed.artist, fluke)
        release, created = Release.objects.get_or_create(
            artist=artist, name=parsed.name, year=parsed.year, type=rtype
        )
        stats.releases += int(created)

        for ei, parsed_edition in enumerate(parsed.editions):
            edition, created = Edition.objects.get_or_create(
                release=release,
                name=parsed_edition.name,
                catalogue_number=parsed_edition.catalogue_number,
                record_label=parsed_edition.record_label,
                year=parsed_edition.year,
                media=parsed_edition.media,
                defaults={"display_order": ei},
            )
            stats.editions += int(created)

            for ci, parsed_cover in enumerate(parsed_edition.covers):
                if not parsed_cover.url:
                    continue
                alt = (
                    f"{parsed_cover.display_name} cover of {release.name} "
                    f"by {artist.name}".strip()
                )
                _, created = CoverImage.objects.get_or_create(
                    edition=edition,
                    source_url=parsed_cover.url,
                    defaults={
                        "display_name": parsed_cover.display_name,
                        "kind": parsed_cover.kind,
                        "alt_text": alt,
                        "display_order": ci,
                    },
                )
                stats.covers += int(created)

            for ti, parsed_track in enumerate(parsed_edition.tracks):
                remixer = None
                if parsed_track.remixer:
                    remixer, _ = Artist.objects.get_or_create(name=parsed_track.remixer.strip())
                lyric = None
                if parsed_track.lyric_title:
                    lyric, created = Lyric.objects.get_or_create(
                        title=parsed_track.lyric_title, defaults={"artist": artist}
                    )
                    stats.lyrics += int(created)
                _, created = Track.objects.get_or_create(
                    edition=edition,
                    track_number=parsed_track.track_number,
                    mix_info=parsed_track.mix_info,
                    name=parsed_track.name,
                    defaults={
                        "length": parsed_track.length,
                        "remixer": remixer,
                        "sample_source_url": parsed_track.sample_url,
                        "lyric": lyric,
                        "display_order": ti,
                    },
                )
                stats.tracks += int(created)

    stats.artists = Artist.objects.count()
    return stats
