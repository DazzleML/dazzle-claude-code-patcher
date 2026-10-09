# Roadmap

The living roadmap is **[issue #1](https://github.com/DazzleML/dazzle-claude-code-patcher/issues/1)**. This file is a summary.

| Phase | What it means | Status |
|---|---|---|
| 1. The tool | Windows container support, patch spec format, a locate / apply / verify engine that fails closed, and a `check` report with diagnosis | Done (v0.1.3) |
| 2. First patch | History past compaction: after a restart or `--resume`, scroll back to the start of the conversation; a patched build labels itself | Done (v0.1.3); in daily use on 2.1.289 to 2.1.295 |
| 3. Operation | `claude` runs the patched build, re-patches on each Claude Code update, falls back to stock when a patch needs attention; `dcc-env`, `status`, PATH backups, kept originals | Done (v0.1.5 to v0.1.11) |
| 4. Reach | Any point in a conversation, for claude-bookmarks: history across session files (built, live check pending); the normal view drawing the compaction rows Ctrl+O draws (#7); plugins detecting the patch (built); loading older history on demand (#10) | In progress |
| 5. More patches and platforms | Container hardening; Linux, then macOS | Planned |
| Release | The bundled patches ship with the package (done); v0.2.0 on PyPI | v0.2.0 |
