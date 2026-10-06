"""The PE container, on the scenarios that matter (minimal, scenario-led: goal
addendum 2026-10-05 13:13). The real-build tests read ~/.local/bin/claude.exe only
and work in memory: nothing is written and nothing is run."""
import os
import struct

import pytest

from dcc_patcher.containers import ContainerError, open_container

REAL = os.path.expanduser('~/.local/bin/claude.exe')
MARKER = b'tengu_chain_parent_cycle'
needs_real = pytest.mark.skipif(not os.path.exists(REAL), reason='no local Claude Code build')


@pytest.fixture(scope='module')
def real():
    with open(REAL, 'rb') as f:
        return open_container(f.read())


@needs_real
def test_a_real_build_parses_and_a_replacement_verifies(real):
    (k,) = real.find_module(MARKER)
    new = real.source(k) + b'\n//dcc'
    image = real.replace_module_source(k, new)
    real.verify(image, k, new)                      # raises on any mismatch
    assert open_container(image).module(k)['bytecode'][1] == 0


@needs_real
def test_verify_refuses_an_image_where_another_module_changed(real):
    (k,) = real.find_module(MARKER)
    new = real.source(k) + b'\n//dcc'
    image = bytearray(real.replace_module_source(k, new))
    other = 0 if k != 0 else 1
    o, n = real.module(other)['src']
    image[real.base + o] ^= 0x01                    # flip one byte of another module's source
    with pytest.raises(ContainerError, match='other modules changed'):
        real.verify(bytes(image), k, new)


def test_a_pe_without_a_bun_section_is_refused_clearly():
    data = bytearray(0x400)
    data[:2] = b'MZ'
    struct.pack_into('<I', data, 0x3c, 0x80)
    data[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<H', data, 0x80 + 6, 1)       # one section
    struct.pack_into('<H', data, 0x80 + 20, 240)    # optional header size
    struct.pack_into('<H', data, 0x80 + 24, 0x20b)  # PE32+
    sec = 0x80 + 24 + 240
    data[sec:sec + 8] = b'.text\0\0\0'
    struct.pack_into('<IIII', data, sec + 8, 0x10, 0x1000, 0x10, 0x200)
    with pytest.raises(ContainerError, match='no .bun section'):
        open_container(bytes(data))
