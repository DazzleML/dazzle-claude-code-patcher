"""For each boundary: where each preserved uuid sits (line, before/after the boundary),
its on-disk parent, and whether it is on the newest chain."""
import json, sys

path = sys.argv[1]
rows = []
with open(path, 'rb') as f:
    for n, line in enumerate(f, 1):
        line = line.strip()
        if line:
            d = json.loads(line); d['_n'] = n; rows.append(d)
by_uuid = {r['uuid']: r for r in rows if r.get('uuid')}
chain = set(); cur = next(r for r in reversed(rows) if r.get('type') in ('user', 'assistant'))
while cur and cur['uuid'] not in chain:
    chain.add(cur['uuid']); cur = by_uuid.get(cur.get('parentUuid') or '')

for b in [r for r in rows if r.get('subtype') == 'compact_boundary']:
    meta = b['compactMetadata']; seg = meta.get('preservedSegment') or {}; U = (meta.get('preservedMessages') or {}).get('uuids') or []
    print(f"\n=== boundary line {b['_n']} durationMs={meta.get('durationMs')} head={seg.get('headUuid','')[:8]} anchor={seg.get('anchorUuid','')[:8]} tail={seg.get('tailUuid','')[:8]} preserved={len(U)}")
    for i, u in enumerate(U):
        r = by_uuid.get(u)
        if r is None:
            print(f"  [{i:>2}] {u[:8]} ABSENT from file"); continue
        where = 'after' if r['_n'] > b['_n'] else 'before'
        p = r.get('parentUuid'); pr = by_uuid.get(p or '')
        pwhere = '' if pr is None else ('after' if pr['_n'] > b['_n'] else 'before')
        print(f"  [{i:>2}] {u[:8]} line {r['_n']:>6} {where:<6} {r.get('type'):<10} ts={str(r.get('timestamp'))[11:23]} parent={str(p)[:8]} ({pwhere}{' preserved' if p in U else ''}{' anchor' if p == seg.get('anchorUuid') else ''}) {'ON-CHAIN' if u in chain else 'off'}")
    # the head's parent, and the row that sits right before the boundary in file order
    head = by_uuid.get(seg.get('headUuid', ''))
    if head:
        hp = by_uuid.get(head.get('parentUuid') or '')
        print('  head parent:', str(head.get('parentUuid'))[:8], 'line', hp['_n'] if hp else None, 'in preserved' if head.get('parentUuid') in U else 'NOT preserved (pre-compaction)')
