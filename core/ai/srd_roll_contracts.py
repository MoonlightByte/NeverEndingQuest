# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Verified-only SRD spell-roll request auditing for combat T096.

Only a manually reviewed ``verified`` contract may reject a model request.
Every missing, ambiguous, or ``no_player_roll`` entry remains playable and is
returned as an observable unchecked result. Numeric modifiers are deliberately
outside this contract; only dice count, sides, and level scaling are compared.
"""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

from core.ai.srd_reference import load_srd_reference_index, normalize_rule_name


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "data" / "srd_spell_roll_contracts.json"
SPELL_REPOSITORY_PATH = ROOT / "data" / "spell_repository.json"
_DICE_RE = re.compile(r"(?<![A-Za-z0-9])(\d*)d(4|6|8|10|12|20|100)(?![A-Za-z0-9])", re.I)


class SpellRollContractError(ValueError):
    """The committed SRD roll-contract data is malformed or stale."""


_SOURCE_LOGGED = set()
_UNAVAILABLE_LOGGED = set()


def _log_error(message):
    try:
        from utils.enhanced_logger import error as _error
        _error(message, category="combat_events")
    except Exception:
        pass


@lru_cache(maxsize=1)
def repository_sha256():
    """sha256 of data/spell_repository.json with CRLF line endings read as LF
    (#890: a Windows checkout may hold it CRLF; strict JSON has no raw line
    break inside a string, so only line endings change), or None when the
    file cannot be read."""
    try:
        raw = SPELL_REPOSITORY_PATH.read_bytes()
    except OSError:
        return None
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def check_source(table, metadata):
    """#890: a derived table records the repository it was generated from.
    A difference is a development-time freshness signal, logged once per
    table as an error; the typed records are still used (they do not read
    the repository at runtime). Never raises."""
    expected = metadata.get("sourceSha256") if isinstance(metadata, dict) else None
    actual = repository_sha256()
    if expected == actual or table in _SOURCE_LOGGED:
        return
    _SOURCE_LOGGED.add(table)
    _log_error(
        "SRD spell table %s was generated from repository %s but data/spell_repository.json is %s; "
        "the typed records are still used (regenerate the table)"
        % (table, str(expected)[:12], actual[:12] if actual else "unreadable"))


def log_unavailable(table, exc):
    """#890: one error per table per process when it cannot be loaded."""
    if table in _UNAVAILABLE_LOGGED:
        return
    _UNAVAILABLE_LOGGED.add(table)
    _log_error("SRD spell table %s could not be loaded (%s: %s); spells fall back to the model's rolls"
               % (table, type(exc).__name__, exc))


@lru_cache(maxsize=1)
def load_spell_roll_contracts():
    raw = CONTRACT_PATH.read_text(encoding="utf-8")
    document = json.loads(raw)
    if not isinstance(document, dict) or set(document) != {"_metadata", "contracts"}:
        raise SpellRollContractError("Spell-roll contracts have an invalid shape")
    metadata = document.get("_metadata")
    contracts = document.get("contracts")
    if not isinstance(metadata, dict) or not isinstance(contracts, dict):
        raise SpellRollContractError("Spell-roll contract sections are invalid")
    if metadata.get("totalSpells") != len(contracts):
        raise SpellRollContractError("Spell-roll contract count is stale")
    check_source("srd_spell_roll_contracts", metadata)
    if not metadata.get("_srd_attribution"):
        raise SpellRollContractError("Spell-roll contracts lack SRD attribution")
    for key, contract in contracts.items():
        if not isinstance(contract, dict) or not contract.get("_srd_attribution"):
            raise SpellRollContractError("%s lacks SRD attribution" % key)
        if contract.get("classification") not in {
            "verified", "ambiguous", "no_player_roll"
        }:
            raise SpellRollContractError("%s has an invalid classification" % key)
        if contract.get("classification") == "verified" and not isinstance(
            contract.get("phases"), list
        ):
            raise SpellRollContractError("%s has no verified phases" % key)
    return document


def _canonical_key(name):
    if not isinstance(name, str) or not name.strip():
        return None
    try:
        reference = load_srd_reference_index().reference(name)
    except Exception:
        reference = None
    if reference:
        return reference.get("key")
    return normalize_rule_name(name)


def _dice_expression(value):
    match = _DICE_RE.search(str(value or ""))
    if not match:
        return None
    return {
        "count": int(match.group(1) or 1),
        "sides": int(match.group(2)),
    }


def _format_dice(dice):
    return "%dd%d" % (dice["count"], dice["sides"])


