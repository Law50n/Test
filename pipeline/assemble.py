"""ffmpeg wrappers: one Ken Burns clip per scene, concatenated, with burned-in
captions. No re-encoding tricks beyond what a solo creator's laptop can run.
"""
import json
import subprocess
from pathlib import Path

# Same bundled font as pipeline/fonts.py, passed to libass via fontsdir so
# it's found by name ("Anton", set in captions.write_ass's style) without
# needing to be installed on the OS -- avoids relying on whatever fonts
# happen to already be present on whichever machine renders this.
FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"

# A single, consistent grade applied to every scene regardless of source.
# Real Pexels photos and video each carry their own exposure/white balance,
# and our own placeholder cards are a third, different look -- with no
# shared grade, cutting between them reads as a mismatched slideshow
# rather than one edited video. A modest contrast/saturation push plus a
# gentle vignette unifies them without looking heavily filtered.
GRADE_FILTER = "eq=contrast=1.08:saturation=1.15,vignette=PI/6"

# Every clip must share this exact framerate before concat_clips crossfades
# them -- confirmed directly: xfade requires matching input timebases, and
# a Pexels video's native rate (24/25/29.97fps, whatever the source was
# shot at) is never guaranteed to match make_scene_clip's Ken Burns output.
# Reproduced the failure with two synthetic clips at 30fps and 25fps: this
# ffmpeg build rejected it outright ("timebase do not match"), but a
# different build could plausibly emit a technically-non-erroring file
# with broken frame timing that only a strict player (confirmed: Windows
# Media Player) refuses to open. Fixing this at the source is what
# actually prevents both failure modes.
SCENE_FPS = 30


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
    fps: int = SCENE_FPS,
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
        f"{GRADE_FILTER},format=yuv420p[v]"
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
        f"crop={w}:{h},{GRADE_FILTER},fps={SCENE_FPS},format=yuv420p[v]"
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


CROSSFADE_DURATION = 0.35  # seconds -- short enough to stay snappy at Shorts pacing


def concat_clips(clip_paths: list[Path], out_path: Path, crossfade: float = CROSSFADE_DURATION) -> None:
    """Crossfades between consecutive scenes instead of hard-cutting straight
    to the next one -- a hard cut every few seconds across mismatched stock
    sources reads as a slideshow; a short blend reads as an edited video.

    This replaces the old stream-copy concat demuxer with an xfade/
    acrossfade filter chain, since blending frames means actually
    re-encoding rather than just concatenating existing encoded streams.
    Each transition eats `crossfade` seconds from both neighboring clips
    (they overlap during the blend), so the output is shorter than the sum
    of the inputs by crossfade * (n - 1) -- callers tracking cumulative
    timing (caption offsets) must subtract that same amount per scene
    after the first, or captions drift out of sync more with every scene.
    """
    if len(clip_paths) == 1:
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(clip_paths[0]), "-c", "copy", str(out_path)])
        return

    durations = [get_duration(p) for p in clip_paths]
    inputs = []
    for p in clip_paths:
        inputs += ["-i", str(p)]

    filter_parts = []
    v_label, a_label = "0:v", "0:a"
    cumulative = durations[0]
    for i in range(1, len(clip_paths)):
        offset = max(cumulative - crossfade, 0.0)
        next_v, next_a = f"v{i}", f"a{i}"
        filter_parts.append(
            f"[{v_label}][{i}:v]xfade=transition=fade:duration={crossfade}:offset={offset:.3f}[{next_v}]"
        )
        filter_parts.append(f"[{a_label}][{i}:a]acrossfade=d={crossfade}[{next_a}]")
        v_label, a_label = next_v, next_a
        cumulative = cumulative + durations[i] - crossfade

    run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            *inputs,
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            f"[{v_label}]",
            "-map",
            f"[{a_label}]",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            str(out_path),
        ]
    )


def _escape_filter_path(path: Path) -> str:
    """ffmpeg's filtergraph parser splits filter options on ':', so a
    Windows path like 'C:\\Users\\...' gets torn apart at the drive
    letter -- escaping just that colon isn't enough for the ass/subtitles
    filter specifically (confirmed against ffmpeg 9.0.1: it still mis-splits
    on the escaped colon unless the whole value is single-quoted). Forward
    slashes are accepted on Windows too, so backslashes are swapped rather
    than escaped; the drive-letter colon is escaped and the value is passed
    as filename='...' rather than a bare positional value.
    """
    return "'" + str(path).replace("\\", "/").replace(":", "\\:") + "'"


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
            f"ass=filename={_escape_filter_path(ass_path)}:fontsdir={_escape_filter_path(FONTS_DIR)}",
            "-c:a",
            "copy",
            str(out_path),
        ]
    )
