"""Disposable real-Flask parity server with deterministic, synthetic game data.

This imports production routes and Socket.IO handlers. Only the data directory
and a test-only scenario HTTP endpoint are synthetic; neither UI is mocked.
"""
from __future__ import annotations

import argparse
from collections import deque
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
    # Keep both spellings because the legacy sheet reads savingThrows while
    # older generated character files used savingThrowProficiencies.
    "proficiencyBonus": 2,
    "savingThrows": ["strength", "dexterity"],
    "savingThrowProficiencies": ["strength", "dexterity"],
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


def npc(name: str, character_class: str, hp: int, maximum_hp: int, armor_class: int) -> dict:
    """Return a complete, deliberately non-empty NPC fixture."""
    return {
        **NPC,
        "name": name,
        "class": character_class,
        "hitPoints": hp,
        "maxHitPoints": maximum_hp,
        "armorClass": armor_class,
    }


PARTY_NPCS = [
    npc("Mira Thorne", "Druid", 19, 24, 14),
    npc("Dain Ashfall", "Fighter", 27, 31, 17),
    npc("Sable Reed", "Bard", 18, 22, 13),
]
LOCATION_NPCS = [
    npc("Keeper Sol", "Cleric", 21, 21, 16),
    npc("Pip Wren", "Rogue", 14, 17, 15),
]

# Extra records are opt-in scenario data.  Keeping them out of the baseline
# preserves the six-chip oracle used by the original parity suite while still
# letting the bounded suite exercise real horizontal overflow and image media.
OVERFLOW_LOCATION_NAMES = [
    "Aster Quill", "Bramble Fen", "Cinder Moss", "Dusk Rowan",
    "Ember Pike", "Fallow Reed", "Gale Thorn", "Hazel Vane",
    "Iris Wold", "Juniper Ash", "Kestrel Dew", "Linden Fox",
]
MEDIA_NPC = npc("Eirik Hearthwise", "Ranger", 24, 24, 15)


def baseline_tracker() -> dict:
    return {
        "module": "Parity_Expedition",
        "partyMembers": ["arden_vale"],
        "partyNPCs": [
            {"name": character["name"], "role": "Companion"}
            for character in PARTY_NPCS
        ],
        "worldConditions": {
            "year": 1492,
            "month": "Springmonth",
            "day": 3,
            "time": "14:20:00",
            "currentLocation": "Mosswatch Gate",
            "currentLocationId": "MG01",
            "currentArea": "Emerald March",
            "currentAreaId": "EM001",
            "activeCombatEncounter": "",
        },
    }


def baseline_messages() -> list[dict]:
    """Fill the 15-message production cache with stable, overflow-heavy text."""
    messages: list[dict] = []
    for index in range(7):
        messages.extend([
            {
                "type": "narration",
                "content": (
                    f"Watch {index + 1}: The green gate rises through the mist while "
                    "lantern light moves across moss-covered stones, old trail markers, "
                    "and the patient faces of the gathered company. The sentinel names "
                    "every landmark so this intentionally long chronicle wraps across "
                    "several lines without changing between captures."
                ),
                "message_id": f"fixture-narration-{index + 1}",
            },
            {
                "type": "user-input",
                "content": f"I inspect rune {index + 1}, then compare it with the map and ask the party what they remember.",
                "message_id": f"fixture-player-{index + 1}",
            },
        ])
    messages.append({
        "type": "narration",
        "content": "Mosswatch answers with a low silver bell. The road ahead is open.",
        "message_id": "fixture-narration-final",
    })
    return messages


def write_mutable_fixture(root: Path) -> None:
    """Reset every scenario-owned file without touching copied dependencies."""
    write_json(root / "party_tracker.json", baseline_tracker())
    write_json(
        root / "modules/Parity_Expedition/areas/EM001.json",
        {"locations": [{
            "locationId": "MG01",
            "npcs": [{"name": character["name"]} for character in LOCATION_NPCS],
        }]},
    )
    write_json(root / "modules/conversation_history/game_interface_cache.json", baseline_messages())


