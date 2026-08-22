"""Optional, experimental: render one full-script video through D-ID's
talking-head API instead of the stock-visual Ken Burns pipeline.

This is NOT part of the default $0 pipeline. D-ID's free trial is a
one-time ~5 minutes of video (20 credits, no card required as of when this
was written) -- not a repeatable per-video budget like everything else in
this repo. Treat the free trial as a single proof-of-concept test, spent on
your strongest script, not a per-video step in the regular workflow.

Unverified: this sandbox's network policy blocks both api.d-id.com and
D-ID's own docs, so this has not been run against the real API. The request
shape below matches D-ID's long-stable /talks endpoint, but confirm field
names against your own dashboard/docs before relying on it.

Source image: use a synthetic (AI-generated, does not depict a real person)
or explicitly-licensed presenter image. Using a real, identifiable person's
photo to create a fake talking channel persona they never agreed to is a
likeness/consent problem, independent of whatever license the photo itself
carries. If the result could pass for a real person, YouTube's synthetic
media policy requires disclosing it as AI-generated.
"""
import base64
import time
from pathlib import Path

import requests

API_BASE = "https://api.d-id.com"


class AvatarError(RuntimeError):
    pass


def create_talking_video(
    source_image_url: str,
    script_text: str,
    api_key: str,
    out_path: Path,
    voice_id: str = "en-US-JennyNeural",
    poll_interval: float = 5.0,
    timeout: float = 300.0,
) -> None:
    """Submits a talk, polls until done, downloads the result to out_path.

    api_key is the raw key string from your D-ID dashboard -- D-ID expects
    it HTTP-Basic-encoded as-is (it's already "id:secret"-shaped).
    """
    auth = base64.b64encode(api_key.encode()).decode()
    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}

    try:
        resp = requests.post(
            f"{API_BASE}/talks",
            headers=headers,
            json={
                "source_url": source_image_url,
                "script": {
                    "type": "text",
                    "input": script_text,
                    "provider": {"type": "microsoft", "voice_id": voice_id},
                },
            },
            timeout=30,
        )
        if resp.status_code >= 400:
            raise AvatarError(f"talk creation failed: HTTP {resp.status_code}: {resp.text}")
        talk_id = resp.json().get("id")
        if not talk_id:
            raise AvatarError(f"no talk id in response: {resp.text}")

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(poll_interval)
            status_resp = requests.get(f"{API_BASE}/talks/{talk_id}", headers=headers, timeout=30)
            if status_resp.status_code >= 400:
                raise AvatarError(f"status check failed: HTTP {status_resp.status_code}: {status_resp.text}")
            data = status_resp.json()
            status = data.get("status")
            print(f"  talk {talk_id}: {status}")
            if status == "done":
                video_resp = requests.get(data["result_url"], timeout=60)
                video_resp.raise_for_status()
                out_path.write_bytes(video_resp.content)
                return
            if status == "error":
                raise AvatarError(f"talk failed: {data}")
    except AvatarError:
        raise
    except requests.exceptions.RequestException as e:
        raise AvatarError(f"request to D-ID failed: {e}") from e

    raise AvatarError(f"talk {talk_id} did not finish within {timeout}s")


def script_to_full_text(scenes: list[dict]) -> str:
    """Joins a script's per-scene narration into one paragraph -- D-ID
    generates one continuous talking video, not scene-by-scene clips.
    """
    return " ".join(scene["text"] for scene in scenes)


def main() -> None:
    import argparse
    import json
    import os

    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(
        description=(
            "One-off test render through D-ID's talking-head API. Spends real "
            "trial credits -- confirm the script and face-url before running."
        )
    )
    parser.add_argument("script", type=Path, help="a content/scripts/**/*.json file")
    parser.add_argument(
        "--face-url",
        required=True,
        help="publicly reachable URL to a synthetic or explicitly-licensed presenter image",
    )
    parser.add_argument("--voice-id", default="en-US-JennyNeural")
    parser.add_argument("--out", type=Path, default=Path("output/avatar_test.mp4"))
    args = parser.parse_args()

    api_key = os.environ.get("D_ID_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Set D_ID_API_KEY in .env first (get one from your D-ID dashboard).")

    data = json.loads(args.script.read_text())
    text = script_to_full_text(data["scenes"])
    print(f"Submitting {len(text)} characters of narration to D-ID...")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    try:
        create_talking_video(args.face_url, text, api_key, args.out, voice_id=args.voice_id)
    except AvatarError as e:
        raise SystemExit(f"D-ID render failed: {e}")
    print(f"Done: {args.out}")


if __name__ == "__main__":
    main()
