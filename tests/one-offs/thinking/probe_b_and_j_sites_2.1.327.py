"""Patch B's banner sites and patch J's loader head, side by side on two builds.

    python probe_b_and_j_sites_2.1.327.py 2.1.326 2.1.327

Read-only; opens the saved stock originals through dcc-patcher's container.
Written 2026-11-18 when 2.1.327 reported B (found 1, expected 2) and J (found 0).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from dcc_patcher import spec  # noqa: E402
from dcc_patcher.containers import open_container  # noqa: E402

P = ROOT / 'dcc_patcher' / 'patches'
B = spec.load(P / 'B-banner-label' / 'patch.toml')
J = spec.load(P / 'J-history-across-files' / 'patch.toml')


def show(src, i, before, after, tag):
    print(f'  -- {tag} @{i}')
    print('     ' + src[max(0, i - before):i + after].decode('latin-1').replace('\n', ' '))


for ver in sys.argv[1:]:
    exe = open_container((ROOT / 'private' / 'builds' / f'claude-cc-{ver}.exe').read_bytes())
    print(f'\n######## {ver}')
    mods = sorted(set(exe.find_module(B.module_marker.encode())))
    print(f'B marker {B.module_marker!r}: modules {mods}')
    for m in mods:
        src = exe.source(m)
        print(f' module {m}: {len(src):,} bytes; edit matches '
              f'{len(re.findall(B.edits[0].pattern.encode(), src))}')
        for k in re.finditer(rb'children:"Claude Code"', src):
            show(src, k.start(), 120, 260, 'title')
    for m in sorted(set(exe.find_module(b'children:"Claude Code"'))):
        if m not in mods:
            src = exe.source(m)
            print(f' (also in module {m}, {len(src):,} bytes, without the marker)')
            for k in list(re.finditer(rb'children:"Claude Code"', src))[:4]:
                show(src, k.start(), 120, 260, 'title')
    (jm,) = exe.find_module(J.module_marker.encode())
    src = exe.source(jm)
    print(f'J module {jm}: edit matches {len(re.findall(J.edits[0].pattern.encode(), src))}')
    for k in re.finditer(rb'\.precede\(', src):
        show(src, k.start(), 700, 60, 'precede')
