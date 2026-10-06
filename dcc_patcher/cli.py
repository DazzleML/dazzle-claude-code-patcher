"""dcc-patcher command line.

Commands: `inspect` (what is in a Claude Code executable), `validate` (is a patch
spec well formed), `check` (does each patch still apply, and if not, what changed)
and `apply` (build a patched copy).

Exit codes: 0 success; 1 the file is the right format but not a usable Bun
executable, or a patch needs a human (nothing is written); 2 usage errors,
malformed specs and unsupported formats.
"""
import argparse
import glob
import json
import os
import re
import sys
import tempfile
from pathlib import Path

from . import diagnose, engine, lock, spec
from ._version import DISPLAY_VERSION
from .containers import ContainerError, UnsupportedFormat, open_container
from .spec import SpecError

PATCHES_DIR = Path(__file__).resolve().parents[1] / 'patches'


def _version_of(data: bytes) -> str:
    m = re.search(rb'VERSION:"(\d+\.\d+\.\d+)"', data)
    return m.group(1).decode() if m else 'unknown'


def _open(path):
    """(bytes, container), or (None, exit code) after printing why not."""
    try:
        with open(path, 'rb') as f:
            data = f.read()
    except OSError as e:
        print(f'dcc-patcher: {path}: {e.strerror or e}', file=sys.stderr)
        return None, 2
    try:
        return data, open_container(data)
    except UnsupportedFormat as e:
        print(f'dcc-patcher: {e}', file=sys.stderr)
        return None, 2
    except ContainerError as e:
        print(f'dcc-patcher: {path}: {e}', file=sys.stderr)
        return None, 1


def _spec_paths(given) -> list[Path]:
    if not given:
        return sorted(PATCHES_DIR.glob('*/patch.toml'))
    return [Path(p) / 'patch.toml' if Path(p).is_dir() else Path(p) for p in given]


def cmd_validate(args) -> int:
    paths = _spec_paths(args.specs)
    for path in paths:
        try:
            patch = spec.load(path)
        except (SpecError, OSError) as e:
            print(f'dcc-patcher: {e}', file=sys.stderr)
            return 2
        n = len(patch.edits)
        print(f'ok  {patch.id}  {patch.title}  ({n} edit{"" if n == 1 else "s"})  {path}')
    return 0


def cmd_apply(args) -> int:
    if os.path.exists(args.output) and os.path.samefile(args.file, args.output):
        print('dcc-patcher: refusing to write over the input; give a different -o', file=sys.stderr)
        return 2
    try:
        patches = [spec.load(p) for p in _spec_paths(args.patch)]
    except (SpecError, OSError) as e:
        print(f'dcc-patcher: {e}', file=sys.stderr)
        return 2
    data, exe = _open(args.file)
    if data is None:
        return exe
    image, results = engine.apply(exe, patches, debug=args.debug)
    _report(results)
    if not all(r.ok for r in results):
        print('dcc-patcher: a patch needs a human; nothing written', file=sys.stderr)
        return 1
    if image is None:
        print('nothing to apply; nothing written')
        return 0
    _write_atomically(args.output, image)
    lock_path = f'{args.output}.dcc-lock.json'
    _write_atomically(lock_path, lock.dumps(lock.build(data, image, _version_of(data), exe, results)).encode())
    print(f'wrote {args.output} and {lock_path}')
    return 0


def _report(results, container=None, baseline=None):
    """Print each patch's and edit's status; under a failing edit, its region diff."""
    for r in results:
        where = f' [module {r.module}]' if r.patch.modules > 1 and r.module is not None else ''
        print(f'  {r.patch.id}{where}  {r.status}' + (f'  ({r.detail})' if r.detail else ''))
        text = container.source(r.module).decode('latin-1') if container and r.module is not None else None
        for e in r.edits:
            print(f'      {e.status:13} x{e.count}  {e.name}' + (f'  ({e.detail})' if e.detail and e.status != 'APPLIES' else ''))
            if e.status == engine.APPLIES or text is None or 'was not captured' in e.detail:
                continue
            spec_edit = next(x for x in r.patch.edits if x.name == e.name)
            before = _baseline_site(baseline, r.patch.id, e.name)
            if before is None:
                print('          no baseline for this edit: pass --baseline <lockfile> for a region diff')
                continue
            for line in diagnose.diff(text, before, spec_edit.near, spec_edit.window):
                print(f'          {line}')


