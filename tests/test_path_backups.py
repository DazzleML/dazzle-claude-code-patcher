"""PATH backups, restore-path, dcc-env's helpers and status colour (#9, v0.1.11),
on the fake registry from test_path.py. A backup is written before every PATH
write and holds only Path; restore-path shows what changes, saves the current
value first, and writes the backup's value and type back.

Rule 1b: conftest makes the real registry and the broadcast raise; the `machine`
fixture swaps in a fake, and everything on disk is under tmp_path."""
import os
import sys

import pytest

from dcc_patcher import builds, install, regfile, style, winpath
from dcc_patcher.cli import main
from tests.test_path import Fake, machine  # noqa: F401  (the fixture)

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='the registry PATH is Windows-only')


@pytest.mark.parametrize('kind, value', [(winpath.REG_SZ, r'C:\a "quoted";C:\b'),
                                         (winpath.REG_EXPAND_SZ, r'%SystemRoot%\system32;' + 'C:\\long\\' * 40)])
def test_a_reg_backup_reads_back_as_the_same_value_and_type(kind, value):
    # CONSEQUENCE: 8 -- a backup that restores something other than what was saved
    data = regfile.dumps(winpath.USER, value, kind)
    assert data.startswith('\ufeff'.encode('utf-16-le')) and b'\r\x00\n\x00' in data
    assert regfile.loads(data) == (winpath.USER, value, kind)


def test_install_saves_the_path_first_under_a_dated_name(machine, capsys):
    # CONSEQUENCE: 7 -- a PATH change with no one-command way back
    reg, *_ = machine
    before = reg.values[winpath.USER]
    main(['install-shim', '--yes'])
    (saved,) = install.backups(winpath.USER)
    assert saved.name.endswith('__path-user__before-install-shim__no-build.reg')
    assert saved.name[:20].count('-') == 4 and saved.name[10:12] == '__'      # YYYY-MM-DD__hh-mm-ss
    assert regfile.loads(saved.read_bytes()) == (winpath.USER, *before)
    assert f'saved the user PATH first: {saved}' in capsys.readouterr().out


def test_restore_path_puts_the_backup_back_after_saving_the_current_value(machine, capsys):
    # CONSEQUENCE: 8 -- undoing a bad PATH change, with the undo itself undoable
    reg, *_ = machine
    original = reg.values[winpath.USER]
    main(['install-shim', '--yes'])
    reg.values[winpath.USER] = (r'C:\something-broke', winpath.REG_EXPAND_SZ)
    capsys.readouterr()
    assert main(['restore-path', '--yes']) == 0
    assert reg.values[winpath.USER] == original
    out = capsys.readouterr().out
    assert r'  + C:\tools' in out and r'  - C:\something-broke' in out and 'type REG_EXPAND_SZ -> REG_SZ' in out
    newest = install.backups(winpath.USER)[-1]
    assert '__before-restore-path__' in newest.name
    assert regfile.loads(newest.read_bytes())[1] == r'C:\something-broke'


def test_a_system_backup_is_not_restored_without_elevation(machine, capsys):
    # CONSEQUENCE: 6 -- a confusing failure halfway through a system write
    reg, *_ = machine
    path = builds.builds_dir() / 'backups' / 'sys.reg'
    path.parent.mkdir(parents=True)
    path.write_bytes(regfile.dumps(winpath.SYSTEM, r'C:\x', winpath.REG_EXPAND_SZ))
    reg.writes.clear()
    assert main(['restore-path', str(path), '--yes']) == 1
    assert reg.writes == [] and 'elevated shell' in capsys.readouterr().err


def test_dcc_env_helpers_add_the_folder_only_when_this_shell_lacks_it(machine, monkeypatch, capsys, tmp_path):
    # CONSEQUENCE: 6 -- dcc-env adding the folder twice, or not at all
    reg, official, bin_, sysdir, _ = machine
    main(['install-shim', '--yes'])
    capsys.readouterr()
    assert main(['install-shim', '--yes', '--if-needed']) == 0 and capsys.readouterr().out == ''
    (bin_ / 'claude').write_bytes(b'#!/bin/sh\n# Written by dcc-patcher install-shim: v0.1.10 left me here\n')
    assert main(['install-shim', '--yes', '--if-needed']) == 0          # not "set up": the old layout
    assert not (bin_ / 'claude').exists() and 'removed' in capsys.readouterr().out
    main(['shellenv', 'cmd', '--folder'])
    assert capsys.readouterr().out.strip() == str(bin_)
    monkeypatch.setenv('PATH', f'{bin_};{official.parent}')
    main(['shellenv', 'cmd', '--folder'])
    assert capsys.readouterr().out == ''