def make_fixture(root: Path) -> None:
    # Copy dependency inputs into the disposable fixture. Windows developer
    # accounts commonly lack symlink privileges, and a symlink would let a
    # mutating parity scenario touch the checked-out game data.
    for copied in ("schemas", "data"):
        shutil.copytree(REPO / copied, root / copied)
    # index() reads VERSION relative to the game directory. Without this copy
    # the legacy fixture silently rendered its fallback and parity compared two
    # different application versions.
    shutil.copy2(REPO / "VERSION", root / "VERSION")
    write_mutable_fixture(root)
    write_json(root / "characters/arden_vale.json", PLAYER)
    for character in PARTY_NPCS + LOCATION_NPCS:
        filename = character["name"].lower().replace(" ", "_") + ".json"
        write_json(root / f"characters/{filename}", character)
    write_json(root / "characters/eirik_hearthwise.json", MEDIA_NPC)
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
    overflow_creatures = [
        {"name": "Arden Vale", "type": "player", "initiative": 24, "status": "alive", "currentHitPoints": 31, "maxHitPoints": 38, "armorClass": 16},
        {"name": "Mira Thorne", "type": "npc", "initiative": 21, "status": "alive", "currentHitPoints": 19, "maxHitPoints": 24, "armorClass": 14},
    ]
    for index in range(18):
        overflow_creatures.append({
            "name": f"Briar Wolf {index + 1}",
            "type": "enemy",
            "monsterType": "wolf",
            "initiative": 19 - index,
            "status": "alive",
            "currentHitPoints": 11,
            "maxHitPoints": 11,
            "armorClass": 13,
        })
    write_json(root / "modules/encounters/encounter_PARITY-COMBAT-OVERFLOW.json", {
        "encounterId": "PARITY-COMBAT-OVERFLOW",
        "combat_round": 7,
        "creatures": overflow_creatures,
    })
    write_json(root / "player_storage.json", {"version": "1.0.0", "playerStorage": [{"id": "st1", "deviceName": "Oak Chest", "deviceType": "chest", "locationName": "Mosswatch Gate", "locationId": "MG01", "contents": [{"item_name": "Silvered Rope", "quantity": 2}], "createdBy": "Arden Vale", "lastAccessed": "1492-03-03"}]})
    write_json(root / "modules/Parity_Expedition/saved_games/save_20260717_120000/save_metadata.json", {"save_timestamp": "2026-07-17T12:00:00", "save_date_readable": "July 17, 2026 12:00", "save_mode": "essential", "module": "Parity Expedition", "description": "Before the briar fight", "game_state": {"current_location": "Mosswatch Gate"}})


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
    parity_game_thread = type("ParityGameThread", (), {"is_alive": lambda self: True})()
    web.game_thread = parity_game_thread

    # Provider controls are part of the visual parity surface, but a disposable
    # screenshot server must never read or write the developer's real secret
    # store. Keep the provider contract live while backing it with deterministic
    # in-memory values scoped to this process.
    import model_config
    parity_provider = {"value": "legacy"}
    model_config.get_provider = lambda: parity_provider["value"]
    model_config.set_provider = lambda value: parity_provider.__setitem__("value", value)
    model_config.persist_provider = lambda value: parity_provider.__setitem__("value", value)
    model_config.get_local_endpoint = lambda: {
        "base_url": "http://localhost:1234/v1",
        "model": "",
        "api_key": "not-needed",
    }
    model_config.has_openai_key = lambda: False
    model_config.has_gemini_key = lambda: False

    # Replace destructive/paid handlers inside this disposable process.  The
    # browser still performs the real user gesture and Socket.IO request, but
    # its deterministic response cannot start the game engine, call an image
    # model, probe a developer endpoint, pull git, install packages, or restart
    # the server.
    @web.socketio.on("start_game")
    def parity_start_game():
        web.startup_handoff_active = True
        web.startup_ready_emitted = False
        web.emit("startup_status", {
            "status": "in_progress",
            "phase": "Synchronizing the opening scene",
            "startupAttemptId": "parity-startup-attempt",
        })

    @web.socketio.on("generate_image")
    def parity_generate_image(data):
        web.emit("image_generated", {
            "image_url": "/static/media/environment/midday.jpg",
            "prompt": data.get("prompt", ""),
            "request_id": data.get("request_id"),
            "source_message_id": data.get("source_message_id"),
        })

    @web.socketio.on("test_local_endpoint")
    def parity_test_local_endpoint(_data):
        web.emit("local_endpoint_test_result", {
            "ok": True,
            "detail": "Connected. 2 model(s) available.",
        })

    @web.socketio.on("trigger_update")
    def parity_trigger_update():
        lines = [
            "Starting auto-update...",
            "Checking repository state...",
            "Validating frontend assets...",
        ]
        web._remember_ui_operation("update", {
            "status": "running", "log": lines, "error": None, "complete": None,
        })
        for line in lines:
            web.emit("update_log", {"message": line})

    # listSaves normally performs a filesystem-wide compatibility scan. That
    # work is useful in production, but it makes a visual fixture both slow and
    # dependent on unrelated files. Return the same complete metadata record
    # already written by make_fixture, through the real Socket.IO action path.
    from updates.save_game_manager import SaveGameManager
    SaveGameManager.list_save_games = lambda self: [{
        "save_folder": "save_20260717_120000",
        "save_timestamp": "2026-07-17T12:00:00",
        "save_date_readable": "July 17, 2026 12:00",
        "save_mode": "essential",
        "module": "Parity Expedition",
        "description": "Before the briar fight",
        "game_state": {"current_location": "Mosswatch Gate"},
    }]

    @web.app.post("/__parity__/scenario/<name>")
    def parity_scenario(name: str):
        tracker_path = fixture / "party_tracker.json"
        # Scenarios are isolated by default. A previous combat, restart, or
        # operation must never leak into a later screenshot pair.
        write_mutable_fixture(fixture)
        tracker = baseline_tracker()
        with web._ui_operation_lock:
            for operation in web._ui_operations:
                web._ui_operations[operation] = None
        with web.message_cache_lock:
            web.message_cache = deque(baseline_messages(), maxlen=web.MESSAGE_CACHE_SIZE)
        web.game_thread = parity_game_thread
        web.startup_handoff_active = False
        web.startup_ready_emitted = True
        parity_provider["value"] = "legacy"
        if name in {"pre-start", "bootstrap-loading", "startup-in-progress", "startup-failed"}:
            web.game_thread = None
            web.startup_ready_emitted = False
        if name in {"startup-in-progress", "startup-failed"}:
            web.startup_handoff_active = True
        if name == "combat-processing-overflow":
            tracker["worldConditions"]["activeCombatEncounter"] = "PARITY-COMBAT-OVERFLOW"
        else:
            tracker["worldConditions"]["activeCombatEncounter"] = "PARITY-COMBAT" if name.startswith("combat") else ""
        if name == "exploration-overflow":
            write_json(
                fixture / "modules/Parity_Expedition/areas/EM001.json",
                {"locations": [{"locationId": "MG01", "npcs": [
                    {"name": value}
                    for value in [*OVERFLOW_LOCATION_NAMES, MEDIA_NPC["name"]]
                ]}]},
            )
        if name == "media-image":
            write_json(
                fixture / "modules/Parity_Expedition/areas/EM001.json",
                {"locations": [{"locationId": "MG01", "npcs": [{"name": MEDIA_NPC["name"]}]}]},
            )
        if name == "server-instance-reset":
            web._server_instance_id = web.uuid4().hex
            web._ui_revision = 0
            tracker["worldConditions"]["currentLocation"] = "Restarted Watchtower"
        write_json(tracker_path, tracker)
        if name in {"processing", "combat-processing-overflow"}:
            from core.managers.status_manager import status_manager
            message = "Resolving twenty combatants..." if name == "combat-processing-overflow" else "The Dungeon Master is thinking..."
            status_manager.update_status(message, True)
        else:
            from core.managers.status_manager import status_manager
            # Reproduce the real failed-kickoff ordering: failure is published
            # before the later Ready status settles the visual controls. Both
            # clients therefore look enabled while their send handlers must
            # still reject commands until game_started is authoritative.
            if name == "startup-failed":
                web.socketio.emit("startup_status", {"status": "failed", "phase": "opening_scene", "startupAttemptId": "parity-startup-attempt"})
                web.socketio.emit("startup_recovery_response", {"status": "failed", "error": "Opening scene handoff timed out", "expectedStartupAttemptId": "parity-startup-attempt"})
            if name == "startup-input-ready":
                web.socketio.emit("startup_status", {"status": "in_progress", "phase": "Choose your character", "startupAttemptId": "parity-startup-attempt"})
            status_manager.update_status("Ready", name == "combat-enemy-turn")
        if name == "update":
            web.socketio.emit("version_status", {"update_available": True, "local_version": "0.3.5", "remote_version": "0.3.6", "message": "NeverEndingQuest 0.3.6 is available."})
        if name == "startup-in-progress":
            web.socketio.emit("startup_status", {"status": "in_progress", "phase": "Synchronizing the opening scene", "startupAttemptId": "parity-startup-attempt"})
        if name == "debug-overflow":
            web.socketio.emit("token_update", {"tpm": 4321, "rpm": 7, "total_tokens": 98765})
            for index in range(64):
                web.socketio.emit("debug_output", {
                    "type": "debug",
                    "timestamp": f"2026-07-18T14:20:{index:02d}Z",
                    "content": f"Deterministic diagnostic line {index + 1}: hydration and rendering checkpoint verified.",
                })
        if name == "journal-error":
            web.socketio.emit("plot_data_response", {"error": "Deterministic quest ledger failure"})
        if name == "update-complete":
            message = "Update complete! Server restarting..."
            web._remember_ui_operation("update", {"status": "complete", "log": ["Starting auto-update...", "Validating frontend assets..."], "error": None, "complete": message})
            web.socketio.emit("update_complete", {"message": message})
        if name == "compression":
            web._remember_ui_operation("compression", {"event": "compression_progress", "status": "running", "total_sections": 4, "completed": 2, "total": 4, "from_cache": False})
            web.socketio.emit("compression_start", {"total_sections": 4})
            web.socketio.emit("compression_progress", {"completed": 2, "total": 4, "from_cache": False})
        if name == "compression-complete":
            web._remember_ui_operation("compression", {"event": "compression_complete", "status": "complete", "reduction_percentage": 38, "original_size": 1000, "compressed_size": 620})
            web.socketio.emit("compression_complete", {"reduction_percentage": 38, "original_size": 1000, "compressed_size": 620})
        if name == "compression-error":
            web._remember_ui_operation("compression", {"event": "compression_error", "status": "failed", "error": "The chronicle archive is temporarily unavailable."})
            web.socketio.emit("compression_error", {"error": "The chronicle archive is temporarily unavailable."})
        if name == "module-progress":
            progress = {"build_id": "fixture-build", "stage": 4, "total_stages": 9, "stage_name": "Forging encounters", "percentage": 47, "message": "Balancing the dangers ahead...", "status": "running", "terminal": False}
            web._remember_ui_operation("module", progress)
            web.socketio.emit("module_creation_progress", progress)
        if name == "module-failed-progress":
            progress = {"build_id": "fixture-build-failed", "stage": 5, "total_stages": 9, "stage_name": "Tempering the adventure", "percentage": 58, "message": "Testing the forge...", "status": "running", "terminal": False}
            web._remember_ui_operation("module", progress)
            web.socketio.emit("module_creation_progress", progress)
        if name == "module-complete":
            progress = {"build_id": "fixture-build", "stage": 9, "total_stages": 9, "stage_name": "Adventure ready", "percentage": 100, "message": "The new module is ready.", "status": "published", "terminal": True, "success": True}
            web._remember_ui_operation("module", progress)
            web.socketio.emit("module_creation_progress", progress)
        if name == "module-failed":
            progress = {"build_id": "fixture-build-failed", "stage": 6, "total_stages": 9, "stage_name": "The forge has gone cold", "percentage": 63, "message": "Adventure forging failed safely.", "status": "failed", "terminal": True, "success": False, "error": "Deterministic fixture failure"}
            web._remember_ui_operation("module", progress)
            web.socketio.emit("module_creation_progress", progress)
        return {"ok": True, "scenario": name}

    web.socketio.run(web.app, host="127.0.0.1", port=args.port, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)


if __name__ == "__main__":
    main()
