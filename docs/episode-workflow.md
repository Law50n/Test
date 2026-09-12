# Episode workflow: research, write, skeptic-check

This is the process for every real-case `stories` episode (Shorts or
longform) -- built to keep the house rules in `CLAUDE.md` from quietly
drifting once a script is mid-draft. It doesn't apply to original fiction
(`"is_fiction": true`) or the fact-list categories (science/tech/finance/
wellbeing), which don't carry the same true-crime accuracy stakes.

The core problem it solves: writing a script in one open-ended pass means
research recall and prose drafting happen in the same breath, so a
half-remembered detail or a theory that sounded plausible can slide from
"something I read somewhere" into "asserted fact" without either of us
noticing. Splitting research from writing, and then checking the writing
against the research afterward, catches that before it ships.

## 1. Research pass -> a committed brief

Before writing a word of script, produce a sourced brief and save it as
`<episode-id>.brief.md` next to where the script will live (e.g.
`content/scripts/stories/006-my-case.brief.md`). Committing it, not just
producing it in chat, is the point -- it's the file to point to later if a
claim in the finished video is ever questioned.

The brief has two sections:

- **Established facts**, each with a real citation (outlet, book,
  official record -- specific enough to actually go verify, not "various
  sources"). Note where sources disagree with each other; that's often
  the most interesting part of the case, not a problem to smooth over.
- **Theories**, each attributed to who actually proposed it (an
  investigator, journalist, family member, researcher) -- not invented --
  with what evidence supports it and what contradicts it.

Confirm the case has enough real documented material to sustain the
episode's intended length before committing to it. If it doesn't, say so
and propose a different case rather than padding.

I'll show you the brief once it's done. That's a chance to catch anything
before it turns into a scripted video, not a mandatory approval gate --
unless you flag something, I'll move on to writing.

## 2. Writing pass -> scripted from the brief only

Draft the script from the brief's content only, not from open recall. If
a scene needs a detail the brief doesn't have, that's a sign to go back
and add it to the brief with a real citation -- not to write around the
gap from memory.

Standard rules still apply here: disputed theories get hedged language
("investigators believed...", "X has never been confirmed, but...") and
attribution to whoever proposed them, never stated as settled fact. Never
name a living private individual as a perpetrator unless charged/
convicted and it's public record.

## 3. Skeptic pass -> check the draft against the brief

Before the script is final, go scene-by-scene (scenes are already
1-3-sentence units, so this maps directly) and check that every claim in
each scene traces back to a specific bullet in the brief. Flag anything
that doesn't -- an invented-sounding specific, a theory stated too
plainly, a detail that crept in from general recall rather than the
brief -- and fix it before calling the script done.

This pass is silent when it's clean. It only gets surfaced to you when
something's actually flagged and fixed, so it doesn't turn into a status
report you have to read through on every episode.

## 4. `sources` and `is_fiction` -- structural, not typed by hand

Once the script JSON is written:

- `"sources"`: a flat list of the brief's citations (outlet/book/report
  names, specific enough to verify), e.g.:

  ```json
  "sources": [
    "Wikipedia's Isdal Woman entry",
    "The BBC/NRK podcast 'Death in Ice Valley'"
  ]
  ```

  `pipeline/script_loader.py` requires this to be non-empty for any
  `category: "stories"` script that isn't fiction -- a script that skips
  real sourcing fails to load instead of quietly shipping. `run.py` folds
  it into `metadata.txt`'s `Sources:` line automatically; don't type a
  `Sources:` line into `description` by hand anymore.

- `"is_fiction": true` on original short fiction instead (see
  `content/scripts/stories/003`, `004`) -- makes the true/fiction split a
  field the loader checks, not just a line in the description and a tag.

Per-claim traceability (which specific source backs which specific
sentence) lives in the episode's `.brief.md` from step 1, not in the
JSON -- that's what the skeptic pass in step 3 checks against, and it's
the actual mechanism that keeps sourcing honest, not the flat list in the
script.
