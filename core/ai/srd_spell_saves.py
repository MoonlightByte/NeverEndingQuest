# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Typed SRD 5.2.1 spell save records (#703).

``data/srd_spell_saves.json`` holds, for each reviewed spell, the ability its
target saves with, what a successful save does to the damage (``half`` or
``none``) and the damage kind. Combat reads the record, never the model's
``save`` object, for a spell that has one; every other spell keeps today's
model-declared path.

The records are hand-authored and reviewed against the SRD text, like the
verified roll contracts. Each one names its roll contract, whose damage phase
gives the dice and whose ``trigger`` must agree with the record's effect. A
missing, stale or malformed file is never a gameplay dependency: the lookup
reports it and every spell keeps today's path.
"""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from core.ai import srd_roll_contracts


ROOT = Path(__file__).resolve().parents[2]
SAVES_PATH = ROOT / "data" / "srd_spell_saves.json"
ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
SUCCESS_EFFECTS = {"none": "failed_save", "half": "save_for_half"}
DAMAGE_KINDS = (
    "acid", "bludgeoning", "cold", "fire", "force", "lightning", "necrotic",
    "piercing", "poison", "psychic", "radiant", "slashing", "thunder",
)
RECORD_FIELDS = {"name", "save", "success", "damageKind", "contractKey", "source", "_srd_attribution"}


class SpellSaveDataError(ValueError):
    """The committed spell save records are malformed or stale."""


def _damage_phase(contract):
    phases = [
        phase for phase in (contract or {}).get("phases") or []
        if isinstance(phase, dict) and phase.get("playerRoll") and phase.get("purpose") == "damage"
    ]
    return phases[0] if len(phases) == 1 else None


@lru_cache(maxsize=1)
def load_spell_saves():
    document = json.loads(SAVES_PATH.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or set(document) != {"_metadata", "saves"}:
        raise SpellSaveDataError("Spell save records have an invalid shape")
    metadata, records = document.get("_metadata"), document.get("saves")
    if not isinstance(metadata, dict) or not isinstance(records, dict):
        raise SpellSaveDataError("Spell save record sections are invalid")
    if metadata.get("schemaVersion") != 1:
        raise SpellSaveDataError("Spell save records have an unknown schemaVersion")
    if metadata.get("totalRecords") != len(records):
        raise SpellSaveDataError("Spell save record count is stale")
    if not metadata.get("_srd_attribution"):
        raise SpellSaveDataError("Spell save records lack SRD attribution")
    source_hash = hashlib.sha256(srd_roll_contracts.SPELL_REPOSITORY_PATH.read_bytes()).hexdigest()
    if metadata.get("sourceSha256") != source_hash:
        raise SpellSaveDataError("Spell save records do not match the SRD repository")
    contracts = srd_roll_contracts.load_spell_roll_contracts().get("contracts") or {}
    for key, record in records.items():
        if not isinstance(record, dict) or set(record) != RECORD_FIELDS:
            raise SpellSaveDataError("%s has invalid fields" % key)
        if not record.get("_srd_attribution") or not str(record.get("source") or "").startswith("SRD 5.2.1 p."):
            raise SpellSaveDataError("%s lacks its SRD source or attribution" % key)
        if srd_roll_contracts._canonical_key(record.get("name")) != key:
            raise SpellSaveDataError("%s does not key its own name" % key)
        if record.get("save") not in ABILITIES:
            raise SpellSaveDataError("%s has an invalid save ability" % key)
        if record.get("success") not in SUCCESS_EFFECTS:
            raise SpellSaveDataError("%s has an invalid success effect" % key)
        if record.get("damageKind") not in DAMAGE_KINDS:
            raise SpellSaveDataError("%s has an invalid damage kind" % key)
        contract = contracts.get(record.get("contractKey"))
        if not isinstance(contract, dict) or contract.get("classification") != "verified":
            raise SpellSaveDataError("%s names no verified roll contract" % key)
        phase = _damage_phase(contract)
        if phase is None or phase.get("trigger") != SUCCESS_EFFECTS[record["success"]]:
            raise SpellSaveDataError("%s disagrees with its roll contract's damage trigger" % key)
    return document


def lookup(name):
    """(status, record, phase) for a spell name: ``recorded`` with the record
    and its contract's damage phase, ``unrecorded``, or ``data_unavailable``
    (a missing or invalid file; every spell then keeps today's path)."""
    key = srd_roll_contracts._canonical_key(name)
    if not key:
        return "unrecorded", None, None
    try:
        records = load_spell_saves()["saves"]
        contracts = srd_roll_contracts.load_spell_roll_contracts().get("contracts") or {}
    except (OSError, TypeError, ValueError, srd_roll_contracts.SpellRollContractError):
        return "data_unavailable", None, None
    record = records.get(key)
    if not isinstance(record, dict):
        return "unrecorded", None, None
    return "recorded", dict(record), _damage_phase(contracts.get(record["contractKey"]))


def damage_dice(phase, slot_level=None, character_level=None):
    """(count, sides) of the damage phase at this slot or character level, or None."""
    try:
        dice = srd_roll_contracts._scaled_dice(phase, slot_level, character_level)
    except (TypeError, ValueError, srd_roll_contracts.SpellRollContractError):
        return None
    return dice["count"], dice["sides"]
