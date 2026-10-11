"""The walker's fallback statement in every saved original: does one pattern match all?"""
import re, sys
from pathlib import Path

ROOT = Path(r'C:\code\claude-projects\dazzle-claude-code-patcher')
sys.path.insert(0, str(ROOT))
from dcc_patcher.containers import open_container  # noqa: E402

PAT = re.compile(r'if\(!(?P<Dw>[\w$]+)\|\|(?P<g>[\w$]+)\.has\((?P=Dw)\.uuid\)\)\{if\((?P=Dw)=(?P<fb>[\w$]+)\((?P<em>[\w$]+),(?P<h>[\w$]+),(?P=g)\),(?P=Dw)\)(?P<tel>[\w$]+)\("tengu_chain_timestamp_fallback",\{\}\)\}')
WALK = re.compile(r'(?P<g>[\w$]+)\.add\((?P<h>[\w$]+)\.uuid\),(?P<s>[\w$]+)\.push\((?P=h)\);let (?P<w>[\w$]+)=(?P=h)\.parentUuid;if\(!(?P=w)\)break;let (?P<Dw>[\w$]+)=(?P<em>[\w$]+)\.get\((?P=w)\);')
for p in sorted((ROOT / 'private' / 'builds').glob('claude-cc-*.exe')):
    exe = open_container(p.read_bytes())
    keys = exe.find_module(b'tengu_chain_parent_cycle')
    text = exe.source(keys[0]).decode('latin-1')
    i = text.find('tengu_chain_parent_cycle')
    win = text[i - 1500:i + 1500]
    m = PAT.search(win); w = WALK.search(win)
    print(f"{p.name:<26} fallback {'match' if m else 'NO MATCH'}  walker {'match' if w else 'NO MATCH'}  "
          f"{'same names' if m and w and (m.group('Dw'), m.group('g'), m.group('em'), m.group('h')) == (w.group('Dw'), w.group('g'), w.group('em'), w.group('h')) else 'NAMES DIFFER'}"
          f"  gap={m.start() - w.end() if m and w else None}")
    if not m:
        j = win.find('tengu_chain_timestamp_fallback')
        print('   ...', win[j - 160:j + 40])
