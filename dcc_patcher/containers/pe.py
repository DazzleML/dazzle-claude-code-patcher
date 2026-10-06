"""Read and rewrite the Bun standalone module graph inside a Windows claude.exe.

Layout (verified against Claude Code 2.1.289, 2026-10-05):
  - the graph lives in the PE section named `.bun`, the last section in the file;
  - the section starts with a u64 payload length, then the payload;
  - the payload ends with an Offsets struct (32 bytes) and the trailer
    "\\n---- Bun! ----\\n"; Offsets = byte_count u64, modules (offset u32, length u32),
    entry_point_id u32, then 12 more bytes kept as-is;
  - the module table is an array of 52-byte records; the first four fields are
    (offset u32, length u32) pointers into the payload: name, source, sourcemap,
    bytecode;
  - a module whose bytecode length is 0 is compiled from its source at load
    (proved by poc/t3_fallback.py: src+nobc printed the edited string).

Moved from poc/bunexe.py (2026-10-05) and adapted to the Container interface: the
proof of concept's asserts became ContainerError, which survives `python -O`.
"""
import struct

from . import ContainerError

TRAILER = b'\n---- Bun! ----\n'
OFFSETS_SIZE = 32
RECORD_SIZE = 52


def _require(condition, message):
    if not condition:
        raise ContainerError(message)


class PeBunExe:
    format = 'pe'

    def __init__(self, data: bytes):
        self.data = data
        try:
            pe = struct.unpack_from('<I', data, 0x3c)[0]
            self.opt = pe + 24
            nsec = struct.unpack_from('<H', data, pe + 6)[0]
            opt_size = struct.unpack_from('<H', data, pe + 20)[0]
            _require(struct.unpack_from('<H', data, self.opt)[0] == 0x20b, 'expected a 64-bit (PE32+) executable')
            table = self.opt + opt_size
            self.sections = []
            for i in range(nsec):
                h = table + 40 * i
                name, vsize, va, rsize, rptr = struct.unpack_from('<8sIIII', data, h)
                self.sections.append((name.rstrip(b'\0'), vsize, va, rsize, rptr, h))
        except struct.error as e:
            raise ContainerError(f'truncated PE headers: {e}') from None
        bun = [s for s in self.sections if s[0] == b'.bun']
        _require(len(bun) == 1, 'no .bun section: not a Bun-compiled executable')
        self.bun = bun[0]
        _require(max(self.sections, key=lambda s: s[2])[0] == b'.bun', '.bun is not the last section by address')
        _require(max(self.sections, key=lambda s: s[4])[0] == b'.bun', '.bun is not the last section in the file')
        rptr = self.bun[4]
        self.base = rptr + 8
        self.payload_len = struct.unpack_from('<Q', data, rptr)[0]
        end = self.base + self.payload_len
        _require(data[end - len(TRAILER):end] == TRAILER, 'Bun trailer not found at the end of the .bun payload')
        self.offsets_at = end - len(TRAILER) - OFFSETS_SIZE
        self.byte_count = struct.unpack_from('<Q', data, self.offsets_at)[0]
        _require(self.byte_count == self.offsets_at - self.base, 'Bun byte_count does not match the layout')
        self.mod_off, self.mod_len = struct.unpack_from('<II', data, self.offsets_at + 8)
        _require(self.mod_len % RECORD_SIZE == 0, 'Bun module table is not a whole number of records')
        self.count = self.mod_len // RECORD_SIZE
        # The last 12 bytes of the Offsets struct, kept as-is. In ojura/claude-patches'
        # ELF handler the flags word says which extra record tables exist (source
        # hashes, module info); reported by `inspect` so a build that adds one shows.
        self.flags = struct.unpack_from('<I', data, self.offsets_at + 28)[0]

    def module(self, k):
        f = struct.unpack_from('<8I', self.data, self.base + self.mod_off + k * RECORD_SIZE)
        name = self.data[self.base + f[0]:self.base + f[0] + f[1]].decode()
        return {'index': k, 'name': name, 'src': (f[2], f[3]), 'bytecode': (f[6], f[7])}

    def source(self, k):
        o, n = self.module(k)['src']
        return self.data[self.base + o:self.base + o + n]

    def find_module(self, marker: bytes):
        return [k for k in range(self.count) if marker in self.source(k)]

    def replace_module_source(self, k, new_source: bytes) -> bytes:
        """A new exe image: module k's source appended to the payload, its bytecode
        dropped, the .bun section grown to fit, and the Authenticode table removed
        (any edit invalidates the signature anyway)."""
        old = self.data[self.base:self.base + self.byte_count]
        new_off = len(old)
        payload = bytearray(old + new_source + b'\0' * ((-len(new_source)) % 8))
        offsets = bytearray(self.data[self.offsets_at:self.offsets_at + OFFSETS_SIZE])
        struct.pack_into('<Q', offsets, 0, len(payload))
        payload += offsets + TRAILER
        rec = self.mod_off + k * RECORD_SIZE
        struct.pack_into('<II', payload, rec + 8, new_off, len(new_source))
        struct.pack_into('<I', payload, rec + 28, 0)  # bytecode length

        sa, fa = struct.unpack_from('<II', self.data, self.opt + 32)
        _, _, va, _, rptr, hdr = self.bun
        body = struct.pack('<Q', len(payload)) + bytes(payload)
        vsize = len(body)
        rsize = -(-vsize // fa) * fa
        body += b'\0' * (rsize - vsize)

        head = bytearray(self.data[:rptr])
        struct.pack_into('<I', head, hdr + 8, vsize)
        struct.pack_into('<I', head, hdr + 16, rsize)
        struct.pack_into('<I', head, self.opt + 56, -(-(va + vsize) // sa) * sa)  # SizeOfImage
        struct.pack_into('<I', head, self.opt + 64, 0)                             # CheckSum
        struct.pack_into('<II', head, self.opt + 112 + 8 * 4, 0, 0)               # security dir
        return bytes(head) + body

    def verify(self, new_image: bytes, k: int, new_source: bytes) -> None:
        """Raise ContainerError unless new_image holds new_source for module k (with
        its bytecode dropped) and every other module byte-identical to this one.
        Moved from poc/patch_history.py's post-build checks."""
        check = PeBunExe(new_image)
        _require(check.count == self.count, f'module count changed: {self.count} -> {check.count}')
        _require(check.source(k) == new_source, f'module {k} does not hold the new source')
        _require(check.module(k)['bytecode'][1] == 0, f'module {k} still has bytecode')
        changed = [j for j in range(self.count)
                   if j != k and (check.module(j) != self.module(j) or check.source(j) != self.source(j))]
        _require(not changed, f'other modules changed: {changed[:5]}')
