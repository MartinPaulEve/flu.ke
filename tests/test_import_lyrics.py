"""Unit tests for the lyric-recovery helper (pure; no database/network)."""

import pytest

from apps.discography.management.commands.import_lyrics import title_from_lyric_url


@pytest.mark.parametrize(
    "url,expected",
    [
        ("http://discography.2bitpie.net:80/lyrics/Absurd/", "Absurd"),
        ("http://discography.2bitpie.net/lyrics/Another%20Kind%20of%20Blues/",
         "Another Kind of Blues"),
        ("http://discography.2bitpie.net:80/lyrics/You%20Got%20Me", "You Got Me"),
    ],
)
def test_title_from_lyric_url(url, expected):
    assert title_from_lyric_url(url) == expected
