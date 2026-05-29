"""Unit tests for the pure discography snapshot parser (no database)."""

from pathlib import Path

import pytest

from apps.discography.parsers.snapshot import _parse_edition_line, parse_discography

FIXTURE = Path(__file__).parent / "fixtures" / "discography_snippet.html"


@pytest.fixture(scope="module")
def releases():
    return parse_discography(FIXTURE.read_text())


def _by_name(releases, name):
    return next(r for r in releases if r.name == name)


def test_parses_each_release(releases):
    assert [r.name for r in releases] == ["Dark Like Snow", "Fly"]


def test_release_section_year_and_artist(releases):
    dls = _by_name(releases, "Dark Like Snow")
    assert dls.section == "Albums"
    assert dls.year == 2009
    assert dls.artist == "Yuki"

    fly = _by_name(releases, "Fly")
    assert fly.section == "Singles"
    assert fly.year == 2006
    assert fly.artist == "2 Bit Pie"


def test_release_has_expected_edition_count(releases):
    assert len(_by_name(releases, "Dark Like Snow").editions) == 2
    assert len(_by_name(releases, "Fly").editions) == 2


def test_name_only_edition_line(releases):
    edition = _by_name(releases, "Dark Like Snow").editions[0]
    assert edition.name == "Promo"
    assert edition.year == 2009
    assert edition.media == "CD-R"
    assert edition.catalogue_number == ""
    assert edition.record_label == ""


def test_catalogue_and_label_edition_line(releases):
    edition = _by_name(releases, "Fly").editions[0]
    assert edition.name == ""
    assert edition.catalogue_number == "TPLP718CD"
    assert edition.record_label == "One Little Indian"
    assert edition.year == 2006
    assert edition.media == "CD"


def test_name_catalogue_and_label_edition_line(releases):
    edition = _by_name(releases, "Fly").editions[1]
    assert edition.name == "Promo: Instrumental Island"
    assert edition.catalogue_number == "TPLP718CDP"
    assert edition.record_label == "One Little Indian"
    assert edition.year == 2006
    assert edition.media == "2xCD"


def test_cover_images_parsed_with_kinds_and_dewaybacked_urls(releases):
    covers = _by_name(releases, "Dark Like Snow").editions[0].covers
    assert [(c.display_name, c.kind) for c in covers] == [
        ("Back", "back"),
        ("CD", "cd"),
        ("Front", "front"),
    ]
    assert covers[0].url == (
        "http://www.2bitpie.net/Files/Covers/DarklikeSnow/DarklikesnowBack.jpg"
    )


def test_tracks_parsed_with_number_length_and_sample(releases):
    tracks = _by_name(releases, "Dark Like Snow").editions[0].tracks
    assert [t.track_number for t in tracks] == ["01", "08"]
    first = tracks[0]
    assert first.name == "Key Lime Heart"
    assert first.length == "3:57"
    assert first.sample_url == "http://2bitpie.net/Files/Samples/01KeyLimeHeart.mp3"
    assert first.lyric_title == ""


def test_track_lyrics_title_extracted(releases):
    you_got_me = _by_name(releases, "Dark Like Snow").editions[0].tracks[1]
    assert you_got_me.name == "You Got Me"
    assert you_got_me.lyric_title == "You Got Me"


def test_mix_info_extracted_from_instrumental_variant(releases):
    track = _by_name(releases, "Dark Like Snow").editions[1].tracks[0]
    assert track.name == "Key Lime Heart"
    assert track.mix_info == "Instrumental"


@pytest.mark.parametrize(
    "line,expected",
    [
        # (name, catalogue, label, year, media)
        ("Promo /  2009 /  CD-R", ("Promo", "", "", 2009, "CD-R")),
        ("TPLP718CD / One Little Indian / 2006 / CD", ("", "TPLP718CD", "One Little Indian", 2006, "CD")),
        # words-then-code two-part: name + catalogue, not catalogue + label
        ("Australian Edition / B00005GOGT / 1997 / CD", ("Australian Edition", "B00005GOGT", "", 1997, "CD")),
        # a lone code-like part is a catalogue, not a name
        ("ASW6224-2 / 1997 / CD", ("", "ASW6224-2", "", 1997, "CD")),
        # no year present: last part is still the media
        ("Promo / CD-R", ("Promo", "", "", None, "CD-R")),
    ],
)
def test_parse_edition_line_variants(line, expected):
    assert _parse_edition_line(line) == expected


def test_remixer_attached_to_preceding_track(releases):
    fly_track = _by_name(releases, "Fly").editions[0].tracks[0]
    assert fly_track.remixer == "Myagi"


def test_empty_remixer_leaves_track_without_one(releases):
    key_lime = _by_name(releases, "Dark Like Snow").editions[0].tracks[0]
    assert key_lime.remixer == ""
