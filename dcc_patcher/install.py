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

from . import builds, originals, regfile, resolve, style, winpath

RECORDS = 'path.json'
LOG = 'path-log.jsonl'
BACKUPS = 'backups'
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


def backup(scope: str, action: str) -> Path:
    """Save the scope's Path value as a .reg file before `action` changes it.
    Named `<date>__<time>__path-<scope>__before-<action>__<current build>.reg`."""
    from . import launch
    value, kind = winpath.read(scope)
    build = Path(launch.load_state().get('current') or 'no-build').stem
    folder = builds.builds_dir() / BACKUPS
    folder.mkdir(parents=True, exist_ok=True)
    stem = f'{time.strftime("%Y-%m-%d__%H-%M-%S")}__path-{scope}__before-{action}__{build}'
    path, n = folder / f'{stem}.reg', 1
    while path.exists():
        n += 1
        path = folder / f'{stem}-{n}.reg'
    originals._write(path, regfile.dumps(scope, value, kind))
    return path


def backups(scope: str | None = None) -> list[Path]:
    """The PATH backups, oldest first."""
    folder = builds.builds_dir() / BACKUPS
    return sorted(folder.glob(f'*__path-{scope or "*"}__*.reg')) if folder.is_dir() else []


def restore(path: str | None, yes: bool) -> int:
    """Put a backed-up Path value back, after showing what changes and saving the current one."""
    found = Path(path) if path else (backups(winpath.USER) or [None])[-1]
    if not found or not found.is_file():
        print(f'dcc-patcher: no PATH backup {"at " + path if path else "yet"} (they are kept in '
              f'{builds.builds_dir() / BACKUPS})', file=sys.stderr)
        return 1
    scope, value, kind = regfile.loads(found.read_bytes())
    current, ckind = winpath.read(scope)
    if (current, ckind) == (value, kind):
        print(f'the {scope} PATH already matches {found.name}; nothing written')
        return 0
    if scope == winpath.SYSTEM and not winpath.is_elevated():
        print(f'dcc-patcher: {found.name} is a system PATH backup; restore it from an elevated shell', file=sys.stderr)
        return 1
    now, then = [p for p in current.split(';') if p], [p for p in value.split(';') if p]
    print(f'Restoring the {scope} PATH from {found.name}:')
    for p in then:
        if p not in now:
            print(f'  + {p}')
    for p in now:
        if p not in then:
            print(f'  - {p}')
    if [p for p in now if p in then] != [p for p in then if p in now]:
        print('  (and the order of some entries changes)')
    if kind != ckind:
        print(f'  (type {TYPES.get(ckind, ckind)} -> {TYPES[kind]})')
    if not confirm(f'Restore the {scope} PATH?', yes):
        print(f'{scope} PATH left as it was')
        return 1
    saved = backup(scope, 'restore-path')
    before = winpath.set_value(scope, value, kind)
    _log(scope, 'restore', before, value, kind)
    winpath.broadcast()
    print(f'{scope} PATH restored; the value it replaced is saved as {saved.name}')
    return 0


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


def ps_scripts_allowed() -> bool:
    """Whether PowerShell will run a local, unsigned .ps1 (the `dcc-env` script).
    Read from the registry the way PowerShell resolves its execution policy;
    Windows' own default is Restricted."""
    if sys.platform != 'win32':
        return False
    import winreg
    shell_ids = r'SOFTWARE\Microsoft\PowerShell\1\ShellIds\Microsoft.PowerShell'
    policies = r'SOFTWARE\Policies\Microsoft\Windows\PowerShell'
    places = [(winreg.HKEY_LOCAL_MACHINE, policies), (winreg.HKEY_CURRENT_USER, policies),
              None, (winreg.HKEY_CURRENT_USER, shell_ids), (winreg.HKEY_LOCAL_MACHINE, shell_ids)]
    for place in places:
        if place is None:
            value = os.environ.get('PSExecutionPolicyPreference')
        else:
            try:
                with winreg.OpenKey(place[0], place[1]) as k:
                    value = winreg.QueryValueEx(k, 'ExecutionPolicy')[0]
            except OSError:
                value = None
        if value and value.lower() != 'undefined':
            return value.lower() in ('remotesigned', 'unrestricted', 'bypass')
    return False


