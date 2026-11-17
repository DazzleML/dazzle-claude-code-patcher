# Patch H: history past compaction

**Status:** `dcc-patcher check` passes on Claude Code 2.1.278 to 2.1.326 (Windows). In daily use on 2.1.289 to 2.1.296: a real session file of 5,947 messages and 5 compactions resumes to its first record, and the model receives the same request as stock (token parity measured on 2.1.289 and 2.1.290). Since v0.2.5 the walk also crosses a compaction whose preserved messages reached disk after the summary (a 7,347-message file with 4 such compactions, simulated on every session file on one machine: 54 of 66 reach their first in-file message; the rest start with a boundary whose history is in another file, patch J's territory).
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
| walker | at a compaction row, continue where the helper says; at a row whose parent is missing or already on the chain, take the parent the prune recorded for it before the walker's own 5-second fallback |

The helper (`__dzCross`) picks where the walk continues past a compaction row:
1. its `logicalParentUuid`, if that message isn't on the chain yet;
2. else the last preserved message not yet on the chain (an earlier compaction, whose preserved tail sits after its summary);
3. else the original parent of the preserved segment's head, which the prune recorded before relinking it (the last compaction);
4. else, when that pick is missing or already on the chain, the latest row before the boundary in file order that isn't on the chain yet, on the same side (`isSidechain`) and of a chain type (`user`, `assistant`, `attachment`, `system`).

**Why rule 4 exists (v0.2.5).** A session file is append-only and deduplicated by uuid, and a compaction can run while a turn's messages are still queued for writing. Those messages reach the file after the boundary and the summary, with their parent links already rewired onto the summary (the compaction's `preservedMessages`). When *all* of a compaction's preserved messages were in flight, the head's original parent is written nowhere: rule 3 finds the summary, which the walk has already visited, and stock's own fallback (the nearest unseen row within 5 seconds) can't bridge the minutes between the boundary and the last row before it. Three shapes occur, and the rules tell them apart by what is already on the chain when the walk arrives: preserved rows in place with only the tail late (rule 2), all preserved rows late (rule 4), and nothing after the summary at all, where the walk reaches the preserved rows from their tail and arrives at the head from the wrong side (the walker's relinked-head fallback, which reads the same record rule 3 does). Measured on one machine on 2026-10-11: 34 of 200 compactions in 31 of 66 session files had the all-late shape, written by Claude Code 2.1.205 through 2.1.292. The one shape the rules can't cross is a file that *opens* with a boundary (a continued session): its history is in another file, which is patch J's job.

**What the model receives is unchanged.** The request sent to the API is cut at the last compaction separately, after this loading code. The proof of concept measured 527,575 tokens patched vs 527,509 stock, and the stock run hit the cache the patched one wrote, so the prefix was identical.

**Recognising an upstream fix:** if the walker itself starts reading `logicalParentUuid`, the patch reports `upstream-fixed` and is not applied. That is an educated guess about how a fix would look, not a known fix; revisit it when Anthropic ships one.

## For plugin authors: detecting this patch

A build with this patch sets `DCC_PATCH_H=history-v1` in Claude Code's own environment when the module loads (since v0.1.8). Plugin hooks run in an isolated context that can't see the patch's JavaScript, but `$.env.get` reads that environment:

```js
const fullReach = $.env.get("DCC_PATCH_H");   // "history-v1" on a patched build; nothing on stock
```

The launcher adds two more when it starts a patched build (since v0.2.3), read from the build's lockfile, so a plugin can see every patch at once and the version that made the build:

```js
const patches = $.env.get("DCC_PATCHES");     // "B=banner-label-v1,B2=banner-label-flicker-free-v1,H=history-v1,J=cross-file-v1,R=rows-v1,V=version-label-v1"
const patcher = $.env.get("DCC_PATCHER");     // "0.2.3"
```

Each patch's tag is its signature's and changes only when that patch's behaviour does. `R=rows-v1` means the normal view draws a row at each compaction summary (a mark on one has somewhere to land); `J=cross-file-v1` means a continued session reaches into its earlier file. `DCC_PATCH_H` is set by the patch itself, so it is there even when the build is run directly, without the launcher; `DCC_PATCHES` and `DCC_PATCHER` are the launcher's. When the launcher starts stock (`claude-stock`, `dcc-env stock`, `dcc-patcher use stock`), it removes all three from the environment first, so a stock Claude Code started from inside a patched session's shell doesn't inherit a signal that isn't true of it.

When it's set, a resumed session's messages from before its compactions are real rows you can scroll to; when it isn't, they aren't. The variable is inherited by the processes Claude Code starts (tools, MCP servers), which is harmless. The value changes only if the patch's behaviour changes.

## Verify

- `dcc-patcher check <claude.exe>`: every edit `APPLIES`.
- Then the High-Value section of [the checklist](../../../tests/checklists/v0.2.0__Phase2__history-past-compaction.md):
  - the patched copy starts;
  - a resumed copy of a compacted session scrolls to its first prompt;
  - the request size matches stock within 0.1%.
- `--debug` builds also write `dcc-debug.log` (or `DZ_DEBUG_LOG`), with one `walk: boundary ...` line per compaction crossed.
