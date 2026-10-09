"""Run the v0.2.1 switch checklist (HV.1 to HV.5) in shells that have a Start-menu
environment: the registry PATH (system, then user), nothing inherited from the shell
that runs this script. That is the difference between a window djdarcy opens and the
Git-Bash-descended shells a Claude Code session can spawn (~/bin first on PATH).

    python tests/one-offs/startmenu_shells_v0.2.1.py

Prints each shell's raw output, then a PASS/FAIL table. Nothing here changes the
persistent state: every leg ends with `dcc-env default`, and DCC_MODE lives only in
the child process. HV.6 (uninstall-shim, which writes the user PATH) is deliberately
not included; it is covered by tests/test_path_backups.py and was run live on v0.1.11.
"""
import os
import re
import subprocess
import sys
import tempfile
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / 'bin'
PINNED = 'claude-dcc-2.1.294+dcc0.1.10.exe'
STOCK = re.compile(r'^\d+\.\d+\.\d+ \(Claude Code\)$', re.M)
DAZZLE = re.compile(r'^\d+\.\d+\.\d+ \+ dcc [\d.]+ \(Dazzle Claude Code\)$', re.M)


def registry_path() -> str:
    parts = []
    for root, key in ((winreg.HKEY_LOCAL_MACHINE, r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'),
                      (winreg.HKEY_CURRENT_USER, r'Environment')):
        with winreg.OpenKey(root, key) as k:
            value, _ = winreg.QueryValueEx(k, 'Path')
        parts += [os.path.expandvars(p) for p in value.split(';') if p]
    return ';'.join(parts)


def startmenu_env() -> dict:
    env = {k: v for k, v in os.environ.items() if k.upper() not in ('DCC_MODE', 'DCC_ENV')}
    env['PATH'] = registry_path()
    return env


def run(cmd, env, timeout=180) -> str:
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout, cwd=str(ROOT))
    out = r.stdout + r.stderr
    return re.sub(r'\x1b\[[0-9;]*m', '', out)


def strip_wrote(out: str) -> str:
    return '\n'.join(l for l in out.splitlines() if not l.startswith(('wrote ', 'user PATH:')))


def cmd_leg(env):
    script = f'''@echo off
echo === HV1
call "{BIN}\\dcc-env.cmd"
where claude dazzle-claude claude-stock
echo === HV2 stock
call "{BIN}\\dcc-env.cmd" stock
echo DCC_MODE=[%DCC_MODE%]
call claude --version
echo === HV3 explicit under stock
call dazzle-claude --version
call claude-stock --version
echo === HV2 default
call "{BIN}\\dcc-env.cmd" default
echo DCC_MODE=[%DCC_MODE%]
call claude --version
echo === HV5 pin
call "{BIN}\\dcc-env.cmd" {PINNED}
call claude --version
echo === HV5 typo
call "{BIN}\\dcc-env.cmd" stok
call claude --version
call "{BIN}\\dcc-env.cmd" default
'''
    path = Path(tempfile.mkdtemp(prefix='dcc-sm-')) / 'leg.cmd'
    path.write_bytes(script.replace('\n', '\r\n').encode('ascii'))
    return run(['cmd', '/c', str(path)], env)


def ps_leg(env):
    b = str(BIN / 'dcc-env.ps1')
    script = f'''
"=== HV1"; & "{b}"; (Get-Command claude, dazzle-claude, claude-stock -ErrorAction SilentlyContinue).Source
"=== HV2 stock"; & "{b}" stock; "DCC_MODE=[$env:DCC_MODE]"; claude --version
"=== HV3 explicit under stock"; dazzle-claude --version; claude-stock --version
"=== HV2 default"; & "{b}" default; "DCC_MODE=[$env:DCC_MODE]"; claude --version
"=== HV5 pin"; & "{b}" {PINNED}; claude --version
"=== HV5 typo"; & "{b}" stok; claude --version; & "{b}" default
'''
    return run(['powershell', '-NoProfile', '-Command', script], env)


