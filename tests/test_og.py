"""Tests for Open Graph image generation."""

from io import BytesIO

from PIL import Image

from apps.blog.og import render_og_image


def _open(data):
    return Image.open(BytesIO(data))


def test_produces_png_at_og_dimensions():
    img = _open(render_og_image("Atom Bomb reissue announced"))
    assert img.format == "PNG"
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
