"""How dcc-patcher's commands are grouped in `dcc-patcher -h` (v0.2.4).

The grouping is data: three sections (what a command acts on) and the one true pair
of opposites, `install-shim` and `uninstall-shim`. The help text of each command is
read from the real parser, so it is written once, beside the command.

`VerbAxis` carries dazzlecmd-lib's field names (`dazzlecmd_lib.verb_axis.VerbAxis`:
axis, warm, cold, applies_at, gloss) so a later move onto dazzlecmd-lib swaps the
type and keeps the declaration. Its `groupable()` returns dazzle-lib's `Groupable`,
imported only when help is drawn: the `claude` launcher loads this package to
rebuild, and it must keep starting with nothing but the standard library.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import FrozenSet, Tuple

from ._cli_sections import FLAT, Section, render_sections

ARROW = ' <-> '


@dataclass(frozen=True)
class VerbAxis:
    """A pair of opposite commands on one axis: `warm` makes something present,
    `cold` takes it away (the names dazzlecmd-lib's VerbAxis uses)."""
    axis: str
    warm: str
    cold: str
    applies_at: FrozenSet[str]
    gloss: str = ''

    def groupable(self):
        from dazzle_lib.groupable import Groupable       # lazily: see the module docstring
        return Groupable(minus=self.cold, plus=self.warm, meaning=self.axis)


SHIM = VerbAxis('shim', 'install-shim', 'uninstall-shim', frozenset({'machine'}),
                gloss='the launchers on PATH')

# (heading, what the section is about, its commands in the order shown)
GROUPS: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    ('patches:', 'read-only -- what a build holds, whether the patches fit',
     ('inspect', 'validate', 'check')),
    ('builds:', 'make a patched build; choose what `claude` runs',
     ('apply', 'use', 'rollback', 'archive')),
    ('this machine:', None,                       # gloss drawn from SHIM, below
     ('status', 'update', 'install-shim', 'uninstall-shim', 'restore-path', 'shellenv')),
)

LABEL_COL = 20      # fits `uninstall-shim` at the row indent
WIDTH = 80


def command_help(parser: argparse.ArgumentParser) -> dict:
    """name -> one-line help, read from the parser's own subcommands."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return {ca.dest: (ca.help or '') for ca in action._choices_actions}
    return {}


def render_help(parser: argparse.ArgumentParser) -> str:
    """The grouped `dcc-patcher -h`. A command missing from GROUPS still shows, under
    `other:`, so a new command can't vanish from the help."""
    helps = command_help(parser)
    g = SHIM.groupable()
    machine_gloss = f'{g.plus}{ARROW}{g.minus}; restore-path undoes PATH'
    sections, shown = [], set()
    for heading, gloss, names in GROUPS:
        rows = tuple((n, helps[n]) for n in names if n in helps)
        shown.update(n for n, _ in rows)
        sections.append(Section(FLAT, heading, gloss if gloss is not None else machine_gloss, rows=rows))
    rest = tuple((n, h) for n, h in helps.items() if n not in shown)
    if rest:
        sections.append(Section(FLAT, 'other:', '', rows=rest))
    sections.append(Section(FLAT, 'options:', '', rows=(
        ('-h, --help', 'show this help message and exit'),
        ('-V, --version', "show program's version number and exit")), header_indent=0, row_indent=2))
    return '\n'.join([
        parser.format_usage().rstrip('\n'), '',
        parser.description, '',
        'commands, by what they act on:', '',
        render_sections(sections, label_col=LABEL_COL, width=WIDTH), '',
        "Run 'dcc-patcher <command> -h' for a command's options.",
    ]) + '\n'


def install_grouped_help(parser: argparse.ArgumentParser) -> None:
    """Make `parser.format_help` the grouped layout, falling back to argparse's own
    when the grouping can't be drawn (dazzle-lib missing or broken): the help changes
    shape, the tool never stops."""
    plain = parser.format_help

    def grouped() -> str:
        try:
            return render_help(parser)
        except Exception:                       # noqa: BLE001 -- any failure: the plain help
            return plain()
    parser.format_help = grouped
