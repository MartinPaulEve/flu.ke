"""Tests for Open Graph image generation."""

from io import BytesIO

from PIL import Image

from apps.core.og import OG_MAX_BYTES, render_og_image


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
