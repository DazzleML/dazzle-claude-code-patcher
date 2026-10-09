"""Red-green for v0.1.10 (#9): revert each BEHAVIOUR (not the API) and check
that the test written for it goes red, then restore and check green again.
Sources are restored in a finally block and re-checked against their originals.

    python -P tests/one-offs/redgreen_v0.1.10.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CASES = [
    ('the rebuilding line is printed before the build',
     'dcc_patcher/launch.py',
     "    print(f'dcc: {why}; building the patched copy... ', end='', file=sys.stderr, flush=True)\n",
     "",
     'tests/test_launcher.py::test_a_rebuild_says_so_before_it_starts_and_finishes_the_same_line'),
    ('the launcher sweeps the updater\'s .old copies',
     'dcc_patcher/launch.py',
     "    _keep_originals(official)\n",
     "",
     'tests/test_launcher.py::test_a_rebuild_also_keeps_the_original_and_the_updaters_old_copies'),
    ('a file already looked at is not read again',
     'dcc_patcher/originals.py',
     "            seen[str(path)] = stamp\n            continue\n",
     "            seen[str(path)] = stamp\n",
     'tests/test_originals.py::test_archive_keeps_each_version_once_and_leaves_the_official_folder_alone'),
    ('a second build of one version gets its own name',
     'dcc_patcher/originals.py',
     "    for target in (folder / f'{base}{suffix}', folder / f'{base}-{sha[:12]}{suffix}'):",
     "    for target in (folder / f'{base}{suffix}',):",
     'tests/test_originals.py::test_two_builds_of_one_version_are_both_kept_and_a_duplicate_is_not'),
    ('an .old copy builds with an .exe name',
     'dcc_patcher/cli.py',
     "builds.build_name(tag, builds.exe_suffix(file))",
     "builds.build_name(tag, Path(file).suffix)",
     'tests/test_originals.py::test_building_from_an_old_copy_names_the_build_exe'),
    ('insert keeps every other byte (here: an empty segment)',
     'dcc_patcher/winpath.py',
     "    return ';'.join(parts[:i] + [entry] + parts[i:])",
     "    return ';'.join(p for p in parts[:i] + [entry] + parts[i:] if p)",
     'tests/test_path.py::test_install_adds_only_our_entry_before_the_official_folder_and_keeps_the_type'),
    ('uninstall removes our entry rather than restoring the saved PATH',
     'dcc_patcher/install.py',
     "    changed, before, after, kind = winpath.drop(winpath.USER, entry)\n",
     "    before, kind = winpath.read(winpath.USER); after = rec['base_path_user']['value']; changed = True\n"
     "    winpath.registry().write(winpath.USER, after, kind)\n",
     'tests/test_path.py::test_uninstall_removes_only_our_entry_and_keeps_what_others_added_since'),
    ('a PATH changed underneath is refused before writing',
     'dcc_patcher/winpath.py',
     "    if (reg.read(scope)[0] or '') != before:",
     "    if False:",
     'tests/test_path.py::test_a_path_changed_underneath_is_refused_and_not_overwritten'),
    ('a script without --yes changes nothing (the early return)',
     'dcc_patcher/install.py',
     "    if not yes and os.environ.get('DCC_YES') != '1' and (not sys.stdin or not sys.stdin.isatty()):",
     "    if False:",
     'tests/test_path.py::test_without_yes_in_a_script_path_is_left_alone'),
    ('the system PATH is written only when elevated',
     'dcc_patcher/install.py',
     "        if not winpath.is_elevated():",
     "        if False:",
     'tests/test_path.py::test_a_system_claude_is_overtaken_only_when_elevated_and_via_the_admin_folder'),
    ('status names a shell that predates the install',
     'dcc_patcher/install.py',
     "        elif os.path.normcase(str(w)) == os.path.normcase(official) and registry_ready:",
     "        elif False:",
     'tests/test_path.py::test_status_names_the_stock_claude_then_the_stale_shell_then_all_clear'),
    ('resolution is folder order first, extension order second',
     'dcc_patcher/resolve.py',
     "    for folder in where:\n        for ext in exts:\n            p = Path(folder) / f'{name}{ext}'",
     "    for ext in exts:\n        for folder in where:\n            p = Path(folder) / f'{name}{ext}'",
     'tests/test_path.py::test_resolution_follows_path_order_then_pathext_order'),
]


def run(test):
    # A fresh bytecode cache per run: a same-size mutation restored within the same
    # second otherwise leaves a .pyc that still looks current (found on the resolve case).
    with tempfile.TemporaryDirectory() as cache:
        r = subprocess.run([sys.executable, '-P', '-m', 'pytest', '-q', '-x', '-p', 'no:cacheprovider', test],
                           cwd=ROOT, capture_output=True, text=True, timeout=300,
                           env={**os.environ, 'PYTHONPYCACHEPREFIX': cache})
    return r.returncode == 0


def main():
    rows = []
    for what, rel, old, new, test in CASES:
        path = ROOT / rel
        original = path.read_text(encoding='utf-8')
        assert original.count(old) == 1, f'anchor not unique in {rel}: {what}'
        try:
            path.write_text(original.replace(old, new), encoding='utf-8')
            red = not run(test)
        finally:
            path.write_text(original, encoding='utf-8')
        assert path.read_text(encoding='utf-8') == original
        green = run(test)
        rows.append((what, red, green))
        print(f"{'ANCHOR' if red and green else 'GUARD/BROKEN'}  red={red} green={green}  {what}")
    sys.exit(0 if all(r and g for _, r, g in rows) else 1)


if __name__ == '__main__':
    main()
