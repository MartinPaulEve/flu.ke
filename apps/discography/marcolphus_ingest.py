"""Idempotent, add-only upsert of parsed Marcolphus data into the discography.

Kept separate from the management command so it can be unit-tested directly with
:class:`~apps.discography.parsers.marcolphus.MarcolphusRelease` structures.

Safety contract
---------------
* **Add-only / fill-blank.** Missing releases, editions, tracks and remixer
  credits are created; a field that is currently blank on an existing record may
  be filled, but a non-empty value is **never overwritten** and nothing is ever
  deleted.
* **Idempotent.** A second run makes no further changes.
* Every create and blank-fill is recorded on the returned :class:`MarcolphusStats`
  so the command can print exactly what changed (or would change, under dry-run).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.db import transaction

from apps.discography.models import (
    PRIMARY_ARTIST_NAME,
    Artist,
    Edition,
    Release,
    ReleaseType,
    Track,
)

PLACEHOLDER_NAMES = {"", "?", "??", "???"}

#: Names that resolve to Fluke aliases (compared case-insensitively, spaces
#: ignored). Their releases hang off Fluke via ``Artist.primary_artist``.
ALIAS_NAMES = {"lucky monkeys": "Lucky Monkeys", "2bitpie": "2 Bit Pie"}

#: The four members of Fluke. A credit naming any of them signals Fluke.
FLUKE_MEMBERS = {"Jon Fugler", "Mike Tournier", "Mike Bryant", "Julian Nugent"}

#: Release-kind word (Fluke / Lucky Monkeys releases) → ReleaseType section name.
KIND_TO_TYPE = {
    "album": "Albums",
    "live-in-the-studio album": "Live Albums",
    "compilation": "Best Ofs",
    "single": "Singles",
    "promo single": "Singles",
    "split single": "Singles",
    "": "Singles",
}

#: Section → ReleaseType for the non-Fluke sections.
SECTION_TO_TYPE = {
    "Remixes": "Remixes",
    "Collaborations": "Collaborations",
    "Compilation Appearances": "Compilation Appearances",
}

#: Display order for ReleaseTypes created by this importer (existing ones keep
#: their order; these sort after the existing 1–5).
TYPE_ORDER = {
    "Albums": 1,
    "Live Albums": 2,
    "Best Ofs": 3,
    "EPs": 4,
    "Singles": 5,
    "Compilation Appearances": 6,
    "Collaborations": 7,
    "Remixes": 8,
}


@dataclass
class Change:
    action: str  # "create" or "fill"
    entity: str  # Release / Edition / Track / Artist / remixer / featured
    detail: str


@dataclass
class MarcolphusStats:
    releases_created: int = 0
    editions_created: int = 0
    tracks_created: int = 0
    artists_created: int = 0
    remixers_added: int = 0
    featured_added: int = 0
    fields_filled: int = 0
    skipped: int = 0
    changes: list[Change] = field(default_factory=list)


class _Rollback(Exception):
    """Internal signal to abort and roll back a dry-run transaction."""


def _alias_canonical(name: str) -> str | None:
    """Return the canonical alias name for ``name``, or ``None`` if not an alias."""
    key = name.lower().replace(" ", "")
    if key == PRIMARY_ARTIST_NAME.lower():
        return PRIMARY_ARTIST_NAME
    return ALIAS_NAMES.get(key)


def _get_or_create_artist(name: str, stats: MarcolphusStats, *, alias_of=None) -> Artist:
    """Get/create an artist, recording creation and (for aliases) linking to Fluke."""
    artist, created = Artist.objects.get_or_create(name=name)
    if created:
        stats.artists_created += 1
        stats.changes.append(Change("create", "Artist", name))
    if alias_of is not None and artist.pk != alias_of.pk:
        if not artist.is_alias or artist.primary_artist_id != alias_of.pk:
            artist.is_alias = True
            artist.primary_artist = alias_of
            artist.save(update_fields=["is_alias", "primary_artist"])
    return artist


def _resolve_release_artist(parsed, fluke: Artist, stats: MarcolphusStats) -> Artist:
    """Resolve the owning artist for a parsed release (alias-aware)."""
    canonical = _alias_canonical(parsed.artist)
    if canonical == PRIMARY_ARTIST_NAME:
        return fluke
    if canonical is not None:  # a Fluke alias (Lucky Monkeys, 2 Bit Pie)
        return _get_or_create_artist(canonical, stats, alias_of=fluke)
    # Lucky Monkeys / Fluke sections own everything via Fluke even if unnamed.
    if parsed.section in ("Fluke", "Lucky Monkeys"):
        return _get_or_create_artist(parsed.artist, stats, alias_of=fluke)
    return _get_or_create_artist(parsed.artist, stats)


def _release_type(parsed, stats: MarcolphusStats) -> ReleaseType:
    name = SECTION_TO_TYPE.get(parsed.section) or KIND_TO_TYPE.get(parsed.kind, "Singles")
    rtype, created = ReleaseType.objects.get_or_create(
        name=name, defaults={"display_order": TYPE_ORDER.get(name, 99)}
    )
    return rtype


def _fill_blanks(obj, values: dict, stats: MarcolphusStats, label: str) -> None:
    """Fill only the currently-blank fields of ``obj`` (never overwrite)."""
    filled = []
    for attr, value in values.items():
        if value and not getattr(obj, attr):
            setattr(obj, attr, value)
            filled.append(attr)
    if filled:
        obj.save(update_fields=filled)
        stats.fields_filled += len(filled)
        for attr in filled:
            stats.changes.append(Change("fill", label, f"{obj} · {attr}={values[attr]!r}"))


def _match_release(artist, name, year):
    qs = Release.objects.filter(artist=artist, name__iexact=name)
    if year is not None:
        match = qs.filter(year=year).first()
        if match:
            return match
    return qs.first()


def _match_edition(release, parsed_edition):
    qs = release.editions.all()
    if parsed_edition.catalogue_number:
        return qs.filter(catalogue_number__iexact=parsed_edition.catalogue_number).first()
    return qs.filter(
        media__iexact=parsed_edition.media, year=parsed_edition.year, catalogue_number=""
    ).first()


def _upsert_track(edition, parsed_track, order, fluke, stats) -> None:
    track = edition.tracks.filter(
        name__iexact=parsed_track.name, mix_info__iexact=parsed_track.mix_info
    ).first()
    if track is None:
        track = Track.objects.create(
            edition=edition, name=parsed_track.name, mix_info=parsed_track.mix_info,
            length=parsed_track.length, display_order=order,
        )
        stats.tracks_created += 1
        stats.changes.append(Change("create", "Track", f"{edition} · {track.display_title}"))
    else:
        _fill_blanks(track, {"length": parsed_track.length}, stats, "Track")

    if parsed_track.remixer:
        remixer = fluke if parsed_track.remixer == PRIMARY_ARTIST_NAME else \
            _get_or_create_artist(parsed_track.remixer, stats)
        if not track.remixers.filter(pk=remixer.pk).exists():
            track.remixers.add(remixer)
            stats.remixers_added += 1
            stats.changes.append(
                Change("create", "remixer", f"{track.display_title} ← {remixer.name}")
            )


def _import_one(parsed, fluke, stats) -> None:
    if parsed.name.strip() in PLACEHOLDER_NAMES:
        stats.skipped += 1
        return
    artist = _resolve_release_artist(parsed, fluke, stats)
    rtype = _release_type(parsed, stats)

    release = _match_release(artist, parsed.name, parsed.year)
    if release is None:
        release = Release.objects.create(
            artist=artist, name=parsed.name, year=parsed.year, type=rtype
        )
        stats.releases_created += 1
        stats.changes.append(Change("create", "Release", str(release)))

    for person in parsed.featured_credits:
        if person in FLUKE_MEMBERS and not release.featured_artists.filter(pk=fluke.pk).exists():
            release.featured_artists.add(fluke)
            stats.featured_added += 1
            stats.changes.append(Change("create", "featured", f"{release.name} feat. Fluke"))

    for ei, parsed_edition in enumerate(parsed.editions):
        edition = _match_edition(release, parsed_edition)
        if edition is None:
            edition = Edition.objects.create(
                release=release, media=parsed_edition.media,
                catalogue_number=parsed_edition.catalogue_number,
                record_label=parsed_edition.record_label, year=parsed_edition.year,
                display_order=ei,
            )
            stats.editions_created += 1
            stats.changes.append(Change("create", "Edition", str(edition)))
        else:
            _fill_blanks(
                edition,
                {
                    "record_label": parsed_edition.record_label,
                    "catalogue_number": parsed_edition.catalogue_number,
                    "media": parsed_edition.media,
                    "year": parsed_edition.year,
                },
                stats,
                "Edition",
            )
        for ti, parsed_track in enumerate(parsed_edition.tracks):
            _upsert_track(edition, parsed_track, ti, fluke, stats)


def import_marcolphus_releases(parsed_releases, *, dry_run: bool = False) -> MarcolphusStats:
    """Upsert parsed Marcolphus releases. Idempotent and add-only.

    With ``dry_run=True`` the work runs inside a rolled-back transaction so the
    returned stats describe exactly what *would* change, writing nothing.
    """
    stats = MarcolphusStats()
    try:
        with transaction.atomic():
            fluke, created = Artist.objects.get_or_create(name=PRIMARY_ARTIST_NAME)
            if created:
                stats.artists_created += 1
                stats.changes.append(Change("create", "Artist", PRIMARY_ARTIST_NAME))
            for parsed in parsed_releases:
                _import_one(parsed, fluke, stats)
            if dry_run:
                raise _Rollback()
    except _Rollback:
        pass
    return stats
