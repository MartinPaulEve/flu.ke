"""Pure parser for an archived lyric page from ``discography.2bitpie.net``.

The old site served one WordPress page per song at ``/lyrics/<title>/``. The
discography import captured only the lyric *titles* (from the ``[Lyrics]`` links),
never the bodies. This module turns a fetched lyric page into plain text — the
lyric itself plus any source attribution — so ``import_lyrics`` can backfill the
empty :class:`~apps.discography.models.Lyric` rows. No Django/ORM/network
dependency, so it is fully unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass

from bs4 import BeautifulSoup


@dataclass
class ParsedLyric:
    lyrics: str = ""
    comments: str = ""


def _clean_paragraph(text: str) -> str:
    """Strip each line and drop blank ones, preserving intentional line breaks."""
    lines = (line.strip() for line in text.split("\n"))
    return "\n".join(line for line in lines if line)


def parse_lyric_page(html: str) -> ParsedLyric:
    """Parse a fetched lyric page into its body text and source comment.

    Returns an empty :class:`ParsedLyric` when the page has no ``#content`` region.
    """
    soup = BeautifulSoup(html, "lxml")
    content = soup.find(id="content")
    if content is None:
        return ParsedLyric()

    # Drop ad scripts and styling noise that share the content region.
    for tag in content.find_all(["script", "style", "ins"]):
        tag.decompose()

    # The source/attribution line is italicised; lift it out as a comment and
    # remove it so it never bleeds into the lyric body.
    comment_bits = []
    for tag in content.find_all(["i", "em"]):
        text = tag.get_text(" ", strip=True)
        if text:
            comment_bits.append(text)
        tag.decompose()

    # Turn <br> into hard newlines before extracting text.
    for br in content.find_all("br"):
        br.replace_with("\n")

    paragraphs = [
        cleaned for p in content.find_all("p") if (cleaned := _clean_paragraph(p.get_text()))
    ]

    return ParsedLyric(
        lyrics="\n\n".join(paragraphs).strip(),
        comments=" ".join(comment_bits).strip(),
    )
