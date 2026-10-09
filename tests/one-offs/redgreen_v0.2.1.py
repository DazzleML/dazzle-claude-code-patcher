"""Red-green audit for the v0.2.1 switch: revert each behaviour (never the API), run only
the new tests, restore, and report anchors vs guards.

    python tests/one-offs/redgreen_v0.2.1.py

Each mutation is a substring replacement with a marker comment; the file is copied aside
first and restored byte for byte afterwards (checked), with a fresh PYTHONPYCACHEPREFIX
per run so a same-size edit can't be served from a stale .pyc.
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARK = '# DZ-MUTANT'

MUTATIONS = [
    ('a: _runs loses the "why" and the invalid-DCC_MODE branch', 'dcc_patcher/install.py',
     [("    env = os.environ.get('DCC_MODE')\n    if env and not launch.valid_mode(env):",
       "    env = os.environ.get('DCC_MODE')\n    env = env if env in ('stock', 'patched') else None  " + MARK +
       "\n    if False and env:"),
      ("    if env:\n        return f'{_describe(env, st, mark)} (this shell: dcc-env {env}; persistent: {st[\"mode\"]})'\n"
       "    return f'{_describe(st[\"mode\"], st, mark)} (persistent: dcc-patcher use {st[\"mode\"]})'",
       "    return _describe(env or st['mode'], st, mark)  " + MARK)],
     ['tests/test_switch.py']),
    ('b: valid_mode accepts stock/patched only', 'dcc_patcher/launch.py',
     [("    return Path(value).name == value and (builds.builds_dir() / value).is_file()   # a bare file name, never a path",
       "    return False  " + MARK)],
     ['tests/test_switch.py', 'tests/test_launcher.py::test_dcc_mode_may_name_a_build_for_one_shell']),
    ('c: no dazzle-claude shim', 'dcc_patcher/cli.py',
     [("              ('dazzle-claude', 'the current patched build', 'patched'))",
       "              )  " + MARK)],
     ['tests/test_launcher.py::test_install_shim_writes_four_launchers_from_two_templates',
      'tests/test_launcher.py::test_an_existing_install_gains_dazzle_claude_and_keeps_its_other_shims']),
    ('e: a shell that inherited ~/bin ahead of the shims is not flagged', 'dcc_patcher/install.py',
     [("    posix = winpath.position(path_value, str(builds.posix_shim_dir()))\n    if posix is None:\n        return False",
       "    return False  " + MARK + "\n    posix = None\n    if posix is None:\n        return False")],
     ['tests/test_switch.py::test_a_shell_that_inherited_tilde_bin_ahead_of_the_shims_is_flagged']),
    ('f: dcc-env skips the prepend when the shims are merely ahead of the official folder', 'dcc_patcher/install.py',
     [("    if _ahead(here, entry, anchor) and not (not posix and posix_dir_ahead(here, entry, 'powershell')):",
       "    if _ahead(here, entry, anchor):  " + MARK)],
     ['tests/test_switch.py::test_dcc_env_prepends_the_shims_when_tilde_bin_was_inherited_ahead_of_them']),
    ('d: is_set_up checks the claude shim only', 'dcc_patcher/install.py',
     [("    if not all((folder / f'{n}{ext}').is_file() for n in SHIM_NAMES):",
       "    if not (folder / f'claude{ext}').is_file():  " + MARK)],
     ['tests/test_switch.py::test_an_install_without_the_new_names_is_not_set_up']),
]


def run(targets):
    env = dict(os.environ, PYTHONPYCACHEPREFIX=tempfile.mkdtemp(prefix='dcc-rg-'))
    r = subprocess.run([sys.executable, '-P', '-m', 'pytest', '-q', '-rf', '--no-header', '-p', 'no:cacheprovider',
                        *targets], cwd=ROOT, env=env, capture_output=True, text=True)
    return r.stdout + r.stderr


def main():
    before = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, capture_output=True, text=True).stdout
    results = []
    for title, rel, edits, targets in MUTATIONS:
        path = ROOT / rel
        original = path.read_bytes()
        crlf = b'\r\n' in original                          # the checkout may be CRLF; match on LF
        text = original.decode('utf-8').replace('\r\n', '\n')
        for old, new in edits:
            assert text.count(old) == 1, f'{title}: anchor not found exactly once: {old[:60]!r}'
            text = text.replace(old, new)
        try:
            path.write_bytes(text.replace('\n', '\r\n' if crlf else '\n').encode('utf-8'))
            out = run(targets)
        finally:
            path.write_bytes(original)
        assert path.read_bytes() == original and MARK not in path.read_text(encoding='utf-8')
        failed = [l for l in out.splitlines() if l.startswith('FAILED')]
        results.append((title, failed, out.splitlines()[-1] if out.strip() else ''))
    green = run(['tests/test_switch.py', 'tests/test_launcher.py'])
    after = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, capture_output=True, text=True).stdout
    for title, failed, last in results:
        print(f'== {title}')
        print(f'   {last}')
        for f in failed:
            print(f'   {f[:150]}')
    print('== restored, new tests green again:', green.splitlines()[-1])
    print('== tree unchanged by the audit:', before == after)


if __name__ == '__main__':
    main()
