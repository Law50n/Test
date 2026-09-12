# Faceless Channel Pipeline

Turns a script (JSON) into a captioned, vertical Short: text-to-speech
narration, stock or generated visuals with a Ken Burns pan/zoom, burned-in
captions, and a thumbnail. Every stage has a genuinely free path — see the
[blueprint](https://claude.ai/code/artifact/e2569c60-49e2-44b7-928c-6d35963d9351)
this was planned from for the original niche reasoning (since revised, see
below).

## Multiple sectors, three channels

Content runs across several pillars, split across three YouTube channels
launched together rather than one channel splitting into more later:

- **Facts channel**: `science`, `tech`, `finance`, `wellbeing`.
- **Mysteries channel**: `stories` — real, sourced true crime/
  unsolved-mystery Shorts and longform/compilation episodes (Shorts there
  double as a discovery funnel into the longform catalog).
- **Fiction channel**: `fiction` — original made-up stories, Shorts now
  and longform "fictional audiobook" episodes eventually, same
  short/longform mechanics as everywhere else, no sourcing involved.

`stories` and `fiction` are never mixed on the same channel, even though
they're both narrative rather than fact-list content — see `CLAUDE.md`.

`category` decides the channel automatically (`pipeline/run.py::CHANNEL_BY_CATEGORY`)
and `metadata.txt` prints a `Channel:` line so a folder of rendered videos
says where each one goes. `category` is also still a playlist/series label
within its channel, same as before — group each category into its own
YouTube playlist so the structure carries through to the channel itself,
and watch view/retention numbers per category to decide where to double
down. One tradeoff worth knowing: a single-niche channel usually gets
recommended faster early on, because YouTube's algorithm has a narrower
audience intent to match against — running several pillars per channel
trades some of that early velocity for a faster read on which sector
actually resonates.

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

Output lands in `output/<category>/<script-id>/`: `video.mp4`, `thumbnail.jpg`,
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
| `ELEVENLABS_API_KEY` | (empty) | required for `TTS_ENGINE=elevenlabs` |
| `ELEVENLABS_VOICE_ID` | George | any voice ID from your ElevenLabs voice library; only used by `TTS_ENGINE=elevenlabs` |
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
noticeably monotone on a single test line. Raising them (`PIPER_NOISE_SCALE=1.0`,
`PIPER_NOISE_W=1.1`, current values) won that comparison, but on a fuller
multi-scene render it came back sounding rougher, not just more expressive
— a real regression, not just a taste call. Current status: unresolved.
A different single-speaker model (`en-us-ryan-medium`, same release tag
above) read better on the same lines at Piper's own default noise settings,
but hasn't been confirmed on a full script yet. If you're picking this back
up, that's the next thing to test before trusting either the noise
settings or the model choice as final.

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

### Highest-quality voice: ElevenLabs (paid, or a fragile free tier)

Every free engine above caps out somewhere short of a real "good enough to
stop tuning" voice. [ElevenLabs](https://elevenlabs.io) is the highest
quality of the five options here, at the cost of an account, a key, and
internet at render time.

**Confirmed working** against a real paid account -- this sandbox's network
policy blocks `api.elevenlabs.io` so it can't be tested from here directly,
but it's been run end to end on a real machine with a real key.

**The free tier is not just small, it can lock you out entirely.** One real
account hit this on the very first request:

```
"detected_unusual_activity" / "Free Tier access has been disabled ...
Please upgrade to a paid subscription to continue."
```

with nothing unusual actually done -- a fresh signup, one API call. If you
hit this, the free tier isn't available to you and the practical options
are paying (their cheapest plan is roughly $5/month) or using `google`
below instead, which doesn't have this failure mode.

Setup:

1. Sign up free at [elevenlabs.io](https://elevenlabs.io) — no card needed
   to create an account and see your dashboard's actual quota/pricing.
2. Get a key from [Settings → API Keys](https://elevenlabs.io/app/settings/api-keys).
3. Put it in `.env` as `ELEVENLABS_API_KEY`.
4. Optionally browse [the voice library](https://elevenlabs.io/app/voice-library)
   for a voice that fits the channel better than the default (George), and
   set `ELEVENLABS_VOICE_ID` to its ID.
5. Set `TTS_ENGINE=elevenlabs`.

One real advantage beyond voice quality, if you get a working key: this
engine uses ElevenLabs' `with-timestamps` endpoint, which returns real
character-level timing converted to word timing in
`pipeline/tts.py::_chars_to_words`. That should give tighter caption sync
than `edge`, which reports timing per-word rather than per-character.

#### Tuning the delivery

Left at ElevenLabs' own defaults, narration comes out flat -- little pitch
or pace variation between lines. Three knobs in `.env` control this
(all `0.0`-`1.0`):

- `ELEVENLABS_STABILITY` (default `0.5`, ElevenLabs' own baseline) -- lower
  means more natural pitch and pacing variation between takes; higher means
  flatter but more consistent. This is the main lever for "monotone."
- `ELEVENLABS_SIMILARITY_BOOST` (default `0.8`) -- how closely it sticks to
  the reference voice's actual timbre. Rarely needs changing.
- `ELEVENLABS_STYLE` (default `0.15`) -- pushes toward a more exaggerated,
  performative delivery. Higher also means slower generation and less
  consistency between renders of the same line, so treat it as a small
  push rather than cranking it up.

**Confirmed by ear, not just in theory: pushing these too far makes some
lines better and others noticeably worse in the same script**, the same
regression already documented above for Piper's `noise_scale` -- more
expressive settings can sound great in isolation and rougher across a full
render. `STABILITY=0.4` / `STYLE=0.35` was tried first and produced exactly
that; the defaults above are a smaller, safer nudge off ElevenLabs' own
baseline instead. If a voice still reads flat at these defaults, that's
more likely the voice itself than the settings -- try a different one from
the voice library rather than pushing style higher to compensate.

### Free-tier voice that doesn't require gambling on account flags: Google Cloud TTS

Confirmed live (not assumed from stale training knowledge): Google Cloud
Text-to-Speech gives **1 million characters/month free for Neural2 voices,
recurring every month, no expiration**. A six-scene short runs maybe
500-700 characters, so that's easily 1,000+ videos/month at zero cost —
the most generous free tier of any engine in this file.

**Unverified**, same caveat as ElevenLabs and D-ID: `texttospeech.googleapis.com`
is blocked in this sandbox, so this hasn't been run against the real API.
The request shape matches Google's long-documented `text:synthesize`
endpoint.

**A card is still required** to create the API key, even though usage
under the free quota isn't charged -- Google ties API key creation to a
billing account. That's a real barrier if you don't want to hand over card
details anywhere, even for something that won't be charged; it's not "free"
in the no-strings sense Piper is.

Setup:

1. Go to [console.cloud.google.com](https://console.cloud.google.com/) and
   create a project (any name).
2. Enable **billing** on the project (Google requires this to issue an API
   key, even for free-tier usage) — you'll need a card, but nothing is
   charged while you stay under 1M characters/month.
3. Enable the **Cloud Text-to-Speech API** for that project (search for it
   in the console's API library and click Enable).
4. Create an API key: **APIs & Services → Credentials → Create Credentials
   → API Key**.
5. Put it in `.env` as `GOOGLE_TTS_API_KEY`.
6. Set `TTS_ENGINE=google`.

#### Making sure you never get charged

"Nothing is charged under 1M characters/month" is not the same as "it's
impossible to be charged" — if this pipeline ever runs away (a bug, a
batch job left running, a much longer script) and crosses that line,
Google will bill the card on file per character with no warning first.
Two Google Cloud features sound like a fix and aren't, plus one that
actually is (confirmed live, August 2026):

- **Billing budgets** (Billing → Budgets & alerts) only send you an email
  when spending crosses a threshold. They do **not** stop usage or block
  further charges by default — by the time the email arrives you may
  already have kept spending.
- Google's newer **spend cap budgets** (a real hard stop that pauses
  usage) exist, but as of now only cover Gemini API, Vertex AI, Cloud Run,
  and Maps — **Text-to-Speech is not on that list**, so it can't be used
  here.
- **Quotas** are the actual fix. Cloud Text-to-Speech has an adjustable
  characters-per-day quota. Go to **APIs & Services → Text-to-Speech API
  → Quotas** (or **IAM & Admin → Quotas**, filtered to the Text-to-Speech
  API), find the characters-per-day metric, and edit it down to something
  like **30,000/day** (≈900k/month — comfortably under the 1M free tier
  with room to spare). Lowering a quota is self-serve and takes effect
  immediately, unlike raising one. Once that daily quota is hit, further
  requests are simply rejected with a quota-exceeded error — nothing gets
  billed for a rejected request.

Do both: the quota is the real guardrail, and a low-threshold billing
budget (e.g. $1) is a free early-warning email in case the quota is ever
misconfigured.

Optionally, browse [available voices](https://cloud.google.com/text-to-speech/docs/voices)
and change `GOOGLE_TTS_VOICE_NAME` (default `en-US-Neural2-D`) to one that
fits the channel better.

Like ElevenLabs, this gets real per-word timing rather than an estimate —
Google's plain synthesis endpoint doesn't report timing on its own, so
`pipeline/tts.py::_synthesize_google` wraps the input in SSML with a
`<mark>` tag before every word and requests `SSML_MARK` time-pointing.
Each word's end time is simply the next word's start; the last word's end
comes from probing the actual rendered audio's duration, since there's no
mark after it to report one.

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
built entirely from real, researched events (`001`, `002` — D.B. Cooper,
the Boston Molasses Flood). It's structurally real-only now: every
`stories` script needs a non-empty `"sources"` list (see below) — one
with none fails to load rather than quietly shipping unsourced.
`run.py` folds `sources` into `metadata.txt`'s `Sources:` line
automatically; don't type it into `description` by hand anymore.

Original short fiction lives in its own `fiction` category and channel
instead (`content/scripts/fiction/`, e.g. `001`, `002`) — same schema and
`format` mechanics (short/longform), no sourcing requirement, and no
research/skeptic-check workflow, since it isn't making any factual
claims. `stories` and `fiction` are never mixed on the same channel — see
`CLAUDE.md`.

For the fuller research → write → skeptic-check process real `stories`
cases should go through before they're scripted at all (especially
longform unsolved-mystery episodes), see `docs/episode-workflow.md`.

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

## Experimental: longform / audiobook-style format (`"format": "longform"`)

A second script format, alongside the default `"short"`. Instead of one
Ken Burns/video/generated clip per scene, `build_longform()`
(`pipeline/run.py`) does:

- Synthesizes and loudness-normalizes every scene's narration exactly like
  `"short"` does, but concatenates all of it into **one continuous audio
  track** (`assemble.concat_audio`) with a clean cut between scenes --
  deliberately no crossfade, since blending one line's ending into the
  next scene's opening would blur words together.
- Holds a small set of **background_images** for the whole episode
  instead of cutting to a new visual every scene, each with a slow
  continuous Ken Burns pan (`assemble.make_hero_clip` -- the zoom rate is
  computed per-image so it paces smoothly across the *entire* hold instead
  of hitting its cap in ~9 seconds and sitting static, which is what
  `make_scene_clip`'s Shorts-tuned rate would do over a multi-minute
  hold), crossfading between images every few minutes
  (`assemble.LONGFORM_CROSSFADE_DURATION`, 2.5s -- much slower than the
  Shorts crossfade) rather than every scene.
- Makes the **captions themselves the primary visual interest** -- bigger
  and more vertically centered than the Shorts bottom-third treatment,
  since a mostly-static screen needs something more engaging on it than a
  small subtitle strip. This is why per-scene visual variety matters less
  here than it does for Shorts: the word-by-word highlight is doing the
  attention-holding work, not the background.

```json
{
  "format": "longform",
  "background_images": ["assets/hero1.png", "assets/hero2.png"],
  "scenes": [
    { "text": "...", "visual_query": "" }
  ]
}
```

`visual_query` is still required by the schema but unused in this format
-- `background_images` (resolved relative to the script file, same as
`local_image`) drives the visuals instead, so a real usable script still
needs actual artwork there, not a placeholder.

To source that artwork from real Pexels photos (rather than hand-picking
and downloading them one at a time), use `pipeline/fetch_backgrounds.py`:

```
python -m pipeline.fetch_backgrounds content/scripts/stories/assets ^
    dyatlov-mountain "snowy mountain slope dusk winter" ^
    dyatlov-forest "dark pine forest snow night"
```

(`^` is cmd.exe's line-continuation character; drop it and put it all on
one line if that's easier.) It reuses the same `visuals.fetch_visual()`
lookup the Shorts pipeline uses per scene, needs a real `PEXELS_API_KEY`
in `.env`, and has no placeholder fallback -- a script meant to source
real artwork failing loudly beats it silently writing a gradient into an
assets folder. Point `background_images` at whatever names you chose.

Verified end-to-end with `experiments/longform-pilot/sodder-children-longform.json`:
rendered a real 14-scene, ~115s narration with two background images,
confirmed final duration matches the narration exactly, the crossfade
between the two images actually happens partway through (extracted and
compared frames before/after), and the usual pixel-format/decode checks
pass.

## Experimental: multi-episode compilations (`"format": "compilation"`)

A third script format for stitching several existing `"longform"` episode
scripts into one continuous sitting -- built once a single well-researched
real case turned out to run well short of a real 15-25+ minute target
(the case's own documented material runs out; padding it with speculation
isn't an option -- see the accuracy rules in the longform research prompt).
Combining several complete episodes back to back, with a short spoken
transition between them, is the real path to that longer runtime, and
matches what this kind of content is for anyway: something to put on and
listen to for a while, like a true-crime podcast, not one two-minute clip.

`run.py::build_compilation()`:

- Loads each script named in `episodes` (each must itself be
  `"format": "longform"`) and runs the same per-episode narration/
  background-building logic `build_longform()` uses (shared via
  `_build_longform_segment()`), one after another.
- Between episodes (not before the first), synthesizes a short spoken
  transition line -- `"Case 2. <episode title>."` -- with its own hero
  clip (using that episode's first background image), so one case doesn't
  bleed straight into the next with nothing marking the change.
- Concatenates all narration (clean cuts, no crossfade -- same reasoning
  as `"longform"`) and all backgrounds (crossfaded,
  `LONGFORM_CROSSFADE_DURATION`) into one continuous track, then finishes
  exactly like a standalone `"longform"` video (mux, captions, thumbnail).

```json
{
  "category": "stories",
  "id": "comp-001-two-unsolved-mysteries",
  "title": "2 Unsolved Mysteries",
  "format": "compilation",
  "episodes": ["sodder-children-longform.json", "isdal-woman.json"],
  "description": "...",
  "tags": ["true story", "unsolved mystery", "compilation", "longform"],
  "scenes": []
}
```

Notes on the schema:
- `episodes` paths are resolved relative to the compilation script's own
  file, same as `background_images`/`local_image` elsewhere.
- A compilation script needs no `scenes` of its own (`scenes: []` is
  fine/expected) -- all the actual narration comes from its episodes.
- Each episode keeps using its own `background_images` for its own
  segment; there's no separate visual asset to prepare for the
  compilation itself.

Verified end-to-end with `experiments/longform-pilot/two-unsolved-mysteries.json`,
combining the already-verified Sodder children (115.1s) and Isdal Woman
(466.7s) episodes: final duration (584.6s) matches narration + transition
exactly, pixel-format/profile/framerate and full decode checks pass, and
frame-by-frame inspection at the episode seam confirms the spoken "Case 2.
The Woman With Eight Names." transition displays with its own background,
then correctly crossfades into the second episode's (visually distinct)
background as its narration begins.

One caveat worth flagging: `make_hero_clip`'s `zoompan` step is genuinely
slow at multi-minute hold durations (real wall-clock minutes per hero
clip, not a hang), and a compilation multiplies that by however many
episodes and their own background images it's built from -- a long
compilation will take a while to render, budget for it.

## Experimental: AI-generated visuals (`experiments/longform-pilot/`)

A third `visual_mode`, `"generated"`, sources each scene's image from Gemini
(`pipeline/image_gen.py`) instead of Pexels or a placeholder -- built as a
pilot for a longform unsolved-mysteries format, where a consistent
illustrated look across a whole series matters more than it does for a
6-scene Short. Not used by any of the main `content/scripts/` categories;
opt in per script.

**Model choice matters here and will keep changing.** Imagen 4's dedicated
endpoints (standard/ultra/fast) were deprecated and shut down 17/08/2026 --
confirmed live, they simply don't work anymore. `GEMINI_IMAGE_MODEL`
defaults to `gemini-3.1-flash-image` (the current "Nano Banana 2"
generation), but check [Google's current model list](https://ai.google.dev/gemini-api/docs/imagen)
before relying on this being current by the time you read it -- this space
moves fast.

**Real, per-image cost** (roughly a few cents each at the time this was
written, resolution-dependent) -- unlike Pexels/placeholders, this isn't
free. Check current pricing before rendering a long script.

**Unverified end-to-end.** This sandbox has no Gemini API key, so this has
only been tested against a mocked response and via the pipeline's fallback
path (see `experiments/longform-pilot/sodder-children.json` — it renders
clean with every scene falling back to a placeholder and printing exactly
why: `GEMINI_API_KEY is not set`). The request/response shape matches
Google's current documented format, but confirm it against a real key
before trusting it.

Setup:

1. Get a key at [aistudio.google.com/apikey](https://aistudio.google.com/apikey).
2. Put it in `.env` as `GEMINI_API_KEY`.
3. Set `"visual_mode": "generated"` in a script, and optionally
   `"image_style_prompt"` -- a shared style descriptor appended to every
   scene's generation prompt so a whole series reads as one consistent,
   recognizable look instead of each scene being independently generated
   with no throughline. See `sodder-children.json` for a real example
   (illustrated, muted, cinematic -- deliberately not photorealistic,
   since several scenes describe real people).

One thing this pipeline does **not** do yet: automatically flag YouTube's
"Altered Content" disclosure at upload. There's no automated upload step at
all currently (uploads are manual, see above) -- so for now, if you publish
something made with generated visuals depicting a real person/place/event,
that disclosure toggle needs to be set by hand in YouTube Studio.

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
- Actually uploading: `output/<category>/<id>/metadata.txt` has the title,
  description, and tags ready to paste into YouTube Studio.
