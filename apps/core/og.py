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


def _line_height(font) -> int:
    """The font's natural line height (ascent + descent)."""
    ascent, descent = font.getmetrics()
    return ascent + descent


def _fit_title(draw, title, text_width, available_height, *, max_px, min_px, line_factor=1.04):
    """Largest title size whose wrapped block fits ``available_height``.

    Returns ``(lines, px, line_height)``. Steps down from ``max_px`` to the first
    size whose wrapped block is no taller than ``available_height`` — so the title
    is as large as possible without the bottom-anchored block rising into the
    header above it. Falls back to ``min_px`` if even that overflows.
    """
    px = max_px
    while True:
        lines = _wrap(draw, title, _font(px), text_width)
        line_height = px * line_factor
        if px <= min_px or line_height * len(lines) <= available_height:
            return lines, px, line_height
        px -= 1


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

    # Red accent bar + brand mark, top-left, with an optional subtitle beneath it.
    brand_font = _font(round(height * 0.05), 600)
    draw.rectangle([margin, margin, margin + round(width * 0.12), margin + 14], fill=accent)
    brand_y = margin + 30
    draw.text((margin, brand_y), "FLUKE.FM", font=brand_font, fill=accent)
    header_bottom = brand_y + _line_height(brand_font)
    if subtitle:
        sub_font = _font(round(height * 0.055), 600)
        sub_y = margin + 80
        draw.text((margin, sub_y), subtitle, font=sub_font, fill=fg)
        header_bottom = sub_y + _line_height(sub_font)

    # Title: bottom-anchored, sized as large as possible without rising into the
    # header. The top clamp keeps a pathologically long title off the subtitle
    # even when it can't shrink enough to fit the space below the header.
    top_limit = header_bottom + round(height * 0.045)
    lines, title_px, line_height = _fit_title(
        draw,
        title,
        text_width,
        (height - margin) - top_limit,
        max_px=round(height * 0.16),
        min_px=round(height * 0.05),
    )
    title_font = _font(title_px)
    y = max(top_limit, height - margin - line_height * len(lines))
    for line in lines:
        draw.text((margin, y), line, font=title_font, fill=fg)
        y += line_height

    return _encode_within(image, max_bytes)
