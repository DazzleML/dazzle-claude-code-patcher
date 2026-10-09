"""PATH backups as .reg files (#9): one value, `Path`, in the format `reg export`
writes, so `reg import <file>` (or a double-click) restores it without
dcc-patcher. Only `Path` is ever in the file: the other user variables can hold
API keys and tokens, and a restore must not roll them back.

Version 5 .reg files are UTF-16 LE with a BOM and CRLF line ends. REG_SZ is a
quoted string with `\\` and `"` escaped; REG_EXPAND_SZ is `hex(2):` followed by
the UTF-16 LE bytes and a terminating null, wrapped with `,\\` continuations.
"""
from __future__ import annotations

import re

from . import winpath

HEADER = 'Windows Registry Editor Version 5.00'


def key_of(scope: str) -> str:
    hive, key = winpath.KEYS[scope]
    return f'{hive}\\{key}'


def dumps(scope: str, value: str, kind: int, name: str = 'Path', key: str | None = None) -> bytes:
    lines = [HEADER, '', f'[{key or key_of(scope)}]']
    if kind == winpath.REG_SZ:
        lines.append(f'"{name}"="' + value.replace('\\', '\\\\').replace('"', '\\"') + '"')
    elif kind == winpath.REG_EXPAND_SZ:
        hexes = [f'{b:02x}' for b in (value + '\0').encode('utf-16-le')]
        line = f'"{name}"=hex(2):'
        for i, h in enumerate(hexes):
            piece = h + (',' if i < len(hexes) - 1 else '')
            if len(line) + len(piece) > 78:
                lines.append(line + '\\')
                line = '  '
            line += piece
        lines.append(line)
    else:
        raise winpath.PathError(f'unexpected registry type {kind}')
    return ('﻿' + '\r\n'.join(lines + ['', ''])).encode('utf-16-le')


def loads(data: bytes, name: str = 'Path', key: str | None = None) -> tuple[str, str, int]:
    """(scope, value, type) from a file `dumps` (or `reg export`) wrote. `key` reads a
    file for another key instead (scope is then that key), for checking against reg.exe."""
    text = data.decode('utf-16')
    lines = text.splitlines()
    if key:
        scope = key if any(l.strip() == f'[{key}]' for l in lines) else None
    else:
        scope = next((s for s in winpath.KEYS for l in lines if l.strip() == f'[{key_of(s)}]'), None)
    start = next((i for i, l in enumerate(lines) if l.startswith(f'"{name}"=')), None)
    if scope is None or start is None:
        raise winpath.PathError('not a dcc-patcher PATH backup (no Environment key or no Path value)')
    body = lines[start][len(name) + 3:]
    i = start
    while body.endswith('\\') and i + 1 < len(lines):
        i += 1
        body = body[:-1] + lines[i].strip()
    if body.startswith('"') and body.endswith('"'):
        return scope, re.sub(r'\\(.)', r'\1', body[1:-1]), winpath.REG_SZ
    if body.startswith('hex(2):'):
        raw = bytes.fromhex(body[len('hex(2):'):].replace(',', ''))
        return scope, raw.decode('utf-16-le').rstrip('\0'), winpath.REG_EXPAND_SZ
    raise winpath.PathError('unrecognised Path value in the backup')
