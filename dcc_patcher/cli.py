"""dcc-patcher command line.

Commands so far: `inspect` (what is in a Claude Code executable). The patch engine's
`validate`, `check` and `apply` arrive with slices S2-S4 of the build.

Exit codes: 0 success; 1 the file is the right format but not a usable Bun
executable; 2 usage errors and unsupported formats.
"""
import argparse
import re
import sys

from ._version import DISPLAY_VERSION
from .containers import ContainerError, UnsupportedFormat, open_container


def _version_of(data: bytes) -> str:
    m = re.search(rb'VERSION:"(\d+\.\d+\.\d+)"', data)
    return m.group(1).decode() if m else 'unknown'


def cmd_inspect(args) -> int:
    with open(args.file, 'rb') as f:
        data = f.read()
    try:
        exe = open_container(data)
    except UnsupportedFormat as e:
        print(f'dcc-patcher: {e}', file=sys.stderr)
        return 2
    except ContainerError as e:
        print(f'dcc-patcher: {args.file}: {e}', file=sys.stderr)
        return 1
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
    args = parser.parse_args(argv)
    if not getattr(args, 'func', None):
        parser.print_help(sys.stderr)
        return 2
    return args.func(args)


if __name__ == '__main__':
    sys.exit(main())
