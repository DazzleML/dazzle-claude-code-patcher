"""Where and why the simulated walk stops, per file, for helper modes h and h4.
Reuses sim_all's loader and prune; adds a stop reason and counts boundaries that lie
before the stop row in file order (history the walk never reached)."""
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from sim_all import load, ts, is_boundary, CHAIN_TYPES, root  # noqa: E402


def run(e0, mode):
    e = dict(e0); order = {u: i for i, u in enumerate(e)}
    orig_parent = {}; n_meta = None; r_i = s_i = -1
    for i, row in enumerate(e.values()):
        if is_boundary(row):
            s_i = i; m = row.get('compactMetadata') or {}
            if m.get('preservedMessages') or m.get('preservedSegment'):
                n_meta, r_i = m, i
    if n_meta and r_i == s_i:
        D = n_meta.get('preservedMessages')
        if D and D.get('uuids') and all(u in e for u in D['uuids']):
            G = D['uuids']; anchor = D['anchorUuid']; tail = G[-1]
            orig_parent[G[0]] = e[G[0]].get('parentUuid'); prev = anchor
            for u in G:
                e[u] = {**e[u], 'parentUuid': prev}; prev = u
            for u, row in list(e.items()):
                if row.get('parentUuid') == anchor and u != G[0]:
                    e[u] = {**row, 'parentUuid': tail}

    def cross(h, seen):
        L = h.get('logicalParentUuid')
        if not L:
            return None, 'no-lpu'
        M = h.get('compactMetadata') or {}
        U = (M.get('preservedMessages') or {}).get('uuids') or []
        H0 = (M.get('preservedSegment') or {}).get('headUuid') or (U[0] if U else None)
        w, how = None, 'lpu'
        if L not in e:
            how = 'lpu-absent'
        elif L not in seen:
            w = L
        else:
            how = 'preserved'
            for k in range(len(U) - 1, -1, -1):
                if U[k] not in seen and U[k] in e:
                    w = U[k]; break
            if not w and H0:
                how = 'head-parent'; w = orig_parent.get(H0) or e.get(H0, {}).get('parentUuid')
        if mode == 'h4' and (not w or w not in e or w in seen):
            how += '>file-order'; w = None
            for u, row in e.items():
                if u == h['uuid']:
                    break
                if u not in seen and bool(row.get('isSidechain')) == bool(h.get('isSidechain')) and row.get('type') in CHAIN_TYPES:
                    w = u
        return w, how

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
    seen = set(); y = main[-1]; reason = None; last = None
    while y:
        if y['uuid'] in seen:
            reason = 'cycle'; break
        seen.add(y['uuid']); last = y
        w = y.get('parentUuid'); how = 'parent'
        if not w:
            if is_boundary(y):
                w, how = cross(y, seen)
                if not w:
                    reason = f'boundary: {how} gave nothing'; break
            else:
                reason = 'start of history'; break
        D = e.get(w)
        if not D or D['uuid'] in seen:
            D2 = q2r(y, seen)
            if not D2:
                reason = f"{how}: pick {'absent' if not D else 'already on chain'}; 5 s fallback found nothing"; break
            D = D2
        y = D
    behind = sum(1 for u, r in e.items() if is_boundary(r) and order[u] < order[last['uuid']])
    return reason, last, behind


for p in (sorted(root.glob('*/*.jsonl')) if __name__ == '__main__' else []):
    data = p.read_bytes()
    if b'"compact_boundary"' not in data:
        continue
    e = load(p)
    nb = sum(1 for r in e.values() if is_boundary(r))
    if not nb:
        continue
    out = []
    for mode in ('h', 'h4'):
        reason, last, behind = run(e, mode)
        out.append((mode, reason, behind, last))
    if all(r[1] == 'start of history' for r in out):
        continue
    print(f"{p.parent.name[:34]:<34} {p.name[:8]} boundaries={nb} version={next((r.get('version') for r in e.values() if r.get('version')), '?')}")
    for mode, reason, behind, last in out:
        print(f"   {mode:<3} stop: {reason}; at {last.get('type')}/{last.get('subtype') or ''} ts={str(last.get('timestamp'))[:19]}; boundaries left behind: {behind}")
