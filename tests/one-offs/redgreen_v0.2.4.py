"""Red-green for v0.2.4: break each guard in turn, run the test written for it, restore.
dcc-env's help/option/-V guards (the tests reach only a stub dcc-patcher, tests/test_switch.py's
`stub`), the grouped help, the offline update check, and every guard in front of pip in
`update --fix` (the tests' pip is a stub that installs nothing, and subprocess.run raises).
Line ends are kept byte for byte (the .cmd/.ps1 are CRLF, the sh script LF).

    python tests/one-offs/redgreen_v0.2.4.py
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
T = 'tests/test_switch.py::'
HELP = T + 'test_dcc_env_help_says_the_choices_and_changes_nothing'
OPT = T + 'test_dcc_env_refuses_an_unknown_option_rather_than_setting_it_as_the_mode'
U = 'tests/test_verbs_update.py::'

MUTANTS = [
    ('cmd help guard', 'bin/dcc-env.cmd', b'if /i "%~1"=="--help" goto help', b'if /i "%~1"=="--hlp" goto help',
     HELP + '[--help-cmd]'),
    ('cmd option guard', 'bin/dcc-env.cmd', b'goto badopt', b'rem badopt', OPT + '[cmd]'),
    ('ps1 help guard', 'bin/dcc-env.ps1', b"'-h', '--help'", b"'-h', '--hlp'", HELP + '[--help-powershell]'),
    ('ps1 option guard', 'bin/dcc-env.ps1', b"if ($Mode.StartsWith('-'))", b"if ($false)", OPT + '[powershell]'),
    ('sh help guard', 'bin/dcc-env', b'-h|--help)', b'-h|--hlp)', HELP + '[--help-sh]'),
    ('sh option guard', 'bin/dcc-env', b'\n-*)\n', b'\n-xyz*)\n', OPT + '[sh]'),
    # dcc-env -V: the mismatch line, per shell
    ('cmd -V mismatch', 'bin/dcc-env.cmd', b'if not "%DCC_P%"=="%DCC_ENV_V%" echo', b'if "%DCC_P%"=="%DCC_ENV_V%" echo',
     T + 'test_dcc_env_version_names_itself_and_dcc_patcher_and_flags_a_mismatch[-V-cmd]'),
    ('ps1 -V mismatch', 'bin/dcc-env.ps1', b'if ($p -ne $DCC_ENV_V)', b'if ($p -eq $DCC_ENV_V)',
     T + 'test_dcc_env_version_names_itself_and_dcc_patcher_and_flags_a_mismatch[-V-powershell]'),
    ('sh -V mismatch', 'bin/dcc-env', b'[ "$p" = "$DCC_ENV_V" ] ||', b'[ "$p" != "$DCC_ENV_V" ] ||',
     T + 'test_dcc_env_version_names_itself_and_dcc_patcher_and_flags_a_mismatch[-V-sh]'),
    ('script stamp', 'bin/dcc-env.ps1', b"$DCC_ENV_V = '", b"$DCC_ENV_V = '9",
     U + 'test_each_dcc_env_script_carries_this_version'),
    # the grouped help
    ('help catch-all', 'dcc_patcher/verbs.py', b'    if rest:\n', b'    if False:\n',
     U + 'test_a_command_missing_from_the_groups_still_shows_under_other'),
    ('help fallback', 'dcc_patcher/verbs.py', b'        except Exception:', b'        except ZeroDivisionError:',
     U + 'test_without_dazzle_lib_the_help_falls_back_and_the_tool_still_works'),
    ('dazzle-lib loaded eagerly', 'dcc_patcher/verbs.py', b'ARROW = ',
     b'from dazzle_lib.groupable import Groupable as _G  # noqa\nARROW = ',
     U + 'test_the_launcher_and_cli_never_load_dazzle_lib'),
    # update --fix: every guard in front of pip (the tests' pip is a stub that installs nothing)
    ('fix: no --fix', 'dcc_patcher/selfupdate.py', b'    if not fix:\n', b'    if False:\n',
     U + 'test_update_without_fix_reports_and_runs_nothing'),
    ('fix: the answer', 'dcc_patcher/selfupdate.py', b"if answer not in ('y', 'yes'):", b'if False:',
     U + 'test_fix_runs_nothing_unless_the_answer_is_yes'),
    ('fix: dry run', 'dcc_patcher/selfupdate.py', b'    if dry_run:\n', b'    if False:\n',
     U + 'test_fix_dry_run_shows_the_command_and_runs_nothing'),
    ('fix: no terminal', 'dcc_patcher/selfupdate.py', b"if not (sys.stdin.isatty() if tty is None else tty):",
     b'if False:', U + 'test_fix_without_a_terminal_needs_yes'),
    ('fix: verify-after', 'dcc_patcher/selfupdate.py', b"if after is not None and not after.get('pending'):",
     b'if True:', U + 'test_a_fix_that_did_not_take_says_so_and_gives_the_command'),
    ('fix: the windows note', 'dcc_patcher/selfupdate.py', b'        if code:\n', b'        if False:\n',
     U + 'test_a_pip_error_after_a_completed_install_reads_as_done_with_the_windows_note'),
    # the offline check
    ('check: copies vs checkout', 'dcc_patcher/selfupdate.py',
     b'current = copy.is_file() and copy.read_bytes() == source.read_bytes()', b'current = True',
     U + 'test_an_editable_install_compares_the_copies_with_the_checkout_and_reinstalls_from_it'),
    ('check: pip record', 'dcc_patcher/selfupdate.py',
     b"if checkout and vtuple(st['installed']) != vtuple(BASE_VERSION):", b'if False:',
     U + 'test_an_editable_install_whose_pip_record_is_behind_the_checkout_is_named'),
    ('status brief row', 'dcc_patcher/install.py', b"            if up and up['pending']:", b'            if False:',
     U + 'test_status_and_dcc_envs_line_name_stale_scripts_and_say_nothing_when_current'),
    # after the live breakage: never pip from the running exe; say so when pip left it uninstalled
    ('fix: not from the exe', 'dcc_patcher/selfupdate.py', b'    if (from_launcher_exe() if exe is None else exe):',
     b'    if False:', U + 'test_fix_never_runs_pip_from_dcc_patcher_exe_and_names_the_python_route'),
    ('exe detection', 'dcc_patcher/selfupdate.py', b"Path(sys.argv[0]).stem.lower() == 'dcc-patcher'",
     b"Path(sys.argv[0]).stem.lower() == 'dcc_patcher'", U + 'test_from_launcher_exe_reads_how_this_process_started'),
    ('fix: uninstalled', 'dcc_patcher/selfupdate.py', b'    if gone:\n', b'    if False:\n',
     U + 'test_a_fix_that_left_dcc_patcher_uninstalled_says_so_loudly'),
    ('-h <command>', 'dcc_patcher/cli.py', b"argv[0] in ('-h', '--help')", b"argv[0] in ('-x',)",
     U + 'test_help_before_a_command_shows_that_commands_help'),
]


def pytest(test):
    env = dict(os.environ, PYTHONPYCACHEPREFIX=tempfile.mkdtemp(prefix='dcc-pyc-'))
    p = subprocess.run([sys.executable, '-P', '-m', 'pytest', '-q', '-p', 'no:cacheprovider', test],
                       cwd=ROOT, env=env, capture_output=True, text=True)
    return p.returncode == 0


def main():
    bad = 0
    for label, rel, old, new, test in MUTANTS:
        path = ROOT / rel
        original = path.read_bytes()
        assert original.count(old) == 1, f'{label}: anchor not found once'
        green_before = pytest(test)
        try:
            path.write_bytes(original.replace(old, new))
            red = not pytest(test)
        finally:
            path.write_bytes(original)
        restored = path.read_bytes() == original
        ok = green_before and red and restored
        bad += not ok
        print(f'{label:18} green={green_before} red_when_broken={red} restored={restored} -> {"OK" if ok else "FAIL"}')
    return bad


if __name__ == '__main__':
    sys.exit(main())
