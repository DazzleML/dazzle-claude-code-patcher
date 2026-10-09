"""Measure, read-only: what does this machine's PATH look like in the registry, and how
does Claude Code's own installer put .local\\bin on it? Decides how dcc-patcher can
manage one PATH entry safely (type preserved, nothing expanded, nothing else touched).

Writes nothing to the registry. Snippets from claude.exe go to the file given as
argv[1] (a scratch path), never into the repository.

    python -P tests/one-offs/measure_v0.1.10_user_path.py <scratch-snippets.txt>
"""
import ctypes
import os
import re
import subprocess
import sys
import winreg

TYPES = {winreg.REG_SZ: 'REG_SZ', winreg.REG_EXPAND_SZ: 'REG_EXPAND_SZ'}
HIVES = {
    'User': (winreg.HKEY_CURRENT_USER, r'Environment', r'HKCU\Environment'),
    'Machine': (winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment',
                r'HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment'),
}


def raw(hive, key):
    with winreg.OpenKey(hive, key, 0, winreg.KEY_READ) as k:
        return winreg.QueryValueEx(k, 'Path')       # (value, type), never expanded


def reg_query(name):
    out = subprocess.run(['reg', 'query', name, '/v', 'Path'], capture_output=True, text=True).stdout
    m = re.search(r'^\s+Path\s+(REG_\w+)\s+(.*)$', out, re.M)
    return (m.group(2).rstrip('\r'), m.group(1)) if m else None


def census(label, value, kind):
    parts = value.split(';')
    entries = [p for p in parts if p]
    lower = [os.path.normcase(os.path.expandvars(p)).rstrip('\\') for p in entries]
    dups = len(lower) - len(set(lower))
    pct = [p for p in entries if '%' in p]
    missing = [p for p in entries if not os.path.isdir(os.path.expandvars(p))]
    print(f'{label}: type {TYPES.get(kind, kind)}, {len(value)} chars, {len(parts)} parts = '
          f'{len(entries)} entries + {len(parts) - len(entries)} empty; trailing ";" {value.endswith(";")}')
    print(f'  entries with %VAR%: {len(pct)}  {pct}')
    print(f'  duplicates after expand+normcase: {dups}')
    print(f'  entries that are not an existing folder: {len(missing)}')
    if 'local\\bin' in value.lower():
        idx = [i for i, p in enumerate(entries) if p.lower().rstrip('\\').endswith('.local\\bin')]
        print(f'  .local\\bin at entry index {idx}')
    expanded = os.path.expandvars(value)
    print(f'  an expand-then-write round trip would change the stored value: {expanded != value}')


def main():
    snippets_path = sys.argv[1] if len(sys.argv) > 1 else None
    print('== 1. PATH in the registry (raw, unexpanded)')
    for label, (hive, key, name) in HIVES.items():
        value, kind = raw(hive, key)
        known = reg_query(name)                       # known-answer: reg.exe's own reading
        same = known is not None and known[0] == value and known[1] == TYPES.get(kind)
        print(f'[known-answer] winreg == reg query for {label}: {same}')
        census(label, value, kind)

    print('\n== 3. Windows APIs reachable from Python (no call made)')
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    print(f'  SendMessageTimeoutW present: {hasattr(user32, "SendMessageTimeoutW")}')
    print(f'  winreg.SetValueEx present: {hasattr(winreg, "SetValueEx")}')

    print('\n== 2. How claude.exe touches PATH (read-only byte search)')
    exe = os.path.expanduser(r'~\.local\bin\claude.exe')
    data = open(exe, 'rb').read()
    needles = [b'HKCU\\Environment', b'HKEY_CURRENT_USER\\Environment', b'setx', b'SetEnvironmentVariable',
               b'WM_SETTINGCHANGE', b'SendMessageTimeout', b'reg add', b'reg query', b'REG_EXPAND_SZ',
               b"[Environment]::", b'EnvironmentVariableTarget']
    out = []
    for n in needles:
        hits = [m.start() for m in re.finditer(re.escape(n), data)]
        print(f'  {n.decode():32} {len(hits)} hit(s)')
        for h in hits[:6]:
            out.append(f'--- {n.decode()} @ {h}\n' + data[max(0, h - 400):h + 400].decode('utf-8', 'replace'))
    if snippets_path:
        with open(snippets_path, 'w', encoding='utf-8') as f:
            f.write('\n\n'.join(out))
        print(f'  snippets written to {snippets_path}')


if __name__ == '__main__':
    main()
