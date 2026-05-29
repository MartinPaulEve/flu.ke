"""Unit tests for the pure MusicBrainz mapping functions (no network)."""

import pytest

from apps.discography.musicbrainz import (
    map_recording,
    map_release,
    map_release_group,
    parse_length,
)


@pytest.mark.parametrize(
    "ms,expected",
    [
        (361000, "6:01"),
        (237000, "3:57"),
        ("361000", "6:01"),
        (None, ""),
        ("", ""),
        (59000, "0:59"),
    ],
)
def test_parse_length(ms, expected):
    assert parse_length(ms) == expected


def test_map_release_group():
    rg = {
        "id": "11111111-1111-1111-1111-111111111111",
        "title": "Risotto",
        "first-release-date": "1997-09-22",
        "primary-type": "Album",
    }
    assert map_release_group(rg) == {
        "mbid": "11111111-1111-1111-1111-111111111111",
        "name": "Risotto",
        "year": 1997,
    }


def test_map_release_group_without_date():
    rg = {"id": "x", "title": "Untitled"}
    assert map_release_group(rg)["year"] is None


def test_map_release():
    release = {
        "id": "22222222-2222-2222-2222-222222222222",
        "date": "1997",
        "label-info-list": [
            {"catalog-number": "ASW6224-2", "label": {"name": "Astralwerks"}}
        ],
        "medium-list": [{"format": "CD"}],
    }
    assert map_release(release) == {
        "mbid": "22222222-2222-2222-2222-222222222222",
        "year": 1997,
        "catalogue_number": "ASW6224-2",
        "record_label": "Astralwerks",
        "media": "CD",
    }


def test_map_release_handles_missing_label_and_media():
    release = {"id": "y", "date": ""}
    mapped = map_release(release)
    assert mapped["catalogue_number"] == ""
    assert mapped["record_label"] == ""
    assert mapped["media"] == ""
    assert mapped["year"] is None


def test_map_recording():
    track = {
        "position": "1",
        "recording": {
            "id": "33333333-3333-3333-3333-333333333333",
            "title": "Fly",
            "length": "361000",
        },
    }
    assert map_recording(track) == {
        "recording_mbid": "33333333-3333-3333-3333-333333333333",
        "track_number": "1",
        "name": "Fly",
        "length": "6:01",
    }
