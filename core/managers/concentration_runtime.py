# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Concentration bookkeeping across the party (CN): code reconciles what the engine decides.

The caster's sheet carries one code-written ``concentration`` record
({"name", "group", "targets", "expiration"}); every effect record of that cast,
on whichever sheet, carries the same ``concentrationId``. The engine holds the
caster's instance, makes the Constitution save when damage lands and ends the
instance on a failed save or an incapacitating state (core/nql/concentration).
This module does the rest by typed-field comparison, never by reading prose:

- ``group_for``: the group a new concentration effect joins (the caster's
  current spell of the same name) or a fresh one.
- ``record_cast``: writes the caster's record; a different spell replaces the
  old one and ends it everywhere (SRD: one concentration spell at a time).
- ``end_group``: queues the removal of every effect of the group on every party
  sheet through the effects outbox (engine numbers restored, one DM notice,
  crash-safe) and clears the caster's record.
- ``sweep``: at the effect lifecycle, ends the group of a caster who became
  incapacitated and clears a record whose effects are all gone (fail forward).
"""
import uuid
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from core.nql import stats
from utils.enhanced_logger import info, warning
from utils.file_operations import safe_read_json, safe_write_json


def _records(sheet: Dict[str, Any], group: str) -> List[Dict[str, Any]]:
    return [e for e in sheet.get("temporaryEffects") or []
            if isinstance(e, dict) and e.get("concentrationId") == group and e.get("effectId")]


def _party() -> Tuple[Dict[str, Dict[str, Any]], Dict[str, str]]:
    from core.managers.effects_runtime import _party_sheets
    party = safe_read_json("party_tracker.json") or {}
    return _party_sheets(party)


def _caster_sheet(caster: str) -> Tuple[Optional[str], Optional[str], Optional[Dict[str, Any]]]:
    from core.managers.effects_runtime import EffectsRuntimeError, _resolve_character
    try:
        resolved, _role, path, sheet = _resolve_character(caster)
    except EffectsRuntimeError:
        return None, None, None
    return resolved, path, sheet


def group_for(caster: str, spell: str) -> str:
    """The caster's current group when they already concentrate on this spell (another target of one cast), else a new id."""
    _resolved, _path, sheet = _caster_sheet(caster)
    current = stats.concentration_of(sheet) if sheet else None
    if current and str(current.get("name", "")).casefold() == str(spell).casefold():
        return current["group"]
    return "CN-" + uuid.uuid4().hex[:12]


def record_cast(caster: str, spell: str, group: str, target: str, expiration: Optional[str]) -> None:
    """Write the caster's concentration record; a different spell replaces (and ends) the previous one."""
    from updates.update_character_info import _get_character_update_lock
    from utils.path_transaction_lock import path_transaction_lock

    resolved, path, sheet = _caster_sheet(caster)
    if not sheet:
        warning(f"CONCENTRATION: caster {caster!r} of {spell} has no sheet; the spell is tracked on the target only",
                category="effects_tracking")
        return
    previous = stats.concentration_of(sheet)
    if previous and previous["group"] != group:
        end_group(previous["group"], f"replaced by {spell}", skip_caster=resolved)
    with _get_character_update_lock(resolved):
        with path_transaction_lock(path, suffix=".effects.lock", timeout_seconds=5.0) as locked:
            if locked is None:
                warning(f"CONCENTRATION: could not lock {resolved}'s sheet to record {spell}", category="effects_tracking")
                return
            current = safe_read_json(path)
            if not isinstance(current, dict):
                return
            record = stats.concentration_of(current) if stats.concentration_of(current) and stats.concentration_of(current)["group"] == group else None
            targets = sorted(set((record or {}).get("targets") or []) | {target})
            current[stats.CONCENTRATION_FIELD] = {"name": spell, "group": group, "targets": targets,
                                                  "expiration": expiration if isinstance(expiration, str) else None}
            if not safe_write_json(path, current):
                warning(f"CONCENTRATION: {resolved}'s record for {spell} could not be saved", category="effects_tracking")
                return
    info(f"CONCENTRATION: {resolved} concentrates on {spell} (targets {', '.join(targets)}; the engine saves on damage)",
         category="effects_tracking")


def clear_record(sheet: Dict[str, Any], group: Optional[str] = None) -> bool:
    """Remove the concentration record from a sheet in memory (only the given group when one is named)."""
    current = stats.concentration_of(sheet)
    if current and (group is None or current["group"] == group):
        sheet.pop(stats.CONCENTRATION_FIELD, None)
        return True
    return False


def end_group(group: str, reason: str, *, skip_caster: Optional[str] = None,
              except_effect_id: Optional[str] = None) -> List[str]:
    """End every effect of the group on every party sheet (via the outbox) and clear the caster's record.

    ``skip_caster`` names a sheet the caller holds in memory and clears itself (its
    disk copy is not touched here). ``except_effect_id`` is a record the caller
    already removed. Returns the "<owner>: <name>" labels queued.
    """
    from core.effects.model import effect_identity
    from core.managers.effects_runtime import _queue_expiration_records
    from updates.update_character_info import _get_character_update_lock
    from utils.path_transaction_lock import path_transaction_lock

    sheets, paths = _party()
    plans = []
    labels: List[str] = []
    for owner, sheet in sheets.items():
        for effect in _records(sheet, group):
            if except_effect_id and effect.get("effectId") == except_effect_id:
                continue
            plans.append({"owner": owner, "op": "remove", "effectId": effect.get("effectId"),
                          "identity": effect_identity(effect), "name": effect.get("name"),
                          "reason": f"concentration:{group}", "path": paths.get(owner),
                          "text": f"{owner}: {effect.get('name')} ended ({reason})"})
            labels.append(f"{owner}: {effect.get('name')}")
        record = stats.concentration_of(sheet)
        if record and record["group"] == group and owner != skip_caster:
            path = paths.get(owner)
            with _get_character_update_lock(owner):
                with path_transaction_lock(path, suffix=".effects.lock", timeout_seconds=5.0) as locked:
                    current = safe_read_json(path) if locked is not None else None
                    if isinstance(current, dict) and clear_record(current, group):
                        safe_write_json(path, current)
    if plans:
        _queue_expiration_records(plans)
    info(f"CONCENTRATION: group {group} ended ({reason}); effects queued to end: {labels or 'none'}",
         category="effects_tracking")
    return labels


def sweep() -> List[str]:
    """Reconcile every caster's record with the party's sheets; returns what was ended or cleared."""
    out: List[str] = []
    sheets, _paths = _party()
    for owner, sheet in sheets.items():
        record = stats.concentration_of(sheet)
        if not record:
            continue
        blocked = stats.concentration_blocked(sheet)
        if blocked:
            end_group(record["group"], f"{owner} is {blocked}")
            out.append(f"{owner}: {record.get('name')} ended ({blocked})")
            continue
        if not any(_records(other, record["group"]) for other in sheets.values()):
            end_group(record["group"], "no effect of the spell remains")
            out.append(f"{owner}: {record.get('name')} record cleared")
    return out
