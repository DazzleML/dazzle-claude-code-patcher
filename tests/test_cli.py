"""The command line, on the scenarios that matter: an unsupported file is refused
cleanly (AC11); a real build is described; and `apply` without `-o` keeps
versioned builds in one fixed folder, never inside Claude Code's config (#3)."""
import os
from pathlib import Path

import pytest

from dcc_patcher import builds as builds_mod
from dcc_patcher._version import BASE_VERSION
from dcc_patcher.cli import main
from tests.bunfixture import make_exe

REAL = os.path.expanduser('~/.local/bin/claude.exe')


def test_inspect_refuses_an_unsupported_file_with_exit_2(tmp_path, capsys):
    f = tmp_path / 'not-an-exe.bin'
    f.write_bytes(b'\x7fELF' + b'\0' * 60)
    assert main(['inspect', str(f)]) == 2
    err = capsys.readouterr().err
    assert 'unsupported format: ELF' in err
    assert 'Traceback' not in err


@pytest.mark.parametrize('command', ['inspect', 'check'])
def test_a_mistyped_path_is_a_message_not_a_traceback(tmp_path, capsys, command):
    # e.g. %USERPROFILE% left unexpanded by Git Bash
    assert main([command, str(tmp_path / '%USERPROFILE%' / 'claude.exe')]) == 2
    err = capsys.readouterr().err
    assert 'No such file' in err and 'Traceback' not in err


def test_validate_accepts_the_bundled_patches(capsys):
    assert main(['validate']) == 0
    assert 'ok  H  History past compaction' in capsys.readouterr().out


def test_validate_refuses_a_malformed_spec_by_name_with_exit_2(tmp_path, capsys):
    f = tmp_path / 'patch.toml'
    f.write_text('format = 1\nid = "X"\ntitle = "x"\n')
    assert main(['validate', str(f)]) == 2
    assert 'missing or empty "module_marker"' in capsys.readouterr().err


# --- apply without -o: versioned builds in one fixed folder (#3) -------------------
# Rule 1b: every path a mutant could reach is under tmp_path. HOME and USERPROFILE
# point there, so "~/.claude" is tmp_path/home/.claude; DCC_BUILDS_DIR is set, so
# the default never resolves to the real private/builds; no exe is ever run.

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


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    builds = tmp_path / 'builds'
    home.mkdir()
    for var in ('HOME', 'USERPROFILE'):
        monkeypatch.setenv(var, str(home))
    monkeypatch.setenv('DCC_BUILDS_DIR', str(builds))
    monkeypatch.delenv('CLAUDE_CONFIG_DIR', raising=False)
    # every fallback a mutant could fall through to stays under tmp_path too
    monkeypatch.setattr(builds_mod, 'REPO', tmp_path / 'repo')
    monkeypatch.setenv('LOCALAPPDATA', str(tmp_path / 'localappdata'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'xdg'))
    exe = tmp_path / 'claude.exe'
    exe.write_bytes(make_exe([b'other();', b'/*MARK*/VERSION:"2.1.999";keep=!0;']))
    spec_path = tmp_path / 'patch.toml'
    spec_path.write_text(SPEC)
    return exe, spec_path, builds, home


def apply(*extra, exe, spec_path):
    return main(['apply', str(exe), '--patch', str(spec_path), *map(str, extra)])


def test_apply_without_o_writes_a_versioned_build_and_points_the_current_name_at_it(isolated, capsys):
    exe, spec_path, builds, _ = isolated
    assert apply(exe=exe, spec_path=spec_path) == 0
    build = builds / f'claude-dcc-2.1.999+dcc{BASE_VERSION}.exe'
    current = builds / 'claude-dcc.exe'
    assert build.exists() and Path(f'{build}.dcc-lock.json').exists()
    assert current.read_bytes() == build.read_bytes() and os.path.samefile(current, build)
    out = capsys.readouterr().out
    assert f'wrote {build}' in out and f'{current} -> {build.name} (hardlink)' in out


