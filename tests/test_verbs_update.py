"""v0.2.4: the grouped `dcc-patcher -h`, `dcc-patcher update [--fix]`, and the offline
check status and dcc-env share. The acceptance checks are AC1-AC9 of
2026-10-09__16-39-46__dev-workflow-process__verb-structure-update-and-dazzle-lib.md.

Rule 1b: no test here can run pip or reach PyPI. Every update() call gets a stub
`run` that records and never installs, conftest stubs PyPI and the pip record, and
the fix tests also make subprocess.run itself raise.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from dcc_patcher import cli, selfupdate, verbs
from dcc_patcher._version import BASE_VERSION
from tests.test_path import machine  # noqa: F401  (the fixture)

ROOT = Path(__file__).resolve().parents[1]


# ---- the grouped help --------------------------------------------------------------

def _help():
    return cli.build_parser().format_help()


def test_every_command_appears_exactly_once_in_the_grouped_help():
    # AC1: a command left out of the groups would otherwise vanish from -h
    parser = cli.build_parser()
    out = parser.format_help()
    for name in verbs.command_help(parser):
        rows = [l for l in out.splitlines() if re.match(rf'^    {re.escape(name)}\s', l)]
        assert len(rows) == 1, (name, rows)
    assert 'other:' not in out                      # every command is in a group


def test_a_command_missing_from_the_groups_still_shows_under_other(monkeypatch):
    monkeypatch.setattr(verbs, 'GROUPS', verbs.GROUPS[:2])
    out = _help()
    assert 'other:' in out and re.search(r'^    install-shim\s', out, re.M)


def test_the_grouped_help_has_its_sections_the_pair_and_fits_80_columns():
    # AC5: the layout djdarcy approved
    out = _help()
    for heading in ('patches:', 'builds:', 'this machine:', 'options:'):
        assert re.search(rf'^  {heading}|^{heading}', out, re.M), heading
    assert 'install-shim <-> uninstall-shim' in out          # drawn from dazzle-lib's Groupable
    assert out.startswith('usage: dcc-patcher [-h] [-V] <command> ...')
    assert max(len(l) for l in out.splitlines()) <= 80
    assert 'rebuilt on update' not in out                    # the old wording, ambiguous beside `update`


@pytest.mark.parametrize('argv, expect', [
    (['install-shim', '--if-needed'], {'if_needed': True}),           # dcc-env, every run
    (['shellenv', 'cmd', '--folder'], {'shell': 'cmd', 'folder': True}),
    (['status', '--brief'], {'brief': True}),
    (['use', 'stock'], {'what': 'stock'}),
    (['use'], {'what': None}),
    (['rollback'], {}),
    (['restore-path', 'x.reg', '--yes'], {'backup': 'x.reg', 'yes': True}),
    (['archive'], {'official': None}),
    (['uninstall-shim'], {}),
    (['inspect', 'a.exe', '--marker', 'm'], {'file': 'a.exe', 'marker': 'm'}),
    (['validate'], {'specs': []}),
    (['check', 'a.exe', '--patch', 'p'], {'files': ['a.exe'], 'patch': ['p']}),
    (['apply', 'a.exe', '-o', 'b.exe', '--debug'], {'file': 'a.exe', 'output': 'b.exe', 'debug': True}),
    (['install-shim', '--dir', 'd', '--yes', '--no-path'], {'dir': 'd', 'yes': True, 'no_path': True}),
    (['update', '--fix', '--dry-run', '--offline'], {'fix': True, 'dry_run': True, 'offline': True}),
])
def test_every_invocation_dcc_env_docs_and_users_rely_on_still_parses(argv, expect):
    # AC2: the grouping changes how help reads, never what a command line means
    args = cli.build_parser().parse_args(argv)
    assert args.command == argv[0] and callable(args.func)
    for k, v in expect.items():
        assert getattr(args, k) == v, k


def _python(code):
    env = dict(os.environ, PYTHONPATH=str(ROOT))
    return subprocess.run([sys.executable, '-P', '-c', code], capture_output=True, text=True, env=env, cwd=ROOT)


def test_the_launcher_and_cli_never_load_dazzle_lib():
    # AC3: `claude` (python -m dcc_patcher.launch) rebuilds through cli; neither may need dazzle-lib
    r = _python('import sys, dcc_patcher.launch, dcc_patcher.cli as c; c.build_parser(); '
                'from dcc_patcher import selfupdate, install; '
                'print([m for m in sys.modules if m.startswith("dazzle_lib")])')
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == '[]'


def test_without_dazzle_lib_the_help_falls_back_and_the_tool_still_works():
    # AC4: dazzle-lib missing or broken changes the help's shape, never the exit code
    r = _python('import sys; sys.modules["dazzle_lib"] = None; sys.modules["dazzle_lib.groupable"] = None\n'
                'from dcc_patcher.cli import main\n'
                'try:\n    main(["-h"])\nexcept SystemExit as e:\n    print("exit", e.code)')
    assert 'exit 0' in r.stdout, r.stderr
    assert 'usage: dcc-patcher' in r.stdout and 'install-shim' in r.stdout
    assert 'this machine:' not in r.stdout                  # the plain argparse layout


# ---- the offline check ---------------------------------------------------------------

class FakeDist:
    """What importlib.metadata gives for an installed dcc-patcher: a version, pip's
    direct_url.json, and RECORD entries for the dcc-env scripts."""

    def __init__(self, root, version, checkout=None):
        self.version = version
        self.root = root
        self._direct = json.dumps({'url': checkout.as_uri(), 'dir_info': {'editable': True}}) if checkout else None
        self.files = [Path('..', 'Scripts', n) for n in selfupdate.SCRIPT_NAMES]

    def read_text(self, name):
        return self._direct if name == 'direct_url.json' else None

    def locate_file(self, f):
        return self.root / 'site-packages' / f


def _install(tmp_path, monkeypatch, version, *, checkout=False, scripts_version=None, same_as_bin=True):
    scripts = tmp_path / 'Scripts'
    scripts.mkdir()
    (tmp_path / 'site-packages').mkdir()
    co = None
    if checkout:
        co = tmp_path / 'checkout'
        (co / 'bin').mkdir(parents=True)
    for n in selfupdate.SCRIPT_NAMES:
        body = f"DCC_ENV_V='{scripts_version}'\n".encode() if scripts_version else b'old dcc-env, no stamp\n'
        (scripts / n).write_bytes(body)
        if co:
            (co / 'bin' / n).write_bytes(body if same_as_bin else body + b'# changed\n')
    monkeypatch.setattr(selfupdate, '_dist', lambda: FakeDist(tmp_path, version, co))
    return co


def test_a_pip_install_with_matching_scripts_is_current(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch, BASE_VERSION, scripts_version=BASE_VERSION)
    st = selfupdate.state()
    assert st['kind'] == 'pip' and st['pending'] == [] and st['fix'] is None
    assert all(s['current'] for s in st['scripts']) and len(st['scripts']) == 3


def test_scripts_older_than_the_package_are_named_with_the_reinstall(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch, BASE_VERSION, scripts_version=None)      # v0.2.1-style: no stamp
    st = selfupdate.state()
    assert st['pending'] == [f'the dcc-env scripts in {tmp_path / "Scripts"} are an older dcc-env, not {BASE_VERSION}']
    assert st['fix'][-1] == f'{selfupdate.DIST}=={BASE_VERSION}' and '--force-reinstall' in st['fix']


def test_an_editable_install_compares_the_copies_with_the_checkout_and_reinstalls_from_it(tmp_path, monkeypatch):
    # AC8: djdarcy's case -- the Scripts copies are older than the checkout's bin/
    co = _install(tmp_path, monkeypatch, BASE_VERSION, checkout=True, scripts_version=BASE_VERSION,
                  same_as_bin=False)
    st = selfupdate.state()
    assert st['kind'] == 'editable' and Path(st['checkout']) == co
    assert st['pending'] == [f"the dcc-env scripts in {tmp_path / 'Scripts'} are dcc-env {BASE_VERSION}, "
                             "not this checkout's bin/"]
    assert [s['current'] for s in st['scripts']] == [False] * 3
    assert st['fix'][-3:] == ['install', '-e', str(co)]


def test_an_editable_install_whose_pip_record_is_behind_the_checkout_is_named(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch, '0.2.1', checkout=True, scripts_version=BASE_VERSION)
    st = selfupdate.state()
    assert st['pending'] == [f'pip records 0.2.1; the checkout is {BASE_VERSION}']


@pytest.mark.skipif(sys.platform != 'win32', reason='the machine fixture fakes the Windows registry')
def test_status_and_dcc_envs_line_name_stale_scripts_and_say_nothing_when_current(machine, monkeypatch, capsys):
    # AC8: the line dcc-env prints gains one row only when something is stale
    from dcc_patcher import install
    stale_line = 'C:\\Py\\Scripts\\dcc-env.cmd is an older dcc-env, not this one'
    monkeypatch.setattr(install, '_updates', lambda: {'pending': []})
    cli.main(['status', '--brief'])
    assert 'update --fix' not in capsys.readouterr().out
    monkeypatch.setattr(install, '_updates', lambda: {'pending': [stale_line]})
    cli.main(['status', '--brief'])
    out = capsys.readouterr().out.splitlines()
    assert len(out) >= 2 and stale_line in out[-2] and selfupdate.fix_hint() in out[-1]
    cli.main(['status'])
    full = capsys.readouterr().out
    assert '\nUpdates\n' in full and stale_line in full


# ---- update and --fix ------------------------------------------------------------------

class Pip:
    """A stand-in for subprocess.run: records every command, installs nothing. The
    verify step (a fresh `python -m dcc_patcher update --offline --json`) is answered
    from `after`."""

    def __init__(self, code=0, after=None):
        self.calls, self.code, self.after = [], code, after if after is not None else {'pending': []}

    def __call__(self, cmd, **kw):
        self.calls.append(cmd)
        if cmd[-1] == '--json':
            return SimpleNamespace(returncode=0, stdout=json.dumps(self.after))
        return SimpleNamespace(returncode=self.code, stdout='')

    @property
    def pip_calls(self):
        return [c for c in self.calls if c[-1] != '--json']


@pytest.fixture
def stale(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch, BASE_VERSION, scripts_version=None)
    monkeypatch.setattr(subprocess, 'run', lambda *a, **k: (_ for _ in ()).throw(
        AssertionError('update reached subprocess.run instead of its stub')))


def _update(**kw):
    out = []
    kw.setdefault('offline', True)
    kw.setdefault('exe', False)                     # as `python -m dcc_patcher`, unless a test says otherwise
    code = selfupdate.update(out=out.append, **kw)
    return code, '\n'.join(out)


def test_update_without_fix_reports_and_runs_nothing(stale):
    # AC6
    pip = Pip()
    code, out = _update(run=pip)
    assert code == 1 and pip.calls == []
    assert f'-> {selfupdate.fix_hint()}' in out and 'waiting:' in out


@pytest.mark.parametrize('answer', ['', 'n', 'no', 'N'])
def test_fix_runs_nothing_unless_the_answer_is_yes(stale, answer):
    # AC6: bare Enter is no
    pip = Pip()
    code, out = _update(fix=True, run=pip, ask=lambda _: answer, tty=True)
    assert code == 1 and pip.calls == [] and 'nothing changed' in out


def test_fix_dry_run_shows_the_command_and_runs_nothing(stale):
    pip = Pip()
    code, out = _update(fix=True, dry_run=True, run=pip, ask=lambda _: 'y', tty=True)
    assert pip.calls == [] and '[dry-run] would run:' in out


def test_fix_without_a_terminal_needs_yes(stale):
    pip = Pip()
    code, out = _update(fix=True, run=pip, ask=lambda _: 'y', tty=False)
    assert code == 2 and pip.calls == [] and '--yes' in out


def test_fix_runs_pip_once_after_yes_and_confirms_from_a_fresh_process(stale):
    pip = Pip()
    code, out = _update(fix=True, run=pip, ask=lambda _: 'y', tty=True)
    assert code == 0 and out.rstrip().endswith('rebuilds if the dcc-patcher version changed.')
    assert len(pip.pip_calls) == 1 and pip.pip_calls[0][1:4] == ['-m', 'pip', 'install']
    assert pip.calls[-1][-3:] == ['update', '--offline', '--json']       # the verify step
    code, out = _update(fix=True, yes=True, run=Pip(), tty=False)      # --yes: no question, no terminal
    assert code == 0


def test_a_pip_error_after_a_completed_install_reads_as_done_with_the_windows_note(stale):
    # AC7: measured -- pip exits 1 when it can't delete the running exe it moved aside
    code, out = _update(fix=True, yes=True, run=Pip(code=1, after={'pending': []}))
    assert code == 0 and 'pip reported an error, but the install completed' in out and 'pip-uninstall-' in out


def test_a_fix_that_did_not_take_says_so_and_gives_the_command(stale):
    code, out = _update(fix=True, yes=True, run=Pip(code=1, after={'pending': ['still old']}))
    assert code == 1 and 'not current yet: still old' in out and 'Run it yourself' in out


def test_fix_never_runs_pip_from_dcc_patcher_exe_and_names_the_python_route(stale):
    # seen live 2026-10-09: pip, run from the running dcc-patcher.exe, failed on the locked exe
    # halfway through and left dcc_patcher uninstalled (claude couldn't start)
    pip = Pip()
    code, out = _update(fix=True, yes=True, run=pip, exe=True)
    assert code == 2 and pip.calls == []
    assert "can't update itself" in out and selfupdate.fix_hint() in out


def test_from_launcher_exe_reads_how_this_process_started(monkeypatch):
    monkeypatch.setattr(selfupdate.sys, 'platform', 'win32')
    for argv0, expect in ((r'C:\Python312\Scripts\dcc-patcher', True), (r'C:\Py\Scripts\dcc-patcher.exe', True),
                          (r'C:\code\x\dcc_patcher\__main__.py', False), ('-c', False)):
        monkeypatch.setattr(selfupdate.sys, 'argv', [argv0])
        assert selfupdate.from_launcher_exe() is expect, argv0
    monkeypatch.setattr(selfupdate.sys, 'platform', 'linux')
    monkeypatch.setattr(selfupdate.sys, 'argv', ['/usr/bin/dcc-patcher'])
    assert not selfupdate.from_launcher_exe()           # only Windows locks a running program's file


def test_a_fix_that_left_dcc_patcher_uninstalled_says_so_loudly(stale):
    class Gone(Pip):
        def __call__(self, cmd, **kw):
            self.calls.append(cmd)
            if cmd[-1] == '--json':
                return SimpleNamespace(returncode=1, stdout='', stderr="ModuleNotFoundError: No module named 'dcc_patcher'")
            return SimpleNamespace(returncode=1, stdout='')
    code, out = _update(fix=True, yes=True, run=Gone())
    assert code == 1 and 'no longer installed. Put it back now' in out and '.local\\bin\\claude.exe still can' in out


def test_help_before_a_command_shows_that_commands_help(capsys):
    with pytest.raises(SystemExit) as e:
        cli.main(['-h', 'status'])
    assert e.value.code == 0
    out = capsys.readouterr().out
    assert out.startswith('usage: dcc-patcher status') and '--brief' in out


def test_a_newer_release_on_pypi_is_offered_as_an_upgrade(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch, '0.2.4', scripts_version='0.2.4')
    monkeypatch.setattr(selfupdate, 'BASE_VERSION', '0.2.4')
    pip = Pip()
    code, out = _update(offline=False, fetch=lambda: ('0.3.0', None), run=pip)
    assert code == 1 and 'dcc-patcher 0.3.0 is out' in out and pip.calls == []
    assert '--upgrade' in out


def test_pypi_unreachable_is_one_line_not_a_failure(tmp_path, monkeypatch):
    _install(tmp_path, monkeypatch, BASE_VERSION, scripts_version=BASE_VERSION)
    code, out = _update(offline=False, fetch=lambda: (None, 'URLError: offline'))
    assert code == 0 and 'PyPI: not reached (URLError: offline)' in out and 'up to date' in out


# ---- the dcc-env stamp ---------------------------------------------------------------------

def test_each_dcc_env_script_carries_this_version():
    # AC9 (half): the version-sync tool edits JSON only, so this test is what keeps the stamps in step
    for n in selfupdate.SCRIPT_NAMES:
        assert selfupdate.stamp(ROOT / 'bin' / n) == BASE_VERSION, n
