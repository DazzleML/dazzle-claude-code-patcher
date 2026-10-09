"""Check dcc_patcher.regfile against the real reg.exe (v0.1.11), on a scratch key.

Prediction: a file `regfile.dumps` writes, `reg import`ed, stores exactly the value
and type it was given, for djdarcy's real user PATH (REG_SZ) and system PATH
(REG_EXPAND_SZ with %SystemRoot%); and `regfile.loads` reads reg.exe's own
`reg export` of that value back to the same thing.
Control: a file whose hex(2) bytes are cut short must NOT read back the same.

Rule 1b: only HKCU\\Software\\dazzle-claude-code-patcher-poc is written, with value
names PathCopy*; the key is deleted at the end. The real Path is only read.

    python -P tests/one-offs/thinking/user-path-editor/regfile_roundtrip.py <scratch folder>
"""
import subprocess
import sys
import winreg
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from dcc_patcher import regfile, winpath  # noqa: E402

KEY = r'Software\dazzle-claude-code-patcher-poc'
FULL = rf'HKEY_CURRENT_USER\{KEY}'


def raw(hive, key, name):
    with winreg.OpenKey(hive, key, 0, winreg.KEY_READ) as k:
        return winreg.QueryValueEx(k, name)


def main():
    folder = Path(sys.argv[1])
    folder.mkdir(parents=True, exist_ok=True)
    cases = {'PathCopyUser': raw(winreg.HKEY_CURRENT_USER, 'Environment', 'Path'),
             'PathCopySystem': raw(winreg.HKEY_LOCAL_MACHINE,
                                   r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment', 'Path')}
    ok = True
    try:
        for name, (value, kind) in cases.items():
            assert name.lower() != 'path'
            ours = folder / f'{name}.reg'
            ours.write_bytes(regfile.dumps(winpath.USER, value, kind, name=name, key=FULL))
            r = subprocess.run(['reg', 'import', str(ours)], capture_output=True, text=True)
            got = raw(winreg.HKEY_CURRENT_USER, KEY, name)
            same = r.returncode == 0 and got == (value, kind)
            exported = folder / f'{name}.export.reg'
            subprocess.run(['reg', 'export', FULL, str(exported), '/y'], capture_output=True)
            parsed = regfile.loads(exported.read_bytes(), name=name, key=FULL)
            back = parsed[1:] == (value, kind)
            print(f'[{"ok" if same and back else "XX"}] {name}: {len(value)} chars, type {kind}; '
                  f'reg import stored it exactly={same}; loads(reg export)={back}')
            ok &= same and back
        # control: a truncated hex(2) value must not read back as the original
        value, kind = cases['PathCopySystem']
        data = regfile.dumps(winpath.USER, value, kind, name='PathCopySystem', key=FULL).decode('utf-16')
        cut = data.replace(',\\\r\n', ',\\\r\n', 1)
        cut = cut[:cut.rfind(',', 0, len(cut) - 40)] + '\r\n\r\n'
        try:
            broken = regfile.loads(('﻿' + cut.lstrip('﻿')).encode('utf-16-le'), name='PathCopySystem',
                                   key=FULL)[1:] != (value, kind)
        except Exception:
            broken = True
        print(f'[{"ok" if broken else "XX"}] CONTROL truncated file does not read back as the original: {broken}')
        ok &= broken
    finally:
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, KEY)
        except FileNotFoundError:
            pass
        print('cleanup: scratch key removed;',
              'real user Path unchanged:', raw(winreg.HKEY_CURRENT_USER, 'Environment', 'Path') == cases['PathCopyUser'])
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
