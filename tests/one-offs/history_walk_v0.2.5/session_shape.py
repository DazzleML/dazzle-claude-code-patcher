"""Shape of a session file as patch H sees it: boundaries, chain, what __dzCross would pick."""
import json, sys
from collections import Counter

path = sys.argv[1]
rows = []
with open(path, 'rb') as f:
    for n, line in enumerate(f, 1):
        line = line.strip()
        if not line:
            continue
        try:
            d = json.loads(line)
        except Exception as e:
            print(f'line {n}: bad json ({e})')
            continue
        d['_n'] = n
        rows.append(d)

print('rows', len(rows))
print('types', Counter(r.get('type') for r in rows).most_common())
print('subtypes', Counter(r.get('subtype') for r in rows if r.get('subtype')).most_common())
print('sidechain', Counter(bool(r.get('isSidechain')) for r in rows))
by_uuid = {r['uuid']: r for r in rows if r.get('uuid')}
print('first row:', rows[0].get('type'), rows[0].get('subtype'), rows[0].get('cwd'), rows[0].get('timestamp'))
print('last row:', rows[-1].get('type'), rows[-1].get('subtype'), rows[-1].get('cwd'), rows[-1].get('timestamp'))

bounds = [r for r in rows if r.get('subtype') == 'compact_boundary' or r.get('type') == 'summary' and r.get('leafUuid')]
print('\nboundaries:', len([r for r in rows if r.get('subtype') == 'compact_boundary']))
for r in rows:
    if r.get('subtype') != 'compact_boundary':
        continue
    lp = r.get('logicalParentUuid')
    cm = r.get('compactMetadata') or {}
    print(f"  line {r['_n']:>6} uuid={r.get('uuid','')[:8]} parent={str(r.get('parentUuid'))[:8]} logicalParent={str(lp)[:8]} "
          f"in-file={lp in by_uuid} trigger={cm.get('trigger')} preTokens={cm.get('preTokens')} preserved={len(cm.get('preservedMessageUuids') or [])} cwd={r.get('cwd')}")

# walk parentUuid back from the newest message with a uuid
last = next(r for r in reversed(rows) if r.get('uuid') and r.get('type') in ('user', 'assistant', 'system'))
seen = set(); cur = last; steps = 0; stops = []
while cur is not None and cur['uuid'] not in seen:
    seen.add(cur['uuid']); steps += 1
    p = cur.get('parentUuid')
    if p is None:
        stops.append((cur['_n'], cur.get('type'), cur.get('subtype'), str(cur.get('logicalParentUuid'))[:8]))
        lp = cur.get('logicalParentUuid')
        if lp and lp in by_uuid and lp not in seen:
            cur = by_uuid[lp]; continue
        break
    cur = by_uuid.get(p)
    if cur is None:
        stops.append(('missing parent', p[:8])); break
print('\nstock-style walk from newest (parentUuid only, then logicalParent at a boundary):', steps, 'rows reached')
print('stops at:', stops)
print('rows with uuid not reached:', len(by_uuid) - len(seen))
