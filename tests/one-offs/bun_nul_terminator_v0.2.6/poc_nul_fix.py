"""POC: rebuild Claude Code 2.1.309 with the proposed one-byte fix to
PeBunExe.replace_module_source (a NUL terminator after the new source, as Bun's
to_bytes writes with append_count_z), into a scratch builds folder, and run the
replica of Bun's startup check on stock, the shipped build, and the POC build.

The repository is not modified: the fix is monkeypatched onto the class for this
process only, and DCC_BUILDS_DIR points the build at the scratchpad.

Usage: python -P poc_nul_fix.py
"""
import os, struct, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'poc_builds'
OUT.mkdir(exist_ok=True)
os.environ['DCC_BUILDS_DIR'] = str(OUT)
sys.path.insert(0, 'C:/code/claude-projects/dazzle-claude-code-patcher')
sys.path.insert(0, str(HERE))
from dcc_patcher.containers import pe                      # noqa: E402
from dcc_patcher.containers.pe import PeBunExe, OFFSETS_SIZE, RECORD_SIZE, TRAILER   # noqa: E402
from dcc_patcher import cli                                # noqa: E402
import bun_graph_check                                     # noqa: E402

REAL = Path('C:/code/claude-projects/dazzle-claude-code-patcher/private/builds')
STOCK = REAL / 'claude-cc-2.1.309.exe'
SHIPPED = REAL / 'claude-dcc-2.1.309+dcc0.2.5.exe'


def replace_module_source_fixed(self, k, new_source: bytes) -> bytes:
    """As shipped, plus the NUL after the new source that Bun's to_bytes writes
    (append_count_z) and that Bun 9b4284f7's slice_to_z checks for."""
    old = self.data[self.base:self.base + self.byte_count]
    new_off = len(old)
    body_src = new_source + b'\0'                                   # <-- the fix
    payload = bytearray(old + body_src + b'\0' * ((-len(body_src)) % 8))
    offsets = bytearray(self.data[self.offsets_at:self.offsets_at + OFFSETS_SIZE])
    struct.pack_into('<Q', offsets, 0, len(payload))
    payload += offsets + TRAILER
    rec = self.mod_off + k * RECORD_SIZE
    struct.pack_into('<II', payload, rec + 8, new_off, len(new_source))
    struct.pack_into('<I', payload, rec + 28, 0)
    sa, fa = struct.unpack_from('<II', self.data, self.opt + 32)
    _, _, va, _, rptr, hdr = self.bun
    body = struct.pack('<Q', len(payload)) + bytes(payload)
    vsize = len(body)
    rsize = -(-vsize // fa) * fa
    body += b'\0' * (rsize - vsize)
    head = bytearray(self.data[:rptr])
    struct.pack_into('<I', head, hdr + 8, vsize)
    struct.pack_into('<I', head, hdr + 16, rsize)
    struct.pack_into('<I', head, self.opt + 56, -(-(va + vsize) // sa) * sa)
    struct.pack_into('<I', head, self.opt + 64, 0)
    struct.pack_into('<II', head, self.opt + 112 + 8 * 4, 0, 0)
    return bytes(head) + body


if __name__ == '__main__':
    print('stock   :', bun_graph_check.check(STOCK.read_bytes()))
    print('shipped :', bun_graph_check.check(SHIPPED.read_bytes()))
    PeBunExe.replace_module_source = replace_module_source_fixed
    code, built, results = cli.build(str(STOCK))
    print('build   :', code, built, [(r.patch.id, r.ok) for r in results])
    if built:
        data = Path(built).read_bytes()
        print('poc     :', bun_graph_check.check(data))
        x = PeBunExe(data); o = PeBunExe(STOCK.read_bytes())
        edited = [k for k in range(o.count) if o.module(k)['src'] != x.module(k)['src']]
        for k in edited:
            off, n = x.module(k)['src']
            print(f'   module {k}: len {n} len%8={n % 8} byte after=0x{data[x.base + off + n]:02x}')
        print('   size:', len(data), 'vs shipped', SHIPPED.stat().st_size)
