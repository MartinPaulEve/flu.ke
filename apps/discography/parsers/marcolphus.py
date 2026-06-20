"""Pure parser for the 2005 "Marcolphus" plain-text Fluke discography.

Like :mod:`apps.discography.parsers.snapshot`, this turns text into plain
dataclasses with no Django/ORM dependency, so it is fully unit-testable. The
``import_marcolphus`` management command does the database upserts on top of the
structures returned here, via :mod:`apps.discography.marcolphus_ingest`.

The file is divided into ``::: Section :::`` blocks. Only these sections are
imported: Fluke, Lucky Monkeys, Compilation Appearances, Collaborations and
Remixes. Bootlegs, Remixers, Unreleased/Rumoured and Samples are ignored.

Grammar (per section)
---------------------
* **Release header** ``Artist: Title    <kind> [<date>]`` — Fluke/Lucky Monkeys.
* **Edition line** ``<media>: <year> <country> (<label>; <catno>) [<notes>]``.
* **Track line** ``[<m:ss>]   <name> (<mix>)`` — length optional.
* **``[Mixers: X]``** blocks credit named remixers to specific Fluke mixes.
* In **Remixes**, ``[Artist: Title]`` headers introduce Fluke remixes of others;
  every listed track is credited to Fluke.
* In **Compilation Appearances**, ``[Track]`` groups list ``[on Various: Comp]``
  releases holding the named Fluke track(s).
* In **Collaborations**, ``[Artist: Title]`` headers introduce releases by that
  artist; trailing ``[Person: role]`` lines credit Fluke members.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Section headers that are imported, mapped to the value stored on
#: :attr:`MarcolphusRelease.section`. Anything not listed here is skipped.
IMPORTED_SECTIONS = {
    "Fluke": "Fluke",
    "Lucky Monkeys": "Lucky Monkeys",
    "Compilation Appearances": "Compilation Appearances",
    "Collaborations": "Collaborations",
    "Remixes": "Remixes",
}

VARIOUS_ARTISTS = "Various Artists"

#: Recognised release-kind words in a release header (longest first so that
#: multi-word kinds win). Each maps to nothing structural — the word itself is
#: stored on the release; the ingest maps it to a ReleaseType section.
_KINDS = (
    "live-in-the-studio album",
    "promo single",
    "split single",
    "compilation",
    "single",
    "album",
)

_SECTION_RE = re.compile(r"^:::\s*(.+?)\s*::+\s*$")
_LENGTH_RE = re.compile(r"^\d{1,3}:\d{2}$")
_YEAR_RE = re.compile(r"^\d{4}$")
# Media tokens are short, spaceless, and end in " or a known abbreviation.
_MEDIA_TOKEN_RE = re.compile(r'^[0-9]*x?(?:\d+"|LP|CD-R|CDR|CD5|CD3|CD|CSS|CS|MC|VHS)$')
_PAREN_RE = re.compile(r"\(([^)\]]*)[)\]]")
_NOTE_RE = re.compile(r"\[([^\]]*)\]")
_TRAILING_ANNOTATION_RE = re.compile(r"\s*\[[^\]]*\]\s*$")


@dataclass
class MarcolphusTrack:
    name: str = ""
    mix_info: str = ""
    length: str = ""
    remixer: str = ""


@dataclass
class MarcolphusEdition:
    media: str = ""
    catalogue_number: str = ""
    record_label: str = ""
    year: int | None = None
    country: str = ""
    notes: str = ""
    tracks: list[MarcolphusTrack] = field(default_factory=list)


@dataclass
class MarcolphusRelease:
    section: str = ""
    artist: str = ""
    name: str = ""
    year: int | None = None
    kind: str = ""
    fluke_is_remixer: bool = False
    featured_credits: list[str] = field(default_factory=list)
    editions: list[MarcolphusEdition] = field(default_factory=list)


def _clean_token(value: str) -> str:
    """Blank out placeholder tokens (``??``, ``???``, ``n/a``)."""
    value = value.strip()
    if value in ("", "??", "???", "n/a", "N/A"):
        return ""
    return value


def _strip_annotations(text: str) -> str:
    """Drop trailing ``[...]`` / ``["..."]`` editorial annotations from a line."""
    prev = None
    while prev != text:
        prev = text
        text = _TRAILING_ANNOTATION_RE.sub("", text).rstrip()
    return text


def _parse_edition_line(line: str) -> MarcolphusEdition | None:
    """Parse a single edition line into a :class:`MarcolphusEdition`.

    Returns ``None`` if the line is not an edition line.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("[") or ":" not in stripped:
        return None
    media, rest = stripped.split(":", 1)
    media = media.strip()
    if not _MEDIA_TOKEN_RE.match(media):
        return None

    edition = MarcolphusEdition(media=media)

    # Label / catalogue number from the first ( ... ) group.
    paren = _PAREN_RE.search(rest)
    if paren:
        inside = paren.group(1)
        if ";" in inside:
            label, catno = inside.split(";", 1)
        else:
            label, catno = inside, ""
        edition.record_label = _clean_token(label)
        edition.catalogue_number = _clean_token(catno)
        head = rest[: paren.start()]
    else:
        head = rest

    # Year and country come from the text before the parenthesis.
    tokens = head.split()
    for i, token in enumerate(tokens):
        if _YEAR_RE.match(token):
            edition.year = int(token)
            if i + 1 < len(tokens):
                edition.country = tokens[i + 1]
            break
    else:
        # No 4-digit year (e.g. "199?"); the country still follows the date token.
        if len(tokens) >= 2:
            edition.country = tokens[1]

    # The first [ ... ] after the parenthesis (or anywhere if no parens) is notes.
    note_search_from = paren.end() if paren else 0
    note = _NOTE_RE.search(rest, note_search_from)
    if note:
        edition.notes = note.group(1).strip()
    return edition


