#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""Regression tests for character creation session abort and startup recovery."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils import character_creator as character_creator_module


RETRY_GUIDANCE = (
    "Character creation final JSON failed validation. "
    "Result: schema_error. Missing/invalid paths: $. "
    "Output a single corrected JSON object with all required fields completed."
)

WORLD_STATE = "--- WORLD STATE ---\nCurrent module: Test_Module"


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class TestCharacterCreationSessionRecovery(unittest.TestCase):
    """Validate fail-closed cleanup for poisoned creation sessions."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)

        self.original_paths = {
            "CONVERSATION_HISTORY_FILE": character_creator_module.CONVERSATION_HISTORY_FILE,
            "CONVERSATION_BACKUP_FILE": character_creator_module.CONVERSATION_BACKUP_FILE,
            "CHAT_HISTORY_FILE": character_creator_module.CHAT_HISTORY_FILE,
            "CHARACTER_CREATION_MARKER": character_creator_module.CHARACTER_CREATION_MARKER,
        }

        character_creator_module.CONVERSATION_HISTORY_FILE = str(self.base_path / "conversation_history.json")
        character_creator_module.CONVERSATION_BACKUP_FILE = str(self.base_path / "conversation_history_backup.json")
        character_creator_module.CHAT_HISTORY_FILE = str(self.base_path / "chat_history.json")
        character_creator_module.CHARACTER_CREATION_MARKER = str(self.base_path / "creation_mode_active.json")

    def tearDown(self) -> None:
        for key, value in self.original_paths.items():
            setattr(character_creator_module, key, value)
        self.temp_dir.cleanup()

    def _marker_path(self) -> Path:
        return Path(character_creator_module.CHARACTER_CREATION_MARKER)

    def _conversation_path(self) -> Path:
        return Path(character_creator_module.CONVERSATION_HISTORY_FILE)

    def _backup_path(self) -> Path:
        return Path(character_creator_module.CONVERSATION_BACKUP_FILE)

    def _chat_path(self) -> Path:
        return Path(character_creator_module.CHAT_HISTORY_FILE)

    def test_abort_session_restores_backup_and_removes_marker(self) -> None:
        backup_messages = [{"role": "assistant", "content": "Original narrative state."}]
        poisoned_messages = [
            {"role": "user", "content": RETRY_GUIDANCE},
            {"role": "user", "content": WORLD_STATE},
        ]

        _write_json(self._backup_path(), backup_messages)
        _write_json(self._conversation_path(), poisoned_messages)
        _write_json(self._chat_path(), poisoned_messages)
        _write_json(self._marker_path(), {"character_name": "Xorn", "started_at": "2026-03-16T12:43:26"})

        result = character_creator_module.abort_character_creation_session("unit_test_abort")

        self.assertTrue(result["backup_present"])
        self.assertTrue(result["conversation_restored"])
        self.assertTrue(result["marker_removed"])
        self.assertFalse(self._marker_path().exists())
        self.assertEqual(_read_json(self._conversation_path()), backup_messages)
        self.assertEqual(_read_json(self._chat_path()), [])

    def test_abort_session_removes_marker_even_without_backup(self) -> None:
        poisoned_messages = [
            {"role": "assistant", "content": "Keep this narration."},
            {"role": "user", "content": RETRY_GUIDANCE},
            {"role": "user", "content": WORLD_STATE},
            {"role": "assistant", "content": "Keep this follow-up."},
        ]

        _write_json(self._conversation_path(), poisoned_messages)
        _write_json(self._chat_path(), poisoned_messages)
        _write_json(self._marker_path(), {"character_name": "Xorn"})

        result = character_creator_module.abort_character_creation_session("no_backup_abort")

        self.assertFalse(result["backup_present"])
        self.assertFalse(result["conversation_restored"])
        self.assertTrue(result["marker_removed"])
        self.assertFalse(self._marker_path().exists())

        conversation_after = _read_json(self._conversation_path())
        chat_after = _read_json(self._chat_path())

        self.assertEqual(
            conversation_after,
            [
                {"role": "assistant", "content": "Keep this narration."},
                {"role": "assistant", "content": "Keep this follow-up."},
            ],
        )
        self.assertEqual(chat_after, conversation_after)

    def test_detect_poisoned_creation_session_requires_threshold(self) -> None:
        _write_json(self._marker_path(), {"character_name": "Xorn", "started_at": "2026-03-16T12:43:26"})
        _write_json(self._conversation_path(), [{"role": "user", "content": RETRY_GUIDANCE}])
        _write_json(self._chat_path(), [])

        healthy_detection = character_creator_module.detect_poisoned_creation_session()
        self.assertTrue(healthy_detection["marker_exists"])
        self.assertFalse(healthy_detection["is_poisoned"])
        self.assertEqual(healthy_detection["retry_count"], 1)

        _write_json(
            self._conversation_path(),
            [
                {"role": "user", "content": RETRY_GUIDANCE},
                {"role": "user", "content": RETRY_GUIDANCE},
            ],
        )

        poisoned_detection = character_creator_module.detect_poisoned_creation_session()
        self.assertTrue(poisoned_detection["is_poisoned"])
        self.assertEqual(poisoned_detection["retry_count"], 2)

    def test_startup_recovery_cleans_only_poisoned_sessions(self) -> None:
        backup_messages = [{"role": "assistant", "content": "Recovered narrative."}]
        poisoned_messages = [
            {"role": "user", "content": RETRY_GUIDANCE},
            {"role": "user", "content": WORLD_STATE},
            {"role": "user", "content": RETRY_GUIDANCE},
        ]

        _write_json(self._backup_path(), backup_messages)
        _write_json(self._conversation_path(), poisoned_messages)
        _write_json(self._chat_path(), poisoned_messages)
        _write_json(self._marker_path(), {"character_name": "Xorn", "started_at": "2026-03-16T12:43:26"})

        poisoned_recovery = character_creator_module.recover_poisoned_creation_session_on_startup()
        self.assertTrue(poisoned_recovery["is_poisoned"])
        self.assertTrue(poisoned_recovery["recovered"])
        self.assertFalse(self._marker_path().exists())
        self.assertEqual(_read_json(self._conversation_path()), backup_messages)

        healthy_messages = [{"role": "assistant", "content": "Healthy in-progress interview."}]
        _write_json(self._conversation_path(), healthy_messages)
        _write_json(self._chat_path(), healthy_messages)
        _write_json(self._marker_path(), {"character_name": "Healthy Hero", "started_at": "2026-03-16T13:00:00"})

        healthy_recovery = character_creator_module.recover_poisoned_creation_session_on_startup()
        self.assertFalse(healthy_recovery["is_poisoned"])
        self.assertFalse(healthy_recovery["recovered"])
        self.assertTrue(self._marker_path().exists())


if __name__ == "__main__":
    unittest.main()
