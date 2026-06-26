"""Tests for Open Graph image generation."""

from io import BytesIO

from PIL import Image, ImageDraw

from apps.core.og import OG_MAX_BYTES, OG_SIZE, _fit_title, render_og_image


def _open(data):
    return Image.open(BytesIO(data))


def test_produces_jpeg_at_og_dimensions():
    img = _open(render_og_image("Atom Bomb reissue announced"))
    assert img.format == "JPEG"
    assert img.size == (1200, 630)


def test_is_deterministic_for_same_input():
    assert render_og_image("Same title") == render_og_image("Same title")


def test_differs_for_different_titles():
    assert render_og_image("Title A") != render_og_image("Title B")


def test_handles_very_long_title():
    img = _open(render_og_image("Fluke announce a sprawling deluxe boxset " * 5))
    assert img.size == (1200, 630)


def test_respects_custom_size():
    img = _open(render_og_image("Hi", size=(600, 315)))
    assert img.size == (600, 315)


def _solid_png(color=(0, 120, 200), size=(600, 600)):
    buffer = BytesIO()
    Image.new("RGB", size, color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_cover_is_composited_at_card_dimensions():
    img = _open(render_og_image("Atom Bomb", "Fluke · 2003", cover=_solid_png()))
    assert img.format == "JPEG"
    assert img.size == (1200, 630)


def test_cover_card_differs_from_plain_card():
    assert render_og_image("X", cover=_solid_png()) != render_og_image("X")


def _noisy_cover(size=(700, 700)):
    """A high-entropy cover so the card is large before compression kicks in."""
    import os

    return _png_bytes(Image.frombytes("RGB", size, os.urandom(size[0] * size[1] * 3)))


def _png_bytes(image):
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_card_stays_within_the_size_cap():
    data = render_og_image("The Fruit", "Sander Kleinenberg · 2003", cover=_noisy_cover())
    assert len(data) <= OG_MAX_BYTES


def test_tighter_cap_compresses_further():
    cover = _noisy_cover()
    big = render_og_image("Title", cover=cover, max_bytes=OG_MAX_BYTES)
    small = render_og_image("Title", cover=cover, max_bytes=60_000)
    assert len(small) <= 60_000
    assert len(small) < len(big)


# --- Title must never overlap the subtitle (regression: long titles did) -----


def _card(title, subtitle):
    return Image.open(BytesIO(render_og_image(title, subtitle))).convert("RGB")


def _title_top_y(full, base, x0, x1):
    """Topmost row where the card's left-column ink differs from the same card
    rendered with an empty title — i.e. where the title's own ink starts."""
    fp, bp = full.load(), base.load()
    for y in range(full.height):
        for x in range(x0, x1, 2):
            if sum(abs(a - b) for a, b in zip(fp[x, y], bp[x, y], strict=True)) > 80:
                return y
    return None


def _header_bottom_y(base, x0, x1):
    """Lowest header-ink row (brand + subtitle) in the top third of a card whose
    title is empty."""
    px = base.load()
    bottom = 0
    for y in range(base.height // 3):
        for x in range(x0, x1, 2):
            r, g, b = px[x, y]
            if (r + g + b) - 30 > 60:  # brighter than the ~(10,10,10) background
                bottom = y
                break
    return bottom


def test_long_title_does_not_overlap_subtitle():
    width, _ = OG_SIZE
    margin = round(width * 0.066)
    x0, x1 = margin, width - margin
    subtitle = "26 June 2026"
    long_title = "Fluke announce a sprawling deluxe boxset reissue spanning every era and remix"

    full = _card(long_title, subtitle)
    base = _card("", subtitle)

    title_top = _title_top_y(full, base, x0, x1)
    header_bottom = _header_bottom_y(base, x0, x1)
    assert title_top is not None
    assert title_top > header_bottom  # the title sits entirely below the subtitle


def _draw():
    return ImageDraw.Draw(Image.new("RGB", (10, 10)))


def test_fit_title_block_fits_available_height():
    lines, px, line_height = _fit_title(
        _draw(),
        "Fluke announce a sprawling deluxe boxset reissue spanning every era",
        text_width=900,
        available_height=200,
        max_px=100,
        min_px=30,
    )
    assert line_height * len(lines) <= 200
    assert 30 <= px <= 100


def test_fit_title_uses_largest_size_when_it_already_fits():
    _, px, _ = _fit_title(
        _draw(), "Short", text_width=900, available_height=500, max_px=100, min_px=30
    )
    assert px == 100
