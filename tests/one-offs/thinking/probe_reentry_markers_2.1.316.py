"""Where do the session re-entry markers live in the 2.1.316 bundle?

Opens the saved stock original with dcc-patcher's own container code and
prints, for each marker string, the module(s) that carry it and a window of
source around each hit. Read-only; nothing is written.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from dcc_patcher.containers import open_container  # noqa: E402

EXE = ROOT / 'private' / 'builds' / 'claude-cc-2.1.316.exe'
DEFAULT_MARKERS = ['leftArrowOpensAgents', 'forkSession', 'fork-session', 'forkedFrom']
WINDOW = int(sys.argv[1]) if len(sys.argv) > 1 else 220
MARKERS = [m.encode() for m in (sys.argv[2:] or DEFAULT_MARKERS)]
MAX_HITS = 6

data = EXE.read_bytes()
exe = open_container(data)

for marker in MARKERS:
    keys = exe.find_module(marker)
    print(f'\n=== {marker.decode()}: {len(keys)} module(s)')
    for k in keys:
        src = exe.source(k)
        name = getattr(k, 'name', None) or str(k)
        print(f'--- module {name} ({len(src):,} bytes)')
        start = 0
        shown = 0
        while shown < MAX_HITS:
            i = src.find(marker, start)
            if i < 0:
                break
            lo, hi = max(0, i - WINDOW), min(len(src), i + len(marker) + WINDOW)
            print(f'  @{i}: ...{src[lo:hi].decode("latin-1")}...')
            start = i + len(marker)
            shown += 1
        rest = src.count(marker) - shown
        if rest > 0:
            print(f'  (+{rest} more)')
