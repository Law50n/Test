"""End-to-end: one script JSON in, one captioned vertical (or horizontal)
video and a thumbnail out.

    python -m pipeline.run content/scripts/001-mantis-shrimp.json
"""
import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from pipeline import assemble, captions, thumbnail, visuals
from pipeline.config import Config
from pipeline.script_loader import VideoScript
from pipeline.tts import TTSError, synthesize


def build(script_path: Path, cfg: Config, out_dir: Path) -> None:
    script = VideoScript.load(script_path)
    out_dir = out_dir / script.id
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"{script.id}-") as tmp:
        tmp_dir = Path(tmp)
        clip_paths: list[Path] = []
        all_captions: list[dict] = []
        cursor = 0.0
        first_visual: Path | None = None

        for i, scene in enumerate(script.scenes):
            print(f"[{i + 1}/{len(script.scenes)}] {scene.text[:60]}...")

            audio_path = tmp_dir / f"scene_{i:02d}.mp3"
            try:
                words = synthesize(scene.text, audio_path, cfg.tts_engine, cfg.tts_voice)
            except TTSError as e:
                print(f"  ! TTS failed: {e}", file=sys.stderr)
                raise SystemExit(1)
            duration = assemble.get_duration(audio_path)

            image_path = tmp_dir / f"scene_{i:02d}.jpg"
            source = visuals.fetch_visual(scene.visual_query, image_path, cfg.pexels_api_key, cfg.size)
            print(f"  visual: {source} ({scene.visual_query!r})")
            if first_visual is None:
                first_visual = image_path

            if words:
                for w in words:
                    all_captions.append({**w, "start": w["start"] + cursor, "end": w["end"] + cursor})
            else:
                for w in captions.estimate_word_timings(scene.text, duration):
                    all_captions.append({**w, "start": w["start"] + cursor, "end": w["end"] + cursor})
            cursor += duration

            clip_path = tmp_dir / f"clip_{i:02d}.mp4"
            assemble.make_scene_clip(
                image_path, audio_path, duration, clip_path, cfg.size, zoom_in=(i % 2 == 0)
            )
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
        captions.write_ass(caption_lines, ass_path, cfg.size, font_size, margin_v)

        print("Burning in captions...")
        final_video = out_dir / "video.mp4"
        assemble.burn_captions(concat_path, ass_path, final_video)

        print("Building thumbnail...")
        thumbnail.make_thumbnail(first_visual, script.title, out_dir / "thumbnail.jpg")

        shutil.copy(srt_path, out_dir / "captions.srt")

    (out_dir / "metadata.txt").write_text(
        f"Title: {script.title}\n"
        f"Category/playlist: {script.category}\n\n"
        f"{script.description}\n\n"
        f"Tags: {', '.join(script.tags)}\n"
    )

    print(f"\nDone: {out_dir}/")
    print("  video.mp4, thumbnail.jpg, captions.srt, metadata.txt")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script", type=Path, help="path to a content/scripts/*.json file")
    parser.add_argument("--out", type=Path, default=Path("output"), help="output directory")
    args = parser.parse_args()

    cfg = Config.load()
    print(f"engine={cfg.tts_engine} voice={cfg.tts_voice} format={cfg.video_format} size={cfg.size}")
    build(args.script, cfg, args.out)


if __name__ == "__main__":
    main()
