"""WCAG AA contrast checks for the design tokens.

Parses the colour custom properties from assets/css/tokens.css and verifies the
real contrast ratios, so neither the light (default) nor the dark palette can
silently regress below AA. Tests form (computed ratios), not visual content.
"""

import re
from pathlib import Path

import pytest

TOKENS = Path(__file__).resolve().parent.parent / "assets" / "css" / "tokens.css"

# The CSS selector that introduces each theme's token block. Light is the
# default (bare :root); dark is opt-in via data-theme="dark".
_THEME_SELECTORS = {
    "light": r":root",
    "dark": r':root\[data-theme="dark"\]',
}


def _theme_block(theme):
    """Return the text inside the ``{ ... }`` of a given theme's selector block."""
    text = TOKENS.read_text()
    selector = _THEME_SELECTORS[theme]
    # Match the selector immediately followed by its brace block. The default
    # selector (:root) must not also match :root[data-theme="dark"], so we
    # require the brace to follow the selector (optionally with whitespace).
    match = re.search(rf"(?<![\w\[\]\"=-]){selector}\s*\{{(.*?)\}}", text, re.DOTALL)
    assert match, f"theme block for {theme!r} not found in tokens.css"
    return match.group(1)


def _token(name, theme="dark"):
    block = _theme_block(theme)
    match = re.search(rf"--{re.escape(name)}\s*:\s*(#[0-9a-fA-F]{{3,8}})", block)
    assert match, f"token --{name} (hex) not found in the {theme!r} block of tokens.css"
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


# Normal-size text must reach AA 4.5:1 against the background, in BOTH themes.
@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("fg_token", ["fg", "muted", "accent-text", "link"])
def test_text_tokens_meet_aa_normal(fg_token, theme):
    assert contrast(_token(fg_token, theme), _token("bg", theme)) >= 4.5


# Large display text and non-text UI must reach 3:1, in BOTH themes.
@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("token", ["accent", "focus"])
def test_large_and_ui_tokens_meet_aa_large(token, theme):
    assert contrast(_token(token, theme), _token("bg", theme)) >= 3.0


def test_default_theme_is_light():
    """The default palette (bare :root, applied when no data-theme is set) is a
    light theme: a light background under dark text."""
    assert _luminance(_token("bg", "light")) > _luminance(_token("fg", "light"))


def test_dark_theme_is_opt_in():
    """Dark is opt-in via :root[data-theme="dark"]: a dark background under light
    text. Its presence also proves the dark palette didn't disappear in the flip."""
    assert _luminance(_token("bg", "dark")) < _luminance(_token("fg", "dark"))
