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


def build(script_path: Path, cfg: Config, out_dir: Path) -> None:
    script = VideoScript.load(script_path)
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
            if first_visual is None:
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
        font_size = max(cfg.size[0] // 22, 18)
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
        thumbnail.make_thumbnail(thumb_source, script.title, out_dir / "thumbnail.jpg")

        shutil.copy(srt_path, out_dir / "captions.srt")

    (out_dir / "metadata.txt").write_text(
        f"Title: {script.title}\n"
        f"Category/playlist: {script.category}\n\n"
        f"{script.description}\n\n"
        f"Tags: {', '.join(script.tags)}\n"
    )

    print(f"\nDone: {out_dir}/")
    print("  video.mp4, thumbnail.jpg, captions.srt, metadata.txt")


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
