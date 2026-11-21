"""Which rows of a session file would Claude Code 2.1.328+ mark "cut off"?

    python probe_cut_off_rows.py <session.jsonl>

Mirrors the bundle's rule over the WHOLE file (no pruning): after the first
user/assistant row, a non-sidechain row whose parentUuid names a row that is not
in the file, and that is not a compact-summary user row. Prints each such row and
the file's first chain rows. Read-only.
"""
import json
import sys

path = sys.argv[1]
rows, uuids = [], set()
with open(path, encoding='utf-8') as f:
    for n, line in enumerate(f, 1):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if not isinstance(r, dict) or 'uuid' not in r:
            continue
        uuids.add(r['uuid'])
        rows.append((n, r))
print(f'{len(rows):,} rows with a uuid')
seen = False
hits = 0
for n, r in rows:
    if r.get('isSidechain'):
        continue
    p = r.get('parentUuid')
    if seen and p and p not in uuids and not (r.get('type') == 'user' and r.get('isCompactSummary')):
        hits += 1
        print(f'CUT line {n} {r.get("type")}/{r.get("subtype")} ts={r.get("timestamp")} '
              f'uuid={r["uuid"][:8]} parent={p[:8]} logicalParent={str(r.get("logicalParentUuid"))[:8]} '
              f'sid={str(r.get("sessionId"))[:8]}')
    seen = seen or r.get('type') in ('user', 'assistant')
print(f'{hits} cut-off row(s)')
for n, r in rows[:3]:
    print(f'first: line {n} {r.get("type")}/{r.get("subtype")} parent={r.get("parentUuid")} sid={str(r.get("sessionId"))[:8]}')
comp = [(n, r) for n, r in rows if r.get('subtype') == 'compact_boundary']
print(f'{len(comp)} compact boundaries at lines {[n for n, _ in comp]}')
