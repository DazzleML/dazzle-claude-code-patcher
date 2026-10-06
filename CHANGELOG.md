# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.2] - 2026-10-05

### Added

- `dcc_patcher.containers`: a format-neutral `Container` interface and format detection. ELF (Linux) and Mach-O (macOS) are recognised and refused by name.
- `dcc_patcher.containers.pe`: reads and rewrites the Bun module graph inside the Windows `claude.exe`. Replacing a module's source drops its bytecode so Bun compiles the new source, and `verify` checks that every other module is byte-identical. Moved from the proof of concept.
- `dcc-patcher inspect <file> [--marker TEXT]`: format, Claude Code version, module count, Bun flags, and the modules containing a marker. Unsupported formats exit 2 with a one-line message.

## [0.1.1] - 2026-10-05

### Fixed

- Tests can import `dcc_patcher` when run as the pre-push hook runs them (`python -P -m pytest`, which leaves the current directory off the import path): pytest's `pythonpath` now names the project root.

## [0.1.0] - 2026-10-05

### Added

- Project scaffold from git-repokit-template, with git-repokit-common vendored at `scripts/repokit-common/`.
- `dcc_patcher` package with a `dcc-patcher` command (placeholder; the engine is not built yet).
- README, roadmap, and platform support notes.

[Unreleased]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.1.2...HEAD
[0.1.2]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.1.1...v0.1.2
[0.1.1]: https://github.com/DazzleML/dazzle-claude-code-patcher/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/DazzleML/dazzle-claude-code-patcher/releases/tag/v0.1.0
