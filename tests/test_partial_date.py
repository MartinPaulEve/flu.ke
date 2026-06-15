"""Pure parsing/formatting of imprecise recording dates."""

import datetime

import pytest

from apps.resources.partial_date import (
    format_partial_date,
    parse_partial_date,
    to_input_value,
)


def test_parse_year_only():
    assert parse_partial_date("2014") == (datetime.date(2014, 1, 1), "year")


def test_parse_year_and_month():
    assert parse_partial_date("2014-02") == (datetime.date(2014, 2, 1), "month")


def test_parse_full_date():
    assert parse_partial_date("2014-02-10") == (datetime.date(2014, 2, 10), "day")


def test_parse_blank_is_none():
    assert parse_partial_date("") == (None, "day")
    assert parse_partial_date("   ") == (None, "day")


@pytest.mark.parametrize("bad", ["abc", "2014-13", "2014-02-30", "14", "2014/02", "2014-"])
def test_parse_rejects_invalid(bad):
    with pytest.raises(ValueError):
        parse_partial_date(bad)


def test_format_respects_precision():
    d = datetime.date(2014, 2, 10)
    assert format_partial_date(d, "year") == "2014"
    assert format_partial_date(d, "month") == "Feb 2014"
    assert format_partial_date(d, "day") == "10 Feb 2014"


def test_format_blank_is_empty_string():
    assert format_partial_date(None, "day") == ""


def test_to_input_value_round_trips_each_precision():
    d = datetime.date(2014, 2, 10)
    assert to_input_value(d, "year") == "2014"
    assert to_input_value(d, "month") == "2014-02"
    assert to_input_value(d, "day") == "2014-02-10"
    assert to_input_value(None, "day") == ""
