"""Patch specs, format 1.

A patch is data, not code: what it means and how to find it, so it survives the
minified renames of each Claude Code release (design document 2026-10-05: exact-text
anchors broke on 6 of the last 7 builds; structural ones held for most edits).

    format = 1
    id = "H"
    title = "History past compaction"
    module_marker = "tengu_chain_parent_cycle"   # finds the module by a stable string
    modules = 1                                  # optional: how many modules it must find
    prelude = "..."                              # optional JS inserted at the module's start

    signature = "/*dazzle-claude-code:history-v1*/"  # optional; marks a patched module
    [upstream_fixed]                             # optional: when this matches, the
    near = "tengu_chain_parent_cycle"            # bug is fixed upstream and the
    pattern = 'logicalParentUuid'                # patch is not applied

    [[edit]]
    name = "walker: cross a compaction boundary"
    near = "tengu_chain_parent_cycle"            # optional landmark ...
    window = 3000                                # ... and how far around it to look
    pattern = 'let (?P<w>[\\w$]+)=(?P<h>[\\w$]+)\\.parentUuid;...'
    replace = 'let @@w@@=@@h@@.parentUuid;...'
    expect = 1                                   # matches required, or the patch fails

A landmark (`near`) scopes a search to `window` characters either side of every
place the landmark occurs. Patterns are Python regular expressions over the module
source (read as Latin-1, so one character is one byte). A named
group captured by one edit can be used by any later edit, in its pattern and its
replacement, as @@name@@ (ASCII, so it can't clash with JavaScript's ${...}). Bun
stores ASCII-only module source as Latin-1, so a spec must be ASCII.

A few names are filled in by the engine rather than captured (RESERVED):
@@dcc_version@@ is this tool's version, so a patch can label the build it made.

A patch whose marker is in several modules says how many (`modules = n`); each one
gets the patch's edits, prelude and signature, and any other count is refused.
"""
from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field

FORMAT = 1
PLACEHOLDER = re.compile(r'@@([A-Za-z_][A-Za-z0-9_]*)@@')
SIGNATURE = re.compile(r'/\*(?:(?!\*/)[ -~])*\*/')
KNOWN = {'format', 'id', 'title', 'module_marker', 'modules', 'edit', 'prelude',
         'debug_prelude', 'signature', 'upstream_fixed', 'issue'}
RESERVED = {'dcc_version'}


class SpecError(Exception):
    """The spec file is malformed; the message names the field."""


@dataclass
class Edit:
    name: str
    pattern: str
    replace: str
    expect: int = 1
    near: str | None = None
    window: int = 4000
    debug_only: bool = False


@dataclass
class Probe:
    """A pattern searched for but never replaced (the upstream-fixed detector)."""
    pattern: str
    near: str | None = None
    window: int = 4000


@dataclass
class Patch:
    id: str
    title: str
    module_marker: str
    edits: list[Edit]
    modules: int = 1
    signature: str = ''
    prelude: str = ''
    debug_prelude: str = ''
    upstream_fixed: Probe | None = None
    issue: str | None = None
    meta: dict = field(default_factory=dict)


def _ascii(value: str, where: str) -> str:
    if not value.isascii():
        raise SpecError(f'{where}: must be ASCII (Bun stores module source as Latin-1)')
    return value


def load(path) -> Patch:
    with open(path, 'rb') as f:
        try:
            raw = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise SpecError(f'{path}: not valid TOML: {e}') from None
    return parse(raw, str(path))


def parse(raw: dict, where: str = 'spec') -> Patch:
    if raw.get('format') != FORMAT:
        raise SpecError(f'{where}: format must be {FORMAT}, got {raw.get("format")!r}')
    for key in ('id', 'title', 'module_marker'):
        if not isinstance(raw.get(key), str) or not raw[key]:
            raise SpecError(f'{where}: missing or empty "{key}"')
    edits_raw = raw.get('edit')
    if not isinstance(edits_raw, list) or not edits_raw:
        raise SpecError(f'{where}: needs at least one [[edit]]')
    modules = raw.get('modules', 1)
    if not isinstance(modules, int) or isinstance(modules, bool) or modules < 1:
        raise SpecError(f'{where}: modules must be a positive integer')
    edits, captured = [], set(RESERVED)
    for i, e in enumerate(edits_raw, 1):
        at = f'{where}: edit {i}'
        for key in ('name', 'pattern', 'replace'):
            if not isinstance(e.get(key), str) or (key != 'replace' and not e[key]):
                raise SpecError(f'{at}: missing "{key}"')
        name = e['name']
        pattern = _ascii(e['pattern'], f'{at} ({name}) pattern')
        replace = _ascii(e['replace'], f'{at} ({name}) replace')
        expect = e.get('expect', 1)
        if not isinstance(expect, int) or expect < 1:
            raise SpecError(f'{at} ({name}): expect must be a positive integer')
        try:
            groups = set(re.compile(PLACEHOLDER.sub('X', pattern)).groupindex)
        except re.error as err:
            raise SpecError(f'{at} ({name}): pattern is not a valid regex: {err}') from None
        for used in PLACEHOLDER.findall(pattern + replace):
            if used not in captured and used not in groups:
                raise SpecError(f'{at} ({name}): @@{used}@@ is not captured by this or an earlier edit')
        captured |= groups
        edits.append(Edit(name=name, pattern=pattern, replace=replace, expect=expect,
                          near=e.get('near'), window=int(e.get('window', 4000)),
                          debug_only=bool(e.get('debug_only', False))))
    signature = _ascii(raw.get('signature', f'/*dazzle-claude-code:{raw["id"]}*/'), f'{where}: signature')
    if not SIGNATURE.fullmatch(signature):
        raise SpecError(f'{where}: signature must be one JavaScript comment, /* ... */')
    return Patch(id=raw['id'], title=raw['title'], module_marker=raw['module_marker'], edits=edits,
                 modules=modules, signature=signature,
                 prelude=_ascii(raw.get('prelude', ''), f'{where}: prelude'),
                 debug_prelude=_ascii(raw.get('debug_prelude', ''), f'{where}: debug_prelude'),
                 upstream_fixed=_probe(raw.get('upstream_fixed'), f'{where}: upstream_fixed'),
                 issue=raw.get('issue'),
                 meta={k: v for k, v in raw.items() if k not in KNOWN})


def _probe(raw, at: str) -> Probe | None:
    if raw is None:
        return None
    if not isinstance(raw, dict) or not isinstance(raw.get('pattern'), str) or not raw['pattern']:
        raise SpecError(f'{at}: needs a "pattern"')
    pattern = _ascii(raw['pattern'], f'{at} pattern')
    if PLACEHOLDER.search(pattern):
        raise SpecError(f'{at}: cannot use @@name@@ (it runs before any edit captures)')
    try:
        re.compile(pattern)
    except re.error as err:
        raise SpecError(f'{at}: pattern is not a valid regex: {err}') from None
    return Probe(pattern=pattern, near=raw.get('near'), window=int(raw.get('window', 4000)))
