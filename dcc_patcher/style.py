"""Colour for terminal output, with no dependency (#9).

The palette follows claude-session-backup's: green done, yellow pending, red a
problem, cyan a command to run, dim detail, bold a heading. Colour reaches only
a real terminal; a pipe, a file or a test capture gets plain text, and so does
anyone with NO_COLOR set. On Windows, the console's escape-code support is
switched on once, so plain cmd and PowerShell windows show it too.
"""
from __future__ import annotations

import os
import sys

CODES = {'green': '32', 'yellow': '33', 'red': '31', 'cyan': '36', 'dim': '2', 'bold': '1'}
_ready: dict[int, bool] = {}


def _enable_windows_vt(stream) -> bool:
    import ctypes
    import msvcrt
    try:
        handle = msvcrt.get_osfhandle(stream.fileno())
        k32 = ctypes.windll.kernel32
        mode = ctypes.c_uint32()
        if not k32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(mode.value & 0x0004 or k32.SetConsoleMode(handle, mode.value | 0x0004))
    except (OSError, ValueError, AttributeError):
        return False


def enabled(stream=None) -> bool:
    stream = stream or sys.stdout
    if os.environ.get('NO_COLOR') or os.environ.get('TERM') == 'dumb':
        return False
    try:
        if not stream.isatty():
            return False
    except (AttributeError, ValueError):
        return False
    key = id(stream)
    if key not in _ready:
        _ready[key] = _enable_windows_vt(stream) if sys.platform == 'win32' else True
    return _ready[key]


def paint(text: str, style: str | None, on: bool) -> str:
    if not on or not style:
        return text
    return f'\033[{CODES[style]}m{text}\033[0m'


# A path inside a line is shown in the bright variant of the line's colour, so the exact
# path stands apart from the words around it. `path()` marks one; `paint_marked` renders
# the marks (or drops them when colour is off).
BRIGHT = {'green': '92', 'yellow': '93', 'red': '91', 'cyan': '96', 'bold': '1',
          'dim': '2'}     # detail lines (the candidate list, notes) stay gray throughout: they're secondary
_OPEN, _CLOSE = '\x01', '\x02'


def path(value) -> str:
    return f'{_OPEN}{value}{_CLOSE}'


def paint_marked(text: str, style: str | None, on: bool) -> str:
    if not on or not style:
        return text.replace(_OPEN, '').replace(_CLOSE, '')
    base, bright = f'\033[{CODES[style]}m', f'\033[{BRIGHT[style]}m'
    return base + text.replace(_OPEN, '\033[0m' + bright).replace(_CLOSE, '\033[0m' + base) + '\033[0m'
