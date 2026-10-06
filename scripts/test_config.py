"""A throwaway Claude Code config folder for live tests, so no test can touch the
real ~/.claude.

Claude Code keeps everything per user in its config folder: the sessions
(projects/), the global .claude.json, the login (.credentials.json), settings,
plugins. CLAUDE_CONFIG_DIR moves all of it; in the 2.1.290 binary both the global
config and the credentials resolve inside it. One exception: IDE lock files still
go to ~/.claude/ide. A run in this folder starts with no user settings, CLAUDE.md,
skills, hooks or plugins, so a patched and a stock run see the same prompt.

The folder is %LOCALAPPDATA%/dazzle-claude-code-patcher/test-config, or
$DCC_TEST_CONFIG. Log in once inside it (start claude with the variables from `env`
and use /login); the login stays in the folder for later runs.

What is ours, and what is Claude Code's. A fork, a branch or a continuation into a
new file can make a session that looks just like one of our copies, with the same
messages under a new id, so a copy is never recognised by its content. Instead, every
copy is marked when it is made: its id starts with dcc0dcc0- (copy_session.MARK), and
it is entered in the ledger, copies.tsv in this folder (id, time, source, the
source's sha256). move-in refuses any id that is neither marked nor in the ledger.

usage: python scripts/test_config.py <command>
  env                     print the lines that select the folder (cmd, PowerShell, bash)
  copy <session .jsonl>   copy a real session into it under a new, marked id (the original is only read)
  move-in <id> ...        move a test copy, and what resuming it left behind, from ~/.claude into it
                          (only marked or ledgered ids)
  move-back [<id> ...]    undo move-in (every recorded id when none is given)
  record <id> <note>      enter a copy made some other way (e.g. by hand) in the ledger, so move-in accepts it
  list                    the sessions in it, each labelled marked / ledger / UNRECORDED
"""
import glob
import hashlib
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from copy_session import MARK, copy  # noqa: E402

HOME = os.path.expanduser('~/.claude')
ROOT = os.environ.get('DCC_TEST_CONFIG') or os.path.join(
    os.environ.get('LOCALAPPDATA', os.path.expanduser('~/.local/share')), 'dazzle-claude-code-patcher', 'test-config')
RECORD = os.path.join(ROOT, 'moved-in.tsv')
LEDGER = os.path.join(ROOT, 'copies.tsv')


def ledger_ids():
    if not os.path.exists(LEDGER):
        return set()
    with open(LEDGER, encoding='utf-8') as f:
        return {line.split('\t')[0] for line in f if line.strip() and not line.startswith('#')}


def provenance(sid):
    """'marked' or 'ledger' for a test copy we made; None for anything else."""
    if sid.startswith(MARK + '-'):
        return 'marked'
    return 'ledger' if sid in ledger_ids() else None


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def leftovers(sid, base):
    """Every path under base that belongs to session sid alone."""
    patterns = [f'projects/*/{sid}.jsonl', f'projects/*/{sid}', f'file-history/{sid}',
                f'session-env/{sid}', f'session-states/{sid}.*', f'todos/{sid}-*',
                f'sesslogs/*__{sid}_*']
    return sorted({p for pat in patterns for p in glob.glob(os.path.join(base, pat))})


def cmd_env(_):
    print(f'cmd.exe:     set CLAUDE_CONFIG_DIR={ROOT}& set DISABLE_AUTOUPDATER=1')
    print(f'PowerShell:  $env:CLAUDE_CONFIG_DIR = "{ROOT}"; $env:DISABLE_AUTOUPDATER = "1"')
    print(f'bash:        export CLAUDE_CONFIG_DIR="{ROOT}" DISABLE_AUTOUPDATER=1')
    if not os.path.exists(os.path.join(ROOT, '.credentials.json')):
        print('\nnot logged in yet: start claude with these set, then /login (once)')
    return 0


def cmd_copy(args):
    if len(args) != 1:
        print('usage: test_config.py copy <session .jsonl>', file=sys.stderr)
        return 2
    src = os.path.abspath(args[0])
    dest = os.path.join(ROOT, 'projects', os.path.basename(os.path.dirname(src)))
    digest = _sha256(src)
    new_id, dst, rows, changed, _ = copy(src, dest)
    with open(LEDGER, 'a', encoding='utf-8') as f:
        f.write(f'{new_id}\t{time.strftime("%Y-%m-%d %H:%M:%S")}\t{src}\t{digest}\n')
    print(f'copied {rows} rows ({changed} sessionIds rewritten) into the test config')
    print(f'copy:   {dst}')
    print(f'resume: claude --resume {new_id}   (with CLAUDE_CONFIG_DIR set; see `env`)')
    return 0


