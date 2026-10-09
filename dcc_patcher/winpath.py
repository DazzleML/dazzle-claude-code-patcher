"""Own exactly one entry in the Windows PATH, safely (#9).

PATH is shared with every other installer, so the tool changes one entry, its
own, and nothing else:

- the raw registry value is read and written back with the same type (REG_SZ
  or REG_EXPAND_SZ); `%VAR%` entries are never expanded;
- after a write the value is read again, and a mismatch is an error;
- removing writes nothing when our entry is already gone, and never restores a
  saved copy (that would delete what other installers added since);
- a WM_SETTINGCHANGE "Environment" broadcast tells new processes to reload.

All registry access goes through `registry()`, so tests replace it (and
`broadcast`) and can never reach the real PATH.
"""
from __future__ import annotations

import os
import sys

USER = 'user'
SYSTEM = 'system'
KEYS = {USER: ('HKEY_CURRENT_USER', r'Environment'),
        SYSTEM: ('HKEY_LOCAL_MACHINE', r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment')}
REG_SZ, REG_EXPAND_SZ = 1, 2                     # winreg's values, also off Windows
MAX = 32767


class PathError(Exception):
    pass


class Registry:
    """The real Path values, through winreg."""

    def read(self, scope: str) -> tuple[str | None, int | None]:
        import winreg
        hive, key = KEYS[scope]
        try:
            with winreg.OpenKey(getattr(winreg, hive), key, 0, winreg.KEY_READ) as k:
                return winreg.QueryValueEx(k, 'Path')      # raw: never expanded
        except FileNotFoundError:
            return None, None

    def write(self, scope: str, value: str, kind: int):
        import winreg
        hive, key = KEYS[scope]
        with winreg.OpenKey(getattr(winreg, hive), key, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, 'Path', 0, kind, value)


def registry() -> Registry:
    return Registry()


def broadcast() -> bool:
    """Tell running programs (Explorer above all) that the environment changed."""
    if sys.platform != 'win32':
        return False
    import ctypes
    from ctypes import wintypes
    result = wintypes.DWORD()
    return bool(ctypes.WinDLL('user32').SendMessageTimeoutW(
        wintypes.HWND(0xFFFF), 0x001A, 0, ctypes.c_wchar_p('Environment'), 0x0002, 5000, ctypes.byref(result)))


def is_elevated() -> bool:
    if sys.platform != 'win32':
        return os.geteuid() == 0 if hasattr(os, 'geteuid') else False
    import ctypes
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


# -- the value, as text: only our segment ever changes -----------------------------------

def _norm(entry: str) -> str:
    return os.path.normcase(os.path.expandvars(entry.strip()).rstrip('\\/'))


def position(value: str, entry: str) -> int | None:
    """Index of `entry` among the value's segments, compared expanded and case-folded."""
    want = _norm(entry)
    for i, p in enumerate(value.split(';')):
        if p and _norm(p) == want:
            return i
    return None


def insert_before(value: str, entry: str, anchor: str | None) -> str:
    """`value` with `entry` just before `anchor` (or first when the anchor is absent).
    Already ahead of the anchor: unchanged. Behind it: moved, nothing else touched."""
    parts = value.split(';') if value else []
    at, here = position(value, anchor) if anchor else None, position(value, entry)
    if here is not None and (at is None or here < at):
        return value
    if here is not None:
        del parts[here]
        at = position(';'.join(parts), anchor)
    i = at if at is not None else 0
    return ';'.join(parts[:i] + [entry] + parts[i:])


def remove(value: str, entry: str) -> str | None:
    """`value` without `entry`; None when it isn't there (so nothing is written)."""
    i = position(value, entry)
    if i is None:
        return None
    parts = value.split(';')
    del parts[i]
    return ';'.join(parts)


# -- reading and writing the registry ----------------------------------------------------

def read(scope: str) -> tuple[str, int]:
    value, kind = registry().read(scope)
    if value is None:
        return '', REG_EXPAND_SZ                     # Windows' type for a new Path
    if kind not in (REG_SZ, REG_EXPAND_SZ):
        raise PathError(f'the {scope} PATH has an unexpected registry type ({kind}); not touching it')
    return value, kind


def _write(scope: str, before: str, after: str, kind: int):
    if len(after) > MAX:
        raise PathError(f'the {scope} PATH would be {len(after)} characters, over Windows\' {MAX}')
    reg = registry()
    if (reg.read(scope)[0] or '') != before:
        raise PathError(f'the {scope} PATH changed while dcc-patcher was working; nothing written, try again')
    reg.write(scope, after, kind)
    if reg.read(scope) != (after, kind):
        raise PathError(f'the {scope} PATH did not read back as written; check it with `dcc-patcher status`')


def add(scope: str, entry: str, anchor: str | None) -> tuple[bool, str, str, int]:
    """Put `entry` ahead of `anchor` in the scope's PATH. Returns (changed, before, after, type)."""
    before, kind = read(scope)
    after = insert_before(before, entry, anchor)
    if after == before:
        return False, before, after, kind
    _write(scope, before, after, kind)
    return True, before, after, kind


def drop(scope: str, entry: str) -> tuple[bool, str, str, int]:
    """Take `entry` out of the scope's PATH. Returns (changed, before, after, type)."""
    before, kind = read(scope)
    after = remove(before, entry)
    if after is None:
        return False, before, before, kind
    _write(scope, before, after, kind)
    return True, before, after, kind
