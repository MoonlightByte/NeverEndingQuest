# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Effects V2 runtime coordinator.

Models classify intent and propose mechanics.  Code owns identity, time,
application, removal, notification delivery, and crash-safe replay.
"""

from copy import deepcopy
import os

from core.ai.effects_agent import classify_effect
from core.effects.clock import scalar_from_calendar
from core.effects.effective import effective_sheet
from core.effects.lifecycle import apply_effect_ops, plan_expirations, plan_rest_clears
from core.effects.outbox import build_message, delivered_ids, notification_id
from core.managers.effects_state import (
    campaign_effects_migrated,
    effects_state_transaction,
    load_effects_state,
)
from updates.update_character_info import (
    _update_character_info_unlocked,
    _get_character_update_lock,
    detect_character_role,
    fuzzy_match_character_name,
    get_character_path,
    normalize_character_name,
    update_character_info,
)
from utils.encoding_utils import safe_json_load
from utils.file_operations import safe_write_json
from utils.path_transaction_lock import path_transaction_lock


class EffectsRuntimeError(RuntimeError):
    """A declarative effect operation could not be completed safely."""


def _resolve_character(character_name):
    party = safe_json_load("party_tracker.json") or {}
    resolved = character_name
    role = detect_character_role(resolved)
    path = get_character_path(resolved, role)
    if not os.path.exists(path):
        matched = fuzzy_match_character_name(resolved, party)
        resolved = matched or normalize_character_name(str(resolved))
        role = detect_character_role(resolved)
        path = get_character_path(resolved, role)
    sheet = safe_json_load(path)
    if not isinstance(sheet, dict):
        raise EffectsRuntimeError("character sheet could not be loaded")
    return resolved, role, path, sheet


def _world_scalar(party=None):
    party = party if isinstance(party, dict) else safe_json_load("party_tracker.json")
    if not isinstance(party, dict):
        raise EffectsRuntimeError("party tracker could not be loaded")
    return scalar_from_calendar(party.get("worldConditions") or {})


def _remove_operation(result, sheet):
    requested = result.get("remove") or {}
    requested_id = requested.get("effectId")
    requested_name = requested.get("name")
    matches = [
        effect
        for effect in sheet.get("temporaryEffects", []) or []
        if isinstance(effect, dict)
        and (
            (requested_id and effect.get("effectId") == requested_id)
            or (not requested_id and requested_name and effect.get("name") == requested_name)
        )
    ]
    if len(matches) != 1:
        raise EffectsRuntimeError("effect removal did not identify exactly one active effect")
    effect = matches[0]
    return {
        "op": "remove",
        "effectId": effect.get("effectId"),
        "name": effect.get("name"),
    }


def update_character_with_effects(character_name, changes, party_tracker_data=None):
    """Classifier-first T078 -> T079 character update for a migrated campaign."""
    if not campaign_effects_migrated():
        # Explicit recovery fallback for campaigns whose automatic conversion
        # was blocked.  Normal converted campaigns never execute this path.
        success = update_character_info(character_name, changes)
        if success:
            from updates.update_character_effects import update_character_effects

            update_character_effects(character_name, changes)
        return success

    resolved, role, path, _sheet = _resolve_character(character_name)
    with _get_character_update_lock(resolved, role):
        with path_transaction_lock(
            path,
            suffix=".effects.lock",
            timeout_seconds=30.0,
        ) as locked:
            if locked is None:
                raise EffectsRuntimeError("timed out acquiring the character effect lease")
            sheet = safe_json_load(path)
            if not isinstance(sheet, dict):
                raise EffectsRuntimeError("character sheet became unavailable")
            result = classify_effect(
                resolved,
                changes,
                effective_sheet(sheet),
                _world_scalar(party_tracker_data),
            )
            operation = None
            if result["operation"] == "add":
                operation = {"op": "add", "effect": result["effect"]}
            elif result["operation"] == "remove":
                operation = _remove_operation(result, sheet)
            success = _update_character_info_unlocked(
                resolved,
                changes,
                character_role=role,
                managed_effect_operation=operation,
            )
    if success:
        text = str(changes).lower()
        rest_kind = (
            "long_rest"
            if "long rest" in text
            else "short_rest"
            if "short rest" in text
            else None
        )
        if rest_kind:
            process_effect_lifecycle(rest_kind=rest_kind)
    return success


def remove_effect(character_name, *, effect_id=None, name=None, reason="removed"):
    """Deterministically remove one uniquely identified active effect."""
    if not campaign_effects_migrated():
        raise EffectsRuntimeError(
            "removeEffect is unavailable until the campaign effects conversion completes"
        )
    resolved, _role, path, sheet = _resolve_character(character_name)
    matches = [
        effect
        for effect in sheet.get("temporaryEffects", []) or []
        if isinstance(effect, dict)
        and (
            (effect_id and effect.get("effectId") == effect_id)
            or (not effect_id and name and effect.get("name") == name)
        )
    ]
    if len(matches) != 1:
        raise EffectsRuntimeError("removeEffect requires exactly one active match")
    effect = matches[0]
    operation = {
        "op": "remove",
        "effectId": effect.get("effectId"),
        "name": effect.get("name"),
    }
    with _get_character_update_lock(resolved):
        with path_transaction_lock(path, suffix=".effects.lock", timeout_seconds=5.0) as locked:
            if locked is None:
                raise EffectsRuntimeError("timed out removing effect")
            current = safe_json_load(path)
            if not isinstance(current, dict):
                raise EffectsRuntimeError("character sheet became unavailable")
            updated = apply_effect_ops(current, [operation])
            if not safe_write_json(path, updated):
                raise EffectsRuntimeError("effect removal could not be persisted")
    return {
        "owner": resolved,
        "effectId": effect.get("effectId"),
        "name": effect.get("name"),
        "reason": reason,
    }


def _party_sheets(party):
    sheets = {}
    paths = {}
    names = list(party.get("partyMembers", []) or [])
    names.extend(
        npc.get("name") for npc in party.get("partyNPCs", []) or [] if isinstance(npc, dict)
    )
    for name in names:
        try:
            resolved, _role, path, sheet = _resolve_character(name)
        except EffectsRuntimeError:
            continue
        sheets[resolved] = sheet
        paths[resolved] = path
    return sheets, paths


def _queue_expiration_records(plans):
    """Persist plans before sheet mutation; repeated calls are idempotent."""
    with effects_state_transaction() as state:
        outbox = state.setdefault("outbox", [])
        known = {record.get("notificationId") for record in outbox if isinstance(record, dict)}
        for plan in plans:
            notice_id = notification_id(
                plan.get("owner"),
                plan.get("effectId") or plan.get("name"),
                plan.get("reason"),
            )
            if notice_id in known:
                continue
            outbox.append(
                {
                    "notificationId": notice_id,
                    "status": "planned",
                    "owner": plan.get("owner"),
                    "path": plan.get("path"),
                    "operation": {
                        "op": "remove",
                        "effectId": plan.get("effectId"),
                        "identity": plan.get("identity"),
                        "name": plan.get("name"),
                    },
                    "text": "%s: %s (%s)"
                    % (plan.get("owner"), plan.get("name"), plan.get("reason")),
                }
            )
            known.add(notice_id)


def _apply_outbox_records(paths):
    state = load_effects_state()
    for record in state.get("outbox", []) or []:
        if not isinstance(record, dict) or record.get("status") in (
            "applied",
            "delivered",
        ):
            continue
        owner = record.get("owner")
        path = record.get("path") or paths.get(owner)
        if not path:
            try:
                _resolved, _role, path, _sheet = _resolve_character(owner)
            except EffectsRuntimeError:
                path = None
        if not path:
            continue
        with path_transaction_lock(path, suffix=".effects.lock", timeout_seconds=5.0) as locked:
            if locked is None:
                raise EffectsRuntimeError("timed out applying expiration")
            sheet = safe_json_load(path)
            if not isinstance(sheet, dict):
                raise EffectsRuntimeError("effect owner sheet became unavailable")
            updated = apply_effect_ops(sheet, [record.get("operation")])
            if not safe_write_json(path, updated):
                raise EffectsRuntimeError("expired effect could not be persisted")
        with effects_state_transaction() as current:
            for candidate in current.get("outbox", []) or []:
                if candidate.get("notificationId") == record.get("notificationId"):
                    candidate["status"] = "applied"


def process_effect_lifecycle(conversation_history=None, rest_kind=None):
    """Apply due expirations/rest clears and return one exactly-once DM note."""
    if not campaign_effects_migrated():
        return None
    history = conversation_history if isinstance(conversation_history, list) else []
    party = safe_json_load("party_tracker.json") or {}
    sheets, paths = _party_sheets(party)
    plans = plan_expirations(sheets, _world_scalar(party))
    if rest_kind in ("short_rest", "long_rest"):
        for owner, sheet in sheets.items():
            plans.extend(plan_rest_clears(owner, sheet, rest_kind))
    for plan in plans:
        if isinstance(plan, dict):
            plan["path"] = paths.get(plan.get("owner"))
    _queue_expiration_records(plans)
    _apply_outbox_records(paths)
    already_in_history = delivered_ids(history)
    state = load_effects_state()
    pending = [
        record
        for record in state.get("outbox", []) or []
        if record.get("status") == "applied"
        and record.get("notificationId") not in already_in_history
        and record.get("notificationId") not in state.get("deliveredNotifications", [])
    ]
    return build_message(pending)


def acknowledge_effect_notifications(conversation_history):
    """Acknowledge only notices proven durable in conversation history."""
    proven = delivered_ids(conversation_history)
    if not proven or not campaign_effects_migrated():
        return
    with effects_state_transaction() as state:
        delivered = state.setdefault("deliveredNotifications", [])
        for notice_id in sorted(proven):
            if notice_id not in delivered:
                delivered.append(notice_id)
        for record in state.get("outbox", []) or []:
            if record.get("notificationId") in proven:
                record["status"] = "delivered"
        # Delivered records cannot fire again: their effects are gone and a
        # restored older timeline brings its own manifest copy. Bound the live
        # manifest so long campaigns do not grow without limit.
        delivered_records = [
            record
            for record in state.get("outbox", []) or []
            if isinstance(record, dict) and record.get("status") == "delivered"
        ]
        retained_delivered = delivered_records[-200:]
        state["outbox"] = [
            record
            for record in state.get("outbox", []) or []
            if not isinstance(record, dict) or record.get("status") != "delivered"
        ] + retained_delivered
        state["deliveredNotifications"] = delivered[-1000:]
