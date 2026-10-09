"""Keep every original Claude Code we build from (#9).

The updater keeps `claude.exe.old.<ms>` copies of earlier releases and deletes
them after 30 days, and a patched build's lockfile records only its input's
hash. So every original we build from is kept in the builds folder as
`claude-cc-<version><ext>`, and the updater's copies are swept in the same way,
to re-test patches on older releases and compare a build with its original.

`originals.json` in the builds folder remembers each kept file's sha256, and the
size, mtime and file id of each official file already looked at, so a sweep
reads a 250 MB file once. The official folder is only ever read.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from . import builds

ORIGINAL = 'claude-cc'
INDEX = 'originals.json'


def _load() -> dict:
    try:
        idx = json.loads((builds.builds_dir() / INDEX).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        idx = {}
    idx.setdefault('kept', {})
    idx.setdefault('seen', {})
    return idx


def _save(idx: dict):
    _write(builds.builds_dir() / INDEX, (json.dumps(idx, indent=2) + '\n').encode('utf-8'))


def _write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.dcc-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def _keep(data: bytes, version: str, suffix: str, idx: dict) -> tuple[Path, bool]:
    folder = builds.builds_dir()
    sha = hashlib.sha256(data).hexdigest()
    for name, kept_sha in idx['kept'].items():
        if kept_sha == sha and (folder / name).is_file():
            return folder / name, False
    base = f'{ORIGINAL}-{version}'
    for target in (folder / f'{base}{suffix}', folder / f'{base}-{sha[:12]}{suffix}'):
        if not target.exists():
            _write(target, data)
            idx['kept'][target.name] = sha
            return target, True
        existing = idx['kept'].get(target.name) or _sha_file(target)
        idx['kept'][target.name] = existing
        if existing == sha:
            return target, False
    return target, False                        # both names taken by other contents: leave them be


def keep(data: bytes, version: str, suffix: str) -> tuple[Path, bool]:
    """Keep `data` as an original unless it already is. Returns (its path, newly kept)."""
    idx = _load()
    path, new = _keep(data, version, suffix, idx)
    _save(idx)
    return path, new


def candidates(official) -> list[Path]:
    """The official exe and the updater's `.old` copies beside it."""
    official = Path(official)
    found = sorted(official.parent.glob(official.name + '.old.*')) if official.parent.is_dir() else []
    return ([official] if official.is_file() else []) + [p for p in found if p.is_file()]


def stamp_of(path) -> list[int]:
    s = os.stat(path)
    return [s.st_size, s.st_mtime_ns, s.st_ino]


def pending(official) -> list[Path]:
    """Files beside `official` a sweep has not looked at (no file is read)."""
    known = [list(v) for v in _load()['seen'].values()]
    return [p for p in candidates(official) if stamp_of(p) not in known]


def sweep(official) -> list[Path]:
    """Keep every original beside `official` not kept yet. Returns the newly kept files."""
    if builds.inside_config(builds.builds_dir()):
        return []
    idx = _load()
    seen, new = {}, []
    known = [list(v) for v in idx['seen'].values()]
    for path in candidates(official):
        stamp = stamp_of(path)
        if stamp in known:                      # the updater renames claude.exe to .old: same file
            seen[str(path)] = stamp
            continue
        data = path.read_bytes()
        kept, created = _keep(data, builds.version_of(data), builds.exe_suffix(path), idx)
        seen[str(path)] = stamp
        if created:
            new.append(kept)
            print(f'kept {path.name} as {kept.name}')
    idx['seen'] = seen
    _save(idx)
    return new
