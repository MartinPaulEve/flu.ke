"""Structured-data (schema.org JSON-LD) builders.

Pure functions returning plain dicts, so they are easy to unit-test. The route
contexts serialise these to JSON and the templates emit them in a
``<script type="application/ld+json">`` tag.
"""

from __future__ import annotations


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


def music_album_jsonld(release, base_url: str) -> dict:
    """schema.org MusicAlbum (with MusicGroup artist and MusicRecording tracks)."""
    data = {
        "@context": "https://schema.org",
        "@type": "MusicAlbum",
        "name": release.name,
        "url": f"{base_url}{release.get_absolute_url()}",
        "byArtist": {"@type": "MusicGroup", "name": release.artist.name},
    }
    if release.year:
        data["datePublished"] = str(release.year)
    tracks = [
        {"@type": "MusicRecording", "name": track.display_title}
        for edition in release.editions.all()
        for track in edition.tracks.all()
    ]
    if tracks:
        data["track"] = tracks
    return data
