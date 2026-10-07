"""The history patch's plugin signal (#8): the prelude sets DCC_PATCH_H when it
runs, and a real build carries it once patched and not before. Read-only on the
real build (in memory); the prelude runs under Node with nothing on disk."""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from dcc_patcher import engine, spec
from dcc_patcher.containers import open_container

H = Path(__file__).resolve().parents[1] / 'patches' / 'H-history-past-compaction' / 'patch.toml'
REAL = os.path.expanduser('~/.local/bin/claude.exe')
NODE = shutil.which('node')
SIGNAL = b'process.env.DCC_PATCH_H="history-v1"'


@pytest.mark.skipif(NODE is None, reason='node is not installed')
def test_running_the_prelude_sets_dcc_patch_h():
    env = {k: v for k, v in os.environ.items() if k != 'DCC_PATCH_H'}
    r = subprocess.run([NODE, '-e', spec.load(H).prelude + ';console.log(process.env.DCC_PATCH_H)'],
                       capture_output=True, text=True, env=env, timeout=60)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == 'history-v1'


@pytest.mark.skipif(not os.path.exists(REAL), reason='no local Claude Code build')
def test_a_patched_build_carries_the_signal_and_stock_does_not():
    exe = open_container(open(REAL, 'rb').read())
    image, (r,) = engine.apply(exe, [spec.load(H)])
    assert SIGNAL not in exe.source(r.module)
    assert SIGNAL in open_container(image).source(r.module)
