# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Typed SRD 5.2.1 spell attack records (#672).

``data/srd_spell_attacks.json`` holds, for each reviewed spell, whether its
spell attack is melee or ranged, the damage kind and whether the spellcasting
ability modifier is added to the damage. A player's cast of a recorded spell
is asked for and scored by code like a plain melee swing (item 3): the d20,
then the damage dice on a hit. Every other spell keeps the model's ruling.

The records are hand-authored and reviewed against the SRD text, like the
#703 save records. Each one names its verified roll contract, which must
have exactly one d20 spell attack phase and one damage phase on a hit; the
contract gives the dice. A missing, stale or malformed file is never a
gameplay dependency: the lookup reports it and every spell keeps today's path.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from core.ai import srd_roll_contracts


ROOT = Path(__file__).resolve().parents[2]
ATTACKS_PATH = ROOT / "data" / "srd_spell_attacks.json"
ATTACK_KINDS = ("melee", "ranged")
DAMAGE_KINDS = (
    "acid", "bludgeoning", "cold", "fire", "force", "lightning", "necrotic",
    "piercing", "poison", "psychic", "radiant", "slashing", "thunder",
)
RECORD_FIELDS = {
    "name", "attack", "damageKind", "abilityModifierToDamage", "contractKey", "source", "_srd_attribution",
}


class SpellAttackDataError(ValueError):
    """The committed spell attack records are malformed or stale."""


def _player_phases(contract, purpose):
    return [
        phase for phase in (contract or {}).get("phases") or []
        if isinstance(phase, dict) and phase.get("playerRoll") and phase.get("purpose") == purpose
    ]


def _attack_phases(contract):
    """(attack phase, damage phase) of a contract shaped as one d20 spell
    attack and one damage roll on a hit, else (None, None)."""
    attacks = _player_phases(contract, "attack")
    damages = _player_phases(contract, "damage")
    if len(attacks) != 1 or len(damages) != 1:
        return None, None
    attack, damage = attacks[0], damages[0]
    if attack.get("baseDice") != {"count": 1, "sides": 20} or attack.get("modifier") != "spellAttackBonus":
        return None, None
    if damage.get("trigger") != "hit":
        return None, None
    return attack, damage


@lru_cache(maxsize=1)
def load_spell_attacks():
    document = json.loads(ATTACKS_PATH.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or set(document) != {"_metadata", "attacks"}:
        raise SpellAttackDataError("Spell attack records have an invalid shape")
    metadata, records = document.get("_metadata"), document.get("attacks")
    if not isinstance(metadata, dict) or not isinstance(records, dict):
        raise SpellAttackDataError("Spell attack record sections are invalid")
    if metadata.get("schemaVersion") != 1:
        raise SpellAttackDataError("Spell attack records have an unknown schemaVersion")
    if metadata.get("totalRecords") != len(records):
        raise SpellAttackDataError("Spell attack record count is stale")
    if not metadata.get("_srd_attribution"):
        raise SpellAttackDataError("Spell attack records lack SRD attribution")
    source_hash = hashlib.sha256(srd_roll_contracts.SPELL_REPOSITORY_PATH.read_bytes()).hexdigest()
    if metadata.get("sourceSha256") != source_hash:
        raise SpellAttackDataError("Spell attack records do not match the SRD repository")
    contracts = srd_roll_contracts.load_spell_roll_contracts().get("contracts") or {}
    for key, record in records.items():
        if not isinstance(record, dict) or set(record) != RECORD_FIELDS:
            raise SpellAttackDataError("%s has invalid fields" % key)
        if not record.get("_srd_attribution") or not str(record.get("source") or "").startswith("SRD 5.2.1 p."):
            raise SpellAttackDataError("%s lacks its SRD source or attribution" % key)
        if srd_roll_contracts._canonical_key(record.get("name")) != key:
            raise SpellAttackDataError("%s does not key its own name" % key)
        if record.get("attack") not in ATTACK_KINDS:
            raise SpellAttackDataError("%s has an invalid attack kind" % key)
        if record.get("damageKind") not in DAMAGE_KINDS:
            raise SpellAttackDataError("%s has an invalid damage kind" % key)
        # Schema 1 types the field; adding the modifier waits for a record
        # that needs it (Spiritual Weapon, #724), so only false is accepted.
        if record.get("abilityModifierToDamage") is not False:
            raise SpellAttackDataError("%s adds an ability modifier, which schema 1 does not score" % key)
        contract = contracts.get(record.get("contractKey"))
        if not isinstance(contract, dict) or contract.get("classification") != "verified":
            raise SpellAttackDataError("%s names no verified roll contract" % key)
        if _attack_phases(contract) == (None, None):
            raise SpellAttackDataError("%s's roll contract is not one spell attack and damage on a hit" % key)
    return document


def lookup(name):
    """(status, record, damage phase) for a spell name: ``recorded`` with the
    record and its contract's damage phase, ``unrecorded``, or
    ``data_unavailable`` (a missing or invalid file; every spell then keeps
    today's path)."""
    key = srd_roll_contracts._canonical_key(name)
    if not key:
        return "unrecorded", None, None
    try:
        records = load_spell_attacks()["attacks"]
        contracts = srd_roll_contracts.load_spell_roll_contracts().get("contracts") or {}
    except (OSError, TypeError, ValueError, srd_roll_contracts.SpellRollContractError):
        return "data_unavailable", None, None
    record = records.get(key)
    if not isinstance(record, dict):
        return "unrecorded", None, None
    return "recorded", dict(record), _attack_phases(contracts.get(record["contractKey"]))[1]


def damage_dice(phase, slot_level=None, character_level=None):
    """(count, sides) of the damage phase at this slot or character level, or None."""
    try:
        dice = srd_roll_contracts._scaled_dice(phase, slot_level, character_level)
    except (TypeError, ValueError, srd_roll_contracts.SpellRollContractError):
        return None
    return dice["count"], dice["sides"]
