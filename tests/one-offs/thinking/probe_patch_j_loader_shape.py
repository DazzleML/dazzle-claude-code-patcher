"""Why does patch J not locate on a given Claude Code build?

    python probe_patch_j_loader_shape.py 2.1.318 2.1.319

For each version: open the saved stock original, run the engine's locate
over patch J alone and print its verdict, then print the loader windows the
edit anchors on (keepAllLeaves / processEntry: / .precede() so the two
builds can be compared by eye. Read-only.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from dcc_patcher import engine, spec            # noqa: E402
from dcc_patcher.containers import open_container  # noqa: E402

J = spec.load(ROOT / 'dcc_patcher' / 'patches' / 'J-history-across-files' / 'patch.toml')
WINDOW = 420
NEEDLES = ['keepAllLeaves??!1', 'processEntry:', '.precede(']

for ver in sys.argv[1:]:
    exe_path = ROOT / 'private' / 'builds' / f'claude-cc-{ver}.exe'
    print(f'\n################ {ver}: {exe_path.name}')
    exe = open_container(exe_path.read_bytes())

    print('--- locate_all(J):')
    try:
        res = engine.locate_all(exe, [J])
        print(json.dumps(res, default=str, indent=1)[:4000])
    except Exception as x:  # noqa: BLE001 - diagnostic
        print(f'raised {type(x).__name__}: {x}')

    keys = exe.find_module(J.module_marker.encode())
    print(f'--- modules with marker {J.module_marker!r}: {keys}')
    for k in keys:
        src = exe.source(k)
        print(f'--- module {k}: {len(src):,} bytes')
        edit = J.edits[0]
        hits = list(re.finditer(edit.pattern.encode('latin-1'), src))
        print(f'    edit regex matches: {len(hits)}')
        for n in NEEDLES:
            b = n.encode()
            idxs = [m.start() for m in re.finditer(re.escape(b), src)]
            print(f'    {n!r}: {len(idxs)} hit(s) at {idxs[:8]}')
        # One window per keepAllLeaves hit: that is where the loader is.
        for i in [m.start() for m in re.finditer(re.escape(b'keepAllLeaves??!1'), src)][:4]:
            lo, hi = max(0, i - WINDOW), min(len(src), i + WINDOW)
            print(f'\n    ----- window @{i} [{lo}:{hi}] -----')
            print('    ' + src[lo:hi].decode('latin-1'))
