from pathlib import Path
from unittest.mock import Mock
import inspect
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


def test_command_line_defaults_to_legacy_and_supports_explicit_react_or_choice():
    assert run_web.parse_args([]).ui == "legacy"
    assert run_web.parse_args(["--ui", "react"]).ui == "react"
    assert run_web.parse_args(["--ui", "choose"]).ui == "choose"


def test_programmatic_launcher_defaults_to_legacy():
    assert inspect.signature(run_web.main).parameters["ui"].default == "legacy"


def test_direct_server_browser_defaults_and_invalid_values_to_legacy():
    source = (Path(run_web.__file__).parent / "web" / "web_interface.py").read_text(
        encoding="utf-8"
    )

    assert source.count("os.environ.get('NEQ_START_PATH', '/')") == 2
    assert "start_path = '/play/'" not in source
    assert "requested_path = safe_join(dist_dir, filename)" in source
    assert "os.path.isfile(os.path.join(dist_dir, filename))" not in source


def test_unreadable_config_is_one_plain_message(tmp_path, monkeypatch, capsys):
    import sys
    monkeypatch.chdir(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.delitem(sys.modules, "config", raising=False)
    (tmp_path / "config.py").write_text('OPENAI_API_KEY = "x\n', encoding="utf-8")

    assert run_web.load_config() is None
    out = capsys.readouterr().out
    assert out.startswith("[SYSTEM] config.py could not be read at line 1 (SyntaxError).")
    assert "Traceback" not in out
    sys.modules.pop("config", None)


def test_credential_check_counts_config_settings_and_local(monkeypatch):
    import model_config
    from types import SimpleNamespace

    placeholder = SimpleNamespace(OPENAI_API_KEY="your_openai_api_key_here",
                                  GEMINI_API_KEY="your_gemini_api_key_here")
    stored = {"openai": False, "gemini": False}
    settings = {}
    monkeypatch.setattr(model_config, "has_openai_key", lambda: stored["openai"])
    monkeypatch.setattr(model_config, "has_gemini_key", lambda: stored["gemini"])
    monkeypatch.setattr(model_config, "_load_user_settings", lambda: settings)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-is-not-read-by-the-web-game")

    assert run_web.provider_credential_found(placeholder) is False
    assert run_web.provider_credential_found(SimpleNamespace(OPENAI_API_KEY=" ")) is False
    assert run_web.provider_credential_found(SimpleNamespace(OPENAI_API_KEY="sk-a")) is True
    assert run_web.provider_credential_found(SimpleNamespace(GEMINI_API_KEY="g-a")) is True
    stored["openai"] = True
    assert run_web.provider_credential_found(placeholder) is True
    stored.update(openai=False, gemini=True)
    assert run_web.provider_credential_found(placeholder) is True
    stored["gemini"] = False
    settings["model_provider"] = "lmstudio"
    assert run_web.provider_credential_found(placeholder) is True
