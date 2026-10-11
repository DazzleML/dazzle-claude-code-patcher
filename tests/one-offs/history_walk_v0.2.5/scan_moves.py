"""Does /cd move a session file between project folders, and does the move change it?
(a) session ids present in more than one project folder, with sizes and byte-prefix check;
(b) per file: the folder it is in vs the cwd of its first and last rows, and the /cd
    commands it records (local_command rows and <command-name>/cd</command-name>);
(c) index files beside the transcripts."""
import json, os, re
from collections import defaultdict
from pathlib import Path

root = Path(os.path.expanduser('~/.claude/projects'))
CWD = re.compile(rb'"cwd":"((?:[^"\\]|\\.)*)"')
CD = re.compile(rb'<command-name>/cd</command-name>\s*<command-message>[^<]*</command-message>\s*<command-args>([^<]*)</command-args>')
UUIDN = re.compile(r'^[0-9a-f-]{36}\.jsonl$')


def enc(p):
    return re.sub(r'[^A-Za-z0-9-]', '-', p)


by_id = defaultdict(list)
for p in root.glob('*/*.jsonl'):
    if UUIDN.match(p.name):
        by_id[p.stem].append(p)

print('(a) session ids in more than one folder:')
dups = {k: v for k, v in by_id.items() if len(v) > 1}
for sid, paths in sorted(dups.items()):
    paths = sorted(paths, key=lambda q: q.stat().st_size)
    datas = [q.read_bytes() for q in paths]
    prefix = all(datas[-1].startswith(d) for d in datas[:-1])
    print(f'  {sid[:8]}: ' + ' | '.join(f'{q.parent.name} {q.stat().st_size}B mtime={q.stat().st_mtime:.0f}' for q in paths) + f'  smaller-is-prefix-of-largest={prefix}')
print(f'  total: {len(dups)} ids, of {len(by_id)} session ids')

print('\n(b) folder vs cwd, and /cd commands:')
moved = 0; stayed = 0; cd_files = 0; rows_out = []
for sid, paths in by_id.items():
    for p in paths:
        data = p.read_bytes()
        cwds = [m.group(1).decode('utf-8', 'replace').replace('\\\\', '\\') for m in CWD.finditer(data)]
        if not cwds:
            continue
        first, last = cwds[0], cwds[-1]
        distinct = len(set(cwds))
        cds = [m.group(1).decode('utf-8', 'replace').strip() for m in CD.finditer(data)]
        folder = p.parent.name
        f_first, f_last = enc(first) == folder, enc(last) == folder
        if cds:
            cd_files += 1
        if not f_first:
            moved += 1
            rows_out.append(f'  {p.name[:8]} in {folder[:44]:<44} first-cwd={first[:40]:<40} last-cwd={last[:40]:<40} distinct-cwd={distinct} /cd={len(cds)} folder==last-cwd={f_last}')
        else:
            stayed += 1
print(f'  files whose folder is the first row\'s cwd: {stayed}; whose folder is NOT the first row\'s cwd: {moved}; files recording a /cd: {cd_files}')
print('\n'.join(rows_out[:40]))

print('\n(c) non-transcript files in project folders (indexes?):')
others = defaultdict(int)
for p in root.glob('*/*'):
    if p.is_file() and not UUIDN.match(p.name):
        others[p.suffix or p.name] += 1
print(' ', dict(others))
for p in list(root.glob('*/*.json'))[:3]:
    print('  e.g.', p.parent.name, p.name, p.stat().st_size, 'B')
