"""Imprecise ("partial") dates: a real ``date`` plus how precise it is.

A recording might be known only to the year, to the month, or to the exact day.
We still store a genuine :class:`datetime.date` (so ordering, filtering and any
date arithmetic keep working), and pair it with a *precision* — ``"year"``,
``"month"`` or ``"day"`` — that says how much of it is actually known. Unknown
parts are stored as ``1`` (the first month / first day) but never displayed.
"""

from __future__ import annotations

import datetime

YEAR = "year"
MONTH = "month"
DAY = "day"

# Django ``date`` template-filter formats for each precision.
_FORMATS = {YEAR: "Y", MONTH: "M Y", DAY: "j M Y"}
# ``strftime`` round-trip formats used to render the value back into an input box.
_INPUT_FORMATS = {YEAR: "%Y", MONTH: "%Y-%m", DAY: "%Y-%m-%d"}


def parse_partial_date(text: str) -> tuple[datetime.date | None, str]:
    """Parse ``2014`` / ``2014-02`` / ``2014-02-10`` into ``(date, precision)``.

    Blank input yields ``(None, "day")``. Raises :class:`ValueError` on anything
    that isn't a valid year, year-month or year-month-day.
    """
    text = (text or "").strip()
    if not text:
        return None, DAY

    parts = text.split("-")
    precision = {1: YEAR, 2: MONTH, 3: DAY}.get(len(parts))
    # Require a 4-digit year and plain integer parts; reject "2014/02", "14",
    # "2014-" (empty trailing part) and over-long inputs.
    if precision is None or not all(p.isdigit() for p in parts) or len(parts[0]) != 4:
        raise ValueError(f"Not a valid year, year-month or date: {text!r}")

    nums = [int(p) for p in parts]
    year, month, day = (nums + [1, 1])[:3]
    return datetime.date(year, month, day), precision  # date() validates the ranges


def format_partial_date(value: datetime.date | None, precision: str) -> str:
    """Render ``value`` showing only the parts allowed by ``precision``."""
    if not value:
        return ""
    # Imported lazily so the module stays importable without Django configured.
    from django.template.defaultfilters import date as date_filter

    return date_filter(value, _FORMATS.get(precision, _FORMATS[DAY]))


def to_input_value(value: datetime.date | None, precision: str) -> str:
    """Render ``value`` back into the ``YYYY[-MM[-DD]]`` text an editor typed."""
    if not value:
        return ""
    return value.strftime(_INPUT_FORMATS.get(precision, _INPUT_FORMATS[DAY]))
