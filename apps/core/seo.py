"""Structured-data (schema.org JSON-LD) builders.

Pure functions returning plain dicts, so they are easy to unit-test. The route
contexts serialise these to JSON and the templates emit them in a
``<script type="application/ld+json">`` tag.
"""

from __future__ import annotations

import json


def jsonld_dumps(data) -> str:
    """Serialise a JSON-LD dict for safe inline ``<script>`` embedding.

    Escapes ``<``, ``>`` and ``&`` as unicode escapes (valid JSON) so values can
    never break out of the script element (e.g. a title containing ``</script>``).
    """
    return (
        json.dumps(data, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def blog_posting_jsonld(post, base_url: str) -> dict:
    """schema.org BlogPosting for a blog post."""
    data = {
        "@context": "https://schema.org",
        "@type": "BlogPosting",
        "headline": post.title,
        "url": f"{base_url}{post.get_absolute_url()}",
    }
    if post.published_at:
        data["datePublished"] = post.published_at.isoformat()
    if post.meta_description:
        data["description"] = post.meta_description
    if post.og_image:
        data["image"] = f"{base_url}{post.og_image.url}"
    return data


def _artist_node(artist, base_url: str) -> dict:
    """A typed schema.org node for an artist — Person or MusicGroup, with a URL."""
    return {
        "@type": artist.schema_type,
        "name": artist.name,
        "url": f"{base_url}{artist.get_absolute_url()}",
    }


def _iso8601_duration(length: str) -> str:
    """Convert an ``m:ss`` (or ``h:mm:ss``) length to an ISO 8601 duration."""
    parts = (length or "").strip().split(":")
    if len(parts) not in (2, 3) or not all(p.isdigit() for p in parts):
        return ""
    nums = [int(p) for p in parts]
    hours, minutes, seconds = ((0, *nums) if len(nums) == 2 else nums)
    return f"PT{f'{hours}H' if hours else ''}{minutes}M{seconds}S"


def _music_release_format(media: str) -> str | None:
    """Map an edition's media string to a schema.org MusicReleaseFormatType."""
    m = (media or "").lower()
    if "vinyl" in m or "lp" in m:
        return "https://schema.org/VinylFormat"
    if "cassette" in m or "tape" in m:
        return "https://schema.org/CassetteFormat"
    if "digital" in m or "download" in m or "stream" in m:
        return "https://schema.org/DigitalFormat"
    if "cd" in m:
        return "https://schema.org/CDFormat"
    return None


def _release_cover_url(release, base_url: str) -> str | None:
    """Absolute URL of the front cover (or any cover) — from prefetched data."""
    fallback = None
    for edition in release.editions.all():
        for cover in edition.covers.all():
            if not cover.image:
                continue
            fallback = fallback or cover
            if cover.kind == "front":
                return f"{base_url}{cover.image.url}"
    return f"{base_url}{fallback.image.url}" if fallback else None


def _track_node(track, by_artist, base_url: str) -> dict:
    node = {"@type": "MusicRecording", "name": track.display_title, "byArtist": by_artist}
    if track.track_number:
        node["position"] = track.track_number
    duration = _iso8601_duration(track.length)
    if duration:
        node["duration"] = duration
    remixers = [_artist_node(r, base_url) for r in track.remixers.all()]
    if remixers:
        node["contributor"] = remixers
    return node


def music_album_jsonld(release, base_url: str) -> dict:
    """schema.org MusicAlbum: typed artists, a tracklist of MusicRecordings, and
    each edition as a MusicRelease (format, catalogue number, label, date)."""
    by_artist = [_artist_node(a, base_url) for a in release.all_artists]
    data = {
        "@context": "https://schema.org",
        "@type": "MusicAlbum",
        "name": release.display_name,
        "url": f"{base_url}{release.get_absolute_url()}",
        "byArtist": by_artist,
    }
    if release.year:
        data["datePublished"] = str(release.year)
    cover = _release_cover_url(release, base_url)
    if cover:
        data["image"] = cover

    editions = list(release.editions.all())
    # Canonical tracklist from the first edition (editions usually share it).
    tracks = [_track_node(t, by_artist, base_url) for t in editions[0].tracks.all()] if editions else []
    if tracks:
        data["numTracks"] = len(tracks)
        data["track"] = tracks

    album_release = []
    for edition in editions:
        node = {
            "@type": "MusicRelease",
            "name": edition.summary_lead or release.display_name,
            "url": f"{base_url}{release.get_absolute_url()}",
        }
        fmt = _music_release_format(edition.media)
        if fmt:
            node["musicReleaseFormat"] = fmt
        if edition.catalogue_number:
            node["catalogNumber"] = edition.catalogue_number
        if edition.record_label:
            node["recordLabel"] = {"@type": "Organization", "name": edition.record_label}
        if edition.year:
            node["datePublished"] = str(edition.year)
        album_release.append(node)
    if album_release:
        data["albumRelease"] = album_release
    return data


def music_group_jsonld(artist, releases, base_url: str) -> dict:
    """schema.org Person/MusicGroup for an artist, with its discography as albums."""
    data = {
        "@context": "https://schema.org",
        "@type": artist.schema_type,
        "name": artist.name,
        "url": f"{base_url}{artist.get_absolute_url()}",
    }
    if artist.biography:
        data["description"] = artist.biography
    if artist.og_image:
        data["image"] = f"{base_url}{artist.og_image.url}"
    if artist.is_alias and artist.primary_artist_id:
        data["memberOf"] = _artist_node(artist.primary_artist, base_url)
    albums = [
        {
            "@type": "MusicAlbum",
            "name": r.display_name,
            "url": f"{base_url}{r.get_absolute_url()}",
        }
        for r in releases
    ]
    if albums:
        data["album"] = albums
    return data


def discography_jsonld(releases, base_url: str) -> dict:
    """schema.org CollectionPage wrapping an ItemList of every release."""
    return {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "Discography",
        "url": f"{base_url}/discography/",
        "mainEntity": {
            "@type": "ItemList",
            "numberOfItems": len(releases),
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": i + 1,
                    "name": r.display_title,
                    "url": f"{base_url}{r.get_absolute_url()}",
                }
                for i, r in enumerate(releases)
            ],
        },
    }
