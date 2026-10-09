"""The launcher (#5), on the scenarios that matter: the first start builds and
runs the patched copy; an unchanged official exe is neither re-hashed nor
rebuilt; an update is rebuilt and switched to; a patch needing a human runs
stock with one line; DCC_MODE, `use`, `rollback` and pinned builds; the test
config never writes; the shims come from two templates.

Rule 1b: `launch._exec` is stubbed for every test (autouse), so nothing is ever
launched. HOME and USERPROFILE point at tmp_path, so "~/.local/bin" and
"~/.claude" are tmp folders, and DCC_BUILDS_DIR, the checkout path and the data
folders are tmp too. The patches folder is a tmp folder holding one test spec."""
import hashlib
import os
from pathlib import Path

import pytest

from dcc_patcher import builds, cli, launch
from tests.bunfixture import make_exe

SPEC = '''
format = 1
id = "T"
title = "test patch"
module_marker = "MARK"
signature = "/*dcc-test*/"
[[edit]]
name = "flag"
pattern = 'keep=!0'
replace = 'keep=!1'
'''


def official_bytes(version='2.1.999', patchable=True):
    body = b'keep=!0;' if patchable else b'keep=gone;'
    return make_exe([b'other();', b'/*MARK*/VERSION:"' + version.encode() + b'";' + body])


def update(official: Path, data: bytes):
    """What the native updater does (measured on 2.1.292): write a staged file,
    then move it into place, so the official exe gets a new file id."""
    staged = official.with_name(official.name + '.new')
    staged.write_bytes(data)
    os.replace(staged, official)


@pytest.fixture
def world(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    official = home / '.local' / 'bin' / ('claude.exe' if os.name == 'nt' else 'claude')
    official.parent.mkdir(parents=True)
    official.write_bytes(official_bytes())
    for var in ('HOME', 'USERPROFILE'):
        monkeypatch.setenv(var, str(home))
    monkeypatch.setenv('DCC_BUILDS_DIR', str(tmp_path / 'builds'))
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'localappdata'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'xdg'))
    for var in ('DCC_MODE', 'CLAUDE_CONFIG_DIR'):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(builds, 'REPO', tmp_path / 'repo')
    patches = tmp_path / 'patches' / 'T'
    patches.mkdir(parents=True)
    (patches / 'patch.toml').write_text(SPEC)
    monkeypatch.setattr(cli, 'PATCHES_DIR', tmp_path / 'patches')
    return official, tmp_path / 'builds', home


@pytest.fixture(autouse=True)
def launched(monkeypatch):
    calls = []
    monkeypatch.setattr(launch, '_exec', lambda exe, args: calls.append((exe, list(args))) or 0)
    return calls


def start(*args):
    return launch.main(list(args))


def test_the_first_start_builds_the_patched_copy_and_runs_it(world, launched, capsys):
    official, builds_dir, _ = world
    assert start('--resume', 'x y') == 0
    build = builds_dir / 'claude-dcc-2.1.999+dcc{}{}'.format(builds.BASE_VERSION, official.suffix)
    assert launched == [(str(build), ['--resume', 'x y'])]
    assert b'keep=!1' in build.read_bytes()
    assert launch.load_state()['current'] == build.name
    assert f'now running {build.name}' in capsys.readouterr().err


def test_an_unchanged_official_exe_is_neither_rehashed_nor_rebuilt(world, launched, monkeypatch, capsys):
    start()
    capsys.readouterr()
    monkeypatch.setattr(hashlib, 'sha256', lambda *a: pytest.fail('re-hashed an unchanged exe'))
    monkeypatch.setattr(launch, 'rebuild', lambda official: pytest.fail('rebuilt an unchanged exe'))
    assert start() == 0
    assert launched[1] == launched[0] and capsys.readouterr().err == ''


def test_after_an_update_the_next_start_builds_and_switches_and_keeps_the_old_build(world, launched):
    official, builds_dir, _ = world
    start()
    update(official, official_bytes('2.1.1000'))
    start()
    new = f'claude-dcc-2.1.1000+dcc{builds.BASE_VERSION}{official.suffix}'
    assert launched[-1][0] == str(builds_dir / new) and launch.load_state()['current'] == new
    assert (builds_dir / f'claude-dcc-2.1.999+dcc{builds.BASE_VERSION}{official.suffix}').exists()