def test_the_catch_up_command_is_dcc_env_when_it_is_installed(machine, monkeypatch, tmp_path):
    # CONSEQUENCE: 5 -- a stale shell told to paste a long line when one word would do
    reg, official, bin_, *_ = machine
    scripts = tmp_path / 'Scripts'
    scripts.mkdir()
    (scripts / 'dcc-env.cmd').write_text('')
    monkeypatch.setenv('PATH', f'{scripts};{official.parent}')
    assert install.catch_up(str(bin_), 'cmd') == 'dcc-env'
    assert install.catch_up(str(bin_), 'powershell') == 'dcc-patcher shellenv powershell | Invoke-Expression'
    monkeypatch.setattr(install, 'ps_scripts_allowed', lambda: True)
    assert install.catch_up(str(bin_), 'powershell') == 'dcc-env'


def test_tilde_bin_is_a_hazard_on_the_windows_path_but_not_on_git_bashs_own(machine, monkeypatch, capsys):
    # CONSEQUENCE: 5 -- a false alarm in every Git Bash shell, or no alarm where Windows can pick the sh script
    reg, official, bin_, sysdir, _ = machine
    home_bin = str(official.parent.parent.parent / 'bin')
    monkeypatch.setenv('PATH', f'{home_bin};{sysdir};{official.parent}')        # what Git Bash hands Python
    main(['status'])
    assert 'is on the Windows PATH' not in capsys.readouterr().out
    user, kind = reg.values[winpath.USER]
    reg.values[winpath.USER] = (f'{home_bin};{user}', kind)
    main(['status'])
    assert f'{home_bin} is on the Windows PATH' in capsys.readouterr().out


def _environment(reg, home):
    """Everything install-shim may touch outside the builds folder, as a comparable value."""
    def tree(folder):
        return sorted((str(p.relative_to(folder)), p.read_bytes() if p.is_file() else None)
                      for p in folder.rglob('*')) if folder.exists() else None
    return {'registry': dict(reg.values), 'home bin': tree(home / 'bin'),
            'program files': tree(install.admin_bin().parent.parent)}


@pytest.mark.parametrize('scenario', ['no ~/bin yet', '~/bin with the user\'s own files', 'system claude, elevated'])
def test_uninstall_after_install_leaves_everything_outside_the_builds_folder_as_it_was(machine, monkeypatch,
                                                                                      scenario):
    # CONSEQUENCE: 9 -- after uninstall, Git Bash (or the system PATH) still running our shim, or user files lost
    reg, official, bin_, sysdir, _ = machine
    home = official.parent.parent.parent
    if scenario == '~/bin with the user\'s own files':
        (home / 'bin').mkdir()
        (home / 'bin' / 'notes.txt').write_bytes(b'mine')
        (home / 'bin' / 'claude-stock').write_bytes(b'#!/bin/sh\n# my own wrapper\n')
    if scenario == 'system claude, elevated':
        (sysdir / 'claude.exe').write_bytes(b'system')
        monkeypatch.setattr(winpath, 'is_elevated', lambda: True)
        install.admin_bin().parent.parent.mkdir(parents=True)          # Program Files itself exists
    before = _environment(reg, home)
    assert main(['install-shim', '--yes']) == 0
    assert _environment(reg, home) != before                           # it did change something
    assert (home / 'bin' / 'claude').is_file()
    assert main(['uninstall-shim']) == 0
    assert _environment(reg, home) == before


def test_status_is_coloured_only_on_a_terminal_and_never_with_no_color(machine, monkeypatch, capsys):
    # CONSEQUENCE: 3 -- escape codes in a pipe, or colour someone turned off
    reg, official, *_ = machine
    plain = (main(['status']), capsys.readouterr().out)[1]
    assert '\033[' not in plain and '\x01' not in plain and '\x02' not in plain     # no marks leak
    real_enabled = style.enabled
    monkeypatch.setattr(style, 'enabled', lambda stream=None: True)
    main(['status'])
    out = capsys.readouterr().out
    assert '\033[33m[ ] claude' in out and '\033[1mThis shell' in out and '\033[36mdcc-patcher install-shim' in out
    assert f'\033[93m{official}\033[0m\033[33m' in out          # the path brighter than its yellow line

    class Tty:
        def isatty(self):
            return True
    monkeypatch.setattr(style, 'enabled', real_enabled)        # not undo(): that would drop the registry guard
    monkeypatch.setattr(style, '_enable_windows_vt', lambda stream: True)
    style._ready.clear()
    assert style.enabled(Tty())
    monkeypatch.setenv('NO_COLOR', '1')
    assert not style.enabled(Tty())
