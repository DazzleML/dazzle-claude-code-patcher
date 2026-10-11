"""Show the row where the simulated walk (mode h4) stops, its parent, the rows before it
in file order, and the file's opening rows."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from sim_all import load, is_boundary  # noqa: E402
from sim_stops import run  # noqa: E402

p = Path(sys.argv[1]); mode = sys.argv[2] if len(sys.argv) > 2 else 'h4'
e = load(p); order = list(e); pos = {u: i for i, u in enumerate(order)}
reason, last, behind = run(e, mode)
print(f'{p.name[:8]}: stop reason: {reason}; boundaries behind: {behind}')


def desc(r, i):
    m = r.get('message') if isinstance(r.get('message'), dict) else {}
    c = m.get('content') if m else None
    pv = c[:50] if isinstance(c, str) else (c[0].get('type', '') + ':' + str(c[0].get('text') or c[0].get('name') or '')[:40] if isinstance(c, list) and c and isinstance(c[0], dict) else '')
    flags = ''.join(k[0] for k in ('isMeta', 'isCompactSummary', 'isSidechain') if r.get(k))
    return f"#{i:>6} {r.get('type'):<10} {str(r.get('subtype') or ''):<16} u={r['uuid'][:8]} p={str(r.get('parentUuid'))[:8]} lp={str(r.get('logicalParentUuid') or '')[:8]} ts={str(r.get('timestamp'))[:19]} v={r.get('version')} {flags:<3} {pv!r}"


print('\nopening rows:')
for i in range(min(4, len(order))):
    print(' ', desc(e[order[i]], i))
i = pos[last['uuid']]
print('\nstop row and the 8 before it (file order):')
for j in range(max(0, i - 8), i + 1):
    print(' ', desc(e[order[j]], j), '<-- STOP' if j == i else '')
par = last.get('parentUuid')
if par in e:
    print('\nparent row:', desc(e[par], pos[par]))
print('\nboundaries (file order):', [(pos[u], str(r.get('logicalParentUuid'))[:8], 'lp in file' if r.get('logicalParentUuid') in e else 'lp ABSENT') for u, r in e.items() if is_boundary(r)])
