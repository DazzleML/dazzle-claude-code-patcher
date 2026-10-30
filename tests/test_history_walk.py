"""Patch H's walk across a compaction boundary, run as the JavaScript that ships.

The prelude (`__dzCross`) and the walker edit's replacement are taken from patch.toml,
the placeholders filled with plain names, and run under Node on small synthetic
session maps shaped like the real files (v0.2.5 design, Ground Truth G3 and G10):

- late-segment: every preserved row reached disk after the summary, already relinked
  onto it, so the head's recorded parent is the summary; the walk must continue from
  the latest row before the boundary in file order (rule 4);
- late-tail: the preserved rows are in place with their original parents and only the
  tail follows the summary; rule 2 still wins and rule 4 is not used;
- idle-last: nothing follows the summary, so the walk reaches the preserved rows from
  their tail and arrives at the head whose in-memory parent is the summary; the walker
  must take the parent the prune recorded (`__dzOrigParent`);
- opening: the file starts with the boundary; the walk ends there without error.

Needs Node. Nothing here touches a real session file or a real build.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from dcc_patcher import spec

H = Path(__file__).resolve().parents[1] / 'dcc_patcher' / 'patches' / 'H-history-past-compaction' / 'patch.toml'
NODE = shutil.which('node')
NAMES = {'g': 'g', 'h': 'h', 's': 's', 'w': 'w', 'Dw': 'D', 'em': 'e', 'fb': 'fb', 'fbargs': 'e,h,g', 'tel': 'tel'}


def row(uuid, type_, parent, **extra):
    return {'uuid': uuid, 'type': type_, 'parentUuid': parent, **extra}


def boundary(uuid, lpu, preserved, anchor):
    return row(uuid, 'system', None, subtype='compact_boundary', logicalParentUuid=lpu,
               compactMetadata={'preservedSegment': {'headUuid': preserved[0], 'anchorUuid': anchor, 'tailUuid': preserved[-1]},
                                'preservedMessages': {'anchorUuid': anchor, 'uuids': list(preserved)}})


# Each fixture: rows in file order (as the loader's Map keeps them, after the prune's
# in-memory relink where it applies), the recorded original parents, and the start row.
FIXTURES = {
    'late-segment': dict(
        rows=[row('m1', 'user', None, cwd='C:\\code'), row('m2', 'assistant', 'm1', cwd='C:\\code\\proj'),
              row('m3', 'user', 'm2', cwd='C:\\code\\proj\\tools'),
              row('x1', 'file-history-snapshot', 'm3'),            # not a chain type
              row('x2', 'user', 'm3', isSidechain=True),            # other side
              boundary('B', 'P3', ['P1', 'P2', 'P3'], 'S'), row('S', 'user', 'B', isCompactSummary=True),
              row('P1', 'assistant', 'S'), row('P2', 'user', 'P1'), row('P3', 'attachment', 'P2'),
              row('n1', 'user', 'P3'), row('n2', 'assistant', 'n1')],
        orig={'P1': 'S'}, start='n2',
        expect=['n2', 'n1', 'P3', 'P2', 'P1', 'S', 'B', 'm3', 'm2', 'm1'], via='file-order'),
    'late-tail': dict(
        rows=[row('m1', 'user', None), row('m2', 'assistant', 'm1'),
              row('P1', 'assistant', 'm2'), row('P2', 'user', 'P1'),
              boundary('B', 'P3', ['P1', 'P2', 'P3'], 'S'), row('S', 'user', 'B', isCompactSummary=True),
              row('P3', 'attachment', 'S'), row('n1', 'user', 'P3')],
        orig={}, start='n1',
        expect=['n1', 'P3', 'S', 'B', 'P2', 'P1', 'm2', 'm1'], via='preserved'),
    'idle-last': dict(
        rows=[row('m1', 'user', None), row('m2', 'assistant', 'm1'),
              row('P1', 'assistant', 'S'), row('P2', 'attachment', 'P1'),      # relinked by the prune
              boundary('B', 'P2', ['P1', 'P2'], 'S'), row('S', 'user', 'B', isCompactSummary=True)],
        orig={'P1': 'm2'}, start='S',
        expect=['S', 'B', 'P2', 'P1', 'm2', 'm1'], via='lpu'),
    'opening': dict(
        rows=[boundary('B', 'P1', ['P1'], 'S'), row('S', 'user', 'B', isCompactSummary=True), row('P1', 'assistant', 'S')],
        orig={'P1': 'S'}, start='P1',
        expect=['P1', 'S', 'B'], via='file-order'),
}


def program():
    patch = spec.load(H)
    walker = next(e for e in patch.edits if e.name.startswith('walker'))
    fragment = re.sub(r'@@(\w+)@@', lambda m: NAMES[m.group(1)], walker.replace)
    assert '@@' not in fragment
    return f'''
{patch.prelude}
const logs=[];globalThis.__dzLog=(m)=>logs.push(m);
function fb(){{return void 0}} function tel(){{}}
function walk(e,start){{let s=[],g=new Set,h=start;while(h){{if(g.has(h.uuid))break;{fragment}h=D}}return s.map(r=>r.uuid)}}
const fx=JSON.parse(require("fs").readFileSync(process.argv[2],"utf8")),out={{}};
for(const [name,f] of Object.entries(fx)){{const e=new Map(f.rows.map(r=>[r.uuid,r]));globalThis.__dzOrigParent=f.orig;logs.length=0;out[name]={{chain:walk(e,e.get(f.start)),logs:[...logs]}}}}
process.stdout.write(JSON.stringify(out));
'''


@pytest.fixture(scope='module')
def walked(tmp_path_factory):
    if NODE is None:
        pytest.skip('node is not installed')
    d = tmp_path_factory.mktemp('walk')
    (d / 'walk.js').write_text(program(), encoding='utf-8')
    (d / 'fx.json').write_text(json.dumps(FIXTURES), encoding='utf-8')
    r = subprocess.run([NODE, str(d / 'walk.js'), str(d / 'fx.json')], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.parametrize('name', list(FIXTURES))
def test_walk_reaches_the_first_message(walked, name):
    assert walked[name]['chain'] == FIXTURES[name]['expect']


@pytest.mark.parametrize('name', list(FIXTURES))
def test_the_rule_used_is_the_one_the_shape_calls_for(walked, name):
    at_boundary = [l for l in walked[name]['logs'] if l.startswith('walk: boundary')]
    assert len(at_boundary) == 1
    assert f'via={FIXTURES[name]["via"]}' in at_boundary[0]


def test_rule_four_skips_other_sides_and_non_chain_rows(walked):
    chain = walked['late-segment']['chain']
    assert 'x1' not in chain and 'x2' not in chain


def test_the_relinked_head_takes_the_recorded_parent(walked):
    assert any(l.startswith('walk: relinked head P1 -> m2') for l in walked['idle-last']['logs'])
