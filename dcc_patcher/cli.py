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

from . import builds, diagnose, engine, lock, originals, spec
from ._version import DISPLAY_VERSION
from .containers import ContainerError, UnsupportedFormat, open_container
from .spec import SpecError

PATCHES_DIR = Path(__file__).resolve().parent / 'patches'   # package data, so a wheel carries them (#4)


_version_of = builds.version_of


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


class NoSpecs(OSError):
    """No patch spec to run: a run with none would look clean and check nothing."""


def _spec_paths(given) -> list[Path]:
    if not given:
        found = sorted(PATCHES_DIR.glob('*/patch.toml'))
        if not found:
            raise NoSpecs(f'no patch specs found in {PATCHES_DIR}; reinstall dcc-patcher, or pass --patch')
        return found
    return [Path(p) / 'patch.toml' if Path(p).is_dir() else Path(p) for p in given]


def cmd_validate(args) -> int:
    try:
        paths = _spec_paths(args.specs)
    except NoSpecs as e:
        print(f'dcc-patcher: {e}', file=sys.stderr)
        return 2
    for path in paths:
        try:
            patch = spec.load(path)
        except (SpecError, OSError) as e:
            print(f'dcc-patcher: {e}', file=sys.stderr)
            return 2
        n = len(patch.edits)
        print(f'ok  {patch.id}  {patch.title}  ({n} edit{"" if n == 1 else "s"})  {path}')
    return 0


def _refuse_output(output) -> bool:
    """True, after saying why, when `output` must not be written."""
    folder = builds.inside_config(output)
    if folder:
        print(f'dcc-patcher: refusing to write inside Claude Code\'s config folder ({folder}): '
              f'{os.path.abspath(output)}', file=sys.stderr)
        return True
    return False


def cmd_apply(args) -> int:
    if args.output and _refuse_output(args.output):
        return 2
    if args.output and os.path.exists(args.output) and os.path.samefile(args.file, args.output):
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
    code, _, _ = _build(args.file, data, exe, patches, args.output, args.debug)
    return code


def build(file) -> tuple[int, str | None, list]:
    """The launcher's rebuild: `apply <file>` into the builds folder with the
    bundled patches. Returns (exit code, the versioned build or None, results)."""
    try:
        patches = [spec.load(p) for p in _spec_paths(None)]
    except (SpecError, OSError) as e:
        print(f'dcc-patcher: {e}', file=sys.stderr)
        return 2, None, []
    data, exe = _open(file)
    if data is None:
        return exe, None, []
    return _build(file, data, exe, patches, None, False)


def _build(file, data, exe, patches, output, debug) -> tuple[int, str | None, list]:
    version = _version_of(data)
    given = output
    if not output:
        tag = version if version != 'unknown' else f'unknown-{lock._sha(data)[:12]}'
        output = str(builds.builds_dir() / builds.build_name(tag, builds.exe_suffix(file)))
        if _refuse_output(output):
            return 2, None, []
        kept, new = originals.keep(data, version, builds.exe_suffix(file))
        if new:
            print(f'kept the original as {kept}')
    image, results = engine.apply(exe, patches, debug=debug)
    _report(results)
    if not all(r.ok for r in results):
        print('dcc-patcher: a patch needs a human; nothing written', file=sys.stderr)
        return 1, None, results
    if image is None:
        print('nothing to apply; nothing written')
        return 0, None, results
    output = os.path.abspath(output)
    lock_path = f'{output}.dcc-lock.json'
    if not given and _same_build(lock_path, image):
        print(f'already built: {output}')
    else:
        _write_atomically(output, image)
        _write_atomically(lock_path, lock.dumps(lock.build(data, image, version, exe, results)).encode())
        print(f'wrote {output}\n  and {lock_path}')
    if given:
        return 0, output, results
    try:
        link, how = builds.point_current(Path(output))
    except PermissionError:
        print(f'dcc-patcher: the current build is in use, so it still points at the old one; '
              f'the new build is at {output}', file=sys.stderr)
        return 1, output, results
    print(f'{link} -> {Path(output).name} ({how})')
    return 0, output, results


def _same_build(lock_path, image: bytes) -> bool:
    """The build at this versioned name is already these bytes (its lockfile says so)."""
    try:
        recorded = json.loads(Path(lock_path).read_text()).get('output_sha256')
    except (OSError, ValueError):
        return False
    return recorded == lock._sha(image) and os.path.exists(lock_path[:-len('.dcc-lock.json')])


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