def _scaled_dice(phase, slot_level=None, character_level=None):
    base = dict(phase.get("baseDice") or {})
    scaling = phase.get("scaling") or {}
    if scaling.get("kind") == "slot_level":
        base_level = int(scaling.get("baseLevel") or 0)
        used_level = int(slot_level or base_level)
        per_level = scaling.get("perLevel") or {}
        if used_level > base_level:
            if per_level.get("sides") != base.get("sides"):
                raise SpellRollContractError("Slot scaling changes die sides")
            base["count"] += (used_level - base_level) * int(
                per_level.get("count") or 0
            )
    elif scaling.get("kind") == "character_level":
        level = max(1, int(character_level or 1))
        choices = []
        for threshold, dice in (scaling.get("breakpoints") or {}).items():
            if str(threshold).isdigit() and int(threshold) <= level:
                choices.append((int(threshold), dice))
        if choices:
            base = dict(max(choices, key=lambda item: item[0])[1])
    if type(base.get("count")) is not int or type(base.get("sides")) is not int:
        raise SpellRollContractError("Verified spell phase has invalid dice")
    return base


# The sheet's spell slot keys (spellcasting.spellSlots): level1 .. level9.
_SLOT_KEY = re.compile(r"level([1-9])")


def _typed_slot_level(intent, request):
    """The typed slotLevel of the request, then of the intent, or None."""
    for source in (request, intent):
        value = source.get("slotLevel") if isinstance(source, dict) else None
        if type(value) is int and value > 0:
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    return None


def _spent_slot_level(intent, owner):
    """The level of the own spell slot the intent spends (#855, F4-Q3 A): a
    spellSlot resource of ``owner`` with an int delta below zero and a name
    in the sheet's key form. None when there is none, or when the spent own
    slots name different levels (F4-Q2 A)."""
    levels = set()
    for resource in (intent or {}).get("resources", []) or []:
        if (not isinstance(resource, dict) or resource.get("kind") != "spellSlot"
                or resource.get("owner") != owner or type(resource.get("delta")) is not int
                or resource["delta"] >= 0):
            continue
        match = _SLOT_KEY.fullmatch(str(resource.get("name") or ""))
        if match:
            levels.add(int(match.group(1)))
    return levels.pop() if len(levels) == 1 else None


def _slot_level(intent, request, owner=None):
    """The level a spell is scored at. With ``owner`` (the caster's sheet
    name) the slot it spends decides, then its typed slotLevel; with no
    owner, the typed slotLevel, then the first spellSlot resource named in
    the sheet's key form."""
    if owner is not None:
        spent = _spent_slot_level(intent, owner)
        return spent if spent is not None else _typed_slot_level(intent, request)
    typed = _typed_slot_level(intent, request)
    if typed is not None:
        return typed
    for resource in (intent or {}).get("resources", []) or []:
        if not isinstance(resource, dict) or resource.get("kind") != "spellSlot":
            continue
        match = _SLOT_KEY.fullmatch(str(resource.get("name") or ""))
        if match:
            return int(match.group(1))
    return None


def spell_base_level(intent):
    """#942: the level data/spell_repository.json types for the spell a cast
    intent names (its ``ability``, then ``spellName``), by the repository's
    canonical key; None for another action, a name the repository does not
    hold, or a cantrip."""
    if not isinstance(intent, dict) or intent.get("action") != "cast":
        return None
    for field in ("ability", "spellName"):
        name = intent.get(field)
        if not isinstance(name, str) or not name.strip():
            continue
        try:
            reference = load_srd_reference_index().reference(name)
        except Exception:
            reference = None
        if not reference or reference.get("kind") != "spell":
            continue
        level = (reference.get("entry") or {}).get("level")
        return level if type(level) is int and level > 0 else None
    return None


def slot_below_spell_level(intent, owner):
    """#942: the correction when the own slot a cast spends is below the
    spell's level (spell_base_level), or None. An unknown spell is never
    refused."""
    spent = _spent_slot_level(intent, owner)
    base = spell_base_level(intent) if spent is not None else None
    if base is None or spent >= base:
        return None
    return ("%s is a level %d spell: spend a level%d or higher slot; level%d is below it"
            % (intent.get("ability") or intent.get("spellName"), base, base, spent))


def slot_level_mismatch(intent, owner, sheet=None):
    """The correction when the intent spends an own slot and also types a
    different slotLevel (F4-Q3 A: the spent slot sets the level), or None.
    A higher slot is offered only when ``sheet`` still holds one."""
    spent = _spent_slot_level(intent, owner)
    if spent is None or not isinstance(intent, dict):
        return None
    request = intent.get("requiresPlayerInput")
    typed = _typed_slot_level(intent, request if isinstance(request, dict) else {})
    if typed is None or typed == spent:
        return None
    below = slot_below_spell_level(intent, owner)
    if below:
        # #942: never offer a slot level below the spell's own.
        return below
    message = ("slotLevel %d disagrees with the spent slot level%d: the slot spent sets the spell's level; "
               "send slotLevel %d" % (typed, spent, spent))
    slots = ((sheet or {}).get("spellcasting") or {}).get("spellSlots") if isinstance(sheet, dict) else None
    held = slots.get("level%d" % typed) if isinstance(slots, dict) else None
    if isinstance(held, dict) and type(held.get("current")) is int and held["current"] > 0:
        message += ", or spend a level%d slot" % typed
    return message


