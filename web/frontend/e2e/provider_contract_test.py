"""Actual provider handlers + persistence, isolated from game/OS credentials.

The handler function bodies are compiled from production source; unrelated Flask
startup is not imported. Model configuration runs from a temporary installation.
This verifies handlers/persistence, not Socket.IO routing or real model responses.
"""
import ast
import importlib.util
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
import sys
import threading
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
        "threading": threading,
    }
    locks = [node for node in source.body if isinstance(node, ast.Assign)
             and any(isinstance(target, ast.Name) and target.id == "_provider_selection_lock" for target in node.targets)]
    exec(compile(ast.Module(body=locks + functions, type_ignores=[]), "web/web_interface.py", "exec"), namespace)
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
    assert rt.module.get_provider() == "legacy"
    assert rt.reload().get_provider() == "legacy"


@pytest.mark.parametrize("payload", [None, [], {"provider": None}, {"provider": []}])
def test_malformed_provider_does_not_change_live_or_persisted_selection(provider_runtime, payload):
    rt = provider_runtime
    rt.handlers["handle_set_provider"]({"provider": "legacy"})
    rt.events.clear()
    rt.handlers["handle_set_provider"](payload)
    assert [event for event, _ in rt.events] == ["error"]
    assert rt.module.get_provider() == "legacy"
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


@pytest.fixture
def local_provider_stub(provider_runtime):
    """Real SDK against a loopback-only HTTP server; no models or paid calls.

    Retry delays are disabled in this test transport, not in production. Request
    headers are never logged. Only synthetic credentials may reach this server.
    """
    import httpx
    from openai import OpenAI

    state = types.SimpleNamespace(mode="models", requests=[])

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            state.requests.append(("GET", self.path))
            if state.mode == "auth":
                self.respond(401, {"error": {"message": "Synthetic authentication rejected", "type": "authentication_error"}})
            elif state.mode == "chat":
                self.respond(404, {"error": {"message": "Model listing unavailable"}})
            else:
                names = [] if state.mode == "empty" else [{"id": "fixture-model", "object": "model"}]
                self.respond(200, {"object": "list", "data": names})

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            state.requests.append(("POST", self.path, body))
            if state.mode == "auth":
                self.respond(401, {"error": {"message": "Synthetic authentication rejected", "type": "authentication_error"}})
            else:
                self.respond(200, {"id": "fixture-chat", "object": "chat.completion", "created": 0,
                                   "model": body["model"], "choices": [{"index": 0, "finish_reason": "stop",
                                   "message": {"role": "assistant", "content": "OK"}}]})

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    state.url = f"http://127.0.0.1:{server.server_port}/v1"
    clients = []

    def client(**kwargs):
        assert kwargs["base_url"] == state.url
        assert kwargs["timeout"] == 10.0
        sdk = OpenAI(**kwargs, max_retries=0, http_client=httpx.Client(trust_env=False))
        clients.append(sdk)
        return sdk

    provider_runtime.handlers["OpenAI"] = client
    try:
        yield state
    finally:
        for sdk in clients:
            sdk.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@pytest.mark.parametrize("mode, model, detail", [
    ("models", "fixture-model", "1 model(s) available"),
    ("models", "missing-model", '"missing-model" not in the model list'),
    ("empty", "", "no models listed"),
    ("chat", "fixture-model", "Chat completion succeeded"),
])
def test_real_sdk_probe_success_and_fallback(provider_runtime, local_provider_stub, mode, model, detail):
    rt, stub = provider_runtime, local_provider_stub
    stub.mode = mode
    before = rt.module.get_local_endpoint()
    rt.handlers["handle_test_local_endpoint"]({"base_url": stub.url, "model": model, "api_key": "fixture-only-key"})
    assert rt.events[-1][0] == "local_endpoint_test_result"
    assert rt.events[-1][1]["ok"] is True
    assert detail in rt.events[-1][1]["detail"]
    assert stub.requests[0] == ("GET", "/v1/models")
    assert len(stub.requests) == (2 if mode == "chat" else 1)
    if mode == "chat":
        assert stub.requests[1][0:2] == ("POST", "/v1/chat/completions")
        assert stub.requests[1][2]["model"] == model
    assert rt.module.get_local_endpoint() == before  # Probe does not save posted values.
    assert "fixture-only-key" not in json.dumps(rt.events)


