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


def make_scene_clip_from_video(
    video_path: Path,
    audio_path: Path,
    duration: float,
    out_path: Path,
    size: tuple[int, int],
) -> None:
    """Same job as make_scene_clip, but the visual is real stock footage
    instead of a Ken Burns pan over a still. -stream_loop -1 covers a clip
    shorter than the scene needs; -t then trims it (and a too-long clip)
    to the exact duration either way, so looping is a safe no-op when the
    source is already long enough.
    """
    w, h = size
    filter_complex = (
        f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},format=yuv420p[v]"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-stream_loop",
            "-1",
            "-i",
            str(video_path),
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


def extract_frame(source_path: Path, out_path: Path) -> None:
    """Grabs the first frame for the thumbnail. Works on both a real video
    clip and a static placeholder image. Deliberately does not seek with
    -ss: a still image is a near-zero-duration stream, so seeking even a
    fraction of a second into it fails ("could not seek to position") and
    ffmpeg exits 0 having written nothing -- confirmed by reproducing it
    directly. Frame 0 is unambiguous and works for both input types.
    """
    run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(source_path),
            "-frames:v",
            "1",
            "-update",
            "1",
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