def catch_up(entry: str, shell: str | None) -> str:
    """The command that brings a shell opened before the install up to date."""
    shell = shell or 'powershell'
    if resolve.winner('dcc-env', os.environ.get('PATH', ''), pathext=os.environ.get('PATHEXT')):
        if shell == 'sh':
            return '. dcc-env'
        if shell == 'cmd' or ps_scripts_allowed():
            return 'dcc-env'
    if shell == 'powershell':
        return 'dcc-patcher shellenv powershell | Invoke-Expression'
    return shellenv(entry, shell)


def shell_folder(posix: bool = False) -> str:
    """The shim folder if this shell's PATH lacks it ahead of the official folder, else ''."""
    from . import launch
    entry = load_records().get('entry') or str(builds.builds_dir() / 'bin')
    if posix and sys.platform == 'win32':
        entry = str(builds.posix_shim_dir())    # the sh shims live apart from the .cmd ones
    anchor = str(Path(launch.load_state()['official']).parent)
    if _ahead(os.environ.get('PATH', ''), entry, anchor):
        return ''
    return shellenv(entry, 'sh')[len('export PATH="'):-len(':$PATH"')] if posix else entry


# -- install and uninstall ----------------------------------------------------------------

def is_set_up(folder: Path, official: str) -> bool:
    """The shims exist and the user PATH already has them ahead of the official folder."""
    shim = folder / ('claude.cmd' if sys.platform == 'win32' else 'claude')
    if not shim.is_file():
        return False
    if sys.platform != 'win32':
        return True
    if (folder / 'claude').is_file() or not (builds.posix_shim_dir() / 'claude').is_file():
        return False                            # v0.1.10's layout: the sh shims still need moving to ~/bin
    return _ahead(winpath.read(winpath.USER)[0], str(folder), str(Path(official).parent))


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
        print(f'saved the user PATH first: {backup(winpath.USER, "install-shim")}')
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
            rec.setdefault('admin_dir_created', not admin_bin().parent.exists())
            save_records(rec)
            write_shims(admin_bin())
            print(f'saved the system PATH first: {backup(winpath.SYSTEM, "install-shim")}')
            changed, before, after, kind = winpath.add(winpath.SYSTEM, str(admin_bin()), str(where.parent))
            rec['system_entry'] = str(admin_bin())
            save_records(rec)
            _log('system', 'add', before, after, kind)
            winpath.broadcast()
            print(f'system PATH updated ({TYPES[kind]}, only our entry changed)')
        else:
            code = 1

    if not _ahead(os.environ.get('PATH', ''), entry, anchor) and not os.environ.get('DCC_ENV'):
        shell = detect_shell()                  # (under dcc-env, the script itself updates the shell next)
        lines = [catch_up(entry, shell)] if shell else [f'{s}:  {catch_up(entry, s)}' for s in ('powershell', 'cmd', 'sh')]
        print('this shell started before the change; to use it here now, run:\n  ' + '\n  '.join(lines))
    return code


def uninstall() -> int:
    if sys.platform != 'win32':
        print('remove the shim folder from PATH in your shell profile')
        return 0
    rec = load_records()
    entry = rec.get('entry') or str(builds.builds_dir() / 'bin')
    if winpath.position(winpath.read(winpath.USER)[0], entry) is not None:
        print(f'saved the user PATH first: {backup(winpath.USER, "uninstall-shim")}')
    changed, before, after, kind = winpath.drop(winpath.USER, entry)
    if changed:
        _log('user', 'remove', before, after, kind)
        print(f'user PATH: removed {entry} (only that entry)')
    else:
        print(f'user PATH: {entry} was not there; nothing written')
    code = 0
    if rec.get('system_entry'):
        if winpath.is_elevated():
            if winpath.position(winpath.read(winpath.SYSTEM)[0], rec['system_entry']) is not None:
                print(f'saved the system PATH first: {backup(winpath.SYSTEM, "uninstall-shim")}')
            changed, before, after, kind = winpath.drop(winpath.SYSTEM, rec['system_entry'])
            if changed:
                _log('system', 'remove', before, after, kind)
                print(f'system PATH: removed {rec["system_entry"]}')
            rec.pop('system_entry')
            save_records(rec)
        else:
            print(f'system PATH: {rec["system_entry"]} is still there; run `dcc-patcher uninstall-shim` elevated')
            code = 1
    _remove_ours(builds.posix_shim_dir(), ('claude', 'claude-stock'), posix_dir_created(rec))
    _remove_ours(Path(entry), ('claude', 'claude-stock'), False)          # v0.1.10's sh shims, if any
    if rec.get('admin_dir_created') is not None and not rec.get('system_entry'):
        _remove_ours(admin_bin(), ('claude.cmd', 'claude-stock.cmd'), rec['admin_dir_created'], parent_too=True)
    winpath.broadcast()
    print('the .cmd shims and the rest of the builds folder (builds, kept originals, PATH backups) stay; '
          '`dcc-env` or `dcc-patcher install-shim` puts everything back')
    return code


