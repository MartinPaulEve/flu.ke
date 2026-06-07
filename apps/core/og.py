"""Generate branded Open Graph card images with Pillow.

Produces a 1200x630 PNG in the site's black/red identity for any content type,
optionally compositing a cover image (e.g. album art) on the right edge. Pure
function (returns bytes) — no model or filesystem coupling — so it stays
deterministic and unit-testable. Lives in ``core`` because every content app's
models generate cards from it.
"""

from __future__ import annotations

from io import BytesIO

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont

# WhatsApp drops link-preview images larger than ~300 KB (Facebook is far more
# lenient). Cards are emitted as JPEG and compressed to stay under this.
OG_MAX_BYTES = 300 * 1024
_JPEG_QUALITIES = (88, 80, 72, 64, 56, 48, 40)


def _encode_within(image: Image.Image, max_bytes: int) -> bytes:
    """JPEG-encode the card, shrinking it until it fits ``max_bytes``.

    Steps the JPEG quality down first (keeping the 1200x630 OG dimensions, which
    is enough for any real cover); only if even the lowest quality is still over
    the cap does it downscale the pixels and retry. Returns the smallest result.
    """
    current = image
    data = b""
    for _ in range(6):
        for quality in _JPEG_QUALITIES:
            buffer = BytesIO()
            current.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
            data = buffer.getvalue()
            if len(data) <= max_bytes:
                return data
        current = current.resize(
            (max(1, current.width * 4 // 5), max(1, current.height * 4 // 5)), Image.LANCZOS
        )
    return data

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


def _square_cover(data: bytes, side: int) -> Image.Image:
    """Center-crop cover image bytes to a square and resize to ``side`` px (RGB)."""
    cover = Image.open(BytesIO(data)).convert("RGB")
    width, height = cover.size
    edge = min(width, height)
    left = (width - edge) // 2
    top = (height - edge) // 2
    cover = cover.crop((left, top, left + edge, top + edge))
    return cover.resize((side, side), Image.LANCZOS)


def render_og_image(
    title: str,
    subtitle: str = "",
    *,
    cover: bytes | None = None,
    bg: str = "#0a0a0a",
    fg: str = "#f4f1ea",
    accent: str = "#ff2e1f",
    size: tuple[int, int] = OG_SIZE,
    max_bytes: int = OG_MAX_BYTES,
) -> bytes:
    """Render an Open Graph card and return JPEG bytes (compressed under max_bytes).

    When ``cover`` (image bytes) is given, it is composited as a full-height
    square on the right and the text is laid out in the remaining space.
    """
    width, height = size
    margin = round(width * 0.066)
    image = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(image)

    # Text occupies the full width unless a cover takes the right-hand square.
    text_right = width - margin
    if cover is not None:
        try:
            panel = _square_cover(cover, height)
            image.paste(panel, (width - height, 0))
            # Thin accent seam between the text and the cover.
            draw.rectangle([width - height - 8, 0, width - height, height], fill=accent)
            text_right = width - height - margin
        except (OSError, ValueError):
            # Unreadable/blank cover: silently fall back to a text-only card.
            text_right = width - margin

    text_width = text_right - margin

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
    lines = _wrap(draw, title, _font(title_px), text_width)
    while len(lines) > 4 and title_px > round(height * 0.07):
        title_px -= round(height * 0.012) or 1
        lines = _wrap(draw, title, _font(title_px), text_width)

    title_font = _font(title_px)
    line_height = title_px * 1.04
    y = height - margin - line_height * len(lines)
    for line in lines:
        draw.text((margin, y), line, font=title_font, fill=fg)
        y += line_height

    return _encode_within(image, max_bytes)