def _parse_track_line(line: str) -> MarcolphusTrack | None:
    """Parse a single track line into a :class:`MarcolphusTrack`.

    Returns ``None`` if the line is not a track line.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("["):
        return None

    length = ""
    first, _, remainder = stripped.partition(" ")
    if _LENGTH_RE.match(first):
        length = first
        body = remainder.strip()
    else:
        body = stripped

    body = _strip_annotations(body).strip()
    if not body:
        return None

    name, mix = body, ""
    if body.endswith(")") and "(" in body:
        idx = body.rfind("(")
        name = body[:idx].strip()
        mix = body[idx + 1 : -1].strip()
    return MarcolphusTrack(name=name, mix_info=mix, length=length)


# --------------------------------------------------------------------------- #
# Higher-level structural parsing
# --------------------------------------------------------------------------- #


def _parse_release_header(line: str) -> tuple[str, str, int | None, str] | None:
    """Parse ``Artist: Title    <kind> [<date>]`` → (artist, title, year, kind).

    Returns ``None`` if the line is not a release header.
    """
    if ":" not in line or line.startswith((" ", "\t", "[")):
        return None
    artist, rest = line.split(":", 1)
    artist = artist.strip()
    rest = rest.rstrip()
    if not artist or not rest:
        return None
    # A wide media token ("3xCD-R:") can sit at column 0 because the colon is
    # right-aligned; that is an edition line, not a release header.
    if _MEDIA_TOKEN_RE.match(artist):
        return None

    # Year from the trailing [date]; keep the 4-digit year only.
    year = None
    note = _NOTE_RE.search(rest)
    body = rest
    if note:
        body = rest[: note.start()].rstrip()
        match = re.search(r"\d{4}", note.group(1))
        if match:
            year = int(match.group(0))

    # The kind word sits at the end of the body; strip it off the title.
    kind = ""
    low = body.lower()
    for candidate in _KINDS:
        marker = " " + candidate
        idx = low.rfind(marker)
        if idx != -1 and low[idx:].strip() == candidate:
            kind = candidate
            body = body[:idx]
            break
    title = body.strip()
    return artist, title, year, kind


def _split_artist_title(text: str) -> tuple[str, str]:
    """Split a ``[Artist: Title]`` bracket body into (artist, title)."""
    text = text.strip()
    if text.startswith("on"):
        text = text[2:].lstrip(": ").strip()
    if ":" in text:
        artist, title = text.split(":", 1)
        return artist.strip(), title.strip()
    return "", text.strip()


def _attach_shared_tracks(editions, tracks):
    """Attach a copy of a parsed tracklist to every edition in a consecutive run."""
    if not tracks or not editions:
        return
    for edition in editions:
        edition.tracks = [MarcolphusTrack(**vars(t)) for t in tracks]


def _apply_mixers(release: MarcolphusRelease, mix_to_remixer: dict[str, str]):
    """Set ``track.remixer`` for tracks whose mix appears in a [Mixers:] block."""
    for edition in release.editions:
        for track in edition.tracks:
            remixer = mix_to_remixer.get(track.mix_info)
            if remixer:
                track.remixer = remixer


def parse_marcolphus(text: str) -> list[MarcolphusRelease]:
    """Parse the Marcolphus discography text into an ordered list of releases."""
    releases: list[MarcolphusRelease] = []
    section: str | None = None

    # Per-block accumulators.
    current: MarcolphusRelease | None = None
    group: list[MarcolphusEdition] = []  # current consecutive run sharing a tracklist
    pending_tracks: list[MarcolphusTrack] = []
    in_mixers = False
    mix_to_remixer: dict[str, str] = {}
    current_mixer = ""
    # Remixes/Collaborations/Compilations: the active "[Artist: Title]" header.
    header_artist = ""
    header_title = ""

    def flush_tracks():
        nonlocal pending_tracks, group
        _attach_shared_tracks(group, pending_tracks)
        pending_tracks = []
        group = []

    def start_release(release):
        nonlocal current, group, pending_tracks
        finish_release()
        current = release
        group = []
        pending_tracks = []
        releases.append(release)

    def flush_mixers():
        nonlocal in_mixers, mix_to_remixer, current_mixer
        if in_mixers and current is not None:
            _apply_mixers(current, mix_to_remixer)
        in_mixers = False
        mix_to_remixer = {}
        current_mixer = ""

    def finish_release():
        flush_tracks()
        flush_mixers()
        if current is not None and current.fluke_is_remixer:
            for edition in current.editions:
                for track in edition.tracks:
                    if not track.remixer:
                        track.remixer = "Fluke"

    for raw in text.splitlines():
        line = raw.rstrip()
        stripped = line.strip()

        section_match = _SECTION_RE.match(stripped)
        if section_match:
            finish_release()
            current = None
            group = []
            name = section_match.group(1).strip()
            section = IMPORTED_SECTIONS.get(name)
            continue

        if section is None or not stripped:
            continue

        if stripped.startswith("---") or stripped.startswith("Please ask"):
            continue

        # ---- bracketed structural lines -------------------------------- #
        if stripped.startswith("["):
            inner = stripped[1:].rstrip("]").strip()
            indent = len(line) - len(line.lstrip())

            if inner.lower().startswith("mixers:"):
                flush_tracks()
                flush_mixers()
                in_mixers = True
                continue
            if in_mixers and inner.lower().startswith("remixed by"):
                current_mixer = inner[len("remixed by") :].strip()
                continue
            if in_mixers:
                continue  # stray note inside a mixers block

            # Section-specific headers in Remixes/Collaborations/Compilations.
            if section in ("Remixes", "Collaborations", "Compilation Appearances"):
                low = inner.lower()
                if low.startswith("on "):  # a new "[on ...]" release block
                    artist, title = _split_artist_title(inner)
                    if low.startswith("on same"):
                        artist, title = header_artist, header_title
                    elif low.startswith("on various"):
                        artist = VARIOUS_ARTISTS
                    elif not artist:
                        # "[on <comp/dj-set name>]" with no Artist: prefix.
                        artist = VARIOUS_ARTISTS
                    start_release(
                        MarcolphusRelease(
                            section=section,
                            artist=artist,
                            name=title,
                            fluke_is_remixer=(section == "Remixes"),
                        )
                    )
                    continue
                if ":" in inner and section in ("Remixes", "Collaborations") and indent <= 3:
                    # "[Artist: Title]" group header (no release yet). Group
                    # headers sit at the left margin; deeper "[Person: role]"
                    # lines are credits handled below.
                    finish_release()
                    current = None
                    group = []
                    header_artist, header_title = _split_artist_title(inner)
                    continue
                if section == "Compilation Appearances" and ":" not in inner:
                    # "[Track]" group header — just records the current song.
                    finish_release()
                    current = None
                    group = []
                    header_artist, header_title = VARIOUS_ARTISTS, ""
                    continue
                if current is not None and ":" in inner and inner.split(":", 1)[1].strip():
                    # Trailing "[Person: role]" credit on a collaboration.
                    person = inner.split(":", 1)[0].strip()
                    if person and person not in current.featured_credits:
                        current.featured_credits.append(person)
                    continue
            continue  # other bracket lines are editorial notes

        # ---- release header (Fluke / Lucky Monkeys) -------------------- #
        # Checked before the mixers-block body so a column-0 header ends any
        # open [Mixers:] block instead of being swallowed as a mix line.
        if section in ("Fluke", "Lucky Monkeys") and not line.startswith((" ", "\t")):
            header = _parse_release_header(line)
            if header is not None:
                artist, title, year, kind = header
                start_release(
                    MarcolphusRelease(
                        section=section, artist=artist, name=title, year=year, kind=kind
                    )
                )
                continue

        # ---- mixers block body: track lines under a "remixed by" ------- #
        if in_mixers:
            track = _parse_track_line(line)
            if track is not None and current_mixer:
                mix_to_remixer.setdefault(track.mix_info, current_mixer)
            continue

        if current is None:
            continue

        # ---- edition / track lines ------------------------------------- #
        edition = _parse_edition_line(line)
        if edition is not None:
            # A tracklist seen since the last edition ends the consecutive run.
            if pending_tracks:
                flush_tracks()
            current.editions.append(edition)
            group.append(edition)
            continue

        track = _parse_track_line(line)
        if track is not None:
            pending_tracks.append(track)

    finish_release()
    return releases
