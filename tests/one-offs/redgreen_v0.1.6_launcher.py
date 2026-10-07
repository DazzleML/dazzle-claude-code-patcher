"""Red-green audit of the #5 tests (v0.1.6): revert one behaviour at a time, keep
the API, run tests/test_launcher.py, restore from a copy. Every launch in those
tests is stubbed and every folder is under tmp_path (rule 1b), so a revert that
breaks a guard writes only into tmp. Not reverted: the file id in the stat
stamp, whose absence fails only by clock timing (a flaky anchor)."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
L, C = ROOT / 'dcc_patcher' / 'launch.py', ROOT / 'dcc_patcher' / 'cli.py'
REVERTS = [
    ('sha cache', L, "    if st.get('official_stat') == stamp", "    if False and st.get('official_stat') == stamp"),
    ('DCC_MODE', L, "            mode = env['DCC_MODE']\n", "            pass\n"),
    ('test config', L, "    writable = not env.get('CLAUDE_CONFIG_DIR')", "    writable = True"),
    ('fallback', L, "    return official, _join(note, f'dcc: {which}", "    return str(builds.builds_dir() / (current or '')), _join(note, f'dcc: {which}"),
    ('crash guard', L, "        except Exception:", "        except KeyError:"),
    ('pinned gone', L, "        if pinned.is_file():", "        if True:"),
    ('notes join', L, "        return built, _join(note, f'dcc: Claude", "        return built, _join(f'dcc: Claude"),
    ('no official', L, "    if not os.path.isfile(exe):", "    if False:"),
    ('use check', C, "        if what not in launch.kept_builds():", "        if False:"),
    ('rollback', C, "    st['mode'] = earlier[-1]", "    st['mode'] = kept[-1]"),
    ('shim mode line', C, "            if not setmode:", "            if False:"),
    ('shim refusal', C, "    if folder == official_bin or official_bin in folder.parents:", "    if False:"),
    ('cmd CRLF', C, "'\\r\\n' if not posix else '\\n'", "'\\n'"),
    ('sh slashes', C, "python.replace('\\\\', '/') if posix else python", "python"),
]

saved = Path(tempfile.mkdtemp(prefix='redgreen-'))
for f in (L, C):
    shutil.copy2(f, saved / f.name)
try:
    for name, f, old, new in REVERTS:
        text = f.read_text(encoding='utf-8')
        assert text.count(old) == 1, f'{name}: anchor found {text.count(old)} times'
        f.write_text(text.replace(old, new), encoding='utf-8')
        r = subprocess.run([sys.executable, '-P', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                            'tests/test_launcher.py'], cwd=ROOT, capture_output=True, text=True, timeout=120)
        failed = [l.split('::')[-1].split(' ')[0] for l in r.stdout.splitlines() if l.startswith('FAILED')]
        print(f'{name:15} -> {len(failed)} red: {", ".join(failed) or "(none)"}')
        shutil.copy2(saved / f.name, f)
finally:
    for f in (L, C):
        shutil.copy2(saved / f.name, f)
