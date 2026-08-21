"""ffmpeg wrappers: one Ken Burns clip per scene, concatenated, with burned-in
captions. No re-encoding tricks beyond what a solo creator's laptop can run.
"""
import json
import subprocess
from pathlib import Path


def run(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(cmd)}\n{result.stderr}")


def get_duration(media_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(media_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(json.loads(result.stdout)["format"]["duration"])


def make_scene_clip(
    image_path: Path,
    audio_path: Path,
    duration: float,
    out_path: Path,
    size: tuple[int, int],
    zoom_in: bool,
    fps: int = 30,
) -> None:
    w, h = size
    frames = max(int(duration * fps), 1)
    if zoom_in:
        zoom_expr = "min(zoom+0.0015,1.4)"
    else:
        zoom_expr = "if(eq(on,0),1.4,max(zoom-0.0015,1.0))"

    filter_complex = (
        f"[0:v]scale={w * 2}:{h * 2}:force_original_aspect_ratio=increase,"
        f"crop={w * 2}:{h * 2},"
        f"zoompan=z='{zoom_expr}':d={frames}"
        f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps},"
        f"format=yuv420p[v]"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-loop",
            "1",
            "-i",
            str(image_path),
            "-i",
            str(audio_path),
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            "1:a",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            "-t",
            f"{duration:.3f}",
            "-shortest",
            str(out_path),
        ]
    )


def concat_clips(clip_paths: list[Path], out_path: Path) -> None:
    list_file = out_path.with_suffix(".txt")
    list_file.write_text("".join(f"file '{p.resolve()}'\n" for p in clip_paths))
    run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_file),
            "-c",
            "copy",
            str(out_path),
        ]
    )
    list_file.unlink(missing_ok=True)


def burn_captions(video_path: Path, ass_path: Path, out_path: Path) -> None:
    """ass_path must be a .ass file with its own PlayResX/PlayResY (see
    captions.write_ass) -- ffmpeg's plain-.srt autoconversion sizes and
    positions text against a hardcoded fallback resolution, not the video's.
    """
    run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-vf",
            f"ass={ass_path}",
            "-c:a",
            "copy",
            str(out_path),
        ]
    )
