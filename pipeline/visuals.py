"""Sources one still image per scene: Pexels when an API key is configured,
otherwise a generated placeholder so the pipeline still runs end to end.
"""
import hashlib
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"


def fetch_visual(query: str, out_path: Path, api_key: str, size: tuple[int, int]) -> str:
    """Returns "pexels" or "placeholder" indicating what was written to out_path."""
    if api_key:
        try:
            _fetch_pexels(query, out_path, api_key)
            return "pexels"
        except _PexelsError as e:
            print(f"  ! Pexels lookup failed for {query!r} ({e}); using a placeholder instead")
    _generate_placeholder(query, out_path, size)
    return "placeholder"


class _PexelsError(RuntimeError):
    pass


def _fetch_pexels(query: str, out_path: Path, api_key: str) -> None:
    resp = requests.get(
        PEXELS_SEARCH_URL,
        headers={"Authorization": api_key},
        params={"query": query, "orientation": "portrait", "per_page": 1},
        timeout=15,
    )
    if resp.status_code != 200:
        raise _PexelsError(f"HTTP {resp.status_code}")
    photos = resp.json().get("photos") or []
    if not photos:
        raise _PexelsError("no results")
    image_url = photos[0]["src"]["large2x"]
    image_resp = requests.get(image_url, timeout=30)
    image_resp.raise_for_status()
    out_path.write_bytes(image_resp.content)


def _generate_placeholder(query: str, out_path: Path, size: tuple[int, int]) -> None:
    """A deterministic gradient card labeled with the search query, so a
    missing Pexels key still produces a watchable (if plain) test render.
    """
    width, height = size
    seed = int(hashlib.sha256(query.encode()).hexdigest(), 16)
    hue_a = seed % 360
    hue_b = (hue_a + 40) % 360
    top = _hsl_to_rgb(hue_a, 0.45, 0.28)
    bottom = _hsl_to_rgb(hue_b, 0.45, 0.14)

    img = Image.new("RGB", (width, height))
    for y in range(height):
        t = y / max(height - 1, 1)
        row = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        ImageDraw.Draw(img).line([(0, y), (width, y)], fill=row)

    draw = ImageDraw.Draw(img)
    font = _load_font(size=int(width * 0.06))
    lines = _wrap(query.upper(), font, draw, max_width=int(width * 0.85))
    line_height = font.size * 1.2
    y = (height - line_height * len(lines)) / 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (width - (bbox[2] - bbox[0])) / 2
        draw.text(
            (x, y),
            line,
            font=font,
            fill=(255, 255, 255),
            stroke_width=max(2, width // 300),
            stroke_fill=(0, 0, 0),
        )
        y += line_height
    img.save(out_path, quality=90)


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


def _hsl_to_rgb(h: float, s: float, l: float) -> tuple[int, int, int]:
    import colorsys

    r, g, b = colorsys.hls_to_rgb(h / 360, l, s)
    return int(r * 255), int(g * 255), int(b * 255)
