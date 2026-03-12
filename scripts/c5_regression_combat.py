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


class TestDmGroupOpeningPhaseTransitionContract(unittest.TestCase):
    """Regression tests for dmGroup opening enemy batch -> PC phase transition and non-loop behavior."""

    def _load_combat_manager_source(self):
        """Load raw source of combat_manager.py for contract tests."""
        cm_path = os.path.join(PROJECT_ROOT, "core/managers/combat_manager.py")
        with open(cm_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_init_dmgroup_sets_opening_marker(self):
        """/init path must set openingEnemyBatchPending when dmGroup wins initiative."""
        source = self._load_combat_manager_source()
        # Find the /init resolution block where dmGroup wins
        # The marker should be set via apply_opening_batch_marker when winner is dmGroup
        self.assertIn('apply_opening_batch_marker(encounter_data, winner)', source)
        # Verify the PHASE_MARKER debug log for dmGroup via /init path
        self.assertIn(
            'PHASE_MARKER: Set openingEnemyBatchPending=True via /init dmGroup path',
            source
        )

    def test_roundstart_dmgroup_sets_opening_marker(self):
        """Round-start path must set openingEnemyBatchPending when roundStartsWith=dmGroup."""
        source = self._load_combat_manager_source()
        # Find the round start block that applies dmGroup phase
        self.assertIn('round_starts_with = encounter_data.get("roundStartsWith", "pcGroup")', source)
        self.assertIn('if round_starts_with == "dmGroup":', source)
        self.assertIn('apply_opening_batch_marker(encounter_data, "dmGroup")', source)
        # Verify the PHASE_MARKER debug log for dmGroup via round-start path
        self.assertIn(
            'PHASE_MARKER: Set openingEnemyBatchPending=True via round-start dmGroup path',
            source
        )

    def test_opening_batch_clears_marker_and_returns_pc_phase(self):
        """Opening batch completion must clear marker and transition to PC_PHASE."""
        source = self._load_combat_manager_source()
        # Find the opening batch completion block
        self.assertIn('if encounter_data.get("openingEnemyBatchPending", False):', source)
        # Verify marker is cleared
        self.assertIn('encounter_data["openingEnemyBatchPending"] = False', source)
        # Verify PC phase is made ready
        self.assertIn('multi_pc_manager.pc_phase_complete = False', source)
        # Verify the PHASE_MARKER debug log for clearing
        self.assertIn(
            'PHASE_MARKER: Cleared openingEnemyBatchPending after opening enemy batch resolution',
            source
        )
        # Verify STATE_CHANGE log for PC phase transition
        self.assertIn(
            'STATE_CHANGE: Opening batch complete -> PC_PHASE',
            source
        )

    def test_opening_batch_completion_block_is_non_looping_contract(self):
        """Opening batch completion block must not re-enable marker in the same path (non-loop)."""
        source = self._load_combat_manager_source()
        # Find the opening batch completion block boundaries
        marker_check_pos = source.find('if encounter_data.get("openingEnemyBatchPending", False):')
        self.assertGreater(marker_check_pos, 0, "Opening batch check must exist")

        # Find the next significant block after the opening batch completion
        # (either next round handling or save/exit)
        save_after_clear = source.find(
            'save_json_file(f"modules/encounters/encounter_{encounter_id}.json", encounter_data)',
            marker_check_pos
        )
        self.assertGreater(save_after_clear, marker_check_pos, "Save must occur after marker clear")

        # Verify that within the completion block, there is no re-setting of the marker
        completion_block = source[marker_check_pos:save_after_clear]

        # Count occurrences of marker being set to True in this block
        # Should be exactly one clear (False), zero sets (True)
        false_count = completion_block.count('"openingEnemyBatchPending"] = False')
        true_count = completion_block.count('"openingEnemyBatchPending"] = True')

        self.assertEqual(false_count, 1, "Marker must be cleared exactly once in completion block")
        self.assertEqual(true_count, 0, "Marker must NOT be set to True in completion block (non-loop)")

    def test_pcgroup_clears_marker_does_not_set(self):
        """pcGroup winner must clear opening marker without setting it."""
        source = self._load_combat_manager_source()
        # Verify the PHASE_MARKER debug log for pcGroup clearing marker
        self.assertIn(
            'PHASE_MARKER: Cleared openingEnemyBatchPending via /init pcGroup path',
            source
        )
        self.assertIn(
            'PHASE_MARKER: Cleared openingEnemyBatchPending via round-start pcGroup path',
            source
        )


class TestEncounterRosterBackfillContract(unittest.TestCase):
    """Regression tests for encounter roster backfill and duplicate-prevention."""

    def _load_combat_manager_source(self):
        """Load raw source of combat_manager.py for contract tests."""
        cm_path = os.path.join(PROJECT_ROOT, "core/managers/combat_manager.py")
        with open(cm_path, "r", encoding="utf-8") as f:
            return f.read()

    def _load_combat_state_sync_source(self):
        """Load raw source of combat_state_sync.py for backfill contract tests."""
        css_path = os.path.join(PROJECT_ROOT, "core/managers/combat_state_sync.py")
        with open(css_path, "r", encoding="utf-8") as f:
            return f.read()

    def _load_combat_builder_source(self):
        """Load raw source of combat_builder.py for encounter generation contract tests."""
        cb_path = os.path.join(PROJECT_ROOT, "core/generators/combat_builder.py")
        with open(cb_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_backfill_contract_present_for_missing_party_members(self):
        """Backfill must add missing party members to encounter roster."""
        # Check combat_state_sync.py for normalize_multi_pc_roster function
        css_source = self._load_combat_state_sync_source()
        self.assertIn(
            "def normalize_multi_pc_roster(",
            css_source,
            "normalize_multi_pc_roster function must exist for roster backfill"
        )
        # Check for party member iteration logic
        self.assertIn(
            'party_members = party_tracker_data.get("partyMembers", [])',
            css_source,
            "Must read partyMembers from party_tracker_data"
        )
        # Check for missing player detection
        self.assertIn(
            "if not normalized_member or normalized_member in existing_players:",
            css_source,
            "Must check for existing players to identify missing ones"
        )
        # Check for player addition to creatures
        self.assertIn(
            'creatures.append(',
            css_source,
            "Must append missing players to creatures list"
        )
        # Check backfill logging
        self.assertIn(
            "ROSTER_BACKFILL: Added missing player",
            css_source,
            "Must log when backfilling missing players"
        )

    def test_backfill_contract_preserves_existing_enemy_npc_state(self):
        """Backfill must preserve existing enemy/NPC HP/status/initiative (additive only)."""
        css_source = self._load_combat_state_sync_source()
        # Verify additive-only approach - creatures list is extended, not replaced
        self.assertIn(
            "creatures = encounter_data.get(\"creatures\", [])",
            css_source,
            "Must read existing creatures list (not replace)"
        )
        # Verify only appending new players, not modifying existing entries
        append_pos = css_source.find("creatures.append(")
        self.assertGreater(append_pos, 0, "Must append to creatures list")
        # Verify no modification of existing creature properties
        self.assertNotIn(
            "creature[\"status\"] =",
            css_source,
            "Must NOT modify existing creature status (preserve enemy/NPC state)"
        )
        self.assertNotIn(
            "creature[\"initiative\"] =",
            css_source,
            "Must NOT modify existing creature initiative (preserve enemy/NPC state)"
        )

    def test_duplicate_prevention_when_player_already_exists(self):
        """Duplicate prevention: existing player must not be added again."""
        css_source = self._load_combat_state_sync_source()
        # Check for existing player tracking set
        self.assertIn(
            "existing_players = {",
            css_source,
            "Must track existing players in a set for deduplication"
        )
        # Check for case-insensitive name normalization
        self.assertIn(
            "def _normalize_name(name: Any) -> str:",
            css_source,
            "Must normalize names for case-insensitive matching"
        )
        self.assertIn(
            '.strip().lower()',
            css_source,
            "Must use lowercase comparison for name deduplication"
        )
        # Check for skip logic when player already exists
        self.assertIn(
            "if not normalized_member or normalized_member in existing_players:",
            css_source,
            "Must skip players already in existing_players set (duplicate prevention)"
        )
        # Also verify combat_builder.py duplicate prevention during generation
        cb_source = self._load_combat_builder_source()
        self.assertIn(
            "if not normalized_member or normalized_member in seen_players:",
            cb_source,
            "combat_builder must also prevent duplicate players during generation"
        )

    def test_fail_open_contract_for_missing_character_sources(self):
        """Missing character file must not crash combat (fail-open behavior)."""
        css_source = self._load_combat_state_sync_source()
        # Check for safe character loading with fallback
        self.assertIn(
            "char_data = safe_json_load(char_file)",
            css_source,
            "Must use safe_json_load for character file loading"
        )
        # Check for continue on missing character (not crash)
        self.assertIn(
            "if not char_data:",
            css_source,
            "Must check if character data loaded successfully"
        )
        self.assertIn(
            "continue",
            css_source,
            "Must continue to next party member if character file missing (fail-open)"
        )
        # Check for warning log instead of error/crash
        self.assertIn(
            "warning(",
            css_source,
            "Must use warning (not error) for missing character data"
        )
        self.assertIn(
            "ROSTER_BACKFILL: Missing character data for",
            css_source,
            "Must log warning when character data missing"
        )
        # Check outer exception handling (fail-open at function level)
        self.assertIn(
            "except Exception as e:",
            css_source,
            "Must have outer exception handler for fail-open behavior"
        )
        self.assertIn(
            "ROSTER_BACKFILL: Fail-open due to normalization error",
            css_source,
            "Must log and return safely on any normalization error"
        )


class TestInitiativePayloadInclusionContract(unittest.TestCase):
    """Regression tests for initiative payload inclusion of unconscious/incapacitated players."""

    def _load_tabletop_socket_handlers_source(self):
        """Load raw source of tabletop_socket_handlers.py for contract tests."""
        tsh_path = os.path.join(PROJECT_ROOT, "web/extensions/tabletop_socket_handlers.py")
        with open(tsh_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_unconscious_incapacitated_players_included_in_payload(self):
        """Unconscious and incapacitated players must be included in initiative payload."""
        source = self._load_tabletop_socket_handlers_source()
        # Verify Section 3.1 TABLETOP MODE comment exists
        self.assertIn(
            "TABLETOP MODE: Section 3.1 - Keep player combatants visible during active combat",
            source,
            "Must have TABLETOP MODE Section 3.1 comment for player visibility"
        )
        # Verify player inclusion logic includes non-dead players
        self.assertIn(
            'if creature_type == "player":',
            source,
            "Must check creature type for player combatants"
        )
        self.assertIn(
            'if status != "dead":',
            source,
            "Must include players with status != dead (covers unconscious/incapacitated)"
        )
        self.assertIn(
            "visible_combatants.append(creature)",
            source,
            "Must append non-dead players to visible combatants"
        )

    def test_dead_players_excluded_from_payload(self):
        """Dead players must be excluded from initiative payload."""
        source = self._load_tabletop_socket_handlers_source()
        # Verify dead player exclusion logic
        self.assertIn(
            'if status != "dead":',
            source,
            "Must exclude dead players via status != dead check"
        )
        # Ensure there's no logic that would include dead players
        player_block_start = source.find('if creature_type == "player":')
        player_block_end = source.find("else:", player_block_start)
        player_block = source[player_block_start:player_block_end]
        # Verify dead check is present in player block
        self.assertIn(
            'if status != "dead":',
            player_block,
            "Dead player exclusion must be in player type block"
        )

    def test_status_field_preserved_for_ui_display(self):
        """Status field must be preserved in payload for UI consumption."""
        source = self._load_tabletop_socket_handlers_source()
        # Verify status is read from creature data
        self.assertIn(
            'status = str(creature.get("status", "unknown")).lower()',
            source,
            "Must read status field from creature data"
        )
        # Verify status is included in combatant_data
        self.assertIn(
            '"status": combatant.get("status")',
            source,
            "Must include status in combatant_data payload"
        )

    def test_all_unconscious_edge_case_payload_still_active(self):
        """All players unconscious/incapacitated must still show active combat payload."""
        source = self._load_tabletop_socket_handlers_source()
        # Verify active flag is set when visible_combatants exist
        self.assertIn(
            "if not visible_combatants:",
            source,
            "Must check if visible combatants exist before setting inactive"
        )
        self.assertIn(
            "'active': True",
            source,
            "Must set active: True when combatants are present"
        )
        # Verify the flow: non-dead players -> visible_combatants -> active: True
        # This ensures even all-unconscious party keeps combat active
        visible_check_pos = source.find("if not visible_combatants:")
        active_true_pos = source.find("'active': True")
        self.assertGreater(
            active_true_pos,
            visible_check_pos,
            "active: True must come after visible_combatants check"
        )


class TestCompatibilityAndSinglePlayerContract(unittest.TestCase):
    """Regression tests for pcGroup starts and single-player behavior compatibility."""

    def _load_combat_manager_source(self):
        """Load raw source of combat_manager.py for contract tests."""
        cm_path = os.path.join(PROJECT_ROOT, "core/managers/combat_manager.py")
        with open(cm_path, "r", encoding="utf-8") as f:
            return f.read()

    def _load_combat_state_sync_source(self):
        """Load raw source of combat_state_sync.py for contract tests."""
        css_path = os.path.join(PROJECT_ROOT, "core/managers/combat_state_sync.py")
        with open(css_path, "r", encoding="utf-8") as f:
            return f.read()

    def _load_combat_builder_source(self):
        """Load raw source of combat_builder.py for contract tests."""
        cb_path = os.path.join(PROJECT_ROOT, "core/generators/combat_builder.py")
        with open(cb_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_pcgroup_winner_no_opening_batch_marker(self):
        """pcGroup winner must NOT set openingEnemyBatchPending marker."""
        cm_source = self._load_combat_manager_source()
        css_source = self._load_combat_state_sync_source()

        # Verify apply_opening_batch_marker exists
        self.assertIn(
            "def apply_opening_batch_marker(",
            css_source,
            "apply_opening_batch_marker function must exist"
        )

        # Verify pcGroup path clears marker via apply_opening_batch_marker
        self.assertIn(
            'apply_opening_batch_marker(encounter_data, winner)',
            cm_source,
            "Must call apply_opening_batch_marker with winner parameter"
        )

        # Verify pcGroup clears marker (sets to False)
        self.assertIn(
            'marker_enabled = str(starts_with or "").strip() == "dmGroup"',
            css_source,
            "Marker must only be enabled for dmGroup, not pcGroup"
        )

        # Verify PHASE_MARKER logs for pcGroup clearing
        self.assertIn(
            'PHASE_MARKER: Cleared openingEnemyBatchPending via /init pcGroup path',
            cm_source,
            "Must log pcGroup marker clearing via /init path"
        )

    def test_single_player_no_roster_expansion(self):
        """Single-player mode must NOT trigger multi-PC roster expansion."""
        css_source = self._load_combat_state_sync_source()
        cb_source = self._load_combat_builder_source()

        # Verify backfill only triggers with > 1 party members
        self.assertIn(
            "if len(party_members) <= 1:",
            css_source,
            "Must skip backfill for single party member"
        )

        # Verify combat_builder single-party-member guard
        self.assertIn(
            "if len(party_members) > 1:",
            cb_source,
            "combat_builder must check party size > 1 before roster expansion"
        )

        # Verify single player keeps existing behavior
        self.assertIn(
            'player_names = [encounter_data["player"]]',
            cb_source,
            "Single-player must use only triggering player, not expand roster"
        )

    def test_legacy_encounter_fail_open_contract(self):
        """Legacy encounters without new fields must work (fail-open compatibility)."""
        cm_source = self._load_combat_manager_source()
        css_source = self._load_combat_state_sync_source()

        # Verify safe defaults for missing initiativeMode
        self.assertIn(
            'encounter_data.get("initiativeMode", "two_group_phase1")',
            cm_source,
            "Must use default initiativeMode when field missing (legacy compatibility)"
        )

        # Verify safe defaults for missing initiativeWinner
        self.assertIn(
            'encounter_data.get("initiativeWinner", "pending")',
            cm_source,
            "Must use default initiativeWinner when field missing"
        )

        # Verify safe defaults for missing roundStartsWith
        self.assertIn(
            'encounter_data.get("roundStartsWith", "pcGroup")',
            cm_source,
            "Must use default roundStartsWith when field missing"
        )

        # Verify safe_json_load usage in backfill
        self.assertIn(
            "char_data = safe_json_load(char_file)",
            css_source,
            "Must use safe_json_load for fail-open character loading"
        )

    def test_roundstart_pcgroup_no_forced_enemy_phase(self):
        """Round start with pcGroup must NOT force enemy phase."""
        cm_source = self._load_combat_manager_source()

        # Verify round start logic differentiates pcGroup vs dmGroup
        self.assertIn(
            'if round_starts_with == "dmGroup":',
            cm_source,
            "Must check round_starts_with value to determine phase"
        )

        # Verify pcGroup path sets pc_phase_complete = False (PC_PHASE ready)
        self.assertIn(
            'multi_pc_manager.pc_phase_complete = False',
            cm_source,
            "pcGroup round start must set pc_phase_complete = False (PC_PHASE)"
        )

        # Verify dmGroup path is explicitly different
        dmgroup_block_start = cm_source.find('if round_starts_with == "dmGroup":')
        pcgroup_block_start = cm_source.find('else:', dmgroup_block_start)
        roundstart_block = cm_source[dmgroup_block_start:pcgroup_block_start]

        # dmGroup path should set pc_phase_complete = True (ENEMY_PHASE)
        self.assertIn(
            "multi_pc_manager.pc_phase_complete = True",
            roundstart_block,
            "dmGroup round start must set pc_phase_complete = True (ENEMY_PHASE)"
        )

        # Verify STATE_CHANGE logging distinguishes the paths
        self.assertIn(
            "STATE_CHANGE: Applied roundStartsWith=pcGroup -> PC_PHASE start",
            cm_source,
            "Must log pcGroup round start as PC_PHASE"
        )


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
        # TABLETOP MODE: Ensure initiative helper auto-prefill marker is preserved
        self.assertIn("[prefill:/init ]", source)
        # Must flush stdout immediately after print
        self.assertIn('import sys', source)
        self.assertIn('sys.stdout.flush()', source)

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
        # TABLETOP MODE: Prompt lines should carry /init input prefill marker
        self.assertIn('[prefill:/init ] Dungeon Master: [SYSTEM] Initiative pending. Usage: /init <1-20>', source)
        self.assertIn('[prefill:/init ] Dungeon Master: [SYSTEM] Initiative pending. Enter /init <1-20> to begin combat.', source)

    def test_initiative_lock_message_uses_readable_phase_text(self):
        """Initiative lock system message should use spaces instead of underscores."""
        source = self._load_combat_manager_source()
        self.assertIn("DM GROUP", source)
        self.assertIn("PC GROUP", source)
        self.assertIn("phase_label_display", source)
        self.assertIn("replace(\"_\", \" \")", source)

    def test_pc_group_winner_followup_prompt_exists(self):
        """PC-group initiative win should emit an immediate spoken turn prompt."""
        source = self._load_combat_manager_source()
        self.assertIn(
            "Dungeon Master: Your party has the initiative and strikes first, ",
            source
        )
        self.assertIn("what does {active_pc_name} do?", source)
        self.assertIn("active_pc_name = (", source)

    def test_fast_lane_skips_initial_scene_bootstrap_contract(self):
        """Fast-lane must skip initial scene bootstrap and defer narration until phase starts."""
        source = self._load_combat_manager_source()
        # Guard must exist to skip bootstrap in fast-lane
        self.assertIn("if not is_fast_lane:", source)
        guard_pos = source.find("if not is_fast_lane:")
        self.assertGreater(guard_pos, 0, "Missing non-fast-lane bootstrap guard")

        # Initial prompt bootstrap must live under this guard
        initial_prompt_pos = source.find('initial_prompt = f"""Dungeon Master Note:', guard_pos)
        self.assertGreater(
            initial_prompt_pos,
            guard_pos,
            "Initial prompt bootstrap must be inside if not is_fast_lane guard"
        )

        # Fast-lane path should explicitly log deferred narration contract
        self.assertIn(
            "COMBAT_INIT: Fast-lane startup complete; deferring narration until phase starts",
            source
        )

    def test_initiative_order_usage_stays_in_non_fast_lane_contract(self):
        """initiative_order assignment and usage must stay in non-fast-lane paths."""
        source = self._load_combat_manager_source()
        # Find the fast-lane block start
        fast_lane_start = source.find("if is_fast_lane:")
        self.assertGreater(fast_lane_start, 0, "if is_fast_lane block must exist")

        # Find the else branch that follows if is_fast_lane
        else_after_fast_lane = source.find("else:", fast_lane_start)
        self.assertGreater(else_after_fast_lane, fast_lane_start, "else branch after if is_fast_lane must exist")

        # Find where initiative_order is assigned
        assignment_pos = source.find("initiative_order = get_initiative_order(encounter_data)")
        self.assertGreater(assignment_pos, else_after_fast_lane, 
            "initiative_order assignment must be in the else branch after if is_fast_lane")

        # Find the if not is_fast_lane bootstrap guard
        bootstrap_guard = source.find("if not is_fast_lane:")
        self.assertGreater(bootstrap_guard, 0, "if not is_fast_lane guard must exist")

        # Find where initiative_order is used in initial prompt
        usage_pos = source.find("Initiative Order: {initiative_order}")
        self.assertGreater(usage_pos, bootstrap_guard, 
            "initiative_order usage must be inside if not is_fast_lane bootstrap block")


if __name__ == "__main__":
    unittest.main(verbosity=2)
