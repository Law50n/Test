"""Sources one still image per scene: Pexels when an API key is configured,
otherwise a generated placeholder so the pipeline still runs end to end.
"""
import hashlib
import random
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFilter

from pipeline.fonts import load_font, wrap

PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"


def fetch_visual(query: str, out_path: Path, api_key: str, size: tuple[int, int]) -> str:
    """Returns "pexels" or "placeholder" indicating what was written to out_path."""
    if api_key:
        try:
            _fetch_pexels(query, out_path, api_key)
            return "pexels"
        except _PexelsError as e:
            print(f"  ! Pexels lookup failed for {query!r} ({e}); using a placeholder instead")
    generate_placeholder(query, out_path, size)
    return "placeholder"


class _PexelsError(RuntimeError):
    pass


def _fetch_pexels(query: str, out_path: Path, api_key: str) -> None:
    try:
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
    except _PexelsError:
        raise
    except requests.exceptions.RequestException as e:
        raise _PexelsError(f"request failed: {e}") from e
    except (KeyError, ValueError) as e:
        raise _PexelsError(f"unexpected response shape: {e}") from e


# Hand-picked (top, bottom) gradient pairs, not random hue math -- free hue
# rotation reliably produces a muddy or clashing pair some fraction of the
# time, and this is the one thing every viewer sees on every placeholder.
_PALETTES = [
    ((70, 88, 138), (22, 26, 46)),    # night blue
    ((128, 68, 104), (34, 22, 40)),   # plum dusk
    ((48, 108, 112), (16, 36, 42)),   # teal depth
    ((124, 82, 46), (38, 26, 18)),    # amber dusk
    ((74, 96, 66), (24, 32, 24)),     # forest
    ((110, 50, 58), (36, 18, 22)),    # wine
    ((58, 68, 116), (20, 22, 46)),    # indigo
    ((92, 92, 96), (30, 30, 34)),     # slate
]


def generate_placeholder(query: str, out_path: Path, size: tuple[int, int]) -> None:
    """A deterministic, cinematic-ish card standing in for the search query,
    labeled with it, so a missing Pexels key (or a query with no results)
    still produces a watchable render. Used for actual scene visuals --
    for a thumbnail source, use generate_placeholder_unlabeled instead (see
    its docstring for why: this one's label will double up with the
    thumbnail's own title text).
    """
    img = _render_card(query, size)
    _add_label(img, query)
    img.save(out_path, format="JPEG", quality=90)


def generate_placeholder_unlabeled(query: str, out_path: Path, size: tuple[int, int]) -> None:
    """Same card as generate_placeholder, minus the query label.

    thumbnail.make_thumbnail() draws the video's real title over its source
    image's own bottom third. Pointing it at an already-labeled placeholder
    stacked one bar's text as a ghost behind the other -- confirmed visually
    in the 16:9 VIDEO_FORMAT=long case, where the source image isn't cropped
    enough during the cover-resize to hide it. Use this whenever the image
    is heading to a thumbnail rather than becoming scene b-roll.
    """
    img = _render_card(query, size)
    img.save(out_path, format="JPEG", quality=90)


def _render_card(query: str, size: tuple[int, int]) -> Image.Image:
    width, height = size
    seed_bytes = hashlib.sha256(query.encode()).digest()
    rnd = random.Random(seed_bytes)
    top, bottom = _PALETTES[seed_bytes[0] % len(_PALETTES)]

    img = Image.new("RGB", (width, height))
    for y in range(height):
        t = y / max(height - 1, 1)
        row = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        ImageDraw.Draw(img).line([(0, y), (width, y)], fill=row)

    img = _add_glows(img, rnd)
    img = _add_grain(img, rnd)
    img = _add_vignette(img)
    return img


def _add_glows(img: Image.Image, rnd: random.Random) -> Image.Image:
    """A couple of soft light blobs for depth -- a flat gradient alone reads
    as a solid color rectangle; these give it something to look at.
    """
    w, h = img.size
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for _ in range(rnd.randint(2, 3)):
        r = rnd.randint(int(w * 0.18), int(w * 0.38))
        cx, cy = rnd.randint(0, w), rnd.randint(0, h)
        alpha = rnd.randint(20, 40)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, alpha))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=w * 0.06))
    return Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")


def _add_grain(img: Image.Image, rnd: random.Random) -> Image.Image:
    """Subtle film grain -- hides gradient banding and reads as intentional
    texture rather than a flat digital fill.
    """
    noise = Image.effect_noise(img.size, 22).convert("L")
    noise_rgb = Image.merge("RGB", (noise, noise, noise))
    return Image.blend(img, noise_rgb, alpha=0.05)


def _add_vignette(img: Image.Image, strength: float = 0.35) -> Image.Image:
    """Darkens only the outer edges (r**3 curve keeps the inner ~60% of the
    frame essentially untouched) -- strong enough to read as intentional
    framing, not so strong it crushes the palette toward black.
    """
    w, h = img.size
    small = (max(w // 24, 24), max(h // 24, 24))
    mask = Image.new("L", small, 0)
    cx, cy = small[0] / 2, small[1] / 2
    max_r = (cx**2 + cy**2) ** 0.5
    for y in range(small[1]):
        for x in range(small[0]):
            r = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5 / max_r
            mask.putpixel((x, y), int(255 * min(1.0, r**3) * strength))
    mask = mask.resize(img.size, Image.BILINEAR)
    black = Image.new("RGB", img.size, (0, 0, 0))
    return Image.composite(black, img, mask)


def _add_label(img: Image.Image, query: str) -> None:
    """A lower-third label bar instead of giant centered shout-text -- this
    is standing in for a photo, not announcing itself as one.
    """
    width, height = img.size
    bar_height = int(height * 0.16)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rectangle(
        [(0, height - bar_height), (width, height)], fill=(0, 0, 0, 130)
    )
    composited = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    img.paste(composited)

    draw = ImageDraw.Draw(img)
    font = load_font(size=int(width * 0.032))
    label = query[:1].upper() + query[1:]
    lines = wrap(label, font, draw, max_width=int(width * 0.88))[:2]
    line_height = font.size * 1.25
    y = height - bar_height / 2 - (line_height * len(lines)) / 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (width - (bbox[2] - bbox[0])) / 2
        draw.text((x, y), line, font=font, fill=(235, 235, 235))
        y += line_height
