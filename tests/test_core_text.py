"""Tests for apps.core.text.unique_slug (pure, no database)."""

import pytest

from apps.core.text import normalize_track_number, unique_slug


def test_slugifies_value_when_free():
    assert unique_slug("Dark Like Snow", exists=lambda s: False) == "dark-like-snow"


def test_strips_punctuation_and_lowercases():
    assert unique_slug("Don't Know Why!", exists=lambda s: False) == "dont-know-why"


def test_appends_suffix_when_base_taken():
    taken = {"fly"}
    assert unique_slug("Fly", exists=lambda s: s in taken) == "fly-2"


def test_increments_suffix_until_free():
    taken = {"fly", "fly-2", "fly-3"}
    assert unique_slug("Fly", exists=lambda s: s in taken) == "fly-4"


def test_respects_max_length_including_suffix():
    # base slugifies+truncates to "abcdef" (max_length=6). It's taken, so the base is
    # shortened to leave room for "-2" within 6 chars -> "abcd-2".
    taken = {"abcdef"}
    result = unique_slug("abcdefghij", exists=lambda s: s in taken, max_length=6)
    assert len(result) <= 6
    assert result == "abcd-2"


def test_empty_value_falls_back_to_default_base():
    # A value that slugifies to empty (e.g. all punctuation) still yields a usable slug.
    assert unique_slug("!!!", exists=lambda s: False) == "item"


def test_empty_value_fallback_is_also_made_unique():
    assert unique_slug("???", exists=lambda s: s == "item") == "item-2"


# --- normalize_track_number -------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [
        ("1", "01"),
        ("9", "09"),
        ("01", "01"),      # already padded
        ("10", "10"),      # two digits left alone
        ("123", "123"),    # three digits left alone
        ("A1", "A01"),     # vinyl side prefix
        ("B9", "B09"),
        ("A01", "A01"),
        ("B12", "B12"),
        ("i-1", "i-01"),   # instrumental-disc numbering
        ("i-01", "i-01"),
        ("", ""),          # blank untouched
        ("  3  ", "03"),   # trimmed then padded
        ("Bonus", "Bonus"),  # non-numeric untouched
    ],
)
def test_normalize_track_number(value, expected):
    assert normalize_track_number(value) == expected