def test_an_update_of_the_same_size_and_mtime_is_still_seen_by_its_new_file_id(world, launched):
    official, builds_dir, _ = world
    start()
    old = os.stat(official)
    update(official, official_bytes('2.1.998'))              # same padded size
    os.utime(official, ns=(old.st_atime_ns, old.st_mtime_ns))
    start()
    assert launched[-1][0] == str(builds_dir / f'claude-dcc-2.1.998+dcc{builds.BASE_VERSION}{official.suffix}')


def test_a_patch_needing_a_human_after_an_update_runs_stock_with_one_line(world, launched, capsys):
    official, _, _ = world
    start()
    update(official, official_bytes('2.1.1000', patchable=False))
    capsys.readouterr()
    assert start() == 0
    assert launched[-1][0] == str(official)
    err = capsys.readouterr().err
    assert err.count('\n') == 1 and 'patch T needs attention' in err and 'running stock' in err
    assert err.startswith('dcc: Claude Code updated; building')


def test_a_rebuild_says_so_before_it_starts_and_finishes_the_same_line(world, launched, monkeypatch, capsys):
    # CONSEQUENCE: 5 -- a silent ~3 s pause on the first start after an update (#9)
    seen = []

    def slow_rebuild(official):
        seen.append(capsys.readouterr().err)        # what was on screen when the build began
        return None, ['T']
    monkeypatch.setattr(launch, 'rebuild', slow_rebuild)
    assert start() == 0
    assert seen[0].startswith('dcc: first start; building') and not seen[0].endswith('\n')
    whole = seen[0] + capsys.readouterr().err
    assert whole.count('\n') == 1 and whole.rstrip().endswith(f'(dcc-patcher check "{world[0]}")')


def test_a_rebuild_also_keeps_the_original_and_the_updaters_old_copies(world, launched):
    # CONSEQUENCE: 7 -- the updater deletes its .old copies after 30 days (#9)
    official, builds_dir, _ = world
    old = official.with_name(official.name + '.old.1790095191038')
    old.write_bytes(official_bytes('2.1.900'))
    before = sorted((p.name, p.stat().st_mtime_ns) for p in official.parent.iterdir())
    start()
    sfx = official.suffix
    assert {p.name for p in builds_dir.glob('claude-cc-*')} == {f'claude-cc-2.1.999{sfx}', f'claude-cc-2.1.900{sfx}'}
    assert (builds_dir / f'claude-cc-2.1.900{sfx}').read_bytes() == old.read_bytes()
    assert sorted((p.name, p.stat().st_mtime_ns) for p in official.parent.iterdir()) == before


def test_a_rebuild_that_crashes_still_starts_stock(world, launched, monkeypatch, capsys):
    official, _, _ = world
    monkeypatch.setattr(cli, 'build', lambda f: 1 / 0)
    assert start() == 0
    assert launched == [(str(official), [])] and 'running stock' in capsys.readouterr().err


def test_dcc_mode_overrides_for_one_shell_and_a_wrong_word_is_named(world, launched, monkeypatch, capsys):
    official, builds_dir, _ = world
    monkeypatch.setenv('DCC_MODE', 'stock')
    start()
    assert launched[-1][0] == str(official)
    monkeypatch.setenv('DCC_MODE', 'vanilla')
    start()
    assert launched[-1][0].startswith(str(builds_dir)) and 'DCC_MODE=vanilla' in capsys.readouterr().err


def test_use_switches_what_the_next_start_runs(world, launched, capsys):
    official, builds_dir, _ = world
    start()
    build = launch.load_state()['current']
    assert cli.main(['use', 'stock']) == 0 and start() == 0
    assert launched[-1][0] == str(official)
    assert cli.main(['use', build]) == 0 and start() == 0
    assert launched[-1][0] == str(builds_dir / build)
    assert cli.main(['use', str(builds_dir / build)]) == 0      # a full path names the same build
    assert launch.load_state()['mode'] == build
    assert cli.main(['use', 'no-such-build.exe']) == 2
    assert cli.main(['use']) == 0 and f'mode:     {build}' in capsys.readouterr().out


def test_rollback_pins_the_build_before_the_current_one(world, launched, capsys):
    official, builds_dir, _ = world
    start()
    old = launch.load_state()['current']
    assert cli.main(['rollback']) == 1                       # nothing older yet
    update(official, official_bytes('2.1.1000'))
    start()
    os.utime(builds_dir / old, ns=(1, 1))                    # older by modification time
    assert cli.main(['rollback']) == 0 and start() == 0
    assert launched[-1][0] == str(builds_dir / old) and launch.load_state()['mode'] == old


