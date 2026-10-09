"""PoC: can dcc-patcher own exactly one PATH entry safely, with plain Python?

Prediction: with winreg + ctypes and no dependencies, inserting one entry before an
anchor and removing it again leaves every other byte and the value's registry type
unchanged; removal still works after something else edited the value, and refuses
(writes nothing) when our entry is gone; and a WM_SETTINGCHANGE "Environment"
broadcast is what makes a process started through Explorer see a new
HKCU\\Environment value.

Rule 1b: nothing here can write the real Path. Every write goes through _write(),
which refuses the value name "Path" in any case, and writes to HKCU\\Environment
only for names starting with DCC_POC_. Arms A-E work on copies of the real PATH
values stored under a scratch key, which is deleted at the end.

    python -P tests/one-offs/thinking/user-path-editor/poc.py <scratch folder>
"""
import ctypes
import json
import os
import subprocess
import sys
import time
import winreg
from ctypes import wintypes
from pathlib import Path

SCRATCH_KEY = r'Software\dazzle-claude-code-patcher-poc'
ENV_KEY = r'Environment'
OWNED = r'C:\dcc-poc\builds\bin'
TYPES = {winreg.REG_SZ: 'REG_SZ', winreg.REG_EXPAND_SZ: 'REG_EXPAND_SZ'}
rows = []


def _guard(key, name):
    assert name.lower() != 'path', 'the PoC never writes a value named Path'
    if key == ENV_KEY:
        assert name.startswith('DCC_POC_'), 'only DCC_POC_* scratch variables in HKCU\\Environment'
    else:
        assert key == SCRATCH_KEY, 'writes go to the scratch key only'


def _write(key, name, value, kind):
    _guard(key, name)
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as k:
        winreg.SetValueEx(k, name, 0, kind, value)


def _delete(key, name):
    _guard(key, name)
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_SET_VALUE) as k:
        winreg.DeleteValue(k, name)


def read(hive, key, name):
    with winreg.OpenKey(hive, key, 0, winreg.KEY_READ) as k:
        return winreg.QueryValueEx(k, name)          # raw: (value, type), never expanded


# -- the editor under test: string-level, so "every other byte" is checkable -----------

def entries(value):
    return value.split(';')


def insert_before(value, owned, anchor):
    """One owned entry before the anchor; already present -> unchanged."""
    parts = entries(value)
    if any(p.rstrip('\\').lower() == owned.rstrip('\\').lower() for p in parts):
        return value
    norm = [p.rstrip('\\').lower() for p in parts]
    i = norm.index(anchor.rstrip('\\').lower()) if anchor.rstrip('\\').lower() in norm else 0
    return ';'.join(parts[:i] + [owned] + parts[i:])


def remove_owned(value, owned):
    """Remove exactly our entry; None when it is not there (the caller writes nothing)."""
    parts = entries(value)
    keep = [p for p in parts if p.rstrip('\\').lower() != owned.rstrip('\\').lower()]
    return None if len(keep) == len(parts) else ';'.join(keep)


def naive_expand_write(value):
    """The control: what an expand-then-write round trip (PowerShell's
    [Environment]::GetEnvironmentVariable then Set...) does to the stored value."""
    return os.path.expandvars(value), winreg.REG_SZ


def row(arm, prediction, observed, ok, fallback=''):
    rows.append({'arm': arm, 'prediction': prediction, 'observed': observed,
                 'verdict': 'as predicted' if ok else 'NOT as predicted', 'fallback': fallback})
    print(f"[{'ok' if ok else 'XX'}] {arm}: {observed}")


# -- broadcast and an Explorer-started probe ----------------------------------------------

def broadcast():
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    res = wintypes.DWORD()
    ok = user32.SendMessageTimeoutW(wintypes.HWND(0xFFFF), 0x001A, 0, ctypes.c_wchar_p('Environment'),
                                    0x0002, 5000, ctypes.byref(res))
    return bool(ok)


def explorer_probe(folder, tag):
    out = folder / f'probe_{tag}.txt'
    if out.exists():
        out.unlink()
    cmd = folder / f'probe_{tag}.cmd'
    cmd.write_text(f'@echo off\r\n(echo NOBC=[%DCC_POC_NOBC%])> "{out}"\r\n', encoding='ascii')
    # Run 1 used `explorer.exe <cmd>`: that starts a NEW explorer process, which builds its
    # environment from the registry, so its control saw the variable unbroadcast (method
    # broken). Run 2-3 used Shell.Application.ShellExecute: the control then held (NOBC=[]),
    # but so did the broadcast arm even 3 s later -- Shell.Application is an in-process COM
    # object, so the probe inherits PowerShell's (our) environment and F can never pass.
    # Arm F is INCONCLUSIVE: settling it needs a launch from inside the running explorer.exe.
    subprocess.run(['powershell', '-NoProfile', '-Command',
                    f"(New-Object -ComObject Shell.Application).ShellExecute('{cmd}')"])
    for _ in range(60):
        if out.exists() and out.stat().st_size:
            time.sleep(0.2)
            return out.read_text(encoding='ascii', errors='replace').strip()
        time.sleep(0.25)
    return '(no output in 15 s)'


