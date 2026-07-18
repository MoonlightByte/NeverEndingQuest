"""Best-effort OS-backed secret storage for local operator credentials.

Provider keys must never be written to the game's JSON settings file.  When an
OS keyring is available (Windows Credential Manager, macOS Keychain, etc.) it
is used.  On headless systems without one, secrets remain only in memory for
the lifetime of the process.
"""

from __future__ import annotations

import logging


_SERVICE_NAME = "NeverEndingQuest"
_session_secrets = {}
_warned_about_keyring = False


def _keyring():
    """Return the optional keyring module, or None when no backend is usable."""
    global _warned_about_keyring
    try:
        import keyring

        keyring.get_keyring()
        return keyring
    except Exception:
        if not _warned_about_keyring:
            logging.getLogger(__name__).warning(
                "No OS credential store is available; provider keys will only "
                "last for this NeverEndingQuest session."
            )
            _warned_about_keyring = True
        return None


def get_secret(name):
    """Return a stored secret without ever logging it."""
    keyring = _keyring()
    if keyring is not None:
        try:
            value = keyring.get_password(_SERVICE_NAME, name)
            if value:
                return value
        except Exception:
            pass
    return _session_secrets.get(name)


def set_secret(name, value):
    """Store a secret in the OS keyring, falling back to this process only."""
    value = (value or "").strip()
    if not value:
        delete_secret(name)
        return

    keyring = _keyring()
    if keyring is not None:
        try:
            keyring.set_password(_SERVICE_NAME, name, value)
            _session_secrets.pop(name, None)
            return
        except Exception:
            pass
    _session_secrets[name] = value


def delete_secret(name):
    """Remove a secret from both the OS keyring and this process."""
    _session_secrets.pop(name, None)
    keyring = _keyring()
    if keyring is not None:
        try:
            keyring.delete_password(_SERVICE_NAME, name)
        except Exception:
            # Missing entries and unavailable backends are both safe no-ops.
            pass
