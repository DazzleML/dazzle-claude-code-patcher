"""The switch (v0.2.1): what `claude` runs in THIS shell versus the persistent choice.

`dcc-env stock | patched | <build>` sets DCC_MODE in the shell; `dcc-patcher use` writes
the persistent mode; `status --brief` says which wins and why. The dcc-env scripts'
setup path is checked live (the v0.2.1 checklist); here are the pieces it leans on, and
the scripts' own argument handling (-h/--help, a refused -option), run for real against a
stub dcc-patcher.
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from dcc_patcher import install, launch

BIN = Path(__file__).resolve().parents[1] / 'bin'
SYS32 = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32'


def _git_bash():
    # Git's own bash, never System32\bash.exe (WSL); git.exe sits in Git\cmd or Git\mingw64\bin
    if sys.platform != 'win32':
        return shutil.which('bash')
    git = shutil.which('git')
    for folder in Path(git).resolve().parents if git else ():
        if (folder / 'bin' / 'bash.exe').is_file() and (folder / 'usr' / 'bin').is_dir():
            return str(folder / 'bin' / 'bash.exe')
    return None


def _shell(name):
    if name == 'cmd' and sys.platform == 'win32':
        return lambda a: [str(SYS32 / 'cmd.exe'), '/d', '/c', str(BIN / 'dcc-env.cmd'), *a]
    if name == 'powershell' and sys.platform == 'win32':
        ps = SYS32 / 'WindowsPowerShell' / 'v1.0' / 'powershell.exe'
        return lambda a: [str(ps), '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(BIN / 'dcc-env.ps1'), *a]
    bash = _git_bash() if name == 'sh' else None
    if bash:
        script = (BIN / 'dcc-env').as_posix()
        return lambda a: [bash, '--noprofile', '--norc', '-c', f'. "{script}" "$@"; echo "[status=$?]"', 'x', *a]
    pytest.skip(f'no {name} here')


@pytest.fixture
def stub(tmp_path):
    """PATH holds a stub dcc-patcher (it records the call, exits 1) and the system folder, and
    nothing else: whatever the scripts do, the real setup and its PATH write cannot run."""
    folder = tmp_path / 'stub'
    folder.mkdir()
    # `-V` answers with DCC_STUB_V (read-only, like the real one); anything else is recorded
    (folder / 'dcc-patcher.cmd').write_bytes(b'@echo off\r\nif "%1"=="-V" (echo dcc-patcher %DCC_STUB_V%& exit /b 0)\r\n'
                                             b'echo %* >> "%DCC_STUB_MARKER%"\r\nexit /b 1\r\n')
    (folder / 'dcc-patcher').write_bytes(b'#!/bin/sh\nif [ "$1" = "-V" ]; then echo "dcc-patcher $DCC_STUB_V"; exit 0; fi\n'
                                         b'echo "$@" >> "$DCC_STUB_MARKER"\nexit 1\n')
    marker = tmp_path / 'called.log'
    env = {k: v for k, v in os.environ.items() if k.upper() not in ('PATH', 'DCC_MODE')}
    env['PATH'] = os.pathsep.join([str(folder), str(SYS32), str(SYS32 / 'WindowsPowerShell' / 'v1.0')]
                                  if sys.platform == 'win32' else [str(folder), '/usr/bin', '/bin'])
    env['DCC_STUB_MARKER'] = str(marker)

    def run(argv, version=None):
        from dcc_patcher._version import BASE_VERSION
        p = subprocess.run(argv, env=dict(env, DCC_STUB_V=version or BASE_VERSION),
                           capture_output=True, text=True, timeout=60)
        return p, marker.exists()
    return run


@pytest.mark.parametrize('shell', ['cmd', 'powershell', 'sh'])
@pytest.mark.parametrize('flag', ['-h', '--help'])
def test_dcc_env_help_says_the_choices_and_changes_nothing(shell, flag, stub):
    p, reached = stub(_shell(shell)([flag]))
    assert 'usage:' in p.stdout and 'dcc-env default' in p.stdout and 'dcc-patcher use' in p.stdout
    assert not reached                                   # no setup, no PATH change, no DCC_MODE
    assert p.returncode == 0 and 'unknown' not in p.stderr


@pytest.mark.parametrize('shell', ['cmd', 'powershell', 'sh'])
def test_dcc_env_refuses_an_unknown_option_rather_than_setting_it_as_the_mode(shell, stub):
    # before v0.2.4, `dcc-env --stock` set DCC_MODE=--stock (named and ignored by the launcher)
    p, reached = stub(_shell(shell)(['--stock']))
    assert 'unknown option --stock' in p.stderr and '--help' in p.stderr
    assert not reached
    assert p.returncode == 2 or '[status=2]' in p.stdout    # sh is sourced, so $? carries it


@pytest.mark.parametrize('shell', ['cmd', 'powershell', 'sh'])
@pytest.mark.parametrize('flag', ['-V', '--version'])
def test_dcc_env_version_names_itself_and_dcc_patcher_and_flags_a_mismatch(shell, flag, stub):
    from dcc_patcher._version import BASE_VERSION
    p, reached = stub(_shell(shell)([flag]))
    assert f'dcc-env {BASE_VERSION}' in p.stdout and f'dcc-patcher {BASE_VERSION}' in p.stdout
    assert 'differ' not in p.stdout and not reached and p.returncode == 0
    p, reached = stub(_shell(shell)([flag]), version='0.2.1')        # a stale pairing
    assert 'dcc-patcher 0.2.1' in p.stdout and 'these differ: dcc-patcher update --fix' in p.stdout
    assert not reached                                             # -V sets nothing up


@pytest.mark.parametrize('shell', ['cmd', 'powershell', 'sh'])
def test_dcc_env_still_sets_up_for_a_mode(shell, stub):
    # the guard must not swallow real arguments: `stock` goes on to install-shim (the stub)
    p, reached = stub(_shell(shell)(['stock']))
    assert reached and 'usage:' not in p.stdout


@pytest.fixture
def state():
    return {'mode': 'patched', 'current': 'claude-dcc-2.1.295+dcc0.2.1.exe', 'official': 'x'}


def test_the_brief_line_says_which_choice_wins_and_why(state, monkeypatch):
    monkeypatch.delenv('DCC_MODE', raising=False)
    assert install._runs(state) == 'claude-dcc-2.1.295+dcc0.2.1.exe (persistent: dcc-patcher use patched)'
    monkeypatch.setenv('DCC_MODE', 'stock')
    assert install._runs(state) == 'stock (this shell: dcc-env stock; persistent: patched)'
    monkeypatch.setenv('DCC_MODE', 'patched')
    state['mode'] = 'stock'
    assert install._runs(state) == 'claude-dcc-2.1.295+dcc0.2.1.exe (this shell: dcc-env patched; persistent: stock)'


def test_a_build_name_in_dcc_mode_pins_it_for_the_shell(state, monkeypatch, tmp_path):
    monkeypatch.setattr(launch.builds, 'builds_dir', lambda: tmp_path)
    (tmp_path / 'claude-dcc-2.1.290+dcc0.1.9.exe').write_bytes(b'x')
    monkeypatch.setenv('DCC_MODE', 'claude-dcc-2.1.290+dcc0.1.9.exe')
    assert launch.valid_mode('claude-dcc-2.1.290+dcc0.1.9.exe')
    assert install._runs(state) == ('the pinned build claude-dcc-2.1.290+dcc0.1.9.exe '
                                    '(this shell: dcc-env claude-dcc-2.1.290+dcc0.1.9.exe; persistent: patched)')


def test_a_wrong_word_in_dcc_mode_is_named_and_ignored(state, monkeypatch, tmp_path):
    monkeypatch.setattr(launch.builds, 'builds_dir', lambda: tmp_path)
    monkeypatch.setenv('DCC_MODE', 'stok')
    assert not launch.valid_mode('stok')
    assert install._runs(state) == ('claude-dcc-2.1.295+dcc0.2.1.exe; this shell\'s DCC_MODE=stok is not stock, '
                                    'patched or a build and is ignored')


def test_an_install_without_the_new_names_is_not_set_up(tmp_path, monkeypatch):
    # so `dcc-env` (install-shim --if-needed) migrates a v0.2.0 layout: claude + claude-stock only
    monkeypatch.setattr(install.sys, 'platform', 'linux')      # the PATH half of is_set_up is Windows-only
    folder = tmp_path / 'bin'
    folder.mkdir()
    for name in ('claude', 'claude-stock'):
        (folder / name).write_bytes(b'#!/bin/sh\n')
    assert not install.is_set_up(folder, str(tmp_path / 'claude'))
    for name in ('claude-stock', 'dazzle-claude'):
        (folder / name).write_bytes(b'#!/bin/sh\n')
    assert install.is_set_up(folder, str(tmp_path / 'claude'))


@pytest.mark.skipif(install.sys.platform != 'win32', reason='a Windows PATH question')
def test_a_shell_that_inherited_tilde_bin_ahead_of_the_shims_is_flagged(monkeypatch, tmp_path):
    # seen live 2026-10-09: a PowerShell opened from Git Bash had ~/bin first, resolved `claude-stock`
    # to the extensionless sh script, and Windows asked "How do you want to open this file?"
    posix = tmp_path / 'home' / 'bin'
    entry = str(tmp_path / 'builds' / 'bin')
    monkeypatch.setattr(install.builds, 'posix_shim_dir', lambda: posix)
    ahead = f'{posix};{entry};C:\\Windows'
    behind = f'{entry};{posix};C:\\Windows'
    without = f'{posix};C:\\Windows'
    assert install.posix_dir_ahead(ahead, entry, 'powershell')
    assert install.posix_dir_ahead(ahead, entry, 'cmd')
    assert install.posix_dir_ahead(without, entry, 'powershell')         # ~/bin there, the shims not at all
    assert not install.posix_dir_ahead(behind, entry, 'powershell')      # dcc-env's prepend fixes it
    assert not install.posix_dir_ahead(ahead, entry, 'sh')               # Git Bash: ~/bin first is right
    assert not install.posix_dir_ahead(f'{entry};C:\\Windows', entry, 'powershell')


@pytest.mark.skipif(install.sys.platform != 'win32', reason='a Windows PATH question')
def test_dcc_env_prepends_the_shims_when_tilde_bin_was_inherited_ahead_of_them(monkeypatch, tmp_path):
    # dcc-env asks `shellenv --folder`; '' means "nothing to do". Ahead of the official folder is
    # not enough when ~/bin sits in front: the prepend is what makes claude-stock resolve to the .cmd
    posix = tmp_path / 'home' / 'bin'
    entry = str(tmp_path / 'builds' / 'bin')
    official = tmp_path / '.local' / 'bin'
    monkeypatch.setattr(install.builds, 'posix_shim_dir', lambda: posix)
    monkeypatch.setattr(install, 'load_records', lambda: {'entry': entry})
    monkeypatch.setattr(launch, 'load_state', lambda: {'official': str(official / 'claude.exe')})
    monkeypatch.setenv('PATH', f'{posix};{entry};{official};C:\\Windows')
    assert install.shell_folder(False) == entry                          # cmd / PowerShell: prepend
    assert install.shell_folder(True) == ''                              # Git Bash: ~/bin is already first
    monkeypatch.setenv('PATH', f'{entry};{posix};{official};C:\\Windows')
    assert install.shell_folder(False) == ''                             # nothing to do
