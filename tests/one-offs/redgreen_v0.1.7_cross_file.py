"""Red-green audit of the #6 tests (v0.1.7): revert one behaviour of Patch J's
prelude at a time, run tests/test_cross_file.py, restore the spec from a copy.
The prelude runs under Node on synthetic files in tmp_path only."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / 'dcc_patcher' / 'patches' / 'J-history-across-files' / 'patch.toml'
REVERTS = [
    ('slice to the line', 'let s=cache.get(n).slice(0,e);', 'let s=cache.get(n);'),
    ('fixed point', 'pass<10&&want.size', 'pass<1&&want.size'),
    ('quiet on bad lines', 'try{o=JSON.parse(line)}catch{continue}', 'o=JSON.parse(line);'),
]
saved = Path(tempfile.mkdtemp(prefix='redgreen-')) / SPEC.name
shutil.copy2(SPEC, saved)
try:
    for name, old, new in REVERTS:
        text = SPEC.read_text(encoding='utf-8')
        assert text.count(old) == 1, f'{name}: anchor found {text.count(old)} times'
        SPEC.write_text(text.replace(old, new), encoding='utf-8')
        r = subprocess.run([sys.executable, '-P', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                            'tests/test_cross_file.py'], cwd=ROOT, capture_output=True, text=True, timeout=120)
        failed = [l.split('::')[-1].split(' ')[0] for l in r.stdout.splitlines() if l.startswith('FAILED')]
        print(f'{name:19} -> {len(failed)} red: {", ".join(failed) or "(none)"}')
        shutil.copy2(saved, SPEC)
finally:
    shutil.copy2(saved, SPEC)
