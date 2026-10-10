"""Probe for dcc-env -h / --help (v0.2.4): run each of the three scripts for real, with
nothing on PATH but a stub dcc-patcher that records its call and exits 1, so neither the
real setup nor a PATH write can happen whatever the scripts do. Prints exit code, the
first output lines, and whether the stub was reached, per shell and argument.

    python tests/one-offs/dcc_env_help_probe_v0.2.4.py
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BIN = Path(__file__).resolve().parents[2] / 'bin'
SYS32 = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32'


def git_bash():
    # Git's own bash, never System32\bash.exe (WSL); git.exe sits in Git\cmd or Git\mingw64\bin
    git = shutil.which('git')
    for folder in Path(git).resolve().parents if git else ():
        if (folder / 'bin' / 'bash.exe').is_file() and (folder / 'usr' / 'bin').is_dir():
            return str(folder / 'bin' / 'bash.exe')
    return shutil.which('bash') if sys.platform != 'win32' else None


def run(argv, stub_dir, marker):
    env = {k: v for k, v in os.environ.items() if k.upper() not in ('PATH', 'DCC_MODE')}
    env['PATH'] = os.pathsep.join([str(stub_dir), str(SYS32), str(SYS32 / 'WindowsPowerShell' / 'v1.0')])
    env['DCC_STUB_MARKER'] = str(marker)
    p = subprocess.run(argv, env=env, capture_output=True, text=True, timeout=60)
    return p.returncode, p.stdout, p.stderr


def main():
    tmp = Path(tempfile.mkdtemp(prefix='dcc-env-help-'))
    stub = tmp / 'stub'
    stub.mkdir()
    (stub / 'dcc-patcher.cmd').write_text('@echo off\r\necho %* >> "%DCC_STUB_MARKER%"\r\nexit /b 1\r\n')
    (stub / 'dcc-patcher').write_text('#!/bin/sh\necho "$@" >> "$DCC_STUB_MARKER"\nexit 1\n')
    shells = {
        'cmd': lambda a: [str(SYS32 / 'cmd.exe'), '/d', '/c', str(BIN / 'dcc-env.cmd'), *a],
        'powershell': lambda a: [str(SYS32 / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe'), '-NoProfile',
                                 '-ExecutionPolicy', 'Bypass', '-File', str(BIN / 'dcc-env.ps1'), *a],
    }
    bash = git_bash()
    if bash:
        script = (BIN / 'dcc-env').as_posix()
        shells['sh'] = lambda a: [bash, '--noprofile', '--norc', '-c', f'. "{script}" "$@"; echo "[status=$?]"', 'x', *a]
    for name, mk in shells.items():
        for args in (['-h'], ['--help'], ['/?'], ['-x'], ['stock'], []):
            if args == ['/?'] and name != 'cmd':
                continue
            marker = tmp / f'{name}-{"_".join(args) or "none"}.log'.replace('/', 'slash').replace('?', 'q')
            code, out, err = run(mk(args), stub, marker)
            first = (out.strip().splitlines() or [''])[0]
            print(f'{name:10} {" ".join(args) or "(none)":7} exit={code} stub_called={marker.exists()} '
                  f'out[0]={first!r} err={err.strip()[:90]!r}')
    print(f'\nscratch: {tmp}')


if __name__ == '__main__':
    sys.exit(main())
