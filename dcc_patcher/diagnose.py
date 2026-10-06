"""Diagnosis: when an edit stops applying, show what changed at its site.

The baseline is a lockfile from a build where the edit applied: it holds the exact
text each edit matched. In the new build the engine finds the region where that text
should be (the edit's landmark windows, or else the places where the longest stable
run of the old text still occurs), lines it up with the old text, and prints a diff.

Both sides are identifier-normalised first: every minified name (an identifier of at
most three characters that isn't a keyword or a property) becomes `_`, so a diff
shows what changed in the code's shape and not the renames every release brings.
"""
from __future__ import annotations

import difflib
import re

from .engine import _region

KEYWORDS = {'if', 'in', 'of', 'do', 'let', 'for', 'new', 'try', 'var', 'get', 'set'}
# A name not preceded by a word character, nor by a property dot -- but a spread's
# "..." is not a property access, so `{...Ee}` normalises like any other name.
NAME = re.compile(r'(?<![\w$])(?:(?<=\.\.\.)|(?<!\.))[A-Za-z_$][\w$]{0,2}(?![\w$])')
LINE_BREAK = re.compile(r'(?<=[;{}])')


def normalise(text: str) -> str:
    return NAME.sub(lambda m: m.group(0) if m.group(0) in KEYWORDS else '_', text)


def _stable_runs(before: str) -> list[str]:
    """Literal runs of the old site that contain no minified name, longest first."""
    runs = re.split(r'_', normalise(before))
    return sorted({r for r in runs if len(r) >= 8}, key=len, reverse=True)


def region_for(text: str, before: str, near: str | None, window: int):
    """The spans where the old site should be, or None with a reason."""
    if near:
        spans = _region(text, near, window)
        if spans:
            return spans, f'landmark {near!r}'
    for run in _stable_runs(before)[:3]:
        if run in text:
            return _region(text, run, max(window, 2 * len(before))), f'stable text {run[:40]!r}'
    return None, 'no landmark and no stable text from the last good site is left in this build'


def diff(text: str, before: str, near: str | None, window: int, context: int = 1) -> list[str]:
    """A unified diff, identifier-normalised, between the last good site and the
    best-aligned stretch of the new build's region; or one line saying why not."""
    spans, how = region_for(text, before, near, window)
    if spans is None:
        return [how]
    old = normalise(before)
    best = None
    for lo, hi in spans:
        new = normalise(text[lo:hi])
        sm = difflib.SequenceMatcher(None, new, old, autojunk=False)
        m = sm.find_longest_match(0, len(new), 0, len(old))
        start = max(0, m.a - m.b)
        piece = new[start:start + len(old) + 40]
        score = difflib.SequenceMatcher(None, piece, old, autojunk=False).ratio()
        if best is None or score > best[0]:
            best = (score, piece)
    score, piece = best
    def split(s):
        return [line for line in LINE_BREAK.split(s) if line]
    lines = difflib.unified_diff(split(old), split(piece),
                                 'last good', 'this build', n=context, lineterm='')
    return [f'region: {how}; similarity {score:.0%}'] + list(lines)
