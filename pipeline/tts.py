"""Text-to-speech. Returns per-word timing so captions can be built without
running a separate speech-recognition pass over our own generated audio.
"""
import asyncio
import subprocess
from pathlib import Path

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
        return _synthesize_piper(text, out_mp3, cfg.piper_model_path, cfg.piper_speaker_id)
    raise TTSError(f"Unknown TTS_ENGINE {cfg.tts_engine!r}, expected 'edge', 'offline', or 'piper'")


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


def _synthesize_piper(text: str, out_mp3: Path, model_path: str, speaker_id: int) -> list[dict]:
    """Local neural TTS via Piper (https://github.com/rhasspy/piper) -- no
    internet needed at synthesis time, and far more natural than espeak-ng.
    No word-level timing (same tradeoff as the offline engine).

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
