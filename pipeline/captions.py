"""Builds an SRT file from either real word-boundary timing (edge engine) or
a duration-based estimate (offline engine).
"""
from pathlib import Path

MAX_WORDS_PER_LINE = 6


def words_to_captions(words: list[dict], max_words: int = MAX_WORDS_PER_LINE) -> list[dict]:
    """words: [{"word", "start", "end"}, ...] -> [{"start", "end", "text"}, ...]"""
    captions = []
    for i in range(0, len(words), max_words):
        chunk = words[i : i + max_words]
        captions.append(
            {
                "start": chunk[0]["start"],
                "end": chunk[-1]["end"],
                "text": "".join(w["word"] for w in chunk).strip(),
            }
        )
    return captions


def estimate_word_timings(text: str, duration: float) -> list[dict]:
    """No per-word timing available (offline/piper engines): split the script
    text into words and distribute the known clip duration by word length
    rather than splitting it evenly. Real speech takes longer on longer
    words, so this tracks actual pacing noticeably better than a flat
    per-word split, though it's still an estimate, not measured timing.
    """
    words = text.split()
    if not words:
        return []
    # +1 approximates the brief gap after each word, so a run of short words
    # doesn't get compressed into an unnaturally clipped caption pace.
    weights = [len(w) + 1 for w in words]
    total_weight = sum(weights)
    timings = []
    cursor = 0.0
    for word, weight in zip(words, weights):
        share = duration * (weight / total_weight)
        timings.append({"word": word + " ", "start": cursor, "end": cursor + share})
        cursor += share
    return timings


def _srt_timestamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    ms = round(seconds * 1000)
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(captions: list[dict], out_path: Path) -> None:
    lines = []
    for i, cap in enumerate(captions, start=1):
        lines.append(str(i))
        lines.append(f"{_srt_timestamp(cap['start'])} --> {_srt_timestamp(cap['end'])}")
        lines.append(cap["text"])
        lines.append("")
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _ass_timestamp(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    cs = round(seconds * 100)
    h, cs = divmod(cs, 360_000)
    m, cs = divmod(cs, 6_000)
    s, cs = divmod(cs, 100)
    return f"{h:01d}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_escape(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\n", "\\N")


def write_ass(captions: list[dict], out_path: Path, size: tuple[int, int], font_size: int, margin_v: int) -> None:
    """A plain .srt burned via ffmpeg's `subtitles` filter gets its font size
    and margins interpreted against libass's fallback script resolution
    (384x288), not the actual video size -- captions come out oversized and
    mispositioned. Writing PlayResX/PlayResY ourselves avoids that.
    """
    w, h = size
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {w}\n"
        f"PlayResY: {h}\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,DejaVu Sans,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
        f"-1,0,0,0,100,100,0,0,1,2,0,2,40,40,{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events = "".join(
        f"Dialogue: 0,{_ass_timestamp(c['start'])},{_ass_timestamp(c['end'])},Default,,0,0,0,,"
        f"{_ass_escape(c['text'])}\n"
        for c in captions
    )
    out_path.write_text(header + events, encoding="utf-8")
