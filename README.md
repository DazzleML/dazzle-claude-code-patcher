# dazzle-claude-code-patcher

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Platform](https://img.shields.io/badge/platform-Windows%20(first)-lightgrey.svg)](docs/platform-support.md)

> **Fix the Claude Code bugs that hurt you, in your own copy, now, and keep the fixes working across updates.**

`dcc-patcher` applies, verifies and diagnoses patches to the native Claude Code CLI (`claude.exe`). When Claude Code updates (roughly every two days), one command tells you which patches re-apply as-is and which need attention, and shows exactly what changed.

> [!NOTE]
> **Pre-alpha.** The proof of concept works on Claude Code 2.1.289 (Windows): the first patch lets a resumed session scroll back past its compactions, and the model still receives exactly the same request as stock Claude Code. The tool itself is being built now. See the [Roadmap](https://github.com/DazzleML/dazzle-claude-code-patcher/issues/1).

## The Problem

Some Claude Code bugs sit in code you can't configure around. For example, after a restart or `claude --resume`, everything before the last compaction disappears from the screen. It's still in the session file, but nothing brings it back. Waiting for an upstream fix can take a while, and patching by hand doesn't survive the next update: Claude Code is minified, so almost every internal name changes from one release to the next.

## How it works

- **Patches are written by structure, not by exact text.** Each patch names a stable landmark (a string that survives builds), the shape of the code to change near it, and a replacement. Minified names are wildcards. Measured on the 7 Claude Code builds from 2026-09-19 to 10-03: exact-text edits broke on 6 of 7 builds, while structural ones held for most edits across all of them.
- **It fails closed.** Every edit must match exactly the number of times it expects, or nothing is written. The output is a new file beside the official `claude.exe`, never an in-place change, and everything except the patched module is verified byte-identical.
- **It diagnoses.** When an edit no longer matches, the report shows that code region in the new build next to the last build where the patch worked.

**This project ships the tool and patch definitions only, never patched binaries or Anthropic's code.** You patch your own copy of Claude Code, locally.

## Patches

| Patch | Fixes | Status |
|---|---|---|
| History past compaction | After a restart or `--resume`, scroll back past compactions to the start of the conversation | Proof of concept on 2.1.289 |

## Installation

Not yet published. From source:

```bash
git clone https://github.com/DazzleML/dazzle-claude-code-patcher.git
cd dazzle-claude-code-patcher
pip install -e ".[dev]"
dcc-patcher --version
```

## Development

```bash
python -m pytest tests/ -v
bash scripts/repokit-common/install-hooks.sh   # version sync and pre-push checks
```

## Related Projects

- [ojura/claude-patches](https://github.com/ojura/claude-patches): patches for the Claude Code VS Code extension, and the inspiration for this project's approach (structural matching, failing closed, byte-stable verification). This project is its Windows-first, native-CLI counterpart.
- [claude-session-logger](https://github.com/DazzleML/claude-session-logger), [Claude-Session-Backup](https://github.com/DazzleML/Claude-Session-Backup), [claude-bookmarks](https://github.com/DazzleML/claude-bookmarks): other DazzleML Claude Code tools.

## Disclaimer

Not affiliated with or endorsed by Anthropic. Patching modifies your local copy of Claude Code and removes its code signature; use it at your own risk, and keep the official `claude.exe` in place.

## License

dazzle-claude-code-patcher, copyright (C) 2026 Dustin Darcy. MIT License; see [LICENSE](LICENSE).
