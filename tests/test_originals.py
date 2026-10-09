"""Keeping the original Claude Code builds (#9): `archive` keeps each version
beside the official exe once, reads a file only once, never writes into the
official folder, and keeps two different builds of one version apart.

Everything is under tmp_path: the official folder, HOME and the builds folder."""
from pathlib import Path

import pytest

from dcc_patcher import builds, cli, originals
from tests.bunfixture import make_exe


def claude(version, extra=b''):
    return make_exe([b'other();', b'/*MARK*/VERSION:"' + version.encode() + b'";keep=!0;' + extra])


@pytest.fixture
def official(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    exe = home / '.local' / 'bin' / 'claude.exe'
    exe.parent.mkdir(parents=True)
    exe.write_bytes(claude('2.1.292'))
    (exe.parent / 'claude.exe.old.1790095191038').write_bytes(claude('2.1.278'))
    (exe.parent / 'claude.exe.old.1791314029496.1688').write_bytes(claude('2.1.291'))
    for var in ('HOME', 'USERPROFILE'):
        monkeypatch.setenv(var, str(home))
    monkeypatch.setenv('DCC_BUILDS_DIR', str(tmp_path / 'builds'))
    monkeypatch.delenv('CLAUDE_CONFIG_DIR', raising=False)
    monkeypatch.setattr(builds, 'REPO', tmp_path / 'repo')
    return exe


def kept(folder: Path):
    return sorted(p.name for p in folder.glob('claude-cc-*'))


def test_archive_keeps_each_version_once_and_leaves_the_official_folder_alone(official, tmp_path, monkeypatch, capsys):
    # CONSEQUENCE: 7 -- losing the releases we test patches against
    before = sorted((p.name, p.stat().st_mtime_ns) for p in official.parent.iterdir())
    assert cli.main(['archive', str(official)]) == 0
    assert kept(tmp_path / 'builds') == ['claude-cc-2.1.278.exe', 'claude-cc-2.1.291.exe', 'claude-cc-2.1.292.exe']
    assert '3 newly kept, 0 already kept' in capsys.readouterr().out
    assert sorted((p.name, p.stat().st_mtime_ns) for p in official.parent.iterdir()) == before
    monkeypatch.setattr(builds, 'version_of', lambda data: pytest.fail('re-read a file already looked at'))
    assert cli.main(['archive', str(official)]) == 0
    assert '0 newly kept, 3 already kept' in capsys.readouterr().out


def test_two_builds_of_one_version_are_both_kept_and_a_duplicate_is_not(official, tmp_path):
    # CONSEQUENCE: 5 -- a re-released version overwriting, or doubling, the kept copy
    (official.parent / 'claude.exe.old.1791000000000').write_bytes(claude('2.1.291', b'rebuilt;'))
    (official.parent / 'claude.exe.old.1791000000001').write_bytes(claude('2.1.278'))   # same bytes again
    originals.sweep(official)
    names = kept(tmp_path / 'builds')
    assert len(names) == 4 and 'claude-cc-2.1.291.exe' in names
    assert [n for n in names if n.startswith('claude-cc-2.1.291-') and n.endswith('.exe')]


def test_building_from_an_old_copy_names_the_build_exe(official, tmp_path):
    # CONSEQUENCE: 4 -- `apply claude.exe.old.<ms>` used the timestamp as the extension
    spec = tmp_path / 'patch.toml'
    spec.write_text('format = 1\nid = "T"\ntitle = "t"\nmodule_marker = "MARK"\nsignature = "/*t*/"\n'
                    '[[edit]]\nname = "f"\npattern = \'keep=!0\'\nreplace = \'keep=!1\'\n')
    old = official.parent / 'claude.exe.old.1790095191038'
    assert cli.main(['apply', str(old), '--patch', str(spec)]) == 0
    assert (tmp_path / 'builds' / f'claude-dcc-2.1.278+dcc{builds.BASE_VERSION}.exe').is_file()