def test_rebuilding_the_same_versions_reports_already_built_and_duplicates_nothing(isolated, capsys):
    exe, spec_path, builds, _ = isolated
    assert apply(exe=exe, spec_path=spec_path) == 0
    build = builds / f'claude-dcc-2.1.999+dcc{BASE_VERSION}.exe'
    mtime = build.stat().st_mtime_ns
    capsys.readouterr()
    assert apply(exe=exe, spec_path=spec_path) == 0
    assert f'already built: {build}' in capsys.readouterr().out
    assert build.stat().st_mtime_ns == mtime
    assert sorted(p.name for p in builds.iterdir()) == sorted(
        [build.name, f'{build.name}.dcc-lock.json', 'claude-dcc.exe',
         'claude-cc-2.1.999.exe', 'originals.json'])           # the original, kept once (#9)


@pytest.mark.parametrize('where', ['default', '-o', 'CLAUDE_CONFIG_DIR'])
def test_apply_refuses_to_write_inside_claude_codes_config_folder(isolated, monkeypatch, capsys, where):
    exe, spec_path, builds, home = isolated
    if where == 'default':
        monkeypatch.setenv('DCC_BUILDS_DIR', str(home / '.claude' / 'build-out'))
        code = apply(exe=exe, spec_path=spec_path)
    elif where == '-o':      # the incident: a relative -o, run from the home folder
        monkeypatch.chdir(home)
        code = apply('-o', Path('.claude') / 'build-out' / 'claude-dcc.exe', exe=exe, spec_path=spec_path)
    else:                    # a relative CLAUDE_CONFIG_DIR still names the same folder
        monkeypatch.chdir(exe.parent)
        monkeypatch.setenv('CLAUDE_CONFIG_DIR', 'test-config')
        code = apply('-o', exe.parent / 'test-config' / 'claude-dcc.exe', exe=exe, spec_path=spec_path)
    assert code == 2
    assert "refusing to write inside Claude Code's config folder" in capsys.readouterr().err
    assert not (home / '.claude').exists() and not (exe.parent / 'test-config').exists()


def test_a_running_current_build_is_one_line_and_the_versioned_build_is_kept(isolated, monkeypatch, capsys):
    exe, spec_path, builds, _ = isolated
    real_replace = os.replace

    def in_use(src, dst):
        if Path(dst).name == 'claude-dcc.exe':
            raise PermissionError(13, 'Access is denied')
        return real_replace(src, dst)

    monkeypatch.setattr(os, 'replace', in_use)
    assert apply(exe=exe, spec_path=spec_path) == 1
    err = capsys.readouterr().err
    assert 'the current build is in use' in err and 'Traceback' not in err
    assert (builds / f'claude-dcc-2.1.999+dcc{BASE_VERSION}.exe').exists()
    assert sorted(p.name for p in builds.iterdir() if p.name.startswith('.dcc-')) == []


def test_only_an_exe_in_use_is_reported_as_in_use(isolated, monkeypatch, capsys):
    exe, spec_path, _, _ = isolated
    real_replace = os.replace

    def disk_full(src, dst):
        if Path(dst).name == 'claude-dcc.exe':
            raise OSError(28, 'No space left on device')
        return real_replace(src, dst)

    monkeypatch.setattr(os, 'replace', disk_full)
    with pytest.raises(OSError, match='No space'):
        apply(exe=exe, spec_path=spec_path)
    assert 'in use' not in capsys.readouterr().err


def test_a_corrupt_lockfile_at_the_versioned_name_means_rebuild(isolated, capsys):
    exe, spec_path, builds, _ = isolated
    build = builds / f'claude-dcc-2.1.999+dcc{BASE_VERSION}.exe'
    builds.mkdir()
    build.write_bytes(b'old')
    Path(f'{build}.dcc-lock.json').write_text('{not json')
    assert apply(exe=exe, spec_path=spec_path) == 0
    assert f'wrote {build}' in capsys.readouterr().out and build.read_bytes() != b'old'


