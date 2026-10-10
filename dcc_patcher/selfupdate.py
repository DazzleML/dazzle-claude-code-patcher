"""Is this dcc-patcher install current, and `dcc-patcher update [--fix]` (v0.2.4).

Two kinds of install. A normal `pip install` puts dcc-patcher and its dcc-env scripts
in place together, so the only thing that can be waiting is a newer release on PyPI.
An editable install (`pip install -e <checkout>`) runs the checkout's code, but pip
copied the dcc-env scripts into Python's Scripts folder when it last ran, and recorded
the version of that moment; both fall behind as the checkout moves on.

`state()` answers offline (status and dcc-env's line use it on every run).
`update()` adds PyPI and, with --fix, runs pip after asking. On Windows pip can't
delete the running dcc-patcher.exe it moved aside, so it reports an error although
the install completed (measured: tests/one-offs/measure_pip_replaces_running_exe.py);
`update` therefore asks a fresh process what is installed rather than trusting
pip's exit code. On a real install it went worse (2026-10-09): pip couldn't even move
the running dcc-patcher.exe, stopped halfway and restored nothing. So `--fix` never
runs pip from dcc-patcher.exe; it says to run `python -m dcc_patcher update --fix`.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from urllib.parse import unquote, urlparse

from ._version import BASE_VERSION

DIST = 'dazzle-claude-code-patcher'
SCRIPT_NAMES = ('dcc-env', 'dcc-env.cmd', 'dcc-env.ps1')
STAMP = re.compile(rb"""DCC_ENV_V\s*=\s*['"]?(\d+\.\d+\.\d+[^'"\s]*)""")
PYPI = f'https://pypi.org/pypi/{DIST}/json'
RELEASES = 'https://github.com/DazzleML/dazzle-claude-code-patcher/releases'


def vtuple(v: str) -> tuple:
    """'0.2.4' -> (0, 2, 4); a pre-release suffix ('-beta') is ignored."""
    return tuple(int(x) for x in re.findall(r'\d+', (v or '').split('-')[0])[:3])


def _dist():
    try:
        return metadata.distribution(DIST)
    except metadata.PackageNotFoundError:
        return None


def checkout_of(dist) -> Path | None:
    """The source folder of an editable install (from pip's direct_url.json)."""
    try:
        info = json.loads(dist.read_text('direct_url.json') or '{}')
    except (OSError, ValueError):
        return None
    if not (info.get('dir_info') or {}).get('editable'):
        return None
    url = urlparse(info.get('url', ''))
    if url.scheme != 'file':
        return None
    path = unquote(url.path)
    if re.match(r'^/[A-Za-z]:', path):            # file:///C:/x -> C:/x
        path = path[1:]
    return Path(path)


def script_copies(dist) -> list:
    """The dcc-env scripts pip installed for this distribution, from its RECORD."""
    return [Path(dist.locate_file(f)).resolve() for f in (dist.files or []) if Path(str(f)).name in SCRIPT_NAMES]


def stamp(path: Path) -> str | None:
    try:
        m = STAMP.search(path.read_bytes())
    except OSError:
        return None
    return m.group(1).decode() if m else None


def state() -> dict:
    """Offline: what runs, what pip recorded, whether the dcc-env copies are current,
    and the pip command that would bring it all in step (None when nothing is due)."""
    dist = _dist()
    st = {'running': BASE_VERSION, 'installed': None, 'kind': 'source', 'checkout': None,
          'scripts': [], 'pending': [], 'fix': None}
    if dist is None:
        return st                                 # run from a checkout without pip: nothing to compare
    st['installed'] = dist.version
    checkout = checkout_of(dist)
    st['kind'] = 'editable' if checkout else 'pip'
    st['checkout'] = str(checkout) if checkout else None
    for copy in script_copies(dist):
        ver = stamp(copy)
        source = checkout / 'bin' / copy.name if checkout else None
        if source and source.is_file():
            current = copy.is_file() and copy.read_bytes() == source.read_bytes()
        else:
            current = ver == BASE_VERSION
        st['scripts'].append({'path': str(copy), 'version': ver, 'current': current})
    stale = [s for s in st['scripts'] if not s['current']]
    if stale:                                     # one line for the three scripts
        vers = {s['version'] for s in stale}
        what = f'dcc-env {next(iter(vers))}' if len(vers) == 1 and None not in vers else 'an older dcc-env'
        st['pending'].append(f'the dcc-env scripts in {Path(stale[0]["path"]).parent} are {what}, '
                             + ("not this checkout's bin/" if checkout else f'not {BASE_VERSION}'))
    if checkout and vtuple(st['installed']) != vtuple(BASE_VERSION):
        st['pending'].append(f'pip records {st["installed"]}; the checkout is {BASE_VERSION}')
    if st['pending']:
        st['fix'] = ([sys.executable, '-m', 'pip', 'install', '-e', str(checkout)] if checkout else
                     [sys.executable, '-m', 'pip', 'install', '--force-reinstall', '--no-deps',
                      f'{DIST}=={st["installed"]}'])
    return st


def pypi_latest(timeout: float = 5.0) -> tuple:
    """(latest version, None) or (None, why not). Network."""
    import urllib.request
    try:
        with urllib.request.urlopen(PYPI, timeout=timeout) as r:
            return json.load(r)['info']['version'], None
    except Exception as e:                      # noqa: BLE001 -- offline, proxy, PyPI down: say so
        return None, f'{type(e).__name__}: {e}'


