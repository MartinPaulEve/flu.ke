"""WCAG AA contrast checks for the design tokens.

Parses the colour custom properties from assets/css/tokens.css and verifies the
real contrast ratios, so the black/red palette can never silently regress below
AA. Tests form (computed ratios), not visual content.
"""

import re
from pathlib import Path

import pytest

TOKENS = Path(__file__).resolve().parent.parent / "assets" / "css" / "tokens.css"


def _token(name):
    text = TOKENS.read_text()
    match = re.search(rf"--{re.escape(name)}\s*:\s*(#[0-9a-fA-F]{{3,8}})", text)
    assert match, f"token --{name} (hex) not found in tokens.css"
    return match.group(1)


def _channel(value):
    c = value / 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _luminance(hex_color):
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(a, b):
    la, lb = _luminance(a), _luminance(b)
    lo, hi = sorted((la, lb))
    return (hi + 0.05) / (lo + 0.05)


# Normal-size text must reach AA 4.5:1 against the background.
@pytest.mark.parametrize("fg_token", ["fg", "muted", "accent-text", "link"])
def test_text_tokens_meet_aa_normal(fg_token):
    assert contrast(_token(fg_token), _token("bg")) >= 4.5


# Large display text and non-text UI must reach 3:1.
@pytest.mark.parametrize("token", ["accent", "focus"])
def test_large_and_ui_tokens_meet_aa_large(token):
    assert contrast(_token(token), _token("bg")) >= 3.0
