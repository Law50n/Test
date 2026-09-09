"""Shared text-rendering helpers for visuals.py and thumbnail.py."""
from pathlib import Path

from PIL import ImageDraw, ImageFont


def load_font(size: int) -> ImageFont.FreeTypeFont:
    """The Linux paths below don't exist on Windows or macOS, so without the
    OS-specific candidates this silently fell through to Pillow's generic
    bundled default font on every non-Linux machine -- not a crash, just a
    plainer typeface than intended (confirmed: this pipeline's real users
    so far are on Windows).
    """
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\segoeuib.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size)
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
