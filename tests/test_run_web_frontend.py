from pathlib import Path
from unittest.mock import Mock
import os

import run_web


def _frontend_tree(root: Path) -> Path:
    frontend = root / "web" / "frontend"
    (frontend / "src").mkdir(parents=True)
    (frontend / "package.json").write_text("{}", encoding="utf-8")
    (frontend / "package-lock.json").write_text("{}", encoding="utf-8")
    (frontend / "src" / "App.tsx").write_text("export {}", encoding="utf-8")
    return frontend


def test_missing_build_runs_clean_install_and_build(tmp_path):
    frontend = _frontend_tree(tmp_path)
    runner = Mock(return_value=Mock(returncode=0))

    available = run_web.ensure_react_frontend(
        tmp_path,
        npm_command="npm",
        runner=runner,
    )

    assert available is True
    assert [call.args[0] for call in runner.call_args_list] == [
        ["npm", "ci"],
        ["npm", "run", "build"],
    ]
    assert all(call.kwargs["cwd"] == frontend for call in runner.call_args_list)


def test_current_build_skips_npm(tmp_path):
    frontend = _frontend_tree(tmp_path)
    dist = frontend / "dist"
    dist.mkdir()
    index = dist / "index.html"
    index.write_text("built", encoding="utf-8")
    newest = max(path.stat().st_mtime for path in frontend.rglob("*") if path.is_file())
    os.utime(index, (newest + 2, newest + 2))
    runner = Mock()

    assert run_web.ensure_react_frontend(tmp_path, runner=runner) is True
    runner.assert_not_called()


def test_source_newer_than_build_triggers_rebuild(tmp_path):
    frontend = _frontend_tree(tmp_path)
    dist = frontend / "dist"
    dist.mkdir()
    index = dist / "index.html"
    index.write_text("old build", encoding="utf-8")
    old_time = index.stat().st_mtime - 2
    os.utime(index, (old_time, old_time))
    runner = Mock(return_value=Mock(returncode=0))

    assert run_web.ensure_react_frontend(
        tmp_path,
        npm_command="npm",
        runner=runner,
    ) is True
    assert runner.call_count == 2


def test_missing_npm_falls_back_without_running_commands(tmp_path):
    _frontend_tree(tmp_path)
    runner = Mock()

    assert run_web.ensure_react_frontend(
        tmp_path,
        npm_command=None,
        runner=runner,
    ) is False
    runner.assert_not_called()


def test_failed_build_falls_back_to_legacy(tmp_path):
    _frontend_tree(tmp_path)
    runner = Mock(side_effect=[Mock(returncode=0), Mock(returncode=1)])

    assert run_web.ensure_react_frontend(
        tmp_path,
        npm_command="npm",
        runner=runner,
    ) is False


def test_ui_choice_defaults_to_react_and_respects_legacy():
    assert run_web.select_ui("react", react_available=True) == "react"
    assert run_web.select_ui("react", react_available=False) == "legacy"
    assert run_web.select_ui("legacy", react_available=True) == "legacy"
    assert run_web.select_ui("choose", react_available=True, input_fn=lambda _: "") == "react"
    assert run_web.select_ui("choose", react_available=True, input_fn=lambda _: "2") == "legacy"


def test_command_line_defaults_to_react_and_supports_choice():
    assert run_web.parse_args([]).ui == "react"
    assert run_web.parse_args(["--ui", "choose"]).ui == "choose"
