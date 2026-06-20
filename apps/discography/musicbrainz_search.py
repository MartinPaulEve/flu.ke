"""Conservative MusicBrainz matching for discography enrichment.

Pure helpers (no network, no ORM) so they can be unit-tested against fixtures.
The ``enrich_from_musicbrainz`` command feeds these the results of MusicBrainz
API calls and uses :mod:`apps.discography.musicbrainz` to do the upserts.

"Conservative" means we only accept a release-group when the normalised artist
and title agree strongly, so a wrong match never attaches the wrong tracklist to
a release. Anything uncertain is reported for manual MBID assignment instead.
"""

from __future__ import annotations

import re
import unicodedata

_PUNCT_RE = re.compile(r"[^a-z0-9]+")

#: Local media token → substring expected in the MusicBrainz format string.
_MEDIA_FORMAT = {
    '12"': '12"',
    '10"': '10"',
    '7"': '7"',
    "cd5": "cd",
    "cd3": "cd",
    "cdr": "cd",
    "cd-r": "cd",
    "cd": "cd",
    "cs": "cassette",
    "css": "cassette",
    "mc": "cassette",
    "lp": "vinyl",
}


def _fold(value: str) -> str:
    """Strip diacritics so 'Björk' and 'Bjork' compare equal."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", value) if not unicodedata.combining(c)
    )


def normalize(value: str) -> str:
    """Lower-case, strip punctuation, collapse spaces and drop a leading "the "."""
    text = _PUNCT_RE.sub(" ", _fold(value).lower()).strip()
    if text.startswith("the "):
        text = text[4:]
    return " ".join(text.split())


def artists_match(local: str, candidate: str) -> bool:
    """True when two artist names refer to the same act (normalised, VA-aware)."""
    a, b = normalize(local), normalize(candidate)
    if not a or not b:
        return False
    if a == b:
        return True
    various = {"various", "various artists"}
    if a in various and b in various:
        return True
    return False


def find_release_group(artist: str, title: str, candidates) -> str | None:
    """Return the MBID of the one confident release-group match, else ``None``.

    ``candidates`` is a list of release-group dicts in musicbrainzngs shape
    (``id``, ``title``, ``artist-credit``). A match requires both the normalised
    title and the artist to agree; ambiguous or absent matches return ``None``.
    """
    want = normalize(title)
    for candidate in candidates or []:
        if normalize(candidate.get("title", "")) != want:
            continue
        credited = " ".join(
            part.get("artist", {}).get("name", "")
            for part in candidate.get("artist-credit", [])
            if isinstance(part, dict)
        )
        if artists_match(artist, credited):
            return candidate.get("id")
    return None


def media_matches_format(media: str, mb_format: str) -> bool:
    """True when a local edition ``media`` (e.g. ``12"``) matches a MB ``format``."""
    needle = _MEDIA_FORMAT.get((media or "").strip().lower())
    if not needle:
        return False
    return needle.lower() in (mb_format or "").lower()


def resolve_catalogue_number(media: str, mb_releases) -> str:
    """Find a catalogue number for an edition of ``media`` among ``mb_releases``.

    Used to fill a blank (``???``) catalogue number from the MusicBrainz release
    of the same format. Returns ``""`` when nothing matches.
    """
    for release in mb_releases or []:
        media_list = release.get("medium-list") or []
        fmt = media_list[0].get("format", "") if media_list else ""
        if not media_matches_format(media, fmt):
            continue
        labels = release.get("label-info-list") or []
        catno = labels[0].get("catalog-number", "") if labels else ""
        if catno:
            return catno
    return ""
