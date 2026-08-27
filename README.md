# Faceless Channel Pipeline

Turns a script (JSON) into a captioned, vertical Short: text-to-speech
narration, stock or generated visuals with a Ken Burns pan/zoom, burned-in
captions, and a thumbnail. Every stage has a genuinely free path — see the
[blueprint](https://claude.ai/code/artifact/e2569c60-49e2-44b7-928c-6d35963d9351)
this was planned from for the original niche reasoning (since revised, see
below).

## Multiple sectors, one channel

The channel now runs several content pillars at once instead of a single
niche: `science`, `tech`, `finance`, `wellbeing`, `stories`, with room for
more. One
tradeoff worth knowing going in: a single-niche channel usually gets
recommended faster early on, because YouTube's algorithm has a narrower
audience intent to match against. Running several pillars from day one
trades some of that early velocity for a faster read on which sector
actually resonates — reasonable, as long as each pillar stays organized
enough that a viewer (and the algorithm) can still tell what they're getting.
That's what `category` does: it's a playlist/series label, not decoration —
group each category into its own YouTube playlist so the structure carries
through to the channel itself, and watch view/retention numbers per category
to decide where to double down.

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
python -m pipeline.run content/scripts/science/001-mantis-shrimp-punch.json

# or a whole category / the whole backlog at once -- one bad script
# doesn't stop the rest, failures are summarized at the end
python -m pipeline.run content/scripts/tech/*.json
python -m pipeline.run content/scripts/*/*.json
```

Output lands in `output/<script-id>/`: `video.mp4`, `thumbnail.jpg`,
`captions.srt` (upload as a caption track for accessibility/SEO), and
`metadata.txt` (title/description/tags to paste into YouTube Studio).

### Config (`.env` or environment variables)

| Variable | Default | Notes |
|---|---|---|
| `PEXELS_API_KEY` | (empty) | leave unset to use placeholder visuals |
| `TTS_ENGINE` | `edge` | `edge` (free, natural, needs internet), `piper` (free, natural, fully offline — see below), or `offline` (espeak-ng, robotic, no download needed) |
| `TTS_VOICE` | `en-US-GuyNeural` | any voice from `edge-tts --list-voices` (only used by `TTS_ENGINE=edge`) |
| `PIPER_MODEL_PATH` | `voices/en-us-libritts-high.onnx` | only used by `TTS_ENGINE=piper` |
| `PIPER_SPEAKER_ID` | `90` | LibriTTS is a 904-speaker model; only used by `TTS_ENGINE=piper` |
| `PIPER_SENTENCE_SILENCE` | `0.35` | pause (seconds) between sentences within a scene; only used by `TTS_ENGINE=piper` |
| `PIPER_NOISE_SCALE` | `1.0` | generator variation, above Piper's own default of 0.667; only used by `TTS_ENGINE=piper` |
| `PIPER_NOISE_W` | `1.1` | phoneme-duration variation, above Piper's own default of 0.8; only used by `TTS_ENGINE=piper` |
| `VIDEO_FORMAT` | `short` | `short` = 1080x1920 (Shorts), `long` = 1920x1080 |

### Better offline voice: Piper

`edge` sounds the most natural but needs internet at render time; `offline`
(espeak-ng) never needs a network but sounds like a GPS unit from 2004.
[Piper](https://github.com/rhasspy/piper) closes most of that gap: a real
neural voice, fully local, no API key ever — you download the voice model
once, then it synthesizes with no network call at all.

```bash
pip install piper-tts   # already in requirements.txt
mkdir -p voices
curl -L https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-en-us-libritts-high.tar.gz \
  | tar -xz -C voices en-us-libritts-high.onnx en-us-libritts-high.onnx.json
```

That's an older release tag (v0.0.2) -- Piper's newer, even-higher-quality
voices have moved to Hugging Face's `rhasspy/piper-voices` repo, worth
checking if you want to try one of those instead; this one was picked
because it's a single self-contained download with no separate host to sign
up with.

Then set `TTS_ENGINE=piper` in `.env`. LibriTTS is a 904-speaker model —
`PIPER_SPEAKER_ID=90` is a decent-sounding default picked by ear, but nothing
stops you from trying others (0–903) for a voice that fits the channel
better. Like `offline`, Piper doesn't report word-level timing, so captions
fall back to a character-length-weighted estimate instead of `edge`'s exact
per-word sync — close, but not measured.

Confirmed by direct listening comparison: `PIPER_SENTENCE_SILENCE` (a pause
between sentences within one scene) mattered more to how natural it sounded
than which of the 904 speakers was picked — the default speaker with no
pause read a multi-sentence scene as one rushed run-on line.

Piper's own defaults (`noise_scale=0.667`, `noise_w=0.8`) also read as
noticeably monotone. `PIPER_NOISE_SCALE=1.0` and `PIPER_NOISE_W=1.1` came
out of a 5-way listening comparison (baseline, each raised individually,
both together, and a different speaker entirely) as sounding the least flat
— more so than switching speakers did.

### Write dates as DD/MM/YYYY, not prose

Also confirmed by listening test: Piper (via its espeak-ng phonemizer)
badly mangles a written-out date like "November 24th, 1971" — the
ordinal-suffix-plus-year combination trips it up in a way a bare year on
its own doesn't. Rather than relying on every script remembering to spell
dates out by hand (easy to forget — it shipped once already, see
`stories/001` and `002`'s git history), write a specific date as
`24/11/1971` in the script text and `pipeline/text_normalize.py` converts
it to natural spoken words automatically, for every engine, before both
synthesis and caption timing. A bare year on its own ("in 1971") doesn't
need this — it's the day+month+year combination that breaks.

## Writing a new script

Drop a new JSON file in `content/scripts/<category>/`, where `<category>` is
`science`, `tech`, `finance`, `wellbeing`, or a new one you're testing:

```json
{
  "category": "tech",
  "id": "003-my-topic",
  "title": "Video title",
  "description": "YouTube description, hashtags included.",
  "tags": ["tech facts", "shorts"],
  "scenes": [
    { "text": "One or two sentences of narration.", "visual_query": "search terms for a matching stock photo" }
  ]
}
```

Each scene becomes its own TTS clip + one Ken Burns still. Keep scene text to
a sentence or two — that's what keeps the visual change matched to the
narration beat. `category` isn't just organizational: it lands in
`metadata.txt` as the playlist to file the upload under.

`finance` and `wellbeing` scripts carry real compliance weight the other two
don't: keep them factual/historical/educational (what happened, what the
research says) rather than prescriptive ("do X with your money", "you should
sleep Y hours"), and put an "Educational content, not financial/medical
advice" line in the description, same as scripts 001 in each of those
folders. That's a content-liability line, not boilerplate — skipping it on
these two categories is the one shortcut worth not taking.

### Two ways to source a script

**Evergreen facts** — a standalone fact that doesn't depend on anything
currently happening. Ask Claude for a batch in a given category and it'll
write from general knowledge, following the schema above.

**Commentary on something real** (`science/006` on) — research an actual
current claim, story, or hoax circulating right now, and write a script that
reports on and explains it, sources cited in the `description`. This is the
"clip other creators' content" idea in its legally sound form: you're not
re-uploading anyone's video, you're doing commentary/analysis on a claim —
the same fair-use footing as news coverage. `science/006` (the "Earth loses
gravity for 7 seconds" hoax) is a worked example: real viral claim, NASA's
actual debunk, sources in the description. Ask Claude to find a current
story in any of the categories and draft one of these when you want the
channel reacting to what's actually happening rather than running on an
evergreen backlog alone.

What this repo deliberately does **not** build: downloading and embedding
clips of someone else's video (reaction/picture-in-picture style). That's a
heavier pipeline with its own YouTube ToS exposure on top of the copyright
question, and straight re-uploads with no added commentary are the weakest
legal position of the three options — treat it as a separate decision, not
a natural next step from this pipeline.

## The `stories` category: narrative Shorts with real video clips

`stories` is a different content shape from the fact-list categories above:
a beginning-middle-twist narrative instead of a run of standalone facts,
mixing real researched events (`001`, `002` — D.B. Cooper, the Boston
Molasses Flood, both sourced and cited the same way as `science/006`) with
original short fiction (`003`, `004`).

It also runs on real stock **video** clips instead of Ken Burns stills — set
`"visual_mode": "video"` in the script JSON (default is `"photo"`, so nothing
about the existing categories changes). `pipeline/video_clips.py` calls
Pexels' Videos endpoint (a separate search from the Photos one `visuals.py`
uses, same free API key), picks whichever result is at least as long as the
scene's narration so it only ever trims rather than looping mid-line, and
falls back to the same generated placeholder as photo mode when no key is
set or nothing suitable comes back. This is the legally clean version of
"use clips to tell the story": licensed stock footage chosen to match the
mood of each beat, not repurposed footage from other creators — see the
commentary-vs-clipping discussion above for why that line matters.

```json
{
  "category": "stories",
  "visual_mode": "video",
  "id": "005-my-story",
  ...
  "scenes": [
    { "text": "One beat of the story.", "visual_query": "mood-matched search terms, not a literal caption" }
  ]
}
```

## Optional: AI talking-head presenter (experimental, untested)

`pipeline/avatar.py` renders one full script as a single talking-head video
through [D-ID's API](https://www.d-id.com/) instead of the stock-visual Ken
Burns pipeline, for testing whether a synthetic on-screen presenter is worth
pursuing before investing further. Some things worth knowing before you try
it:

- **It's not a repeatable step.** D-ID's free trial is a one-time ~5 minutes
  of video, not a per-video budget like Pexels/edge-tts above. HeyGen, the
  other obvious option, dropped free API access entirely as of Feb 2026 —
  its free tier is web-UI-only, watermarked, and can't be scripted, so it
  doesn't fit this pipeline at all.
- **It's genuinely untested.** This was built and reviewed in a sandbox whose
  network policy blocks both `api.d-id.com` and D-ID's own docs, so unlike
  the rest of this repo, nobody has run it against the real API yet. The
  request shape matches D-ID's long-stable `/talks` endpoint, but confirm
  field names against your own dashboard before spending trial credits on it.
- **The source face matters.** Use a synthetic (AI-generated, not a real
  person) or explicitly-licensed presenter image. A real, identifiable
  person's photo turned into a fake talking channel persona is a
  likeness/consent problem no matter how the photo itself is licensed.
- **Disclose it.** If the result is realistic enough to pass for an actual
  person, YouTube's synthetic media policy requires labeling it as
  AI-generated/altered.

```bash
# D_ID_API_KEY in .env, from your D-ID dashboard
python -m pipeline.avatar content/scripts/science/006-gravity-hoax-debunked.json \
  --face-url https://example.com/your-synthetic-presenter.jpg
```

Spend the one-time trial on your strongest script — there's no re-run budget
if the first attempt doesn't land.

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
