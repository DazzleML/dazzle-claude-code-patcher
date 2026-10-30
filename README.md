# dazzle-claude-code-patcher

[![PyPI](https://img.shields.io/pypi/v/dazzle-claude-code-patcher?color=green)](https://pypi.org/project/dazzle-claude-code-patcher/)
[![Release Date](https://img.shields.io/github/release-date/DazzleML/dazzle-claude-code-patcher?color=green)](https://github.com/DazzleML/dazzle-claude-code-patcher/releases)
[![PyPI Downloads](https://static.pepy.tech/personalized-badge/dazzle-claude-code-patcher?period=total&units=international_system&left_color=black&right_color=green&left_text=downloads)](https://pypistats.org/packages/dazzle-claude-code-patcher)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://github.com/DazzleML/dazzle-claude-code-patcher/blob/main/LICENSE)
[![GitHub Discussions](https://img.shields.io/github/discussions/DazzleML/dazzle-claude-code-patcher)](https://github.com/DazzleML/dazzle-claude-code-patcher/discussions)
[![Installs](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/djdarcy/f7a6548744c4bfa11989d00d78fe59ed/raw/installs.json)](https://dazzleml.github.io/dazzle-claude-code-patcher/stats/#installs)
[![Platform](https://img.shields.io/badge/platform-Windows%20(first)-lightgrey.svg)](https://github.com/DazzleML/dazzle-claude-code-patcher/blob/main/docs/platform-support.md)

> **Fix problematic Claude Code bugs in your local copy now, and keep the fixes working across updates.**

`dcc-patcher` diagnoses, verifies, and applies patches to the native Claude Code CLI (`claude.exe`). When Claude Code updates (roughly every two days), one command tells you which patches re-apply as-is and which need attention, and shows exactly what changed. Once set up, `claude` runs the patched build and re-patches each update by itself.

> [!NOTE]
> **Pre-alpha, Windows only.** Five patches apply unchanged on every Claude Code build from 2.1.278 to 2.1.314. The history patch is in daily use: a resumed session scrolls back past every compaction, and the model still receives exactly the same request as stock Claude Code. See the [Roadmap](https://github.com/DazzleML/dazzle-claude-code-patcher/issues/1).

## The Problem

Some Claude Code bugs sit in code you can't configure around. For example, after a restart or `claude --resume`, everything before the last compaction disappears from the screen. It's still in the session file, but nothing brings it back. Waiting for an upstream improvement or fix can take a while, and patching by hand doesn't survive the next update (Claude Code is minified, so almost every internal name changes from one release to the next).

## Patches

| Patch | Fixes | Status |
|---|---|---|
| [History past compaction](https://github.com/DazzleML/dazzle-claude-code-patcher/blob/main/dcc_patcher/patches/H-history-past-compaction/README.md) | After a restart or `--resume`, scroll back past compactions to the start of the session file | `check` passes on 2.1.278 to 2.1.314; live-tested on 2.1.289 to 2.1.296 |
| [History across session files](https://github.com/DazzleML/dazzle-claude-code-patcher/blob/main/dcc_patcher/patches/J-history-across-files/README.md) | A conversation that continued into a new session file (after running out of context, or a fork) scrolls back into the file it came from, and on to its first message. Needs the history patch. Derived from ojura/claude-patches' Patch J | `check` passes on 2.1.278 to 2.1.314; not yet live-tested |
| [Version label](https://github.com/DazzleML/dazzle-claude-code-patcher/blob/main/dcc_patcher/patches/V-version-label/patch.toml) | `--version` says it is a patched build and which patcher made it: `2.1.295 + dcc 0.1.11 (Dazzle Claude Code)`. Only the displayed text changes; the version Claude Code checks against is untouched | `check` passes on 2.1.278 to 2.1.314 |
| Banner label ([classic](https://github.com/DazzleML/dazzle-claude-code-patcher/blob/main/dcc_patcher/patches/B-banner-label/patch.toml), [flicker-free](https://github.com/DazzleML/dazzle-claude-code-patcher/blob/main/dcc_patcher/patches/B2-banner-label-flicker-free/patch.toml)) | The header at the top of every session reads `Dazzle Claude Code v2.1.295 · dcc 0.1.11`, in both rendering modes. Only the drawn text changes | `check` passes on 2.1.278 to 2.1.314; flicker-free live-tested on 2.1.291 to 2.1.295 |
| [Compaction rows in the normal view](https://github.com/DazzleML/dazzle-claude-code-patcher/blob/main/dcc_patcher/patches/R-compaction-rows/README.md) | The normal screen shows a `Compact summary (ctrl+o to expand)` line at each compaction, as the transcript does, so both views start at the same first row after a resume. Display only | `check` passes on 2.1.278 to 2.1.314; not yet live-tested |

> [!CAUTION]
> **This project ships the tool and patch definitions only *NEVER* patched binaries.** You patch your own copy of Claude Code, locally. Use at your own risk. No warranty. Backup anything important first. I'd recommend: [claude-session-backup](https://github.com/DazzleML/Claude-Session-Backup).

## Installation

Python 3.11 or newer. The one dependency, [dazzle-lib](https://pypi.org/project/dazzle-lib/), is itself standard-library only.

```bash
pip install dazzle-claude-code-patcher
dcc-patcher -h                   # the commands, grouped by what they act on
dcc-patcher validate             # lists the bundled patches
dcc-patcher update               # is this install current? (--fix updates it, after asking)
```

To work on it, install from source instead (`pip install -e ".[dev]"` in a clone). Builds then go to the checkout's `private\builds\` rather than `%LOCALAPPDATA%\dazzle-claude-code-patcher\builds\`.

## Usage

```bash
# Does every patch still apply to this build? (read-only)
dcc-patcher check %USERPROFILE%\.local\bin\claude.exe

# Build a patched copy into the builds folder, with a lockfile recording every edit
dcc-patcher apply %USERPROFILE%\.local\bin\claude.exe
#   wrote <builds>\claude-dcc-2.1.295+dcc0.1.11.exe
#     and <builds>\claude-dcc-2.1.295+dcc0.1.11.exe.dcc-lock.json
#   <builds>\claude-dcc.exe -> claude-dcc-2.1.295+dcc0.1.11.exe (hardlink)

# Run the patched copy instead of claude
<builds>\claude-dcc.exe --resume
```

The official `claude.exe` is never modified. Older builds stay in the builds folder for rollback, and the original Claude Code each build was made from is kept beside it. After an update, `check` again; if an edit fails, nothing is written and `check --baseline` shows what changed. Where everything goes, and every option: [docs/launcher.md](https://github.com/DazzleML/dazzle-claude-code-patcher/blob/main/docs/launcher.md).

### Make the patched build just `claude`

```bash
dcc-env                         # cmd or PowerShell; in Git Bash: . dcc-env
dcc-patcher status              # which claude this shell runs, and anything left to do
```

`dcc-env` exists because no program can change the `PATH` of the shell that started it: it's a small script that runs inside your shell, so it works in one that was already open. The first time, it writes the `claude`, `dazzle-claude` and `claude-stock` shims and adds their folder to your user `PATH` (after asking, and after saving the old value as a `.reg` file). Every time, it puts that folder on the `PATH` of the shell you typed it in. Shells opened afterwards don't need it.

From then on, `claude` runs the current patched build. When Claude Code updates, the next start says so, rebuilds in a few seconds, and runs the new build; if a patch no longer applies, it runs stock instead and says which patch needs attention.

**Switching.** `dazzle-claude` and `claude-stock` always run the patched and the official build, whatever `claude` means. To change what `claude` itself means:

```bash
dcc-env stock                   # in this shell only (also: patched, a build's file name, or default to undo)
dcc-env --help                  # the choices, without changing anything
dcc-patcher use stock           # everywhere, from the next start (also: patched, a build's file name)
dcc-patcher status              # says which one wins in this shell, and why
```

`dcc-patcher uninstall-shim` puts everything back. The details, including how to check or undo any of it by hand: [docs/launcher.md](https://github.com/DazzleML/dazzle-claude-code-patcher/blob/main/docs/launcher.md).

## How it works

- **Patches are written by structure, not by exact text.** Each patch names a stable landmark (a string that survives builds), the shape of the code to change near it, and a replacement. Minified names are wildcards, captured once and reused by later edits. Measured on the 7 Claude Code builds from 2.1.278 to 2.1.289 (2026-09-19 to 10-03): the same edits written as exact text applied in full on only one build, while the structural patch applies unchanged on all seven.
- **It fails closed.** Every edit must match exactly the number of times it expects, or nothing is written. The output is a new file beside the official `claude.exe`, never an in-place change, and everything except the patched module is verified byte-identical.
- **It knows when to stop.** A patched module carries a signature, so a patch is never applied twice; and a patch can say how to recognise that Anthropic fixed the bug, so it reports *fixed upstream* instead of *broken*.
- **It diagnoses.** When an edit no longer matches, `check` shows a diff of that code region against the last build where the patch worked, with minified names normalised so that only real code changes show.

## Development

```bash
python -P -m pytest tests/ -v   # tests that need a local claude.exe are skipped without one
bash scripts/repokit-common/install-hooks.sh   # version sync and pre-push checks
```

## Related Projects

- [ojura/claude-patches](https://github.com/ojura/claude-patches): patches for the Claude Code VS Code extension, and the inspiration for this project's approach (structural matching, failing closed, byte-stable verification). This project is its Windows-first, native-CLI counterpart.
- [claude-session-logger](https://github.com/DazzleML/claude-session-logger), [Claude-Session-Backup](https://github.com/DazzleML/Claude-Session-Backup), [claude-bookmarks](https://github.com/DazzleML/claude-bookmarks): other DazzleML Claude Code tools.

## Disclaimer

Not affiliated with or endorsed by Anthropic. Patching modifies your local copy of Claude Code and removes its code signature; use it at your own risk, and keep the official `claude.exe` in place.

## License

dazzle-claude-code-patcher, copyright (C) 2026 Dustin Darcy.

This project is licensed under the MIT License - see the [LICENSE](https://github.com/DazzleML/dazzle-claude-code-patcher/blob/main/LICENSE) file for details.
