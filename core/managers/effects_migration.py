# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Automatic, campaign-atomic conversion from legacy effect bookkeeping."""

from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import glob
import json
import os
import re
import uuid

from core.effects.clock import (
    display_iso_from_scalar,
    scalar_from_calendar,
    scalar_from_display_iso,
)
from core.effects.effective import effective_sheet
from core.effects.lifecycle import exit_combat_effect
from core.effects.model import canonical_stat, normalize_effect, validate_effect
from core.managers.effects_state import (
    EFFECTS_STATE_PATH,
    campaign_effects_migrated,
    effects_state_transaction,
    load_effects_state,
)
from updates.save_game_manager import SaveGameManager
from utils.encoding_utils import safe_json_load
from utils.file_operations import safe_write_json
from utils.path_transaction_lock import path_transaction_lock


TRACKER_PATH = os.path.join("modules", "effects_tracker.json")
MIGRATION_GUARD_PATH = os.path.join("modules", "effects_migration")


class EffectsMigrationError(RuntimeError):
    """The legacy campaign could not be converted without guessing."""


def _normalized_name(value):
    text = str(value or "").strip().lower().replace(" ", "_").replace("'", "_")
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9_]", "_", text)).strip("_")


def _canonical_hash(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _legacy_now(world):
    """Frozen v1 calculation adapter used only to rebase tracker deadlines."""
    try:
        day = int((world or {}).get("day", 0))
        parts = str((world or {}).get("time", "00:00:00")).split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        second = int(parts[2]) if len(parts) > 2 else 0
    except (TypeError, ValueError, IndexError) as exc:
        raise EffectsMigrationError("legacy game time cannot be interpreted") from exc
    return datetime(2000, 1, 1) + timedelta(
        days=day, hours=hour, minutes=minute, seconds=second
    )


def _discover_character_files(party, tracker_names=None):
    module = str((party or {}).get("module") or "").replace(" ", "_")
    roots = ["characters"]
    if module:
        roots.append(os.path.join("modules", module, "characters"))
    tracker_names = {_normalized_name(name) for name in (tracker_names or [])}
    for candidate in glob.glob(os.path.join("modules", "*", "characters")):
        if candidate not in roots:
            roots.append(candidate)
    discovered = {}
    duplicates = {}
    for root in roots:
        if not os.path.isdir(root):
            continue
        for filename in sorted(os.listdir(root)):
            if (
                not filename.endswith(".json")
                or filename.endswith(("_BU.json", "_backup.json"))
                or ".backup_" in filename
                or filename.endswith(".backup_latest.json")
            ):
                continue
            path = os.path.join(root, filename)
            value = safe_json_load(path)
            if not isinstance(value, dict) or not value.get("name"):
                continue
            key = _normalized_name(value["name"])
            if root not in (
                "characters",
                os.path.join("modules", module, "characters"),
            ) and key not in tracker_names:
                continue
            if key in discovered and os.path.realpath(discovered[key]) != os.path.realpath(path):
                duplicates.setdefault(key, [discovered[key]]).append(path)
            else:
                discovered[key] = path
    return discovered, duplicates


def _load_tracker():
    if not os.path.exists(TRACKER_PATH):
        return {"version": "1.0", "characters": {}, "metadata": {}}
    value = safe_json_load(TRACKER_PATH)
    if not isinstance(value, dict) or not isinstance(value.get("characters"), dict):
        raise EffectsMigrationError("legacy effects tracker is malformed")
    return value


def _combat_migration_gate(party):
    active = (party.get("worldConditions") or {}).get("activeCombatEncounter")
    if active:
        return "active combat must reach a safe boundary"
    patterns = (
        os.path.join("modules", "encounters", "encounter_*.json"),
        os.path.join("modules", "*", "encounters", "encounter_*.json"),
    )
    for pattern in patterns:
        for path in glob.glob(pattern):
            encounter = safe_json_load(path)
            if not isinstance(encounter, dict):
                continue
            state = encounter.get("combatState") or {}
            if isinstance(state.get("pendingTurn"), dict):
                return "a combat turn transaction is pending"
            completion = state.get("completion") or {}
            if completion.get("status") not in (None, "active", "closed"):
                return "a combat completion transaction is unresolved"
            if completion.get("status") != "closed" and any(
                completion.get(field)
                for field in (
                    "rewardsApplied",
                    "summaryPublished",
                    "transcriptArchived",
                    "pendingRewards",
                )
            ):
                return "a combat completion transaction is unresolved"
    return None


def _effect_matches(effect, source):
    def label(value):
        normalized = re.sub(r"\s+", " ", str(value or "").strip().casefold())
        return re.sub(r"\s+(spell|effect|bonus|penalty)$", "", normalized)

    source_key = label(source)
    if not source_key or not isinstance(effect, dict):
        return False
    candidates = {
        label(effect.get("name")),
        label(effect.get("source")),
    }
    return source_key in candidates


def _legacy_effect_id(owner, effect, index):
    material = "%s|%s|%s|%d" % (
        owner,
        effect.get("name", ""),
        effect.get("source", ""),
        index,
    )
    return "LEGACY-%s" % hashlib.sha256(material.encode("utf-8")).hexdigest()[:20]


def _rebase_carried_expiration(effect, world, now_scalar, report):
    """Move every carried sheet deadline onto the V2 fantasy clock.

    T050 normally wrote fantasy-calendar ISO strings, while the old tracker
    used a neutral year-2000 calculation epoch. Weak models also occasionally
    emitted real-world or invalid dates. Only the first two representations
    can be converted without guessing; anything else becomes explicitly
    ``special`` instead of becoming silently permanent or expiring at once.
    """
    expiration = effect.get("expiration")
    if not isinstance(expiration, str) or not expiration.strip():
        return
    try:
        parsed = datetime.fromisoformat(expiration.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    current_year = int((world or {}).get("year", 1492))
    if parsed is not None and parsed.year == 2000:
        try:
            legacy_deadline = parsed.replace(tzinfo=None)
            remaining = max(
                0,
                int((legacy_deadline - _legacy_now(world)).total_seconds()),
            )
            effect["expiration"] = display_iso_from_scalar(now_scalar + remaining)
            effect.setdefault("durationKind", "minutes")
            report.append("year-2000 sheet deadline rebased onto game-time scalar")
            return
        except (EffectsMigrationError, OverflowError, ValueError):
            pass
    try:
        scalar_from_display_iso(expiration)
        valid_fantasy_deadline = parsed is not None and abs(parsed.year - current_year) <= 1
    except (TypeError, ValueError):
        valid_fantasy_deadline = False
    if valid_fantasy_deadline:
        effect.setdefault("durationKind", "minutes")
        return
    effect.pop("expiration", None)
    effect["durationKind"] = "special"
    effect["duration"] = str(effect.get("duration") or "legacy deadline needs review")
    report.append(
        "untrusted or invalid sheet deadline retained as special; expiry was not guessed"
    )


def _unbake_modifier(sheet, modifier, effect, report):
    stat = canonical_stat(modifier.get("stat"))
    value = modifier.get("value")
    if stat is None or type(value) is not int:
        raise EffectsMigrationError("tracker modifier has an unsupported stat/value")
    affects_max = modifier.get("affects_max") is True

    if stat == "hitPoints":
        # Current HP is a consumed resource, not a derived stat. Preserve its
        # present value. When an Aid-like maximum ends, lifecycle code clamps
        # current HP to the newly derived maximum; it never subtracts healing.
        if affects_max:
            stat = "maxHitPoints"
        else:
            report.append(
                "legacy current-HP-only modifier retained as display-only; "
                "resource arithmetic was not guessed"
            )
            return

    if stat in ("attackRolls", "damageRolls", "abilityChecks", "savingThrows", "initiative", "spellSaveDC", "spellAttackBonus") or stat.startswith(("savingThrow.", "abilityCheck.")):
        effect.setdefault("modifiers", []).append({"stat": stat, "value": value})
        return

    if stat.startswith("abilities."):
        ability = stat.split(".", 1)[1]
        abilities = sheet.get("abilities")
        if not isinstance(abilities, dict) or type(abilities.get(ability)) is not int:
            raise EffectsMigrationError("ability modifier has no numeric sheet target")
        new_value = abilities[ability] - value
        if new_value < 1:
            raise EffectsMigrationError("un-baking %s would produce an invalid ability" % stat)
        abilities[ability] = new_value
    else:
        if type(sheet.get(stat)) is not int:
            raise EffectsMigrationError("modifier %s has no numeric sheet target" % stat)
        new_value = sheet[stat] - value
        minimum = 1 if stat == "maxHitPoints" else 0
        if new_value < minimum:
            raise EffectsMigrationError("un-baking %s would violate its minimum" % stat)
        sheet[stat] = new_value
    effect.setdefault("modifiers", []).append({"stat": stat, "value": value})


def _rebase_duration(effect, modifier, world, now_scalar, report):
    duration_type = modifier.get("duration_type")
    duration_value = modifier.get("duration_value")
    expires_at = modifier.get("expires_at")
    if expires_at in ("short_rest", "long_rest") or duration_type == "until_rest":
        effect["durationKind"] = "until_rest"
        effect["restKind"] = expires_at if expires_at in ("short_rest", "long_rest") else duration_value
        effect["duration"] = "until %s" % str(effect.get("restKind", "rest")).replace("_", " ")
        return
    if expires_at == "special" or duration_type == "special":
        effect["durationKind"] = "special"
        effect["duration"] = str(duration_value or "special")
        return
    if isinstance(expires_at, str):
        try:
            legacy_deadline = datetime.fromisoformat(expires_at)
            if legacy_deadline.month != 1 or legacy_deadline.year != 2000:
                raise EffectsMigrationError("cross-month legacy deadline")
            remaining = max(
                0,
                int((legacy_deadline - _legacy_now(world)).total_seconds()),
            )
        except EffectsMigrationError:
            effect["durationKind"] = "special"
            effect["duration"] = str(duration_value or "legacy cross-month duration")
            report.append(
                "cross-month legacy deadline retained as special; remaining time was not guessed"
            )
            return
        except (TypeError, ValueError):
            remaining = None
        if remaining is not None:
            effect["expiration"] = display_iso_from_scalar(now_scalar + remaining)
            effect["durationKind"] = duration_type if duration_type in ("hours", "days") else "minutes"
            effect["duration"] = "%s %s" % (duration_value, duration_type or "legacy")
            report.append("legacy calculation deadline rebased onto game-time scalar")
            return
    effect["durationKind"] = "special"
    effect["duration"] = str(duration_value or "legacy duration")
    report.append("unreadable legacy deadline retained as special duration")


def _convert_sheet(owner, original, modifiers, world, migration_id):
    sheet = deepcopy(original)
    # Engine-authored effects can exist when an upgrade first resumes an
    # already-active agentic combat. Their files already store base values and
    # the current runtime renders their overlay even before the campaign stamp
    # exists, so preserve that actual visible view during conversion.
    report = []
    effects = []
    now_scalar = scalar_from_calendar(world)
    for index, current in enumerate(sheet.get("temporaryEffects", []) or []):
        if not isinstance(current, dict):
            report.append("non-object temporary effect dropped")
            continue
        converted = deepcopy(current)
        converted.setdefault("effectId", _legacy_effect_id(owner, converted, index))
        converted.setdefault("authoredBy", "legacy")
        if not isinstance(converted.get("description"), str) or not converted["description"].strip():
            label = str(converted.get("name") or converted.get("source") or "temporary effect").strip()
            converted["description"] = "Legacy effect carried forward: %s" % label
            report.append("missing legacy effect description replaced with a safe label")
        converted.setdefault("modifiers", [])
        converted.setdefault("conditions", [])
        converted.setdefault("created", {})["migrationId"] = migration_id
        rounds_remaining = converted.get("roundsRemaining")
        if (
            converted.get("durationKind") == "rounds"
            and type(rounds_remaining) is not int
        ):
            converted.pop("roundsRemaining", None)
            converted.pop("tickTrigger", None)
            converted.pop("expiration", None)
            converted["durationKind"] = "special"
            converted["duration"] = str(
                converted.get("duration")
                or "legacy round duration needs review"
            )
            report.append(
                "missing legacy round counter retained as special; expiry was not guessed"
            )
        elif rounds_remaining is not None:
            if type(rounds_remaining) is int:
                exited = exit_combat_effect(converted, now_scalar)
                if exited is None:
                    report.append(
                        "stale encounter/finished round effect removed at the safe boundary"
                    )
                    continue
                converted = exited
                report.append("stale round clock converted back to game time")
            else:
                converted.pop("roundsRemaining", None)
                converted.pop("tickTrigger", None)
                converted.pop("expiration", None)
                converted["durationKind"] = "special"
                converted["duration"] = str(
                    converted.get("duration") or "legacy round duration needs review"
                )
                report.append(
                    "invalid legacy round counter retained as special; expiry was not guessed"
                )
        else:
            _rebase_carried_expiration(
                converted,
                world,
                now_scalar,
                report,
            )
        effects.append(converted)
    # The only intentional visible migration change is removal of a stale
    # encounter effect at a proven no-combat boundary. Use the safely closed
    # carried set as the comparison view so all other arithmetic must remain
    # byte-for-byte equivalent.
    expected_original = deepcopy(original)
    expected_original["temporaryEffects"] = deepcopy(effects)
    original_visible = effective_sheet(expected_original)
    sheet["temporaryEffects"] = effects

    for index, modifier in enumerate(modifiers or []):
        if not isinstance(modifier, dict):
            raise EffectsMigrationError("tracker contains a non-object modifier")
        if modifier.get("reversal_state") == "in_progress":
            raise EffectsMigrationError("tracker contains an unresolved reversal claim")
        source = str(modifier.get("source") or "Legacy effect").strip()
        matching_effects = [item for item in effects if _effect_matches(item, source)]
        if len(matching_effects) > 1:
            raise EffectsMigrationError(
                "tracker modifier matches multiple sheet effects: %s" % source
            )
        effect = matching_effects[0] if matching_effects else None
        if effect is None:
            effect = {
                "effectId": "MIG-%s" % str(modifier.get("id") or "%s-%d" % (owner, index)),
                "name": source,
                "description": str(modifier.get("description") or source),
                "source": source,
                "authoredBy": "classifier",
                "modifiers": [],
                "conditions": [],
                "created": {"migrationId": migration_id},
            }
            effects.append(effect)
            report.append("tracker-only modifier materialized as an effect object")
        else:
            effect["authoredBy"] = "classifier"
            effect.setdefault("modifiers", [])
            effect.setdefault("conditions", [])
            effect.setdefault("created", {})["migrationId"] = migration_id
        _unbake_modifier(sheet, modifier, effect, report)
        _rebase_duration(effect, modifier, world, now_scalar, report)

    normalized_effects = []
    for effect in effects:
        normalized = normalize_effect(effect)
        problems = validate_effect(
            normalized,
            require_managed=normalized.get("authoredBy") in ("engine", "classifier"),
        )
        if problems:
            raise EffectsMigrationError("converted effect is invalid: %s" % "; ".join(problems))
        normalized_effects.append(normalized)
    sheet["temporaryEffects"] = normalized_effects
    sheet["effectsMigration"] = {"version": 2, "migrationId": migration_id}

    rendered = effective_sheet(sheet)
    for path in ("armorClass", "hitPoints", "maxHitPoints", "speed"):
        if (
            type(original_visible.get(path)) is int
            and rendered.get(path) != original_visible.get(path)
        ):
            raise EffectsMigrationError("migration changed visible %s" % path)
    for ability, before in (original_visible.get("abilities") or {}).items():
        if type(before) is int and (rendered.get("abilities") or {}).get(ability) != before:
            raise EffectsMigrationError("migration changed visible ability %s" % ability)
    return sheet, report


def preflight_effects_migration():
    party = safe_json_load("party_tracker.json")
    if not isinstance(party, dict) or not party.get("module"):
        return {"status": "not_ready", "reason": "campaign is not initialized"}
    if campaign_effects_migrated():
        return {"status": "already_migrated"}
    combat_gate = _combat_migration_gate(party)
    if combat_gate:
        return {"status": "deferred", "reason": combat_gate}

    tracker = _load_tracker()
    files, duplicates = _discover_character_files(
        party,
        (tracker.get("characters") or {}).keys(),
    )
    if duplicates:
        return {"status": "blocked", "refusals": ["duplicate character sheets: %s" % sorted(duplicates)]}
    migration_id = uuid.uuid4().hex
    conversions = []
    reports = []
    refusals = []
    world = party.get("worldConditions") or {}
    for owner, path in sorted(files.items()):
        original = safe_json_load(path)
        modifiers = ((tracker.get("characters") or {}).get(owner) or {}).get("modifiers", [])
        try:
            converted, sheet_report = _convert_sheet(
                owner, original, modifiers, world, migration_id
            )
            conversions.append(
                {
                    "owner": owner,
                    "path": path.replace("\\", "/"),
                    "beforeHash": _canonical_hash(original),
                    "afterHash": _canonical_hash(converted),
                    "converted": converted,
                }
            )
            reports.extend("%s: %s" % (owner, item) for item in sheet_report)
        except Exception as exc:
            refusals.append("%s: %s" % (owner, exc))
    missing = sorted(set((tracker.get("characters") or {})) - set(files))
    reports.extend("tracker entry without a sheet dropped: %s" % item for item in missing)
    return {
        "status": "ready" if not refusals else "blocked",
        "migrationId": migration_id,
        "party": party,
        "tracker": tracker,
        "conversions": conversions,
        "reports": reports,
        "refusals": refusals,
    }


def _create_backup():
    manager = SaveGameManager()
    before = {item.get("save_folder") for item in manager.list_save_games()}
    success, message = manager.create_save_game(
        "Automatic backup before Effects V2 conversion", "essential"
    )
    if not success:
        raise EffectsMigrationError("pre-migration save failed: %s" % message)
    after = manager.list_save_games()
    created = next((item for item in after if item.get("save_folder") not in before), None)
    if not created:
        raise EffectsMigrationError("pre-migration save could not be identified")
    return created.get("save_folder"), created.get("save_path")


def _retire_tracker(migration_id, backup_path):
    retired_tracker = {
        "version": "2.0",
        "retired": True,
        "characters": {},
        "metadata": {
            "description": "Derived effects now live on character sheets",
            "migrationId": migration_id,
            "legacyBackup": backup_path,
        },
    }
    if not safe_write_json(TRACKER_PATH, retired_tracker):
        raise EffectsMigrationError("could not retire the legacy effects tracker")


def _resume_applying_migration(state):
    migration = state.get("migration") or {}
    if migration.get("status") != "applying":
        return None
    migration_id = migration.get("migrationId")
    plan = migration.get("plan")
    if not migration_id or not isinstance(plan, list):
        raise EffectsMigrationError("incomplete migration journal is malformed")
    for record in plan:
        path = record.get("path")
        converted = record.get("converted")
        if not path or not isinstance(converted, dict):
            raise EffectsMigrationError("migration journal lacks converted sheet data")
        with path_transaction_lock(path, suffix=".effects.lock", timeout_seconds=5.0) as locked:
            if locked is None:
                raise EffectsMigrationError("timed out resuming %s" % record.get("owner"))
            current = safe_json_load(path)
            current_hash = _canonical_hash(current)
            if current_hash == record.get("beforeHash"):
                if not safe_write_json(path, converted):
                    raise EffectsMigrationError("could not resume %s" % record.get("owner"))
            elif current_hash != record.get("afterHash"):
                raise EffectsMigrationError(
                    "character diverged during migration: %s; restore automatic "
                    "backup '%s' before retrying"
                    % (record.get("owner"), migration.get("backupFolder"))
                )
        with effects_state_transaction() as current_state:
            current_migration = current_state.get("migration") or {}
            receipts = current_migration.setdefault("receipts", [])
            if record.get("afterHash") not in receipts:
                receipts.append(record.get("afterHash"))
    _retire_tracker(migration_id, migration.get("backupPath"))
    with effects_state_transaction() as current_state:
        current_migration = current_state.get("migration") or {}
        if len(current_migration.get("receipts", [])) != len(plan):
            raise EffectsMigrationError("resumed migration receipts are incomplete")
        current_migration["status"] = "complete"
        current_migration["completedAt"] = datetime.now().isoformat()
        current_migration["trackerRetired"] = True
        current_state["migration"] = current_migration
        current_state["pipelineMode"] = "declarative"
        current_state["schemaVersion"] = 2
    return {
        "status": "migrated",
        "migrationId": migration_id,
        "convertedSheets": len(plan),
        "reports": migration.get("reports", []),
        "backupFolder": migration.get("backupFolder"),
        "recovered": True,
    }


def run_effects_migration(create_backup=True):
    """Preflight, journal, convert, and stamp the whole campaign once."""
    os.makedirs("modules", exist_ok=True)
    with path_transaction_lock(
        MIGRATION_GUARD_PATH,
        suffix=".effects-migration.lock",
        timeout_seconds=30.0,
    ) as acquired:
        if acquired is None:
            return {"status": "deferred", "reason": "another migration is active"}
        if campaign_effects_migrated():
            return {"status": "already_migrated"}
        existing_state = load_effects_state()
        resumed = _resume_applying_migration(existing_state)
        if resumed is not None:
            return resumed
        preflight = preflight_effects_migration()
        if preflight.get("status") != "ready":
            if preflight.get("status") == "blocked":
                with effects_state_transaction() as state:
                    state["pipelineMode"] = "blocked"
                    state["migration"] = {
                        "status": "blocked",
                        "refusals": preflight.get("refusals", []),
                        "reports": preflight.get("reports", []),
                    }
            return preflight

        backup_folder = backup_path = None
        if create_backup:
            backup_folder, backup_path = _create_backup()
        migration_id = preflight["migrationId"]
        with effects_state_transaction() as state:
            state["pipelineMode"] = "unmigrated"
            state["migration"] = {
                "migrationId": migration_id,
                "status": "applying",
                "backupFolder": backup_folder,
                "backupPath": backup_path,
                "reports": preflight.get("reports", []),
                "receipts": [],
                "plan": [
                    {
                        key: record[key]
                        for key in ("owner", "path", "beforeHash", "afterHash", "converted")
                    }
                    for record in preflight["conversions"]
                ],
            }

        for record in preflight["conversions"]:
            path = record["path"]
            with path_transaction_lock(path, suffix=".effects.lock", timeout_seconds=5.0) as locked:
                if locked is None:
                    raise EffectsMigrationError("timed out converting %s" % record["owner"])
                current = safe_json_load(path)
                current_hash = _canonical_hash(current)
                if current_hash == record["beforeHash"]:
                    if not safe_write_json(path, record["converted"]):
                        raise EffectsMigrationError("could not convert %s" % record["owner"])
                elif current_hash != record["afterHash"]:
                    raise EffectsMigrationError(
                        "character changed during migration: %s; restore automatic "
                        "backup '%s' before retrying"
                        % (record["owner"], backup_folder)
                    )
            with effects_state_transaction() as state:
                migration = state.get("migration") or {}
                receipts = migration.setdefault("receipts", [])
                if record["afterHash"] not in receipts:
                    receipts.append(record["afterHash"])

        _retire_tracker(migration_id, backup_path)

        with effects_state_transaction() as state:
            migration = state.get("migration") or {}
            expected = len(preflight["conversions"])
            if len(migration.get("receipts", [])) != expected:
                raise EffectsMigrationError("migration receipts are incomplete")
            migration["status"] = "complete"
            migration["completedAt"] = datetime.now().isoformat()
            migration["trackerRetired"] = True
            state["migration"] = migration
            state["pipelineMode"] = "declarative"
            state["schemaVersion"] = 2
        return {
            "status": "migrated",
            "migrationId": migration_id,
            "convertedSheets": len(preflight["conversions"]),
            "reports": preflight.get("reports", []),
            "backupFolder": backup_folder,
        }
