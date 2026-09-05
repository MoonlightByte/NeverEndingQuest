"""Actual provider handlers + persistence, isolated from game/OS credentials.

The handler function bodies are compiled from production source; unrelated Flask
startup is not imported. Model configuration runs from a temporary installation.
This verifies handlers/persistence, not Socket.IO routing or real model responses.
"""
import ast
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import types

import pytest

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture
def provider_runtime(tmp_path, monkeypatch):
    # Import-time settings/key migration must never see the developer's profile.
    shutil.copy2(REPO / "model_config.py", tmp_path / "model_config.py")
    shutil.copytree(REPO / "schemas", tmp_path / "schemas")
    secrets = {}
    secret_module = types.ModuleType("utils.secret_store")
    secret_module.get_secret = secrets.get
    secret_module.set_secret = lambda name, value: (secrets.__setitem__(name, value), True)[1]
    secret_module.delete_secret = lambda name: secrets.pop(name, None)
    monkeypatch.setitem(sys.modules, "utils.secret_store", secret_module)
    config = types.ModuleType("config")
    config.OPENAI_API_KEY = ""
    config.GEMINI_API_KEY = ""
    monkeypatch.setitem(sys.modules, "config", config)

    def reload_config():
        spec = importlib.util.spec_from_file_location("model_config", tmp_path / "model_config.py")
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, "model_config", module)
        spec.loader.exec_module(module)
        return module

    module = reload_config()
    source = ast.parse((REPO / "web/web_interface.py").read_text(encoding="utf-8"))
    names = {
        "handle_get_provider", "handle_set_provider", "handle_get_local_endpoint",
        "handle_set_local_endpoint", "handle_get_openai_key", "handle_set_openai_key",
        "handle_get_gemini_key", "handle_set_gemini_key", "handle_test_local_endpoint",
    }
    functions = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in functions} == names
    for node in functions:
        node.decorator_list = []
    events = []
    namespace = {
        "emit": lambda event, payload, **kwargs: events.append((event, payload)),
        "debug": lambda *args, **kwargs: None,
        "error": lambda *args, **kwargs: None,
    }
    exec(compile(ast.Module(body=functions, type_ignores=[]), "web/web_interface.py", "exec"), namespace)
    return types.SimpleNamespace(module=module, reload=reload_config, handlers=namespace,
                                 events=events, root=tmp_path, secrets=secrets)


@pytest.mark.parametrize("provider", ["legacy", "openai", "gemini", "lmstudio"])
def test_provider_round_trip_survives_fresh_module_import(provider_runtime, provider):
    rt = provider_runtime
    rt.handlers["handle_set_provider"]({"provider": provider})
    assert rt.events[-1] == ("provider_changed", {"provider": provider})
    assert rt.module.get_provider() == provider
    assert rt.reload().get_provider() == provider
    rt.handlers["handle_get_provider"]()
    assert rt.events[-1] == ("provider_changed", {"provider": provider})


def test_invalid_provider_does_not_change_persisted_selection(provider_runtime):
    rt = provider_runtime
    rt.handlers["handle_set_provider"]({"provider": "legacy"})
    rt.handlers["handle_set_provider"]({"provider": "not-a-provider"})
    assert rt.events[-1][0] == "error"
    assert rt.reload().get_provider() == "legacy"


def test_endpoint_preserves_blank_key_without_echoing_secret(provider_runtime):
    rt = provider_runtime
    synthetic = "fixture-only-local-key"
    rt.handlers["handle_set_local_endpoint"]({"base_url": "http://127.0.0.1:9999/v1", "model": "test-model", "api_key": synthetic})
    rt.handlers["handle_set_local_endpoint"]({"base_url": "http://127.0.0.1:9998/v1", "model": "next-model", "api_key": ""})
    reloaded = rt.reload()
    assert reloaded.get_local_endpoint() == {"base_url": "http://127.0.0.1:9998/v1", "model": "next-model", "api_key": synthetic}
    rt.handlers["handle_get_local_endpoint"]()
    assert rt.events[-1][1]["has_key"] is True
    assert synthetic not in json.dumps(rt.events)
    assert synthetic not in (rt.root / "user_settings.json").read_text()


@pytest.mark.parametrize("provider", ["openai", "gemini"])
def test_key_set_and_blank_submit_report_status_only(provider_runtime, provider):
    rt = provider_runtime
    synthetic = f"fixture-only-{provider}-key"
    rt.handlers[f"handle_set_{provider}_key"]({"api_key": synthetic})
    rt.handlers[f"handle_set_{provider}_key"]({"api_key": ""})
    rt.reload()
    rt.handlers[f"handle_get_{provider}_key"]()
    assert rt.events[-1] == (f"{provider}_key_status", {"has_key": True})
    assert synthetic not in json.dumps(rt.events)


def test_probe_uses_posted_values_and_reports_model_mismatch(provider_runtime):
    rt = provider_runtime
    calls = []

    def client(**kwargs):
        calls.append(kwargs)
        return types.SimpleNamespace(models=types.SimpleNamespace(list=lambda: types.SimpleNamespace(data=[types.SimpleNamespace(id="available")])) )

    rt.handlers["OpenAI"] = client
    rt.handlers["handle_test_local_endpoint"]({"base_url": "http://127.0.0.1:9999/v1", "model": "absent", "api_key": ""})
    assert calls[0]["api_key"] == "not-needed"
    assert rt.events[-1][0] == "local_endpoint_test_result"
    assert rt.events[-1][1]["ok"] is True
    assert 'not in the model list' in rt.events[-1][1]["detail"]


def test_probe_rejects_empty_url_without_network(provider_runtime):
    rt = provider_runtime
    rt.handlers["handle_test_local_endpoint"]({"base_url": ""})
    assert rt.events[-1] == ("local_endpoint_test_result", {"ok": False, "detail": "Base URL is required."})


def test_production_event_decorators_route_through_flask_socketio(provider_runtime):
    from flask import Flask
    from flask_socketio import SocketIO, emit

    rt = provider_runtime
    app = Flask(__name__)
    app.config["TESTING"] = True
    socketio = SocketIO(app, async_mode="threading")
    source = ast.parse((REPO / "web/web_interface.py").read_text(encoding="utf-8"))
    # Keep the production decorators this time: actual names/payloads must route.
    functions = [node for node in source.body if isinstance(node, ast.FunctionDef) and node.name in rt.handlers]
    namespace = {"socketio": socketio, "emit": emit,
                 "debug": lambda *args, **kwargs: None,
                 "error": lambda *args, **kwargs: None}
    exec(compile(ast.Module(body=functions, type_ignores=[]), "web/web_interface.py", "exec"), namespace)
    client = socketio.test_client(app)
    try:
        for provider in ("legacy", "openai", "gemini", "lmstudio"):
            client.emit("set_model_provider", {"provider": provider})
            packet = client.get_received()[-1]
            assert packet["name"] == "provider_changed"
            assert packet["args"] == [{"provider": provider}]
            rt.reload()
            client.disconnect()
            client.connect()
            client.emit("get_model_provider")
            assert client.get_received()[-1]["args"] == [{"provider": provider}]
    finally:
        if client.is_connected():
            client.disconnect()
