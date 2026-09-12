"""End-to-end: one or more script JSONs in, one captioned vertical (or
horizontal) video and a thumbnail out per script.

    python -m pipeline.run content/scripts/science/001-mantis-shrimp-punch.json
    python -m pipeline.run content/scripts/tech/*.json   # a whole category
"""
import argparse
import glob
import shutil
import sys
import tempfile
from pathlib import Path

from pipeline import assemble, captions, image_gen, thumbnail, video_clips, visuals
from pipeline.config import Config
from pipeline.image_gen import ImageGenError
from pipeline.script_loader import VideoScript
from pipeline.text_normalize import normalize_dates_for_speech
from pipeline.tts import TTSError, synthesize


# Which of the two YouTube channels each category uploads to -- "stories"
# (Shorts and longform/compilation alike) goes on the mysteries channel,
# everything else goes on the facts channel. Printed into metadata.txt so
# a folder of rendered videos says where each one goes without having to
# remember the mapping by hand; update this if a category ever needs to
# move channels or a third channel gets added.
CHANNEL_BY_CATEGORY = {"stories": "Mysteries"}
DEFAULT_CHANNEL = "Facts"


def _compose_metadata(script: VideoScript) -> str:
    """Builds metadata.txt's content, folding script.sources into a
    "Sources:" line automatically instead of requiring it typed by hand
    into the end of `description` -- see script_loader.VideoScript.sources.
    """
    channel = CHANNEL_BY_CATEGORY.get(script.category, DEFAULT_CHANNEL)
    body = script.description
    if script.sources:
        body = f"{body}\n\nSources: {'; '.join(script.sources)}."
    return (
        f"Title: {script.title}\n"
        f"Channel: {channel}\n"
        f"Category/playlist: {script.category}\n\n"
        f"{body}\n\n"
        f"Tags: {', '.join(script.tags)}\n"
    )


def build(script_path: Path, cfg: Config, out_dir: Path) -> None:
    script = VideoScript.load(script_path)
    if script.format == "compilation":
        build_compilation(script, cfg, out_dir)
    elif script.format == "longform":
        build_longform(script, cfg, out_dir)
    else:
        build_short(script, cfg, out_dir)


