"""Putting the shim on PATH, taking it off again, and `status` (#9).

`install-shim` owns one entry in the user PATH (the shim folder, just before the
official Claude Code's folder). It writes the system PATH only when a `claude`
there would otherwise always win (the system PATH is searched first), only when
elevated, and then through an admin-owned copy of the shims, never the user's
builds folder. The first values it saw are kept as `base_path_user` and
`base_path_system` in `<builds>/path.json`; every write is appended to
`<builds>/path-log.jsonl`. A child process cannot change its shell's PATH, so
the shell that ran the install gets a one-line command instead (`shellenv`).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from . import builds, originals, resolve, winpath

RECORDS = 'path.json'
LOG = 'path-log.jsonl'
TYPES = {winpath.REG_SZ: 'REG_SZ', winpath.REG_EXPAND_SZ: 'REG_EXPAND_SZ'}
SHELLS = {'cmd.exe': 'cmd', 'powershell.exe': 'powershell', 'pwsh.exe': 'powershell',
          'bash.exe': 'sh', 'sh.exe': 'sh', 'zsh.exe': 'sh'}


def _now() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%S')


def load_records() -> dict:
    try:
        return json.loads((builds.builds_dir() / RECORDS).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def save_records(rec: dict):
    originals._write(builds.builds_dir() / RECORDS, (json.dumps(rec, indent=2) + '\n').encode('utf-8'))


def _log(scope: str, action: str, before: str, after: str, kind: int):
    path = builds.builds_dir() / LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps({'at': _now(), 'scope': scope, 'action': action, 'type': TYPES.get(kind, kind),
                            'before': before, 'after': after}) + '\n')


def admin_bin() -> Path:
    return Path(os.environ.get('ProgramFiles', r'C:\Program Files')) / 'dazzle-claude-code-patcher' / 'bin'


def confirm(question: str, yes: bool) -> bool:
    if yes or os.environ.get('DCC_YES') == '1':
        return True
    if not sys.stdin or not sys.stdin.isatty():
        print(f'{question} -- not asked (not an interactive shell); rerun with --yes to do it')
        return False
    return input(f'{question} [y/N] ').strip().lower() in ('y', 'yes')


def system_claudes(system_value: str, rec: dict) -> list[Path]:
    """`claude` files the system PATH finds, other than our own admin shims."""
    ours = os.path.normcase(str(rec.get('system_entry') or admin_bin()))
    return [p for p in resolve.candidates('claude', system_value)
            if os.path.normcase(str(p.parent)) != ours]


# -- the current shell ---------------------------------------------------------------------

def _process_names() -> dict[int, tuple[int, str]]:
    import ctypes
    from ctypes import wintypes

    class Entry(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('cntUsage', wintypes.DWORD), ('th32ProcessID', wintypes.DWORD),
                    ('th32DefaultHeapID', ctypes.c_size_t), ('th32ModuleID', wintypes.DWORD),
                    ('cntThreads', wintypes.DWORD), ('th32ParentProcessID', wintypes.DWORD),
                    ('pcPriClassBase', ctypes.c_long), ('dwFlags', wintypes.DWORD),
                    ('szExeFile', ctypes.c_wchar * 260)]
    k32 = ctypes.WinDLL('kernel32', use_last_error=True)
    k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snap = k32.CreateToolhelp32Snapshot(0x2, 0)
    procs, e = {}, Entry()
    e.dwSize = ctypes.sizeof(Entry)
    try:
        ok = k32.Process32FirstW(snap, ctypes.byref(e))
        while ok:
            procs[e.th32ProcessID] = (e.th32ParentProcessID, e.szExeFile.lower())
            ok = k32.Process32NextW(snap, ctypes.byref(e))
    finally:
        k32.CloseHandle(snap)
    return procs


def detect_shell() -> str | None:
    """'cmd', 'powershell' or 'sh': the nearest shell among this process's parents."""
    if sys.platform != 'win32':
        return 'sh'
    try:
        procs = _process_names()
    except Exception:
        return None
    pid = os.getpid()
    for _ in range(8):
        parent, _name = procs.get(pid, (None, ''))
        if parent is None or parent not in procs:
            return None
        shell = SHELLS.get(procs[parent][1])
        if shell:
            return shell
        pid = parent
    return None


def shellenv(entry: str, shell: str) -> str:
    if shell == 'cmd':
        return f'set "PATH={entry};%PATH%"'
    if shell == 'sh':
        posix = entry.replace('\\', '/')
        if len(posix) > 1 and posix[1] == ':':
            posix = f'/{posix[0].lower()}{posix[2:]}'
        return f'export PATH="{posix}:$PATH"'
    return f'$env:Path = "{entry};" + $env:Path'


