"""Preview the region diff on a realistic breakage, in memory (nothing written, nothing
run): take 2.1.289's history module, rewrite the walker's stop the way an upstream
change might (and rename its variables, as every release does), and diff the failing
edit against the last good site from a baseline lock built from the untouched module."""
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from dcc_patcher import diagnose, engine, lock, spec  # noqa: E402
from dcc_patcher.containers import open_container      # noqa: E402

data = open(os.path.expanduser('~/.local/bin/claude.exe'), 'rb').read()
exe = open_container(data)
h = spec.load(ROOT / 'patches' / 'H-history-past-compaction' / 'patch.toml')
baseline = lock.build(data, None, '2.1.289', exe, engine.locate_all(exe, [h]))
walker = next(e for e in baseline['patches'][0]['edits'] if e['name'].startswith('walker'))
before = walker['sites'][0]['before']
print('last good site:', before)

(k,) = exe.find_module(h.module_marker.encode())
text = exe.source(k).decode('latin-1')
m = re.search(r'let ([\w$]+)=([\w$]+)\.parentUuid;if\(!\1\)break;', text)
w, hh = m.group(1), m.group(2)
changed = text.replace(m.group(0), f'let Q9={hh}.parentUuid??{hh}.prevUuid;if(Q9===void 0)break;', 1)

r = engine.locate(h, changed.encode('latin-1'))
bad = next(e for e in r.edits if e.status != engine.APPLIES)
print(r.status, '--', bad.name, bad.status, bad.detail)
e = next(x for x in h.edits if x.name == bad.name)
print('\n'.join(diagnose.diff(changed, before, e.near, e.window)))
