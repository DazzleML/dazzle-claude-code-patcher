"""Simulate Claude Code 2.1.296's prune + chain walk on a session file, as patched by H
(edits 2-4 and the walker), with the stock timestamp fallback (q2r, 5 s window).
Mode 'h' = __dzCross rules 1-3 as shipped; mode 'h4' adds a 4th rule: when the pick is
already on the chain, continue from the latest row before the boundary in file order
that is not on the chain yet (same sidechain flag)."""
import json, sys
from datetime import datetime

path, mode = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else 'h')


def ts(r):
    try:
        return datetime.fromisoformat(r['timestamp'].replace('Z', '+00:00')).timestamp()
    except Exception:
        return None


e = {}        # uuid -> row, insertion order = file order
line_of = {}
with open(path, 'rb') as f:
    for n, line in enumerate(f, 1):
        line = line.strip()
        if not line:
            continue
        d = json.loads(line)
        if d.get('uuid'):
            e[d['uuid']] = d; line_of[d['uuid']] = n

is_boundary = lambda r: r.get('type') == 'system' and r.get('subtype') == 'compact_boundary'

# ---- prune (j2r) with H's edits: record the head's parent, delete nothing ----
orig_parent = {}
idx = {}; n_meta = None; r_i = s_i = -1
for i, row in enumerate(e.values()):
    idx[row['uuid']] = i
    if is_boundary(row):
        s_i = i; m = row.get('compactMetadata') or {}
        if m.get('preservedMessages') or m.get('preservedSegment'):
            n_meta, r_i = m, i
if n_meta and r_i == s_i:
    D = n_meta.get('preservedMessages')
    if D and D['uuids'] and all(u in e for u in D['uuids']):
        G = D['uuids']; anchor = D['anchorUuid']; tail = G[-1]
        orig_parent[G[0]] = e[G[0]].get('parentUuid')          # H edit 2
        prev = anchor
        for u in G:
            e[u] = {**e[u], 'parentUuid': prev}; prev = u
        for u, row in list(e.items()):
            if row.get('parentUuid') == anchor and u != G[0]:
                e[u] = {**row, 'parentUuid': tail}
        print(f'prune: last boundary relinked {len(G)} preserved rows; __dzOrigParent[head]={str(orig_parent[G[0]])[:8]} (line {line_of.get(orig_parent[G[0]])})')


def dz_cross(h, seen):
    if not is_boundary(h):
        return None
    L = h.get('logicalParentUuid')
    if not L:
        return None
    M = h.get('compactMetadata') or {}
    U = (M.get('preservedMessages') or {}).get('uuids') or []
    H0 = (M.get('preservedSegment') or {}).get('headUuid') or (U[0] if U else None)
    w, how = None, 'lpu'
    if L not in seen:
        w = L
    else:
        how = 'preserved'
        for k in range(len(U) - 1, -1, -1):
            if U[k] not in seen and U[k] in e:
                w = U[k]; break
        if not w and H0:
            how = 'head-parent'
            w = orig_parent.get(H0) or e.get(H0, {}).get('parentUuid')
    if mode == 'h4' and (not w or w not in e or w in seen):
        how = 'file-order'; w = None
        for u, row in e.items():
            if u == h['uuid']:
                break
            if u not in seen and bool(row.get('isSidechain')) == bool(h.get('isSidechain')) and row.get('type') in ('user', 'assistant', 'attachment', 'system'):
                w = u
    print(f"  walk: boundary line {line_of[h['uuid']]} lpu={L[:8]} seen={L in seen} via={how} -> {str(w)[:8]} (line {line_of.get(w)}, {'SEEN' if w in seen else 'new' if w in e else 'absent'})")
    return w


def q2r(y, seen):
    s = ts(y)
    if s is None:
        return None
    best, bd = None, float('inf')
    for row in e.values():
        if row['uuid'] in seen or bool(row.get('isSidechain')) != bool(y.get('isSidechain')):
            continue
        w = ts(row)
        if w is None:
            continue
        d = s - w
        if 0 <= d <= 5 and d < bd:
            bd, best = d, row
    return best


# ---- walker (Akt) with H's edit ----
start = next(r for r in reversed(list(e.values())) if r.get('type') in ('user', 'assistant'))
seen, chain, y = set(), [], start
while y:
    if y['uuid'] in seen:
        print('  cycle at', y['uuid'][:8]); break
    seen.add(y['uuid']); chain.append(y)
    w = y.get('parentUuid')
    if not w:
        w = dz_cross(y, seen)
    if not w:
        break
    D = e.get(w)
    if not D or D['uuid'] in seen:
        D = q2r(y, seen)
        print(f"  stock timestamp fallback at line {line_of[y['uuid']]}: -> {('line %d' % line_of[D['uuid']]) if D else 'nothing within 5 s'}")
    y = D
chain.reverse()
print(f'mode={mode}: chain rows {len(chain)}, earliest line reached {line_of[chain[0]["uuid"]]}, boundaries crossed {sum(1 for r in chain if is_boundary(r))}/4, first row: {chain[0].get("type")} {str((chain[0].get("message") or {}).get("content"))[:60]!r}')
