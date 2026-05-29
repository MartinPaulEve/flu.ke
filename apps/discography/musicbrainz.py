"""MusicBrainz mapping and idempotent upsert.

Built so the discography can later be enriched/cross-checked from MusicBrainz, but
the archived snapshot remains the data source for now (MB coverage of Fluke's
editions is incomplete). Mapping functions are pure and tested against fixtures;
upserts are keyed by MBID so snapshot data and MB data compose without duplicates.

Input dicts follow the musicbrainzngs shape (hyphenated keys, ``*-list`` arrays).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from apps.discography.models import Edition, Release, Track


@dataclass
class SyncStats:
    releases: int = 0
    editions: int = 0
    tracks: int = 0
    notes: list = field(default_factory=list)


def _year(value) -> int | None:
    if value and len(str(value)) >= 4 and str(value)[:4].isdigit():
        return int(str(value)[:4])
    return None


def parse_length(milliseconds) -> str:
    """Convert a MusicBrainz length in ms to ``m:ss`` (``''`` if unknown)."""
    if milliseconds in (None, ""):
        return ""
    total = round(int(milliseconds) / 1000)
    return f"{total // 60}:{total % 60:02d}"


def map_release_group(rg: dict) -> dict:
    """Map a release-group to Release fields (mbid, name, year)."""
    return {
        "mbid": rg["id"],
        "name": rg.get("title", ""),
        "year": _year(rg.get("first-release-date")),
    }


def map_release(release: dict) -> dict:
    """Map a release to Edition fields (mbid, catalogue_number, label, year, media)."""
    labels = release.get("label-info-list") or []
    first_label = labels[0] if labels else {}
    media = release.get("medium-list") or []
    return {
        "mbid": release["id"],
        "year": _year(release.get("date")),
        "catalogue_number": first_label.get("catalog-number", ""),
        "record_label": (first_label.get("label") or {}).get("name", ""),
        "media": media[0].get("format", "") if media else "",
    }


def map_recording(track: dict) -> dict:
    """Map a medium track to Track fields (recording_mbid, track_number, name, length)."""
    recording = track.get("recording") or {}
    return {
        "recording_mbid": recording.get("id", ""),
        "track_number": track.get("position", ""),
        "name": recording.get("title", ""),
        "length": parse_length(recording.get("length")),
    }


def _iter_tracks(release: dict):
    for medium in release.get("medium-list") or []:
        yield from medium.get("track-list") or []


def _upsert_release(fields, artist, release_type):
    release = Release.objects.filter(mbid=fields["mbid"]).first()
    if release:
        updates = {}
        if fields["name"] and release.name != fields["name"]:
            updates["name"] = fields["name"]
        if fields["year"] and release.year != fields["year"]:
            updates["year"] = fields["year"]
        if updates:
            for attr, value in updates.items():
                setattr(release, attr, value)
            release.save(update_fields=list(updates))
        return release, False
    release = Release.objects.create(
        mbid=fields["mbid"], name=fields["name"], year=fields["year"],
        artist=artist, type=release_type,
    )
    return release, True


def _upsert_edition(fields, release):
    edition = Edition.objects.filter(mbid=fields["mbid"]).first()
    if edition:
        updates = [a for a in ("catalogue_number", "record_label", "year", "media")
                   if fields[a] and getattr(edition, a) != fields[a]]
        if updates:
            for attr in updates:
                setattr(edition, attr, fields[attr])
            edition.save(update_fields=updates)
        return edition, False
    edition = Edition.objects.create(
        release=release, mbid=fields["mbid"], catalogue_number=fields["catalogue_number"],
        record_label=fields["record_label"], year=fields["year"], media=fields["media"],
    )
    return edition, True


def _upsert_track(fields, edition):
    mbid = fields["recording_mbid"] or None
    track = Track.objects.filter(recording_mbid=mbid).first() if mbid else None
    if track:
        updates = [a for a in ("name", "track_number", "length")
                   if fields[a] and getattr(track, a) != fields[a]]
        if updates:
            for attr in updates:
                setattr(track, attr, fields[attr])
            track.save(update_fields=updates)
        return track, False
    track = Track.objects.create(
        edition=edition, recording_mbid=mbid, name=fields["name"],
        track_number=fields["track_number"], length=fields["length"],
    )
    return track, True


def sync_release_groups(artist, release_type, release_groups, *, dry_run=False) -> SyncStats:
    """Upsert a list of MB release-groups (with nested releases/tracks) for an artist.

    Idempotent: matches Release by release-group MBID, Edition by release MBID and
    Track by recording MBID, creating or updating as needed without duplicating.
    """
    stats = SyncStats()
    for rg in release_groups:
        if dry_run:
            stats.releases += 1
            for release in rg.get("release-list") or []:
                stats.editions += 1
                stats.tracks += sum(1 for _ in _iter_tracks(release))
            continue
        release_obj, created = _upsert_release(map_release_group(rg), artist, release_type)
        stats.releases += int(created)
        for release in rg.get("release-list") or []:
            edition_obj, created = _upsert_edition(map_release(release), release_obj)
            stats.editions += int(created)
            for track in _iter_tracks(release):
                _, created = _upsert_track(map_recording(track), edition_obj)
                stats.tracks += int(created)
    return stats
