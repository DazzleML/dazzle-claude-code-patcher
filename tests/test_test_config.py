"""scripts/test_config.py on the scenario that matters: it must never move a real
session. A session we did not make -- a real one, or a fork Claude Code made, which
looks the same from outside -- is refused by move-in; a marked or ledgered copy is
moved. Every path the script touches is pointed at tmp_path first, so even a broken
guard can only move files the test created (global rule 1b)."""
import importlib
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


@pytest.fixture
def tc(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    mod = importlib.import_module('test_config')
    home, root = tmp_path / 'home', tmp_path / 'test-config'
    root.mkdir()
    for name, value in (('HOME', home), ('ROOT', root), ('RECORD', root / 'moved-in.tsv'),
                        ('LEDGER', root / 'copies.tsv')):
        monkeypatch.setattr(mod, name, str(value))

    def session(sid, old=True):
        p = home / 'projects' / 'C--proj' / f'{sid}.jsonl'
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('{"sessionId":"%s"}\n' % sid)
        if old:                                   # move-in skips files written in the last 2 minutes
            import os
            os.utime(p, (p.stat().st_atime - 600, p.stat().st_mtime - 600))
        return p
    return mod, session, root


def test_move_in_refuses_a_session_we_did_not_make(tc, capsys):
    mod, session, _ = tc
    real = session('a1b2c3d4-0000-4000-8000-000000000000')
    assert mod.cmd_move_in([real.stem]) == 1
    assert real.exists()
    assert 'refused' in capsys.readouterr().err


def test_move_in_moves_a_marked_copy_and_move_back_restores_it(tc):
    mod, session, root = tc
    ours = session(f'{mod.MARK}-0000-4000-8000-000000000000')
    assert mod.cmd_move_in([ours.stem]) == 0
    moved = root / 'projects' / 'C--proj' / ours.name
    assert moved.exists() and not ours.exists()
    assert mod.cmd_move_back([]) == 0
    assert ours.exists() and not moved.exists()


def test_copy_marks_the_new_id_and_enters_it_in_the_ledger(tc, tmp_path):
    mod, session, root = tc
    src = session('a1b2c3d4-0000-4000-8000-000000000000')
    assert mod.cmd_copy([str(src)]) == 0
    (sid,) = mod.ledger_ids()
    assert sid.startswith(mod.MARK + '-') and (root / 'projects' / 'C--proj' / f'{sid}.jsonl').exists()
    assert src.read_text() == '{"sessionId":"a1b2c3d4-0000-4000-8000-000000000000"}\n'   # original untouched