def _ahead(value: str, entry: str, anchor: str | None) -> bool:
    here, at = winpath.position(value, entry), winpath.position(value, anchor) if anchor else None
    return here is not None and (at is None or here < at)


# -- install and uninstall ----------------------------------------------------------------

def install(folder: Path, official: str, yes: bool, write_shims) -> int:
    """The PATH step of `install-shim`. `write_shims(folder)` writes a shim set."""
    entry, anchor = str(folder), str(Path(official).parent)
    if sys.platform != 'win32':
        print(f'Add {entry} ahead of {anchor} on PATH in your shell profile, for example:\n  {shellenv(entry, "sh")}')
        return 0
    if not yes and os.environ.get('DCC_YES') != '1' and (not sys.stdin or not sys.stdin.isatty()):
        print(f'PATH not changed (not an interactive shell). To put {entry} ahead of {anchor}: '
              f'dcc-patcher install-shim --yes')
        return 0
    rec = load_records()
    user, ukind = winpath.read(winpath.USER)
    system, skind = winpath.read(winpath.SYSTEM)
    rec.setdefault('base_path_user', {'value': user, 'type': TYPES[ukind], 'at': _now()})
    rec.setdefault('base_path_system', {'value': system, 'type': TYPES[skind], 'at': _now()})
    rec.update(entry=entry, anchor=anchor)
    save_records(rec)
    code = 0

    if _ahead(user, entry, anchor):
        print(f'user PATH: already has {entry} ahead of {anchor}')
    elif confirm(f'User PATH: add {entry} just before {anchor}?', yes):
        changed, before, after, kind = winpath.add(winpath.USER, entry, anchor)
        _log('user', 'add', before, after, kind)
        winpath.broadcast()
        print(f'user PATH updated ({TYPES[kind]}, {len(before)} -> {len(after)} chars, only our entry changed); '
              'new shells will use it')
    else:
        print('user PATH left as it was')
        code = 1

    blockers = system_claudes(system, rec)
    if blockers and not _ahead(system, str(admin_bin()), str(blockers[0].parent)):
        where = blockers[0]
        if not winpath.is_elevated():
            print(f'system PATH: has {where}, which is searched before the user PATH, so it always wins. '
                  f'Run `dcc-patcher install-shim` in an elevated shell to put the shims ahead of it there')
            code = 1
        elif confirm(f'System PATH: {where} always wins over the user PATH. Add the shims '
                     f'(an admin-only copy in {admin_bin()}) just before {where.parent}?', yes):
            write_shims(admin_bin())
            changed, before, after, kind = winpath.add(winpath.SYSTEM, str(admin_bin()), str(where.parent))
            rec['system_entry'] = str(admin_bin())
            save_records(rec)
            _log('system', 'add', before, after, kind)
            winpath.broadcast()
            print(f'system PATH updated ({TYPES[kind]}, only our entry changed)')
        else:
            code = 1

    if not _ahead(os.environ.get('PATH', ''), entry, anchor):
        shell = detect_shell()
        lines = [shellenv(entry, shell)] if shell else [f'{s}:  {shellenv(entry, s)}' for s in ('powershell', 'cmd', 'sh')]
        print('this shell started before the change; to use it here now, run:\n  ' + '\n  '.join(lines))
    return code


def uninstall() -> int:
    if sys.platform != 'win32':
        print('remove the shim folder from PATH in your shell profile')
        return 0
    rec = load_records()
    entry = rec.get('entry') or str(builds.builds_dir() / 'bin')
    changed, before, after, kind = winpath.drop(winpath.USER, entry)
    if changed:
        _log('user', 'remove', before, after, kind)
        print(f'user PATH: removed {entry} (only that entry)')
    else:
        print(f'user PATH: {entry} was not there; nothing written')
    code = 0
    if rec.get('system_entry'):
        if winpath.is_elevated():
            changed, before, after, kind = winpath.drop(winpath.SYSTEM, rec['system_entry'])
            if changed:
                _log('system', 'remove', before, after, kind)
                print(f'system PATH: removed {rec["system_entry"]}')
            rec.pop('system_entry')
            save_records(rec)
        else:
            print(f'system PATH: {rec["system_entry"]} is still there; run `dcc-patcher uninstall-shim` elevated')
            code = 1
    winpath.broadcast()
    print('the shim files are left in place; `dcc-patcher install-shim` puts them back on PATH')
    return code


