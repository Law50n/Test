# Faceless Channel Pipeline

Turns a script (JSON) into a captioned, vertical Short: text-to-speech
narration, stock or generated visuals with a Ken Burns pan/zoom, burned-in
captions, and a thumbnail. Every stage has a genuinely free path — see the
[blueprint](https://claude.ai/code/artifact/e2569c60-49e2-44b7-928c-6d35963d9351)
this was planned from for the niche pick and reasoning.

## Setup

```bash
sudo apt-get install ffmpeg espeak-ng   # espeak-ng only needed for --offline
pip install -r requirements.txt
cp .env.example .env
```

Get a free Pexels key at https://www.pexels.com/api/ (no cost, no card) and
put it in `.env` as `PEXELS_API_KEY`. Without a key, the pipeline still runs
end to end — it fills each scene with a generated placeholder card instead of
a real photo, which is useful for testing but not for actually publishing.

## Run it

```bash
python -m pipeline.run content/scripts/001-mantis-shrimp-punch.json
```

Output lands in `output/<script-id>/`: `video.mp4`, `thumbnail.jpg`,
`captions.srt` (upload as a caption track for accessibility/SEO), and
`metadata.txt` (title/description/tags to paste into YouTube Studio).

### Config (`.env` or environment variables)

| Variable | Default | Notes |
|---|---|---|
| `PEXELS_API_KEY` | (empty) | leave unset to use placeholder visuals |
| `TTS_ENGINE` | `edge` | `edge` (free, natural, needs internet) or `offline` (espeak-ng, robotic, no internet — good for testing) |
| `TTS_VOICE` | `en-US-GuyNeural` | any voice from `edge-tts --list-voices` |
| `VIDEO_FORMAT` | `short` | `short` = 1080x1920 (Shorts), `long` = 1920x1080 |

## Writing a new script

Drop a new JSON file in `content/scripts/`:

```json
{
  "id": "006-my-topic",
  "title": "Video title",
  "description": "YouTube description, hashtags included.",
  "tags": ["science facts", "shorts"],
  "scenes": [
    { "text": "One or two sentences of narration.", "visual_query": "search terms for a matching stock photo" }
  ]
}
```

Each scene becomes its own TTS clip + one Ken Burns still. Keep scene text to
a sentence or two — that's what keeps the visual change matched to the
narration beat.

### Two ways to source a script

**Evergreen facts** (scripts 001–005) — a standalone fact that doesn't depend
on anything currently happening. Ask Claude for a batch in this niche and
it'll write from general knowledge, following the schema above.

**Commentary on something real** (script 006 on) — research an actual current
claim, story, or hoax circulating right now, and write a script that reports
on and explains it, sources cited in the `description`. This is the
"clip other creators' content" idea in its legally sound form: you're not
re-uploading anyone's video, you're doing commentary/analysis on a claim —
the same fair-use footing as news coverage. Script 006 (the "Earth loses
gravity for 7 seconds" hoax) is a worked example: real viral claim, NASA's
actual debunk, sources in the description. Ask Claude to find a current
story in the niche and draft one of these when you want the channel to be
reacting to what's actually happening rather than running on an evergreen
backlog alone.

What this repo deliberately does **not** build: downloading and embedding
clips of someone else's video (reaction/picture-in-picture style). That's a
heavier pipeline with its own YouTube ToS exposure on top of the copyright
question, and straight re-uploads with no added commentary are the weakest
legal position of the three options — treat it as a separate decision, not
a natural next step from this pipeline.

## How captions get their timing

The `edge` engine reports word-level timestamps as it synthesizes (an
`edge_tts.Communicate` word-boundary event), so captions are built from that —
no separate speech-to-text pass needed on audio we generated ourselves. The
`offline` engine can't report timing, so its captions are evenly spread across
the clip's measured duration; good enough for testing, not as tight as `edge`.

Captions are burned in via a hand-written `.ass` file with explicit
`PlayResX`/`PlayResY` (see `pipeline/captions.py::write_ass`). Feeding ffmpeg's
`subtitles` filter a plain `.srt` instead sizes and positions text against a
hardcoded fallback resolution rather than the actual video, so it comes out
oversized and pinned near the top — that's the failure mode this avoids.

## What still needs a human

- A Pexels API key for real visuals (free, but you have to sign up for it).
- Reviewing script/topic output before it renders — nothing here auto-uploads.
- Actually uploading: `output/<id>/metadata.txt` has the title, description,
  and tags ready to paste into YouTube Studio.
