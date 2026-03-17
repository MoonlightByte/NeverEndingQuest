# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest - Mechanical Follow-Through Hardening Tests
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Focused contracts for scene gift reconciliation, feature usage ops,
and pre-combat hostile scene presence wiring.
"""

import ast
import copy
import os
import sys
import unittest
from typing import Any, Dict, List, Optional, Tuple


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

UPDATE_CHARACTER_INFO_PATH = os.path.join(REPO_ROOT, "updates", "update_character_info.py")


def _load_update_helpers():
    with open(UPDATE_CHARACTER_INFO_PATH, "r", encoding="utf-8") as file_handle:
        source = file_handle.read()

    parsed = ast.parse(source)
    target_assign_names = {"SUPPORTED_CHARACTER_OPS"}
    target_func_names = {
        "_to_int",
        "_resolve_op_type",
        "_find_equipment_entry",
        "_find_ammunition_entry",
        "_find_class_feature_entry",
        "_read_feature_usage",
        "_write_feature_usage",
        "_apply_character_ops_deterministic",
    }

    selected_nodes = []
    for node in parsed.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in target_assign_names:
                    selected_nodes.append(node)
                    break
        elif isinstance(node, ast.FunctionDef) and node.name in target_func_names:
            selected_nodes.append(node)

    helper_module = ast.Module(body=selected_nodes, type_ignores=[])
    namespace = {
        "copy": copy,
        "Any": Any,
        "Dict": Dict,
        "List": List,
        "Optional": Optional,
        "Tuple": Tuple,
    }
    exec(compile(helper_module, filename=UPDATE_CHARACTER_INFO_PATH, mode="exec"), namespace)
    return namespace


class TestSceneItemReconcile(unittest.TestCase):
    def test_generic_named_actor_gives_item(self):
        from utils.scene_item_reconcile import infer_scene_item_grant_actions

        parsed_response = {
            "narration": "Quartermaster Dain gives Scout Kira a healing potion.",
            "actions": [],
        }
        party_tracker = {
            "partyMembers": ["Chronos", "Blairen", "Vitreol"],
            "partyNPCs": [{"name": "Scout Kira"}],
        }
        location_data = {
            "npcs": [{"name": "Quartermaster Dain"}],
        }
        conversation_history = [{"role": "user", "content": "We accept Dain's help."}]

        inferred = infer_scene_item_grant_actions(parsed_response, party_tracker, location_data, conversation_history)
        self.assertEqual(len(inferred), 1)
        self.assertEqual(inferred[0]["parameters"]["characterName"], "Scout Kira")
        self.assertEqual(inferred[0]["parameters"]["ops"][0]["op"], "inventory_add")
        self.assertEqual(inferred[0]["parameters"]["ops"][0]["item"], "Healing Potion")

    def test_each_distribution_pattern_generates_per_recipient_grants(self):
        from utils.scene_item_reconcile import infer_scene_item_grant_actions

        parsed_response = {
            "narration": (
                "Quartermaster Dain offers gifts for the road. "
                "Chronos and Blairen take a ward stone each."
            ),
            "actions": [],
        }
        party_tracker = {
            "partyMembers": ["Chronos", "Blairen", "Vitreol"],
            "partyNPCs": [{"name": "Scout Kira"}],
        }
        location_data = {
            "npcs": [{"name": "Quartermaster Dain"}],
        }

        inferred = infer_scene_item_grant_actions(parsed_response, party_tracker, location_data, [])
        self.assertEqual(len(inferred), 2)
        targets = {item["parameters"]["characterName"] for item in inferred}
        self.assertEqual(targets, {"Chronos", "Blairen"})
        for item in inferred:
            self.assertEqual(item["parameters"]["ops"][0]["item"], "Ward Stone")
            self.assertEqual(item["parameters"]["ops"][0]["quantity"], 1)

    def test_recipient_receives_from_actor_pattern_supported(self):
        from utils.scene_item_reconcile import infer_scene_item_grant_actions

        parsed_response = {
            "narration": "Scout Kira receives the healing potion from Quartermaster Dain.",
            "actions": [],
        }
        party_tracker = {
            "partyMembers": ["Chronos", "Blairen", "Vitreol"],
            "partyNPCs": [{"name": "Scout Kira"}],
        }
        location_data = {
            "npcs": [{"name": "Quartermaster Dain"}],
        }

        inferred = infer_scene_item_grant_actions(parsed_response, party_tracker, location_data, [])
        self.assertEqual(len(inferred), 1)
        self.assertEqual(inferred[0]["parameters"]["characterName"], "Scout Kira")
        self.assertEqual(inferred[0]["parameters"]["ops"][0]["item"], "Healing Potion")

    def test_vague_reward_language_is_noop(self):
        from utils.scene_item_reconcile import infer_scene_item_grant_actions

        parsed_response = {
            "narration": "The party receives some supplies before departing.",
            "actions": [],
        }
        party_tracker = {
            "partyMembers": ["Chronos", "Blairen", "Vitreol"],
            "partyNPCs": [{"name": "Scout Kira"}],
        }

        inferred = infer_scene_item_grant_actions(parsed_response, party_tracker, {}, [])
        self.assertEqual(inferred, [])

    def test_scene_reconcile_has_no_maelo_hardwire(self):
        reconcile_path = os.path.join(REPO_ROOT, "utils", "scene_item_reconcile.py")
        with open(reconcile_path, "r", encoding="utf-8") as file_handle:
            source = file_handle.read().lower()

        self.assertNotIn("_has_maelo_context", source)
        self.assertNotIn("hermit maelo", source)


class TestFeatureUsageOps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        namespace = _load_update_helpers()
        cls.apply_ops = staticmethod(namespace["_apply_character_ops_deterministic"])

    def test_feature_usage_delta_updates_nested_usage(self):
        character_data = {
            "classFeatures": [
                {"name": "Rage", "usage": {"current": 2, "max": 2, "refreshOn": "longRest"}}
            ]
        }
        ops = [{"op": "feature_usage_delta", "feature": "Rage", "delta": -1}]

        success, updated, error_message, unsupported = self.apply_ops(character_data, ops)
        self.assertTrue(success)
        self.assertEqual(error_message, "")
        self.assertEqual(unsupported, [])
        self.assertEqual(updated["classFeatures"][0]["usage"]["current"], 1)

    def test_feature_usage_set_updates_legacy_flat_usage(self):
        character_data = {
            "classFeatures": [
                {"name": "Second Wind", "currentUses": 1, "maxUses": 1, "uses": 1}
            ]
        }
        ops = [{"op": "feature_usage_set", "feature": "Second Wind", "current": 0, "max": 1}]

        success, updated, error_message, unsupported = self.apply_ops(character_data, ops)
        self.assertTrue(success)
        self.assertEqual(error_message, "")
        self.assertEqual(unsupported, [])
        self.assertEqual(updated["classFeatures"][0]["currentUses"], 0)
        self.assertEqual(updated["classFeatures"][0]["uses"], 0)
        self.assertEqual(updated["classFeatures"][0]["maxUses"], 1)


class TestPreCombatHostilePresenceSourceContracts(unittest.TestCase):
    def test_party_data_payload_includes_location_hostiles(self):
        socket_handler_path = os.path.join(
            REPO_ROOT,
            "web",
            "extensions",
            "tabletop_socket_handlers.py",
        )
        with open(socket_handler_path, "r", encoding="utf-8") as file_handle:
            source = file_handle.read()

        self.assertIn("location_hostiles", source)
        self.assertIn("'type': 'location_hostile'", source)

    def test_party_strip_renders_location_hostiles(self):
        template_path = os.path.join(
            REPO_ROOT,
            "web",
            "templates",
            "game_interface.html",
        )
        with open(template_path, "r", encoding="utf-8") as file_handle:
            source = file_handle.read()

        self.assertIn("response.location_hostiles", source)
        self.assertIn("Hostile Presence", source)


class TestDMNoteMechanicalVisibilitySourceContracts(unittest.TestCase):
    def test_dm_note_uses_equipment_and_ammunition_visibility(self):
        dm_note_path = os.path.join(
            REPO_ROOT,
            "utils",
            "multi_pc_dm_note.py",
        )
        with open(dm_note_path, "r", encoding="utf-8") as file_handle:
            source = file_handle.read()

        self.assertIn("pc_data.get('equipment'", source)
        self.assertIn("pc_data.get('ammunition'", source)
        self.assertIn("_summarize_limited_resources", source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