def posix_dir_created(rec: dict) -> bool:
    """Whether install-shim made ~/bin (so uninstall may remove it once empty). Recorded at
    the first install; for an install made before it was recorded, inferred: a ~/bin that
    holds nothing but our own shims was ours."""
    if 'posix_dir_created' in rec:
        return rec['posix_dir_created']
    folder = builds.posix_shim_dir()
    if not folder.is_dir():
        return True
    return all(p.is_file() and _ours(p) for p in folder.iterdir())


def _ours(path: Path) -> bool:
    try:
        return b'Written by dcc-patcher install-shim' in path.read_bytes()[:200]
    except OSError:
        return False


def _remove_ours(folder: Path, names, created: bool | None, parent_too: bool = False):
    """Remove the shims we wrote in `folder` (never a file without our marker), and the
    folder itself when install-shim created it and nothing else is left in it."""
    for name in names:
        path = folder / name
        if path.is_file() and _ours(path):
            path.unlink()
            print(f'removed {path}')
    for where in ([folder, folder.parent] if parent_too else [folder]):
        if created and where.is_dir() and not any(where.iterdir()):
            where.rmdir()
            print(f'removed the empty folder {where}')


# -- status -------------------------------------------------------------------------------

MARKS = {'x': 'green', ' ': 'yellow', '!': 'red', '~': 'dim'}


