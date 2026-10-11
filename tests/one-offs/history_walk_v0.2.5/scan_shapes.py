"""Two more population counts: (i) files that open with a compaction boundary (continued
sessions) and whether that boundary's logicalParentUuid is inside the file; (ii) files
whose newest user/assistant row is the compaction summary itself (the compaction was the
last event before the resume), where the walk reaches the preserved rows through rule 1
and dead-ends at the head's relinked parent."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from sim_all import load, is_boundary, root  # noqa: E402

opening = []; idle_last = []; files = 0
for p in sorted(root.glob('*/*.jsonl')):
    if b'"compact_boundary"' not in p.read_bytes():
        continue
    e = load(p); rows = list(e.values())
    if not any(is_boundary(r) for r in rows):
        continue
    files += 1
    if is_boundary(rows[0]):
        opening.append((p.name[:8], rows[0].get('version'), 'lp in file' if rows[0].get('logicalParentUuid') in e else 'lp absent'))
    main = [r for r in rows if r.get('type') in ('user', 'assistant') and not r.get('isSidechain')]
    if main and main[-1].get('isCompactSummary'):
        b = [r for r in rows if is_boundary(r)][-1]
        U = ((b.get('compactMetadata') or {}).get('preservedMessages') or {}).get('uuids') or []
        idle_last.append((p.name[:8], main[-1].get('version'), f'{len(U)} preserved'))
print('files with boundaries:', files)
print(f'(i) files opening with a boundary: {len(opening)}; lp in file: {sum(1 for o in opening if o[2] == "lp in file")}; lp absent: {sum(1 for o in opening if o[2] == "lp absent")}')
for o in opening:
    print('   ', o)
print(f'(ii) files whose newest message is the compaction summary (idle compaction last): {len(idle_last)}')
for o in idle_last:
    print('   ', o)
