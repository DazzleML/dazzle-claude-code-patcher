# Roadmap

The living roadmap is **[issue #1](https://github.com/DazzleML/dazzle-claude-code-patcher/issues/1)**. This file is a summary.

| Phase | What it means | Status |
|---|---|---|
| 1. The tool | Windows container support, patch spec format, a locate / apply / verify engine that fails closed, and a `check` report with diagnosis | Proof of concept done |
| 2. First patch | History past compaction: after a restart or `--resume`, scroll back to the start of the conversation | Proof of concept on 2.1.289 |
| 3. Operation | A patched build beside the official `claude.exe`, kept current across updates | Planned |
| 4. More patches and platforms | History across session files; Linux, then macOS | Planned |
