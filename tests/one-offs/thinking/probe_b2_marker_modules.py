"""Which modules carry patch B2's marker, and which of them hold its two edit sites?

    python probe_b2_marker_modules.py <version> [<version> ...]

Read-only; opens the saved stock originals through dcc-patcher's container.
Written 2026-11-13 when 2.1.323 reported the marker in two modules.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from dcc_patcher.containers import open_container  # noqa: E402

MARKER = b'Using flicker-free rendering'
TITLE = re.compile(rb'\{bold:!0,children:"Claude Code"\}')
VER = re.compile(rb'\{dimColor:!0,children:\["v",(?P<ver>[\w$]+)\]\}')

for ver in sys.argv[1:]:
    exe = open_container((ROOT / 'private' / 'builds' / f'claude-cc-{ver}.exe').read_bytes())
    hits = sorted(set(exe.find_module(MARKER)))
    print(f'{ver}: marker in modules {hits}')
    for m in hits:
        src = exe.source(m)
        n_marker = src.count(MARKER)
        print(f'  module {m}: {len(src):,} bytes; marker x{n_marker}; '
              f'title sites {len(TITLE.findall(src))}; version sites {len(VER.findall(src))}')
        for i in [k.start() for k in re.finditer(re.escape(MARKER), src)][:3]:
            lo, hi = max(0, i - 160), min(len(src), i + 120)
            print('    ...' + src[lo:hi].decode('latin-1').replace('\n', ' ') + '...')
