# Platform support

`dcc-patcher` patches the native Claude Code CLI, a Bun-compiled executable. Each operating system packs that executable differently, so support goes one container format at a time.

| Platform | Claude Code binary | Status |
|---|---|---|
| Windows x64 | PE (`.bun` section) | **Supported.** Every bundled patch applies unchanged on Claude Code 2.1.278 to 2.1.295; the launcher, `dcc-env` and `status` are in daily use |
| Linux x64 | ELF (`.bun` section) | Planned |
| macOS | Mach-O | Planned |
| Windows / Linux arm64 | PE / ELF | Untested |

The tool itself is Python 3.11+ with the standard library only.
