"""Red-green audit of tests/test_history_walk.py against patch H's v0.2.5 change.

Two mutants, each applied to patch.toml by exact substring replacement, the test file
run against each, the file restored byte for byte and its hash checked:

  A. rule 4 removed: the file-order block in the prelude is made unreachable
     (`if(false&&...)`), every signature kept;
  B. the relinked-head branch removed: the walker's __dzOrigParent branch is made
     unreachable (`if(false&&__dzO...)`), so stock's own fallback runs instead.

Prints, per mutant, which tests went red. Nothing here touches a real build or a real
session file; the test runs the JavaScript under Node on synthetic fixtures.
"""
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOML = ROOT / 'dcc_patcher' / 'patches' / 'H-history-past-compaction' / 'patch.toml'
TEST = ROOT / 'tests' / 'test_history_walk.py'

MUTANTS = {
    'A rule 4 off': ('if((!w||!e.has(w)||g.has(w))&&e.has(h.uuid)){how="file-order";',
                     'if(false&&(!w||!e.has(w)||g.has(w))&&e.has(h.uuid)){how="file-order";'),
    'B head fallback off': ('if(__dzO&&!@@g@@.has(__dzO)&&@@em@@.has(__dzO))',
                            'if(false&&__dzO&&!@@g@@.has(__dzO)&&@@em@@.has(__dzO))'),
}


def run_tests():
    r = subprocess.run([sys.executable, '-m', 'pytest', str(TEST), '-q', '--no-header', '-p', 'no:cacheprovider', '-rf'],
                       capture_output=True, text=True, cwd=ROOT)
    failed = [l.split(' ', 1)[1].split(' - ')[0] for l in r.stdout.splitlines() if l.startswith('FAILED ')]
    summary = next((l for l in r.stdout.splitlines() if 'passed' in l or 'failed' in l), r.stdout[-200:])
    return failed, summary


original = TOML.read_bytes()
digest = hashlib.sha256(original).hexdigest()
text = original.decode('utf-8')
for name, (old, new) in MUTANTS.items():
    assert text.count(old) == 1, (name, text.count(old))
    try:
        TOML.write_bytes(text.replace(old, new, 1).encode('utf-8'))
        failed, summary = run_tests()
        print(f'{name}: {summary.strip()}')
        for f in failed:
            print('   red:', f)
        if not failed:
            print('   (no test went red)')
    finally:
        TOML.write_bytes(original)
    assert hashlib.sha256(TOML.read_bytes()).hexdigest() == digest, 'restore failed'
print('restored: sha256 unchanged', digest[:12])
