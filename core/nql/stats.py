"""Character stats through the rules engine (E13a).

The sheet states facts: level, speed, the six ability scores, and which
saves, skills, expertise, features and feats the character has. Genesis
declares those facts and the SRD rules (core/nql/srd_stats.py); the engine
derives every total (proficiency, modifiers, checks, saves, skills,
initiative, passive perception, spell DC and attack). After any engine
request that returns the character's status, ``write_back`` stores the
engine's totals in the sheet fields the readers already use
(proficiencyBonus, initiative, senses.passivePerception, skills values,
spellcasting.spellSaveDC / spellAttackBonus). No model and no Python
arithmetic writes a derived total.

Expertise is a typed sheet field, ``expertise: ["Stealth"]``. A sheet
without it gets the list inferred once from a stored skill value equal to
the ability modifier plus twice the proficiency bonus (the only mark a
legacy sheet carries), and ``write_back`` stores the list so the inference
never runs again.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from core.nql import srd_stats

EXPERTISE_FIELD = "expertise"
DEFAULT_SPEED = 30

_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])")


def _q(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _int(value: Any) -> Optional[int]:
    return value if type(value) is int else None


def skill_id(name: Any) -> Optional[str]:
    """The engine skill id for a sheet skill name: 'Sleight of Hand', 'sleight_of_hand', 'sleightOfHand'."""
    if not isinstance(name, str):
        return None
    text = _CAMEL.sub("-", name.strip()).casefold()
    text = re.sub(r"[\s_]+", "-", text)
    return text if text in srd_stats.SKILLS else None


def ability_id(name: Any) -> Optional[str]:
    if not isinstance(name, str):
        return None
    text = name.strip().casefold()
    return text if text in srd_stats.ABILITIES else None


def _skill_items(sheet: Dict[str, Any]) -> List[Tuple[Any, Optional[int]]]:
    """(sheet key, stored bonus) for the skills field: dict of bonuses or a legacy list of names."""
    skills = sheet.get("skills")
    if isinstance(skills, dict):
        return [(key, _int(value)) for key, value in skills.items()]
    if isinstance(skills, list):
        return [(key, None) for key in skills]
    return []


def modifier(score: Any) -> int:
    value = _int(score)
    return (value - 10) // 2 if value is not None else 0


def proficiency_bonus(level: Any) -> int:
    value = _int(level)
    return (max(1, min(20, value)) + 7) // 4 if value is not None else 2


def expertise_of(sheet: Dict[str, Any]) -> Tuple[List[str], bool]:
    """(skill ids with expertise, inferred).

    The typed field wins when present. Otherwise a stored skill bonus equal to
    modifier + 2 x proficiency is the mark of expertise on a legacy sheet.
    """
    typed = sheet.get(EXPERTISE_FIELD)
    if isinstance(typed, list):
        return [sid for sid in (skill_id(x) for x in typed) if sid], False
    abilities = sheet.get("abilities") if isinstance(sheet.get("abilities"), dict) else {}
    pb = proficiency_bonus(sheet.get("level"))
    found: List[str] = []
    for key, bonus in _skill_items(sheet):
        sid = skill_id(key)
        if sid is None or bonus is None:
            continue
        expected = modifier(abilities.get(srd_stats.SKILLS[sid])) + 2 * pb
        if bonus == expected and sid not in found:
            found.append(sid)
    return found, True


def condition_types(sheet: Dict[str, Any], gaps: List[str]) -> List[str]:
    """The proficiency, expertise, feature and feat Condition types this sheet has, in world order."""
    cid = sheet.get("name", "")
    out: List[str] = []

    def add(kind: str) -> None:
        if kind not in out:
            out.append(kind)

    saves = sheet.get("savingThrows")
    for entry in saves if isinstance(saves, list) else []:
        aid = ability_id(entry)
        if aid is None:
            gaps.append(f"{cid}: savingThrows entry {entry!r} is not an ability; no proficiency declared")
            continue
        add("prof:save:" + aid)
    for key, _ in _skill_items(sheet):
        sid = skill_id(key)
        if sid is None:
            gaps.append(f"{cid}: skills entry {key!r} is not an SRD skill; no proficiency declared")
            continue
        add("prof:skill:" + sid)
    for sid in expertise_of(sheet)[0]:
        add("expertise:skill:" + sid)
    for feature in sheet.get("classFeatures") or []:
        name = feature.get("name") if isinstance(feature, dict) else feature
        kind = srd_stats.FEATURE_TYPES.get(str(name or "").strip().casefold())
        if kind:
            add(kind)
    for feat in sheet.get("feats") or []:
        name = feat.get("name") if isinstance(feat, dict) else feat
        kind = srd_stats.FEAT_TYPES.get(str(name or "").strip().casefold())
        if kind:
            add(kind)
    return [kind for kind in out if kind in srd_stats.CONDITION_TYPES]


def casting_ability(sheet: Dict[str, Any]) -> Optional[str]:
    casting = sheet.get("spellcasting")
    if not isinstance(casting, dict):
        return None
    return ability_id(casting.get("ability"))


def stat_lines(sheet: Dict[str, Any], gaps: List[str]) -> List[str]:
    """The fact and total declarations for one character block (dexterity and defense are declared by genesis)."""
    cid = sheet.get("name", "")
    abilities = sheet.get("abilities") if isinstance(sheet.get("abilities"), dict) else {}
    lines: List[str] = []
    for ability in srd_stats.ABILITIES:
        if ability == "dexterity":
            continue
        score = _int(abilities.get(ability))
        if score is None:
            gaps.append(f"{cid}: abilities.{ability} is not an integer; 10 declared")
            score = 10
        lines.append(f' stat {_q(ability)} = {score};')
    level = _int(sheet.get("level"))
    if level is None or level < 1:
        gaps.append(f"{cid}: level is not a positive integer; 1 declared")
        level = 1
    speed = _int(sheet.get("speed"))
    if speed is None:
        speed = DEFAULT_SPEED
    lines.append(f' stat "level" = {level}; stat "speed" = {speed};')
    lines.append(' stat "bonus:saves" = 0; stat "bonus:checks" = 0; stat "bonus:d20" = 0;')
    lines.append(' stat "proficiency" = 0;')
    for prefix in ("mod", "check", "save"):
        lines.append(" " + " ".join(f'stat "{prefix}:{a}" = 0;' for a in srd_stats.ABILITIES))
    skills = list(srd_stats.SKILLS)
    for start in range(0, len(skills), 6):
        lines.append(" " + " ".join(f'stat "skill:{s}" = 0;' for s in skills[start:start + 6]))
    lines.append(' stat "initiative" = 0; stat "passive:perception" = 10;')
    ability = casting_ability(sheet)
    if ability:
        lines.append(f' stat "spell-dc:{ability}" = 8; stat "spell-attack:{ability}" = 0;')
    return lines


def totals(status: Dict[str, Any]) -> Dict[str, int]:
    """stat id -> effective value from a status record (a list of stat records)."""
    out: Dict[str, int] = {}
    for record in status.get("stats") or []:
        if isinstance(record, dict) and isinstance(record.get("stat"), str) and type(record.get("effective")) is int:
            out[record["stat"]] = record["effective"]
    return out


def write_back(sheet: Dict[str, Any], status: Dict[str, Any]) -> List[str]:
    """Store the engine's totals on the sheet; return the fields whose value changed."""
    values = totals(status)
    if "proficiency" not in values:
        return []
    changes: List[str] = []
    if not isinstance(sheet.get(EXPERTISE_FIELD), list):
        # Inferred from the stored values before the engine's replace them.
        inferred, _ = expertise_of(sheet)
        sheet[EXPERTISE_FIELD] = [_display(sid) for sid in inferred]
        changes.append(f"{EXPERTISE_FIELD} inferred {sheet[EXPERTISE_FIELD]}")

    def put(container: Dict[str, Any], key: str, value: int, label: str) -> None:
        if container.get(key) != value:
            changes.append(f"{label} {container.get(key)!r} -> {value}")
            container[key] = value

    put(sheet, "proficiencyBonus", values["proficiency"], "proficiencyBonus")
    if "initiative" in values:
        put(sheet, "initiative", values["initiative"], "initiative")
    if "passive:perception" in values:
        senses = sheet.get("senses")
        if not isinstance(senses, dict):
            senses = {}
            sheet["senses"] = senses
        put(senses, "passivePerception", values["passive:perception"], "senses.passivePerception")
    skills = sheet.get("skills")
    if isinstance(skills, dict):
        for key in list(skills):
            sid = skill_id(key)
            if sid is not None and ("skill:" + sid) in values:
                put(skills, key, values["skill:" + sid], f"skills.{key}")
    ability = casting_ability(sheet)
    if ability and ("spell-dc:" + ability) in values:
        casting = sheet["spellcasting"]
        put(casting, "spellSaveDC", values["spell-dc:" + ability], "spellcasting.spellSaveDC")
        put(casting, "spellAttackBonus", values["spell-attack:" + ability], "spellcasting.spellAttackBonus")
    return changes


def _display(skill: str) -> str:
    """The schema's skill name for an engine skill id ('sleight-of-hand' -> 'Sleight of Hand')."""
    return " ".join(part if part == "of" else part.capitalize() for part in skill.split("-"))


def store(sheet: Dict[str, Any], status: Dict[str, Any]) -> List[str]:
    """write_back with a log line per changed field (the engine's totals correcting stored ones)."""
    changes = write_back(sheet, status)
    if changes:
        from utils.enhanced_logger import info
        info(f"STATS: {sheet.get('name', '?')}: " + "; ".join(changes), category="character_updates")
    return changes
