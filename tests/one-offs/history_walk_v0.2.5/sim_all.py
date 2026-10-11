"""Run the simulated prune + walk (see sim_walk.py) over every session file under
~/.claude/projects that has a compaction boundary, in three helper modes:
  h     -- __dzCross as shipped (rules 1-3) + stock's 5 s timestamp fallback
  h4    -- plus rule 4: latest not-yet-seen row before the boundary in FILE order
  h4ts  -- plus rule 4 by TIMESTAMP: the unseen row with the greatest timestamp not after
           the preserved head's (or the boundary's, when there is no head)
Reports boundaries crossed per mode and the files whose walk reaches their first chain row."""
import json, os, sys
from datetime import datetime
from pathlib import Path

root = Path(os.path.expanduser('~/.claude/projects'))


def ts(r):
    try:
        return datetime.fromisoformat(r['timestamp'].replace('Z', '+00:00')).timestamp()
    except Exception:
        return None


def load(p):
    e = {}
    with open(p, 'rb') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get('uuid') and d['uuid'] not in e:
                e[d['uuid']] = d
    return e


is_boundary = lambda r: r.get('type') == 'system' and r.get('subtype') == 'compact_boundary'
CHAIN_TYPES = ('user', 'assistant', 'attachment', 'system')


def walk(e, mode):
    e = dict(e)
    orig_parent = {}
    n_meta = None; r_i = s_i = -1
    for i, row in enumerate(e.values()):
        if is_boundary(row):
            s_i = i; m = row.get('compactMetadata') or {}
            if m.get('preservedMessages') or m.get('preservedSegment'):
                n_meta, r_i = m, i
    if n_meta and r_i == s_i:
        D = n_meta.get('preservedMessages')
        if D and D.get('uuids') and all(u in e for u in D['uuids']):
            G = D['uuids']; anchor = D['anchorUuid']; tail = G[-1]
            orig_parent[G[0]] = e[G[0]].get('parentUuid')
            prev = anchor
            for u in G:
                e[u] = {**e[u], 'parentUuid': prev}; prev = u
            for u, row in list(e.items()):
                if row.get('parentUuid') == anchor and u != G[0]:
                    e[u] = {**row, 'parentUuid': tail}

    def cross(h, seen):
        L = h.get('logicalParentUuid')
        if not L:
            return None
        M = h.get('compactMetadata') or {}
        U = (M.get('preservedMessages') or {}).get('uuids') or []
        H0 = (M.get('preservedSegment') or {}).get('headUuid') or (U[0] if U else None)
        w = None
        if L not in seen:
            w = L
        else:
            for k in range(len(U) - 1, -1, -1):
                if U[k] not in seen and U[k] in e:
                    w = U[k]; break
            if not w and H0:
                w = orig_parent.get(H0) or e.get(H0, {}).get('parentUuid')
        if mode != 'h' and (not w or w not in e or w in seen):
            w = None
            if mode == 'h4':
                for u, row in e.items():
                    if u == h['uuid']:
                        break
                    if u not in seen and bool(row.get('isSidechain')) == bool(h.get('isSidechain')) and row.get('type') in CHAIN_TYPES:
                        w = u
            else:
                ref = e.get(H0) if H0 else None
                t0 = ts(ref) if ref else ts(h)
                best = None
                if t0 is not None:
                    for u, row in e.items():
                        if u in seen or bool(row.get('isSidechain')) != bool(h.get('isSidechain')) or row.get('type') not in CHAIN_TYPES:
                            continue
                        t = ts(row)
                        if t is not None and t <= t0 and (best is None or t >= best[0]):
                            best = (t, u)
                w = best[1] if best else None
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

    main = [r for r in e.values() if r.get('type') in ('user', 'assistant') and not r.get('isSidechain')]
    if not main:
        return 0, 0, None
    seen = set(); y = main[-1]; crossed = 0; first = None
    while y and y['uuid'] not in seen:
        seen.add(y['uuid']); first = y
        if is_boundary(y):
            pass
        w = y.get('parentUuid')
        if not w and is_boundary(y):
            w = cross(y, seen)
            if w:
                crossed += 1
        if not w:
            break
        D = e.get(w)
        if not D or D['uuid'] in seen:
            o = orig_parent.get(y['uuid']) if mode != 'h' else None     # v0.2.5: the relinked head
            D = e[o] if o and o in e and o not in seen else q2r(y, seen)
        y = D
    first_chain = main[0]
    return crossed, len(seen), first is not None and first['uuid'] == first_chain['uuid'] or (first is not None and ts(first) is not None and ts(first_chain) is not None and ts(first) <= ts(first_chain) + 1)


if __name__ != '__main__':
    sys.exit  # imported for load/ts/is_boundary only; the scan below is the script's job
tot = {'h': [0, 0], 'h4': [0, 0], 'h4ts': [0, 0]}; nb = 0; files = 0; rows_out = []
for p in (sorted(root.glob('*/*.jsonl')) if __name__ == '__main__' else []):
    data = p.read_bytes()
    if b'"compact_boundary"' not in data:
        continue
    e = load(p)
    b = sum(1 for r in e.values() if is_boundary(r))
    if not b:
        continue
    files += 1; nb += b
    res = {}
    for mode in tot:
        c, n, reached = walk(e, mode)
        tot[mode][0] += c; tot[mode][1] += 1 if reached else 0
        res[mode] = (c, reached)
    if res['h'][0] < b or not res['h'][1]:
        rows_out.append(f"{p.parent.name[:38]:<38} {p.name[:8]} boundaries={b} h={res['h']} h4={res['h4']} h4ts={res['h4ts']}")
if __name__ == '__main__':
    print(f'files {files}, boundaries {nb}')
    for mode, (c, reached) in tot.items():
        print(f'  {mode:<5} boundaries crossed {c}/{nb}; files whose walk reaches the first message {reached}/{files}')
    print('\nfiles where the shipped helper falls short:')
    print('\n'.join(rows_out))
