# Project context

**The user (Will) only ever runs this on Windows, in `cmd.exe`.** This has
caused repeat, avoidable bugs and bad advice when code or commands were
written assuming a Unix shell. Default to Windows for everything:

- **Never suggest bash/zsh-only command syntax.** No `VAR=value command`
  inline env vars (use `set VAR=value` then a separate line, for `cmd.exe`).
  No relying on shell glob expansion (`*.json`) -- `cmd.exe` does not expand
  wildcards; `pipeline/run.py` handles this itself via `_expand_globs()` for
  this exact reason, so pipeline commands are safe, but ad-hoc shell
  commands suggested to the user are not.
- **Never hardcode Linux-only file paths** (`/usr/share/fonts/...`, `/tmp/...`)
  in code the user will actually run. Assets the pipeline depends on (fonts,
  etc.) should be bundled in the repo (see `assets/fonts/`) rather than
  assumed to exist on the OS, for exactly this reason -- it silently broke
  before (`pipeline/fonts.py` fell back to a generic font on every real
  Windows render until this was caught).
- When giving the user a command to type, write it for `cmd.exe`
  specifically (not PowerShell, not bash), since that's confirmed to be
  what they use.
- This project's own sandbox (used for development/testing here) is Linux,
  so code changes get regression-tested here before the user tries them --
  but that's this environment's limitation, not a reason to write
  Linux-flavored instructions or paths into anything the user runs.

# Pipeline overview

See README.md for full setup/usage docs. Quick orientation: `pipeline/run.py`
is the entry point (`python -m pipeline.run <script.json>`), `pipeline/tts.py`
has all 5 TTS engine integrations, `pipeline/config.py` loads `.env`.
Content scripts live in `content/scripts/<category>/*.json`.

# Three YouTube channels, launched together

Will runs three separate channels, all live from early on rather than
one channel splitting into more later:

- **Facts channel**: science/tech/finance/wellbeing Shorts -- short,
  scrolling, "did you know" content.
- **Mysteries channel** (`category: "stories"`): real, sourced true
  crime/unsolved-mystery content only -- Shorts *and* the longform/
  compilation episodes. Shorts there double as a discovery funnel into
  the longform catalog on the same channel. Goes through the full
  research -> writing -> skeptic-check workflow below; every script here
  needs real, non-empty `sources`.
- **Fiction channel** (`category: "fiction"`, `content/scripts/fiction/`):
  original made-up stories only -- Shorts and, eventually, longform
  "fictional audiobook" episodes, same `format` mechanics as everything
  else. No sourcing, no research/skeptic-check workflow -- it's just
  good writing. Never mixed with `"stories"` -- a script is either a real,
  sourced case in `stories`, or made up in `fiction`, never both and
  never ambiguous between them.

`category` alone decides the channel (`pipeline/run.py::CHANNEL_BY_CATEGORY`)
and metadata.txt prints a `Channel:` line accordingly -- don't invent a
separate "channel" field in the schema, and don't split a category's
content across two channels. Non-YouTube platforms are a deliberately
later decision -- don't build or plan for them until asked.

**`category` records the fiction/non-fiction decision, it doesn't make
it.** Whether something is fiction is decided by which process created
it -- real research + a sourced brief + a skeptic-check means `stories`;
sitting down and inventing a plot with no research means `fiction`.
Nothing in the schema can catch a script deliberately mislabeled to dodge
sourcing -- that's a process/honesty question, not a code one: always say
which one is being written, and category should follow that decision, not
decide it. What *is* structurally guaranteed: every `category: "fiction"`
script gets an automatic disclosure line in metadata.txt
(`run.py::_FICTION_DISCLOSURE`, "This is a work of fiction. It is not a
true story.") -- viewer-facing labeling doesn't depend on remembering to
type it into `description` by hand, same reasoning as the `sources` line.

**On batching work across all three channels**: rendering already batches
today -- `pipeline/run.py` takes multiple scripts or a whole folder glob
in one invocation, so "build every video across all three channels" is
already just one command, nothing new needed. Research and the skeptic-
check are not that kind of deterministic, scriptable step -- they're
judgment work (real web research, then reading a script against its
brief) done per episode, not a `pipeline.verify`-style command. Several
episodes' research/writing/skeptic-check can happen in one sitting when
asked, but don't front-load *all* research across every channel before
any writing happens -- a brief's gaps often only surface once a script is
actually drafted and skeptic-checked against it (see the Dyatlov Pass
episode's second research pass), so collapsing research into one
big up-front batch risks missing exactly what this workflow exists to
catch.

# Long-form/`stories` episode content rules

These apply automatically to every unsolved-mystery/true-story episode --
don't wait to be reminded of them per episode:

- **Every factual claim must be real and checkable.** Never invent
  statistics, quotes, studies, or dialogue that weren't actually reported
  somewhere real.
- **Disputed theories are presented as theories, attributed to who
  proposed them** ("investigators believed...", "a theory pushed by
  journalist X holds that...") -- never asserted as settled fact, even
  the one that seems most convincing.
- **True and fictional episodes are kept strictly separate and
  structurally labeled.** Real cases are `category: "stories"` with a
  real, non-empty `"sources"` list; original fiction is `category:
  "fiction"` instead, its own folder and channel (see
  `pipeline/script_loader.py`) -- there's no in-between, and the loader
  rejects a `"stories"` script with no sources.
- **Never name a living private individual as a perpetrator** unless
  they were actually charged/convicted and it's part of the public
  record. This is a legal boundary, not a courtesy one.

Follow the research -> writing -> skeptic-check process in
`docs/episode-workflow.md` for every real-case episode, especially
longform ones -- it's what actually keeps the above rules from drifting
as an episode gets drafted.
