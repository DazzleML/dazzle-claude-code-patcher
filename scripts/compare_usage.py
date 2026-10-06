"""Compare what the model was sent in two resumed session copies (read-only).

For each session file: find the last typed prompt, then the assistant rows that
answered it, and print the API's own usage figures for the first of them: input
tokens, cache creation, cache read, and their total (the size of the request).
Also counts compaction rows after the prompt, to catch an auto-compaction
triggered by the resume.

Used by the history patch's checklist to show that a patched build sends the model
the same request as stock (HV.5). Graduated from the proof of concept.

usage: python scripts/compare_usage.py <session id or .jsonl> [<session id or .jsonl> ...]
"""
import glob
import json
import os
import sys

# The same folder Claude Code uses: the test config when CLAUDE_CONFIG_DIR is set.
PROJECTS = os.path.join(os.environ.get('CLAUDE_CONFIG_DIR') or os.path.expanduser('~/.claude'), 'projects')


def path_for(arg):
    """A .jsonl path as given, or the session id looked up in every project folder."""
    if arg.endswith('.jsonl'):
        return arg
    hits = glob.glob(os.path.join(PROJECTS, '*', arg + '.jsonl'))
    if len(hits) != 1:
        sys.exit(f'{arg}: found in {len(hits)} project folders; pass the .jsonl path instead')
    return hits[0]


def prompt_text(o):
    if o.get('type') != 'user' or o.get('isMeta'):
        return None
    c = (o.get('message') or {}).get('content')
    if isinstance(c, str):
        return c
    if isinstance(c, list) and not any(isinstance(b, dict) and b.get('type') == 'tool_result' for b in c):
        t = [b.get('text', '') for b in c if isinstance(b, dict) and b.get('type') == 'text']
        return ' '.join(t) if t else None
    return None


for arg in sys.argv[1:]:
    p = path_for(arg)
    rows = [json.loads(l) for l in open(p, encoding='utf-8') if l.strip()]
    last = max((i for i, r in enumerate(rows) if prompt_text(r) is not None), default=None)
    print(f'== {os.path.basename(p)}  ({len(rows)} rows)')
    if last is None:
        print('   no typed prompt found')
        continue
    print(f'   last prompt @{last}: {prompt_text(rows[last])[:60]!r}  ({rows[last].get("timestamp")})')
    after = rows[last + 1:]
    replies = [r for r in after if r.get('type') == 'assistant' and (r.get('message') or {}).get('usage')]
    compactions = sum(1 for r in after if r.get('subtype') == 'compact_boundary')
    if not replies:
        print('   no assistant reply with usage after it')
    else:
        m = replies[0]['message']
        u = m['usage']
        inp, cc, cr = u.get('input_tokens', 0), u.get('cache_creation_input_tokens', 0), u.get('cache_read_input_tokens', 0)
        print(f'   model {m.get("model")}')
        print(f'   input {inp:,}  cache_creation {cc:,}  cache_read {cr:,}  TOTAL sent {inp + cc + cr:,}  output {u.get("output_tokens", 0):,}')
    print(f'   compactions after the prompt: {compactions}')
