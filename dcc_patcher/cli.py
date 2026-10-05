"""dcc-patcher command line.

Scaffold only: the engine (containers, patch specs, check/apply/diagnose) moves in
from poc/ once the design (private design document, 2026-10-05) is finalised.
"""
import argparse
import sys

from ._version import DISPLAY_VERSION


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog='dcc-patcher',
        description='Apply, verify and diagnose patches to the native Claude Code CLI.',
    )
    parser.add_argument('--version', action='version', version=f'dcc-patcher {DISPLAY_VERSION}')
    parser.parse_args(argv)
    print('dcc-patcher: not implemented yet. See the README for status.', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main())
