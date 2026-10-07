"""The engine and `apply`, on the scenarios that matter (minimal, scenario-led: goal
addendum 2026-10-05 13:13): the history patch applies to the real build; applying
twice is a no-op (AC4); a missing anchor fails
closed with nothing written (AC5); an upstream fix is recognised (AC9); two sites
of one edit keep their own names; the input is never overwritten.

The synthetic executable is written only under tmp_path and never run. Real-build
tests read ~/.local/bin/claude.exe in memory and are skipped when it is absent."""
import os
import re
import tomllib
from pathlib import Path

import pytest

from dcc_patcher import cli, engine, spec
from dcc_patcher.containers import open_container
from tests.bunfixture import make_exe

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT / 'dcc_patcher' / 'patches' / 'H-history-past-compaction' / 'patch.toml'
REAL = os.path.expanduser('~/.local/bin/claude.exe')
needs_real = pytest.mark.skipif(not os.path.exists(REAL), reason='no local Claude Code build')

SPEC = r'''
format = 1
id = "T"
title = "test patch"
module_marker = "MARK"
signature = "/*dcc-test*/"
[upstream_fixed]
near = "MARK"
pattern = 'fixedUpstream'
[[edit]]
name = "walker"
near = "MARK"
window = 200
pattern = 'let (?P<w>\w+)=(?P<h>\w+)\.parentUuid;if\(!(?P=w)\)break;'
replace = 'let @@w@@=@@h@@.parentUuid;if(!@@w@@)@@w@@=cross(@@h@@);if(!@@w@@)break;'
[[edit]]
name = "two sites"
pattern = '!(?P<n>\w+)\.keep&&(?P<buf>\w+)\.length>9\)'
replace = '!1&&@@buf@@.length>9)'
expect = 2
'''
SOURCE = b'/*MARK*/let w=h.parentUuid;if(!w)break;if(!o.keep&&D.length>9)x();if(!o.keep&&Ce.length>9)y();'


@pytest.fixture
def world(tmp_path):
    def build(source=SOURCE):
        exe = tmp_path / 'claude.exe'
        exe.write_bytes(make_exe([b'other();', source]))
        return exe
    spec_path = tmp_path / 'patch.toml'
    spec_path.write_text(SPEC)
    return build, spec_path, tmp_path


def run(*argv):
    return cli.main([str(a) for a in argv])


def test_two_sites_of_one_edit_keep_their_own_names():
    r = engine.locate(spec.parse(tomllib.loads(SPEC)), SOURCE)
    assert r.status == 'applies'
    assert b'!1&&D.length>9)x()' in r.source and b'!1&&Ce.length>9)y()' in r.source


def test_applying_to_its_own_output_is_a_no_op(world, capsys):          # AC4
    build, spec_path, tmp = world
    assert run('apply', build(), '-o', tmp / 'out.exe', '--patch', spec_path) == 0
    assert (tmp / 'out.exe.dcc-lock.json').exists()
    assert run('apply', tmp / 'out.exe', '-o', tmp / 'again.exe', '--patch', spec_path) == 0
    assert 'already-applied' in capsys.readouterr().out
    assert not (tmp / 'again.exe').exists()


def test_a_missing_anchor_fails_closed_and_writes_nothing(world, capsys):  # AC5
    build, spec_path, tmp = world
    exe = build(SOURCE.replace(b'if(!w)break;', b''))
    assert run('apply', exe, '-o', tmp / 'out.exe', '--patch', spec_path) == 1
    out, err = capsys.readouterr()
    assert re.search(r'MISSING\s+x0\s+walker', out) and 'nothing written' in err
    assert not (tmp / 'out.exe').exists()


def test_apply_never_writes_over_its_input(world):
    build, spec_path, _ = world
    exe = build()
    before = exe.read_bytes()
    assert run('apply', exe, '-o', exe, '--patch', spec_path) == 2
    assert exe.read_bytes() == before


def test_a_two_module_patch_labels_both_and_reapplying_is_a_no_op():
    # The version label: its edit rewrites its own marker, so a patched module is
    # found again by its signature; @@dcc_version@@ is filled in by the engine.
    label = spec.parse({'format': 1, 'id': 'V', 'title': 'v', 'module_marker': '(Claude Code)',
                        'modules': 2, 'signature': '/*v*/',
                        'edit': [{'name': 'label', 'pattern': r'\.VERSION\} \(Claude Code\)',
                                  'replace': '.VERSION} + dcc @@dcc_version@@ (Dazzle Claude Code)'}]})
    exe = open_container(make_exe([b'a(`${X.VERSION} (Claude Code)`)', b'other()',
                                   b'b(`${X.VERSION} (Claude Code)`,"-v")']))
    image, results = engine.apply(exe, [label])
    assert [r.module for r in results] == [0, 2] and image is not None
    out = open_container(image)
    want = f'.VERSION}} + dcc {engine.DISPLAY_VERSION} (Dazzle Claude Code)'.encode()
    assert want in out.source(0) and want in out.source(2) and out.source(1) == b'other()'
    again, results = engine.apply(out, [label])
    assert again is None and [r.status for r in results] == ['already-applied'] * 2


def test_an_edit_found_more_often_than_expected_fails_closed():
    # The walker shape twice (the code changed): neither copy may be patched.
    walker = b'let w=h.parentUuid;if(!w)break;'
    r = engine.locate(spec.parse(tomllib.loads(SPEC)), SOURCE.replace(walker, walker * 2))
    assert r.status == 'needs-human' and r.source is None
    assert (r.edits[0].status, r.edits[0].count) == ('AMBIGUOUS', 2)


def test_the_history_patch_recognises_an_upstream_fix():                  # AC9
    source = b'x();tengu_chain_parent_cycle;let w=h.parentUuid??h.logicalParentUuid;'
    r = engine.locate(spec.load(HISTORY), source)
    assert r.status == 'upstream-fixed' and r.source is None and not r.edits


def test_a_vanished_landmark_is_not_mistaken_for_an_upstream_fix():
    # The detector's word appears elsewhere, but the walker's landmark is gone:
    # that is a broken patch to report, not one to retire.
    r = engine.locate(spec.load(HISTORY), b'x();let a=m.logicalParentUuid;')
    assert r.status == 'needs-human'


@needs_real
def test_the_history_patch_applies_to_the_real_build():                   # AC1, in memory
    exe = open_container(open(REAL, 'rb').read())
    image, (r,) = engine.apply(exe, [spec.load(HISTORY)])                 # verify() runs inside
    assert r.status == 'applies' and image is not None
    assert [e.count for e in r.edits] == [e.expect for e in r.patch.edits]
