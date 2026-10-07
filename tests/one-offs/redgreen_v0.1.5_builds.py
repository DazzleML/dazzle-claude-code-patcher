"""Red-green audit of the #3 tests (v0.1.5): revert one behaviour at a time, keep
the API, run the new tests, restore from a copy. Never reverts DCC_BUILDS_DIR
(that would aim writes at the real private/builds; rule 1b)."""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
B, C = ROOT / 'dcc_patcher' / 'builds.py', ROOT / 'dcc_patcher' / 'cli.py'
REVERTS = [
    ('refusal', B, '    target = Path(path).resolve()\n', '    return None\n    target = Path(path).resolve()\n'),
    ('already built', C, '    return recorded == lock._sha(image)', '    return False and recorded == lock._sha(image)'),
    ('in-use message', C, '    except PermissionError:\n        print(f\'dcc-patcher: the current', '    except ZeroDivisionError:\n        print(f\'dcc-patcher: the current'),
    ('copy fallback', B, '    except OSError:\n        shutil.copyfile', '    except ZeroDivisionError:\n        shutil.copyfile'),
    ('hardlink', B, '        os.link(build, tmp)\n', '        raise OSError("no link")\n'),
    ('versioned name', B, "    return f'{CURRENT}-{claude_version}+dcc{BASE_VERSION}{suffix}'", "    return f'{CURRENT}{suffix}'"),
    ('absolute path', C, '    output = os.path.abspath(output)\n', '    output = output\n'),
    ('no link with -o', C, '    if args.output:\n        return 0\n    try:', '    if False:\n        return 0\n    try:'),
]
SEL = 'apply_without_o or rebuilding or refuses_to_write or running_current or without_hardlinks or with_o_there'

saved = Path(tempfile.mkdtemp(prefix='redgreen-'))
for f in (B, C):
    shutil.copy2(f, saved / f.name)
try:
    for name, f, old, new in REVERTS:
        text = f.read_text(encoding='utf-8')
        assert text.count(old) == 1, f'{name}: anchor not unique'
        f.write_text(text.replace(old, new), encoding='utf-8')
        r = subprocess.run([sys.executable, '-P', '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                            'tests/test_cli.py', '-k', SEL], cwd=ROOT, capture_output=True, text=True, timeout=120)
        failed = [l.split('::')[-1].split(' ')[0] for l in r.stdout.splitlines() if l.startswith('FAILED')]
        print(f'{name:16} -> {len(failed)} red: {", ".join(failed) or "(none)"}')
        shutil.copy2(saved / f.name, f)
finally:
    for f in (B, C):
        shutil.copy2(saved / f.name, f)
