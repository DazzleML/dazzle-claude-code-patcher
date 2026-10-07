# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.6] - 2026-10-07

### Added

- **A launcher, so the patched build is just `claude`.** `dcc-patcher install-shim` writes `claude` and `claude-stock` (plus `.cmd` versions on Windows) into `<builds>\bin`. Put that folder ahead of `~/.local/bin` on `PATH`.
  - `claude` runs the current patched build. When the official `claude.exe` has changed, the next start rebuilds into the builds folder and switches to the new build.
  - If a patch needs attention after an update, or the rebuild fails, `claude` runs stock, with one line on stderr naming the patch.
  - `claude-stock` always runs the official build. It's a generated file, not a shell alias, so it works the same in cmd, PowerShell and POSIX shells.
  - All the logic is in one Python module (`dcc_patcher.launch`). The shims come from two templates, one `.cmd` and one POSIX `sh`.
  - The official exe's hash is cached against its size, modification time and file id, so a start with nothing changed doesn't re-read 250 MB.
- **`dcc-patcher use [stock | patched | <build>]`** chooses what `claude` runs from the next start; with no argument it shows the state. **`dcc-patcher rollback`** pins the build before the current one. `DCC_MODE=stock` or `DCC_MODE=patched` overrides the choice for one shell.
- With `CLAUDE_CONFIG_DIR` set (a test config), the launcher never rebuilds or changes its state.
- **The launcher never writes into `~/.local/bin` or `~/.claude`,** and `install-shim` refuses both. Claude Code's updater writes only to its own fixed path in `~/.local/bin` and never searches `PATH`, so it doesn't touch the shims.

## [0.1.5] - 2026-10-07

### Added

