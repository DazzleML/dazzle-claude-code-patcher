"""`check`, on the scenarios that matter (minimal, scenario-led): a build where every
edit applies passes (AC1); when the code at a site changes, the failing edit names
itself and shows a region diff against the last good build's lockfile, with renames
normalised away; a run over several files survives one it can't read (AC2: no
traceback). Synthetic executables live under tmp_path and are never run."""
import os

import pytest

from dcc_patcher import cli
from tests.bunfixture import make_exe
from tests.test_engine import SOURCE, SPEC

REAL = os.path.expanduser('~/.local/bin/claude.exe')


@pytest.fixture
def spec_path(tmp_path):
    p = tmp_path / 'patch.toml'
    p.write_text(SPEC)
    return p


def test_a_changed_site_is_named_and_diffed_against_the_last_good_build(tmp_path, spec_path, capsys):
    good, bad = tmp_path / 'good.exe', tmp_path / 'bad.exe'
    good.write_bytes(make_exe([SOURCE]))
    # The next "release": names renamed (should not show) and the stop rewritten (should).
    bad.write_bytes(make_exe([SOURCE.replace(b'let w=h.parentUuid;if(!w)break;',
                                             b'let q=k.parentUuid;if(q===void 0)break;')]))
    locks = tmp_path / 'locks'
    assert cli.main(['check', str(good), '--patch', str(spec_path), '--lock-out', str(locks)]) == 0
    (baseline,) = locks.iterdir()
    capsys.readouterr()
    assert cli.main(['check', str(bad), '--patch', str(spec_path), '--baseline', str(baseline)]) == 1
    out = capsys.readouterr().out
    assert 'MISSING' in out and 'walker' in out and '--- last good' in out
    assert '+if(_===void 0)break;' in out and '-if(!_)break;' in out
    assert '-let _=_.parentUuid;' not in out          # the rename alone is not a change


def test_a_rename_inside_a_spread_is_not_a_change():
    # Seen on the 2.1.289 -> 2.1.290 update: `{...Ee,` became `{...be,`.
    from dcc_patcher.diagnose import normalise
    old = 'Ee.parentUuid!==null&&ye.has(Ee.parentUuid))e.set(be,{...Ee,parentUuid:he})'
    new = 'be.parentUuid!==null&&_e.has(be.parentUuid))e.set(ke,{...be,parentUuid:he})'
    assert normalise(old) == normalise(new)
    assert normalise('a.parentUuid') == '_.parentUuid'      # a real property stays itself


def test_check_over_several_files_survives_one_it_cannot_read(tmp_path, spec_path, capsys):
    (tmp_path / 'a.exe').write_bytes(make_exe([SOURCE]))
    (tmp_path / 'b.exe').write_bytes(b'\x7fELF' + b'\0' * 60)
    assert cli.main(['check', str(tmp_path / '*.exe'), '--patch', str(spec_path)]) == 2
    out, err = capsys.readouterr()
    assert 'T  applies' in out and 'unsupported format: ELF' in err and 'Traceback' not in err


@pytest.mark.skipif(not os.path.exists(REAL), reason='no local Claude Code build')
def test_every_history_edit_applies_to_the_real_build(capsys):                    # AC1
    assert cli.main(['check', REAL]) == 0
    out = capsys.readouterr().out
    assert 'H  applies' in out and 'MISSING' not in out and 'AMBIGUOUS' not in out
    assert out.count('V [module') == 2 and 'needs-human' not in out
