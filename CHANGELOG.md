# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.11] - 2026-11-18

### Fixed

- **The banner patch applies on Claude Code 2.1.327 again.** Through 2.1.326 the classic session header was written twice in one component, a truncating form for narrow terminals and a normal one, and the patch required exactly two. 2.1.327 writes it once and picks the wrap inline, so the patch found one and refused. It now labels one copy or two and still refuses any other count.
- **The cross-file history patch applies on Claude Code 2.1.327 again, and should stop breaking this way.** 2.1.326 and 2.1.327 each added an argument to the call that builds the loader's entry map, nested one and then two calls deep, and each time the patch's one edit stopped matching because it described what those arguments could look like. It now carries whatever follows the first argument, up to 300 characters, as far as the call's close and the destructure that follows it on every build. Nothing in what the patch does changed.

  In both cases the launcher saw `patch B, J needs attention; running stock` and ran stock Claude Code, as designed.

### Added

- **A patch edit can list the counts different builds have.** `expect = [1, 2]` in a patch spec accepts either count and refuses any other; a single number still means exactly that many. The check's report says `expected 1 or 2`.

### Changed

- Every patch applies on every saved original from 2.1.278 to 2.1.327 (`dcc-patcher check`, 36 builds).

## [0.2.10] - 2026-11-17

### Fixed

- **The cross-file history patch applies on Claude Code 2.1.326 again.** Its one edit anchors on the head of Claude Code's session-file loader and carries the entry map maker's extra arguments as written. 2.1.326 gave the maker a third argument that holds a parenthesised group, which the edit's pattern did not allow, so it found no site. The launcher saw `patch J needs attention; running stock` and ran stock Claude Code, as designed. The pattern now takes one level of parentheses inside the maker's extra arguments and still reproduces them as written, so it applies on every saved original from 2.1.278 to 2.1.326. Nothing in what the patch does changed.

### Changed

- Every patch applies unchanged on Claude Code 2.1.325 (the launcher built it on its own) and on 2.1.326 with the refreshed anchor (`dcc-patcher check` on the saved originals, 2.1.278 to 2.1.326).

## [0.2.9] - 2026-11-13

### Fixed

- **The flicker-free banner patch applies on Claude Code 2.1.323 again.** The patch finds its module by a status message printed beside the fullscreen header, `Using flicker-free rendering`. The fullscreen tips say the same words after a leading space, and until 2.1.322 both lived in one module. 2.1.323 moved the header and its status line into a small module of their own, so the words named two modules and the patch refused to choose. The launcher saw `patch B2 needs attention; running stock` and ran stock Claude Code, as designed. The marker now starts at the message's opening quote, which only the header's module has, on every saved original from 2.1.278 to 2.1.323. Neither edit changed.

### Changed

- Every patch applies unchanged on Claude Code 2.1.321 and 2.1.322 (the launcher built each on its own) and on 2.1.323 with the refreshed marker (`dcc-patcher check` on the saved originals, 2.1.278 to 2.1.323).

## [0.2.8] - 2026-11-06

### Fixed

- **The cross-file history patch applies on Claude Code 2.1.319 again.** Its one edit anchored on the exact head of Claude Code's session-file loader, which 2.1.319 reshaped three ways: a local declared before the entry map's maker, a second argument to the maker, and a resume-head block (a tail-load trial, switched off on Windows) between the destructure and `precede()`. The launcher saw `patch J needs attention; running stock` and ran stock Claude Code, as designed. The edit now lets plain declarators precede the maker's, takes the maker's extra arguments, and allows a bounded gap before `precede()`, reproducing each as written, so it applies to both shapes: every saved original from 2.1.278 to 2.1.319. Nothing in what the patch does changed.

### Changed

- Every patch applies unchanged on Claude Code 2.1.316, 2.1.317 and 2.1.318 (the launcher built each on its own) and on 2.1.319 with the refreshed anchor (`dcc-patcher check` on the saved originals, 2.1.278 to 2.1.319).

## [0.2.7] - 2026-10-30

### Fixed

- **The history patch applies on Claude Code 2.1.314 again.** Its walker edit anchored on the exact call of Claude Code's five-second fallback, which 2.1.314 gave a new first argument (a per-walk cache that sorts each side's rows by time once and binary-searches them, replacing a scan of every row on every miss). The launcher saw `patch H needs attention; running stock` and ran stock Claude Code, as designed. The edit now captures the fallback's argument list whole and reproduces it as written, so it applies to both shapes: every saved original from 2.1.278 to 2.1.314, 13 edit sites each. Nothing in what the patch does changed.

