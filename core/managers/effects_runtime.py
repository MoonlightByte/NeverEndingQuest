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
from core.effects.model import effect_identity
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
from utils.enhanced_logger import info, warning
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
    if not matches:
        raise EffectsRuntimeError("effect removal did not identify an active effect")
    # Several records of one name are the same effect (an earlier double
    # classification); ending it ends them all.
    return [
        {"op": "remove", "effectId": effect.get("effectId"), "name": effect.get("name")}
        for effect in matches
    ]


def update_character_with_effects(
    character_name,
    changes,
    party_tracker_data=None,
    action_context=None,
):
    """Classifier-first T078 -> T079 character update for a migrated campaign."""
    if not campaign_effects_migrated():
        # Explicit recovery fallback for campaigns whose automatic conversion
        # was blocked.  Normal converted campaigns never execute this path.
        success = update_character_info(
            character_name, changes, action_context=action_context
        )
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
            classifier = _lazy_classifier(resolved, changes, sheet, _world_scalar(party_tracker_data))
            success = _update_character_info_unlocked(
                resolved,
                changes,
                character_role=role,
                managed_effect_operation=classifier,
                action_context=action_context,
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


class _lazy_classifier:
    """T078 on demand: the T079 loop calls this with each parsed delta.

    The classifier runs only when the update model flagged an effect change
    ("effectChange": true) or answered with an empty delta (an effect-only
    change leaves T079 nothing else to say). One T078 result is kept across
    T079 reissues. A pure number change never pays for the classifier.
    """

    def __init__(self, character_name, changes, sheet, now_scalar):
        self._name = character_name
        self._changes = changes
        self._sheet = sheet
        self._now = now_scalar
        self.result = None
        self.operation = None
        self.skipped = False

    def __call__(self, updates, effect_flag):
        if self.result is None and (effect_flag is True or updates == {}):
            self.result = classify_effect(
                self._name, self._changes, effective_sheet(self._sheet), self._now
            )
            if self.result["operation"] == "add":
                self.operation = [{"op": "add", "effect": self.result["effect"]}]
            elif self.result["operation"] == "remove":
                self.operation = _remove_operation(self.result, self._sheet)
            self.skipped = False
        elif self.result is None:
            self.skipped = True
            info(
                f"T078 skipped for {self._name}: the update model reported no effect change",
                category="effects_tracking",
            )
        return self.operation


def _resolve_effect_reference(effects, *, effect_id=None, name=None):
    """Reconcile explicit structured identity without reading narrative prose."""
    candidates = [effect for effect in effects if isinstance(effect, dict)]
    if effect_id:
        id_matches = [
            effect
            for effect in candidates
            if effect.get("effectId") == effect_id
        ]
        if id_matches:
            if name and any(effect.get("name") != name for effect in id_matches):
                return []
            return id_matches
    if name:
        return [effect for effect in candidates if effect.get("name") == name]
    return []


def _condition_reference(sheet, *, effect_id=None, name=None):
    """The stated condition a removeEffect reference names, or None (typed values compared, no prose).

    A DM may end a grapple or a poisoning with removeEffect although a
    condition is a sheet fact, not a temporary effect; the structured intent
    is honoured by ending the condition the sheet actually states.
    """
    from core.nql import stats as nql_stats

    listed = [c for c in sheet.get("condition_affected") or [] if isinstance(c, str)]
    single = sheet.get("condition") if isinstance(sheet.get("condition"), str) else None
    stated = {c.casefold() for c in listed} | ({single.casefold()} if single and single != "none" else set())
    for reference in (effect_id, name):
        if isinstance(reference, str) and reference.strip().casefold() in stated:
            return reference.strip().casefold()
    return None


def _end_condition(sheet, condition):
    """The sheet with one stated condition ended; the engine's view (status, speed) refreshed."""
    from core.nql import stats as nql_stats

    updated = deepcopy(sheet)
    updated["condition_affected"] = [c for c in updated.get("condition_affected") or []
                                     if not (isinstance(c, str) and c.casefold() == condition)]
    if isinstance(updated.get("condition"), str) and updated["condition"].casefold() == condition:
        updated["condition"] = updated["condition_affected"][0] if updated["condition_affected"] else "none"
    problem = nql_stats.refresh(updated)
    if problem:
        warning(f"STATES: {sheet.get('name', '?')}: condition {condition!r} ended on the sheet; engine view not refreshed ({problem})",
                category="character_updates")
    else:
        info(f"STATES: {sheet.get('name', '?')}: removeEffect named the condition {condition!r}; ended on the sheet",
             category="character_updates")
    return updated


def remove_effect(character_name, *, effect_id=None, name=None, reason="removed"):
    """Deterministically remove one uniquely identified active effect."""
    if not campaign_effects_migrated():
        raise EffectsRuntimeError(
            "removeEffect is unavailable until the campaign effects conversion completes"
        )
    resolved, _role, path, sheet = _resolve_character(character_name)
    matches = _resolve_effect_reference(
        sheet.get("temporaryEffects", []) or [], effect_id=effect_id, name=name
    )
    condition = None if matches else _condition_reference(sheet, effect_id=effect_id, name=name)
    if not matches and condition is None:
        raise EffectsRuntimeError("removeEffect found no active effect to end")
    operations = [
        {"op": "remove", "effectId": item.get("effectId"), "name": item.get("name")}
        for item in matches
    ]
    with _get_character_update_lock(resolved):
        with path_transaction_lock(path, suffix=".effects.lock", timeout_seconds=5.0) as locked:
            if locked is None:
                raise EffectsRuntimeError("timed out removing effect")
            current = safe_json_load(path)
            if not isinstance(current, dict):
                raise EffectsRuntimeError("character sheet became unavailable")
            updated = _end_condition(current, condition) if condition else apply_effect_ops(current, operations)
            if not safe_write_json(path, updated):
                raise EffectsRuntimeError("effect removal could not be persisted")
    if condition:
        return {"owner": resolved, "effectId": condition, "name": condition, "reason": reason}
    effect = matches[0]
    return {
        "owner": resolved,
        "effectId": effect.get("effectId"),
        "name": effect.get("name"),
        "reason": reason,
    }


def prepare_remove_effect(character_name, *, effect_id=None, name=None, reason="removed"):
    """Freeze the exact sheet mutation for one v2 travel sibling."""
    if not campaign_effects_migrated():
        raise EffectsRuntimeError(
            "removeEffect is unavailable until the campaign effects conversion completes"
        )
    resolved, role, path, sheet = _resolve_character(character_name)
    matches = _resolve_effect_reference(
        sheet.get("temporaryEffects", []) or [], effect_id=effect_id, name=name
    )
    condition = None if matches else _condition_reference(sheet, effect_id=effect_id, name=name)
    if not matches and condition is None:
        raise EffectsRuntimeError("removeEffect found no active effect to end")
    operations = [
        {"op": "remove", "effectId": item.get("effectId"), "name": item.get("name")}
        for item in matches
    ]
    # The whole sheet is frozen: ending an effect also changes the numbers
    # the engine holds for it (armor class, maximum and current hit points).
    after = _end_condition(sheet, condition) if condition else apply_effect_ops(sheet, operations)
    effect = {"effectId": condition, "name": condition} if condition else matches[0]
    return {
        "kind": "removeEffect",
        "owner": resolved,
        "role": role,
        "path": path,
        "before": deepcopy(sheet),
        "after": after,
        "effectId": effect.get("effectId"),
        "name": effect.get("name"),
        "reason": reason,
    }


def prepare_character_update(character_name, changes, party_tracker_data=None):
    """Freeze required T078/T079 output and advisory sheet corrections."""
    resolved, role, _path, sheet = _resolve_character(character_name)
    classifier = _lazy_classifier(resolved, changes, sheet, _world_scalar(party_tracker_data))
    receipt = _update_character_info_unlocked(
        resolved,
        changes,
        character_role=role,
        managed_effect_operation=classifier,
        prepare_only=True,
        structural_reissue=True,
    )
    if not isinstance(receipt, dict):
        raise EffectsRuntimeError("required character proposal was not prepared")
    try:
        from core.validation.character_validator import AICharacterValidator

        validation = AICharacterValidator().validate_and_correct_character_smart_with_result(
            deepcopy(receipt["after"]), before=deepcopy(receipt["before"]), max_attempts=1
        )
        receipt["after"] = validation.data
        receipt["advisory_validation"] = {
            "status": "accepted" if validation.success else "fallback",
            "error": None if validation.success else str(validation.error or "unavailable"),
        }
    except Exception as exc:
        receipt["advisory_validation"] = {
            "status": "attempted_unavailable",
            "error": type(exc).__name__,
        }
    receipt["effect_proposal"] = classifier.result or {"operation": "none", "effect": {}, "remove": {}}
    return receipt


def apply_staged_character_update(receipt):
    """Apply or recognize one exact prepared character sheet."""
    with _get_character_update_lock(receipt["owner"], receipt.get("role")):
        with path_transaction_lock(
            receipt["path"], suffix=".effects.lock", timeout_seconds=30.0
        ) as locked:
            if locked is None:
                raise EffectsRuntimeError("character file is busy")
            current = safe_json_load(receipt["path"])
            if current == receipt["after"]:
                return "already_committed"
            if current != receipt["before"]:
                return "blocked_conflict"
            if not safe_write_json(receipt["path"], receipt["after"]):
                raise EffectsRuntimeError("character update could not be persisted")
    return "committed"


def apply_staged_remove_effect(receipt):
    """Apply or recognize a frozen exact removeEffect sheet value."""
    with _get_character_update_lock(receipt["owner"], receipt.get("role")):
        with path_transaction_lock(
            receipt["path"], suffix=".effects.lock", timeout_seconds=30.0
        ) as locked:
            if locked is None:
                raise EffectsRuntimeError("character effect file is busy")
            current = safe_json_load(receipt["path"])
            if not isinstance(current, dict):
                raise EffectsRuntimeError("character sheet became unavailable")
            if current == receipt["after"]:
                return "already_committed"
            if current != receipt["before"]:
                return "blocked_conflict"
            if not safe_write_json(receipt["path"], deepcopy(receipt["after"])):
                raise EffectsRuntimeError("effect removal could not be persisted")
    return "committed"


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
                    "text": plan.get("text")
                    or "%s: %s (%s)" % (plan.get("owner"), plan.get("name"), plan.get("reason")),
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


def _engine_expirations(sheets, now_scalar):
    """Remove plans for the owned timed effects the engine clock says are due.

    One ``advance time`` request over the party decides what ended (the
    engine's order and its ended_conditions record with the numbers each
    effect was giving). The removal itself goes through the outbox like any
    other expiry, so a crash between the decision and the write replays
    safely; the note text carries the engine's before/after numbers.
    """
    from core.nql import effects as nql_effects

    outcome = nql_effects.advance(sheets, now_scalar)
    if not outcome.ok:
        warning(
            "[Effects Engine] time advance left to the next turn: %s" % outcome.reason,
            category="effects_tracking",
        )
        return []
    plans = []
    for item in outcome.ended:
        effect = item.effect
        plans.append(
            {
                "owner": item.owner,
                "op": "remove",
                "effectId": effect.get("effectId"),
                "identity": effect_identity(effect),
                "name": effect.get("name"),
                "reason": "expired",
                "effect": deepcopy(effect),
                "text": nql_effects.ended_text(item, outcome.sheets.get(item.owner) or {}),
            }
        )
    return plans


def process_effect_lifecycle(conversation_history=None, rest_kind=None):
    """Apply due expirations/rest clears and return one exactly-once DM note."""
    if not campaign_effects_migrated():
        return None
    history = conversation_history if isinstance(conversation_history, list) else []
    party = safe_json_load("party_tracker.json") or {}
    sheets, paths = _party_sheets(party)
    now_scalar = _world_scalar(party)
    plans = plan_expirations(sheets, now_scalar)
    plans.extend(_engine_expirations(sheets, now_scalar))
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
