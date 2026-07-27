import json
import os
import stat

import model_config
from utils import secret_store


def _isolated_settings(monkeypatch, tmp_path):
    secrets = {}
    settings_path = tmp_path / "user_settings.json"
    monkeypatch.setattr(model_config, "_USER_SETTINGS_FILE", str(settings_path))

    def _set(name, value):
        # True mirrors set_secret's contract: stored somewhere durable.
        secrets[name] = value
        return True

    monkeypatch.setattr(model_config, "get_secret", lambda name: secrets.get(name))
    monkeypatch.setattr(model_config, "set_secret", _set)
    monkeypatch.setattr(model_config, "delete_secret", lambda name: secrets.pop(name, None))
    return settings_path, secrets


def test_provider_secrets_never_enter_json_settings(monkeypatch, tmp_path):
    settings_path, secrets = _isolated_settings(monkeypatch, tmp_path)

    model_config.persist_openai_key("openai-test-secret")
    model_config.persist_gemini_key("gemini-test-secret")
    model_config.persist_local_endpoint(
        base_url="http://127.0.0.1:1234/v1",
        api_key="local-test-secret",
        model="local-model",
    )

    saved = json.loads(settings_path.read_text())
    assert saved == {
        "local_base_url": "http://127.0.0.1:1234/v1",
        "local_model": "local-model",
    }
    assert secrets == {
        "openai_api_key": "openai-test-secret",
        "gemini_api_key": "gemini-test-secret",
        "local_api_key": "local-test-secret",
    }
    assert model_config.get_local_endpoint()["api_key"] == "local-test-secret"


def test_legacy_json_secrets_are_migrated_and_removed(monkeypatch, tmp_path):
    settings_path, secrets = _isolated_settings(monkeypatch, tmp_path)
    settings_path.write_text(json.dumps({
        "model_provider": "openai",
        "openai_api_key": "old-openai-secret",
        "gemini_api_key": "old-gemini-secret",
        "local_api_key": "old-local-secret",
    }))

    model_config._migrate_plaintext_secrets(model_config._load_user_settings())

    assert json.loads(settings_path.read_text()) == {"model_provider": "openai"}
    assert secrets == {
        "openai_api_key": "old-openai-secret",
        "gemini_api_key": "old-gemini-secret",
        "local_api_key": "old-local-secret",
    }


def test_settings_file_is_owner_only_on_posix(monkeypatch, tmp_path):
    settings_path, _ = _isolated_settings(monkeypatch, tmp_path)
    model_config.persist_provider("openai")

    if os.name == "posix":
        assert stat.S_IMODE(settings_path.stat().st_mode) == 0o600


def test_os_credential_backend_is_used_when_available(monkeypatch):
    class FakeKeyring:
        values = {}

        @classmethod
        def set_password(cls, service, name, value):
            cls.values[(service, name)] = value

        @classmethod
        def get_password(cls, service, name):
            return cls.values.get((service, name))

        @classmethod
        def delete_password(cls, service, name):
            cls.values.pop((service, name), None)

    monkeypatch.setattr(secret_store, "_keyring", lambda: FakeKeyring)
    secret_store._session_secrets.clear()

    secret_store.set_secret("test-provider", "credential-value")

    assert secret_store.get_secret("test-provider") == "credential-value"
    assert secret_store._session_secrets == {}


def test_web_server_defaults_to_loopback_and_same_origin_cors():
    source = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "web", "web_interface.py"))
    with open(source, encoding="utf-8") as source_file:
        contents = source_file.read()
    assert 'NEQ_WEB_HOST", "127.0.0.1"' in contents
    assert "cors_allowed_origins=None" in contents
    assert "NEQ_OPERATOR_TOKEN" in contents
    assert '"Referrer-Policy", "no-referrer"' in contents
    assert contents.count("@socketio.on('connect')") == 1
