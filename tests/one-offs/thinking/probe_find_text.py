"""Which modules of a saved Claude Code build hold a piece of text, and where.

    python probe_find_text.py <version> <text> [<radius>]

Prints each module that holds <text>, with a window round up to 4 hits.
Read-only; opens the saved stock original through dcc-patcher's container.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from dcc_patcher.containers import open_container  # noqa: E402

ver, text = sys.argv[1], sys.argv[2].encode()
radius = int(sys.argv[3]) if len(sys.argv) > 3 else 400
exe = open_container((ROOT / 'private' / 'builds' / f'claude-cc-{ver}.exe').read_bytes())
for m in sorted(set(exe.find_module(text))):
    src = exe.source(m)
    print(f'== {ver} module {m}: {len(src):,} bytes, {src.count(text)} hit(s)')
    start = 0
    for _ in range(4):
        i = src.find(text, start)
        if i < 0:
            break
        print(f'-- @{i}')
        print(src[max(0, i - radius):i + radius].decode('latin-1'))
        start = i + len(text)
