"""Population: for every boundary with a preserved segment, is the segment's HEAD written
before the boundary (patch H's rule 3 works) or after it (rule 3 lands on the summary)?
By writer version, with file counts."""
import json, os, re
from collections import Counter, defaultdict
from pathlib import Path

root = Path(os.path.expanduser('~/.claude/projects'))
UUID = re.compile(rb'"uuid":"([0-9a-f-]{36})"')
tot = Counter(); byver = defaultdict(Counter); files_bad = set(); files_all = set(); bad_last = 0
for p in root.glob('*/*.jsonl'):
    data = p.read_bytes()
    if b'"compact_boundary"' not in data:
        continue
    lines = data.split(b'\n'); line_of = {}
    for i, l in enumerate(lines):
        m = UUID.search(l)
        if m and m.group(1) not in line_of:
            line_of[m.group(1)] = i
    bidx = [i for i, l in enumerate(lines) if b'"compact_boundary"' in l]
    for i in bidx:
        try:
            d = json.loads(lines[i])
        except Exception:
            continue
        if d.get('subtype') != 'compact_boundary':
            continue
        files_all.add(p)
        m = d.get('compactMetadata') or {}
        head = ((m.get('preservedSegment') or {}).get('headUuid') or ((m.get('preservedMessages') or {}).get('uuids') or [None])[0] or '').encode()
        if not head:
            k = 'no preserved segment'
        elif head not in line_of:
            k = 'head absent'
        elif line_of[head] > i:
            k = 'head AFTER boundary (rule 3 fails)'; files_bad.add(p)
            if i == bidx[-1]:
                bad_last += 1
        else:
            k = 'head before boundary'
        tot[k] += 1; byver[d.get('version')][k] += 1
print('boundaries:', dict(tot))
print('files with boundaries:', len(files_all), '| files with at least one failing boundary:', len(files_bad), '| failing boundaries that are the file\'s last:', bad_last)
print('by version:')
for v in sorted(byver, key=lambda s: tuple(int(x) for x in s.split('.')) if s and re.fullmatch(r'[\d.]+', s) else (0,)):
    print(' ', v, dict(byver[v]))
