"""Measure a loosened loader regex for patch J against saved builds.

    python probe_patch_j_candidate.py 2.1.316 2.1.317 2.1.318 2.1.319

Prints, per build, how many times the candidate matches the loader module
and the captured groups, so the new anchor is proven to hit exactly once on
every build we still carry before it goes into patch.toml. Read-only.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from dcc_patcher.containers import open_container  # noqa: E402

MARKER = b'tengu_chain_parent_cycle'

# Changes against the shipped pattern: (pre) any plain declarators before the
# maker's; (mkargs) extra arguments after keepAllLeaves; (mid) a bounded lazy
# gap between the destructure and the .precede() call.
CANDIDATE = (
    r'async function (?P<fn>[\w$]+)\((?P<f>[\w$]+),(?P<o>[\w$]+)(?P<more>(?:,[\w$]+)*)\)\{'
    r'let (?P<pre>(?:[\w$]+=[^,(){};]*,)*)'
    r'(?P<r>[\w$]+)=(?P<mk>[\w$]+)\((?P=o)\?\.keepAllLeaves\?\?!1(?P<mkargs>(?:,[^()]*)?)\),'
    r'\{processEntry:(?P<add>[\w$]+),(?P<rest>[^}]*)\}=(?P=r)'
    r'(?P<mid>.{0,500}?)'
    r'(?P=r)\.precede\((?P=o)\?\.precedingEntries\?\?\[\]\);'
)
rx = re.compile(CANDIDATE.encode('latin-1'))

for ver in sys.argv[1:]:
    exe = open_container((ROOT / 'private' / 'builds' / f'claude-cc-{ver}.exe').read_bytes())
    (k,) = exe.find_module(MARKER)
    src = exe.source(k)
    hits = list(rx.finditer(src))
    print(f'\n=== {ver}: module {k}, {len(hits)} match(es)')
    for m in hits:
        g = {n: v.decode('latin-1') for n, v in m.groupdict().items()}
        for n in ('fn', 'f', 'o', 'more', 'pre', 'r', 'mk', 'mkargs', 'add', 'rest'):
            print(f'    {n:7}= {g[n]!r}')
        print(f'    mid    = {g["mid"]!r}')
        print(f'    span   = {m.start()}..{m.end()} ({m.end() - m.start()} bytes)')
