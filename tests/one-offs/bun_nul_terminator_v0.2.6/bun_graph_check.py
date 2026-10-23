"""Replicate the per-module part of Bun's startup check of a compiled module graph
(src/standalone_graph/StandaloneModuleGraph.rs at 9b4284f7, PR #46021, the version
Claude Code 2.1.308 and 2.1.309 carry; reverted in Bun by #46461 on 2026-10-22).

Checks, in Bun's order, stopping at the first failure as Bun does:
  byte_count <= raw_len                       -> "byte count is out of range"
  module list slice in [0, raw_len)           -> "module list is out of range"
  per module (in table order):
    name:      offset+len+1 <= raw_len and the byte after is NUL  -> "module name is out of range"
    contents:  same                                                -> "module contents are out of range"
    sourcemap: same, when length > 0                               -> "module source map is out of range"
    bytecode:  offset+len <= raw_len (no terminator)               -> "module bytecode is out of range"
The optional records after the module table (source hashes etc.) are not replicated:
dcc-patcher never moves them. raw_len is the .bun payload length (the u64 before it).

Usage: python -I bun_graph_check.py <exe> [...]
"""
import struct, sys
sys.path.insert(0, 'C:/code/claude-projects/dazzle-claude-code-patcher')
from dcc_patcher.containers.pe import PeBunExe, RECORD_SIZE


def check(data: bytes) -> str:
    x = PeBunExe(data)
    raw_len = x.payload_len
    base = x.base
    if x.byte_count > raw_len:
        return 'byte count is out of range'
    if x.mod_off + x.mod_len > raw_len:
        return 'module list is out of range'

    def z(off, n):
        return n == 0 or (off + n + 1 <= raw_len and data[base + off + n] == 0)

    for k in range(x.count):
        f = struct.unpack_from('<8I', data, base + x.mod_off + k * RECORD_SIZE)
        name = data[base + f[0]:base + f[0] + f[1]].decode(errors='replace')
        if not z(f[0], f[1]):
            return f'module name is out of range (module {k} {name!r})'
        if not z(f[2], f[3]):
            return f'module contents are out of range (module {k} {name!r}: contents {f[2]}+{f[3]}, byte after 0x{data[base + f[2] + f[3]]:02x})'
        if not z(f[4], f[5]):
            return f'module source map is out of range (module {k} {name!r})'
        if f[7] and f[6] + f[7] > raw_len:
            return f'module bytecode is out of range (module {k} {name!r})'
    return 'ok'


if __name__ == '__main__':
    for p in sys.argv[1:]:
        print(f'{p}: {check(open(p, "rb").read())}')
