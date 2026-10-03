# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Compact character evidence for the validation call (context views, C1).

The validator used to receive every party sheet as raw JSON (25-42 KB per
call, the largest block of the turn). This module renders the same stored
sheets as KEY=value lines, one fact per line, at about half the bytes:

- Stored values, never effective ones. The validator is told these are the
  committed pre-action sheets, and effects are listed beside them.
- Every fact the validator's instruction names survives: abilities,
  proficiencies, resources (current and max), equipment (name, quantity,
  equipped), effects (name and how each ends) and spell slots; so do
  identity, currency, features with their uses, attacks, spells, conditions,
  ammunition, concentration and typed armor.
- Item descriptions are kept only for items that are magical, carry effects
  or charges, or are consumable (potions, scrolls, wands, rods, staffs,
  rings, amulets). Plain rows keep name, quantity, type, equipped flag and
  catalog id. The engine nql_id is dropped: the validator never names items
  by id.
- Dropped: effect bookkeeping (effectId, created, onApply, onRemove,
  authoredBy, engine ticks, source combat ids), effectsMigration, the
  record's path, item _update and _remove markers, and JSON syntax.
- An unknown top-level key is never dropped silently: it renders as
  EXTRA_<key>=<json>.

The line grammar is the contract the kit's field-coverage control checks
(kit c1_harness.py); keep it when changing this file.
"""
import json
import re

HANDLED = {
    "name", "character_role", "character_type", "type", "size", "level", "race", "class", "subclass",
    "alignment", "background", "status", "condition", "condition_affected", "hitPoints", "maxHitPoints",
    "temporaryHitPoints", "armorClass", "initiative", "speed", "abilities", "savingThrows",
    "savingThrowBonuses", "skills", "expertise", "proficiencyBonus", "senses", "languages", "proficiencies",
    "damageVulnerabilities", "damageResistances", "damageImmunities", "conditionImmunities", "classFeatures",
    "racialTraits", "feats", "backgroundFeature", "attacksAndSpellcasting", "spellcasting", "equipment",
    "equipment_effects", "ammunition", "currency", "experience_points", "exp_required_for_next_level",
    "challengeRating", "exhaustion", "levelUpsPending", "deathSaves", "rollModes", "temporaryEffects",
    "concentration", "injuries", "acquisitions", "personality_traits", "ideals", "bonds", "flaws",
}
DROPPED = {"effectsMigration"}
DESCRIBED_SUBTYPES = {"potion", "scroll", "wand", "rod", "staff", "ring", "amulet"}


def one_line(value):
    """Whole text on one line: whitespace collapsed; nothing else changes."""
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def val(value):
    """A scalar as the grammar prints it (JSON spelling for null and booleans)."""
    if isinstance(value, bool) or value is None:
        return json.dumps(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return one_line(value)


def signed(value):
    return "%+d" % value if type(value) is int else val(value)


def joined(items):
    return "[" + ", ".join(val(x) for x in items or []) + "]"


def keyed(mapping):
    return ", ".join("%s:%s" % (k, val(v)) for k, v in (mapping or {}).items())


def described(row):
    """D2: does this equipment row keep its description?"""
    return bool(row.get("magical") is True or row.get("effects") or row.get("charges") is not None
                or row.get("consumable") is True or row.get("item_type") == "consumable"
                or row.get("item_subtype") in DESCRIBED_SUBTYPES)


def effect_text(effect):
    """One item effect: type target value, then its description."""
    return "%s %s %s: %s" % (val(effect.get("type")), val(effect.get("target")), val(effect.get("value")),
                             one_line(effect.get("description")))


def item_line(row):
    parts = ["ITEM=%s x%s" % (one_line(row.get("item_name") or row.get("name")), val(row.get("quantity", 1)))]
    kind = val(row.get("item_type"))
    if row.get("item_subtype"):
        kind += "/" + val(row["item_subtype"])
    parts.append("[%s]" % kind)
    if row.get("equipped") is True:
        parts.append("equipped")
    elif row.get("equipped") is False:
        parts.append("unequipped")
    for key, label in (("catalog_id", "catalog"), ("value", "value"), ("charges", "charges")):
        if key in row:
            parts.append("%s=%s" % (label, val(row[key])))
    if row.get("armor_category") is not None or row.get("ac_base") is not None:
        armor = "armor=%s base %s bonus %s" % (val(row.get("armor_category")), val(row.get("ac_base")),
                                               signed(row.get("ac_bonus", 0)))
        if "dex_limit" in row:
            armor += " dexlimit %s" % val(row.get("dex_limit"))
        if row.get("stealth_disadvantage") is True:
            armor += " stealth-disadvantage"
        parts.append(armor)
    for key in ("weapon_type", "attack_bonus", "damage"):
        if key in row:
            parts.append("%s=%s" % (key, val(row[key])))
    if row.get("magical") is True:
        parts.append("magical")
    if row.get("consumable") is True:
        parts.append("consumable")
    if row.get("effects"):
        parts.append("effects={%s}" % " | ".join(effect_text(e) for e in row["effects"]))
    line = " ".join(parts)
    if described(row) and one_line(row.get("description")):
        line += ": " + one_line(row.get("description"))
    return line


def effect_end(effect):
    """How a temporary effect ends, from its own fields."""
    for key, fmt in (("roundsRemaining", "%s rounds"), ("expiration", "until %s"), ("duration", "%s")):
        if effect.get(key) not in (None, ""):
            return fmt % one_line(effect[key])
    return "unrecorded"


def item_effect_sources(sheet):
    """(source, type, target, value) of every effect shown on an item line."""
    seen = set()
    for row in sheet.get("equipment") or []:
        if isinstance(row, dict):
            for e in row.get("effects") or []:
                if isinstance(e, dict):
                    seen.add((one_line(row.get("item_name")), val(e.get("type")), val(e.get("target")), val(e.get("value"))))
    return seen


def feature_line(key, feature):
    if not isinstance(feature, dict):
        return "%s=%s" % (key, one_line(feature))
    head = one_line(feature.get("name"))
    usage = feature.get("usage") if isinstance(feature.get("usage"), dict) else None
    if usage is None and ("current" in feature or "max" in feature):
        usage = {"current": feature.get("current"), "max": feature.get("max")}
    if usage is not None:
        head += " (uses %s/%s" % (val(usage.get("current")), val(usage.get("max")))
        if usage.get("refreshOn"):
            head += " per %s" % val(usage["refreshOn"])
        head += ")"
    if feature.get("source"):
        head += " [%s]" % one_line(feature["source"])
    desc = one_line(feature.get("description"))
    return "%s=%s%s" % (key, head, ": " + desc if desc else "")


def compact_sheet(sheet):
    s = sheet
    out = []
    out.append("CHAR=%s; ROLE=%s; TYPE=%s/%s; SIZE=%s; RACE=%s; CLASS=%s%s; LVL=%s; BG=%s; ALIGN=%s" % (
        val(s.get("name")), val(s.get("character_role")), val(s.get("character_type")), val(s.get("type")),
        val(s.get("size")), val(s.get("race")), val(s.get("class")),
        " (%s)" % val(s["subclass"]) if s.get("subclass") else "", val(s.get("level")),
        val(s.get("background")), val(s.get("alignment"))))
    out.append("STATUS=%s; CONDITION=%s; AFFECTED=%s; EXH=%s; DEATH_SAVES=%s; INJURIES=%s" % (
        val(s.get("status")), val(s.get("condition")), joined(s.get("condition_affected")),
        val(s.get("exhaustion", 0)), keyed(s.get("deathSaves")) or "none", joined(s.get("injuries"))))
    out.append("HP=%s/%s; TEMP_HP=%s; AC=%s; SPD=%s; INIT=%s; PROF=%s; XP=%s/%s; LEVELUPS=%s; CR=%s" % (
        val(s.get("hitPoints")), val(s.get("maxHitPoints")), val(s.get("temporaryHitPoints", 0)),
        val(s.get("armorClass")), val(s.get("speed")), signed(s.get("initiative")), signed(s.get("proficiencyBonus")),
        val(s.get("experience_points")), val(s.get("exp_required_for_next_level")),
        val(s.get("levelUpsPending", 0)), val(s.get("challengeRating"))))
    out.append("ABIL=" + keyed(s.get("abilities")))
    out.append("SAVES=prof %s; totals %s" % (joined(s.get("savingThrows")), keyed(s.get("savingThrowBonuses")) or "none"))
    skills = s.get("skills")
    out.append("SKILLS=" + (keyed(skills) if isinstance(skills, dict) else joined(skills)))
    out.append("EXPERTISE=" + joined(s.get("expertise")))
    out.append("SENSES=" + keyed(s.get("senses")))
    out.append("LANG=" + joined(s.get("languages")))
    prof = s.get("proficiencies") or {}
    out.append("PROF_ARMOR=%s; PROF_WEAPONS=%s; PROF_TOOLS=%s" % (
        joined(prof.get("armor")), joined(prof.get("weapons")), joined(prof.get("tools"))))
    out.append("RES=%s; VULN=%s; IMM=%s; COND_IMM=%s" % (
        joined(s.get("damageResistances")), joined(s.get("damageVulnerabilities")),
        joined(s.get("damageImmunities")), joined(s.get("conditionImmunities"))))
    if s.get("rollModes"):
        out.append("MODES=" + keyed(s["rollModes"]))
    out.append("CURRENCY=" + keyed(s.get("currency")))
    sc = s.get("spellcasting") if isinstance(s.get("spellcasting"), dict) else {}
    if sc:
        out.append("SPELLCAST=ability:%s, DC:%s, ATK:%s" % (val(sc.get("ability")), val(sc.get("spellSaveDC")),
                                                          signed(sc.get("spellAttackBonus"))))
        slots = sc.get("spellSlots") or {}
        out.append("SLOTS=" + ", ".join("%s:%s/%s" % (k, val(v.get("current")), val(v.get("max")))
                                        for k, v in slots.items() if isinstance(v, dict) and (v.get("max") or v.get("current"))))
        out.append("SPELLS=" + "; ".join("%s:%s" % (k, joined(v)) for k, v in (sc.get("spells") or {}).items() if v))
        if sc.get("preparedSpells"):
            out.append("PREPARED=" + joined(sc["preparedSpells"]))
        for k in sc:
            if k not in ("ability", "spellSaveDC", "spellAttackBonus", "spellSlots", "spells", "preparedSpells"):
                out.append("SPELLCAST_%s=%s" % (k, val(sc[k])))
    for f in s.get("classFeatures") or []:
        out.append(feature_line("FEATURE", f))
    for f in s.get("racialTraits") or []:
        out.append(feature_line("TRAIT", f))
    for f in s.get("feats") or []:
        out.append(feature_line("FEAT", f))
    if s.get("backgroundFeature"):
        out.append(feature_line("BG_FEATURE", s["backgroundFeature"]))
    for a in s.get("attacksAndSpellcasting") or []:
        line = "ATTACK=%s: %s to hit, %s%s %s, %s" % (
            one_line(a.get("name")), signed(a.get("attackBonus")), val(a.get("damageDice")),
            signed(a.get("damageBonus")) if a.get("damageBonus") else "", val(a.get("damageType")), val(a.get("type")))
        for k in ("lastAttackRoll", "lastAttackHit"):
            if k in a:
                line += "; %s=%s" % (k, val(a[k]))
        out.append(line)
    for row in s.get("equipment") or []:
        if isinstance(row, dict):
            out.append(item_line(row))
        else:
            out.append("ITEM=%s x1 [untyped]" % one_line(row))
    shown = item_effect_sources(s)
    for e in s.get("equipment_effects") or []:
        if isinstance(e, dict) and (one_line(e.get("source")), val(e.get("type")), val(e.get("target")), val(e.get("value"))) not in shown:
            out.append("ITEM_EFFECT=%s: %s" % (one_line(e.get("source")), effect_text(e)))
    for a in s.get("ammunition") or []:
        line = "AMMO=%s x%s" % (one_line(a.get("name")), val(a.get("quantity")))
        if "recoverable" in a:
            line += " recoverable=%s" % val(a["recoverable"])
        out.append(line)
    for e in s.get("temporaryEffects") or []:
        if not isinstance(e, dict):
            continue
        line = "EFFECT=%s; ends %s" % (one_line(e.get("name")), effect_end(e))
        if e.get("source"):
            line += "; source %s" % one_line(e["source"])
        if e.get("modifiers"):
            line += "; modifiers %s" % ", ".join("%s %s" % (val(m.get("stat")), signed(m.get("value")))
                                                 for m in e["modifiers"] if isinstance(m, dict))
        if e.get("conditions"):
            line += "; conditions %s" % joined(e["conditions"])
        if e.get("incapacitates") is True:
            line += "; incapacitates"
        if e.get("concentration") is True:
            line += "; concentration"
        if e.get("engineOwned") is True:
            line += "; engine-owned"
        if one_line(e.get("description")):
            line += ": " + one_line(e.get("description"))
        out.append(line)
    c = s.get("concentration")
    if isinstance(c, dict) and c.get("name"):
        out.append("CONC=%s; targets %s; ends %s" % (one_line(c["name"]), joined(c.get("targets")),
                                                   val(c.get("expiration")) if c.get("expiration") else "unrecorded"))
    for a in s.get("acquisitions") or []:
        if isinstance(a, dict):
            out.append("ACQUIRED=%s" % one_line(a.get("message")))
    for k, label in (("personality_traits", "TRAITS"), ("ideals", "IDEALS"), ("bonds", "BONDS"), ("flaws", "FLAWS")):
        if s.get(k):
            out.append("%s=%s" % (label, one_line(s[k])))
    for k in s:
        if k not in HANDLED and k not in DROPPED:
            out.append("EXTRA_%s=%s" % (k, val(s[k])))
    return "\n".join(out)


LEGEND = ("Compact sheet format: one KEY=value line per fact; ITEM lines are name xquantity [type/subtype], "
          "equipped or unequipped when recorded, catalog id, typed armor and effects; an item description follows a colon "
          "only for magical, effect-bearing, charged or consumable items. SLOTS are level:current/max. "
          "EFFECT lines give how each effect ends. Values are the stored sheet's, before effects.")


def compact_records(records):
    """The validation block's payload: one section per record, in order."""
    out = [LEGEND]
    for rec in records:
        if rec.get("status") == "available" and isinstance(rec.get("sheet"), dict):
            out.append("== RECORD %s (available)\n%s" % (one_line(rec.get("name")), compact_sheet(rec["sheet"])))
        else:
            out.append("== RECORD %s (%s; reason %s)" % (one_line(rec.get("name")), val(rec.get("status")),
                                                        val(rec.get("reason"))))
    return "\n".join(out)


