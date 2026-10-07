"""Red-green audit of the #4 tests (v0.1.9): revert one behaviour at a time, run
tests/test_packaging.py, restore from a copy. The wheel is built and installed only
under tmp_path."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
P, C = ROOT / 'pyproject.toml', ROOT / 'dcc_patcher' / 'cli.py'
REVERTS = [
    ('package data', P, 'dcc_patcher = ["patches/*/*.toml", "patches/*/*.md", "shims/*.in"]', ''),
    ('refusal', C, '        if not found:\n            raise NoSpecs(', '        if False:\n            raise NoSpecs('),
]
saved = Path(tempfile.mkdtemp(prefix='redgreen-'))
for f in (P, C):
    shutil.copy2(f, saved / f.name)
try:
    for name, f, old, new in REVERTS:
        text = f.read_text(encoding='utf-8')
        assert text.count(old) == 1, f'{name}: anchor found {text.count(old)} times'
        f.write_text(text.replace(old, new), encoding='utf-8')
        r = subprocess.run([sys.executable, '-P', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                            'tests/test_packaging.py'], cwd=ROOT, capture_output=True, text=True, timeout=600)
        failed = [l.split('::')[-1].split(' ')[0] for l in r.stdout.splitlines() if l.startswith('FAILED')]
        print(f'{name:13} -> {len(failed)} red: {", ".join(failed) or "(none)"}')
        shutil.copy2(saved / f.name, f)
finally:
    for f in (P, C):
        shutil.copy2(saved / f.name, f)
