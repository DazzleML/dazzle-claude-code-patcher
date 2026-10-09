# Contributing to dazzle-claude-code-patcher

Thank you for considering contributing to dazzle-claude-code-patcher!

## Development Setup

### Prerequisites

- **Python 3.11+** (the patch specs are read with `tomllib`)
- **Git**

### Clone and Install

```bash
git clone https://github.com/DazzleML/dazzle-claude-code-patcher.git
cd dazzle-claude-code-patcher
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# or: .venv\Scripts\activate     # Windows
pip install -e ".[dev]"
```

### Run Tests

```bash
python -m pytest tests/ -v
```

## Project Structure

```
dcc_patcher/
  cli.py              # The dcc-patcher command: check, apply, use, install-shim, status, ...
  engine.py, spec.py  # Locate, apply and verify a patch spec; the spec format
  containers/         # The executable formats (PE today); the Bun module graph
  lock.py, diagnose.py# Lockfiles, and the diff against the last good build
  launch.py           # What `claude` runs: the current build, rebuilt on update
  builds.py, originals.py
                      # The builds folder; the original Claude Code kept beside each build
  install.py, winpath.py, regfile.py, resolve.py, style.py
                      # The shims, PATH, .reg backups, status
  patches/            # The bundled patch specs, one folder each (patch.toml + README)
  shims/              # The claude / claude-stock launcher templates
  _version.py         # Version (PEP 440)
bin/                  # dcc-env for cmd, PowerShell and sh (installed beside dcc-patcher)
docs/                 # launcher.md (builds, PATH, backups, undoing by hand), platform-support.md
tests/
  conftest.py         # Shared fixtures (the registry and PATH are always stubbed)
  test_*.py           # Test files
  checklists/         # Human test checklists, one per version
  one-offs/           # Quick checks, proof-of-concept scripts, red-green audits
scripts/
  repokit-common/     # Shared tools (git subtree)
```

## Key Design Principles

1. **Tests are important** -- write tests for new features, and never a test that can touch the real `PATH`, registry or session files (the fixtures stub them)
2. **One-offs graduate** -- quick tests in `tests/one-offs/` can be promoted to proper tests
3. **Fails closed** -- a patch that doesn't match exactly as expected writes nothing
4. **Clean commits** -- subjects read `vX.Y.Z: what changed`, bodies say why