def status(brief: bool = False) -> int:
    """Which claude this shell runs and why, and whether PATH, the launcher and the
    kept originals are in order. `brief`: the first line only (used by `dcc-env`)."""
    from . import launch
    st = launch.load_state()
    rec = load_records()
    official = st['official']
    entry = rec.get('entry') or str(builds.builds_dir() / 'bin')
    anchor = str(Path(official).parent)
    shims = {os.path.normcase(entry), os.path.normcase(str(rec.get('system_entry') or admin_bin()))}
    on = style.enabled(sys.stdout)
    lines, bad = [], 0

    def item(mark, text, fix=None, note=None):
        """One checklist row. A `note` goes on its own line under the text (under the
        path, when the text is `name -> path`), so long rows don't wrap into the marks."""
        nonlocal bad
        bad += mark in (' ', '!')
        row = '  ' + style.paint_marked(f'[{mark}] {text}', MARKS[mark], on)
        if note:
            indent = 6 + (text.index(' -> ') + 4 if ' -> ' in text else 0)
            row += '\n' + ' ' * indent + style.paint_marked(f'({note})', 'dim', on)
        lines.append(row + (f'\n        -> {style.paint_marked(fix, "cyan", on)}' if fix else ''))

    def heading(text):
        if lines:
            lines.append('')                    # a blank line between groups
        lines.append(style.paint(text, 'bold', on))

    def detail(text):
        lines.append(style.paint_marked(text, 'dim', on))

    P = style.path                              # a path or file name: shown brighter than its line

    here = os.environ.get('PATH', '')
    user = system = ''
    if sys.platform == 'win32':
        user, _ = winpath.read(winpath.USER)
        system, _ = winpath.read(winpath.SYSTEM)
    registry_ready = _ahead(user, entry, anchor)
    found = resolve.candidates('claude', here, os.environ.get('PATHEXT'))
    heading('This shell')
    if not found:
        item(' ', 'claude: not found on this shell\'s PATH', 'dcc-patcher install-shim')
    else:
        w = found[0]
        if os.path.normcase(str(w.parent)) in shims:
            item('x', f'claude -> {P(w)}', note=f'the dcc-patcher shim; runs {_runs(st, P)}')
        elif os.path.normcase(str(w)) == os.path.normcase(official) and registry_ready:
            item('!', f'claude -> {P(w)}', catch_up(entry, detect_shell()),
                 note='stock: this shell started before the PATH change')
        elif os.path.normcase(str(w)) == os.path.normcase(official):
            item(' ', f'claude -> {P(w)}', 'dcc-patcher install-shim', note='stock Claude Code')
        else:
            item('!', f'claude -> {P(w)}', note='neither the shim nor the official Claude Code')
        if brief:
            print(lines[-1])
            return 1 if bad else 0
        for p in found:
            detail(f'        {"*" if p == w else " "} {P(p)}')
    if brief:
        print('\n'.join(lines))
        return 1
    stock = resolve.winner('claude-stock', here, pathext=os.environ.get('PATHEXT'))
    item('x' if stock else '~', f'claude-stock -> {P(stock)}' if stock else 'claude-stock: not on this shell\'s PATH')
    if sys.platform == 'win32':
        sh = builds.posix_shim_dir() / 'claude'
        stale = Path(entry) / 'claude'
        if stale.is_file():
            item('!', f'{P(stale)} is an sh script on the Windows PATH', 'dcc-patcher install-shim (moves it to ~/bin)',
                 note='some tools pick it and fail: "not a valid Win32 application"')
        if any(winpath.position(v, str(sh.parent)) is not None for v in (user, system)):   # not `here`:
            # Git Bash adds ~/bin to its own PATH, which is right; only the Windows PATH is a hazard
            item('!', f'{P(sh.parent)} is on the Windows PATH', f'take {P(sh.parent)} off the Windows PATH '
                 '(Git Bash adds it by itself)', note=f'so Windows tools can pick the sh script {P(sh)}')
        item('x' if sh.is_file() else '~', f'Git Bash: claude -> {P(sh)}' if sh.is_file()
             else f'Git Bash: no shim in {P(sh.parent)}', None if sh.is_file() else 'dcc-patcher install-shim')

    if sys.platform == 'win32':
        heading('PATH')
        if registry_ready:
            item('x', f'user PATH has {P(entry)}', note=f'ahead of {P(anchor)}')
        elif winpath.position(user, entry) is not None:
            item('!', f'user PATH has {P(entry)}', 'dcc-patcher install-shim', note=f'but behind {P(anchor)}')
        else:
            item(' ', f'user PATH does not have {P(entry)}', 'dcc-patcher install-shim')
        blockers = system_claudes(system, rec)
        if not blockers:
            item('x', 'system PATH has no claude of its own')
        elif _ahead(system, str(admin_bin()), str(blockers[0].parent)):
            item('x', f'system PATH has the admin shims ahead of {P(blockers[0])}')
        else:
            item(' ', f'system PATH has {P(blockers[0])}, which always wins', 'dcc-patcher install-shim (elevated)')

    heading('Launcher')
    detail(f'      mode {st["mode"]}; current {P(st["current"]) if st.get("current") else "(none yet)"}')
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
            item('x', f'Claude Code unchanged since the last start; the next start runs {P(st["current"])}')
    except OSError:
        item(' ', f'no Claude Code at {P(official)}')

    heading('Originals')
    idx = originals._load()
    pending = originals.pending(official)
    if pending:
        item(' ', f'{len(pending)} not kept yet ({", ".join(P(p.name) for p in pending[:3])}'
                  f'{", ..." if len(pending) > 3 else ""}); Claude Code\'s updater deletes its old copies over time',
             'dcc-patcher archive')
    else:
        item('x', f'{len(idx["kept"])} kept in {P(builds.builds_dir())}')
    saved = backups()
    if saved or rec.get('base_path_user'):
        heading('Backups')
        if saved:
            detail(f'      {len(saved)} PATH backup{"" if len(saved) == 1 else "s"}; newest {P(saved[-1].name)}')
            detail('      undo the last change: dcc-patcher restore-path')
        base = rec.get('base_path_user')
        if base:
            detail(f'      PATH as first seen recorded {base["at"]} ({RECORDS})')
    print('\n'.join(lines))
    return 1 if bad else 0


def _runs(st: dict, mark=str) -> str:
    if os.environ.get('DCC_MODE') == 'stock' or st['mode'] == 'stock':
        return 'stock'
    if st['mode'] != 'patched':
        return f'the pinned build {mark(st["mode"])}'
    return mark(st['current']) if st.get('current') else 'a new patched build'
