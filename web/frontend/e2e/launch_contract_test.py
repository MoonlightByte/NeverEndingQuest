"""Run Windows launch branches in a disposable folder, with no installs/browser."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

REPO = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows entry points")


@pytest.mark.parametrize("script", ["launch_game.bat", "install_neverendingquest_windows.bat"])
@pytest.mark.parametrize("selection, expected", [("O", "ONLINE_SELECTED"), ("X", None)])
def test_online_or_exit_never_reaches_local_setup(tmp_path, script, selection, expected):
    text = (REPO / script).read_text()
    # Replace only the external browser launch with an observable sentinel.
    # Everything after the local label is a tripwire: not even Python is needed.
    text = text.replace('start "" "https://eternaltavern.com/neverendingquest/"', 'echo ONLINE_SELECTED')
    label = ':LOCAL_SETUP\n' if script.startswith('install') else ':LOCAL\n'
    text = text.split(label)[0] + label + 'echo LOCAL_TRIPWIRE\nexit /b 99\n'
    target = tmp_path / script
    target.write_text(text)
    env = dict(os.environ)
    env.pop('NEQ_LOCAL_ONLY', None)
    result = subprocess.run(['cmd', '/d', '/c', str(target)], input=selection, text=True,
                            capture_output=True, env=env, timeout=10)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'LOCAL_TRIPWIRE' not in result.stdout
    assert ('ONLINE_SELECTED' in result.stdout) == bool(expected)


def test_explicit_local_arguments_are_forwarded_and_exit_status_preserved(tmp_path):
    # Use a genuine Python venv executable; the only program it runs is a stub.
    subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(tmp_path / 'venv')], check=True)
    (tmp_path / 'launch_game.bat').write_text((REPO / 'launch_game.bat').read_text())
    (tmp_path / 'run_web.py').write_text('import sys\nprint(repr(sys.argv[1:]))\nraise SystemExit(7)\n')
    result = subprocess.run(['cmd', '/d', '/c', str(tmp_path / 'launch_game.bat'), '--ui', 'legacy'],
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 7
    assert "['--ui', 'legacy']" in result.stdout
    assert 'choose how to play' not in result.stdout


def test_installer_uses_checkout_launcher_and_local_checkout_label():
    text = (REPO / 'install_neverendingquest_windows.bat').read_text()
    assert ':REPOSITORY_READY\n' in text
    assert 'echo @echo off > launch_game.bat' not in text
    assert text.index('choice /C OLX') < text.index('python --version')
