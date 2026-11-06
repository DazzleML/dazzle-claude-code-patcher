"""Print source windows from one module of a saved Claude Code build.

    python probe_windows.py <version> <module-index> <spec> [<spec> ...]

A spec is either  @<offset>:<radius>   (window centred on a byte offset)
or                find:<text>:<radius>  (a window round every hit of <text>,
                                         up to 8 hits).
Read-only; opens the saved stock original through dcc-patcher's container.
The 2.1.316-only probe_reentry_windows_2.1.316.py is this with the build fixed.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from dcc_patcher.containers import open_container  # noqa: E402

MAX_HITS = 8

ver, want = sys.argv[1], int(sys.argv[2])
exe = open_container((ROOT / 'private' / 'builds' / f'claude-cc-{ver}.exe').read_bytes())
src = exe.source(want)
print(f'{ver} module {want}: {len(src):,} bytes')


def show(i, radius, tag):
    lo, hi = max(0, i - radius), min(len(src), i + radius)
    print(f'\n----- {tag} [{lo}:{hi}] -----')
    print(src[lo:hi].decode('latin-1'))


for spec in sys.argv[3:]:
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
