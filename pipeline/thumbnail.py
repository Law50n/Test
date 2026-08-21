"""Thumbnail = the first scene's visual plus a bold title card, so there's
always something to upload without opening a design tool.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

from pipeline.fonts import load_font, wrap

THUMB_SIZE = (1280, 720)  # YouTube's recommended thumbnail size


MAX_TEXT_HEIGHT_FRACTION = 0.5  # never let title text claim more than this much of the frame
MAX_LINES = 4


def make_thumbnail(source_image: Path, title: str, out_path: Path) -> None:
    img = Image.open(source_image).convert("RGB")
    img = _cover_resize(img, THUMB_SIZE)
    img = ImageEnhance.Contrast(img).enhance(1.1)
    img = ImageEnhance.Brightness(img).enhance(0.85)

    draw = ImageDraw.Draw(img)
    font, lines, line_height = _fit_title(title.upper(), draw, img.width, img.height)
    total_h = line_height * len(lines)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_top = img.height - total_h - img.height * 0.1
    overlay_draw.rectangle([(0, overlay_top), (img.width, img.height)], fill=(0, 0, 0, 150))
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    y = img.height - total_h - img.height * 0.06
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (img.width - (bbox[2] - bbox[0])) / 2
        draw.text(
            (x, y),
            line,
            font=font,
            fill=(255, 255, 255),
            stroke_width=max(3, img.width // 220),
            stroke_fill=(0, 0, 0),
        )
        y += line_height

    img.save(out_path, quality=92)


def _fit_title(text: str, draw: ImageDraw.ImageDraw, width: int, height: int):
    """Shrinks the font until the wrapped title fits within
    MAX_TEXT_HEIGHT_FRACTION of the frame, so a long title can never bury
    the whole thumbnail in text. Falls back to truncating lines at the
    smallest readable size if it still doesn't fit.
    """
    max_total_h = height * MAX_TEXT_HEIGHT_FRACTION
    min_size = max(int(width * 0.03), 14)
    size = int(width * 0.075)
    while True:
        font = load_font(size=size)
        lines = wrap(text, font, draw, max_width=int(width * 0.9))
        line_height = font.size * 1.15
        if (len(lines) * line_height <= max_total_h and len(lines) <= MAX_LINES) or size <= min_size:
            if len(lines) > MAX_LINES:
                lines = lines[:MAX_LINES]
                lines[-1] = lines[-1].rstrip(".,;:") + "..."
            return font, lines, line_height
        size = int(size * 0.9)


def _cover_resize(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    src_ratio = img.width / img.height
    target_ratio = target_w / target_h
    if src_ratio > target_ratio:
        new_h = target_h
        new_w = int(new_h * src_ratio)
    else:
        new_w = target_w
        new_h = int(new_w / src_ratio)
    img = img.resize((new_w, new_h))
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))
