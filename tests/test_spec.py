"""Patch spec format 1, on the scenarios that matter (minimal, scenario-led): the
shipped patch loads, and the mistakes a patch author is likely to make are refused
with the field named instead of failing later at apply time."""
from pathlib import Path

import pytest

from dcc_patcher import spec

ROOT = Path(__file__).resolve().parents[1]


def base(**edit):
    e = {'name': 'e1', 'pattern': 'a(?P<x>b)', 'replace': '@@x@@'}
    e.update(edit)
    return {'format': 1, 'id': 'T', 'title': 't', 'module_marker': 'm', 'edit': [e]}


def test_the_history_patch_loads():
    patch = spec.load(ROOT / 'dcc_patcher' / 'patches' / 'H-history-past-compaction' / 'patch.toml')
    assert patch.id == 'H' and len(patch.edits) == 6
    assert patch.edits[4].expect == 2


@pytest.mark.parametrize('edit, words', [
    ({'pattern': 'aé'}, 'ASCII'),
    ({'replace': '@@nope@@'}, '@@nope@@ is not captured'),
    ({'pattern': 'a(b'}, 'not a valid regex'),
    ({'expect': 0}, 'expect must be a positive integer'),
])
def test_author_mistakes_are_refused_by_name(edit, words):
    with pytest.raises(spec.SpecError, match=words):
        spec.parse(base(**edit))


def test_a_capture_from_an_earlier_edit_may_be_used_later():
    raw = base()
    raw['edit'].append({'name': 'e2', 'pattern': '@@x@@c', 'replace': ''})
    assert len(spec.parse(raw).edits) == 2