# -- status -------------------------------------------------------------------------------

def status() -> int:
    from . import launch
    st = launch.load_state()
    rec = load_records()
    official = st['official']
    entry = rec.get('entry') or str(builds.builds_dir() / 'bin')
    anchor = str(Path(official).parent)
    shims = {os.path.normcase(entry), os.path.normcase(str(rec.get('system_entry') or admin_bin()))}
    lines, bad = [], 0

    def item(mark, text, fix=None):
        nonlocal bad
        bad += mark in (' ', '!')
        lines.append(f'  [{mark}] {text}' + (f'\n        -> {fix}' if fix else ''))

    here = os.environ.get('PATH', '')
    found = resolve.candidates('claude', here, os.environ.get('PATHEXT'))
    lines.append('This shell')
    if not found:
        item(' ', 'claude: not found on this shell\'s PATH', 'dcc-patcher install-shim')
    else:
        w = found[0]
        if os.path.normcase(str(w.parent)) in shims:
            item('x', f'claude -> {w} (the dcc-patcher shim; runs {_runs(st)})')
        elif os.path.normcase(str(w)) == os.path.normcase(official):
            item(' ', f'claude -> {w} (stock Claude Code)', 'dcc-patcher install-shim')
        else:
            item('!', f'claude -> {w} (neither the shim nor the official Claude Code)')
        for p in found:
            lines.append(f'        {"*" if p == w else " "} {p}')
    stock = resolve.winner('claude-stock', here, pathext=os.environ.get('PATHEXT'))
    item('x' if stock else '~', f'claude-stock -> {stock}' if stock else 'claude-stock: not on this shell\'s PATH')

    if sys.platform == 'win32':
        user, _ = winpath.read(winpath.USER)
        system, _ = winpath.read(winpath.SYSTEM)
        lines.append('PATH')
        if _ahead(user, entry, anchor):
            item('x', f'user PATH has {entry}, ahead of {anchor}')
            if not _ahead(here, entry, anchor):
                item('!', 'this shell started before that change', shellenv(entry, detect_shell() or 'powershell'))
        elif winpath.position(user, entry) is not None:
            item('!', f'user PATH has {entry}, but behind {anchor}', 'dcc-patcher install-shim')
        else:
            item(' ', f'user PATH does not have {entry}', 'dcc-patcher install-shim')
        blockers = system_claudes(system, rec)
        if not blockers:
            item('x', 'system PATH has no claude of its own')
        elif _ahead(system, str(admin_bin()), str(blockers[0].parent)):
            item('x', f'system PATH has the admin shims ahead of {blockers[0]}')
        else:
            item(' ', f'system PATH has {blockers[0]}, which always wins', 'dcc-patcher install-shim (elevated)')

    lines.append('Launcher')
    lines.append(f'      mode {st["mode"]}; current {st.get("current") or "(none yet)"}')
    try:
        s = os.stat(official)
        changed = st.get('official_stat') != [s.st_size, s.st_mtime_ns, s.st_ino]
        if st['mode'] == 'stock':
            item('~', 'mode stock: claude runs the official Claude Code', 'dcc-patcher use patched')
        elif not st.get('current'):
            item('~', 'no patched build yet; the first start builds one (a few seconds)')
        elif changed:
            item('~', 'Claude Code changed since the last start; the next start rebuilds (a few seconds)')
        else:
            item('x', f'Claude Code unchanged since the last start; the next start runs {st["current"]}')
    except OSError:
        item(' ', f'no Claude Code at {official}')

    lines.append('Originals')
    idx = originals._load()
    pending = originals.pending(official)
    if pending:
        item(' ', f'{len(pending)} not kept yet ({", ".join(p.name for p in pending[:3])}'
                  f'{", ..." if len(pending) > 3 else ""}); the updater deletes its .old copies after 30 days',
             'dcc-patcher archive')
    else:
        item('x', f'{len(idx["kept"])} kept in {builds.builds_dir()}')
    base = rec.get('base_path_user')
    if base:
        lines.append(f'      PATH as first seen recorded {base["at"]} ({RECORDS})')
    print('\n'.join(lines))
    return 1 if bad else 0


def _runs(st: dict) -> str:
    if os.environ.get('DCC_MODE') == 'stock' or st['mode'] == 'stock':
        return 'stock'
    if st['mode'] != 'patched':
        return f'the pinned build {st["mode"]}'
    return st.get('current') or 'a new patched build'
