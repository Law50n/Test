"""Sources one real stock video clip per scene (Pexels Videos -- a separate
endpoint from the photo search in visuals.py, same free API key), falling
back to the same generated placeholder image visuals.py uses when no key is
configured or nothing suitable comes back.
"""
from pathlib import Path

import requests

from pipeline.visuals import generate_placeholder

PEXELS_VIDEO_SEARCH_URL = "https://api.pexels.com/videos/search"


class _VideoError(RuntimeError):
    pass


def fetch_video_clip(
    query: str, out_path: Path, api_key: str, size: tuple[int, int], min_duration: float
) -> str:
    """Returns "pexels_video" or "placeholder". A "placeholder" result is a
    still image, not a video -- assemble.make_scene_clip (the Ken Burns
    path) handles it the same way the photo-mode pipeline does.
    """
    if api_key:
        try:
            _fetch_pexels_video(query, out_path, api_key, size, min_duration)
            return "pexels_video"
        except _VideoError as e:
            print(f"  ! Pexels video lookup failed for {query!r} ({e}); using a placeholder instead")
    generate_placeholder(query, out_path, size)
    return "placeholder"


def _fetch_pexels_video(
    query: str, out_path: Path, api_key: str, size: tuple[int, int], min_duration: float
) -> None:
    want_portrait = size[1] > size[0]
    try:
        resp = requests.get(
            PEXELS_VIDEO_SEARCH_URL,
            headers={"Authorization": api_key},
            params={"query": query, "orientation": "portrait" if want_portrait else "landscape", "per_page": 5},
            timeout=15,
        )
        if resp.status_code != 200:
            raise _VideoError(f"HTTP {resp.status_code}")
        videos = resp.json().get("videos") or []
        if not videos:
            raise _VideoError("no results")

        # Prefer a clip that's already at least as long as the scene needs,
        # so assemble.make_scene_clip_from_video only ever trims, never loops
        # mid-sentence on a jarring seam. Fall back to the longest available.
        candidates = sorted(videos, key=lambda v: v.get("duration", 0), reverse=True)
        best = next((v for v in candidates if v.get("duration", 0) >= min_duration), candidates[0])

        video_file = _pick_video_file(best.get("video_files", []), size)
        if not video_file:
            raise _VideoError("no usable video_files in result")

        video_resp = requests.get(video_file["link"], timeout=60)
        video_resp.raise_for_status()
        out_path.write_bytes(video_resp.content)
    except _VideoError:
        raise
    except requests.exceptions.RequestException as e:
        raise _VideoError(f"request failed: {e}") from e
    except (KeyError, ValueError) as e:
        raise _VideoError(f"unexpected response shape: {e}") from e


def _pick_video_file(video_files: list[dict], size: tuple[int, int]) -> dict | None:
    """Picks the file closest to 1080p in the orientation we need, preferring
    mp4. Pexels returns several resolutions per video (sd/hd/uhd and a few
    exact pixel sizes) with no single "best" flag.
    """
    mp4_files = [f for f in video_files if f.get("file_type") == "video/mp4"]
    if not mp4_files:
        return None
    target_h = max(size)  # the larger dimension, regardless of orientation
    return min(mp4_files, key=lambda f: abs((f.get("height") or 0) - target_h))
