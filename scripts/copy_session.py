"""Copy a Claude Code session file under a new session id, for safe testing.

The original file is only read. Every row's `sessionId` is set to the new id, so
`claude --resume <new id>` opens the copy and anything a test run appends lands in
the copy only. The new id always starts with dcc0dcc0-, so a copy is recognisable
as ours wherever its id shows. By default the copy goes next to the original; `--into DIR` puts it
in DIR instead. scripts/test_config.py uses that to copy straight into the
throwaway test config folder, which is where test copies belong.

Graduated from the proof of concept.

usage: python scripts/copy_session.py <session .jsonl path> [--into DIR]
"""
import json
import os
import sys
import uuid


MARK = 'dcc0dcc0'   # the first 8 hex digits of every test copy's id: ours, at a glance


def marked_id():
    """A fresh session id that starts with MARK. Still a valid version-4 UUID: the
    first group of a v4 UUID is random, so choosing it costs nothing, and Claude Code's
    own random ids start this way about once in four billion."""
    return MARK + str(uuid.uuid4())[8:]


def copy(src, dest_dir=None):
    """Copy src under a new, marked id into dest_dir (default: beside src). Returns
    (new id, copy path, rows, sessionIds rewritten, unparsed rows kept)."""
    old_id = os.path.splitext(os.path.basename(src))[0]
    new_id = marked_id()
    dest_dir = dest_dir or os.path.dirname(src)
    os.makedirs(dest_dir, exist_ok=True)
    dst = os.path.join(dest_dir, new_id + '.jsonl')
    rows = changed = kept = 0
    with open(src, encoding='utf-8') as f, open(dst, 'x', encoding='utf-8', newline='\n') as out:
        for line in f:
            rows += 1
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                out.write(line)
                kept += 1
                continue
            if o.get('sessionId') == old_id:
                o['sessionId'] = new_id
                changed += 1
            out.write(json.dumps(o, ensure_ascii=False, separators=(',', ':')) + '\n')
    return new_id, dst, rows, changed, kept


if __name__ == '__main__':
    args = sys.argv[1:]
    into = None
    if '--into' in args:
        i = args.index('--into')
        into = args[i + 1]
        del args[i:i + 2]
    if len(args) != 1:
        sys.exit(__doc__.strip().splitlines()[-1])
    new_id, dst, rows, changed, kept = copy(args[0], into)
    print(f'copied {rows} rows ({changed} sessionIds rewritten, {kept} unparsed rows copied as-is)')
    print(f'copy:   {dst}')
    print(f'resume: claude --resume {new_id}')
