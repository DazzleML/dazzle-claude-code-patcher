"""What a command name resolves to, the way the shells search (#9).

cmd and PowerShell walk PATH in order and, in each folder, try the name with
each PATHEXT extension in order; cmd also tries the current folder first. A
POSIX shell (Git Bash included) wants the name itself, or on Windows also
name.exe. A new process's PATH is the system PATH followed by the user PATH.
"""
from __future__ import annotations

import os
from pathlib import Path

DEFAULT_PATHEXT = '.COM;.EXE;.BAT;.CMD'


def folders(path_value: str) -> list[str]:
    return [os.path.expandvars(p.strip()) for p in path_value.split(os.pathsep) if p.strip()]


def candidates(name: str, path_value: str, pathext: str | None = None, cwd: str | None = None,
               posix: bool = False) -> list[Path]:
    """Every file `name` could run, in the order the shell tries them."""
    if posix:
        exts = ['', '.exe'] if os.name == 'nt' else ['']
    else:
        exts = [e.lower() for e in (pathext or DEFAULT_PATHEXT).split(';') if e]
        if Path(name).suffix.lower() in exts:
            exts = ['']
    where = ([cwd] if cwd and not posix else []) + folders(path_value)
    found, seen = [], set()
    for folder in where:
        for ext in exts:
            p = Path(folder) / f'{name}{ext}'
            key = os.path.normcase(str(p))
            if key not in seen and p.is_file():
                seen.add(key)
                found.append(p)
    return found


def winner(name: str, path_value: str, **kw) -> Path | None:
    found = candidates(name, path_value, **kw)
    return found[0] if found else None
