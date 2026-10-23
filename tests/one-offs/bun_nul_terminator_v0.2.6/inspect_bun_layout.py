"""Compare the Bun standalone layout across claude.exe originals and one patched build.
Read-only. Usage: python -I inspect_bun_layout.py <exe> [<exe> ...]"""
import re, struct, sys
sys.path.insert(0, 'C:/code/claude-projects/dazzle-claude-code-patcher')
from dcc_patcher.containers.pe import PeBunExe, RECORD_SIZE

for path in sys.argv[1:]:
    data = open(path, 'rb').read()
    print('=' * 100); print(path, len(data), 'bytes')
    m = re.search(rb'bun-v?(\d+\.\d+\.\d+)', data) or re.search(rb'Bun v(\d+\.\d+\.\d+)', data)
    vers = sorted(set(re.findall(rb'(?:bun|Bun)[ -]v?(\d+\.\d+\.\d+)', data)))
    print('bun version strings:', [v.decode() for v in vers][:8])
    try:
        x = PeBunExe(data)
    except Exception as e:
        print('PeBunExe failed:', e); continue
    off = data[x.offsets_at:x.offsets_at + 32]
    print(f'payload_len={x.payload_len} byte_count={x.byte_count} mod_off={x.mod_off} mod_len={x.mod_len} count={x.count} flags=0x{x.flags:x}')
    print('Offsets raw:', off.hex(' '))
    print('Offsets tail u32s:', struct.unpack_from('<6I', off, 8))
    # what lies between the end of the last module's data and the module table / offsets?
    ends = []
    for k in range(x.count):
        f = struct.unpack_from('<13I', data, x.base + x.mod_off + k * RECORD_SIZE)
        ends.append(max(f[i] + f[i + 1] for i in range(0, 8, 2)))
        if k < 3 or k == x.count - 1:
            print(f'  mod[{k}] fields={f}')
    print('max module data end:', max(ends), ' mod table at:', x.mod_off, '..', x.mod_off + x.mod_len, ' byte_count:', x.byte_count)
    gap = x.byte_count - (x.mod_off + x.mod_len)
    print('bytes after module table before Offsets:', gap)
    if gap:
        print('  first 64 of them:', data[x.base + x.mod_off + x.mod_len: x.base + x.mod_off + x.mod_len + 64].hex(' '))
    # the error text and its neighbours
    for msg in (b'module contents are out of range', b'Corrupted module graph'):
        for i in [m.start() for m in re.finditer(re.escape(msg), data)][:3]:
            print(f'  {msg.decode()!r} at {i}: ', data[max(0, i - 120):i + 80])
