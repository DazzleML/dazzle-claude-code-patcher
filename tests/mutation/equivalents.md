# Recorded equivalent and don't-care survivors

Entries expire when the file's hash changes (`git hash-object <file>`; first 12 characters below). Re-triage before reuse; never feed stale entries to a generator. Written only by separated-generation runs (modes 1-2).

## dcc_patcher/containers/__init__.py @ (uncommitted, S1 unit 1, 2026-10-05)

- `if data[:2] == b'MZ' and len(data) >= 0x40:` -> `if data[:2] == b'MZ':` -- **equivalent**: a short `MZ` file slices to `b''` or reads offset 0, never `PE\0\0`, so `detect` returns `unknown` either way. Mode 1, 2026-10-05.
- `len(data) >= 0x40` -> `> 0x40` -- **don't-care**: only an exactly-64-byte `MZ` file differs. Mode 1, 2026-10-05.
- `data[pe:pe + 4] == b'PE\0\0'` -> `data[pe:pe + 2] == b'PE'` -- **don't-care**: no real file carries `PE` with non-zero trailing bytes; `PeBunExe` validates further. Mode 1, 2026-10-05.
- `data[:4] == b'\x7fELF'` -> `data[:3] == b'\x7fEL'` -- **don't-care**: only changes which refusal message a non-ELF file gets. Mode 1, 2026-10-05.
- `self.kind = kind` -> `self.kind = ''` -- **don't-care**: nothing reads `.kind`; the message carries the format. Mode 1, 2026-10-05.

The heading's hash is filled in when the file is first committed.
