# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - updateEncounter ops runtime tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Runtime coverage for Workstream I Step 3.2 deterministic encounter ops.
"""

import json
import os
import sys
import unittest


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

MISSING_JSONSCHEMA = False

try:
    from updates.update_encounter import update_encounter
except ModuleNotFoundError as import_error:
    if getattr(import_error, "name", "") == "jsonschema":
        MISSING_JSONSCHEMA = True
        update_encounter = None
    else:
        raise


@unittest.skipIf(MISSING_JSONSCHEMA, "jsonschema dependency unavailable")
class TestUpdateEncounterOpsRuntime(unittest.TestCase):
    """Covers narrow deterministic enemy encounter ops runtime path."""

    def setUp(self):
        self.encounter_id = "UNITTEST_ENCOUNTER_OPS"
        self.encounter_path = os.path.join(
            REPO_ROOT,
            "modules",
            "encounters",
            f"encounter_{self.encounter_id}.json",
        )
        self._write_fixture()

    def tearDown(self):
        if os.path.exists(self.encounter_path):
            os.remove(self.encounter_path)

    def _write_fixture(self):
        fixture = {
            "encounterId": self.encounter_id,
            "encounterSummary": "Unit test encounter",
            "creatures": [
                {
                    "name": "Goblin-1",
                    "type": "enemy",
                    "monsterType": "goblin",
                    "initiative": 12,
                    "status": "alive",
                    "conditions": [],
                    "actions": {"actionType": "attack", "target": "pc"},
                    "currentHitPoints": 15,
                    "maxHitPoints": 15,
                }
            ],
        }
        with open(self.encounter_path, "w", encoding="utf-8") as file_handle:
            json.dump(fixture, file_handle, indent=2)

    def _read_encounter(self):
        with open(self.encounter_path, "r", encoding="utf-8") as file_handle:
            return json.load(file_handle)

    def test_supported_enemy_ops_apply_deterministically(self):
        result = update_encounter(
            self.encounter_id,
            None,
            ops=[
                {"op": "hp_delta", "creature": "Goblin-1", "delta": -7},
                {"op": "condition_add", "creature": "Goblin-1", "condition": "Prone"},
                {"op": "set_status", "creature": "Goblin-1", "status": "defeated"},
            ],
        )

        self.assertIsNotNone(result)
        goblin = result["creatures"][0]
        self.assertEqual(goblin["currentHitPoints"], 8)
        self.assertEqual(goblin["status"], "defeated")
        self.assertIn("Prone", goblin["conditions"])

        persisted = self._read_encounter()
        persisted_goblin = persisted["creatures"][0]
        self.assertEqual(persisted_goblin["currentHitPoints"], 8)
        self.assertEqual(persisted_goblin["status"], "defeated")
        self.assertIn("Prone", persisted_goblin["conditions"])

    def test_unsupported_ops_fail_open_to_noop_without_changes(self):
        baseline = self._read_encounter()
        result = update_encounter(
            self.encounter_id,
            None,
            ops=[{"op": "initiative_set", "creature": "Goblin-1", "initiative": 20}],
        )

        self.assertEqual(result, baseline)
        self.assertEqual(self._read_encounter(), baseline)


if __name__ == "__main__":
    unittest.main(verbosity=2)