def cmd_use(args) -> int:
    from . import launch
    st = launch.load_state()
    if not args.what:
        print(f'mode:     {st["mode"]}')
        print(f'current:  {st.get("current") or "(none yet)"}')
        print(f'official: {st["official"]}')
        print(f'builds:   {builds.builds_dir()}')
        return 0
    what = args.what
    if what not in launch.MODES:
        what = Path(what).name
        if what not in launch.kept_builds():
            print(f'dcc-patcher: no build {what} in {builds.builds_dir()} '
                  f'(stock, patched, or one of: {", ".join(launch.kept_builds()) or "none"})', file=sys.stderr)
            return 2
    st['mode'] = what
    launch.save_state(st)
    print(f'claude runs {what} from the next start')
    return 0


def cmd_rollback(args) -> int:
    from . import launch
    st = launch.load_state()
    kept = launch.kept_builds()
    now = st['mode'] if st['mode'] not in launch.MODES else st.get('current')
    earlier = kept[:kept.index(now)] if now in kept else []
    if not earlier:
        print(f'dcc-patcher: no build older than {now or "the current one"} in {builds.builds_dir()}', file=sys.stderr)
        return 1
    st['mode'] = earlier[-1]
    launch.save_state(st)
    print(f'claude runs {earlier[-1]} from the next start (pinned; `dcc-patcher use patched` to follow updates again)')
    return 0


def cmd_archive(args) -> int:
    from . import launch
    official = args.official or launch.load_state()['official']
    if _refuse_output(builds.builds_dir()):
        return 2
    found = originals.candidates(official)
    if not found:
        print(f'dcc-patcher: no Claude Code at {official}', file=sys.stderr)
        return 1
    new = originals.sweep(official)
    print(f'{len(new)} newly kept, {len(found) - len(new)} already kept, in {builds.builds_dir()}')
    return 0


SHIMS = Path(__file__).resolve().parent / 'shims'


def cmd_install_shim(args) -> int:
    folder = Path(args.dir).resolve() if args.dir else builds.builds_dir() / 'bin'
    official_bin = (Path(os.path.expanduser('~')) / '.local' / 'bin').resolve()
    if _refuse_output(folder):
        return 2
    if folder == official_bin or official_bin in folder.parents:
        print(f'dcc-patcher: refusing to write into the official install\'s folder ({official_bin})', file=sys.stderr)
        return 2
    from . import install, launch
    if args.if_needed:
        try:
            if install.is_set_up(folder, launch.load_state()['official']):
                return 0
        except (install.winpath.PathError, OSError):
            pass
    if sys.platform == 'win32':                 # so uninstall-shim knows whether ~/bin was ours to make
        rec = install.load_records()
        if 'posix_dir_created' not in rec:
            rec['posix_dir_created'] = install.posix_dir_created(rec)
            install.save_records(rec)
    _write_shims(folder)
    if args.no_path:
        print(f'PATH not changed (--no-path). Put {folder} ahead of {official_bin} on PATH '
              f'(keep {official_bin} on PATH too: the updater checks it).')
        return 0
    try:
        return install.install(folder, launch.load_state()['official'], args.yes,
                               lambda where: _write_shims(where, posix_too=False))
    except (install.winpath.PathError, OSError) as e:
        print(f'dcc-patcher: {e}', file=sys.stderr)
        return 1


MARKER = b'Written by dcc-patcher install-shim'


posix_shim_dir = builds.posix_shim_dir


# The three names on PATH: `claude` runs whatever `dcc-patcher use` (or this shell's
# DCC_MODE) says; the other two are explicit whatever `claude` means.
SHIM_STEMS = (('claude', 'the current build (dcc-patcher use)', ''),
              ('claude-stock', 'the official Claude Code', 'stock'),
              ('dazzle-claude', 'the current patched build', 'patched'))


def _remove_stale(path: Path, why: str):
    if path.is_file() and MARKER in path.read_bytes()[:200]:
        path.unlink()
        print(f'removed {path} ({why})')


def _write_shims(folder: Path, posix_too: bool = True):
    python = sys.executable
    if sys.platform == 'win32':
        kinds = [('claude.cmd', 'claude.cmd.in', folder)] + \
                ([('claude', 'claude.sh.in', posix_shim_dir())] if posix_too else [])
        for stem, _, _ in SHIM_STEMS:                    # v0.1.10 put the sh shims beside the .cmd ones
            _remove_stale(folder / stem, f'the sh shims now live in {posix_shim_dir()}')
    else:
        kinds = [('claude', 'claude.sh.in', folder)]
    for name, template, where in kinds:
        where.mkdir(parents=True, exist_ok=True)
        text = (SHIMS / template).read_text(encoding='ascii')
        posix = template.endswith('.sh.in')
        exe = python.replace('\\', '/') if posix else python
        for stem, what, setmode in SHIM_STEMS:
            body = (text.replace('@@python@@', exe).replace('@@what@@', what)
                    .replace('@@mode@@', setmode))
            if not setmode:
                body = '\n'.join(l for l in body.split('\n') if 'DCC_MODE' not in l)
            target = where / name.replace('claude', stem, 1)
            if target.exists() and MARKER not in target.read_bytes()[:200]:
                print(f'dcc-patcher: {target} exists and isn\'t one of ours; left it alone', file=sys.stderr)
                continue
            target.write_bytes(body.replace('\n', '\r\n' if not posix else '\n').encode('ascii'))
            if posix:
                target.chmod(0o755)
            print(f'wrote {target}')


