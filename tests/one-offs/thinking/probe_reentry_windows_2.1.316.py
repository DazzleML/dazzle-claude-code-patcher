"""Print source windows from one module of the 2.1.316 bundle.

    python probe_reentry_windows_2.1.316.py <module-index> <spec> [<spec> ...]

A spec is either  @<offset>:<radius>   (window centred on a byte offset)
or                find:<text>:<radius>  (a window round every hit of <text>,
                                         up to 8 hits).
Read-only; opens the saved stock original through dcc-patcher's container.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from dcc_patcher.containers import open_container  # noqa: E402

EXE = ROOT / 'private' / 'builds' / 'claude-cc-2.1.316.exe'
MAX_HITS = 8

exe = open_container(EXE.read_bytes())
want = int(sys.argv[1])
key = next(k for k in exe.modules() if int(getattr(k, 'index', k)) == want) \
    if hasattr(exe, 'modules') else want
src = exe.source(key)
print(f'module {want}: {len(src):,} bytes')


def show(i, radius, tag):
    lo, hi = max(0, i - radius), min(len(src), i + radius)
    print(f'\n----- {tag} [{lo}:{hi}] -----')
    print(src[lo:hi].decode('latin-1'))


for spec in sys.argv[2:]:
    if spec.startswith('@'):
        off, rad = spec[1:].split(':')
        show(int(off), int(rad), f'@{off}')
    elif spec.startswith('find:'):
        _, text, rad = spec.split(':', 2)
        needle, rad = text.encode(), int(rad)
        start, n = 0, 0
        while n < MAX_HITS:
            i = src.find(needle, start)
            if i < 0:
                break
            show(i, rad, f'{text!r} hit {n + 1} @{i}')
            start, n = i + len(needle), n + 1
        if n == 0:
            print(f'\n----- {text!r}: no hits -----')
