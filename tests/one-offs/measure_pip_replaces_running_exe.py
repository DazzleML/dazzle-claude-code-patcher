"""Measure: on Windows, can a console-script .exe (as pip writes for dcc-patcher) run
`python -m pip install` that replaces ITSELF, and does the next start run the new code?
This is the question `dcc-patcher update --fix` rests on.

Everything happens in a throwaway venv under a temp folder, from two locally built wheels
(--no-index: no network, nothing outside the temp folder is installed or changed).

Result 2026-10-09: pip moved the running exe aside, installed v2, then exited 1 failing to
delete the moved copy (WinError 5). ONE SAMPLE, and not what the real install did: the
same evening, `dcc-patcher update --fix` on an editable install failed to move
dcc-patcher.exe at all (WinError 32), stopped halfway and left dcc_patcher uninstalled.
So --fix never runs pip from dcc-patcher.exe (selfupdate.from_launcher_exe).

    python tests/one-offs/measure_pip_replaces_running_exe.py
"""
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

PROBE = '''
import subprocess, sys
VERSION = "{v}"
def main():
    print("running", VERSION)
    if len(sys.argv) > 1:
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--no-index", "--no-deps",
                            "--force-reinstall", "-q", sys.argv[1]], capture_output=True, text=True)
        print("pip exit", r.returncode)
        print(r.stdout.strip()[-400:])
        print(r.stderr.strip()[-600:])
    return 0
'''


def make_wheel(root, version, out):
    src = root / f'src-{version}'
    (src / 'dccprobe').mkdir(parents=True)
    (src / 'dccprobe' / '__init__.py').write_text(PROBE.format(v=version))
    (src / 'pyproject.toml').write_text(textwrap.dedent(f'''
        [build-system]
        requires = ["setuptools>=61"]
        build-backend = "setuptools.build_meta"
        [project]
        name = "dccprobe"
        version = "{version}"
        [project.scripts]
        dccprobe = "dccprobe:main"
        [tool.setuptools]
        packages = ["dccprobe"]
    '''))
    subprocess.run([sys.executable, '-m', 'pip', 'wheel', '--no-deps', '--no-build-isolation', '-q',
                    '-w', str(out), str(src)], check=True)
    return next(out.glob(f'dccprobe-{version}-*.whl'))


def main():
    root = Path(tempfile.mkdtemp(prefix='dcc-pip-exe-'))
    wheels = root / 'wheels'
    w1, w2 = make_wheel(root, '1.0', wheels), make_wheel(root, '2.0', wheels)
    venv = root / 'venv'
    subprocess.run([sys.executable, '-m', 'venv', str(venv)], check=True)
    py = venv / 'Scripts' / 'python.exe'
    subprocess.run([str(py), '-m', 'pip', 'install', '--no-index', '-q', str(w1)], check=True)
    exe = venv / 'Scripts' / 'dccprobe.exe'
    print('=== v1 exe runs pip to install v2 over itself')
    r = subprocess.run([str(exe), str(w2)], capture_output=True, text=True)
    print(f'exit {r.returncode}\n{r.stdout}{r.stderr}')
    print('=== next start')
    r = subprocess.run([str(exe)], capture_output=True, text=True)
    print(r.stdout.strip(), r.stderr.strip())
    leftovers = [p.name for p in (venv / 'Scripts').iterdir() if 'dccprobe' in p.name.lower() or p.name.startswith('~')]
    print('Scripts entries:', leftovers)
    print('scratch:', root)


if __name__ == '__main__':
    main()
