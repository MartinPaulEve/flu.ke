"""Unit tests for conservative MusicBrainz matching (no network)."""

from apps.discography.musicbrainz_search import (
    artists_match,
    find_release_group,
    media_matches_format,
    normalize,
    resolve_catalogue_number,
)


def _rg(mbid, title, artist):
    return {"id": mbid, "title": title, "artist-credit": [{"artist": {"name": artist}}]}


# --------------------------------------------------------------------------- #
# normalize / artists_match
# --------------------------------------------------------------------------- #


def test_normalize_strips_case_punctuation_and_leading_the():
    assert normalize("The Techno-Rose of Blighty!") == "techno rose of blighty"
    assert normalize("Out (in essence)") == "out in essence"


def test_artists_match_is_normalised():
    assert artists_match("Bjork", "Björk") is True  # punctuation/diacritic-insensitive
    assert artists_match("Fluke", "New Order") is False


def test_artists_match_various_artists_aliases():
    assert artists_match("Various Artists", "Various") is True


# --------------------------------------------------------------------------- #
# find_release_group (conservative)
# --------------------------------------------------------------------------- #


def test_find_release_group_accepts_confident_title_and_artist():
    candidates = [
        _rg("rg-wrong", "Bermuda", "Fluke"),
        _rg("rg-right", "Risotto", "Fluke"),
    ]
    assert find_release_group("Fluke", "Risotto", candidates) == "rg-right"


def test_find_release_group_rejects_when_title_differs():
    candidates = [_rg("rg-x", "Completely Different", "Fluke")]
    assert find_release_group("Fluke", "Risotto", candidates) is None


def test_find_release_group_rejects_when_artist_differs():
    # Same title, wrong artist — must not match (avoids attaching wrong data).
    candidates = [_rg("rg-x", "Spooky", "The Hangman")]
    assert find_release_group("New Order", "Spooky", candidates) is None


def test_find_release_group_none_when_no_candidates():
    assert find_release_group("Fluke", "Risotto", []) is None


# --------------------------------------------------------------------------- #
# Catalogue-number resolution by format (the ??? case)
# --------------------------------------------------------------------------- #


def test_media_matches_format():
    assert media_matches_format('12"', '12" Vinyl') is True
    assert media_matches_format("CD5", "CD") is True
    assert media_matches_format('12"', "CD") is False


def _release_with(fmt, catno):
    return {
        "medium-list": [{"format": fmt}],
        "label-info-list": [{"catalog-number": catno}],
    }


def test_resolve_catalogue_number_matches_format():
    mb_releases = [
        _release_with("CD", "657036 5034-2"),
        _release_with('12" Vinyl', "6D-12-001"),
    ]
    assert resolve_catalogue_number('12"', mb_releases) == "6D-12-001"


def test_resolve_catalogue_number_blank_when_no_format_match():
    mb_releases = [_release_with("CD", "657036 5034-2")]
    assert resolve_catalogue_number('12"', mb_releases) == ""
