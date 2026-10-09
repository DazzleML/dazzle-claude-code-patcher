# The launcher: builds, shims, PATH and backups

This is the detail behind `dcc-env`, `dcc-patcher status` and the builds folder. The README has the short version; this page says where every file goes, what each command changes, and how to check or undo any of it by hand.

## The builds folder

Every `apply` writes into one folder, whatever folder you run it from:

| Install | Builds folder |
|---|---|
| a checkout of this repository (`pip install -e .`) | `private\builds\` in the checkout |
| a package install (`pip install dazzle-claude-code-patcher`) | `%LOCALAPPDATA%\dazzle-claude-code-patcher\builds\` (Windows); `~/.local/share/dazzle-claude-code-patcher/builds/` (Linux, macOS) |
| either, with `DCC_BUILDS_DIR` set | that folder |

What lives there:

| File | What it is |
|---|---|
| `claude-dcc-<claude version>+dcc<patcher version>.exe` | a patched build. Older builds stay for rollback; rebuilding the same versions says `already built` |
| `claude-dcc-<…>.exe.dcc-lock.json` | that build's lockfile: every edit's site and the text it replaced |
| `claude-dcc.exe` | a hardlink to the newest build. If it's running, `apply` keeps the new build, says the link still points at the old one, and exits 1 |
| `claude-cc-<claude version>.exe` | the original Claude Code the build was made from, kept for re-testing a patch or diffing a build against its source. The updater's own `claude.exe.old.*` backups are kept too, since it deletes them over time. `dcc-patcher archive` keeps any not kept yet (about 250 MB each). `originals.json` is the index |
| `launcher.json` | the launcher's state: which build `claude` runs (see *Choosing what runs*) |
| `bin\claude.cmd`, `bin\dazzle-claude.cmd`, `bin\claude-stock.cmd` | the shims for cmd and PowerShell |
| `path.json`, `path-log.jsonl` | the `PATH` values first seen, and every change made since |
| `backups\*.reg` | a copy of `Path` taken before each change |

`apply -o <path>` writes exactly that file instead, with no link and no record. `apply` never writes inside Claude Code's own config folder (`~/.claude`, or `CLAUDE_CONFIG_DIR`).

## What `dcc-env` does

`dcc-env` (cmd, PowerShell) or `. dcc-env` (Git Bash) is a script that runs *inside* your shell, because no program can change the `PATH` of the shell that started it. It runs `dcc-patcher install-shim --if-needed`, then prepends the shim folder to that shell's `PATH`, then prints `dcc-patcher status --brief`. Shells and Windows Terminal tabs opened afterwards see the new `PATH` by themselves; `dcc-env` is for the shell you already have open.

pip installs the three scripts beside `dcc-patcher.exe` (on Windows, the Python `Scripts` folder), which every shell can already find. PowerShell runs `dcc-env.ps1` only when its execution policy allows local scripts; when it doesn't, `dcc-patcher shellenv powershell | Invoke-Expression` does the same in one line.

### `install-shim`, step by step

1. Writes `claude.cmd`, `dazzle-claude.cmd` and `claude-stock.cmd` to `<builds>\bin\`, and `claude`, `dazzle-claude` and `claude-stock` (sh) to `~/bin`. (`dazzle-claude` is new in v0.2.1; an older install gets it on its next `dcc-env`.) Git for Windows puts `~/bin` first on Git Bash's `PATH`, and Windows never searches it, so no Windows tool can pick an sh script by mistake. If `~/bin` doesn't exist, it's created and that fact recorded, so `uninstall-shim` can remove it again. A file in `~/bin` that `install-shim` didn't write is never overwritten.
2. Asks before changing `PATH` (`--yes` skips the question; `--no-path` leaves `PATH` alone; `DCC_YES=1` is `--yes` for scripts).
3. Saves the current user `Path` to `backups\` (see below).
4. Adds one entry to the user `PATH`: `<builds>\bin`, just before `%USERPROFILE%\.local\bin`. That folder stays on `PATH` because Claude Code's updater checks for it. Nothing else changes: the value keeps its registry type (`REG_SZ` or `REG_EXPAND_SZ`), `%VAR%` entries stay unexpanded, and the value is read back to confirm. Then it broadcasts the change, which is what new shells and Windows Terminal tabs pick up.
5. Only if the *system* `PATH` (searched before yours) has a `claude` of its own: an elevated run puts an admin-only copy of the shims in `%ProgramFiles%\dazzle-claude-code-patcher\bin` and adds that entry to the system `PATH` just ahead of it, after asking. A non-elevated run says so and leaves the system `PATH` alone. Otherwise the system `PATH` is never written.

Every shim carries the line `Written by dcc-patcher install-shim`; the tool only ever removes files that carry it.

### Checking by hand

```cmd
where claude                      :: cmd: every claude on PATH, in order; the first one runs
```
```powershell
Get-Command claude -All           # PowerShell
```
```bash
which -a claude                   # Git Bash
```

`<builds>\bin\claude.cmd` should come first (in Git Bash, `~/bin/claude`), then `%USERPROFILE%\.local\bin\claude.exe`. `dcc-patcher status` does the same check and explains anything out of order.

The registry values themselves:

```cmd
reg query HKCU\Environment /v Path
reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v Path
```

## Choosing what runs

| Command | What `claude` runs from the next start |
|---|---|
| `dcc-patcher use patched` | the newest good build, rebuilt after each Claude Code update (the default) |
| `dcc-patcher use stock` | the official `claude.exe` |
| `dcc-patcher use <build file name>` | that build, pinned (no rebuilds) |
| `dcc-patcher rollback` | the build before the current one, pinned |
| `dcc-patcher use` | shows the current state |

### Switching, in the shell you're in

`dazzle-claude` always runs the current patched build and `claude-stock` the official one, whatever `claude` means. `use` changes what `claude` means everywhere, from the next start. For one shell:

```
dcc-env stock                     # claude runs the official build in THIS shell (cmd, PowerShell; Git Bash: . dcc-env stock)
dcc-env patched                   # the current patched build
dcc-env claude-dcc-2.1.290+dcc0.1.9.exe   # that build, pinned, in this shell
dcc-env default                   # back to the persistent choice
```

Under the hood each one sets or clears `DCC_MODE` in the shell (`set DCC_MODE=stock`, `$env:DCC_MODE = 'stock'`, `export DCC_MODE=stock` do the same by hand). The launcher reads it at every start, ahead of the persistent choice; a value that is neither `stock`, `patched` nor a build's file name is named and ignored. A new window starts from the persistent choice again. `dcc-patcher status` (and the `--brief` line `dcc-env` prints) says which one wins and why:

```
  [x] claude -> C:\...\builds\bin\claude.cmd
                (the dcc-patcher shim; runs stock (this shell: dcc-env stock; persistent: patched))
