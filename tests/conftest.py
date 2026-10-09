"""Shared test fixtures for dazzle-claude-code-patcher."""

import pytest
from pathlib import Path

from dcc_patcher import winpath


@pytest.fixture(autouse=True)
def no_real_path(monkeypatch):
    """Rule 1b: no test can read or write the real PATH or broadcast a change.
    Tests that exercise PATH install a fake registry over these (tests/test_path.py)."""
    def refuse(*a, **k):
        raise AssertionError('a test reached the real registry or the WM_SETTINGCHANGE broadcast')
    monkeypatch.setattr(winpath, 'registry', refuse)
    monkeypatch.setattr(winpath, 'broadcast', refuse)
    monkeypatch.setattr(winpath, 'is_elevated', lambda: False)


@pytest.fixture
def tmp_project(tmp_path):
    """Create a temporary project directory for testing."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir()
    return project_dir


@pytest.fixture
def sample_data(tmp_path):
    """Create sample data files for testing."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir
