# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Typed SRD 5.2.1 effect rules for legacy effect records (#1442).

``data/srd_spell_effect_rules.json`` holds, for each reviewed spell, the typed
modifiers its effect carries today (Mage Armor: armorClass set 13 +
Dexterity, #1322). A record saved before that form existed has no modifiers;
``core/nql/legacy_effect_rules`` gives it these at load. A spell whose typed
form needs a choice the record never kept (Guidance: the skill, #1446) has
``choice`` in place of ``modifiers``: its record is reported, never filled
(D-KW-18). Each rule quotes the
SRD words it encodes (``evidence``), checked against the repository by the
rows, never read at runtime. A missing, stale or malformed file is never a
gameplay dependency: the lookup reports it and the record stays as saved.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from core.ai import srd_roll_contracts
from core.effects.model import normalize_modifier


ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = ROOT / "data" / "srd_spell_effect_rules.json"
RECORD_FIELDS = {"name", "modifiers", "evidence", "source", "_srd_attribution"}
CHOICE_FIELDS = {"name", "choice", "evidence", "source", "_srd_attribution"}
CHOICES = {"skill"}


class SpellEffectRuleDataError(ValueError):
    """The committed spell effect rules are malformed or stale."""


@lru_cache(maxsize=1)
def load_spell_effect_rules():
    document = json.loads(RULES_PATH.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or set(document) != {"_metadata", "rules"}:
        raise SpellEffectRuleDataError("Spell effect rules have an invalid shape")
    metadata, records = document.get("_metadata"), document.get("rules")
    if not isinstance(metadata, dict) or not isinstance(records, dict):
        raise SpellEffectRuleDataError("Spell effect rule sections are invalid")
    if metadata.get("schemaVersion") != 1:
        raise SpellEffectRuleDataError("Spell effect rules have an unknown schemaVersion")
    if metadata.get("totalRecords") != len(records):
        raise SpellEffectRuleDataError("Spell effect rule count is stale")
    if not metadata.get("_srd_attribution"):
        raise SpellEffectRuleDataError("Spell effect rules lack SRD attribution")
    srd_roll_contracts.check_source("srd_spell_effect_rules", metadata)
    for key, record in records.items():
        if not isinstance(record, dict) or set(record) not in (RECORD_FIELDS, CHOICE_FIELDS):
            raise SpellEffectRuleDataError("%s has invalid fields" % key)
        if not record.get("_srd_attribution") or not str(record.get("source") or "").startswith("SRD 5.2.1 "):
            raise SpellEffectRuleDataError("%s lacks its SRD source or attribution" % key)
        if srd_roll_contracts._canonical_key(record.get("name")) != key:
            raise SpellEffectRuleDataError("%s does not key its own name" % key)
        if not isinstance(record.get("evidence"), str) or not record["evidence"].strip():
            raise SpellEffectRuleDataError("%s quotes no SRD evidence" % key)
        if "choice" in record:
            if record["choice"] not in CHOICES:
                raise SpellEffectRuleDataError("%s names an unknown choice" % key)
            continue
        modifiers = record.get("modifiers")
        if not isinstance(modifiers, list) or not modifiers:
            raise SpellEffectRuleDataError("%s has no modifiers" % key)
        try:
            if [normalize_modifier(m) for m in modifiers] != modifiers:
                raise SpellEffectRuleDataError("%s modifiers are not in normal form" % key)
        except ValueError as exc:
            raise SpellEffectRuleDataError("%s has an invalid modifier: %s" % (key, exc)) from exc
    return document


def lookup(name):
    """(status, key, modifiers) for an effect name: ``recorded`` with the spell's key and a copy of
    its typed modifiers, ``needs_choice`` with the key and the choice its record never kept (in
    place of modifiers), ``unrecorded``, or ``data_unavailable`` (a missing or invalid file)."""
    key = srd_roll_contracts._canonical_key(name)
    if not key:
        return "unrecorded", None, None
    try:
        records = load_spell_effect_rules()["rules"]
    except (OSError, TypeError, ValueError) as exc:
        srd_roll_contracts.log_unavailable("srd_spell_effect_rules", exc)
        return "data_unavailable", None, None
    record = records.get(key)
    if not isinstance(record, dict):
        return "unrecorded", None, None
    if "choice" in record:
        return "needs_choice", key, record["choice"]
    return "recorded", key, json.loads(json.dumps(record["modifiers"]))
