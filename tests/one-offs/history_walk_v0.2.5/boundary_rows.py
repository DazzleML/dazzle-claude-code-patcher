"""Rows around each compaction boundary, with chain membership from the newest message."""
import json, sys

path = sys.argv[1]
span = int(sys.argv[2]) if len(sys.argv) > 2 else 8
rows = []
with open(path, 'rb') as f:
    for n, line in enumerate(f, 1):
        line = line.strip()
        if line:
            d = json.loads(line); d['_n'] = n; rows.append(d)
by_uuid = {r['uuid']: r for r in rows if r.get('uuid')}

# newest chain by parentUuid only
chain = set(); cur = next(r for r in reversed(rows) if r.get('type') in ('user', 'assistant'))
while cur and cur['uuid'] not in chain:
    chain.add(cur['uuid']); cur = by_uuid.get(cur.get('parentUuid') or '')

def preview(r):
    m = r.get('message')
    if not isinstance(m, dict):
        return (r.get('content') or r.get('summary') or '')[:70] if isinstance(r.get('content'), str) else ''
    c = m.get('content')
    if isinstance(c, str):
        return c[:70]
    if isinstance(c, list) and c:
        b = c[0]
        if isinstance(b, dict):
            return (b.get('type', '') + ':' + str(b.get('text') or b.get('name') or b.get('tool_use_id') or '')[:60])
    return ''

for b in [r for r in rows if r.get('subtype') == 'compact_boundary']:
    print(f"\n=== boundary at line {b['_n']}  ts={b.get('timestamp')}  logicalParent={b['logicalParentUuid'][:8]}")
    lo, hi = max(0, b['_n'] - 1 - span), min(len(rows), b['_n'] + span + 6)
    for r in rows[lo:hi]:
        m = r.get('message') if isinstance(r.get('message'), dict) else {}
        flags = ''.join(k[0] for k in ('isMeta', 'isCompactSummary', 'isVisibleInTranscriptOnly') if r.get(k))
        print(f"{r['_n']:>6} {'*' if r.get('uuid') in chain else ' '} {str(r.get('type')):<10} {str(r.get('subtype') or ''):<16} "
              f"u={str(r.get('uuid'))[:8]} p={str(r.get('parentUuid'))[:8]} lp={str(r.get('logicalParentUuid') or '')[:8]} "
              f"ts={str(r.get('timestamp'))[11:19]} {m.get('role','') if m else '':<9} {flags:<3} {preview(r).replace(chr(10),' ')!r}")
