"""Offline regressions from the Airik/Kira phone walkthrough; no provider calls."""
import json
from unittest.mock import patch

from core.npc.actor_facts import actor_sheet_facts


def test_actor_facts_preserve_ownership_resources_and_unknowns():
    airik = {"hitPoints": 0, "condition_affected": ["Unconscious"],
             "equipment": [{"item_name": "Longsword", "quantity": 1, "equipped": False}],
             "classFeatures": [{"name": "Second Wind", "usage": {"current": 0, "max": 1}}],
             "secrets": "not player-facing equipment context"}
    facts = json.loads(actor_sheet_facts("Airik", airik))
    assert facts["owner"] == "Airik" and facts["hp"] == 0
    assert facts["equipment"][0]["item_name"] == "Longsword"
    assert facts["classFeatures"][0]["usage"]["current"] == 0
    assert "Shortbow" not in json.dumps(facts) and "secrets" not in facts
    assert "unknown" in actor_sheet_facts("Airik", None)
    assert json.loads(actor_sheet_facts("Airik", {}))["equipment"] == "unknown"


def test_actual_combat_packet_labels_airik_weapon_separately_from_kira(tmp_path):
    from core.npc.voice_context import build_combat_packets_for_window
    from core.npc.relationship_store import RelationshipStore

    encounter = {"encounterId": "test", "combatState": {"round": 1, "revision": 0},
                 "creatures": [{"name": "Airik", "type": "player", "combatantId": "p"},
                               {"name": "Kira", "type": "npc", "combatantId": "k"}]}
    sheets = {"Airik": {"equipment": [{"item_name": "Longsword", "quantity": 1}]},
              "Kira": {"name": "Kira", "hitPoints": 15, "maxHitPoints": 15,
                       "attacksAndSpellcasting": [{"name": "Shortbow"}]}}
    with patch("core.npc.profile_service.profile_for_packet_best_effort", return_value={}):
        packets = build_combat_packets_for_window(
            encounter_data=encounter, actor_ids=["k"], character_paths={"Airik": "airik.json", "Kira": "kira.json"},
            context_sheets=sheets, party_tracker_data={"module": "test", "partyNPCs": [{"name": "Kira"}]},
            location_info={}, player_input="What should I attack with?",
            relationship_store=RelationshipStore(tmp_path / "relationships.json"))
    assert len(packets) == 1
    packet = packets[0][1]
    assert "Shortbow" in packet["context"]["capabilities"]
    ally = json.loads(packet["context"]["allies"][0])
    assert ally["owner"] == "Airik"
    assert ally["equipment"][0]["item_name"] == "Longsword"
    assert "Shortbow" not in packet["context"]["allies"][0]


def test_postcombat_packet_exposes_zero_hp_and_actual_resources(tmp_path):
    from core.npc.voice_context import build_ooc_packet_for_turn
    from core.npc.relationship_store import RelationshipStore
    from types import SimpleNamespace

    sheets = {"Airik": {"name": "Airik", "hitPoints": 0, "equipment": [],
                        "condition_affected": ["Unconscious"]},
              "Kira": {"name": "Kira", "hitPoints": 15, "equipment": [{"item_name": "Shortbow", "quantity": 1}]}}
    with patch("core.npc.profile_service.profile_for_packet_best_effort", return_value={}):
        packet = build_ooc_packet_for_turn(
            party_tracker_data={"module": "test", "partyNPCs": [{"name": "Kira"}]},
            player_name="Airik", raw_input="Kira needs to heal me", location_data={}, conversation_prefix=[],
            path_manager=SimpleNamespace(get_character_path=lambda name: name), json_loader=sheets.get,
            relationship_store=RelationshipStore(tmp_path / "relationships.json"))
    context = packet["context"]["socialContext"]
    assert '"owner":"Airik"' in context and '"hp":0' in context
    assert '"owner":"Kira"' in context and '"Shortbow"' in context
    assert "potion" not in context.lower()
