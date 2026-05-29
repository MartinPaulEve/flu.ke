"""Unit tests for the pure media-import helpers (no IO)."""

import pytest

from apps.discography.media_import import (
    file_kind_for,
    match_source,
    relpath_after_files,
    resource_kind_for,
)


@pytest.mark.parametrize(
    "name,kind",
    [
        ("01KeyLimeHeart.mp3", "audio"),
        ("Tosh.rar", "archive"),
        ("DarklikesnowFront.JPG", "image"),
        ("Atmosphere.mp4", "video"),
        ("liner-notes.pdf", "document"),
        ("README", "document"),
    ],
)
def test_file_kind_for(name, kind):
    assert file_kind_for(name) == kind


@pytest.mark.parametrize(
    "name,kind",
    [
        ("JCToshRemix2012.mp3", "fan"),
        ("PeaceVibrationJCRmx.mp3", "fan"),
        ("01.Atom Bomb, Interview & Absurd.rar", "official"),
        ("BBC Radio 1.zip", "official"),
    ],
)
def test_resource_kind_for(name, kind):
    assert resource_kind_for(name) == kind


def test_relpath_after_files_extracts_tail():
    url = "http://www.2bitpie.net/Files/Covers/DarklikeSnow/DarklikesnowFront.jpg"
    assert relpath_after_files(url) == "Covers/DarklikeSnow/DarklikesnowFront.jpg"


def test_relpath_after_files_handles_alternate_prefix():
    assert relpath_after_files("http://2bitpie.net/2bitpie/Files/fly.mp3") == "fly.mp3"


def test_relpath_after_files_decodes_percent_encoding():
    url = "http://x/Files/Samples/My%20Track.mp3"
    assert relpath_after_files(url) == "Samples/My Track.mp3"


def test_relpath_after_files_returns_none_without_files_segment():
    assert relpath_after_files("http://x/other/thing.jpg") is None


def test_match_source_prefers_exact_relpath():
    relpaths = {"Covers/DLS/Front.jpg"}
    url = "http://x/Files/Covers/DLS/Front.jpg"
    assert match_source(url, relpaths, {}) == "Covers/DLS/Front.jpg"


def test_match_source_falls_back_to_basename():
    index = {"front.jpg": "Covers/Elsewhere/Front.jpg"}
    url = "http://x/Files/moved/Front.jpg"
    assert match_source(url, set(), index) == "Covers/Elsewhere/Front.jpg"


def test_match_source_returns_none_when_unmatched():
    assert match_source("http://x/Files/nope.jpg", set(), {}) is None