def bash_leg(env):
    bash = r'C:\Program Files\Git\bin\bash.exe'
    b = str(BIN / 'dcc-env').replace('\\', '/')
    script = f'''
echo "=== HV1"; . "{b}"; which -a claude dazzle-claude claude-stock
echo "=== HV2 stock"; . "{b}" stock; echo "DCC_MODE=[$DCC_MODE]"; claude --version
echo "=== HV3 explicit under stock"; dazzle-claude --version; claude-stock --version
echo "=== HV2 default"; . "{b}" default; echo "DCC_MODE=[$DCC_MODE]"; claude --version
echo "=== HV5 pin"; . "{b}" {PINNED}; claude --version
echo "=== HV5 typo"; . "{b}" stok; claude --version; . "{b}" default
'''
    return run([bash, '--login', '-c', script], env)       # --login: /etc/profile, as a Start-menu Git Bash


def new_window(env, shell):
    """HV.4: a fresh process with the Start-menu environment has no DCC_MODE and runs patched."""
    if shell == 'cmd':
        return run(['cmd', '/c', 'echo DCC_MODE=[%DCC_MODE%] && claude --version'], env)
    if shell == 'powershell':
        return run(['powershell', '-NoProfile', '-Command', '"DCC_MODE=[$env:DCC_MODE]"; claude --version'], env)
    return run([r'C:\Program Files\Git\bin\bash.exe', '--login', '-c', 'echo "DCC_MODE=[$DCC_MODE]"; claude --version'], env)


def section(out, name):
    m = re.search(rf'=== {re.escape(name)}\n(.*?)(?=\n=== |\Z)', out, re.S)
    return m.group(1) if m else ''


def judge(shell, out, fresh):
    checks = []
    hv1 = section(out, 'HV1')
    ok1 = all(n in hv1 for n in ('claude', 'dazzle-claude', 'claude-stock')) and '[x] claude ->' in hv1
    checks.append(('HV.1 three names resolve; brief line green', ok1))
    s = section(out, 'HV2 stock')
    checks.append(('HV.2 stock: version is stock, DCC_MODE=stock, line says why',
                   bool(STOCK.search(s)) and 'DCC_MODE=[stock]' in s and 'this shell: dcc-env stock' in s))
    e = section(out, 'HV3 explicit under stock')
    checks.append(('HV.3 dazzle-claude patched / claude-stock stock, under stock',
                   bool(DAZZLE.search(e)) and bool(STOCK.search(e))))
    d = section(out, 'HV2 default')
    checks.append(('HV.2 default: patched again, DCC_MODE empty',
                   bool(DAZZLE.search(d)) and 'DCC_MODE=[]' in d and 'persistent: dcc-patcher use' in d))
    # cmd leaves an undefined %VAR% literal on a command line (it expands to '' only inside a batch file)
    checks.append(('HV.4 new window: no DCC_MODE, patched',
                   ('DCC_MODE=[]' in fresh or 'DCC_MODE=[%DCC_MODE%]' in fresh) and bool(DAZZLE.search(fresh))))
    p = section(out, 'HV5 pin')
    checks.append(('HV.5 pin: the named build runs', '2.1.294 + dcc 0.1.10' in p and f'pinned build {PINNED}' in p))
    t = section(out, 'HV5 typo')
    checks.append(('HV.5 typo: named and ignored, patched runs',
                   'DCC_MODE=stok is not stock, patched or a build' in t and bool(DAZZLE.search(t))))
    return checks


def main():
    env = startmenu_env()
    print('PATH head (registry):', ' ; '.join(env['PATH'].split(';')[:4]), '...')
    print('~/bin on it:', any(p.rstrip('\\').lower().endswith(r'\extreme\bin') for p in env['PATH'].split(';')))
    results = {}
    for shell, leg in (('cmd', cmd_leg), ('powershell', ps_leg), ('git bash (login)', bash_leg)):
        out = leg(env)
        fresh = new_window(env, shell.split()[0] if shell != 'git bash (login)' else 'bash')
        print(f'\n##### {shell}\n{strip_wrote(out)}\n--- new window ---\n{fresh}')
        results[shell] = judge(shell, out, fresh)
    print('\n===== RESULTS')
    for shell, checks in results.items():
        for name, ok in checks:
            print(f'  {"PASS" if ok else "FAIL"}  {shell:18s} {name}')
    print('all passed:', all(ok for c in results.values() for _, ok in c))


if __name__ == '__main__':
    main()
