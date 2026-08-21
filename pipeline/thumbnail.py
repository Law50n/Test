"""Thumbnail = the first scene's visual plus a bold title card, so there's
always something to upload without opening a design tool.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

THUMB_SIZE = (1280, 720)  # YouTube's recommended thumbnail size


def make_thumbnail(source_image: Path, title: str, out_path: Path) -> None:
    img = Image.open(source_image).convert("RGB")
    img = _cover_resize(img, THUMB_SIZE)
    img = ImageEnhance.Contrast(img).enhance(1.1)
    img = ImageEnhance.Brightness(img).enhance(0.85)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle(
        [(0, img.height * 0.55), (img.width, img.height)],
        fill=(0, 0, 0, 150),
    )
    img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    draw = ImageDraw.Draw(img)
    font = _load_font(size=int(img.width * 0.075))
    lines = _wrap(title.upper(), font, draw, max_width=int(img.width * 0.9))
    line_height = font.size * 1.15
    total_h = line_height * len(lines)
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


def _wrap(text: str, font: ImageFont.FreeTypeFont, draw: ImageDraw.ImageDraw, max_width: int) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()
