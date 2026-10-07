"""The launcher behind the `claude` shim (#5): run the current patched build,
re-patch when the official Claude Code updates, fall back to stock.

The shims `install-shim` writes are one line each; everything else is here, so
a new platform adds a template and no logic. State lives in the builds folder as
`launcher.json`:

    mode      "patched" (the newest good build, rebuilt on update), "stock", or
              a build's file name (pinned; never rebuilt)
    current   the versioned build "patched" runs; the launcher runs that file,
              never `claude-dcc.exe`, so a running session never locks the link
              `apply` refreshes
    official  the official executable (default ~/.local/bin/claude.exe)
    official_stat, official_sha256
              the official exe's size and mtime, and its sha256, so a start
              that finds nothing changed does not hash 250 MB

`DCC_MODE=stock` or `DCC_MODE=patched` overrides `mode` for one shell. A run
with `CLAUDE_CONFIG_DIR` set (the test config) never writes state or builds; if
a rebuild would be needed, it runs stock and says so. The official install and
`~/.claude` are only ever read.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

from . import builds

MODES = ('stock', 'patched')
STATE = 'launcher.json'


def default_official() -> str:
    name = 'claude.exe' if sys.platform == 'win32' else 'claude'
    return str(Path(os.path.expanduser('~')) / '.local' / 'bin' / name)


def state_path() -> Path:
    return builds.builds_dir() / STATE


def load_state() -> dict:
    try:
        st = json.loads(state_path().read_text(encoding='utf-8'))
    except (OSError, ValueError):
        st = {}
    st.setdefault('mode', 'patched')
    st.setdefault('official', default_official())
    return st


def save_state(st: dict):
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f'.{STATE}.tmp')
    tmp.write_text(json.dumps(st, indent=2) + '\n', encoding='utf-8')
    os.replace(tmp, path)


def official_sha(st: dict, official: str) -> str:
    """The official exe's sha256, hashed only when its size, mtime or file id changed.
    The updater moves a staged file into place, so an update always changes the id."""
    s = os.stat(official)
    stamp = [s.st_size, s.st_mtime_ns, s.st_ino]
    if st.get('official_stat') == stamp and st.get('official_sha256'):
        return st['official_sha256']
    h = hashlib.sha256()
    with open(official, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    st['official_stat'], st['official_sha256'] = stamp, h.hexdigest()
    return st['official_sha256']


def built_from(name: str) -> str | None:
    """The input sha256 a build's lockfile records, or None."""
    try:
        lock = json.loads((builds.builds_dir() / f'{name}.dcc-lock.json').read_text())
    except (OSError, ValueError):
        return None
    return lock.get('input_sha256')


def kept_builds() -> list[str]:
    """The versioned builds in the folder, oldest first (by modification time)."""
    folder = builds.builds_dir()
    if not folder.is_dir():
        return []
    found = [p for p in folder.glob(f'{builds.CURRENT}-*') if not p.name.endswith(('.json', '.md', '.tmp'))]
    return [p.name for p in sorted(found, key=lambda p: p.stat().st_mtime_ns)]


def choose(env=None) -> tuple[str, str | None]:
    """(the executable to run, a one-line note for stderr or None)."""
    env = os.environ if env is None else env
    st = load_state()
    official = st['official']
    mode, note = st['mode'], None
    if env.get('DCC_MODE'):
        if env['DCC_MODE'] in MODES:
            mode = env['DCC_MODE']
        else:
            note = f'dcc: DCC_MODE={env["DCC_MODE"]} is not stock or patched; using "{mode}"'
    if mode == 'stock':
        return official, note
    if mode != 'patched':                                   # a pinned build
        pinned = builds.builds_dir() / mode
        if pinned.is_file():
            return str(pinned), note
        return official, _join(note, f'dcc: the pinned build {mode} is gone; running stock (dcc-patcher use patched)')
    writable = not env.get('CLAUDE_CONFIG_DIR')
    try:
        sha = official_sha(st, official)
    except OSError as e:
        return official, _join(note, f'dcc: cannot read {official} ({e.strerror or e}); running it as is')
    current = st.get('current')
    if current and (builds.builds_dir() / current).is_file() and built_from(current) == sha:
        if writable:
            save_state(st)                                  # keeps the sha cache fresh
        return str(builds.builds_dir() / current), note
    if not writable:
        return official, _join(note, 'dcc: Claude Code changed since the current build, and this is the test '
                                     'config (CLAUDE_CONFIG_DIR), so nothing is rebuilt here; running stock')
    built, failing = rebuild(official)
    if built:
        st['current'] = Path(built).name
        save_state(st)
        return built, _join(note, f'dcc: Claude Code updated; now running {Path(built).name}')
    save_state(st)
    which = f'patch {", ".join(failing)} needs' if failing else 'the rebuild needs'
    return official, _join(note, f'dcc: {which} attention after the Claude Code update; '
                                 f'running stock (dcc-patcher check "{official}")')


def _join(*notes) -> str | None:
    return '\n'.join(n for n in notes if n) or None


def rebuild(official: str) -> tuple[str | None, list[str]]:
    """Build the official exe into the builds folder, quietly.
    Returns (the new build, []) or (None, the ids of the patches that need a human)."""
    from . import cli
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            code, built, results = cli.build(official)
        except Exception:                                   # a bad build must never stop claude starting
            return None, []
    if built and results and all(r.ok for r in results):
        return built, []
    return None, [r.patch.id for r in results if not r.ok]


def _exec(exe: str, args: list[str]) -> int:
    if sys.platform != 'win32':
        os.execv(exe, [exe, *args])
    signal.signal(signal.SIGINT, signal.SIG_IGN)            # Ctrl+C belongs to Claude Code
    return subprocess.call([exe, *args])


def main(argv=None) -> int:
    args = sys.argv[1:] if argv is None else argv
    exe, note = choose()
    if note:
        print(note, file=sys.stderr)
    if not os.path.isfile(exe):
        print(f'dcc: no Claude Code at {exe}', file=sys.stderr)
        return 127
    return _exec(exe, args)


if __name__ == '__main__':
    sys.exit(main())
