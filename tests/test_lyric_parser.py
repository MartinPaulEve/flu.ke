"""Unit tests for the pure archived-lyric-page parser (no database/network)."""

from pathlib import Path

import pytest

from apps.discography.parsers.lyrics import ParsedLyric, parse_lyric_page

FIXTURE = Path(__file__).parent / "fixtures" / "lyric_page.html"


@pytest.fixture(scope="module")
def parsed():
    return parse_lyric_page(FIXTURE.read_text())


def test_extracts_verses_with_line_breaks(parsed):
    # <br> becomes a newline; blank line separates the two verses.
    assert parsed.lyrics == (
        "King kong in Cannes, On a date with Spiderman,\n"
        "Dan Dar's sitting there, scared by the killer teddy bears,\n"
        "Down town Mini Mouse\n"
        "\n"
        "Judge Dredd found dead, Face down in Snoopy's bed,\n"
        "Outside Tweetie pie's, getting itchy on more supplies"
    )


def test_extracts_source_attribution_as_comment(parsed):
    assert parsed.comments == "Source: Risotto Booklet"


def test_ignores_nav_ads_and_footer(parsed):
    # Only the #content lyric body is captured — not chrome around it.
    assert "google_ad_client" not in parsed.lyrics
    assert "Home" not in parsed.lyrics
    assert "About" not in parsed.lyrics
    assert "Copyright" not in parsed.lyrics
    # The source line is a comment, not part of the lyric body.
    assert "Source" not in parsed.lyrics


def test_decodes_html_entities():
    html = '<div id="content"><p>I won&#39;t &amp; can&#39;t</p></div>'
    assert parse_lyric_page(html).lyrics == "I won't & can't"


def test_missing_content_region_returns_empty():
    assert parse_lyric_page("<html><body>no content div</body></html>") == ParsedLyric()


def test_page_without_source_has_empty_comments():
    html = '<div id="content"><p>Just a verse</p></div>'
    result = parse_lyric_page(html)
    assert result.lyrics == "Just a verse"
    assert result.comments == ""
