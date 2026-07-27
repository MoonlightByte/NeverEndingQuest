import json
import os
import stat

import model_config
from utils import secret_store


def _isolated_settings(monkeypatch, tmp_path):
    secrets = {}
    settings_path = tmp_path / "user_settings.json"

    def _set(name, value):
        # True mirrors set_secret's real contract: the value is now stored
        # somewhere that outlives this process.
        secrets[name] = value
        return True

    monkeypatch.setattr(model_config, "_USER_SETTINGS_FILE", str(settings_path))
    monkeypatch.setattr(model_config, "get_secret", lambda name: secrets.get(name))
    monkeypatch.setattr(model_config, "set_secret", _set)
    monkeypatch.setattr(model_config, "delete_secret", lambda name: secrets.pop(name, None))
    return settings_path, secrets


def _real_store(monkeypatch, tmp_path, keyring_backend=None):
    """Use the REAL secret_store against a temp settings file.

    keyring_backend=None reproduces the environment most end users are in:
    the 'keyring' package is absent, or present with no usable backend.
    """
    settings_path = tmp_path / "user_settings.json"
    monkeypatch.setattr(model_config, "_USER_SETTINGS_FILE", str(settings_path))
    monkeypatch.setattr(secret_store, "_keyring", lambda: keyring_backend)
    secret_store._session_secrets.clear()
    return settings_path


def _restart():
    """Simulate closing and reopening the game: process memory is gone."""
    secret_store._session_secrets.clear()


class _FakeKeyring:
    """A working OS credential store."""

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


def test_legacy_keys_survive_restart_without_os_credential_store(monkeypatch, tmp_path):
    """Regression for issue #129.

    Migrating a legacy plaintext key must never destroy it. Without an OS
    credential store the only durable place is the settings file itself, so the
    plaintext copy has to stay until something durable replaces it.
    """
    settings_path = _real_store(monkeypatch, tmp_path)
    settings_path.write_text(json.dumps({
        "model_provider": "openai",
        "openai_api_key": "sk-legacy-user-key",
        "gemini_api_key": "gm-legacy-user-key",
    }))

    model_config.apply_persisted_openai_key()
    model_config.apply_persisted_gemini_key()
    assert model_config.has_openai_key()
    assert model_config.has_gemini_key()

    _restart()

    assert model_config.has_openai_key(), "OpenAI key must survive a restart"
    assert model_config.has_gemini_key(), "Gemini key must survive a restart"


def test_retained_plaintext_key_is_made_owner_only(monkeypatch, tmp_path):
    settings_path = _real_store(monkeypatch, tmp_path)
    settings_path.write_text(json.dumps({"openai_api_key": "sk-legacy-user-key"}))
    os.chmod(settings_path, 0o644)

    model_config._migrate_plaintext_secrets(model_config._load_user_settings())

    if os.name == "posix":
        assert stat.S_IMODE(settings_path.stat().st_mode) == 0o600


def test_ui_saved_key_survives_restart_without_os_credential_store(monkeypatch, tmp_path):
    _real_store(monkeypatch, tmp_path)

    model_config.persist_openai_key("sk-typed-into-settings")
    assert model_config.has_openai_key()

    _restart()

    assert model_config.has_openai_key(), (
        "a key saved from the web UI must not have to be re-entered every launch"
    )


def test_local_endpoint_key_survives_restart_without_os_credential_store(monkeypatch, tmp_path):
    _real_store(monkeypatch, tmp_path)

    model_config.persist_local_endpoint(
        base_url="http://127.0.0.1:1234/v1",
        api_key="local-secret",
        model="local-model",
    )
    _restart()

    endpoint = model_config.get_local_endpoint()
    assert endpoint["api_key"] == "local-secret"
    assert endpoint["base_url"] == "http://127.0.0.1:1234/v1"


def test_clearing_a_key_removes_it_from_disk(monkeypatch, tmp_path):
    settings_path = _real_store(monkeypatch, tmp_path)

    model_config.persist_openai_key("sk-temporary")
    model_config.persist_openai_key("")
    _restart()

    assert not model_config.has_openai_key()
    assert "openai_api_key" not in json.loads(settings_path.read_text())


def test_plaintext_is_removed_once_a_credential_store_is_available(monkeypatch, tmp_path):
    """The security intent of the original change must still hold."""
    _FakeKeyring.values.clear()
    settings_path = _real_store(monkeypatch, tmp_path, keyring_backend=_FakeKeyring)
    settings_path.write_text(json.dumps({
        "model_provider": "openai",
        "openai_api_key": "sk-legacy-user-key",
    }))

    model_config._migrate_plaintext_secrets(model_config._load_user_settings())

    saved = json.loads(settings_path.read_text())
    assert "openai_api_key" not in saved, "a working keyring must keep plaintext out of JSON"
    assert saved == {"model_provider": "openai"}
    assert secret_store.get_secret("openai_api_key") == "sk-legacy-user-key"


def test_set_secret_reports_whether_storage_is_durable(monkeypatch):
    _FakeKeyring.values.clear()
    secret_store._session_secrets.clear()

    monkeypatch.setattr(secret_store, "_keyring", lambda: None)
    assert secret_store.set_secret("probe", "value") is False, (
        "memory-only storage must not be reported as durable"
    )

    monkeypatch.setattr(secret_store, "_keyring", lambda: _FakeKeyring)
    assert secret_store.set_secret("probe", "value") is True


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
