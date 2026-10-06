"""The `inspect` command, on the scenarios that matter: an unsupported file is
refused cleanly (AC11), and a real build is described. Read-only throughout."""
import os

import pytest

from dcc_patcher.cli import main

REAL = os.path.expanduser('~/.local/bin/claude.exe')


def test_inspect_refuses_an_unsupported_file_with_exit_2(tmp_path, capsys):
    f = tmp_path / 'not-an-exe.bin'
    f.write_bytes(b'\x7fELF' + b'\0' * 60)
    assert main(['inspect', str(f)]) == 2
    err = capsys.readouterr().err
    assert 'unsupported format: ELF' in err
    assert 'Traceback' not in err


@pytest.mark.skipif(not os.path.exists(REAL), reason='no local Claude Code build')
def test_inspect_describes_a_real_build(capsys):
    assert main(['inspect', REAL, '--marker', 'tengu_chain_parent_cycle']) == 0
    out = capsys.readouterr().out
    assert 'format:   pe' in out
    assert 'marker:   [' in out
