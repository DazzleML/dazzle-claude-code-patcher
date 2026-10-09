"""PATH and `status` (#9), on a fake registry: the tool owns one entry and
changes nothing else; uninstall removes only that entry and keeps what others
added; the system PATH is written only when a system `claude` would win and the
shell is elevated; `status` names a shell that predates the install.

Rule 1b: conftest's autouse fixture makes the real registry and the broadcast
raise; these tests replace them with `Fake` and a recorder, and HOME, the
builds folder and every PATH folder are under tmp_path."""
import os
import sys
from pathlib import Path

import pytest

from dcc_patcher import builds, install, resolve, winpath
from dcc_patcher.cli import main

pytestmark = pytest.mark.skipif(sys.platform != 'win32', reason='the registry PATH is Windows-only')


class Fake:
    def __init__(self, user, system, user_type=winpath.REG_SZ):
        self.values = {winpath.USER: (user, user_type), winpath.SYSTEM: (system, winpath.REG_EXPAND_SZ)}
        self.writes = []

    def read(self, scope):
        return self.values[scope]

    def write(self, scope, value, kind):
        self.writes.append(scope)
        self.values[scope] = (value, kind)


@pytest.fixture
def machine(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    official = home / '.local' / 'bin' / 'claude.exe'
    official.parent.mkdir(parents=True)
    official.write_bytes(b'stock')
    sysdir = tmp_path / 'Windows'
    sysdir.mkdir()
    for var in ('HOME', 'USERPROFILE'):
        monkeypatch.setenv(var, str(home))
    monkeypatch.setenv('DCC_BUILDS_DIR', str(tmp_path / 'builds'))
    monkeypatch.setenv('ProgramFiles', str(tmp_path / 'ProgramFiles'))
    monkeypatch.delenv('CLAUDE_CONFIG_DIR', raising=False)
    monkeypatch.delenv('DCC_YES', raising=False)
    monkeypatch.setattr(builds, 'REPO', tmp_path / 'repo')
    user = rf'C:\tools;%USERPROFILE%\x;{official.parent};;C:\later'
    reg = Fake(user, rf'%SystemRoot%\system32;{sysdir}')
    sent = []
    monkeypatch.setattr(winpath, 'registry', lambda: reg)
    monkeypatch.setattr(winpath, 'broadcast', lambda: sent.append(1) or True)
    monkeypatch.setattr(install, 'detect_shell', lambda: 'powershell')
    monkeypatch.setenv('PATH', f'{sysdir};{official.parent}')       # a shell from before the install
    return reg, official, tmp_path / 'builds' / 'bin', sysdir, sent


def test_install_adds_only_our_entry_before_the_official_folder_and_keeps_the_type(machine, capsys):
    # CONSEQUENCE: 9 -- damaging the user's PATH
    reg, official, bin_, _, sent = machine
    before = reg.values[winpath.USER][0]
    assert main(['install-shim', '--yes']) == 0
    after, kind = reg.values[winpath.USER]
    assert kind == winpath.REG_SZ and '%USERPROFILE%' in after
    assert after == before.replace(str(official.parent), f'{bin_};{official.parent}')
    assert reg.writes == [winpath.USER] and sent
    out = capsys.readouterr().out
    assert 'this shell started before the change' in out
    assert 'dcc-patcher shellenv powershell | Invoke-Expression' in out    # no dcc-env here; scripts blocked
    assert install.load_records()['base_path_user']['value'] == before


def test_uninstall_removes_only_our_entry_and_keeps_what_others_added_since(machine):
    # CONSEQUENCE: 9 -- restoring a saved PATH would delete other installers' entries
    reg, *_ = machine
    before = reg.values[winpath.USER][0]
    main(['install-shim', '--yes'])
    value, kind = reg.values[winpath.USER]
    reg.values[winpath.USER] = (value + r';C:\another-installer', kind)
    assert main(['uninstall-shim']) == 0
    assert reg.values[winpath.USER] == (before + r';C:\another-installer', winpath.REG_SZ)
    reg.writes.clear()
    assert main(['uninstall-shim']) == 0 and reg.writes == []          # already gone: nothing written


def test_a_path_changed_underneath_is_refused_and_not_overwritten(machine, monkeypatch, capsys):
    # CONSEQUENCE: 8 -- overwriting another installer's simultaneous change
    reg, *_ = machine
    insert = winpath.insert_before

    def racing(value, entry, anchor):         # another installer writes after we read, before we write
        user, kind = reg.values[winpath.USER]
        reg.values[winpath.USER] = (user + r';C:\raced', kind)
        return insert(value, entry, anchor)
    monkeypatch.setattr(winpath, 'insert_before', racing)
    assert main(['install-shim', '--yes']) == 1
    assert reg.writes == [] and 'changed while dcc-patcher was working' in capsys.readouterr().err


def test_without_yes_in_a_script_path_is_left_alone(machine, capsys):
    # CONSEQUENCE: 6 -- PATH changed by an unattended run nobody confirmed
    reg, *_ = machine
    assert main(['install-shim']) == 0
    assert reg.writes == [] and 'install-shim --yes' in capsys.readouterr().out


@pytest.mark.parametrize('elevated, expect_system', [(False, False), (True, True)])
def test_a_system_claude_is_overtaken_only_when_elevated_and_via_the_admin_folder(machine, monkeypatch, elevated,
                                                                              expect_system, capsys):
    # CONSEQUENCE: 8 -- a system claude always winning, or a user folder in the system PATH
    reg, official, bin_, sysdir, _ = machine
    (sysdir / 'claude.exe').write_bytes(b'system')
    monkeypatch.setattr(winpath, 'is_elevated', lambda: elevated)
    code = main(['install-shim', '--yes'])
    system = reg.values[winpath.SYSTEM][0]
    admin = install.admin_bin()
    assert (winpath.SYSTEM in reg.writes) == expect_system and str(bin_) not in system
    if expect_system:
        assert code == 0 and system.split(';').index(str(admin)) == system.split(';').index(str(sysdir)) - 1
        assert (admin / 'claude.cmd').is_file()
    else:
        assert code == 1 and 'elevated shell' in capsys.readouterr().out


def test_no_system_claude_means_no_system_write_even_when_elevated(machine, monkeypatch):
    # CONSEQUENCE: 7 -- touching the system PATH with no reason to
    reg, *_ = machine
    monkeypatch.setattr(winpath, 'is_elevated', lambda: True)
    main(['install-shim', '--yes'])
    assert winpath.SYSTEM not in reg.writes


def test_status_names_the_stock_claude_then_the_stale_shell_then_all_clear(machine, monkeypatch, capsys):
    # CONSEQUENCE: 6 -- a shell quietly running stock with nothing saying why
    reg, official, bin_, sysdir, _ = machine
    assert main(['status']) == 1
    out = capsys.readouterr().out
    assert f'claude -> {official}\n' in out and '(stock Claude Code)' in out and 'user PATH does not have' in out
    assert out.startswith('This shell\n') and '\n\nPATH\n' in out and '\n\nLauncher\n' in out   # groups apart
    main(['install-shim', '--yes'])
    capsys.readouterr()
    assert main(['status']) == 1
    out = capsys.readouterr().out
    assert '(stock: this shell started before the PATH change)' in out and '-> dcc-patcher install-shim' not in out
    monkeypatch.setenv('PATH', f'{sysdir};{bin_};{official.parent}')
    main(['status'])
    out = capsys.readouterr().out
    assert f'claude -> {bin_ / "claude.cmd"}\n' in out and '(the dcc-patcher shim' in out and 'started before' not in out


def test_resolution_follows_path_order_then_pathext_order(tmp_path):
    # CONSEQUENCE: 5 -- status naming the wrong file as the one that runs
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir(), b.mkdir()
    (a / 'claude.cmd').write_text('')
    (a / 'claude').write_text('')                    # extensionless: cmd and PowerShell skip it
    (b / 'claude.exe').write_text('')
    (a / 'claude.exe').write_text('')
    found = resolve.candidates('claude', f'{a};{b}', '.COM;.EXE;.BAT;.CMD')
    assert found == [a / 'claude.exe', a / 'claude.cmd', b / 'claude.exe']
    assert resolve.candidates('claude', f'{a};{b}', posix=True)[0] == a / 'claude'
