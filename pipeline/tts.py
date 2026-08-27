"""Text-to-speech. Returns per-word timing so captions can be built without
running a separate speech-recognition pass over our own generated audio.
"""
import asyncio
import subprocess
from pathlib import Path

import requests

from pipeline.config import Config


class TTSError(RuntimeError):
    pass


def synthesize(text: str, out_mp3: Path, cfg: Config) -> list[dict]:
    """Renders `text` to `out_mp3`. Returns a list of
    {"word": str, "start": float, "end": float} in seconds, relative to the
    start of this clip. Empty list if the engine can't provide word timing.
    """
    if cfg.tts_engine == "edge":
        return asyncio.run(_synthesize_edge(text, out_mp3, cfg.tts_voice))
    if cfg.tts_engine == "offline":
        return _synthesize_offline(text, out_mp3)
    if cfg.tts_engine == "piper":
        return _synthesize_piper(
            text,
            out_mp3,
            cfg.piper_model_path,
            cfg.piper_speaker_id,
            cfg.piper_sentence_silence,
            cfg.piper_noise_scale,
            cfg.piper_noise_w,
        )
    if cfg.tts_engine == "elevenlabs":
        return _synthesize_elevenlabs(text, out_mp3, cfg.elevenlabs_api_key, cfg.elevenlabs_voice_id)
    raise TTSError(
        f"Unknown TTS_ENGINE {cfg.tts_engine!r}, expected 'edge', 'offline', 'piper', or 'elevenlabs'"
    )


async def _synthesize_edge(text: str, out_mp3: Path, voice: str) -> list[dict]:
    import edge_tts

    words: list[dict] = []
    try:
        communicate = edge_tts.Communicate(text, voice)
        with open(out_mp3, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    # edge-tts reports offsets in 100-nanosecond units. Each
                    # "text" is a bare word with no trailing space, so add one
                    # here -- captions.words_to_captions() joins these back
                    # together and expects the same convention _synthesize_offline
                    # below already uses.
                    words.append(
                        {
                            "word": chunk["text"] + " ",
                            "start": chunk["offset"] / 1e7,
                            "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                        }
                    )
    except TTSError:
        raise
    except Exception as e:
        raise TTSError(f"edge-tts failed: {e}") from e
    if out_mp3.stat().st_size == 0:
        raise TTSError(
            "edge-tts returned no audio (usually a network/firewall issue reaching "
            "Microsoft's speech service). Try TTS_ENGINE=offline to test the "
            "pipeline without internet."
        )
    return words


def _synthesize_offline(text: str, out_mp3: Path) -> list[dict]:
    """espeak-ng fallback: no internet required, no word-level timing, and
    a noticeably robotic formant voice -- see TTS_ENGINE=piper for a much
    more natural-sounding option that's still fully offline.
    """
    wav_path = out_mp3.with_suffix(".tmp.wav")
    try:
        subprocess.run(
            ["espeak-ng", "-v", "en-us", "-s", "160", "-w", str(wav_path), text],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path), str(out_mp3)],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as e:
        raise TTSError(
            "offline engine needs espeak-ng and ffmpeg on PATH "
            "(e.g. `apt-get install espeak-ng ffmpeg`)"
        ) from e
    except subprocess.CalledProcessError as e:
        raise TTSError(f"espeak-ng/ffmpeg failed: {e.stderr.decode(errors='replace')}") from e
    finally:
        wav_path.unlink(missing_ok=True)
    return []


def _synthesize_piper(
    text: str,
    out_mp3: Path,
    model_path: str,
    speaker_id: int,
    sentence_silence: float,
    noise_scale: float,
    noise_w: float,
) -> list[dict]:
    """Local neural TTS via Piper (https://github.com/rhasspy/piper) -- no
    internet needed at synthesis time, and far more natural than espeak-ng.
    No word-level timing (same tradeoff as the offline engine).

    sentence_silence adds a pause between sentences within one scene's text.
    Without it, multi-sentence scenes run straight into the next sentence
    with no breath -- confirmed by listening comparison that this, not the
    speaker choice, was the main thing making the default sound rushed/flat.

    noise_scale/noise_w raise generator and phoneme-duration variation above
    Piper's defaults (0.667/0.8) -- confirmed by listening comparison across
    5 variants that this combination read as noticeably less monotone than
    the model's defaults, more than switching speakers did.

    Needs a voice model downloaded once -- see README setup.
    """
    if not Path(model_path).exists():
        raise TTSError(
            f"Piper voice model not found at {model_path!r}. Download it first -- see "
            "README's \"Better offline voice: Piper\" section for the exact command."
        )
    wav_path = out_mp3.with_suffix(".tmp.wav")
    try:
        subprocess.run(
            [
                "python3",
                "-m",
                "piper",
                "-m",
                model_path,
                "--speaker",
                str(speaker_id),
                "--sentence-silence",
                str(sentence_silence),
                "--noise-scale",
                str(noise_scale),
                "--noise-w-scale",
                str(noise_w),
                "-f",
                str(wav_path),
            ],
            input=text.encode(),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav_path), str(out_mp3)],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as e:
        raise TTSError("piper engine needs `pip install piper-tts` and ffmpeg on PATH") from e
    except subprocess.CalledProcessError as e:
        raise TTSError(f"piper/ffmpeg failed: {e.stderr.decode(errors='replace')}") from e
    finally:
        wav_path.unlink(missing_ok=True)
    return []


