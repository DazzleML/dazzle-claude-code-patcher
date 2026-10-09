"""Where builds go and what they are called (#3).

`apply` without `-o` writes `claude-dcc-<claude version>+dcc<patcher version><ext>`
and its lockfile into one fixed builds folder, whatever folder it is run from,
and points `claude-dcc<ext>` there at the newest build. The folder is
`DCC_BUILDS_DIR` when set; `private/builds/` in the repository when the package
runs from a checkout (djdarcy, 2026-10-07); otherwise a per-user data folder.

Nothing is ever written inside Claude Code's own config folder (`~/.claude`, or
`CLAUDE_CONFIG_DIR`): a relative `-o` run from there once put a 258 MB build
into a folder kept under git (#3's comment).
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from pathlib import Path

from ._version import BASE_VERSION

REPO = Path(__file__).resolve().parents[1]
CURRENT = 'claude-dcc'


def builds_dir() -> Path:
    env = os.environ.get('DCC_BUILDS_DIR')
    if env:
        return Path(env).resolve()
    if (REPO / '.git').exists():
        return REPO / 'private' / 'builds'
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~/AppData/Local')
    else:
        base = os.environ.get('XDG_DATA_HOME') or os.path.expanduser('~/.local/share')
    return Path(base) / 'dazzle-claude-code-patcher' / 'builds'


def build_name(claude_version: str, suffix: str) -> str:
    return f'{CURRENT}-{claude_version}+dcc{BASE_VERSION}{suffix}'


def made_by_this_version(name: str) -> bool:
    """Whether a build's file name carries this patcher's version. A build made by an
    older dcc-patcher lacks the patches added since, so the launcher rebuilds it."""
    stem = name.split('.exe')[0] if name.endswith('.exe') else name
    return stem.endswith(f'+dcc{BASE_VERSION}')


def version_of(data: bytes) -> str:
    """Claude Code's version, from the VERSION constant its bundle carries."""
    m = re.search(rb'VERSION:"(\d+\.\d+\.\d+)"', data)
    return m.group(1).decode() if m else 'unknown'


def exe_suffix(path) -> str:
    """'.exe' for a Windows build, '' otherwise -- also for the updater's
    `claude.exe.old.<ms>` copies, whose last suffix is the timestamp."""
    return '.exe' if '.exe' in Path(path).name.lower() else ''


def posix_shim_dir() -> Path:
    """Where the sh shims go on Windows: ~/bin, which Git for Windows puts first on
    Git Bash's PATH (/etc/profile.d/env.sh) and Windows itself never searches. An
    extensionless script in a folder on the Windows PATH is picked by resolvers that
    try the bare name (Python 3.12.0's shutil.which), and CreateProcess can't run it."""
    return Path(os.path.expanduser('~')) / 'bin'


def config_dirs() -> list[Path]:
    dirs = [Path(os.path.expanduser('~')) / '.claude']
    if os.environ.get('CLAUDE_CONFIG_DIR'):
        dirs.append(Path(os.environ['CLAUDE_CONFIG_DIR']))
    return [d.resolve() for d in dirs]


def inside_config(path) -> Path | None:
    """The Claude Code config folder `path` would land in, or None."""
    target = Path(path).resolve()
    for d in config_dirs():
        if target == d or d in target.parents:
            return d
    return None


def point_current(build: Path) -> tuple[Path, str]:
    """Make `<folder>/claude-dcc<ext>` the newest build: a hardlink, else a copy.

    Returns (link path, 'hardlink' | 'copy'). Raises PermissionError when the
    current build is running (Windows will not replace an exe in use)."""
    link = build.with_name(CURRENT + build.suffix)
    tmp = link.with_name(f'.dcc-{link.name}.tmp')
    if tmp.exists():
        tmp.unlink()
    try:
        os.link(build, tmp)
        how = 'hardlink'
    except OSError:
        shutil.copyfile(build, tmp)
        how = 'copy'
    try:
        os.replace(tmp, link)
    except BaseException:
        tmp.unlink()
        raise
    return link, how
