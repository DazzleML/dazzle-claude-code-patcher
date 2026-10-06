"""The lockfile: what one build was patched with, recorded so it can be reproduced
and so the next build's diagnosis has a last-good baseline (design C3: "a prebuilt
is a cache of a known-good result").

One JSON file per output exe, beside it as `<output>.dcc-lock.json`: the input and
output sha256, the Claude Code version, and for each patch its module, the source
hashes before and after, and every edit's sites with the exact text replaced.
"""
from __future__ import annotations

import hashlib
import json

from ._version import DISPLAY_VERSION

FORMAT = 1


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build(input_image: bytes, output_image: bytes | None, version: str, container, results) -> dict:
    patches = []
    for r in results:
        entry = {'id': r.patch.id, 'status': r.status, 'signature': r.patch.signature}
        if r.module is not None:
            m = container.module(r.module)
            entry['module'] = {'index': r.module, 'name': m['name'],
                               'source_sha256': _sha(container.source(r.module))}
        if r.source is not None:
            entry['module']['patched_sha256'] = _sha(r.source)
        if r.edits:
            entry['edits'] = [{'name': e.name, 'status': e.status, 'expect': e.expect,
                               'sites': [{'offset': s.offset, 'before': s.before, 'after': s.after}
                                         for s in e.sites]} for e in r.edits]
        patches.append(entry)
    return {'format': FORMAT, 'tool': f'dcc-patcher {DISPLAY_VERSION}', 'claude_version': version,
            'input_sha256': _sha(input_image),
            'output_sha256': _sha(output_image) if output_image is not None else None,
            'patches': patches}


def dumps(lock: dict) -> str:
    return json.dumps(lock, indent=2) + '\n'
