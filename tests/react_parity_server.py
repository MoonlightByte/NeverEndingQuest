"""Disposable real-Flask parity server with deterministic, synthetic game data.

This imports production routes and Socket.IO handlers. Only the data directory
and a test-only scenario HTTP endpoint are synthetic; neither UI is mocked.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


PLAYER = {
    "name": "Arden Vale", "level": 4, "race": "Human", "class": "Ranger",
    "experience_points": 2700, "exp_required_for_next_level": 6500,
    "background": "Outlander", "alignment": "neutral good",
    "abilities": {"strength": 12, "dexterity": 18, "constitution": 14, "intelligence": 11, "wisdom": 16, "charisma": 10},
    "hitPoints": 31, "maxHitPoints": 38, "armorClass": 16, "initiative": 4,
    "proficiencyBonus": 2, "savingThrowProficiencies": ["strength", "dexterity"],
    "skills": ["Survival", "Perception", "Stealth"],
    "currency": {"gold": 42, "silver": 7, "copper": 3},
    "attacksAndSpellcasting": [{"name": "Longbow", "attackBonus": 6, "damageDice": "1d8", "damageBonus": 4, "description": "A weathered yew longbow."}],
    "ammunition": [{"name": "Arrows", "quantity": 34}],
    "equipment": [
        {"item_name": "Longbow", "item_type": "Weapon", "quantity": 1, "equipped": True, "description": "A weathered yew longbow."},
        {"item_name": "Potion of Healing", "item_type": "Potion", "quantity": 2, "consumable": True, "magical": True, "description": "Restores vitality."},
        {"item_name": "Scroll of Goodberry", "item_type": "Scroll", "quantity": 1, "consumable": True, "magical": True, "spellLevel": 1},
        {"item_name": "Moonlit Compass", "item_type": "Wondrous Item", "quantity": 1, "magical": True, "charges": {"current": 2, "max": 3}},
    ],
    "classFeatures": [{"name": "Favored Foe", "description": "Mark a foe.", "usage": {"current": 2, "max": 3, "refreshOn": "long rest"}}],
    "racialTraits": [{"name": "Versatile", "description": "Adaptable training."}],
    "backgroundFeature": {"name": "Wanderer", "description": "Excellent memory for maps."},
    "feats": [{"name": "Sharpshooter", "description": "Master of ranged attacks."}],
    "temporaryEffects": [{"name": "Blessed", "description": "Add 1d4 to attacks.", "duration": "3 rounds"}],
    "spellcasting": {"ability": "wisdom", "spellSaveDC": 13, "spellAttackBonus": 5, "spellSlots": {"level1": {"current": 2, "max": 3}}, "spells": {"level1": ["Goodberry", "Hunter's Mark"]}, "preparedSpells": ["Goodberry"]},
}

NPC = {
    **PLAYER, "name": "Mira Thorne", "race": "Half-Elf", "class": "Druid",
    "level": 3, "hitPoints": 19, "maxHitPoints": 24, "armorClass": 14,
    "currency": {"gold": 8, "silver": 4, "copper": 0},
    "savingThrows": ["Wisdom", "Charisma"],
    "skills": {"Nature": 5, "Medicine": 5, "Perception": 5},
    "status": "Wary", "conditions": ["Inspired"],
}


def make_fixture(root: Path) -> None:
    # Copy dependency inputs into the disposable fixture. Windows developer
    # accounts commonly lack symlink privileges, and a symlink would let a
    # mutating parity scenario touch the checked-out game data.
    for copied in ("schemas", "data"):
        shutil.copytree(REPO / copied, root / copied)
    tracker = {
        "module": "Parity_Expedition", "partyMembers": ["arden_vale"],
        "partyNPCs": [{"name": "Mira Thorne", "role": "Guide"}],
        "worldConditions": {
            "year": 1492, "month": "Springmonth", "day": 3, "time": "14:20:00",
            "currentLocation": "Mosswatch Gate", "currentLocationId": "MG01",
            "currentArea": "Emerald March", "currentAreaId": "EM001",
            "activeCombatEncounter": "",
        },
    }
    write_json(root / "party_tracker.json", tracker)
    write_json(root / "characters/arden_vale.json", PLAYER)
    write_json(root / "characters/mira_thorne.json", NPC)
    write_json(root / "modules/Parity_Expedition/areas/EM001.json", {"locations": [{"locationId": "MG01", "npcs": [{"name": "Keeper Sol"}]}]})
    write_json(root / "modules/Parity_Expedition/module_plot.json", {"plotPoints": [
        {"id": "q1", "title": "Open the Verdant Seal", "description": "Find three runes at Mosswatch.", "status": "in progress", "sideQuests": [{"id": "sq1", "title": "The Lost Satchel", "description": "Return Mira's herb satchel.", "status": "completed"}]},
        {"id": "q2", "title": "Defeat the Briar Warden", "description": "The old road is safe again.", "status": "completed"},
        {"id": "q3", "title": "Undiscovered", "description": "Hidden", "status": "not started"},
    ]})
    write_json(root / "modules/encounters/encounter_PARITY-COMBAT.json", {
        "encounterId": "PARITY-COMBAT", "combat_round": 2,
        "creatures": [
            {"name": "Arden Vale", "type": "player", "initiative": 18, "status": "alive", "currentHitPoints": 31, "maxHitPoints": 38, "armorClass": 16},
            {"name": "Mira Thorne", "type": "npc", "initiative": 14, "status": "alive", "currentHitPoints": 19, "maxHitPoints": 24, "armorClass": 14},
            {"name": "Briar Wolf", "type": "enemy", "monsterType": "wolf", "initiative": 9, "status": "alive", "currentHitPoints": 11, "maxHitPoints": 11, "armorClass": 13},
        ],
    })
    write_json(root / "player_storage.json", {"version": "1.0.0", "playerStorage": [{"id": "st1", "deviceName": "Oak Chest", "deviceType": "chest", "locationName": "Mosswatch Gate", "locationId": "MG01", "contents": [{"item_name": "Silvered Rope", "quantity": 2}], "createdBy": "Arden Vale", "lastAccessed": "1492-03-03"}]})
    write_json(root / "modules/Parity_Expedition/saved_games/save_20260717_120000/save_metadata.json", {"save_timestamp": "2026-07-17T12:00:00", "save_date_readable": "July 17, 2026 12:00", "save_mode": "essential", "module": "Parity Expedition", "description": "Before the briar fight", "game_state": {"current_location": "Mosswatch Gate"}})
    write_json(root / "modules/conversation_history/game_interface_cache.json", [
        {"type": "narration", "content": "The green gate rises through the mist.", "message_id": "fixture-1"},
        {"type": "user-input", "content": "I inspect the runes.", "message_id": "fixture-2"},
    ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8359)
    parser.add_argument("--fixture-dir")
    args = parser.parse_args()
    fixture = Path(args.fixture_dir) if args.fixture_dir else Path(tempfile.mkdtemp(prefix="neq-react-parity-"))
    if fixture.exists(): shutil.rmtree(fixture)
    fixture.mkdir(parents=True)
    make_fixture(fixture)

    import utils.version_checker as version_checker
    version_checker.check_for_updates = lambda silent=True: ("up_to_date", "0.3.5", "0.3.5", "NeverEndingQuest is up to date.")
    os.chdir(fixture)
    from web import web_interface as web
    web.game_thread = type("ParityGameThread", (), {"is_alive": lambda self: True})()

    @web.app.post("/__parity__/scenario/<name>")
    def parity_scenario(name: str):
        tracker_path = fixture / "party_tracker.json"
        tracker = json.loads(tracker_path.read_text(encoding="utf-8"))
        tracker["worldConditions"]["activeCombatEncounter"] = "PARITY-COMBAT" if name.startswith("combat") else ""
        if name == "server-instance-reset":
            web._server_instance_id = web.uuid4().hex
            web._ui_revision = 0
            tracker["worldConditions"]["currentLocation"] = "Restarted Watchtower"
        write_json(tracker_path, tracker)
        if name == "processing":
            from core.managers.status_manager import status_manager
            status_manager.update_status("The Dungeon Master is thinking...", True)
        else:
            from core.managers.status_manager import status_manager
            status_manager.update_status("Ready", name == "combat-enemy-turn")
        if name == "update":
            web.socketio.emit("version_status", {"update_available": True, "local_version": "0.3.5", "remote_version": "0.3.6", "message": "NeverEndingQuest 0.3.6 is available."})
        if name == "compression":
            web._remember_ui_operation("compression", {"event": "compression_progress", "status": "running", "total_sections": 4, "completed": 2, "total": 4, "from_cache": False})
            web.socketio.emit("compression_start", {"total_sections": 4})
            web.socketio.emit("compression_progress", {"completed": 2, "total": 4, "from_cache": False})
        if name == "compression-complete":
            web._remember_ui_operation("compression", {"event": "compression_complete", "status": "complete", "reduction_percentage": 38, "original_size": 1000, "compressed_size": 620})
            web.socketio.emit("compression_complete", {"reduction_percentage": 38, "original_size": 1000, "compressed_size": 620})
        if name == "module-progress":
            progress = {"build_id": "fixture-build", "stage": 4, "total_stages": 9, "stage_name": "Forging encounters", "percentage": 47, "message": "Balancing the dangers ahead...", "status": "running", "terminal": False}
            web._remember_ui_operation("module", progress)
            web.socketio.emit("module_creation_progress", progress)
        if name == "module-complete":
            progress = {"build_id": "fixture-build", "stage": 9, "total_stages": 9, "stage_name": "Adventure ready", "percentage": 100, "message": "The new module is ready.", "status": "published", "terminal": True, "success": True}
            web._remember_ui_operation("module", progress)
            web.socketio.emit("module_creation_progress", progress)
        return {"ok": True, "scenario": name}

    web.socketio.run(web.app, host="127.0.0.1", port=args.port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
