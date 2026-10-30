# Patch R: compaction rows in the normal view

**Status:** `dcc-patcher check` passes on Claude Code 2.1.278 to 2.1.314 (Windows). Live check pending.
**Tracking:** [DazzleML/dazzle-claude-code-patcher#7](https://github.com/DazzleML/dazzle-claude-code-patcher/issues/7).

## Symptom

With the history patch, a resumed session scrolls back past its compactions in both views, but they don't start on the same row. The transcript (`Ctrl+O`, `Ctrl+Home`) begins with the compaction summary ("Compact summary"); the normal screen begins one step later, at the first rows after it, and shows nothing at any compaction it walks past. A bookmark on a compaction summary has nowhere to land in the normal view.

## Root cause

The normal screen builds its row list through a filter that drops every user row marked `isVisibleInTranscriptOnly` unless the screen is the transcript:

```js
function P7r(e, n) {                       // n: the screen is the transcript (2.1.295's names)
  if (e.type !== "user") return true;
  if (e.isMeta) return pN(e.origin);
  if (e.isVisibleInTranscriptOnly && !n) return false;
  return true;
}
```

Compaction summaries are created with that mark. The row renderer behind the filter already draws a summary on the normal screen, as a bold `Compact summary (ctrl+o to expand)` line with the text itself shown only in the transcript, so nothing else is missing.

## Fix shape

One edit, in the module found by the string `tengu_filtered_trailing_thinking_block`: the filter keeps a row that is a compaction summary (`isCompactSummary`) even when it is transcript-only. Every other transcript-only row stays hidden, so the normal screen gains exactly the compaction rows and nothing else.

What the model receives is unchanged: the filter runs when the screen is drawn, after the request is built.

## Verify

- `dcc-patcher check <claude.exe>`: the edit `APPLIES` once.
- Live: resume a session with at least one compaction on the patched build. `Ctrl+Home` in the normal view lands on the same `Compact summary` row as `Ctrl+O`, `Ctrl+Home`; each compaction the history patch walks past shows that line at its place; `Ctrl+O` on it shows the summary text.
