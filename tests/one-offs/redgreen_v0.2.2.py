"""Red-green audit for v0.2.2: the launcher's rebuild-on-patcher-change rule (a fix, so an
anchor is required) and the spec of patch R (a feature: its test is a fence).

    python tests/one-offs/redgreen_v0.2.2.py

Same harness as redgreen_v0.2.1.py: each mutation is a substring replacement with a marker
comment, the file is restored byte for byte afterwards (checked), a fresh
PYTHONPYCACHEPREFIX per run, and git status compared before and after.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARK = '# DZ-MUTANT'

MUTATIONS = [
    ('a: the launcher reuses a fresh build whatever patcher made it (the old rule)', 'dcc_patcher/launch.py',
     [("    if fresh and builds.made_by_this_version(current):",
       "    if fresh:  " + MARK)],
     ['tests/test_launcher.py::test_a_build_made_by_an_older_patcher_is_rebuilt_at_the_next_start']),
    ('b: patch R carries a prelude and a second edit (the fence)', 'dcc_patcher/patches/R-compaction-rows/patch.toml',
     [('signature = "/*dazzle-claude-code:rows-v1*/"',
       'signature = "/*dazzle-claude-code:rows-v1*/"\nprelude = "globalThis.__dzRows=1;"  ' + MARK)],
     ['tests/test_spec.py::test_the_compaction_rows_patch_loads_as_one_display_edit']),
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
        crlf = b'\r\n' in original
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
        results.append((title, failed))
    green = run(['tests/test_launcher.py', 'tests/test_spec.py'])
    after = subprocess.run(['git', 'status', '--porcelain'], cwd=ROOT, capture_output=True, text=True).stdout
    for title, failed in results:
        print(f'== {title}')
        for f in failed:
            print(f'   {f[:150]}')
        if not failed:
            print('   (no failure: survived)')
    print('== restored, tests green again:', 'passed' in green.splitlines()[-1], '|', green.splitlines()[-1][:60])
    print('== tree unchanged by the audit:', before == after)


if __name__ == '__main__':
    main()
