"""Packaging (#4): an installed wheel carries the bundled patches and the shim
templates and finds them; with no patch specs, every command refuses rather than
reporting a clean run that checked nothing.

The wheel is built from a copy of the source under tmp_path (building in place
would write build/ and *.egg-info into the repository) and installed into a
scratch target, never into the running Python."""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from dcc_patcher import cli

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def wheel(tmp_path_factory):
    src = tmp_path_factory.mktemp('src')
    shutil.copytree(ROOT / 'dcc_patcher', src / 'dcc_patcher', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(ROOT / 'bin', src / 'bin')                  # the dcc-env scripts (#9)
    for name in ('pyproject.toml', 'README.md', 'LICENSE'):
        if (ROOT / name).exists():
            shutil.copy2(ROOT / name, src / name)
    out = tmp_path_factory.mktemp('dist')
    r = subprocess.run([sys.executable, '-m', 'pip', 'wheel', str(src), '-w', str(out), '--no-deps',
                        '--no-build-isolation', '-q'], capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        pytest.skip(f'cannot build a wheel here: {r.stderr.strip()[-200:]}')
    return next(out.glob('*.whl'))


def test_the_wheel_carries_the_patch_specs_and_the_shim_templates(wheel):
    names = set(zipfile.ZipFile(wheel).namelist())
    for patch in ('B-banner-label', 'B2-banner-label-flicker-free', 'H-history-past-compaction',
                  'J-history-across-files', 'V-version-label'):
        assert f'dcc_patcher/patches/{patch}/patch.toml' in names
    assert {'dcc_patcher/shims/claude.cmd.in', 'dcc_patcher/shims/claude.sh.in'} <= names


def test_the_wheel_installs_dcc_env_beside_dcc_patcher_with_the_line_ends_each_shell_needs(wheel, tmp_path):
    # CONSEQUENCE: 6 -- a shell opened before install-shim has no one-word way onto the shim
    names = zipfile.ZipFile(wheel).namelist()
    scripts = {n.rsplit('/', 1)[-1]: n for n in names if '.data/scripts/' in n}
    assert {'dcc-env.cmd', 'dcc-env.ps1', 'dcc-env'} <= set(scripts)
    z = zipfile.ZipFile(wheel)
    assert b'\r\n' in z.read(scripts['dcc-env.cmd'])          # cmd wants CRLF
    assert b'\r' not in z.read(scripts['dcc-env'])            # bash, when sourced, chokes on CR


def test_an_installed_wheel_finds_its_bundled_patches(wheel, tmp_path):
    site = tmp_path / 'site'
    r = subprocess.run([sys.executable, '-m', 'pip', 'install', str(wheel), '--target', str(site), '--no-deps', '-q'],
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stderr
    run = subprocess.run([sys.executable, '-P', '-c',
                          f'import sys; sys.path.insert(0, {str(site)!r}); '
                          'from dcc_patcher.cli import main; sys.exit(main(["validate"]))'],
                         capture_output=True, text=True, cwd=tmp_path, timeout=60)
    assert run.returncode == 0, run.stderr
    assert str(site) in run.stdout                              # the installed copy, not this checkout
    assert 'ok  H  ' in run.stdout and 'ok  V  ' in run.stdout


@pytest.mark.parametrize('command', [['validate'], ['check', 'x.exe'], ['apply', 'x.exe']])
def test_no_patch_specs_is_one_line_and_exit_2(tmp_path, monkeypatch, capsys, command):
    monkeypatch.setattr(cli, 'PATCHES_DIR', tmp_path / 'empty')
    assert cli.main(command) == 2
    err = capsys.readouterr().err
    assert 'no patch specs found' in err and err.count('\n') == 1 and 'Traceback' not in err
