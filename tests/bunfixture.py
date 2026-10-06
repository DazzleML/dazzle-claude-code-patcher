"""A tiny synthetic Bun standalone executable (PE32+), for tests that must run
without a real Claude Code build: two sections, `.text` and `.bun`, with the module
graph laid out as dcc_patcher.containers.pe reads it. It is never run."""
import struct

TRAILER = b'\n---- Bun! ----\n'
RECORD = 52


def make_exe(sources: list[bytes]) -> bytes:
    blobs, records = bytearray(), []
    for i, src in enumerate(sources):
        name = f'mod{i}.js'.encode()
        name_at = len(blobs)
        blobs += name
        src_at = len(blobs)
        blobs += src
        records.append((name_at, len(name), src_at, len(src)))
    mod_off = len(blobs)
    for name_at, name_len, src_at, src_len in records:
        blobs += struct.pack('<8I', name_at, name_len, src_at, src_len, 0, 0, 0, 0) + b'\0' * (RECORD - 32)
    offsets = struct.pack('<QIIIIII', len(blobs), mod_off, len(records) * RECORD, 0, 0, 0, 0x1bff)
    payload = bytes(blobs) + offsets + TRAILER
    body = struct.pack('<Q', len(payload)) + payload
    rsize = -(-len(body) // 0x200) * 0x200

    head = bytearray(0x600)
    head[:2] = b'MZ'
    struct.pack_into('<I', head, 0x3c, 0x80)
    head[0x80:0x84] = b'PE\0\0'
    struct.pack_into('<HH', head, 0x84, 0x8664, 2)       # machine, two sections
    struct.pack_into('<H', head, 0x80 + 20, 240)          # optional header size
    opt = 0x98
    struct.pack_into('<H', head, opt, 0x20b)              # PE32+
    struct.pack_into('<II', head, opt + 32, 0x1000, 0x200)  # section, file alignment
    struct.pack_into('<I', head, opt + 56, 0x2000 + -(-len(body) // 0x1000) * 0x1000)
    table = opt + 240
    head[table:table + 8] = b'.text\0\0\0'
    struct.pack_into('<IIII', head, table + 8, 0x10, 0x1000, 0x200, 0x400)
    head[table + 40:table + 48] = b'.bun\0\0\0\0'
    struct.pack_into('<IIII', head, table + 48, len(body), 0x2000, rsize, 0x600)
    return bytes(head[:0x600]) + body + b'\0' * (rsize - len(body))