def summary(st: dict) -> str:
    """One line for status's Updates row."""
    where = {'editable': f' (editable: {st["checkout"]})', 'pip': ' (pip install)',
             'source': ' (run from source; pip has no record of it)'}[st['kind']]
    return f'dcc-patcher {st["running"]}{where}'


def _verify(run) -> tuple:
    """What a fresh process sees after pip ran: the new code, not this process's.
    (state or None, whether dcc_patcher can't even be imported any more)."""
    r = run([sys.executable, '-P', '-m', 'dcc_patcher', 'update', '--offline', '--json'],
            capture_output=True, text=True)
    try:
        return json.loads(r.stdout), False
    except (ValueError, TypeError):
        return None, "No module named 'dcc_patcher'" in (getattr(r, 'stderr', '') or '')


def fix_hint() -> str:
    """The command that runs the fix. On Windows it goes through python.exe, never
    dcc-patcher.exe (see from_launcher_exe)."""
    if sys.platform == 'win32':
        exe = f'"{sys.executable}"' if ' ' in sys.executable else sys.executable
        return f'{exe} -m dcc_patcher update --fix'
    return 'dcc-patcher update --fix'


def from_launcher_exe() -> bool:
    """Started as dcc-patcher.exe (the console launcher pip wrote), rather than as
    `python -m dcc_patcher`. Windows keeps a running .exe locked; on 2026-10-09 pip,
    run from it, moved the install's metadata, path hook and scripts aside, failed on
    the locked dcc-patcher.exe (WinError 32), and put nothing back: dcc_patcher was
    left uninstalled and `claude` couldn't start."""
    return sys.platform == 'win32' and Path(sys.argv[0]).stem.lower() == 'dcc-patcher'


def update(fix=False, yes=False, dry_run=False, offline=False, as_json=False, *,
           run=None, fetch=None, ask=input, tty=None, out=print, exe=None) -> int:
    """Report; with `fix`, run the one pip command that brings the install current,
    after asking (bare Enter = no). 0: current (or brought current); 1: something
    is waiting (or the fix didn't take); 2: asked to fix with no terminal and no --yes.
    `run` and `fetch` are looked up at call time, so a test's stub always wins."""
    run = run or subprocess.run
    fetch = fetch or pypi_latest
    st = state()
    latest = why = None
    if not offline:
        latest, why = fetch()
    if latest and st['kind'] == 'pip' and vtuple(latest) > vtuple(st['running']):
        st['pending'].append(f'dcc-patcher {latest} is out (this is {st["running"]})')
        st['fix'] = [sys.executable, '-m', 'pip', 'install', '--upgrade', DIST]
    if as_json:
        out(json.dumps(dict(st, latest=latest)))
        return 1 if st['pending'] else 0
    out(summary(st))
    for s in st['scripts']:
        tag = f' (dcc-env {s["version"]})' if s['version'] else ''
        out(f'  [{"x" if s["current"] else "!"}] {s["path"]}{tag}')
    if offline:
        out('  PyPI: not checked (--offline)')
    elif latest:
        out(f'  PyPI: {latest} is the latest release ({RELEASES})')
    else:
        out(f'  PyPI: not reached ({why})')
    if not st['pending']:
        out('up to date')
        return 0
    for p in st['pending']:
        out(f'  waiting: {p}')
    cmd = ' '.join(f'"{a}"' if ' ' in a else a for a in st['fix'])
    if not fix:
        out(f'-> {fix_hint()}   (runs: {cmd})')
        return 1
    if dry_run:
        out(f'[dry-run] would run: {cmd}')
        return 1
    if (from_launcher_exe() if exe is None else exe):
        out('dcc-patcher.exe can\'t update itself: Windows keeps it locked while it runs, and pip then stops '
            'halfway and leaves dcc-patcher uninstalled. Run this instead (the same check, without the .exe):')
        out(f'  {fix_hint()}')
        return 2
    if not yes:
        if not (sys.stdin.isatty() if tty is None else tty):
            out(f'dcc-patcher: no terminal to ask in; rerun with --yes, or run it yourself: {cmd}')
            return 2
        try:
            answer = ask(f'run {cmd} ? [y/N] ').strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ''
        if answer not in ('y', 'yes'):
            out('nothing changed')
            return 1
    code = run(st['fix']).returncode
    after, gone = _verify(run)
    if gone:
        out(f'pip stopped partway and dcc-patcher is no longer installed. Put it back now, from a new shell: {cmd}')
        out('Until then `claude`, `claude-stock` and `dazzle-claude` can\'t start; the official '
            '%USERPROFILE%\\.local\\bin\\claude.exe still can.')
        return 1
    if after is not None and not after.get('pending'):
        if code:
            out('done. pip reported an error, but the install completed: on Windows pip can\'t delete the '
                'running dcc-patcher.exe it moved aside; that copy is left in a pip-uninstall-* folder in '
                '%TEMP% and is safe to delete.')
        else:
            out('done.')
        out('The next `claude` start rebuilds if the dcc-patcher version changed.')
        return 0
    out(f'not current yet{": " + "; ".join(after["pending"]) if after else ""}. '
        f'Run it yourself from a new shell: {cmd}')
    return 1