def test_rollback_steps_back_one_build_at_a_time(world, launched):
    official, builds_dir, _ = world
    names = []
    for i, version in enumerate(('2.1.997', '2.1.998', '2.1.999')):
        update(official, official_bytes(version))
        start()
        names.append(launch.load_state()['current'])
        os.utime(builds_dir / names[-1], ns=(i + 1, i + 1))
    assert cli.main(['rollback']) == 0 and launch.load_state()['mode'] == names[1]
    assert cli.main(['rollback']) == 0 and launch.load_state()['mode'] == names[0]


def test_a_pinned_build_that_is_gone_runs_stock_and_says_so(world, launched, capsys):
    official, builds_dir, _ = world
    start()
    build = launch.load_state()['current']
    cli.main(['use', build])
    (builds_dir / build).unlink()
    capsys.readouterr()
    start()
    assert launched[-1][0] == str(official) and 'is gone' in capsys.readouterr().err


def test_the_test_config_never_writes_state_or_builds(world, launched, monkeypatch, capsys):
    official, builds_dir, home = world
    start()
    state = (builds_dir / 'launcher.json').read_bytes()
    listing = sorted(p.name for p in builds_dir.iterdir())
    monkeypatch.setenv('CLAUDE_CONFIG_DIR', str(home / 'test-config'))
    update(official, official_bytes('2.1.1000'))
    capsys.readouterr()
    start()
    assert launched[-1][0] == str(official) and 'test config' in capsys.readouterr().err
    assert (builds_dir / 'launcher.json').read_bytes() == state
    assert sorted(p.name for p in builds_dir.iterdir()) == listing


def test_nothing_is_written_into_the_official_folder_or_claude_config(world, launched):
    official, _, home = world
    before = {p.name: p.read_bytes() for p in official.parent.iterdir()}
    start()
    cli.main(['use', 'stock'])
    start()
    assert {p.name: p.read_bytes() for p in official.parent.iterdir()} == before
    assert not (home / '.claude').exists()


def test_no_official_exe_is_one_line_and_exit_127(world, launched, capsys):
    official, _, _ = world
    official.unlink()
    assert start() == 127 and launched == []
    assert 'no Claude Code at' in capsys.readouterr().err.splitlines()[-1]


@pytest.mark.skipif(os.name != 'nt', reason='the .cmd shim is written on Windows only')
def test_install_shim_writes_four_launchers_from_two_templates(world, tmp_path, capsys):
    official, _, home = world
    folder = tmp_path / 'bin'
    # on Windows the sh shims go to ~/bin, never beside the .cmd ones on the Windows PATH (#9)
    sh_folder = home / 'bin' if os.name == 'nt' else folder
    assert cli.main(['install-shim', '--dir', str(folder), '--no-path']) == 0
    if os.name == 'nt':
        assert sorted(p.name for p in folder.iterdir()) == ['claude-stock.cmd', 'claude.cmd', 'dazzle-claude.cmd']
        for name in ('claude.cmd', 'claude-stock.cmd', 'dazzle-claude.cmd'):
            raw = (folder / name).read_bytes()
            assert b'\r\n' in raw and b'" -P -m dcc_patcher.launch %*' in raw   # -P: the cwd never shadows modules
        assert b'DCC_MODE=stock' in (folder / 'claude-stock.cmd').read_bytes()
        assert b'DCC_MODE=patched' in (folder / 'dazzle-claude.cmd').read_bytes()
        assert b'DCC_MODE' not in (folder / 'claude.cmd').read_bytes()
    for name in ('claude', 'claude-stock', 'dazzle-claude'):
        raw = (sh_folder / name).read_bytes()
        assert raw.startswith(b'#!/bin/sh\n') and b'\r' not in raw and b'" -P -m dcc_patcher.launch "$@"' in raw
        assert b'\\' not in raw                              # Git Bash wants forward slashes
    assert b'DCC_MODE=stock' in (sh_folder / 'claude-stock').read_bytes()
    assert b'DCC_MODE=patched' in (sh_folder / 'dazzle-claude').read_bytes()
    assert b'DCC_MODE' not in (sh_folder / 'claude').read_bytes()