@pytest.mark.parametrize("model", ["", "fixture-model"])
def test_real_sdk_authentication_failure_is_not_success(provider_runtime, local_provider_stub, model):
    rt, stub = provider_runtime, local_provider_stub
    stub.mode = "auth"
    rt.handlers["handle_test_local_endpoint"]({"base_url": stub.url, "model": model, "api_key": "fixture-only-key"})
    assert rt.events[-1][1]["ok"] is False
    assert "401" in rt.events[-1][1]["detail"]
    assert len(stub.requests) == (2 if model else 1)
    assert "fixture-only-key" not in json.dumps(rt.events)


@pytest.mark.parametrize("failure", ["connect", "timeout"])
def test_real_sdk_transport_failure_can_be_retried(provider_runtime, failure):
    import httpx
    from openai import OpenAI

    rt = provider_runtime
    failing = True

    def transport(request):
        if failing:
            error_type = httpx.ConnectError if failure == "connect" else httpx.ReadTimeout
            raise error_type("Synthetic transport failure", request=request)
        return httpx.Response(200, json={"object": "list", "data": [{"id": "fixture-model"}]})

    with httpx.Client(transport=httpx.MockTransport(transport), trust_env=False) as http:
        rt.handlers["OpenAI"] = lambda **kwargs: OpenAI(**kwargs, max_retries=0, http_client=http)
        payload = {"base_url": "http://fixture.invalid/v1", "model": "fixture-model", "api_key": "fixture-only-key"}
        rt.handlers["handle_test_local_endpoint"](payload)
        assert rt.events[-1][1]["ok"] is False
        assert "fixture-only-key" not in json.dumps(rt.events)
        failing = False
        rt.handlers["handle_test_local_endpoint"](payload)
        assert rt.events[-1][1]["ok"] is True


def test_failed_provider_write_keeps_live_and_persisted_selection(provider_runtime, monkeypatch):
    rt = provider_runtime
    rt.handlers["handle_set_provider"]({"provider": "legacy"})
    persist = rt.module.persist_provider
    monkeypatch.setattr(rt.module, "persist_provider", lambda provider: (_ for _ in ()).throw(OSError("Synthetic read-only settings")))
    rt.events.clear()
    rt.handlers["handle_set_provider"]({"provider": "gemini"})
    assert [event for event, _ in rt.events] == ["error"]
    assert rt.module.get_provider() == "legacy"
    assert json.loads((rt.root / "user_settings.json").read_text())["model_provider"] == "legacy"
    monkeypatch.setattr(rt.module, "persist_provider", persist)
    rt.handlers["handle_set_provider"]({"provider": "openai"})
    assert rt.events[-1] == ("provider_changed", {"provider": "openai"})
    assert rt.reload().get_provider() == "openai"


def test_overlapping_provider_selections_preserve_write_apply_broadcast_order(provider_runtime, monkeypatch):
    rt = provider_runtime
    rt.handlers["handle_set_provider"]({"provider": "legacy"})
    rt.events.clear()
    first_persisted = threading.Event()
    release_first = threading.Event()
    second_attempted_lock = threading.Event()
    second_persisted = threading.Event()
    persist = rt.module.persist_provider
    real_lock = rt.handlers["_provider_selection_lock"]

    class ObservedLock:
        def __enter__(self):
            if threading.current_thread().name == "provider-second":
                second_attempted_lock.set()
            real_lock.acquire()

        def __exit__(self, *args):
            real_lock.release()

    def paused_persist(provider):
        persist(provider)
        if provider == "openai":
            first_persisted.set()
            if not release_first.wait(timeout=5):
                raise TimeoutError("Test failed to release first selection")
        elif provider == "gemini":
            second_persisted.set()

    monkeypatch.setitem(rt.handlers, "_provider_selection_lock", ObservedLock())
    monkeypatch.setattr(rt.module, "persist_provider", paused_persist)
    first = threading.Thread(target=rt.handlers["handle_set_provider"], args=({"provider": "openai"},), daemon=True)
    second = threading.Thread(target=rt.handlers["handle_set_provider"], args=({"provider": "gemini"},), name="provider-second", daemon=True)
    first.start()
    try:
        assert first_persisted.wait(timeout=3)
        second.start()
        assert second_attempted_lock.wait(timeout=3)
        assert not second_persisted.is_set()
        assert rt.events == []
    finally:
        release_first.set()
        first.join(timeout=5)
        if second.ident is not None:
            second.join(timeout=5)
    assert not first.is_alive() and not second.is_alive()
    assert rt.events == [("provider_changed", {"provider": "openai"}), ("provider_changed", {"provider": "gemini"})]
    assert rt.module.get_provider() == "gemini"
    assert rt.reload().get_provider() == "gemini"


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
                 "_provider_selection_lock": rt.handlers["_provider_selection_lock"],
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
