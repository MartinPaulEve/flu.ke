"""Generate branded Open Graph card images with Pillow.

Produces a 1200x630 PNG in the site's black/red identity for a post/page/release,
so social shares look intentional. Pure function (returns bytes) — no model or
filesystem coupling — which keeps it deterministic and unit-testable.
"""

from __future__ import annotations

from io import BytesIO

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont

OG_SIZE = (1200, 630)
_FONT_PATH = settings.BASE_DIR / "assets" / "fonts" / "og-display.ttf"


def _font(px: int, weight: int = 800):
    try:
        font = ImageFont.truetype(str(_FONT_PATH), px)
        try:
            font.set_variation_by_axes([weight])
        except (AttributeError, OSError, ValueError):
            pass
        return font
    except OSError:
        return ImageFont.load_default()


def _wrap(draw, text, font, max_width):
    lines, current = [], ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if not current or draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def render_og_image(
    title: str,
    subtitle: str = "",
    *,
    bg: str = "#0a0a0a",
    fg: str = "#f4f1ea",
    accent: str = "#ff2e1f",
    size: tuple[int, int] = OG_SIZE,
) -> bytes:
    """Render an Open Graph card and return PNG bytes."""
    width, height = size
    margin = round(width * 0.066)
    image = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(image)

    # Red accent bar + brand mark, top-left.
    draw.rectangle([margin, margin, margin + round(width * 0.12), margin + 14], fill=accent)
    draw.text((margin, margin + 30), "FLUKE.FM", font=_font(round(height * 0.05), 600), fill=accent)
    if subtitle:
        draw.text(
            (margin, margin + 80),
            subtitle,
            font=_font(round(height * 0.055), 600),
            fill=fg,
        )

    # Title: fill from the bottom, shrinking until it fits in <= 4 lines.
    title_px = round(height * 0.16)
    lines = _wrap(draw, title, _font(title_px), width - 2 * margin)
    while len(lines) > 4 and title_px > round(height * 0.07):
        title_px -= round(height * 0.012) or 1
        lines = _wrap(draw, title, _font(title_px), width - 2 * margin)

    title_font = _font(title_px)
    line_height = title_px * 1.04
    y = height - margin - line_height * len(lines)
    for line in lines:
        draw.text((margin, y), line, font=title_font, fill=fg)
        y += line_height

    buffer = BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