```

At each start the launcher compares the official `claude.exe` with what the current build was made from. When Claude Code has updated, it says so (`dcc: Claude Code updated; building the patched copy...`), rebuilds in a few seconds, keeps the original, and runs the new build. If a patch no longer applies, it runs stock instead, with one line naming what needs attention and the `check` command to run.

With `CLAUDE_CONFIG_DIR` set (a test config), the launcher never rebuilds or changes its state: if a rebuild would be needed, it runs stock and says so. The official install and its updater are only ever read; the updater writes to its own fixed path under `.local\bin`, so it never touches the shims or the builds.

## PATH backups and `restore-path`

Before every `PATH` write (install, uninstall, restore), the old value is saved as a `.reg` file in `<builds>\backups\`, named for when it was taken, what was about to change it and which build was current:

```
2026-10-08__21-10-05__path-user__before-install-shim__claude-dcc-2.1.295+dcc0.1.11.reg
```

It holds `Path` only, never your other variables, in the same format `reg export` writes (so `REG_EXPAND_SZ` values appear as `hex(2):` bytes, as they do in any exported `.reg`).

- `dcc-patcher restore-path` puts the newest backup back, after showing which entries come back and which go, and asking. It saves the current value first, so a restore can itself be undone.
- `dcc-patcher restore-path <file>` picks another backup.
- **Without dcc-patcher:** double-click the file, or `reg import <file>`. Then open a new shell.

## `status`

`dcc-patcher status` shows, in groups: which `claude` this shell runs and whether it's the patched build; the user and system `PATH` entries and anything out of order; the launcher's state and current build; the originals kept; and the backups. Each row has a mark (done, pending, a problem) and the command that fixes it. It exits 1 while anything is left to do, so a script can test it. `status --brief` is the short form `dcc-env` prints. Colour is on for a terminal and off for pipes and `NO_COLOR`.

## Undoing everything

`dcc-patcher uninstall-shim` puts back everything outside the builds folder:

- removes the entries `install-shim` added from the user `PATH` (and, when elevated, from the system `PATH`), saving a backup first, and leaving anything other installers added since;
- removes the Git Bash shims from `~/bin`, and `~/bin` itself if `install-shim` created it and it's now empty;
- when elevated, removes the admin copy of the shims and its Program Files folder, if `install-shim` created them.

The builds folder stays (builds, originals, backups, the `.cmd` shims), so a later `dcc-env` puts everything back. Delete the folder to remove the rest.

**By hand**, if the tool isn't available:

1. `reg import` the newest `backups\*path-user*.reg` (and the newest `*path-system*.reg`, elevated, if one exists), or edit `Path` in *System Properties > Environment Variables* and remove the `<builds>\bin` entry.
2. Delete `<builds>\bin\`, and `~/bin/claude`, `~/bin/dazzle-claude`, `~/bin/claude-stock` (only the ones with the `Written by dcc-patcher install-shim` line), and `%ProgramFiles%\dazzle-claude-code-patcher\` if it exists.
3. Open a new shell and run `where claude`: only `%USERPROFILE%\.local\bin\claude.exe` should be left.

The official `claude.exe` is never modified by any of this, so there is nothing to restore there.

## After a Claude Code update

The launcher handles it at the next start. To do it yourself, or to see what changed:

```cmd
dcc-patcher check %USERPROFILE%\.local\bin\claude.exe      :: does every patch still apply? (read-only)
dcc-patcher apply %USERPROFILE%\.local\bin\claude.exe      :: build the new copy
dcc-patcher check --baseline <builds>\claude-dcc.exe.dcc-lock.json %USERPROFILE%\.local\bin\claude.exe
```

The last form, when an edit fails, shows a diff of that code region against the last build where the patch worked, with minified names normalised so only real changes show. Exit codes: 0 fine, 1 a patch needs a human, 2 a usage error or an unsupported file.

A patched copy has its code signature removed (any edit invalidates it), so antivirus or SmartScreen may question it the first time.
