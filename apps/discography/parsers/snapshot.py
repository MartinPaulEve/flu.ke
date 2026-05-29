"""Pure parser for the archived discography snapshot (``discography.html``).

The snapshot is the canonical source for the discography (no database survives).
This module turns its HTML into plain dataclasses with no Django/ORM dependency,
so it is fully unit-testable. The management command ``import_discography`` does
the database upserts on top of the structures returned here.

Snapshot grammar
----------------
* ``tr.colhead_dark``        -> a section header (ReleaseType), e.g. "Albums"
* ``tr.group.discog``        -> a release: ``<strong>YEAR - ARTIST - NAME</strong>``
* ``tr.group_artist.discog`` -> an edition: a ``swapDisplay(<id>)`` link whose text
  is a slash-separated ``[name /] [catalogue /] [label /] year / media`` line, plus
  ``[Front][Back][CD]`` cover links in a ``td.addinfo`` cell
* the hidden ``tr#<id>`` named by the edition holds a ``table.tracklist`` of track
  rows (number, title with optional ``(<mix>)`` link, ``(m:ss)``, ``[Sample]``,
  ``[Lyrics]``) interleaved with hidden ``Remixed by <strong>NAME</strong>`` rows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import unquote

from bs4 import BeautifulSoup

_YEAR_RE = re.compile(r"\d{4}")
_NUMBER_RE = re.compile(r"\d+\.")
_LENGTH_RE = re.compile(r"\(\d+:\d+\)")
_SWAP_RE = re.compile(r"swapDisplay\('([^']+)'\)")
_WAYBACK_RE = re.compile(r"/web/\d+[a-z_]*/(https?://.+)$")
_LYRIC_RE = re.compile(r"/lyrics/([^/]+)/?$")


def _original_url(href: str) -> str:
    """Strip a Wayback Machine wrapper, returning the original captured URL."""
    match = _WAYBACK_RE.search(href or "")
    return match.group(1) if match else (href or "")


def _lyric_title(url: str) -> str:
    match = _LYRIC_RE.search(url)
    return unquote(match.group(1)).strip() if match else ""


def _classify_cover_kind(display_name: str) -> str:
    low = display_name.lower()
    for needle, kind in (
        ("front", "front"),
        ("back", "back"),
        ("inlay", "inlay"),
        ("booklet", "booklet"),
        ("cd", "cd"),
    ):
        if needle in low:
            return kind
    return "other"


def _parse_release_strong(text: str) -> tuple[int | None, str, str]:
    parts = [p.strip() for p in text.split(" - ") if p.strip()]
    year: int | None = None
    if parts and _YEAR_RE.fullmatch(parts[0]):
        year = int(parts[0])
        parts = parts[1:]
    artist = parts[0] if parts else ""
    name = " - ".join(parts[1:]) if len(parts) > 1 else ""
    return year, artist, name


def _looks_like_catalogue(part: str) -> bool:
    """A catalogue number is a spaceless alphanumeric code (e.g. TPLP718CD, ASW6224-2).

    Labels ("One Little Indian") and edition names ("Australian Edition") are wordy
    and/or spaced, so this distinguishes the ambiguous middle parts of an edition line.
    """
    return bool(re.search(r"\d", part)) and " " not in part


def _parse_edition_line(text: str) -> tuple[str, str, str, int | None, str]:
    """Map a slash-separated edition line to (name, catalogue, label, year, media).

    The line is the non-empty subset of name/catalogue/label, then year, then media.
    We locate the year, treat the part after it as media, and map the parts before it,
    using :func:`_looks_like_catalogue` to disambiguate the one- and two-part cases.
    """
    parts = [p.strip() for p in text.split("/") if p.strip()]
    year: int | None = None
    year_idx: int | None = None
    for i, part in enumerate(parts):
        if _YEAR_RE.fullmatch(part):
            year = int(part)
            year_idx = i
    if year_idx is not None:
        before = parts[:year_idx]
        after = parts[year_idx + 1 :]
        media = after[0] if after else ""
    else:
        before = parts[:-1]
        media = parts[-1] if parts else ""

    name = catalogue = label = ""
    if len(before) == 1:
        if _looks_like_catalogue(before[0]):
            catalogue = before[0]
        else:
            name = before[0]
    elif len(before) == 2:
        first, second = before
        if not _looks_like_catalogue(first) and _looks_like_catalogue(second):
            name, catalogue = first, second
        elif _looks_like_catalogue(first):
            catalogue, label = first, second
        else:
            name, label = first, second
    elif len(before) >= 3:
        name, catalogue, label = before[0], before[1], before[2]
    return name, catalogue, label, year, media


@dataclass
class ParsedCover:
    display_name: str
    url: str
    kind: str


@dataclass
class ParsedTrack:
    track_number: str = ""
    name: str = ""
    mix_info: str = ""
    length: str = ""
    sample_url: str = ""
    remixer: str = ""
    lyric_title: str = ""


@dataclass
class ParsedEdition:
    name: str = ""
    catalogue_number: str = ""
    record_label: str = ""
    year: int | None = None
    media: str = ""
    covers: list[ParsedCover] = field(default_factory=list)
    tracks: list[ParsedTrack] = field(default_factory=list)


@dataclass
class ParsedRelease:
    section: str = ""
    year: int | None = None
    artist: str = ""
    name: str = ""
    editions: list[ParsedEdition] = field(default_factory=list)


def _parse_tracklist(table) -> list[ParsedTrack]:
    tracks: list[ParsedTrack] = []
    last: ParsedTrack | None = None
    for row in table.find_all("tr"):
        if row.get_text(" ", strip=True).startswith("Remixed by"):
            strong = row.find("strong")
            remixer = strong.get_text(strip=True) if strong else ""
            if last is not None and remixer:
                last.remixer = remixer
            continue

        cells = row.find_all("td", recursive=False)
        number_idx = next(
            (i for i, td in enumerate(cells) if _NUMBER_RE.fullmatch(td.get_text(strip=True))),
            None,
        )
        if number_idx is None:
            continue

        track = ParsedTrack(track_number=cells[number_idx].get_text(strip=True).rstrip("."))

        if number_idx + 1 < len(cells):
            name_cell = cells[number_idx + 1]
            full = name_cell.get_text(" ", strip=True)
            if name_cell.find("a") is not None:
                track.mix_info = name_cell.find("a").get_text(strip=True)
                track.name = full[: full.rfind("(")].strip() if "(" in full else full
            else:
                track.name = full

        for td in cells:
            text = td.get_text(strip=True)
            if _LENGTH_RE.fullmatch(text):
                track.length = text.strip("()")
            for anchor in td.find_all("a"):
                label = anchor.get_text(strip=True)
                if label == "Sample":
                    track.sample_url = _original_url(anchor.get("href", ""))
                elif label == "Lyrics":
                    track.lyric_title = _lyric_title(_original_url(anchor.get("href", "")))

        tracks.append(track)
        last = track
    return tracks


def _parse_edition(row, soup) -> ParsedEdition:
    link = row.find("a", href=lambda h: h and "swapDisplay" in h)
    line = link.get_text(strip=True) if link else ""
    name, catalogue, label, year, media = _parse_edition_line(line)
    edition = ParsedEdition(
        name=name, catalogue_number=catalogue, record_label=label, year=year, media=media
    )

    addinfo = row.find("td", class_="addinfo")
    if addinfo is not None:
        for anchor in addinfo.find_all("a"):
            display = anchor.get_text(strip=True)
            edition.covers.append(
                ParsedCover(
                    display_name=display,
                    url=_original_url(anchor.get("href", "")),
                    kind=_classify_cover_kind(display),
                )
            )

    if link is not None:
        match = _SWAP_RE.search(link.get("href", ""))
        if match:
            container = soup.find(attrs={"id": match.group(1)})
            inner = container.find("table", class_="tracklist") if container else None
            if inner is not None:
                edition.tracks = _parse_tracklist(inner)
    return edition


def parse_discography(html: str) -> list[ParsedRelease]:
    """Parse the snapshot HTML into an ordered list of :class:`ParsedRelease`."""
    soup = BeautifulSoup(html, "lxml")
    releases: list[ParsedRelease] = []
    current_section = ""
    current_release: ParsedRelease | None = None

    for row in soup.find_all("tr"):
        classes = row.get("class") or []
        if "colhead_dark" in classes:
            strong = row.find("strong")
            current_section = strong.get_text(strip=True) if strong else ""
        elif "group_artist" in classes and "discog" in classes:
            if current_release is not None:
                current_release.editions.append(_parse_edition(row, soup))
        elif "group" in classes and "discog" in classes:
            strong = row.find("strong")
            year, artist, name = _parse_release_strong(
                strong.get_text(strip=True) if strong else ""
            )
            current_release = ParsedRelease(
                section=current_section, year=year, artist=artist, name=name
            )
            releases.append(current_release)
    return releases
