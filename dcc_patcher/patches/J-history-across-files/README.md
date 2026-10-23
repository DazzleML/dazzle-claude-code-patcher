# Patch J: history across session files

Derived from ojura/claude-patches (MIT), Patch J: "Resolve cross-file logicalParentUuid at session load". That patch targets the VS Code extension; this is the same idea for the native CLI, as a structural spec. Credit to its author.

## The problem

When a conversation runs out of context and continues, or is forked, Claude Code starts a new session file. Its first line is a compaction boundary whose `logicalParentUuid` names the last message of the conversation so far, and that message lives in the **previous** file. Patch H follows a boundary's `logicalParentUuid` when the walk back reaches it. But the message isn't in the file that was loaded, so the walk stops at the start of the new file: "back to the very beginning" means only the beginning of this file.

## What this patch does

Before the loader reads a session file's own lines, J:

1. lists the `logicalParentUuid`s the file names but doesn't contain;
2. looks for each in the other `.jsonl` files of the same folder, newest first;
3. feeds that file's lines **up to and including** the one holding the message to the loader's own entry handler. Later lines are left out, because they belong to the other session's own continuation;
4. repeats on what it added, so a grandparent session is reached too (at most 10 times).

Then H's walk crosses the boundary into those messages and on back to the first message of the original conversation.

**Needs patch H.** Without H, the extra messages are loaded but nothing walks to them.

## What it does not change

The model's request. The messages from the earlier file sit before a compaction boundary, which is where the model's context already starts. It isn't verified yet: token parity is part of the live check.

## When something is missing

A missing or unreadable earlier file, a damaged line, or any error ends the search, and the session loads exactly as it would without this patch. (ojura's version fails loudly instead; issue #6 asks for a clean stop.)

## Cost

Only sessions that point outside their file pay anything. Those pay for reading the session file once more, plus the earlier file(s), on every load. A sibling the search doesn't find means every other `.jsonl` in the folder is read. The cost on a real pair of files is part of the live check.

## Limits

- Only the same project folder is searched. A conversation continued under a different project folder isn't followed.
- `check` passes on every saved build, 2.1.278 to 2.1.309. On 2.1.290 the edit lands in the loader that opens files by path. That release read storage-backed sessions through a second function, which isn't patched. Later releases use one function for both.
