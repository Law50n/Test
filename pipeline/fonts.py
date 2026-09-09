"""Shared text-rendering helpers for visuals.py and thumbnail.py."""
from pathlib import Path

from PIL import ImageDraw, ImageFont

# Bundled directly in the repo (assets/fonts/) rather than relying on
# whatever's installed on the OS -- the previous version guessed at Linux/
# Windows/macOS system font paths, which is fragile (exact filenames vary
# by Windows locale/edition) and pointless when every real render happens
# on the same machine anyway. Anton (OFL-licensed, see assets/fonts/
# Anton-OFL.txt) is also just a better fit for bold video titles/captions
# than generic Arial.
FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Anton-Regular.ttf"


def load_font(size: int) -> ImageFont.FreeTypeFont:
    if FONT_PATH.exists():
        return ImageFont.truetype(str(FONT_PATH), size)
    return ImageFont.load_default(size=size)


def wrap(text: str, font: ImageFont.FreeTypeFont, draw: ImageDraw.ImageDraw, max_width: int) -> list[str]:
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
