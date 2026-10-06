# Patch H: history past compaction

**Status:** `dcc-patcher check` passes on Claude Code 2.1.278 to 2.1.289 (Windows). The fix was live-tested on 2.1.289 as a proof of concept; a live run of this spec's own build is pending (see the checklist below).
**Tracking:** [DazzleML/dazzle-claude-code-patcher#1](https://github.com/DazzleML/dazzle-claude-code-patcher/issues/1). Not yet reported upstream.

## Symptom

After a restart or `claude --resume`, the conversation shown on screen starts at the last compaction. Everything before it is still in the session file on disk, but nothing in the interface brings it back: `Ctrl+O` and `Ctrl+Home` stop at the compaction summary. Setting `CLAUDE_CODE_DISABLE_PRECOMPACT_SKIP=1` does not help in 2.1.289.

## Root cause

Loading a session for display cuts the history in four places, all in one module (found by the stable string `tengu_chain_parent_cycle`). Each cut on its own is enough to hide the older history.

1. **The loader skips the bytes before the last compaction** in session files over 5 MiB, unless the `CLAUDE_CODE_DISABLE_PRECOMPACT_SKIP` variable is set.
2. **A walk before parsing** (also for files over 5 MiB) keeps only the lines reachable from the newest message by `parentUuid`, and a compaction row has none. In 2.1.289 this walk is gated only by file size, so the variable in cut 1 no longer turns it off.
3. **A prune deletes every message before the last compaction** when the compaction preserved a segment of recent messages, and relinks that segment onto the summary.
4. **The chain walker stops at a compaction row,** because its `parentUuid` is null; the row records where it came from in `logicalParentUuid` instead.

## Fix shape

Six edits (seven sites) plus a small helper inserted at the module's start:

| Edit | Change |
|---|---|
| loader | always parse the lines before the last compaction |
| prune, 1 | before relinking, remember the preserved segment's original parent |
| prune, 2 | keep the messages before the last compaction instead of deleting them |
| prune, 3 | don't rewire the kept messages themselves |
| pre-parse walk (2 sites) | keep lines that are off the newest chain |
| walker | at a compaction row, continue where the helper says |

The helper (`__dzCross`) picks where the walk continues past a compaction row:
1. its `logicalParentUuid`, if that message isn't on the chain yet;
2. else the last preserved message not yet on the chain (an earlier compaction, whose preserved tail sits after its summary);
3. else the original parent of the preserved segment's head, which the prune recorded before relinking it (the last compaction).

**What the model receives is unchanged.** The request sent to the API is cut at the last compaction separately, after this loading code. The proof of concept measured 527,575 tokens patched vs 527,509 stock, and the stock run hit the cache the patched one wrote, so the prefix was identical.

**Recognising an upstream fix:** if the walker itself starts reading `logicalParentUuid`, the patch reports `upstream-fixed` and is not applied. That is an educated guess about how a fix would look, not a known fix; revisit it when Anthropic ships one.

## Verify

- `dcc-patcher check <claude.exe>`: every edit `APPLIES`.
- Then the High-Value section of [the checklist](../../tests/checklists/v0.2.0__Phase2__history-past-compaction.md):
  - the patched copy starts;
  - a resumed copy of a compacted session scrolls to its first prompt;
  - the request size matches stock within 0.1%.
- `--debug` builds also write `dcc-debug.log` (or `DZ_DEBUG_LOG`), with one `walk: boundary ...` line per compaction crossed.