### Changed

- Every patch applies unchanged on Claude Code 2.1.311, 2.1.312 and 2.1.314 (`dcc-patcher check` on the saved originals, 2.1.278 to 2.1.314). 2.1.314 also attaches, after the walk, rows written as children of the newest entry (tool results that reached the file late) and, behind a flag, honours explicit checkpoint rewinds; neither touches what the patch edits.

## [0.2.6] - 2026-10-22

### Fixed

- **A patched Claude Code 2.1.308 or 2.1.309 could refuse to start** with `error: An internal error occurred (Corrupted module graph: module contents are out of range)`. The Bun runtime those two releases are compiled with checks, at startup, that a NUL byte follows every module's embedded JavaScript (oven-sh/bun#46021; reverted upstream in oven-sh/bun#46461, which later Claude Code releases may or may not carry). The patcher wrote that NUL only as 8-byte alignment padding, so a replaced module whose new length was a multiple of 8 had none: two of the five edited modules in 2.1.309, none in 2.1.308, which started by luck. Every replacement now ends with a NUL, as Bun's own writer does, and the build's verify step checks for it. The launcher rebuilds on the next start (`dcc: dcc-patcher updated`).

### Changed

- Every patch applies unchanged on Claude Code 2.1.299 to 2.1.309 (`dcc-patcher check` on the saved originals, 2.1.278 to 2.1.309). The launcher rebuilt for each update on its own.

## [0.2.5] - 2026-10-11

### Fixed

