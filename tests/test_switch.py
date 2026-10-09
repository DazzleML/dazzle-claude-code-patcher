"""The switch (v0.2.1): what `claude` runs in THIS shell versus the persistent choice.

`dcc-env stock | patched | <build>` sets DCC_MODE in the shell; `dcc-patcher use` writes
the persistent mode; `status --brief` says which wins and why. The dcc-env scripts
themselves are shell code and are checked live (the v0.2.1 checklist); here are the
pieces they lean on.
"""
import pytest

from dcc_patcher import install, launch


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
    from dcc_patcher import launch
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
