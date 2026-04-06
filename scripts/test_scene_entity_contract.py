# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Regression Tests - Scene Entity Contract
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.scene_entity_contract import evaluate_scene_entity_encounter_resolution


class TestSceneEntityEncounterResolution(unittest.TestCase):
    """Regression coverage for scene-entity combat validity and violence policy."""

    def test_red_style_scene_only_incorporeal_rejects_create_encounter(self):
        location_data = {
            "npcs": [
                {
                    "name": "Red (The Crimson Binder)",
                    "description": "A projected envoy of the Pumpkin King.",
                    "attitude": "Hostile",
                    "sceneEntity": {
                        "combatValidity": "scene_only",
                        "manifestation": "incorporeal",
                        "violencePolicy": "incorporeal_no_effect",
                    },
                }
            ]
        }

        result = evaluate_scene_entity_encounter_resolution(
            ["Red (The Crimson Binder)"],
            location_data,
        )

        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("error_type"), "non_combat_valid_scene_entity")
        self.assertIn("non_combat_valid_scene_entity", result.get("error_message", ""))

    def test_helpless_kill_else_escalate_resolves_without_combat_when_helpless(self):
        location_data = {
            "npcs": [
                {
                    "name": "Captured Acolyte",
                    "description": "Bound at the wrists and unable to resist.",
                    "attitude": "Fearful",
                    "sceneEntity": {
                        "combatValidity": "escalatable",
                        "manifestation": "corporeal",
                        "violencePolicy": "helpless_kill_else_escalate",
                    },
                }
            ]
        }

        result = evaluate_scene_entity_encounter_resolution(["Captured Acolyte"], location_data)

        self.assertEqual(result.get("status"), "resolved_without_combat")
        helpless_resolutions = result.get("helpless_resolutions", [])
        self.assertEqual(len(helpless_resolutions), 1)
        self.assertEqual(helpless_resolutions[0].get("name"), "Captured Acolyte")

    def test_helpless_kill_else_escalate_requires_proxy_when_resisting(self):
        location_data = {
            "npcs": [
                {
                    "name": "Bandit Courier",
                    "description": "Alert and reaching for a blade.",
                    "attitude": "Hostile",
                    "sceneEntity": {
                        "combatValidity": "escalatable",
                        "manifestation": "corporeal",
                        "violencePolicy": "helpless_kill_else_escalate",
                    },
                }
            ]
        }

        result = evaluate_scene_entity_encounter_resolution(["Bandit Courier"], location_data)

        self.assertEqual(result.get("status"), "error")
        self.assertEqual(result.get("error_type"), "scene_entity_missing_combat_proxy")

    def test_helpless_kill_else_escalate_rewrites_to_proxy_when_resisting(self):
        location_data = {
            "npcs": [
                {
                    "name": "Bandit Courier",
                    "description": "Alert and reaching for a blade.",
                    "attitude": "Hostile",
                    "sceneEntity": {
                        "combatValidity": "escalatable",
                        "manifestation": "corporeal",
                        "violencePolicy": "helpless_kill_else_escalate",
                        "combatProxy": "Bandit",
                    },
                }
            ]
        }

        result = evaluate_scene_entity_encounter_resolution(["Bandit Courier"], location_data)

        self.assertEqual(result.get("status"), "ok")
        self.assertEqual(result.get("resolved_monsters"), ["Bandit"])


class TestActionHandlerSourceContracts(unittest.TestCase):
    """Source contracts for scene-entity guard ordering and success logs."""

    def test_create_encounter_has_scene_entity_preflight_guard(self):
        action_handler_path = Path(__file__).parent.parent / "core/ai/action_handler.py"
        content = action_handler_path.read_text(encoding="utf-8")

        self.assertIn("evaluate_scene_entity_encounter_resolution", content)
        self.assertIn("non_combat_valid_scene_entity", content)

    def test_combat_success_log_occurs_only_after_success_marker_check(self):
        action_handler_path = Path(__file__).parent.parent / "core/ai/action_handler.py"
        content = action_handler_path.read_text(encoding="utf-8")

        marker_check = 'if "Encounter successfully built and saved to" in result.stdout:'
        success_log = 'info("SUCCESS: Combat encounter created successfully", category="combat_processing")'

        marker_index = content.find(marker_check)
        success_index = content.find(success_log)

        self.assertGreater(marker_index, -1, "Success marker check must exist")
        self.assertGreater(success_index, -1, "Success log must exist")
        self.assertGreater(success_index, marker_index, "Success log must execute only inside success branch")


if __name__ == "__main__":
    unittest.main(verbosity=2)
