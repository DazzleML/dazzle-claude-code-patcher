"""Candidate rule-2 changes for __dzCross, simulated beside the shipped walk (h4).

Modes:
  h4   -- v0.2.5 as shipped (rules 1-4 + relinked head + stock 5 s fallback)
  h5   -- rule 2 skips a preserved row whose ancestor chain (by parentUuid, staying inside the
          preserved list) reaches a row already on the chain: it is a side branch, not history
  h6   -- rule 2 considers only preserved rows that sit BEFORE the boundary in file order
          (a row written after the boundary was relinked onto the summary and leads nowhere older)

Usage:
  python -I sim_v026.py                      sweep every session file; report per mode
  python -I sim_v026.py --trace <path> [mode] per-boundary trace of one file
"""
import json, os, sys
from datetime import datetime
from pathlib import Path

root = Path(os.path.expanduser('~/.claude/projects'))
CHAIN_TYPES = ('user', 'assistant', 'attachment', 'system')
is_boundary = lambda r: r.get('type') == 'system' and r.get('subtype') == 'compact_boundary'


def ts(r):
    try:
        return datetime.fromisoformat(r['timestamp'].replace('Z', '+00:00')).timestamp()
    except Exception:
        return None


def load(p):
    e, line_of = {}, {}
    with open(p, 'rb') as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            if d.get('uuid') and d['uuid'] not in e:
                e[d['uuid']] = d; line_of[d['uuid']] = n
    return e, line_of


def walk(e, mode, trace=None, line_of=None):
    e = dict(e)
    order = {u: i for i, u in enumerate(e)}
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

    def is_branch(u, U, seen):
        """h5: does u's ancestor chain, staying inside U, reach a seen row?"""
        Us = set(U); hops = 0
        while u in e and hops < len(U) + 1:
            p = e[u].get('parentUuid')
            if not p:
                return False
            if p in seen:
                return True
            if p not in Us:
                return False
            u = p; hops += 1
        return False

    def cross(h, seen):
        L = h.get('logicalParentUuid')
        if not L:
            return None, 'no-lpu'
        M = h.get('compactMetadata') or {}
        U = (M.get('preservedMessages') or {}).get('uuids') or []
        H0 = (M.get('preservedSegment') or {}).get('headUuid') or (U[0] if U else None)
        w = None; how = 'lpu'
        if L not in seen:
            w = L
        else:
            how = 'preserved'
            for k in range(len(U) - 1, -1, -1):
                u = U[k]
                if u in seen or u not in e:
                    continue
                if mode in ('h5', 'h7') and is_branch(u, U, seen):
                    continue
                if mode == 'h6' and order[u] > order[h['uuid']]:
                    continue
                w = u; break
            if not w and H0:
                how = 'head-parent'
                w = orig_parent.get(H0) or e.get(H0, {}).get('parentUuid')
        if not w or w not in e or w in seen:
            how = 'file-order'; w = None
            for u, row in e.items():
                if u == h['uuid']:
                    break
                if u not in seen and bool(row.get('isSidechain')) == bool(h.get('isSidechain')) and row.get('type') in CHAIN_TYPES:
                    w = u
        if not w and mode == 'h7':
            # last resort: a preserved side branch after all (what h4 did at this boundary)
            how = 'preserved-branch'
            for k in range(len(U) - 1, -1, -1):
                if U[k] not in seen and U[k] in e:
                    w = U[k]; break
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
    if not main:
        return 0, 0, None, None
    seen = set(); y = main[-1]; crossed = 0; first = None
    while y and y['uuid'] not in seen:
        seen.add(y['uuid']); first = y
        w = y.get('parentUuid')
        if not w and is_boundary(y):
            w, how = cross(y, seen)
            if trace is not None:
                ln = line_of.get(y['uuid']) if line_of else None
                trace.append(f"  boundary {y['uuid'][:8]} line {ln}: via={how} -> {w[:8] if w else None}"
                             f" (line {line_of.get(w) if (w and line_of) else None})")
            if w:
                crossed += 1
        if not w:
            break
        D = e.get(w)
        if not D or D['uuid'] in seen:
            o = orig_parent.get(y['uuid'])
            D = e[o] if o and o in e and o not in seen else q2r(y, seen)
            if trace is not None:
                trace.append(f"    fallback at {y['uuid'][:8]} (line {line_of.get(y['uuid']) if line_of else None}):"
                             f" parent {w[:8] if w else None} {'missing' if w not in e else 'seen'} ->"
                             f" {'relinked-head' if (o and o in e and o not in seen) else 'ts-5s'} -> {D['uuid'][:8] if D else None}")
        y = D
    first_chain = main[0]
    reached = first is not None and (first['uuid'] == first_chain['uuid'] or (ts(first) is not None and ts(first_chain) is not None and ts(first) <= ts(first_chain) + 1))
    return crossed, len(seen), reached, (first['uuid'], line_of.get(first['uuid']) if line_of else None) if first else None


MODES = ('h4', 'h5', 'h6', 'h7')

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--trace':
        p = Path(sys.argv[2]); modes = sys.argv[3:] or MODES
        e, line_of = load(p)
        b = [u for u, r in e.items() if is_boundary(r)]
        print(f'{p.name[:8]}: {len(e)} rows, {len(b)} boundaries at lines {[line_of[u] for u in b]}')
        for mode in modes:
            tr = []
            c, n, reached, first = walk(e, mode, tr, line_of)
            print(f'\n[{mode}] crossed {c}/{len(b)}, chain {n} rows, reached first: {reached}, stops at {first}')
            print('\n'.join(tr))
        sys.exit(0)
    tot = {m: [0, 0] for m in MODES}; nb = 0; files = 0; diffs = []
    for p in sorted(root.glob('*/*.jsonl')):
        data = p.read_bytes()
        if b'"compact_boundary"' not in data:
            continue
        e, line_of = load(p)
        b = sum(1 for r in e.values() if is_boundary(r))
        if not b:
            continue
        files += 1; nb += b
        res = {}
        for mode in MODES:
            c, n, reached, first = walk(e, mode)
            tot[mode][0] += c; tot[mode][1] += 1 if reached else 0
            res[mode] = (c, n, reached)
        if len({(r[0], r[1], r[2]) for r in res.values()}) > 1 or not res['h4'][2]:
            diffs.append(f"{p.parent.name[:38]:<38} {p.name[:8]} b={b} " + ' '.join(f"{m}={res[m]}" for m in MODES))
    print(f'files {files}, boundaries {nb}')
    for mode, (c, reached) in tot.items():
        print(f'  {mode:<4} boundaries crossed {c}/{nb}; files reaching their first message {reached}/{files}')
    print('\nfiles where modes differ or h4 falls short (crossed, chain rows, reached):')
    print('\n'.join(diffs))