- **A resumed session reaches the history before a compaction whose last messages were still in flight when it ran** (`patches/H-history-past-compaction/`, #1). When Claude Code compacts while messages are still being written, those messages reach the session file after the summary, already linked onto it, so the file never records what came before them. The walk used that missing link, found the summary instead, and stopped at the last compaction: the screen began at `Compact summary`, with thousands of earlier rows loaded and unreachable. The walk now continues from the latest row before the boundary in file order when the recorded links lead nowhere, and a session resumed right after an idle compaction (nothing after the summary) continues from the parent the prune recorded. On this machine 34 of 200 compactions in 31 of 66 session files had the first shape, written by Claude Code 2.1.205 through 2.1.292; it is not tied to one release. What the model receives is unchanged. Applies on 2.1.278 to 2.1.296.

## [0.2.4] - 2026-10-09

### Added

- **`dcc-patcher update`** says whether this install is current: the dcc-patcher that runs, how it was installed, whether the `dcc-env` scripts pip copied are this version's, and the latest release on PyPI (`--offline` skips PyPI). **`update --fix`** shows the one pip command that brings it current and runs it only after you say yes (a bare Enter is no; `--yes` when there's no terminal; `--dry-run` shows it and runs nothing), then checks what is actually installed rather than trusting pip's exit code. On Windows run it as `python -m dcc_patcher update --fix` (the command `status` and `update` print): pip can't reliably replace `dcc-patcher.exe` while it is running, and can stop halfway with dcc-patcher uninstalled, so `dcc-patcher update --fix` refuses and names that command instead.
- **`dcc-patcher -h <command>`** shows that command's help (the same as `dcc-patcher <command> -h`).
- **An Updates group in `dcc-patcher status`**, from the same check, without going online. The line `dcc-env` prints gains a second row only when something is out of date, with the fix. An editable install's `dcc-env` copies that pip left behind are now named instead of silently running old code.
- **`dcc-patcher -h` groups the commands by what they act on**: patches (read-only), builds, and this machine. Every command and option works as before.
- **`dcc-patcher -V`**, short for `--version`.
- **`dcc-env -V` and `dcc-env --version`** print the script's version and dcc-patcher's, and say when they differ.
- **`dcc-env -h` and `dcc-env --help`** (and `dcc-env /?` in cmd) list the choices (`stock`, `patched`, a build's file name, `default`) and what each does, then stop: no setup, no `PATH` change, no change to what `claude` runs.

### Changed

- **One dependency: [dazzle-lib](https://pypi.org/project/dazzle-lib/)**, itself standard-library only. It draws the paired commands in `dcc-patcher -h` and is loaded for nothing else: the `claude` launcher and patching still use the standard library alone, and the help falls back to the plain layout if dazzle-lib is missing.
- `use`'s help now says the patched build is rebuilt "when Claude Code or dcc-patcher changes" (it said "on update", which read as `dcc-patcher update`).

### Fixed

- **`dcc-env` refuses an unknown option** instead of taking it as the mode. Before, `dcc-env --help` or `dcc-env --stock` set `DCC_MODE` to that word, which the launcher then named and ignored. It now prints `dcc-env: unknown option ...`, points at `--help`, and changes nothing.

## [0.2.3] - 2026-10-09

### Added

- **Plugins can see every patch a build carries** (#8). When the launcher starts a patched build it sets `DCC_PATCHES` (the patch ids and their tags, from the build's lockfile: `B=banner-label-v1,B2=banner-label-flicker-free-v1,H=history-v1,J=cross-file-v1,R=rows-v1,V=version-label-v1`) and `DCC_PATCHER` (the version that made the build), beside the `DCC_PATCH_H` the history patch sets itself. A plugin reads them with `$.env.get`. When the launcher starts stock, it removes all three first, so a stock Claude Code started from inside a patched session's shell doesn't inherit a signal that isn't true of it.

## [0.2.2] - 2026-10-09

### Added

- **Compaction rows in the normal view** (`patches/R-compaction-rows/`, #7). The normal screen now draws each compaction summary where it happened, as a bold `Compact summary (ctrl+o to expand)` line, the same row the transcript starts with, so after a resume `Ctrl+Home` lands on the same first row in both views and a bookmark on a compaction summary has somewhere to land. One edit in the prompt screen's row filter, which dropped every transcript-only user row; it now keeps the compaction summaries and nothing else. Display only: what is loaded and what the model receives are unchanged. Applies on 2.1.278 to 2.1.295.
- **The launcher rebuilds when dcc-patcher itself changed**, not only when Claude Code did. A build's name carries the patcher version that made it; when that isn't the installed version, the next start says `dcc: dcc-patcher updated; building the patched copy...` and runs the new build, so a new or changed patch reaches `claude` right after `pip install --upgrade`. The older build stays in the builds folder.

## [0.2.1] - 2026-10-09

### Added

- **Switching what `claude` means, in the shell you're in.** `dcc-env stock`, `dcc-env patched`, `dcc-env <build file name>` and `dcc-env default` set (or clear) the choice for that shell, on top of `dcc-patcher use`, which sets it everywhere from the next start. In Git Bash: `. dcc-env stock`. A build's file name pins that build, as `use <build>` does.
- **`dazzle-claude`**, a shim that always runs the current patched build, beside `claude-stock`, which always runs the official one, whatever `claude` means.
- **`status` says which choice wins and why**: `runs stock (this shell: dcc-env stock; persistent: patched)`, also on the `--brief` line `dcc-env` prints. A `DCC_MODE` value that is neither `stock`, `patched` nor a build is named and ignored.
- **`status` flags a cmd or PowerShell that inherited `~/bin` ahead of the shims** (a shell opened from Git Bash does). PowerShell then resolves `claude-stock` to the extensionless sh script and hands it to Windows, which asks how to open the file. The fix is `dcc-env`, which puts the shims first in that shell.

### Changed

- **An existing install gains `dazzle-claude` on its next `dcc-env`**: a layout without it counts as not set up, so `install-shim --if-needed` writes the three shims (the existing two rewritten in place; a file by one of those names that isn't ours is left alone, as before).

## [0.2.0] - 2026-10-09

The first tagged release, on PyPI: `pip install dazzle-claude-code-patcher`. It carries everything from v0.1.5 to v0.1.11 (versioned builds, the launcher, `dcc-env`, `status`, PATH backups, kept originals, history across session files, the plugin signal, the bundled patches) on top of the tool and the history patch. No code changed since v0.1.11.

### Changed

- **The README is down to what you need to use the tool**: install, `check` and `apply`, `dcc-env` and `status`, how it works. The detail moved to `docs/launcher.md`: the builds folder and every file in it, what `install-shim` changes step by step, choosing what `claude` runs, the `.reg` backups and `restore-path`, `status`, `uninstall-shim`, and how to check or undo all of it by hand, without dcc-patcher.
- README links are absolute, so the page renders on PyPI.
- `ROADMAP.md`, `docs/platform-support.md`, `CONTRIBUTING.md` and the patch READMEs say where things stand (every patch applies on 2.1.278 to 2.1.295; the history patch is in daily use).
- The source distribution carries the package, the `dcc-env` scripts, README, CHANGELOG and LICENSE, and nothing else (`MANIFEST.in`). Tests, checklists and docs stay in the repository.
- The PyPI workflow runs when a GitHub Release is published, and can also be run by hand from the Actions tab for a given tag; a re-run skips files already on PyPI.

## [0.1.11] - 2026-10-08

### Added

- **`dcc-env`: one word that sets up and fixes the shell you're in.** In cmd or PowerShell type `dcc-env`, in Git Bash `. dcc-env`. It runs `install-shim` if the launcher isn't set up yet, then puts it on `PATH` in that shell, including one that was open before the install (a program can't change its shell's `PATH`, so this is a script that runs inside the shell). pip installs the three scripts beside `dcc-patcher`. In PowerShell it needs an execution policy that runs local scripts; `status` gives the alternative when it doesn't.
- **A backup before every `PATH` change**, as a `.reg` file holding only `Path`, in the builds folder's `backups\`, named `<date>__<time>__path-<user|system>__before-<command>__<current build>.reg`. `reg import` restores it without dcc-patcher.
- **`dcc-patcher restore-path [file]`** puts the newest (or the named) backup back, after showing which entries come back and which go, and saves the current value first.
- **`status` is coloured on a terminal**: green done, yellow pending, red a problem, cyan the command to run, with each path in a brighter shade of its line's colour. A blank line separates the groups, and a row's explanation goes on its own line under the path, so narrow terminals don't wrap into the marks. Pipes and `NO_COLOR` get plain text. It also shows the backups, the Git Bash shim, and two hazards: an sh script on the Windows `PATH`, and `~/bin` on the Windows `PATH`.

### Changed

- **The Git Bash shims moved to `~/bin`**, which Git for Windows puts first on Git Bash's `PATH` and Windows never searches. In v0.1.10 they sat beside `claude.cmd` on the Windows `PATH`, where a resolver that tries the bare name first (Python 3.12.0's `shutil.which`) picked the sh script, and launching it failed with "not a valid Win32 application" (claude-session-backup's `resume`). `install-shim` removes the old ones it wrote and never overwrites a file in `~/bin` that isn't its own.
- **`uninstall-shim` now puts back everything outside the builds folder as it was**: besides its `PATH` entries, it removes the Git Bash shims from `~/bin` (and `~/bin` itself if `install-shim` created it and it's empty) and, when elevated, the admin copy of the shims in Program Files. It never removes a file that isn't its own. The builds folder (builds, kept originals, `PATH` backups, the `.cmd` shims) stays, so a later `dcc-env` puts everything back.
- **A shell opened before the install is told how to catch up** (`dcc-env`), instead of being told to run `install-shim` again.
- **The launcher's first start says "first start"**, and a start after an update says "Claude Code updated", before building.

## [0.1.10] - 2026-10-08

### Added

- **`install-shim` puts the launcher on `PATH` for you** (Windows), after asking (`--yes` skips the question, `--no-path` leaves `PATH` alone). It adds one entry to the user `PATH`, the shim folder, just before Claude Code's own folder, and changes nothing else: the registry type and `%VAR%` entries are kept, and the value is read back to confirm. When the system `PATH` has a `claude` of its own, an elevated run puts an admin-only copy of the shims just ahead of it; otherwise the system `PATH` is never touched. The first values seen and every change are recorded in the builds folder.
- **`dcc-patcher uninstall-shim`** removes only the entries `install-shim` added, so anything other installers added since stays.
- **`dcc-patcher status`**: which `claude` this shell runs (every candidate, in the order the shell searches), whether the user and system `PATH` are set up, whether this shell was opened before the change, what the next start will run, and whether every original build is kept. Each open item comes with the command that fixes it; the exit code is 1 while anything is open.
- **`dcc-patcher shellenv`** prints the one line that puts the launcher on `PATH` in the current shell (cmd, PowerShell or sh), so a shell opened before the install needn't be closed.
- **Every original Claude Code is kept** as `claude-cc-<version>.exe` in the builds folder: the input of every build, and the updater's own `claude.exe.old.*` backups, which it deletes after a while. `dcc-patcher archive` keeps any not kept yet.

### Changed

- **The launcher says it's rebuilding before it starts**, on the same single line that then reports the result.

### Fixed

- **Building from an updater backup (`claude.exe.old.<number>`) names the build `.exe`**, instead of using the number as its extension.

## [0.1.9] - 2026-10-07

### Changed

- **The bundled patches ship inside the package** (`dcc_patcher/patches/`), so an installed wheel finds them. Until now they sat at the repository's root, and only a source checkout could see them. The launcher's shim templates ship as package data too.

### Fixed

- **`validate`, `check` and `apply` refuse to run with no patch specs** (exit 2, one line), instead of reporting a clean run that checked nothing.

## [0.1.8] - 2026-10-07

### Added

- **Plugins can tell the history patch is in place.** A build with the history patch sets `DCC_PATCH_H=history-v1` in Claude Code's environment. A plugin reads it with `$.env.get("DCC_PATCH_H")` and can then scroll straight to a resumed session's earliest messages; on stock it reads nothing. The history patch's README has a section for plugin authors. Builds made before this version don't set it, so rebuild.

## [0.1.7] - 2026-10-07

### Added

- **`patches/J-history-across-files/`: history across session files.** A conversation that continued into a new session file, after running out of context or after a fork, now scrolls back into the file it came from, and on to the first message of the original conversation.
  - When a session file points at a message it doesn't contain, the loader finds it in another `.jsonl` file of the same folder and loads that file's lines up to the message. It repeats for a grandparent session.
  - A missing or damaged earlier file stops the search quietly, and the session loads as before.
  - Needs the history patch (H).
  - `check` passes on every saved build from 2.1.278 through 2.1.292. Not yet live-tested.
  - Derived from ojura/claude-patches' Patch J (MIT), with credit in the patch and its README.

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

[Unreleased]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.2.11...HEAD
[0.2.11]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.2.10...v0.2.11
[0.2.10]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.2.9...v0.2.10
[0.2.9]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.2.8...v0.2.9
[0.2.8]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.2.7...v0.2.8
[0.2.7]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.2.6...v0.2.7
[0.2.6]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.2.5...v0.2.6
[0.2.5]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.2.4...v0.2.5
[0.2.4]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.2.3...v0.2.4
[0.2.3]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.2.2...v0.2.3
[0.2.2]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.2.1...v0.2.2
[0.2.1]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/DazzleML/dazzle-claude-code-patcher/releases/tag/v0.2.0
[0.1.11]: https://github.com/DazzleML/dazzle-claude-code-patcher/commit/e0aa8ec305c8d8fc29f1bc5314a0655818265c42
[0.1.10]: https://github.com/DazzleML/dazzle-claude-code-patcher/commit/40423e590306a4b3481a45a5c11ddaeba7cd3a23
[0.1.9]: https://github.com/DazzleML/dazzle-claude-code-patcher/commit/6262f679cb17cd8331201794ab841533fcad5f50
[0.1.8]: https://github.com/DazzleML/dazzle-claude-code-patcher/commit/94d9f5ab77583ccd6fefaa138b0e6984ed6d3f2a
[0.1.7]: https://github.com/DazzleML/dazzle-claude-code-patcher/commit/9b84f6cfb96afa074f873e84ff125d02a43ff74e
[0.1.6]: https://github.com/DazzleML/dazzle-claude-code-patcher/commit/23b92bcae02dbfe8e114c6ff33344b23efc12b2b
[0.1.5]: https://github.com/DazzleML/dazzle-claude-code-patcher/commit/35e2736a3d0b147e22a0d0dbb0a750ad195b7b4b
[0.1.4]: https://github.com/DazzleML/dazzle-claude-code-patcher/commit/78865b92f2c3a4c1201bb6c2b8f2cd24ce0c7d23
[0.1.3]: https://github.com/DazzleML/dazzle-claude-code-patcher/commit/6cbf0af6daf78c6b2e7f5679b4af5fde1a0d49a9
[0.1.2]: https://github.com/DazzleML/dazzle-claude-code-patcher/commit/52e38298478081a794b82e092b51111036530cc2
[0.1.1]: https://github.com/DazzleML/dazzle-claude-code-patcher/commit/16a5fab94b4f6166ac30c649e866f03e8da0731e
[0.1.0]: https://github.com/DazzleML/dazzle-claude-code-patcher/commit/fff40a72a499d3756830d86c6b1af2b1a75ef41c
