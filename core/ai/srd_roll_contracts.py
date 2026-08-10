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
    source_hash = hashlib.sha256(SPELL_REPOSITORY_PATH.read_bytes()).hexdigest()
    if metadata.get("sourceSha256") != source_hash:
        raise SpellRollContractError("Spell-roll contracts do not match the SRD repository")
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


def _slot_level(intent, request):
    for source in (request, intent):
        value = source.get("slotLevel") if isinstance(source, dict) else None
        if type(value) is int and value > 0:
            return value
        if isinstance(value, str) and value.strip().isdigit():
            return int(value.strip())
    for resource in (intent or {}).get("resources", []) or []:
        if not isinstance(resource, dict) or resource.get("kind") != "spellSlot":
            continue
        match = re.search(r"(\d+)", str(resource.get("name") or ""))
        if match:
            return int(match.group(1))
    return None


def _request_dice(request):
    prompt = str((request or {}).get("prompt") or "")
    structured = _dice_expression((request or {}).get("die"))
    # Existing weak-model repair law: an explicit spell/attack-roll prompt is
    # a d20 phase even when the nested die field accidentally names later damage.
    if re.search(r"\b(?:spell\s+attack|attack\s+roll)\b", prompt, re.I):
        return {"count": 1, "sides": 20}
    return structured or _dice_expression(prompt)


def _select_phase(contract, request, actual, slot_level, character_level):
    phases = [phase for phase in contract.get("phases", []) if phase.get("playerRoll")]
    explicit = str((request or {}).get("phase") or "").strip()
    if explicit:
        return next((phase for phase in phases if phase.get("id") == explicit), None)
    prompt = str((request or {}).get("prompt") or "").lower()
    if actual and actual.get("sides") == 20:
        attack = [phase for phase in phases if phase.get("purpose") == "attack"]
        if len(attack) == 1:
            return attack[0]
    for marker, phase_id in (
        ("later", "later_damage"),
        ("end of", "later_damage"),
        ("initial", "initial_damage"),
    ):
        if marker in prompt:
            selected = next((phase for phase in phases if phase.get("id") == phase_id), None)
            if selected:
                return selected
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
    except (OSError, TypeError, ValueError, SpellRollContractError):
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
    slot_level = _slot_level(intent, request)
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
