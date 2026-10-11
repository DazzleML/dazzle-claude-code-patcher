"""Why the walk stops: duplicates, the row each boundary's logicalParentUuid names, and
__dzCross's three choices at each boundary."""
import json, sys
from collections import Counter, defaultdict

path = sys.argv[1]
rows = []
with open(path, 'rb') as f:
    for n, line in enumerate(f, 1):
        line = line.strip()
        if line:
            d = json.loads(line); d['_n'] = n; rows.append(d)

occ = defaultdict(list)
for r in rows:
    if r.get('uuid'):
        occ[r['uuid']].append(r['_n'])
dups = {u: ns for u, ns in occ.items() if len(ns) > 1}
print('uuids', len(occ), 'duplicated', len(dups))
for u, ns in list(dups.items())[:10]:
    print('  dup', u[:8], ns, [rows[n-1].get('type') for n in ns])

by_uuid = {}
for r in rows:
    if r.get('uuid') and r['uuid'] not in by_uuid:
        by_uuid[r['uuid']] = r        # first occurrence
by_uuid_last = {r['uuid']: r for r in rows if r.get('uuid')}

def show(r, tag):
    print(f"  {tag}: line {r['_n']} type={r.get('type')} subtype={r.get('subtype')} uuid={r.get('uuid','')[:8]} parent={str(r.get('parentUuid'))[:8]} ts={r.get('timestamp')}")

for b in [r for r in rows if r.get('subtype') == 'compact_boundary']:
    print(f"\nboundary line {b['_n']} uuid={b['uuid'][:8]} logicalParent={b['logicalParentUuid'][:8]}")
    lp = b['logicalParentUuid']
    for tag, m in (('first occurrence', by_uuid), ('last occurrence', by_uuid_last)):
        if lp in m:
            t = m[lp]; show(t, tag)
            # walk parent chain a few steps
            cur = t
            for i in range(4):
                p = cur.get('parentUuid')
                if p is None:
                    print('     -> parent None at line', cur['_n'], cur.get('type'), cur.get('subtype')); break
                cur = m.get(p)
                if cur is None:
                    print('     -> parent', p[:8], 'MISSING'); break
                print(f"     -> line {cur['_n']} {cur.get('type')} {str(cur.get('subtype') or '')} uuid={cur['uuid'][:8]}")
    # rows between the previous boundary and this one with parentUuid None (segment heads)
    heads = [r for r in rows if r.get('type') in ('user','assistant') and r.get('parentUuid') is None]
print('\nuser/assistant rows with parentUuid None:', [(r['_n'], r['type'], r['uuid'][:8]) for r in heads][:20])

# full walk using first-occurrence map with __dzCross rule 1 only
seen = set(); cur = next(r for r in reversed(rows) if r.get('type') in ('user','assistant')); steps = 0; trail = []
while cur and cur['uuid'] not in seen:
    seen.add(cur['uuid']); steps += 1
    p = cur.get('parentUuid')
    if p is None:
        lp = cur.get('logicalParentUuid')
        trail.append((cur['_n'], cur.get('subtype'), 'lp' if lp else 'none'))
        if lp and lp in by_uuid and lp not in seen:
            cur = by_uuid[lp]; continue
        break
    nxt = by_uuid.get(p)
    if nxt is None:
        trail.append((cur['_n'], 'missing parent', p[:8])); break
    cur = nxt
print('\nwalk (first-occurrence map): rows reached', steps, 'trail', trail, 'ended at line', cur['_n'] if cur else None)