def _request_dice(request):
    """The request's typed die (#853); its prompt text is never read."""
    return _dice_expression((request or {}).get("die"))


def _select_phase(contract, request, actual, slot_level, character_level):
    phases = [phase for phase in contract.get("phases", []) if phase.get("playerRoll")]
    explicit = str((request or {}).get("phase") or "").strip()
    if explicit:
        return next((phase for phase in phases if phase.get("id") == explicit), None)
    if actual and actual.get("sides") == 20:
        attack = [phase for phase in phases if phase.get("purpose") == "attack"]
        if len(attack) == 1:
            return attack[0]
    if len(phases) == 1:
        return phases[0]
    if actual:
        matching = [
            phase
            for phase in phases
            if _scaled_dice(phase, slot_level, character_level) == actual
        ]
        if len(matching) == 1:
            return matching[0]
    return None


def audit_spell_roll_request(intent, actor_sheet=None, document=None):
    """Classify one T096 roll request; only verified dice drift can reject."""
    intent = intent if isinstance(intent, dict) else {}
    request = intent.get("requiresPlayerInput")
    if not isinstance(request, dict) or request.get("kind") != "roll":
        return {"status": "not_applicable"}
    spell_name = request.get("spellName") or intent.get("spellName") or intent.get("spell")
    key = _canonical_key(spell_name)
    try:
        contracts = (document or load_spell_roll_contracts()).get("contracts") or {}
    except (OSError, TypeError, ValueError, SpellRollContractError) as exc:
        log_unavailable("srd_spell_roll_contracts", exc)
        # Contract data is an advisory guard, never a gameplay dependency. A
        # stale/corrupt/missing generated sidecar must degrade to observable
        # unvalidated play instead of consuming the model correction budget.
        return {
            "status": "rules_contract_unavailable",
            "contractKey": key,
            "spellName": spell_name,
        }
    contract = contracts.get(key) if key else None
    if not isinstance(contract, dict):
        return {
            "status": "rules_drift_unchecked_no_profile",
            "contractKey": key,
            "spellName": spell_name,
        }
    classification = contract.get("classification")
    if classification == "ambiguous":
        return {
            "status": "rules_drift_unchecked_ambiguous",
            "contractKey": key,
            "spellName": contract.get("name"),
        }
    if classification != "verified":
        # ``no_player_roll`` means no typed profile, not that a creative ruling
        # is forbidden from requesting dice. It can never reject.
        return {
            "status": "rules_drift_unchecked_no_profile",
            "contractKey": key,
            "spellName": contract.get("name"),
        }
    actual = _request_dice(request)
    if actual is None:
        return {
            "status": "rules_drift_unchecked_ambiguous",
            "contractKey": key,
            "spellName": contract.get("name"),
            "reason": "No unambiguous requested dice expression was available.",
        }
    slot_level = _slot_level(intent, request, (actor_sheet or {}).get("name") or None)
    character_level = (actor_sheet or {}).get("level")
    try:
        phase = _select_phase(contract, request, actual, slot_level, character_level)
    except (TypeError, ValueError, SpellRollContractError):
        return {
            "status": "rules_contract_unavailable",
            "contractKey": key,
            "spellName": contract.get("name"),
        }
    if phase is None:
        return {
            "status": "rules_drift_unchecked_ambiguous",
            "contractKey": key,
            "spellName": contract.get("name"),
            "actual": _format_dice(actual),
            "reason": "The requested spell phase could not be identified safely.",
        }
    try:
        expected = _scaled_dice(phase, slot_level, character_level)
    except (TypeError, ValueError, SpellRollContractError):
        return {
            "status": "rules_contract_unavailable",
            "contractKey": key,
            "spellName": contract.get("name"),
        }
    result = {
        "status": "verified_match" if actual == expected else "rules_drift_reject",
        "contractKey": key,
        "spellName": contract.get("name"),
        "phase": phase.get("id"),
        "actual": _format_dice(actual),
        "expected": _format_dice(expected),
        "slotLevel": slot_level,
        "characterLevel": character_level,
        "source": contract.get("source"),
        "version": contract.get("version"),
        "guidance": (
            "%s %s uses %s. Validate dice count and sides only; do not infer "
            "or reject numeric modifiers."
            % (contract.get("name"), phase.get("id"), _format_dice(expected))
        ),
    }
    return {key: value for key, value in result.items() if value is not None}
