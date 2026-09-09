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