def build_short(script: VideoScript, cfg: Config, out_dir: Path) -> None:
    out_dir = out_dir / script.category / script.id
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"{script.id}-") as tmp:
        tmp_dir = Path(tmp)
        clip_paths: list[Path] = []
        all_captions: list[dict] = []
        cursor = 0.0
        first_visual: Path | None = None
        first_visual_query = ""
        first_visual_was_placeholder = False

        for i, scene in enumerate(script.scenes):
            narration = normalize_dates_for_speech(scene.text)
            print(f"[{i + 1}/{len(script.scenes)}] {narration[:60]}...")

            audio_path = tmp_dir / f"scene_{i:02d}.mp3"
            try:
                words = synthesize(narration, audio_path, cfg)
            except TTSError as e:
                print(f"  ! TTS failed: {e}", file=sys.stderr)
                raise SystemExit(1)
            assemble.normalize_audio(audio_path)
            duration = assemble.get_duration(audio_path)

            clip_path = tmp_dir / f"clip_{i:02d}.mp4"
            if scene.local_image is not None:
                # A specific, provided-in-advance image (project artwork,
                # a frame pulled from a reference clip, etc.) instead of a
                # Pexels search or a generated placeholder -- still gets
                # the same Ken Burns treatment as any other still image.
                visual_path = scene.local_image
                source = "local_image"
                print(f"  visual: {source} ({visual_path.name})")
                assemble.make_scene_clip(
                    visual_path, audio_path, duration, clip_path, cfg.size, zoom_in=(i % 2 == 0)
                )
            elif script.visual_mode == "video":
                visual_path = tmp_dir / f"scene_{i:02d}.media"
                source = video_clips.fetch_video_clip(
                    scene.visual_query, visual_path, cfg.pexels_api_key, cfg.size, duration
                )
                print(f"  visual: {source} ({scene.visual_query!r})")
                if source == "pexels_video":
                    assemble.make_scene_clip_from_video(visual_path, audio_path, duration, clip_path, cfg.size)
                    # A stock clip that passed the download-size check can
                    # still be subtly corrupt in a way ffmpeg doesn't error
                    # on -- confirmed to produce a badly broken/glitchy,
                    # way-too-long scene instead of a clean failure. Catch
                    # that here by checking the clip we just built actually
                    # matches the audio it's paired with, and fall back to
                    # a placeholder rather than ship broken footage.
                    if abs(assemble.get_duration(clip_path) - duration) > 0.75:
                        print(
                            f"  ! scene clip duration is way off from its audio "
                            f"(likely a corrupt download) -- using a placeholder instead"
                        )
                        source = "placeholder"
                        visuals.generate_placeholder(scene.visual_query, visual_path, cfg.size)
                        assemble.make_scene_clip(
                            visual_path, audio_path, duration, clip_path, cfg.size, zoom_in=(i % 2 == 0)
                        )
                else:
                    assemble.make_scene_clip(
                        visual_path, audio_path, duration, clip_path, cfg.size, zoom_in=(i % 2 == 0)
                    )
            elif script.visual_mode == "generated":
                visual_path = tmp_dir / f"scene_{i:02d}.png"
                try:
                    image_gen.generate_image(
                        scene.visual_query, visual_path, cfg.gemini_api_key, script.image_style_prompt,
                        cfg.gemini_image_model,
                    )
                    source = "generated"
                except ImageGenError as e:
                    print(f"  ! image generation failed for {scene.visual_query!r} ({e}); using a placeholder instead")
                    visuals.generate_placeholder(scene.visual_query, visual_path, cfg.size)
                    source = "placeholder"
                print(f"  visual: {source} ({scene.visual_query!r})")
                assemble.make_scene_clip(
                    visual_path, audio_path, duration, clip_path, cfg.size, zoom_in=(i % 2 == 0)
                )
            else:
                visual_path = tmp_dir / f"scene_{i:02d}.jpg"
                source = visuals.fetch_visual(scene.visual_query, visual_path, cfg.pexels_api_key, cfg.size)
                print(f"  visual: {source} ({scene.visual_query!r})")
                assemble.make_scene_clip(
                    visual_path, audio_path, duration, clip_path, cfg.size, zoom_in=(i % 2 == 0)
                )
            if i == script.thumbnail_scene:
                first_visual = visual_path
                first_visual_query = scene.visual_query
                first_visual_was_placeholder = source == "placeholder"

            # The clip's real rendered length can be a touch shorter than
            # its audio's nominal duration -- zoompan quantizes to whole
            # frames, and -shortest then quietly trims the audio to match.
            # Confirmed by direct measurement: using the audio-based
            # `duration` for cross-scene timing instead of this compounds
            # a growing gap between the concatenated video's real length
            # and where captions think each scene starts.
            clip_duration = assemble.get_duration(clip_path)

            if words:
                for w in words:
                    all_captions.append({**w, "start": w["start"] + cursor, "end": w["end"] + cursor})
            else:
                for w in captions.estimate_word_timings(narration, duration):
                    all_captions.append({**w, "start": w["start"] + cursor, "end": w["end"] + cursor})
            # Every scene after the first overlaps the previous one by
            # assemble.CROSSFADE_DURATION once concat_clips blends them
            # together, so each one actually starts that much earlier in
            # the final video than a plain sum of durations would suggest
            # -- skipping this would drift captions further out of sync
            # with every scene.
            cursor += clip_duration if i == 0 else clip_duration - assemble.CROSSFADE_DURATION

            clip_paths.append(clip_path)

        print("Concatenating scenes...")
        concat_path = tmp_dir / "concat.mp4"
        assemble.concat_clips(clip_paths, concat_path)

        print("Writing captions...")
        srt_path = tmp_dir / "captions.srt"
        caption_lines = captions.words_to_captions(all_captions)
        captions.write_srt(caption_lines, srt_path)
        ass_path = tmp_dir / "captions.ass"
        font_size = max(cfg.size[0] // 15, 18)
        margin_v = cfg.size[1] // 7
        captions.write_ass_karaoke(all_captions, ass_path, cfg.size, font_size, margin_v)

        print("Burning in captions...")
        final_video = out_dir / "video.mp4"
        assemble.burn_captions(concat_path, ass_path, final_video)

        print("Building thumbnail...")
        thumb_source = tmp_dir / "thumb_source.jpg"
        if first_visual_was_placeholder:
            # The scene's own placeholder is labeled with its search query;
            # thumbnail.make_thumbnail() draws the real title over the same
            # bottom third, so reusing that file ghosts one label behind the
            # other. Render a clean, unlabeled card instead, just for this.
            visuals.generate_placeholder_unlabeled(first_visual_query, thumb_source, cfg.size)
        else:
            assemble.extract_frame(first_visual, thumb_source)
        thumbnail.make_thumbnail(thumb_source, script.title, out_dir / "thumbnail.jpg", script.thumbnail_highlight)

        shutil.copy(srt_path, out_dir / "captions.srt")

    (out_dir / "metadata.txt").write_text(_compose_metadata(script))

    print(f"\nDone: {out_dir}/")
    print("  video.mp4, thumbnail.jpg, captions.srt, metadata.txt")


def _synthesize_scene(
    text: str, out_path: Path, cfg: Config, cursor: float, all_captions: list[dict]
) -> float:
    """Synthesizes one line of narration, normalizes it, and appends its
    word timings (offset by `cursor`) onto `all_captions` in place. Shared
    by every longform/compilation code path that needs "one more spoken
    line added to the running track" -- scene narration and the spoken
    transitions between compilation episodes are otherwise the same
    operation. Returns the line's duration.
    """
    try:
        words = synthesize(text, out_path, cfg)
    except TTSError as e:
        print(f"  ! TTS failed: {e}", file=sys.stderr)
        raise SystemExit(1)
    assemble.normalize_audio(out_path)
    duration = assemble.get_duration(out_path)
    if words:
        for w in words:
            all_captions.append({**w, "start": w["start"] + cursor, "end": w["end"] + cursor})
    else:
        for w in captions.estimate_word_timings(text, duration):
            all_captions.append({**w, "start": w["start"] + cursor, "end": w["end"] + cursor})
    return duration


def _build_longform_segment(script: VideoScript, cfg: Config, tmp_dir: Path, prefix: str, cursor_start: float) -> dict:
    """Synthesizes narration and builds the held-visual background for one
    longform script's scenes, stopping short of the final mux/caption-burn/
    thumbnail steps. Shared by build_longform (one episode, standalone) and
    build_compilation (several of these back to back with a spoken
    transition in between). Returns narration_path, background_path, this
    segment's captions (already offset by cursor_start), and its total
    duration.
    """
    audio_paths: list[Path] = []
    all_captions: list[dict] = []
    cursor = cursor_start

    for i, scene in enumerate(script.scenes):
        narration = normalize_dates_for_speech(scene.text)
        print(f"  [{i + 1}/{len(script.scenes)}] {narration[:60]}...")
        audio_path = tmp_dir / f"{prefix}_scene_{i:02d}.mp3"
        cursor += _synthesize_scene(narration, audio_path, cfg, cursor, all_captions)
        audio_paths.append(audio_path)

    narration_path = tmp_dir / f"{prefix}_narration.mp3"
    assemble.concat_audio(audio_paths, narration_path)
    total_duration = assemble.get_duration(narration_path)
    print(f"  segment narration: {total_duration:.1f}s")

    images = script.background_images
    n = len(images)
    # Built a bit longer than an even split so the (possibly crossfaded)
    # background is never shorter than the narration -- always, even for a
    # single image (n==1), since a compilation crossfades *between*
    # segments too and needs the same trailing slack there that concat_clips
    # already gives a multi-image segment internally. mux_audio's -shortest
    # then trims any excess rather than risking the background running out
    # before the narration does.
    hold_duration = total_duration / n + assemble.LONGFORM_CROSSFADE_DURATION
    hero_clips = []
    for idx, img in enumerate(images):
        clip_path = tmp_dir / f"{prefix}_hero_{idx:02d}.mp4"
        assemble.make_hero_clip(img, hold_duration, clip_path, cfg.size, zoom_in=(idx % 2 == 0))
        hero_clips.append(clip_path)

    bg_path = tmp_dir / f"{prefix}_bg.mp4"
    if n == 1:
        shutil.copy(hero_clips[0], bg_path)
    else:
        assemble.concat_clips(hero_clips, bg_path, crossfade=assemble.LONGFORM_CROSSFADE_DURATION)

    return {
        "narration_path": narration_path,
        "background_path": bg_path,
        "captions": all_captions,
        "duration": total_duration,
    }


def _finish_longform_output(
    script: VideoScript,
    cfg: Config,
    out_dir: Path,
    tmp_dir: Path,
    muxed_path: Path,
    all_captions: list[dict],
    thumbnail_source: Path,
) -> None:
    """The tail end shared by build_longform and build_compilation once
    each has its own fully-assembled, narration-muxed video: captions,
    caption burn-in, thumbnail, metadata.
    """
    print("Writing captions...")
    srt_path = tmp_dir / "captions.srt"
    caption_lines = captions.words_to_captions(all_captions)
    captions.write_srt(caption_lines, srt_path)
    ass_path = tmp_dir / "captions.ass"
    # Bigger and more vertically centered than the Shorts treatment -- here
    # the captions ARE the primary visual interest (a "read along"
    # experience over a mostly-static screen), not a bottom-third
    # accessibility afterthought.
    font_size = max(cfg.size[0] // 11, 18)
    margin_v = cfg.size[1] // 2 - font_size
    captions.write_ass_karaoke(all_captions, ass_path, cfg.size, font_size, margin_v)

    print("Burning in captions...")
    final_video = out_dir / "video.mp4"
    assemble.burn_captions(muxed_path, ass_path, final_video)

    print("Building thumbnail...")
    thumbnail.make_thumbnail(thumbnail_source, script.title, out_dir / "thumbnail.jpg", script.thumbnail_highlight)

    shutil.copy(srt_path, out_dir / "captions.srt")

    (out_dir / "metadata.txt").write_text(_compose_metadata(script))

    print(f"\nDone: {out_dir}/")
    print("  video.mp4, thumbnail.jpg, captions.srt, metadata.txt")


def build_longform(script: VideoScript, cfg: Config, out_dir: Path) -> None:
    """One continuous narration track held under a small set of slowly-
    panning background_images, crossfading between them every few minutes,
    instead of cutting to a new visual every scene -- for content meant to
    be listened to (audiobook-style), where the captions carry the visual
    interest rather than per-scene imagery. See README for how this
    differs from build_short.
    """
    out_dir = out_dir / script.category / script.id
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"{script.id}-") as tmp:
        tmp_dir = Path(tmp)
        seg = _build_longform_segment(script, cfg, tmp_dir, "ep", 0.0)

        print("Muxing narration onto the background...")
        muxed_path = tmp_dir / "muxed.mp4"
        assemble.mux_audio(seg["background_path"], seg["narration_path"], muxed_path)

        _finish_longform_output(
            script, cfg, out_dir, tmp_dir, muxed_path, seg["captions"], script.background_images[0]
        )


def build_compilation(script: VideoScript, cfg: Config, out_dir: Path) -> None:
    """Stitches several existing longform-format scripts (script.episodes)
    into one continuous sitting -- one narration track, one background
    track, a short spoken transition between each story ("Case two:
    <title>.") instead of one case bleeding straight into the next. Each
    episode keeps its own background_images for its own segment; the
    compilation script itself only needs id/category/title/description/
    tags/format/episodes, no scenes of its own.
    """
    out_dir = out_dir / script.category / script.id
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"{script.id}-") as tmp:
        tmp_dir = Path(tmp)
        narration_paths: list[Path] = []
        background_paths: list[Path] = []
        all_captions: list[dict] = []
        cursor = 0.0
        first_image: Path | None = None

        for ep_idx, ep_path in enumerate(script.episodes):
            episode = VideoScript.load(ep_path)
            if episode.format != "longform":
                raise SystemExit(
                    f"compilation episode {ep_path} must itself be format=\"longform\", got {episode.format!r}"
                )
            print(f"\n=== Episode {ep_idx + 1}/{len(script.episodes)}: {episode.title} ===")

            if first_image is None:
                first_image = episode.background_images[0]

            if ep_idx > 0:
                # A short spoken seam between stories -- without this, one
                # case's ending trails straight into the next case's cold
                # open with nothing to mark the change.
                intro_text = f"Case {ep_idx + 1}. {episode.title}."
                intro_audio = tmp_dir / f"intro_{ep_idx:02d}.mp3"
                intro_duration = _synthesize_scene(intro_text, intro_audio, cfg, cursor, all_captions)
                cursor += intro_duration
                narration_paths.append(intro_audio)

                intro_bg = tmp_dir / f"intro_bg_{ep_idx:02d}.mp4"
                assemble.make_hero_clip(
                    episode.background_images[0],
                    intro_duration + assemble.LONGFORM_CROSSFADE_DURATION,
                    intro_bg,
                    cfg.size,
                    zoom_in=True,
                )
                background_paths.append(intro_bg)

            seg = _build_longform_segment(episode, cfg, tmp_dir, f"ep{ep_idx}", cursor)
            all_captions.extend(seg["captions"])
            cursor += seg["duration"]
            narration_paths.append(seg["narration_path"])
            background_paths.append(seg["background_path"])

        print("\nConcatenating all narration...")
        narration_path = tmp_dir / "narration.mp3"
        assemble.concat_audio(narration_paths, narration_path)

        print("Concatenating all backgrounds...")
        bg_path = tmp_dir / "bg.mp4"
        if len(background_paths) == 1:
            shutil.copy(background_paths[0], bg_path)
        else:
            assemble.concat_clips(background_paths, bg_path, crossfade=assemble.LONGFORM_CROSSFADE_DURATION)

        print("Muxing narration onto the background...")
        muxed_path = tmp_dir / "muxed.mp4"
        assemble.mux_audio(bg_path, narration_path, muxed_path)

        _finish_longform_output(script, cfg, out_dir, tmp_dir, muxed_path, all_captions, first_image)


