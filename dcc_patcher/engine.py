"""The patch engine: locate each edit, apply it in memory, verify, fail closed.

For one patch and one module source the engine answers, per edit, one of

    APPLIES          found exactly `expect` times (one of them, when `expect` lists several)
    AMBIGUOUS        found, but not `expect` times
    MISSING          not found
    LANDMARK-GONE    the landmark that scopes the edit is not in the module

and, for the patch as a whole, `applies`, `needs-human`, `already-applied` (the
signature is in the module) or `upstream-fixed` (its detector matched). Only a patch
whose every edit APPLIES produces new source; anything else changes nothing.

Edits run in order on the source as the earlier edits left it, which is how the
proof of concept applied them and what a later edit's @@name@@ captures assume.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ._version import DISPLAY_VERSION
from .spec import PLACEHOLDER, Patch, Probe

RESERVED_VALUES = {'dcc_version': DISPLAY_VERSION}   # spec.RESERVED, filled in here

APPLIES, AMBIGUOUS, MISSING, LANDMARK_GONE = 'APPLIES', 'AMBIGUOUS', 'MISSING', 'LANDMARK-GONE'


@dataclass
class Site:
    offset: int      # where the match started, in the source as earlier edits left it
    before: str
    after: str


@dataclass
class EditResult:
    name: str
    status: str
    count: int
    expect: int | tuple[int, ...]
    sites: list[Site] = field(default_factory=list)
    detail: str = ''


@dataclass
class PatchResult:
    patch: Patch
    status: str                       # applies | needs-human | already-applied | upstream-fixed
    module: int | None = None
    edits: list[EditResult] = field(default_factory=list)
    source: bytes | None = None       # the new module source, only when status == 'applies'
    detail: str = ''

    @property
    def ok(self) -> bool:
        return self.status != 'needs-human'


def _region(text: str, near: str | None, window: int) -> list[tuple[int, int]] | None:
    """The spans to search: the whole text, or `window` either side of every place
    `near` occurs, merged. None when the landmark is absent."""
    if not near:
        return [(0, len(text))]
    spans = [(max(0, m.start() - window), min(len(text), m.end() + window))
             for m in re.finditer(re.escape(near), text)]
    if not spans:
        return None
    merged = [spans[0]]
    for lo, hi in spans[1:]:
        if lo <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    return merged


def _matches(regex: re.Pattern, text: str, spans) -> list[re.Match]:
    return [m for lo, hi in spans for m in regex.finditer(text, lo, hi)]


def probe(p: Probe, text: str) -> bool:
    spans = _region(text, p.near, p.window)
    return bool(spans and _matches(re.compile(p.pattern), text, spans))


def locate(patch: Patch, source: bytes, debug: bool = False) -> PatchResult:
    """Every edit's status, and the patched source when all of them apply."""
    text = source.decode('latin-1')
    if patch.signature in text:
        return PatchResult(patch, 'already-applied', detail=f'signature {patch.signature} present')
    if patch.upstream_fixed and probe(patch.upstream_fixed, text):
        return PatchResult(patch, 'upstream-fixed', detail=f'detector matched: {patch.upstream_fixed.pattern}')
    captured: dict[str, str | None] = dict(RESERVED_VALUES)   # None: an edit's matches disagreed
    results = []
    for e in patch.edits:
        if e.debug_only and not debug:
            continue
        results.append(_one_edit(e, text, captured))
        if results[-1].status == APPLIES:
            text = _splice(text, results[-1].sites)
    if any(r.status != APPLIES for r in results):
        bad = next(r for r in results if r.status != APPLIES)
        return PatchResult(patch, 'needs-human', edits=results, detail=f'{bad.name}: {bad.status}')
    head = patch.signature + patch.prelude + (patch.debug_prelude if debug else '')
    return PatchResult(patch, 'applies', edits=results, source=(head + text).encode('latin-1'))


