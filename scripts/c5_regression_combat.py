# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest C5 Regression - Combat hardening checks.

Focused checks for C4 behavior:
- Enemy-phase actor batching only includes valid living non-PC actors.
- Integrity validation accepts legal non-active PC targets.
- Integrity validation rejects unknown targets.
"""

import os
import sys
import types
import ast
import unittest


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


from core.managers.multi_pc_combat import Combatant, CombatantType, TurnQueueManager


def _load_main_helper_namespace():
    """Load selected pure helper functions from main.py via AST."""
    main_path = os.path.join(PROJECT_ROOT, "main.py")
    with open(main_path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source, filename="main.py")
    helper_names = {
        "_normalize_combat_command_input",
        "_is_combat_only_command",
        "get_noncombat_guard_message",
        "get_validation_retry_exhaustion_message",
    }

    helper_defs = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in helper_names
    ]

    helper_module = ast.Module(body=helper_defs, type_ignores=[])
    namespace = {}
    exec(compile(helper_module, filename="main.py", mode="exec"), namespace)
    return namespace


def _import_integrity_validator():
    """Import validate_combatant_integrity with lightweight dependency stubs."""
    openai_mod = types.ModuleType("openai")

    class OpenAI:
        def __init__(self, *args, **kwargs):
            self.chat = types.SimpleNamespace(
                completions=types.SimpleNamespace(create=lambda *a, **k: None)
            )

    openai_mod.OpenAI = OpenAI
    sys.modules["openai"] = openai_mod

    update_character_info_mod = types.ModuleType("updates.update_character_info")
    update_character_info_mod.update_character_info = lambda *a, **k: None
    update_character_info_mod.normalize_character_name = lambda name: name
    sys.modules["updates.update_character_info"] = update_character_info_mod
    sys.modules["updates.update_encounter"] = types.ModuleType("updates.update_encounter")
    sys.modules["updates.update_party_tracker"] = types.ModuleType("updates.update_party_tracker")

    core_ai_pkg = types.ModuleType("core.ai")
    sys.modules["core.ai"] = core_ai_pkg
    import core
    core.ai = core_ai_pkg

    sys.modules["core.ai.cumulative_summary"] = types.ModuleType("core.ai.cumulative_summary")

    combat_compressor_mod = types.ModuleType("core.ai.combat_compressor")

    class CombatUserMessageCompressor:
        def __init__(self, *args, **kwargs):
            pass

        def process_combat_conversation(self, history):
            return history

    combat_compressor_mod.CombatUserMessageCompressor = CombatUserMessageCompressor
    sys.modules["core.ai.combat_compressor"] = combat_compressor_mod

    inventory_mod = types.ModuleType("core.ai.inventory_context_integration")
    inventory_mod.enhance_player_input_with_inventory = lambda *a, **k: a[0] if a else ""
    sys.modules["core.ai.inventory_context_integration"] = inventory_mod

    if "core.managers.combat_manager" in sys.modules:
        del sys.modules["core.managers.combat_manager"]

    from core.managers.combat_manager import validate_combatant_integrity

    return validate_combatant_integrity


class TestC4Hardening(unittest.TestCase):
    """Regression tests for C4 combat hardening."""

    @classmethod
    def setUpClass(cls):
        cls.validate_integrity = staticmethod(_import_integrity_validator())

    def test_enemy_phase_actor_filter(self):
        manager = TurnQueueManager()
        manager.current_turn_index = 0
        manager.turn_queue = [
            Combatant("Goblin A", CombatantType.ENEMY, 15, 7, 7, 15, "alive"),
            Combatant("Fallen Orc", CombatantType.ENEMY, 12, 0, 15, 13, "dead"),
            Combatant("Guard Ally", CombatantType.NPC, 10, 12, 12, 14, "alive"),
            Combatant("Stunned Ally", CombatantType.NPC, 9, 0, 12, 13, "unconscious"),
            Combatant("Acheron", CombatantType.PC, 18, 21, 21, 16, "alive"),
        ]

        remaining = manager.get_remaining_enemies_for_round()
        self.assertEqual(remaining, ["Goblin A", "Guard Ally"])

    def test_integrity_accepts_non_active_pc_target(self):
        response = (
            '{"actions":[{"action":"updateCharacterInfo",'
            '"parameters":{"characterName":"Merisiel","changes":"Takes 6 damage."}}]}'
        )
        encounter_data = {
            "creatures": [
                {"name": "Goblin A", "type": "enemy"},
                {"name": "Guard Ally", "type": "npc"},
            ]
        }
        multi_pc_manager = types.SimpleNamespace(pc_states={"Acheron": {}, "Merisiel": {}})

        result = self.validate_integrity(
            response,
            encounter_data,
            multi_pc_manager=multi_pc_manager,
            party_tracker_data={},
        )
        self.assertTrue(result is True)

    def test_integrity_rejects_unknown_target(self):
        response = (
            '{"actions":[{"action":"updateCharacterInfo",'
            '"parameters":{"characterName":"Phantom Knight","changes":"Takes 5 damage."}}]}'
        )
        encounter_data = {
            "creatures": [
                {"name": "Goblin A", "type": "enemy"},
                {"name": "Acheron", "type": "player"},
            ]
        }

        result = self.validate_integrity(response, encounter_data, multi_pc_manager=None, party_tracker_data={})
        self.assertIsInstance(result, str)
        self.assertIn("INTEGRITY ERROR", result)
        self.assertIn("Phantom Knight", result)


class TestC1C2MainLoopHelpers(unittest.TestCase):
    """Regression tests for C1/C2 fail-closed + command guard helpers."""

    @classmethod
    def setUpClass(cls):
        cls.helper_ns = _load_main_helper_namespace()

    def test_noncombat_guard_init_outside_combat(self):
        guard_fn = self.helper_ns["get_noncombat_guard_message"]
        msg = guard_fn("/init 13", "")
        self.assertIsInstance(msg, str)
        self.assertIn("No active combat encounter", msg)
        self.assertIn("/init", msg)

    def test_noncombat_guard_end_outside_combat(self):
        guard_fn = self.helper_ns["get_noncombat_guard_message"]
        msg = guard_fn("/end", "")
        self.assertIsInstance(msg, str)
        self.assertIn("No active combat encounter", msg)
        self.assertIn("/end command", msg)

    def test_noncombat_guard_ignores_when_active_combat_exists(self):
        guard_fn = self.helper_ns["get_noncombat_guard_message"]
        msg = guard_fn("/end", "encounter_123")
        self.assertIsNone(msg)

    def test_noncombat_guard_handles_tagged_input(self):
        guard_fn = self.helper_ns["get_noncombat_guard_message"]
        msg = guard_fn("[Acheron]: /att goblin 15", "")
        self.assertIsInstance(msg, str)
        self.assertIn("No active combat encounter", msg)
        self.assertIn("/att", msg)

    def test_fail_closed_retry_exhaustion_message_is_deterministic(self):
        msg_fn = self.helper_ns["get_validation_retry_exhaustion_message"]
        msg = msg_fn()
        self.assertEqual(
            msg,
            "[SYSTEM] Unable to generate a valid response after multiple attempts. "
            "The game state may be inconsistent. Please try a different action or restart the session.",
        )

    def test_fail_closed_path_present_and_fail_open_text_removed(self):
        main_path = os.path.join(PROJECT_ROOT, "main.py")
        with open(main_path, "r", encoding="utf-8") as f:
            source = f.read()

        self.assertIn("if not valid_response_received:", source)
        self.assertIn("continue", source)
        self.assertNotIn("Proceeding with the last generated response.", source)


class TestFastLaneInitiationContract(unittest.TestCase):
    """Regression tests for Phase 1 fast-lane combat initiation (no-duplicate-opening)."""

    def _load_combat_manager_source(self):
        """Load raw source of combat_manager.py for contract tests."""
        cm_path = os.path.join(PROJECT_ROOT, "core/managers/combat_manager.py")
        with open(cm_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_fast_lane_guard_contract_exists(self):
        """Fast-lane must guard on multi_pc_manager and awaitingPcGroupRoll."""
        source = self._load_combat_manager_source()
        # Must contain the guard condition
        self.assertIn("multi_pc_manager is not None", source)
        self.assertIn('encounter_data.get("awaitingPcGroupRoll", False) is True', source)
        # Must be assigned to is_fast_lane and used in if statement
        self.assertIn("is_fast_lane = (", source)
        self.assertIn("if is_fast_lane:", source)

    def test_immediate_initiative_prompt_exists(self):
        """Fast-lane must print immediate initiative prompt without LLM call."""
        source = self._load_combat_manager_source()
        expected_msg = (
            "Dungeon Master: [SYSTEM] Combat initiated. Initiative pending. "
            "Enter /init <1-20> to begin combat."
        )
        self.assertIn(expected_msg, source)
        # Must flush stdout immediately after print
        self.assertIn('import sys\n            sys.stdout.flush()', source)

    def test_initial_scene_llm_in_non_fast_lane_path(self):
        """Initial scene AI call must be in non-fast-lane (else) branch."""
        source = self._load_combat_manager_source()
        # The AI call should NOT appear in fast-lane block (before else)
        # Instead it should be in the else branch
        # Find the fast-lane block boundary
        fast_lane_start = source.find("if is_fast_lane:")
        else_start = source.find("else:", fast_lane_start)
        # Verify AI call comes after else (in non-fast-lane path)
        ai_call_pos = source.find('debug("AI_CALL: Getting initial scene description..."')
        self.assertGreater(ai_call_pos, else_start, "AI_CALL must be in else branch, not fast-lane")

    def test_existing_init_gate_preserved(self):
        """Existing /init validation gate must remain present."""
        source = self._load_combat_manager_source()
        # Must contain the awaitingPcGroupRoll gate in combat loop
        self.assertIn(
            'if multi_pc_manager and encounter_data.get("awaitingPcGroupRoll", False):',
            source
        )
        # Must contain usage prompts for invalid /init
        self.assertIn('Dungeon Master: [SYSTEM] Initiative pending. Usage: /init <1-20>', source)
        self.assertIn(
            'Dungeon Master: [SYSTEM] Initiative pending. Roll must be between 1 and 20.',
            source
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