def _expand_globs(patterns: list[Path]) -> list[Path]:
    """bash/zsh expand a wildcard like content/scripts/tech/*.json into a
    file list before this script ever sees it, but Windows' cmd.exe and
    PowerShell both pass the literal '*.json' straight through -- so on
    Windows every argument here needs expanding ourselves. glob.glob() on
    a plain filename with no wildcard just returns that filename unchanged,
    so this is a safe no-op on Linux/Mac where the shell already expanded it.
    """
    paths = []
    for pattern in patterns:
        matches = sorted(Path(m) for m in glob.glob(str(pattern)))
        paths.extend(matches if matches else [pattern])
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "scripts", type=Path, nargs="+", help="one or more content/scripts/**/*.json files"
    )
    parser.add_argument("--out", type=Path, default=Path("output"), help="output directory")
    args = parser.parse_args()
    args.scripts = _expand_globs(args.scripts)

    cfg = Config.load()
    print(f"engine={cfg.tts_engine} voice={cfg.tts_voice} format={cfg.video_format} size={cfg.size}")

    if len(args.scripts) == 1:
        build(args.scripts[0], cfg, args.out)
        return

    failed = []
    for i, script_path in enumerate(args.scripts, start=1):
        print(f"\n=== [{i}/{len(args.scripts)}] {script_path} ===")
        try:
            build(script_path, cfg, args.out)
        except (SystemExit, Exception) as e:
            if not isinstance(e, SystemExit):
                print(f"  ! {script_path} failed: {e}", file=sys.stderr)
            failed.append(script_path)
    if failed:
        print(f"\n{len(failed)} of {len(args.scripts)} script(s) failed:", file=sys.stderr)
        for p in failed:
            print(f"  {p}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