def cmd_uninstall_shim(args) -> int:
    from . import install
    try:
        return install.uninstall()
    except (install.winpath.PathError, OSError) as e:
        print(f'dcc-patcher: {e}', file=sys.stderr)
        return 1


def cmd_status(args) -> int:
    from . import install
    return install.status(brief=args.brief)


def cmd_shellenv(args) -> int:
    from . import install
    if args.folder:                             # for the dcc-env scripts: '' when this shell already has it
        folder = install.shell_folder(posix=args.shell == 'sh')
        if folder:
            print(folder)
        return 0
    entry = install.load_records().get('entry') or str(builds.builds_dir() / 'bin')
    print(install.shellenv(entry, args.shell or install.detect_shell() or 'powershell'))
    return 0


def cmd_restore_path(args) -> int:
    from . import install
    try:
        return install.restore(args.backup, args.yes)
    except (install.winpath.PathError, OSError, ValueError) as e:
        print(f'dcc-patcher: {e}', file=sys.stderr)
        return 1


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
    p.add_argument('-o', '--output', help='the patched copy (never the input). Default: the builds folder, '
                   'as claude-dcc-<claude version>+dcc<patcher version>, with claude-dcc pointing at it')
    p.add_argument('--patch', action='append', help='a patch.toml or patch folder (repeatable; default: every bundled patch)')
    p.add_argument('--debug', action='store_true', help='also apply each patch\'s debug prelude and debug-only edits')
    p.set_defaults(func=cmd_apply)
    p = sub.add_parser('use', help='choose what the claude shim runs: stock, patched (the newest build, '
                       'rebuilt on update) or one build; no argument shows the state')
    p.add_argument('what', nargs='?', help='stock | patched | a build\'s file name')
    p.set_defaults(func=cmd_use)
    p = sub.add_parser('rollback', help='pin the build before the current one')
    p.set_defaults(func=cmd_rollback)
    p = sub.add_parser('install-shim', help='write the claude, claude-stock and dazzle-claude launchers and put '
                                            'them on PATH')
    p.add_argument('--dir', help='where to write them (default: <builds folder>/bin)')
    p.add_argument('--yes', action='store_true', help='change PATH without asking (also: DCC_YES=1)')
    p.add_argument('--no-path', action='store_true', help='write the launchers only; leave PATH alone')
    p.add_argument('--if-needed', action='store_true', help='do nothing when already set up (used by dcc-env)')
    p.set_defaults(func=cmd_install_shim)
    p = sub.add_parser('uninstall-shim', help='take the launchers off PATH (only the entries dcc-patcher added)')
    p.set_defaults(func=cmd_uninstall_shim)
    p = sub.add_parser('status', help='which claude this shell runs, and whether PATH, the launcher '
                       'and the kept originals are in order')
    p.add_argument('--brief', action='store_true', help='only the line saying which claude this shell runs')
    p.set_defaults(func=cmd_status)
    p = sub.add_parser('shellenv', help='print the line that puts the launchers on PATH in this shell '
                       '(or run dcc-env, which does it for you)')
    p.add_argument('shell', nargs='?', choices=('cmd', 'powershell', 'sh'), help='default: detected')
    p.add_argument('--folder', action='store_true', help='print only the folder, and nothing when this shell has it')
    p.set_defaults(func=cmd_shellenv)
    p = sub.add_parser('restore-path', help='put a PATH backup back (default: the newest user PATH backup), '
                       'after showing what changes')
    p.add_argument('backup', nargs='?', help='a .reg file from the builds folder\'s backups')
    p.add_argument('--yes', action='store_true', help='restore without asking (also: DCC_YES=1)')
    p.set_defaults(func=cmd_restore_path)
    p = sub.add_parser('archive', help='keep every original Claude Code beside the official one '
                       '(including the updater\'s .old copies) in the builds folder')
    p.add_argument('official', nargs='?', help='the official executable (default: the launcher\'s)')
    p.set_defaults(func=cmd_archive)
    args = parser.parse_args(argv)
    if not getattr(args, 'func', None):
        parser.print_help(sys.stderr)
        return 2
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
