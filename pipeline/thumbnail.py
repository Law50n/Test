"""Thumbnail = the first scene's visual plus a bold title card, so there's
always something to upload without opening a design tool.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

from pipeline.fonts import load_font, wrap

THUMB_SIZE = (1280, 720)  # YouTube's recommended thumbnail size
ACCENT_RGB = (255, 212, 0)  # same gold as the caption highlight, for a consistent look


MAX_TEXT_HEIGHT_FRACTION = 0.5  # never let title text claim more than this much of the frame
MAX_LINES = 4


def make_thumbnail(source_image: Path, title: str, out_path: Path, highlight: str = "") -> None:
    img = Image.open(source_image).convert("RGB")
    img = _cover_resize(img, THUMB_SIZE)
    img = ImageEnhance.Contrast(img).enhance(1.15)
    img = ImageEnhance.Brightness(img).enhance(0.8)
    # Thumbnails need to be more vivid than the video itself to catch the
    # eye in a scrolling feed -- the in-video grade (assemble.GRADE_FILTER)
    # is deliberately subtle so a whole video isn't oversaturated, but a
    # thumbnail can and should push further.
    img = ImageEnhance.Color(img).enhance(1.35)

    draw = ImageDraw.Draw(img)
    font, lines, line_height = _fit_title(title.upper(), draw, img.width, img.height)
    total_h = line_height * len(lines)
    top_y = img.height - total_h - img.height * 0.08

    img = _bottom_scrim(img, top_y / img.height)

    highlight_words = {w.strip(".,;:!?()\"'").lower() for w in highlight.split()} if highlight else set()

    draw = ImageDraw.Draw(img)
    stroke_width = max(3, img.width // 220)
    y = img.height - total_h - img.height * 0.05
    for i, line in enumerate(lines):
        words = line.split(" ")
        # Default (no explicit highlight given): the last word on the last
        # line is usually the payoff of the title -- pull it out in gold
        # instead of leaving every line flat white, which read as generic
        # meme-text. An explicit `highlight` overrides this, since "last
        # word" is sometimes a throwaway ("...Actually Works") rather than
        # the punchy part of the title.
        highlight_last_word = not highlight_words and i == len(lines) - 1
        space_w = draw.textlength(" ", font=font)
        word_widths = [draw.textlength(w, font=font) for w in words]
        line_w = sum(word_widths) + space_w * (len(words) - 1)
        x = (img.width - line_w) / 2
        for j, (word, ww) in enumerate(zip(words, word_widths)):
            is_last_word_default = highlight_last_word and j == len(words) - 1
            is_explicit_match = word.strip(".,;:!?()\"'").lower() in highlight_words
            color = ACCENT_RGB if (is_last_word_default or is_explicit_match) else (255, 255, 255)
            draw.text((x, y), word, font=font, fill=color, stroke_width=stroke_width, stroke_fill=(0, 0, 0))
            x += ww + space_w
        y += line_height

    img.save(out_path, quality=92)


def _bottom_scrim(img: Image.Image, top_frac: float, max_alpha: int = 205) -> Image.Image:
    """A smooth gradient darkening from `top_frac` down to the bottom edge,
    instead of a flat semi-transparent rectangle -- the hard edge on a flat
    box is what made the previous version look like a sticker slapped over
    the photo rather than a graded, intentional frame.
    """
    w, h = img.size
    small_h = 128
    top_row = int(small_h * max(top_frac, 0))
    mask = Image.new("L", (2, small_h), 0)
    for y in range(small_h):
        if y < top_row:
            alpha = 0
        else:
            t = (y - top_row) / max(small_h - top_row - 1, 1)
            alpha = int(max_alpha * (t**1.3))
        mask.putpixel((0, y), alpha)
        mask.putpixel((1, y), alpha)
    mask = mask.resize((w, h), Image.BILINEAR)
    black = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(black, img, mask)


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
