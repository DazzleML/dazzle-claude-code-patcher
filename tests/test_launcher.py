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
    folder = tmp_path / 'bin'
    assert cli.main(['install-shim', '--dir', str(folder)]) == 0
    assert sorted(p.name for p in folder.iterdir()) == ['claude', 'claude-stock', 'claude-stock.cmd', 'claude.cmd']
    for name in ('claude.cmd', 'claude-stock.cmd'):
        raw = (folder / name).read_bytes()
        assert b'\r\n' in raw and b'" -P -m dcc_patcher.launch %*' in raw   # -P: the cwd never shadows modules
    for name in ('claude', 'claude-stock'):
        raw = (folder / name).read_bytes()
        assert raw.startswith(b'#!/bin/sh\n') and b'\r' not in raw and b'" -P -m dcc_patcher.launch "$@"' in raw
        assert b'\\' not in raw                              # Git Bash wants forward slashes
    for stock, plain in (('claude-stock.cmd', 'claude.cmd'), ('claude-stock', 'claude')):
        assert b'DCC_MODE=stock' in (folder / stock).read_bytes()
        assert b'DCC_MODE' not in (folder / plain).read_bytes()


@pytest.mark.parametrize('where', ['official', 'inside official', 'config'])
def test_install_shim_refuses_the_official_folder_and_claude_config(world, capsys, where):
    official, _, home = world
    folder = {'official': official.parent, 'inside official': official.parent / 'shims',
              'config': home / '.claude' / 'bin'}[where]
    before = sorted(p.name for p in official.parent.iterdir())
    assert cli.main(['install-shim', '--dir', str(folder)]) == 2
    assert sorted(p.name for p in official.parent.iterdir()) == before and not (home / '.claude').exists()
    assert not (official.parent / 'shims').exists()