@pytest.mark.skipif(os.name != 'nt', reason='the Windows layout')
def test_an_existing_install_gains_dazzle_claude_and_keeps_its_other_shims(world, tmp_path, capsys):
    # v0.1.6 to v0.2.0 wrote claude and claude-stock; v0.2.1 adds dazzle-claude (the switch) and
    # rewrites the other two in place
    official, _, home = world
    folder = tmp_path / 'bin'
    folder.mkdir()
    ours = b'@echo off\r\nrem Written by dcc-patcher install-shim: runs the official Claude Code.\r\n'
    (folder / 'claude.cmd').write_bytes(ours)
    (folder / 'claude-stock.cmd').write_bytes(ours)
    assert cli.main(['install-shim', '--dir', str(folder), '--no-path']) == 0
    assert sorted(p.name for p in folder.iterdir()) == ['claude-stock.cmd', 'claude.cmd', 'dazzle-claude.cmd']
    assert (folder / 'claude-stock.cmd').read_bytes() != ours            # rewritten from the template
    assert b'DCC_MODE=patched' in (folder / 'dazzle-claude.cmd').read_bytes()
    assert capsys.readouterr().out.count('wrote ') == 6                  # three .cmd, three sh


def test_dcc_mode_may_name_a_build_for_one_shell(world, launched, monkeypatch, capsys):
    # the switch: `dcc-env <build>` sets DCC_MODE to a build file name, as `use <build>` pins one
    official, builds_dir, _ = world
    start()                                                   # builds the first copy
    first = launched[-1][0]
    capsys.readouterr()
    monkeypatch.setenv('DCC_MODE', Path(first).name)
    official.write_bytes(official.read_bytes() + b'\0')       # Claude Code "updated"
    start()
    assert launched[-1][0] == first and 'building' not in capsys.readouterr().err
    monkeypatch.setenv('DCC_MODE', 'patched')
    start()
    assert 'Claude Code updated; building' in capsys.readouterr().err   # patched follows the update


def test_a_build_made_by_an_older_patcher_is_rebuilt_at_the_next_start(world, launched, monkeypatch, capsys):
    # v0.2.2: a new patch (or a changed one) reaches `claude` without waiting for a Claude Code
    # update. The build's name carries the patcher version that made it; a mismatch rebuilds.
    from dcc_patcher import builds
    official, builds_dir, _ = world
    start()
    old = launched[-1][0]
    capsys.readouterr()
    start()
    assert launched[-1][0] == old and 'building' not in capsys.readouterr().err   # same patcher: no rebuild
    monkeypatch.setattr(builds, 'BASE_VERSION', '9.9.9')                            # "pip install" of a newer one
    start()
    err = capsys.readouterr().err
    assert 'dcc-patcher updated; building the patched copy' in err
    assert launched[-1][0] != old and launched[-1][0].endswith('+dcc9.9.9' + Path(old).suffix)
    assert (builds_dir / Path(old).name).is_file()                                   # the old build is kept


@pytest.mark.skipif(os.name != 'nt', reason='the Windows layout')
def test_reinstalling_moves_the_old_sh_shims_off_the_windows_path_and_spares_files_not_ours(world, tmp_path, capsys):
    # CONSEQUENCE: 8 -- csb's `resume` failed with WinError 193 on the sh script v0.1.10 left there
    official, _, home = world
    folder = tmp_path / 'bin'
    folder.mkdir()
    (folder / 'claude').write_bytes(b'#!/bin/sh\n# Written by dcc-patcher install-shim: runs x.\n')
    (home / 'bin').mkdir()
    (home / 'bin' / 'claude-stock').write_bytes(b'#!/bin/sh\n# the user\'s own script\n')      # an old name, not ours
    (home / 'bin' / 'dazzle-claude').write_bytes(b'#!/bin/sh\n# the user\'s own wrapper\n')    # a name we write, not ours
    assert cli.main(['install-shim', '--dir', str(folder), '--no-path']) == 0
    assert not (folder / 'claude').exists()
    assert (home / 'bin' / 'claude-stock').read_bytes() == b'#!/bin/sh\n# the user\'s own script\n'
    assert (home / 'bin' / 'dazzle-claude').read_bytes() == b'#!/bin/sh\n# the user\'s own wrapper\n'
    assert "isn't one of ours; left it alone" in capsys.readouterr().err


@pytest.mark.parametrize('where', ['official', 'inside official', 'config'])
def test_install_shim_refuses_the_official_folder_and_claude_config(world, capsys, where):
    official, _, home = world
    folder = {'official': official.parent, 'inside official': official.parent / 'shims',
              'config': home / '.claude' / 'bin'}[where]
    before = sorted(p.name for p in official.parent.iterdir())
    assert cli.main(['install-shim', '--dir', str(folder)]) == 2
    assert sorted(p.name for p in official.parent.iterdir()) == before and not (home / '.claude').exists()
    assert not (official.parent / 'shims').exists()