def _one_edit(e, text: str, captured: dict) -> EditResult:
    used = PLACEHOLDER.findall(e.pattern)
    for name in used:
        if captured.get(name) is None and name in captured:
            return EditResult(e.name, MISSING, 0, e.expect, detail=f'@@{name}@@ differs between the matches of an earlier edit')
        if name not in captured:
            return EditResult(e.name, MISSING, 0, e.expect, detail=f'@@{name}@@ was not captured (an earlier edit failed)')
    regex = re.compile(PLACEHOLDER.sub(lambda m: re.escape(captured[m.group(1)]), e.pattern))
    spans = _region(text, e.near, e.window)
    if spans is None:
        return EditResult(e.name, LANDMARK_GONE, 0, e.expect, detail=f'landmark {e.near!r} not found')
    found = _matches(regex, text, spans)
    accepted = e.expect if isinstance(e.expect, tuple) else (e.expect,)
    if len(found) not in accepted:
        status = MISSING if not found else AMBIGUOUS
        return EditResult(e.name, status, len(found), e.expect,
                          detail=f'found {len(found)}, expected {" or ".join(map(str, accepted))}')
    for name in regex.groupindex:
        values = {m.group(name) for m in found}
        captured[name] = values.pop() if len(values) == 1 else None
    sites = [Site(m.start(), m.group(0), _fill(e.replace, m, captured)) for m in found]
    return EditResult(e.name, APPLIES, len(found), e.expect, sites=sites)


def _fill(template: str, m: re.Match, captured: dict) -> str:
    """The replacement for one match: @@name@@ is this match's own group when it has
    one (so each of two sites keeps its own names), else the earlier capture."""
    def value(p):
        name = p.group(1)
        if name in m.re.groupindex and m.group(name) is not None:
            return m.group(name)
        return captured[name]
    return PLACEHOLDER.sub(value, template)


def _splice(text: str, sites: list[Site]) -> str:
    out, at = [], 0
    for s in sorted(sites, key=lambda s: s.offset):
        out += [text[at:s.offset], s.after]
        at = s.offset + len(s.before)
    return ''.join(out) + text[at:]


def locate_all(container, patches: list[Patch], debug: bool = False) -> list[PatchResult]:
    """Each patch located in its module(s); nothing is built. A module is found by
    the patch's marker, or by its signature once patched (an edit may have rewritten
    the marker itself), and there must be exactly `patch.modules` of them."""
    results = []
    for patch in patches:
        hits = sorted(set(container.find_module(patch.module_marker.encode()))
                      | set(container.find_module(patch.signature.encode())))
        if len(hits) != patch.modules:
            results.append(PatchResult(patch, 'needs-human',
                                       detail=f'module marker {patch.module_marker!r} found in {len(hits)} '
                                              f'modules, expected {patch.modules}'))
            continue
        for k in hits:
            r = locate(patch, container.source(k), debug)
            r.module = k
            results.append(r)
    return results


def apply(container, patches: list[Patch], debug: bool = False):
    """(new image or None, results). The image is None when any patch needs a human
    (fail closed) or when nothing needed changing. Each changed module is verified:
    it holds the new source, its bytecode is dropped, every other module is
    byte-identical."""
    from .containers import open_container
    image = None
    results = locate_all(container, patches, debug)
    if not all(r.ok for r in results):
        return None, results
    current = container
    for r in results:
        if r.status != 'applies':
            continue
        if image is not None:
            current = open_container(image)
            r = _relocate(r, current, debug)   # a second patch in an already-edited module
        new = current.replace_module_source(r.module, r.source)
        current.verify(new, r.module, r.source)
        image = new
    return image, results


def _relocate(r: PatchResult, container, debug: bool) -> PatchResult:
    fresh = locate(r.patch, container.source(r.module), debug)
    if fresh.status != 'applies':
        raise RuntimeError(f'{r.patch.id}: no longer applies after an earlier patch in the same module')
    r.source, r.edits = fresh.source, fresh.edits
    return r
