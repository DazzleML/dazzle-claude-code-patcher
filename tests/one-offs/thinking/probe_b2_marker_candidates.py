"""Measure candidate module markers for patch B2 across every saved original.

    python probe_b2_marker_candidates.py

For each build: how many modules hold each candidate, and whether the module(s)
it names hold B2's two edit sites. Read-only. Written 2026-11-13 (2.1.323 split
the flicker-free status module from the banner module).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from dcc_patcher.containers import open_container  # noqa: E402

CANDIDATES = {
    'current  "Using flicker-free rendering"': b'Using flicker-free rendering',
    'quoted   \':"Using flicker-free rendering"\'': b':"Using flicker-free rendering"',
    'tui-back "use /tui default"': b'if you want to go back, use /tui default',
}
TITLE = re.compile(rb'\{bold:!0,children:"Claude Code"\}')
VER = re.compile(rb'\{dimColor:!0,children:\["v",(?P<ver>[\w$]+)\]\}')


def vkey(p):
    return tuple(int(x) for x in p.stem.split('-')[-1].split('.'))


builds = sorted((ROOT / 'private' / 'builds').glob('claude-cc-*.exe'), key=vkey)
print(f'{len(builds)} originals: {builds[0].stem} .. {builds[-1].stem}\n')
for name, needle in CANDIDATES.items():
    print(f'== {name}')
    bad = []
    for b in builds:
        exe = open_container(b.read_bytes())
        hits = sorted(set(exe.find_module(needle)))
        sites = [(m, len(TITLE.findall(exe.source(m))), len(VER.findall(exe.source(m)))) for m in hits]
        ok = len(hits) == 1 and sites[0][1] == 1 and sites[0][2] == 1
        if not ok:
            bad.append((b.stem.split('-')[-1], sites))
    print(f'   one module with both sites on {len(builds) - len(bad)}/{len(builds)} builds')
    for v, s in bad:
        print(f'   {v}: modules (idx, title, ver) = {s}')
