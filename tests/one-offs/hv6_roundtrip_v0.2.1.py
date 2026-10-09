"""HV.6 of the v0.2.1 checklist, live: `dcc-patcher uninstall-shim`, then `dcc-env` to put
everything back, with the user PATH compared byte for byte (value and registry type)
before and after, and the shim folders listed at each step.

    python tests/one-offs/hv6_roundtrip_v0.2.1.py

Safety: before anything is written, HKCU\\Environment and the system Environment key
are exported with reg.exe to the session scratchpad (printed), on top of the .reg
backup the tool itself writes into <builds>\\backups before each PATH change. The
shells run with the Start-menu environment (registry PATH), and DCC_YES=1 so the
non-interactive dcc-env may change PATH.
"""
import os
import re
import subprocess
import sys
import winreg
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dcc_patcher import builds                                          # noqa: E402

SCRATCH = Path(os.environ['LOCALAPPDATA']) / 'Temp' / 'claude' / 'hv6-backups'
HOME_BIN = Path.home() / 'bin'
BIN = builds.builds_dir() / 'bin'


def user_path():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as k:
        return winreg.QueryValueEx(k, 'Path')


def registry_path() -> str:
    parts = []
    for root, key in ((winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'),
                      (winreg.HKEY_CURRENT_USER, r'Environment')):
        with winreg.OpenKey(root, key) as k:
            value, _ = winreg.QueryValueEx(k, 'Path')
        parts += [os.path.expandvars(p) for p in value.split(';') if p]
    return ';'.join(parts)


def run(cmd, env):
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=300, cwd=str(ROOT))
    return re.sub(r'\x1b\[[0-9;]*m', '', r.stdout + r.stderr), r.returncode


def listing(folder: Path):
    return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else None


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y-%m-%d__%H-%M-%S')
    for name, key in (('hkcu-environment', r'HKCU\Environment'),
                      ('hklm-environment', r'HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment')):
        out = SCRATCH / f'{stamp}__{name}.reg'
        subprocess.run(['reg', 'export', key, str(out), '/y'], check=True, capture_output=True)
        print(f'backup: {out} ({out.stat().st_size} bytes)')

    env = {k: v for k, v in os.environ.items() if k.upper() not in ('DCC_MODE', 'DCC_ENV')}
    env['PATH'] = registry_path()
    env['DCC_YES'] = '1'

    before = user_path()
    print(f'\nuser PATH before: type {before[1]}, {len(before[0])} chars, {len(before[0].split(";"))} entries')
    print('~/bin before:', listing(HOME_BIN))
    print('bin before:  ', listing(BIN))

    print('\n=== dcc-patcher uninstall-shim')
    out, code = run(['dcc-patcher', 'uninstall-shim'], env)
    print(out.rstrip(), f'\n(exit {code})')
    mid = user_path()
    print(f'user PATH after uninstall: type {mid[1]}, {len(mid[0].split(";"))} entries; '
          f'shim entry present: {str(BIN).lower() in mid[0].lower()}')
    print('~/bin after uninstall:', listing(HOME_BIN))
    print('bin after uninstall:  ', listing(BIN))

    print('\n=== dcc-env (cmd, Start-menu environment, DCC_YES=1)')
    out, code = run(['cmd', '/c', 'call', str(ROOT / 'bin' / 'dcc-env.cmd')], env)   # separate argv: no quoting games
    print(out.rstrip(), f'\n(exit {code})')
    after = user_path()
    print(f'user PATH after dcc-env: type {after[1]}, {len(after[0].split(";"))} entries')
    print('~/bin after:', listing(HOME_BIN))
    print('bin after:  ', listing(BIN))

    print('\n===== RESULT')
    # the run of 2026-10-09 06:30: uninstall removed the entry and ~/bin (ours, created by install);
    # dcc-env wrote the six shims back and re-added the entry; the value matched the tool's own
    # pre-uninstall backup byte for byte (regfile.loads returns (name, value, kind)), type REG_SZ
    print('user PATH value identical:', after[0] == before[0])
    print('user PATH type identical: ', after[1] == before[1])
    print('~/bin identical:          ', listing(HOME_BIN) == ['claude', 'claude-stock', 'dazzle-claude'])
    print('bin identical:            ', listing(BIN) == ['claude-stock.cmd', 'claude.cmd', 'dazzle-claude.cmd'])
    backups = sorted((builds.builds_dir() / 'backups').glob('*.reg'))[-2:]
    print("tool's own backups this run:", [b.name for b in backups])


if __name__ == '__main__':
    main()
