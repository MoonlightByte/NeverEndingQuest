# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Durable state, migration receipts, and notification outbox for effects."""

from contextlib import contextmanager
from copy import deepcopy
import os

from core.effects.model import EFFECTS_PIPELINE_VERSION
from utils.encoding_utils import safe_json_load
from utils.file_operations import safe_write_json
from utils.path_transaction_lock import path_transaction_lock


EFFECTS_STATE_PATH = os.path.join("modules", "effects_state.json")


class EffectsStateError(RuntimeError):
    """Effects state could not be safely read or persisted."""


def _empty_state():
    return {
        "schemaVersion": EFFECTS_PIPELINE_VERSION,
        "pipelineMode": "unmigrated",
        "migration": None,
        "outbox": [],
        "deliveredNotifications": [],
    }


def _normalize_state(value):
    if value is None:
        return _empty_state()
    if not isinstance(value, dict):
        raise EffectsStateError("effects_state.json must contain an object")
    result = deepcopy(value)
    result.setdefault("schemaVersion", EFFECTS_PIPELINE_VERSION)
    result.setdefault("pipelineMode", "unmigrated")
    result.setdefault("migration", None)
    result.setdefault("outbox", [])
    result.setdefault("deliveredNotifications", [])
    if result["pipelineMode"] not in ("unmigrated", "declarative", "blocked"):
        raise EffectsStateError("effects pipelineMode is invalid")
    if not isinstance(result["outbox"], list):
        raise EffectsStateError("effects outbox must be an array")
    if not isinstance(result["deliveredNotifications"], list):
        raise EffectsStateError("deliveredNotifications must be an array")
    return result


def load_effects_state():
    return _normalize_state(safe_json_load(EFFECTS_STATE_PATH))


def write_effects_state(value):
    os.makedirs(os.path.dirname(EFFECTS_STATE_PATH), exist_ok=True)
    if not safe_write_json(EFFECTS_STATE_PATH, _normalize_state(value)):
        raise EffectsStateError("could not persist effects_state.json")


@contextmanager
def effects_state_transaction(timeout_seconds=5.0):
    os.makedirs(os.path.dirname(EFFECTS_STATE_PATH), exist_ok=True)
    with path_transaction_lock(
        EFFECTS_STATE_PATH,
        suffix=".effects.lock",
        timeout_seconds=timeout_seconds,
    ) as acquired:
        if acquired is None:
            raise EffectsStateError("timed out acquiring the effects-state lease")
        state = load_effects_state()
        yield state
        write_effects_state(state)


def campaign_effects_migrated():
    try:
        state = load_effects_state()
    except Exception:
        return False
    return (
        state.get("schemaVersion") == EFFECTS_PIPELINE_VERSION
        and state.get("pipelineMode") == "declarative"
        and isinstance(state.get("migration"), dict)
        and state["migration"].get("status") == "complete"
    )
