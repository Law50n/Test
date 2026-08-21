"""Text-to-speech. Returns per-word timing so captions can be built without
running a separate speech-recognition pass over our own generated audio.
"""
import asyncio
import subprocess
from pathlib import Path


class TTSError(RuntimeError):
    pass


def synthesize(text: str, out_mp3: Path, engine: str, voice: str) -> list[dict]:
    """Renders `text` to `out_mp3`. Returns a list of
    {"word": str, "start": float, "end": float} in seconds, relative to the
    start of this clip. Empty list if the engine can't provide word timing.
    """
    if engine == "edge":
        return asyncio.run(_synthesize_edge(text, out_mp3, voice))
    if engine == "offline":
        return _synthesize_offline(text, out_mp3, voice)
    raise TTSError(f"Unknown TTS_ENGINE {engine!r}, expected 'edge' or 'offline'")


async def _synthesize_edge(text: str, out_mp3: Path, voice: str) -> list[dict]:
    import edge_tts

    words: list[dict] = []
    communicate = edge_tts.Communicate(text, voice)
    with open(out_mp3, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # edge-tts reports offsets in 100-nanosecond units.
                words.append(
                    {
                        "word": chunk["text"],
                        "start": chunk["offset"] / 1e7,
                        "end": (chunk["offset"] + chunk["duration"]) / 1e7,
                    }
                )
    if out_mp3.stat().st_size == 0:
        raise TTSError(
            "edge-tts returned no audio (usually a network/firewall issue reaching "
            "Microsoft's speech service). Try TTS_ENGINE=offline to test the "
            "pipeline without internet."
        )
    return words


def _synthesize_offline(text: str, out_mp3: Path, voice: str) -> list[dict]:
    """espeak-ng fallback: no internet required, no word-level timing."""
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