def _baseline_site(baseline, patch_id, edit_name):
    for p in (baseline or {}).get('patches', []):
        if p.get('id') == patch_id:
            for e in p.get('edits', []):
                if e.get('name') == edit_name and e.get('sites'):
                    return e['sites'][0]['before']
    return None


def _expand(paths) -> list[str]:
    """Shell-independent globbing, so `claude.exe*` works from cmd.exe too."""
    out = []
    for p in paths:
        out += sorted(glob.glob(p), key=os.path.getmtime) if glob.has_magic(p) else [p]
    return out


def cmd_check(args) -> int:
    try:
        patches = [spec.load(p) for p in _spec_paths(args.patch)]
        baseline = json.loads(Path(args.baseline).read_text()) if args.baseline else None
    except (SpecError, OSError, ValueError) as e:
        print(f'dcc-patcher: {e}', file=sys.stderr)
        return 2
    files = _expand(args.files)
    if not files:
        print('dcc-patcher: no files matched', file=sys.stderr)
        return 2
    worst = 0
    for path in files:
        data, exe = _open(path)
        if data is None:
            worst = max(worst, exe)
            continue
        version = _version_of(data)
        results = engine.locate_all(exe, patches)
        print(f'{version}  {path}')
        _report(results, exe, baseline)
        if not all(r.ok for r in results):
            worst = max(worst, 1)
        if args.lock_out:
            name = version if version != 'unknown' else lock._sha(data)[:12]
            _write_atomically(os.path.join(args.lock_out, f'{name}.dcc-lock.json'),
                              lock.dumps(lock.build(data, None, version, exe, results)).encode())
    return worst


def _write_atomically(path, data: bytes):
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=folder, prefix='.dcc-', suffix='.tmp')
    try:
        with os.fdopen(fd, 'wb') as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def cmd_inspect(args) -> int:
    data, exe = _open(args.file)
    if data is None:
        return exe
    print(f'file:     {args.file}')
    print(f'format:   {exe.format}')
    print(f'version:  {_version_of(data)}')
    print(f'modules:  {exe.count}')
    print(f'flags:    0x{exe.flags:x}')
    if args.marker:
        hits = exe.find_module(args.marker.encode())
        for k in hits:
            m = exe.module(k)
            print(f'marker:   [{k}] {m["name"]}  source {m["src"][1]:,} bytes, bytecode {m["bytecode"][1]:,} bytes')
        if not hits:
            print('marker:   not found')
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='dcc-patcher',
        description='Apply, verify and diagnose patches to the native Claude Code CLI.',
    )
    parser.add_argument('--version', action='version', version=f'dcc-patcher {DISPLAY_VERSION}')
    sub = parser.add_subparsers(dest='command')
    p = sub.add_parser('inspect', help='show what is inside a Claude Code executable')
    p.add_argument('file')
    p.add_argument('--marker', help='list the modules whose source contains this string')
    p.set_defaults(func=cmd_inspect)
    p = sub.add_parser('validate', help='check patch specs are well formed (default: every bundled patch)')
    p.add_argument('specs', nargs='*', help='patch.toml files or patch folders')
    p.set_defaults(func=cmd_validate)
    p = sub.add_parser('check', help='say, per patch and edit, whether it applies to each build (read-only)')
    p.add_argument('files', nargs='+', help='Claude Code executables; wildcards allowed (claude.exe*)')
    p.add_argument('--patch', action='append', help='a patch.toml or patch folder (repeatable; default: every bundled patch)')
    p.add_argument('--baseline', help='a lockfile from a build where the patches applied: failing edits get a region diff against it')
    p.add_argument('--lock-out', metavar='DIR', help='write each build\'s located sites to DIR/<version>.dcc-lock.json')
    p.set_defaults(func=cmd_check)
    p = sub.add_parser('apply', help='write a patched copy of a Claude Code executable')
    p.add_argument('file')
    p.add_argument('-o', '--output', required=True, help='the patched copy (never the input)')
    p.add_argument('--patch', action='append', help='a patch.toml or patch folder (repeatable; default: every bundled patch)')
    p.add_argument('--debug', action='store_true', help='also apply each patch\'s debug prelude and debug-only edits')
    p.set_defaults(func=cmd_apply)
    args = parser.parse_args(argv)
    if not getattr(args, 'func', None):
        parser.print_help(sys.stderr)
        return 2
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
