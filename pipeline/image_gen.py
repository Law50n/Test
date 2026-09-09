"""AI-generated scene visuals via the Gemini API's image-capable model, for
the long-form pilot -- Pexels/placeholders remain the default for the
Shorts pipeline; this is opt-in per script via visual_mode="generated".

Model choice: Imagen 4's dedicated predict endpoints (standard/ultra/fast)
were deprecated and shut down 17/08/2026 -- confirmed live, they are not
an option as of this being written. gemini-3.1-flash-image (the current
"Nano Banana 2" generation) via generateContent is what's actually live.
Model IDs and pricing in this space change fast; treat GEMINI_IMAGE_MODEL
as something to revisit, not a permanent choice.

Unverified end-to-end: generativelanguage.googleapis.com is reachable from
this sandbox (confirmed directly -- a real API-level 403 asking for
credentials, not a network-level block, unlike api.openai.com/
api.stability.ai/api.replicate.com which all fail at the proxy itself),
but no API key is available here to actually call it. Request/response
shape matches Google's current documented format; verify against a real
key before trusting it fully.
"""
import base64
from pathlib import Path

import requests

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_MODEL = "gemini-3.1-flash-image"


class ImageGenError(RuntimeError):
    pass


def generate_image(prompt: str, out_path: Path, api_key: str, style_prompt: str, model: str = DEFAULT_MODEL) -> None:
    if not api_key:
        raise ImageGenError("GEMINI_API_KEY is not set")
    full_prompt = f"{prompt}. {style_prompt}" if style_prompt else prompt
    try:
        resp = requests.post(
            f"{GEMINI_API_BASE}/models/{model}:generateContent",
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": full_prompt}]}],
                "generationConfig": {"responseModalities": ["IMAGE"]},
            },
            timeout=60,
        )
        if resp.status_code >= 400:
            raise ImageGenError(f"Gemini image request failed: HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
    except ImageGenError:
        raise
    except requests.exceptions.RequestException as e:
        raise ImageGenError(f"request to Gemini failed: {e}") from e
    except ValueError as e:
        raise ImageGenError(f"unexpected response from Gemini: {e}") from e

    try:
        parts = data["candidates"][0]["content"]["parts"]
        image_part = next(p for p in parts if "inlineData" in p)
        image_bytes = base64.b64decode(image_part["inlineData"]["data"])
    except (KeyError, IndexError, StopIteration) as e:
        raise ImageGenError(f"no image in Gemini response: {e}") from e

    out_path.write_bytes(image_bytes)