def cmd_record(args):
    """A person's word that <id> is a test copy: the one way into the ledger besides `copy`."""
    if len(args) < 2:
        print('usage: test_config.py record <session id> <note: who made it, from what>', file=sys.stderr)
        return 2
    sid, note = args[0], ' '.join(args[1:])
    if sid in ledger_ids():
        print(f'{sid}: already in the ledger')
        return 0
    os.makedirs(ROOT, exist_ok=True)
    with open(LEDGER, 'a', encoding='utf-8') as f:
        f.write(f'{sid}\t{time.strftime("%Y-%m-%d %H:%M:%S")}\t{note}\t-\n')
    print(f'{sid}: recorded as a test copy ({note})')
    return 0


def cmd_move_in(ids):
    if not ids:
        print('usage: test_config.py move-in <session id> ...', file=sys.stderr)
        return 2
    os.makedirs(ROOT, exist_ok=True)
    for sid in ids:
        if provenance(sid) is None:
            print(f'{sid}: not a test copy we made (no {MARK}- mark, not in {LEDGER}); refused. '
                  'A real session, or a fork Claude Code made, looks the same from outside.', file=sys.stderr)
            return 1
        paths = leftovers(sid, HOME)
        main = next((p for p in paths if p.endswith('.jsonl')), None)
        if main is None:
            print(f'{sid}: no session file under {HOME}; skipped')
            continue
        if time.time() - os.path.getmtime(main) < 120:
            print(f'{sid}: written in the last two minutes, may still be open; skipped')
            continue
        moved = []
        for p in paths:
            dst = os.path.join(ROOT, os.path.relpath(p, HOME))
            if os.path.exists(dst):
                print(f'{sid}: {dst} already exists; stopping', file=sys.stderr)
                return 1
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.rename(p, dst)                     # same drive: a rename, timestamps kept
            moved.append((p, dst))
            with open(RECORD, 'a', encoding='utf-8') as f:
                f.write(f'{sid}\t{p}\t{dst}\n')
        print(f'{sid}: moved {len(moved)} paths into the test config')
    return 0


def cmd_move_back(ids):
    if not os.path.exists(RECORD):
        print('nothing recorded as moved in')
        return 0
    with open(RECORD, encoding='utf-8') as f:
        rows = [line.rstrip('\n').split('\t') for line in f if line.strip()]
    chosen = set(ids) or {r[0] for r in rows}
    keep = []
    for sid, src, dst in rows:
        if sid not in chosen:
            keep.append((sid, src, dst))
            continue
        if os.path.exists(src):
            print(f'{sid}: {src} exists again; left in the test config', file=sys.stderr)
            keep.append((sid, src, dst))
            continue
        os.makedirs(os.path.dirname(src), exist_ok=True)
        os.rename(dst, src)
        print(f'{sid}: moved back {os.path.relpath(src, HOME)}')
    with open(RECORD, 'w', encoding='utf-8') as f:
        f.writelines('\t'.join(r) + '\n' for r in keep)
    return 0


def cmd_list(_):
    found = sorted(glob.glob(os.path.join(ROOT, 'projects', '*', '*.jsonl')), key=os.path.getmtime)
    print(f'{ROOT}  ({"logged in" if os.path.exists(os.path.join(ROOT, ".credentials.json")) else "not logged in"})')
    for p in found:
        sid = os.path.basename(p)[:-6]
        print(f'  {sid}  {provenance(sid) or "UNRECORDED":10}  {os.path.getsize(p) / 1048576:6.1f} MB  '
              f'{time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(p)))}  {os.path.basename(os.path.dirname(p))}')
    if not found:
        print('  (no sessions)')
    return 0


COMMANDS = {'env': cmd_env, 'copy': cmd_copy, 'record': cmd_record, 'move-in': cmd_move_in,
            'move-back': cmd_move_back, 'list': cmd_list}

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__.strip().split('usage:')[1].strip())
    sys.exit(COMMANDS[sys.argv[1]](sys.argv[2:]))
