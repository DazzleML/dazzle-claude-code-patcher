"""The history patch's first edit, on the loader as each build writes it (scenario-led).

The loader reads one switch, CLAUDE_CODE_DISABLE_PRECOMPACT_SKIP, into a local; when
it is on, the lines before the last compaction are parsed like any others. The edit
turns that local on. Builds have read the switch two ways (through process.env until
2.1.329, through a settings object from 2.1.330), and from 2.1.319 a second function
tests the same switch inline: that one decides where a tail load starts, and the edit
must leave it alone."""
import re
from pathlib import Path

import pytest

from dcc_patcher import spec

ROOT = Path(__file__).resolve().parents[1]
EDIT = spec.load(ROOT / 'dcc_patcher' / 'patches' / 'H-history-past-compaction' / 'patch.toml').edits[0]

# The tail-load function's inline test of the same switch (2.1.319 on).
INLINE = 'async function Lmi(e){if(Rsn()!=="on"||s.CLAUDE_CODE_DISABLE_PRECOMPACT_SKIP||X()||vl())return 0;}'

# (source, the source the edit must leave behind)
LOADERS = {
    'through-2.1.318': (
        'r.precede(n?.precedingEntries??[]);let S=De(process.env.CLAUDE_CODE_DISABLE_PRECOMPACT_SKIP);if(Q())x();',
        'r.precede(n?.precedingEntries??[]);let S=!0;if(Q())x();'),
    '2.1.329': (
        INLINE + 'g.precede(o?.precedingEntries??[]);let z=Oe(process.env.CLAUDE_CODE_DISABLE_PRECOMPACT_SKIP),'
        'Y=Vc().skipsUnusedRows()?(xe)=>g.messages.has(xe):void 0;',
        INLINE + 'g.precede(o?.precedingEntries??[]);let z=!0,'
        'Y=Vc().skipsUnusedRows()?(xe)=>g.messages.has(xe):void 0;'),
    '2.1.330': (
        INLINE + 'g.precede(o?.precedingEntries??[]);let z=s.CLAUDE_CODE_DISABLE_PRECOMPACT_SKIP,'
        'Y=rf().skipsUnusedRows()?(Oe)=>g.messages.has(Oe):void 0;',
        INLINE + 'g.precede(o?.precedingEntries??[]);let z=!0,'
        'Y=rf().skipsUnusedRows()?(Oe)=>g.messages.has(Oe):void 0;'),
}


@pytest.mark.parametrize('build', LOADERS)
def test_the_loader_switch_is_turned_on_and_the_tail_load_test_is_left_alone(build):
    # CONSEQUENCE: 8 -- without this edit the lines before the last compaction are
    # never parsed and the whole history patch does nothing (and fails closed)
    source, want = LOADERS[build]
    pattern = re.compile(EDIT.pattern)
    assert len(pattern.findall(source)) == 1
    assert pattern.sub(lambda m: EDIT.replace, source) == want