def test_without_hardlinks_the_current_name_is_a_copy(isolated, monkeypatch, capsys):
    exe, spec_path, builds, _ = isolated

    def no_links(src, dst):
        raise OSError(1, 'hardlinks not supported')

    monkeypatch.setattr(os, 'link', no_links)
    assert apply(exe=exe, spec_path=spec_path) == 0
    build = builds / f'claude-dcc-2.1.999+dcc{BASE_VERSION}.exe'
    current = builds / 'claude-dcc.exe'
    assert current.read_bytes() == build.read_bytes() and not os.path.samefile(current, build)
    assert '(copy)' in capsys.readouterr().out


def test_with_o_there_is_no_current_name_and_the_path_is_printed_absolute(isolated, monkeypatch, capsys):
    exe, spec_path, builds, _ = isolated
    monkeypatch.chdir(exe.parent)
    assert apply('-o', 'out.exe', exe=exe, spec_path=spec_path) == 0
    assert f'wrote {exe.parent / "out.exe"}' in capsys.readouterr().out
    assert not builds.exists() and not (exe.parent / 'claude-dcc.exe').exists()


def test_with_o_a_rebuild_always_writes(isolated, capsys):
    exe, spec_path, _, _ = isolated
    out = exe.parent / 'out.exe'
    assert apply('-o', out, exe=exe, spec_path=spec_path) == 0
    capsys.readouterr()
    assert apply('-o', out, exe=exe, spec_path=spec_path) == 0
    assert f'wrote {out}' in capsys.readouterr().out


def test_changed_patches_at_the_same_versions_rebuild_rather_than_report_already_built(isolated, capsys):
    exe, spec_path, builds, _ = isolated
    assert apply(exe=exe, spec_path=spec_path) == 0
    spec_path.write_text(SPEC.replace("replace = 'keep=!1'", "replace = 'keep=!1/*v2*/'"))
    capsys.readouterr()
    assert apply(exe=exe, spec_path=spec_path) == 0
    assert 'already built' not in capsys.readouterr().out
    assert b'/*v2*/' in (builds / f'claude-dcc-2.1.999+dcc{BASE_VERSION}.exe').read_bytes()


def test_a_stale_temporary_link_left_by_a_killed_run_does_not_block_the_hardlink(isolated, capsys):
    exe, spec_path, builds, _ = isolated
    builds.mkdir()
    (builds / '.dcc-claude-dcc.exe.tmp').write_bytes(b'stale')
    assert apply(exe=exe, spec_path=spec_path) == 0
    assert '(hardlink)' in capsys.readouterr().out
    assert not (builds / '.dcc-claude-dcc.exe.tmp').exists()


@pytest.mark.parametrize('platform, var', [('win32', 'LOCALAPPDATA'), ('linux', 'XDG_DATA_HOME')])
def test_the_default_builds_folder(tmp_path, monkeypatch, platform, var):
    monkeypatch.delenv('DCC_BUILDS_DIR', raising=False)
    monkeypatch.setattr(builds_mod.sys, 'platform', platform)
    monkeypatch.setenv(var, str(tmp_path / 'data'))
    repo = tmp_path / 'repo'
    monkeypatch.setattr(builds_mod, 'REPO', repo)
    assert builds_mod.builds_dir() == tmp_path / 'data' / 'dazzle-claude-code-patcher' / 'builds'
    (repo / '.git').mkdir(parents=True)                      # running from a checkout
    assert builds_mod.builds_dir() == repo / 'private' / 'builds'


@pytest.mark.skipif(not os.path.exists(REAL), reason='no local Claude Code build')
def test_inspect_describes_a_real_build(capsys):
    assert main(['inspect', REAL, '--marker', 'tengu_chain_parent_cycle']) == 0
    out = capsys.readouterr().out
    assert 'format:   pe' in out
    assert 'marker:   [' in out
