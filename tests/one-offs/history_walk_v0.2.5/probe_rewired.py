"""18ba9d65: rows around its last boundary, who points at the anchor, where the preserved
rows sit, and the order the newest chain visits the anchor and the head."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from sim_all import load, is_boundary  # noqa: E402

p = Path(sys.argv[1]); e = load(p); order = list(e); pos = {u: i for i, u in enumerate(order)}
b = [r for r in e.values() if is_boundary(r)][-1]; bi = pos[b['uuid']]
meta = b['compactMetadata']; seg = meta.get('preservedSegment') or {}; U = (meta.get('preservedMessages') or {}).get('uuids') or []
anchor, head, tail = seg.get('anchorUuid'), seg.get('headUuid'), seg.get('tailUuid')
print(f"last boundary at #{bi} ts={b['timestamp']} lp={b['logicalParentUuid'][:8]} head={head[:8]} anchor={anchor[:8]} tail={tail[:8]} preserved={len(U)} durationMs={meta.get('durationMs')}")
print('preserved positions:', [(pos.get(u), 'after' if pos.get(u, -1) > bi else 'before') for u in U])
print('rows whose parent is the anchor:', [(pos[u], r.get('type')) for u, r in e.items() if r.get('parentUuid') == anchor])
print('\nrows', bi - 8, 'to', bi + 12)
for j in range(bi - 8, min(len(order), bi + 13)):
    r = e[order[j]]
    print(f"  #{j:>5} {r.get('type'):<10} {str(r.get('subtype') or ''):<16} u={r['uuid'][:8]} p={str(r.get('parentUuid'))[:8]} ts={str(r.get('timestamp'))[11:19]} v={r.get('version')} {'PRESERVED' if r['uuid'] in U else ''} {'ANCHOR' if r['uuid'] == anchor else ''}")
# newest chain visit order
main = [r for r in e.values() if r.get('type') in ('user', 'assistant') and not r.get('isSidechain')]
seen = []; y = main[-1]
while y and y['uuid'] not in set(seen):
    seen.append(y['uuid']); y = e.get(y.get('parentUuid') or '')
print('\nnewest chain (parentUuid only, no prune):', len(seen), 'rows; visits anchor at step', seen.index(anchor) if anchor in seen else None, '; head at step', seen.index(head) if head in seen else None, '; boundary at step', seen.index(b['uuid']) if b['uuid'] in seen else None)
print('first 12 steps:', [(pos[u], e[u].get('type')) for u in seen[:12]])
