"""Write the history module (tengu_chain_parent_cycle) of each named build next to this
script, and report size thresholds and a few markers in each."""
import re, sys
from pathlib import Path

ROOT = Path(r'C:\code\claude-projects\dazzle-claude-code-patcher')
sys.path.insert(0, str(ROOT))
from dcc_patcher.containers import open_container  # noqa: E402

out = Path(__file__).parent
for arg in sys.argv[1:]:
    data = Path(arg).read_bytes()
    exe = open_container(data)
    keys = exe.find_module(b'tengu_chain_parent_cycle')
    print(arg, 'modules with marker:', keys)
    for k in keys:
        text = exe.source(k).decode('latin-1')
        dst = out / (Path(arg).stem + f'.history-{k}.js')
        dst.write_text(text, encoding='latin-1')
        print('  wrote', dst.name, len(text), 'bytes')
        for pat in (r'\d+\*1024\*1024', r'\d{6,}', r'CLAUDE_CODE_DISABLE_PRECOMPACT_SKIP', r'logicalParentUuid', r'compact_boundary',
                    r'__dzCross', r'DCC_PATCH_H', r'\.size\b', r'statSync', r'truncat', r'MAX_[A-Z_]+', r'slice\(-\d+\)'):
            hits = [m.start() for m in re.finditer(pat, text)]
            if hits:
                print(f'   {pat!r}: {len(hits)}x  e.g. ...{text[max(0,hits[0]-60):hits[0]+80]!r}')
