"""Structured (group/axis) help sections -- a copy of dazzlecmd's `cli_lib/sections.py`.

Origin: dazzlecmd `src/dazzlecmd/_vendor/cli_lib/sections.py` (2026-10-09), which is
in development and meant to become the standalone `dazzle-cli-lib` (import
`dazzle_cli_lib`). The public names are kept as they are there, so when that package
is published this module is replaced by `from dazzle_cli_lib import ...` and nothing
else changes. The one local addition: `width` wraps a row's text at the label column
(upstream doesn't wrap; dcc-patcher's help lines run past 80 columns). Standard
library only, so the launcher can load it without any dependency.
"""
import textwrap
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple


def aligned_row(indent: int, name: str, text: str, label_col: int = 17,
                width: Optional[int] = None) -> str:
    """One ``<indent><name>  <text>`` row, ``text`` aligned to start at ``label_col``
    (a >=2-space gap when the name overruns). Empty ``text`` -> the bare label. With
    ``width``, ``text`` wraps and its continuation lines start at the same column."""
    prefix = " " * indent + name
    if not text:
        return prefix
    gap = max(2, label_col - len(prefix))
    if width is None:
        return prefix + " " * gap + text
    col = len(prefix) + gap
    lines = textwrap.wrap(text, width=max(20, width - col), break_on_hyphens=False,
                          break_long_words=False) or [""]
    return "\n".join([prefix + " " * gap + lines[0]] + [" " * col + l for l in lines[1:]])


def render_labeled_section(label: str, description: str,
                           rows: Iterable[Tuple[str, str]], *,
                           label_col: int = 17,
                           header_indent: int = 2,
                           row_indent: int = 4,
                           width: Optional[int] = None) -> str:
    """Render one GROUP/axis help section: a ``<label>  <description>`` header, then
    each ``(name, description)`` in ``rows`` as an indented, column-aligned row.
    Returns the section as a string with NO trailing newline (the caller spaces
    sections)."""
    lines = [aligned_row(header_indent, label, description, label_col, width)]
    for name, desc in rows:
        lines.append(aligned_row(row_indent, name, desc, label_col, width))
    return "\n".join(lines)


def render_nested_section(label: str, description: str,
                          groups: Iterable[Tuple[str, str,
                                                 Iterable[Tuple[str, str]]]], *,
                          label_col: int = 17,
                          header_indent: int = 2,
                          group_indent: int = 4,
                          item_indent: int = 6,
                          width: Optional[int] = None) -> str:
    """Render an AXIS-EXPOSED (grouped) section: a ``<label>  <description>`` header,
    then each ``(group_label, group_text, items)`` group as a group-row followed by its
    indented item-rows. A blank line BETWEEN groups (not after the last); no trailing
    newline."""
    lines = [aligned_row(header_indent, label, description, label_col, width)]
    group_list = list(groups)
    for idx, (g_label, g_text, items) in enumerate(group_list):
        lines.append(aligned_row(group_indent, g_label, g_text, label_col, width))
        for name, text in items:
            lines.append(aligned_row(item_indent, name, text, label_col, width))
        if idx != len(group_list) - 1:
            lines.append("")
    return "\n".join(lines)


# The two section kinds: FLAT (a header + rows) and NESTED (a header + a group-row per
# axis with its poles under it).
FLAT = "flat"
NESTED = "nested"


@dataclass(frozen=True)
class Section:
    """One help section as data: ``kind=FLAT`` uses ``rows`` (``(name, text)``
    pairs); ``kind=NESTED`` uses ``groups`` (``(group_label, group_text, items)``
    triples). ``header_indent``/``row_indent`` let a section depart from the 2/4
    default (e.g. an ``options:`` block at 0/2)."""

    kind: str
    label: str
    description: str = ""
    rows: Tuple[Tuple[str, str], ...] = ()
    groups: Tuple[Tuple[str, str, Tuple[Tuple[str, str], ...]], ...] = ()
    header_indent: int = 2
    row_indent: int = 4

    def render(self, *, label_col: int = 17, width: Optional[int] = None) -> str:
        if self.kind == NESTED:
            return render_nested_section(
                self.label, self.description, self.groups,
                label_col=label_col, header_indent=self.header_indent, width=width)
        return render_labeled_section(
            self.label, self.description, self.rows,
            label_col=label_col, header_indent=self.header_indent,
            row_indent=self.row_indent, width=width)


def render_sections(sections: Sequence[Section], *,
                    label_col: int = 17, width: Optional[int] = None) -> str:
    """Render a list of :class:`Section`s, one blank line between each. No
    leading/trailing blank (the caller frames it)."""
    return "\n\n".join(s.render(label_col=label_col, width=width) for s in sections)
