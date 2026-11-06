"""Patch J's sibling search (#6), run under Node on synthetic session files in
tmp_path, on the scenarios that matter: a continued session pulls in the parent
file's lines up to the message it points at, and no further; a grandparent is
reached too; a missing parent or a damaged file stops quietly. Plus H and J
applying together to the real build, in memory.

No real session file is read: the "sessions" are a few JSON lines written here.
Skipped when Node is not installed."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from dcc_patcher import engine, spec
from dcc_patcher.containers import open_container

ROOT = Path(__file__).resolve().parents[1]
J = ROOT / 'dcc_patcher' / 'patches' / 'J-history-across-files' / 'patch.toml'
H = ROOT / 'dcc_patcher' / 'patches' / 'H-history-past-compaction' / 'patch.toml'
REAL = os.path.expanduser('~/.local/bin/claude.exe')
NODE = shutil.which('node')
needs_node = pytest.mark.skipif(NODE is None, reason='node is not installed')


def boundary(uuid, lpu):
    return {'type': 'system', 'subtype': 'compact_boundary', 'uuid': uuid, 'parentUuid': None,
            'logicalParentUuid': lpu}


def msg(uuid, parent=None):
    return {'type': 'user', 'uuid': uuid, 'parentUuid': parent, 'message': {'content': uuid}}


def write(path: Path, rows, mtime=None):
    # compact, as Claude Code writes them (JSON.stringify): the search keys on '"uuid":"<id>"'
    path.write_text(''.join((r if isinstance(r, str) else json.dumps(r, separators=(',', ':'))) + '\n'
                            for r in rows), encoding='utf-8')
    if mtime:
        os.utime(path, (mtime, mtime))
    return path


def siblings(tmp_path, session: Path) -> list[str]:
    """The uuids J's prelude hands to the loader for `session`, in order."""
    harness = tmp_path / 'harness.mjs'
    harness.write_text('import {createRequire} from "module";\n'
                       'import.meta.require = createRequire(import.meta.url);\n'
                       + spec.load(J).prelude + '\n'
                       'const out = []; globalThis.__dzSiblings(process.argv[2], (e) => out.push(e.uuid));\n'
                       'console.log(JSON.stringify(out));\n', encoding='utf-8')
    r = subprocess.run([NODE, str(harness), str(session)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@needs_node
def test_a_continued_session_gets_the_parent_file_up_to_the_message_it_points_at(tmp_path):
    folder = tmp_path / 'project'
    folder.mkdir()
    write(folder / 'parent.jsonl', [msg('p1'), msg('p2', 'p1'), msg('p3', 'p2'), msg('p4', 'p3')])
    write(folder / 'other.jsonl', [msg('x1')])
    child = write(folder / 'child.jsonl', [boundary('c0', 'p3'), msg('c1', 'c0')])
    assert siblings(tmp_path, child) == ['p1', 'p2', 'p3']           # p4 came after the fork


@needs_node
def test_a_grandparent_session_is_reached_through_the_parent(tmp_path):
    folder = tmp_path / 'project'
    folder.mkdir()
    write(folder / 'grand.jsonl', [msg('g1'), msg('g2', 'g1'), msg('g3', 'g2')])
    write(folder / 'parent.jsonl', [boundary('p0', 'g2'), msg('p1', 'p0'), msg('p2', 'p1')])
    child = write(folder / 'child.jsonl', [boundary('c0', 'p2'), msg('c1', 'c0')])
    assert siblings(tmp_path, child) == ['g1', 'g2', 'p0', 'p1', 'p2']


@needs_node
def test_a_missing_parent_or_a_damaged_file_stops_quietly(tmp_path):
    folder = tmp_path / 'project'
    folder.mkdir()
    child = write(folder / 'child.jsonl', [boundary('c0', 'gone'), msg('c1', 'c0')])
    assert siblings(tmp_path, child) == []                           # the parent is gone
    assert siblings(tmp_path, folder / 'no-such-session.jsonl') == []
    write(folder / 'parent.jsonl', ['{not json', msg('p1'), msg('p2', 'p1')])
    child.write_text(child.read_text().replace('"gone"', '"p2"'))
    assert siblings(tmp_path, child) == ['p1', 'p2']                 # a damaged line is skipped


@pytest.mark.skipif(not os.path.exists(REAL), reason='no local Claude Code build')
def test_history_and_cross_file_patches_apply_together_to_the_real_build():
    exe = open_container(open(REAL, 'rb').read())
    image, results = engine.apply(exe, [spec.load(H), spec.load(J)])   # verify() runs inside
    assert image is not None and [r.status for r in results] == ['applies', 'applies']
    k = results[1].module
    src = open_container(image).source(k)
    assert b'globalThis.__dzSiblings?.(' in src and b'/*dazzle-claude-code:history-v1*/' in src


# The loader's head as each build writes it. 2.1.319 put a local before the map
# maker's, gave the maker a second argument, and opened a resume-head block between
# the destructure and precede(); the edit must take both shapes and change neither.
LOADER_HEADS = {
    'through-2.1.318': (
        'async function Wle(e,n){let r=yFt(n?.keepAllLeaves??!1),{processEntry:s,artifactCommentMonitors:h,'
        'artifactAutoReactLedgers:y}=r;r.precede(n?.precedingEntries??[]);', 's'),
    '2.1.319': (
        'async function aZ(e,n){let r=n?.resumeHeadTrial,s=VUt(n?.keepAllLeaves??!1,r!==void 0),{processEntry:h,'
        'artifactCommentMonitors:y,artifactAutoReactLedgers:S}=s,w=n?.resumeHead?QBt():void 0,N;'
        'if(w==="verify"&&n?.precedingEntries?.length)try{N=Ri(n.precedingEntries)}catch(ve){N=F(ve)}'
        's.precede(n?.precedingEntries??[]);', 'h'),
}


@pytest.mark.parametrize('shape', list(LOADER_HEADS))
def test_the_loader_edit_keeps_the_head_as_written_and_appends_the_sibling_call(shape):
    head, add = LOADER_HEADS[shape]
    source = ('function other(){return 1}' + head + 'let S=De(process.env.X);return r.finish()}').encode()
    res = engine.locate(spec.load(J), source)
    assert res.status == 'applies', res.detail
    (site,) = res.edits[0].sites
    assert site.before == head                                         # nothing of the head is lost
    assert site.after == head + f'globalThis.__dzSiblings?.(e,{add});'


def test_every_file_that_names_ojura_credits_it():
    named = [p for p in ROOT.joinpath('dcc_patcher').rglob('*')          # the patches live in the package
             if p.is_file() and p.suffix in ('.py', '.toml', '.md') and 'ojura' in p.read_text(encoding='utf-8')]
    assert named and all('Derived from ojura/claude-patches' in p.read_text(encoding='utf-8') for p in named)