ELEVENLABS_API_BASE = "https://api.elevenlabs.io/v1"


def _synthesize_elevenlabs(text: str, out_mp3: Path, api_key: str, voice_id: str) -> list[dict]:
    """Paid/free-tier cloud TTS (https://elevenlabs.io) -- the quality
    ceiling above everything else in this file, at the cost of needing an
    account, a key, and internet at render time.

    Unverified: this sandbox's network policy blocks api.elevenlabs.io (same
    as api.pexels.com and api.d-id.com), so this has not been run against
    the real API. The request/response shape matches ElevenLabs'
    long-documented /text-to-speech/{voice_id}/with-timestamps endpoint, but
    confirm against your own dashboard/docs before relying on it.

    Uses the with-timestamps endpoint specifically because it returns real
    character-level alignment -- converted to word timing below -- instead
    of the estimated timing the offline/piper engines fall back to. This
    should give the tightest caption sync of any engine in this file,
    edge included.

    ElevenLabs' free-tier API access has genuinely conflicting reports as of
    when this was written (some sources say API access is paid-only, others
    say a small free monthly quota is included) -- confirm current terms on
    your own account rather than assuming either way.
    """
    if not api_key:
        raise TTSError("ELEVENLABS_API_KEY is not set")
    try:
        resp = requests.post(
            f"{ELEVENLABS_API_BASE}/text-to-speech/{voice_id}/with-timestamps",
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
            json={"text": text, "model_id": "eleven_multilingual_v2"},
            timeout=60,
        )
        if resp.status_code >= 400:
            raise TTSError(f"ElevenLabs request failed: HTTP {resp.status_code}: {resp.text[:300]}")
        data = resp.json()
    except TTSError:
        raise
    except requests.exceptions.RequestException as e:
        raise TTSError(f"request to ElevenLabs failed: {e}") from e
    except ValueError as e:
        raise TTSError(f"unexpected response from ElevenLabs: {e}") from e

    import base64

    try:
        out_mp3.write_bytes(base64.b64decode(data["audio_base64"]))
        alignment = data.get("alignment") or {}
        words = _chars_to_words(
            alignment.get("characters", []),
            alignment.get("character_start_times_seconds", []),
            alignment.get("character_end_times_seconds", []),
        )
    except (KeyError, ValueError) as e:
        raise TTSError(f"unexpected response shape from ElevenLabs: {e}") from e
    return words


def _chars_to_words(chars: list[str], starts: list[float], ends: list[float]) -> list[dict]:
    """Groups ElevenLabs' per-character timing into per-word timing, in the
    same {"word", "start", "end"} shape every other engine here returns.
    """
    words: list[dict] = []
    current = ""
    current_start = None
    last_end = 0.0
    for ch, start, end in zip(chars, starts, ends):
        if ch.isspace():
            if current:
                words.append({"word": current + " ", "start": current_start, "end": last_end})
                current = ""
                current_start = None
        else:
            if current_start is None:
                current_start = start
            current += ch
        last_end = end
    if current:
        words.append({"word": current + " ", "start": current_start, "end": last_end})
    return words
