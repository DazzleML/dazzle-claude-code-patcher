# dazzle-claude-code-patcher

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20(first)-lightgrey.svg)](docs/platform-support.md)

> **Fix problematic Claude Code bugs in your local copy now, and keep the fixes working across updates.**

`dcc-patcher` applies, verifies and diagnoses patches to the native Claude Code CLI (`claude.exe`). When Claude Code updates (roughly every two days), one command tells you which patches re-apply as-is and which need attention, and shows exactly what changed.

> [!NOTE]
> **Pre-alpha, Windows only.** The proof of concept works on Claude Code 2.1.289: the first patch lets a resumed session scroll back past its compactions, and the model still receives exactly the same request as stock Claude Code. The tool now checks, applies and diagnoses that patch; a live run of the tool's own build is the next step before v0.2.0. See the [Roadmap](https://github.com/DazzleML/dazzle-claude-code-patcher/issues/1).

## The Problem

Some Claude Code bugs sit in code you can't configure around. For example, after a restart or `claude --resume`, everything before the last compaction disappears from the screen. It's still in the session file, but nothing brings it back. Waiting for an upstream improvement or fix can take a while, and patching by hand doesn't survive the next update (Claude Code is minified, so almost every internal name changes from one release to the next).


## Patches

| Patch | Fixes | Status |
|---|---|---|
| [History past compaction](patches/H-history-past-compaction/README.md) | After a restart or `--resume`, scroll back past compactions to the start of the session file | `check` passes on 2.1.278 to 2.1.292; live-tested on 2.1.289 to 2.1.291 |
| [Version label](patches/V-version-label/patch.toml) | `--version` says it is a patched build and which patcher made it: `2.1.291 + dcc 0.1.3 (Dazzle Claude Code)`. Only the displayed text changes; the version Claude Code checks against is untouched | `check` passes on 2.1.278 to 2.1.292 |
| Banner label ([classic](patches/B-banner-label/patch.toml), [flicker-free](patches/B2-banner-label-flicker-free/patch.toml)) | The header at the top of every session reads `Dazzle Claude Code v2.1.291 · dcc 0.1.3`, in both rendering modes. Only the drawn text changes | `check` passes on 2.1.278 to 2.1.292; flicker-free live-tested on 2.1.291 |

> [!CAUTION]
> **This project ships the tool and patch definitions only *NEVER* patched binaries.** You patch your own copy of Claude Code, locally.  
>
> Use at your own risk. No warranty. Backup anything important first. For myself I use: [claude-session-backup](https://github.com/DazzleML/Claude-Session-Backup). 

## Installation

Not yet published. From source, with Python 3.11 or newer:

```bash
git clone https://github.com/DazzleML/dazzle-claude-code-patcher.git
cd dazzle-claude-code-patcher
pip install -e ".[dev]"
dcc-patcher --version
```

## Usage

```bash
# Does every patch still apply to this build? (read-only)
dcc-patcher check %USERPROFILE%\.local\bin\claude.exe

# Build a patched copy into the builds folder, with a lockfile recording every edit
dcc-patcher apply %USERPROFILE%\.local\bin\claude.exe
#   wrote <builds>\claude-dcc-2.1.292+dcc0.1.5.exe
#     and <builds>\claude-dcc-2.1.292+dcc0.1.5.exe.dcc-lock.json
#   <builds>\claude-dcc.exe -> claude-dcc-2.1.292+dcc0.1.5.exe (hardlink)

# Run the patched copy instead of claude
<builds>\claude-dcc.exe --resume
```

**The builds folder** is the same whatever folder you run `apply` from: `private\builds\` in a checkout of this repository, otherwise `%LOCALAPPDATA%\dazzle-claude-code-patcher\builds\` (`~/.local/share/dazzle-claude-code-patcher/builds/` on Linux and macOS); set `DCC_BUILDS_DIR` to choose another. Each build is named after both versions, so older builds stay for rollback, and `claude-dcc.exe` points at the newest. Rebuilding the same versions says `already built`. If `claude-dcc.exe` is running, `apply` keeps the new versioned build, says the current name still points at the old one, and exits 1. `-o <path>` writes exactly that file instead, with no `claude-dcc.exe` link. `apply` prints absolute paths, and refuses to write inside Claude Code's own config folder (`~/.claude`, or `CLAUDE_CONFIG_DIR`).

After Claude Code updates, run `check` again. Every edit `APPLIES`: run `apply` again. An edit fails: nothing is written, and `check --baseline <builds>\claude-dcc.exe.dcc-lock.json` shows what changed at its site. Other commands: `inspect <exe>` (version, modules, where a string lives) and `validate [patch.toml ...]` (is a patch spec well formed). Exit codes: 0 fine, 1 a patch needs a human, 2 a usage error or an unsupported file.

The patched copy has its code signature removed (any edit invalidates it), so antivirus or SmartScreen may question it the first time. The official `claude.exe` and its updater are never touched.

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

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