- **Versioned builds in one fixed folder.** `dcc-patcher apply <claude.exe>` with no `-o` names each build after both versions, for example `claude-dcc-2.1.292+dcc0.1.5.exe`, with its lockfile beside it. Older builds stay for rollback.
  - The builds folder is the same whatever folder `apply` is run from: `private\builds\` in a checkout of this repository, otherwise `%LOCALAPPDATA%\dazzle-claude-code-patcher\builds\` (`~/.local/share/...` on Linux and macOS). `DCC_BUILDS_DIR` overrides it.
  - `claude-dcc.exe` in that folder points at the newest build: a hardlink, or a copy where hardlinks aren't available.
  - Rebuilding the same versions reports `already built` and writes nothing. Changed patches at the same versions rebuild.
  - If `claude-dcc.exe` is running, the new build is kept, one line says the current name still points at the old one, and the exit code is 1.

### Changed

- **`apply` prints absolute paths,** so a misplaced build is obvious.
- **`apply` refuses to write inside Claude Code's own config folder** (`~/.claude`, or `CLAUDE_CONFIG_DIR`), with or without `-o`, and exits 2. A relative `-o` run from `~/.claude` once put a 258 MB build there.
- `-o` is now optional; with it, `apply` writes exactly that file, as before, with no `claude-dcc.exe` link.

## [0.1.4] - 2026-10-07

### Added

- **Banner label:** a patched build's session header reads, for example, `Dazzle Claude Code v2.1.291 · dcc 0.1.3` instead of `Claude Code v2.1.291`.
  - Claude Code draws that header in two places, one for each rendering mode, so there are two small patches: `patches/B-banner-label/` for the classic header and `patches/B2-banner-label-flicker-free/` for the flicker-free one.
  - Only the drawn text changes. The version constant, and the name Claude Code gives MCP and language servers, are untouched.
  - Both apply unchanged on every saved build from 2.1.278 through 2.1.292.

## [0.1.3] - 2026-10-05

### Added

- **Patch spec format 1** (`dcc_patcher.spec`). A patch is a TOML file, not code.
  - Each edit is a regular expression that names the minified identifiers it captures, so the same patch keeps matching when a release renames them.
  - A name captured by one edit can be reused by later edits as `@@name@@`.
  - An edit can be scoped to a window around a stable landmark string, and states how many matches it expects.
  - Common authoring mistakes are refused with the field named: non-ASCII text, an unknown `@@name@@`, an invalid pattern, a zero match count.
- **Signatures and upstream-fixed detectors.** A patch can carry a signature comment, so a patched module is recognised and never patched twice. It can also carry an upstream-fixed detector, so a patch the bug fix made unnecessary is reported as fixed instead of broken.
- **Patches across several modules.** A patch can span several modules (`modules = n`), and `@@dcc_version@@` in a patch is filled with this tool's version. A patched module is recognised by its signature even when an edit removed the text used to find it, so re-applying is still a no-op.
- **`dcc-patcher validate [spec ...]`** checks patch specs (by default, every bundled patch). A malformed spec exits 2 with the field named.
- **`dcc-patcher check <exe>... [--baseline LOCK] [--lock-out DIR]`** is read-only and says, per build, whether each patch and edit applies. Wildcards such as `claude.exe*` are expanded by the tool, so they work from cmd.exe.
  - With a baseline lockfile from a build where the patches applied, each failing edit shows a diff of its site. Minified names are normalised, so a rename doesn't show as a change and a real code change does.
  - Exit codes: 0 when every patch is fine, 1 when one needs a human, 2 when a file can't be read.
- **`dcc-patcher apply <exe> -o <out> [--patch ...] [--debug]`** writes a patched copy, with a `.dcc-lock.json` record beside it holding each edit's site and the text it replaced.
  - It reports every edit as `APPLIES`, `AMBIGUOUS`, `MISSING` or `LANDMARK-GONE`. When any edit doesn't apply, it writes nothing and exits 1.
  - It never writes over its input. Run on its own output, it reports `already-applied` and writes nothing.
- **A missing or unreadable input file** is a one-line message with exit 2 in every command, not a traceback.
- **`patches/H-history-past-compaction/`: history past compaction.** After a restart or `--resume`, the conversation scrolls back past compactions to its first message.
  - `check` passes it unchanged on every saved build from 2.1.278 through 2.1.289, and on 2.1.290.
  - Live on 2.1.290, the model received the same request as stock: 563,935 tokens patched vs 563,939 stock.
- **`patches/V-version-label/`: a version label.** A patched build's `--version` reads, for example, `2.1.290 + dcc 0.1.3 (Dazzle Claude Code)`: which Claude Code it came from, which patcher built it, and that it is not the stock build. The version constant Claude Code itself checks is untouched.
- **`scripts/test_config.py`**: a throwaway Claude Code config folder for live tests (`CLAUDE_CONFIG_DIR`), so test sessions never touch `~/.claude`.
  - Every copy it makes gets a session id starting `dcc0dcc0-` and an entry in its copies list.
  - `move-in` refuses any session that is neither marked nor listed, because a fork Claude Code made looks the same from outside.
  - Its commands are `env`, `copy`, `record`, `move-in`/`move-back`, and `list`.
- **`scripts/copy_session.py` and `scripts/compare_usage.py`** copy a session under a new id, and compare the request size two resumed copies sent. The history patch's checklist uses both.
- **A human test checklist:** `tests/checklists/v0.2.0__Phase2__history-past-compaction.md`.

### Changed

- **Python 3.11 or newer is required,** because `tomllib` reads the patch specs. CI no longer tests 3.10.

## [0.1.2] - 2026-10-05

### Added

- `dcc_patcher.containers`: a format-neutral `Container` interface and format detection. ELF (Linux) and Mach-O (macOS) are recognised and refused by name.
- `dcc_patcher.containers.pe`: reads and rewrites the Bun module graph inside the Windows `claude.exe`. Replacing a module's source drops its bytecode so Bun compiles the new source, and `verify` checks that every other module is byte-identical. Moved from the proof of concept.
- `dcc-patcher inspect <file> [--marker TEXT]`: format, Claude Code version, module count, Bun flags, and the modules containing a marker. Unsupported formats exit 2 with a one-line message.

## [0.1.1] - 2026-10-05

### Fixed

- Tests can import `dcc_patcher` when run as the pre-push hook runs them (`python -P -m pytest`, which leaves the current directory off the import path): pytest's `pythonpath` now names the project root.

## [0.1.0] - 2026-10-05

### Added

- Project scaffold from git-repokit-template, with git-repokit-common vendored at `scripts/repokit-common/`.
- `dcc_patcher` package with a `dcc-patcher` command (placeholder; the engine is not built yet).
- README, roadmap, and platform support notes.

[Unreleased]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.1.6...HEAD
[0.1.6]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.1.5...v0.1.6
[0.1.5]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/DazzleML/dazzle-claude-code-patcher/releases/tag/v0.1.0