def main():
    folder = Path(sys.argv[1]).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    HKCU, HKLM = winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE
    user, user_t = read(HKCU, ENV_KEY, 'Path')
    mach, mach_t = read(HKLM, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'Path')
    anchor = next(p for p in entries(user) if p.rstrip('\\').lower().endswith('.local\\bin'))
    try:
        # A: a raw copy keeps value and type
        _write(SCRATCH_KEY, 'UserCopy', user, user_t)
        _write(SCRATCH_KEY, 'MachineCopy', mach, mach_t)
        u = read(HKCU, SCRATCH_KEY, 'UserCopy')
        m = read(HKCU, SCRATCH_KEY, 'MachineCopy')
        row('A raw copy', 'value and type identical', f'user {TYPES[u[1]]} same={u == (user, user_t)}; '
            f'machine {TYPES[m[1]]} same={m == (mach, mach_t)}', u == (user, user_t) and m == (mach, mach_t))

        # B: insert before the anchor, write back with the original type
        record = {'value': 'UserCopy', 'type': TYPES[user_t], 'owned': OWNED, 'anchor': anchor,
                  'before': user, 'at': time.strftime('%Y-%m-%dT%H:%M:%S')}
        (folder / 'record.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
        new = insert_before(user, OWNED, anchor)
        _write(SCRATCH_KEY, 'UserCopy', new, user_t)
        got, t = read(HKCU, SCRATCH_KEY, 'UserCopy')
        others_same = got.replace(OWNED + ';', '', 1) == user
        pos = entries(got).index(OWNED) == entries(got).index(anchor) - 1
        row('B insert', 'type kept; only "<owned>;" added, right before the anchor',
            f'type {TYPES[t]}; others byte-identical={others_same}; just before anchor={pos}; '
            f'{len(user)} -> {len(got)} chars', t == user_t and others_same and pos)

        # C: inserting again changes nothing
        row('C idempotent', 'a second insert is a no-op', f'unchanged={insert_before(got, OWNED, anchor) == got}',
            insert_before(got, OWNED, anchor) == got)

        # D: removal restores the original exactly
        back = remove_owned(got, OWNED)
        _write(SCRATCH_KEY, 'UserCopy', back, user_t)
        b = read(HKCU, SCRATCH_KEY, 'UserCopy')
        row('D remove', 'byte-identical to the before-image, same type', f'identical={b == (user, user_t)}',
            b == (user, user_t))

        # E1: something else edits PATH while ours is in; removal keeps their edit
        theirs = insert_before(user, OWNED, anchor) + r';C:\some-other-installer\bin'
        after = remove_owned(theirs, OWNED)
        ok = after == user + r';C:\some-other-installer\bin'
        row('E1 remove after a foreign edit', 'their entry kept, ours gone, rest identical',
            f'kept theirs and dropped ours={ok}', ok,
            'restoring the saved before-image instead would have deleted their entry')
        # E2: our entry already gone -> refuse, write nothing
        row('E2 ours already gone', 'remove returns None (nothing written)',
            f'returned {remove_owned(user, OWNED)!r}', remove_owned(user, OWNED) is None)

        # CONTROL: the naive expand-and-write round trip, on the REG_EXPAND_SZ machine copy,
        # must FAIL the same identity check, or the check proves nothing
        nv, nt = naive_expand_write(mach)
        _write(SCRATCH_KEY, 'MachineCopy', nv, nt)
        c = read(HKCU, SCRATCH_KEY, 'MachineCopy')
        row('CONTROL naive expand+write (predicted to FAIL identity)',
            'identity check fails: %SystemRoot% expanded, type REG_EXPAND_SZ -> REG_SZ',
            f'identical={c == (mach, mach_t)}; type {TYPES[c[1]]}; %VAR% left={nv.count("%")}',
            c != (mach, mach_t))

        # F: the broadcast, with a before/after control on one variable
        _write(ENV_KEY, 'DCC_POC_NOBC', 'seen', winreg.REG_SZ)
        before = explorer_probe(folder, 'before_broadcast')
        row('F-control written, NOT broadcast (predicted NOT seen)', 'NOBC=[] (Explorer has not reloaded)',
            before, before.strip() in ('NOBC=[]', 'NOBC=[%DCC_POC_NOBC%]'))
        sent = broadcast()
        after_b = explorer_probe(folder, 'after_broadcast')
        row('F broadcast', 'NOBC=[seen] after WM_SETTINGCHANGE', f'sent={sent}; {after_b}', after_b == 'NOBC=[seen]')
        time.sleep(3)
        late = explorer_probe(folder, 'after_broadcast_3s')
        row('F broadcast, probed 3 s later', 'NOBC=[seen]', late, late == 'NOBC=[seen]')
    finally:
        for key, name in ((ENV_KEY, 'DCC_POC_NOBC'),):
            try:
                _delete(key, name)
            except FileNotFoundError:
                pass
        broadcast()
        try:
            winreg.DeleteKey(HKCU, SCRATCH_KEY)
        except FileNotFoundError:
            pass
        still = []
        for key, name in ((ENV_KEY, 'DCC_POC_NOBC'),):
            try:
                read(HKCU, key, name)
                still.append(name)
            except FileNotFoundError:
                pass
        real_after = read(HKCU, ENV_KEY, 'Path')
        print(f'cleanup: scratch values left={still}; real user Path unchanged={real_after == (user, user_t)}')
        (folder / 'rows.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
