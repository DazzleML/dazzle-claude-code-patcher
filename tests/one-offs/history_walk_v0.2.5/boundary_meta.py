"""Each boundary's full compactMetadata, the writer's version, and the chain rows just
before the boundary in file order (the end of the previous segment)."""
import json, sys

path = sys.argv[1]
rows = []
with open(path, 'rb') as f:
    for n, line in enumerate(f, 1):
        line = line.strip()
        if line:
            d = json.loads(line); d['_n'] = n; rows.append(d)
by_uuid = {r['uuid']: r for r in rows if r.get('uuid')}
print('first row version:', next((r.get('version') for r in rows if r.get('version')), None))
for b in [r for r in rows if r.get('subtype') == 'compact_boundary']:
    print(f"\n=== boundary line {b['_n']} version={b.get('version')} uuid={b['uuid'][:8]}")
    meta = dict(b)
    for k in ('_n', 'uuid', 'parentUuid', 'sessionId', 'cwd', 'timestamp', 'content', 'userType', 'gitBranch', 'entrypoint', 'slug'):
        meta.pop(k, None)
    print(json.dumps(meta, indent=1)[:1500])
    # last 6 rows with a uuid before the boundary, in file order
    prev = [r for r in rows if r['_n'] < b['_n'] and r.get('uuid')][-6:]
    for r in prev:
        m = r.get('message') if isinstance(r.get('message'), dict) else {}
        c = m.get('content') if m else None
        pv = (c if isinstance(c, str) else (c[0].get('type', '') + ':' + str(c[0].get('text') or c[0].get('name') or '')[:50] if isinstance(c, list) and c and isinstance(c[0], dict) else ''))
        print(f"  before: {r['_n']:>6} {r.get('type'):<10} u={r['uuid'][:8]} p={str(r.get('parentUuid'))[:8]} ts={str(r.get('timestamp'))[11:19]} v={r.get('version')} {pv[:60]!r}")
    # preserved rows after the summary: rows after boundary whose timestamp is earlier than the boundary's
    after = [r for r in rows if r['_n'] > b['_n'] and r.get('uuid') and r.get('timestamp') and r['timestamp'] < b['timestamp']][:12]
    print('  rows after the boundary with an earlier timestamp (re-logged):', [(r['_n'], r['uuid'][:8], r.get('type')) for r in after])
    if after:
        head = after[0]
        print('  head of those:', head['_n'], 'parent', str(head.get('parentUuid'))[:8], '->', by_uuid.get(head.get('parentUuid') or '', {}).get('type'))
