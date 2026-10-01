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

SRD conditions (C1a): the sheet's ``condition_affected`` list (and ``condition``)
states which conditions a character has; genesis declares one ``state:<name>``
instance per entry. Unconscious at 0 hit points is the engine's own (held while
hp is at its minimum, ended by healing), so it is never declared from the sheet
then, and ``write_back`` copies the engine's view back: the list, the primary
condition, and ``status`` unconscious/alive. ``dead`` stays the DM's word.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from core.nql import srd_stats

EXPERTISE_FIELD = "expertise"
STATE_FIELDS = ("status", "condition", "condition_affected")
EXHAUSTION_FIELD = "exhaustion"
SAVES_FIELD = "savingThrowBonuses"  # engine-written {ability: total}
ROLL_MODES_FIELD = "rollModes"
XP_FIELD = "experience_points"  # a fact: the base of the engine stat "xp"
XP_NEXT_FIELD = "exp_required_for_next_level"  # engine-written from xp:next
LEVEL_UPS_FIELD = "levelUpsPending"  # engine-written from xp:pending
CONCENTRATION_FIELD = "concentration"  # code-written: {"name", "group", "targets", "expiration"} while the character concentrates
# SRD states that are Incapacitated or include it (NQL 70352b9): a caster in one of
# them cannot hold concentration, and the engine refuses a world that declares both.
INCAPACITATING_STATES = ("incapacitated", "paralyzed", "petrified", "stunned", "unconscious")
EXHAUSTION_MAX = 6
STATE_PREFIX = "state:"
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


def state_names(sheet: Dict[str, Any], gaps: List[str]) -> List[str]:
    """The SRD condition names the sheet states: condition_affected plus condition, casefolded, known ones only."""
    cid = sheet.get("name", "")
    listed = sheet.get("condition_affected")
    entries: List[Any] = list(listed) if isinstance(listed, list) else []
    single = sheet.get("condition")
    if isinstance(single, str) and single.strip().casefold() not in ("", "none"):
        entries.append(single)
    out: List[str] = []
    for entry in entries:
        name = entry.strip().casefold() if isinstance(entry, str) else None
        if name is None or name not in srd_stats.STATE_NAMES:
            gaps.append(f"{cid}: condition {entry!r} is not an SRD condition; no state declared")
            continue
        if name not in out:
            out.append(name)
    return out


def exhaustion_level(sheet: Dict[str, Any], gaps: List[str]) -> int:
    """The typed ``exhaustion`` level (0..6). A legacy sheet listing "exhaustion" with no field is level 1."""
    cid = sheet.get("name", "")
    level = sheet.get(EXHAUSTION_FIELD)
    if type(level) is int:
        if 0 <= level <= EXHAUSTION_MAX:
            return level
        gaps.append(f"{cid}: exhaustion {level} is outside 0..{EXHAUSTION_MAX}; clamped")
        return max(0, min(EXHAUSTION_MAX, level))
    if level is not None:
        gaps.append(f"{cid}: exhaustion {level!r} is not an integer; ignored")
    return 1 if "exhaustion" in state_names(sheet, []) else 0


def exhaustion_instance(level: int) -> str:
    """The instance id prefix of one exhaustion level (genesis appends the character scope)."""
    return f"{STATE_PREFIX}exhaustion:{level}"


def state_instances(sheet: Dict[str, Any], gaps: List[str]) -> List[Tuple[str, str]]:
    """(instance id prefix, ``state:<name>`` type) pairs to instantiate for this sheet.

    Unconscious is the engine's while hit points are 0 (held at the minimum
    and ended by healing), so the sheet's entry is not declared then; at more
    than 0 it is a stated fact (a magical sleep) and is declared like any other.
    Exhaustion is one instance per level of the typed field (each costs 5 feet
    of speed and 2 on d20 rolls in the engine).
    """
    hp = _int(sheet.get("hitPoints"))
    out: List[Tuple[str, str]] = []
    for name in state_names(sheet, gaps):
        if name == "exhaustion" or (name == "unconscious" and hp is not None and hp <= 0):
            continue
        out.append((STATE_PREFIX + name, STATE_PREFIX + name))
    for level in range(1, exhaustion_level(sheet, gaps) + 1):
        out.append((exhaustion_instance(level), STATE_PREFIX + "exhaustion"))
    return out


def exhaustion_of(status: Dict[str, Any]) -> int:
    """The number of exhaustion instances in a status record."""
    return sum(1 for record in status.get("conditions") or []
               if isinstance(record, dict) and record.get("type") == STATE_PREFIX + "exhaustion")


def concentration_of(sheet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """The typed concentration record (a dict with a non-empty ``group``) or None."""
    record = sheet.get(CONCENTRATION_FIELD)
    if isinstance(record, dict) and isinstance(record.get("group"), str) and record["group"]:
        return record
    return None


def concentration_blocked(sheet: Dict[str, Any]) -> Optional[str]:
    """Why this sheet cannot hold concentration right now (an incapacitating state or 0 hit points), else None."""
    hp = _int(sheet.get("hitPoints"))
    if hp is not None and hp <= 0:
        return "unconscious at 0 hit points"
    for name in state_names(sheet, []):
        if name in INCAPACITATING_STATES:
            return name
    return None


def concentration_instance(sheet: Dict[str, Any]) -> Optional[str]:
    """The engine instance id for this sheet's concentration, or None when there is none to declare."""
    if concentration_of(sheet) is None or concentration_blocked(sheet):
        return None
    return "concentration:" + sheet_scope(sheet)


def sheet_scope(sheet: Dict[str, Any]) -> str:
    from core.nql import genesis
    return genesis.character_id(sheet).split(":", 1)[1]


def states_of(status: Dict[str, Any]) -> List[str]:
    """Sorted SRD condition names present in a status record (declared instances and held ones)."""
    names: List[str] = []
    for record in list(status.get("conditions") or []) + list(status.get("held_conditions") or []):
        kind = record.get("type") if isinstance(record, dict) else None
        if isinstance(kind, str) and kind.startswith(STATE_PREFIX) and kind[len(STATE_PREFIX):] not in names:
            if kind == srd_stats.CONCENTRATION_TYPE:
                continue  # CN: the caster's concentration is the typed field, not an SRD condition
            names.append(kind[len(STATE_PREFIX):])
    return sorted(names)


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
    xp = _int(sheet.get(XP_FIELD))
    if xp is None or xp < 0:
        gaps.append(f"{cid}: {XP_FIELD} is not a whole number; 0 declared")
        xp = 0
    lines.append(f' stat "xp" = {xp}; stat "xp:next" = 0; stat "xp:pending" = 0;')
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


ROLL_LABELS = {"bonus:checks": "ability checks", "bonus:saves": "saving throws", "bonus:d20": "all d20 rolls",
               "initiative": "initiative", "attack": "attack rolls"}


def roll_modes_of(status: Dict[str, Any]) -> Dict[str, str]:
    """{what: 'mode (causes)'} for every stat a condition targets directly with a roll mode.

    Derived stats (a skill under Poisoned) inherit the mode through their terms
    and are not listed twice; the engine still applies it when the check runs.
    """
    out: Dict[str, str] = {}
    for record in status.get("stats") or []:
        if not isinstance(record, dict) or not isinstance(record.get("stat"), str):
            continue
        mode = record.get("roll")
        if not isinstance(mode, str) or mode == "normal":
            continue
        stat = record["stat"]
        causes = sorted({str(src.get("type", "")).replace(STATE_PREFIX, "")
                         for src in record.get("roll_sources") or []
                         if isinstance(src, dict) and src.get("stat") == stat})
        if not causes:
            continue  # inherited from another stat's modifier
        if stat.startswith("save:"):
            label = stat[len("save:"):].capitalize() + " save"
        else:
            label = ROLL_LABELS.get(stat, stat)
        out[label] = f"{mode} ({', '.join(causes)})"
    return out


def write_back(sheet: Dict[str, Any], status: Dict[str, Any]) -> List[str]:
    """Store the engine's totals and condition states on the sheet; return the fields whose value changed."""
    changes: List[str] = []

    def put(container: Dict[str, Any], key: str, value: Any, label: str) -> None:
        if container.get(key) != value:
            changes.append(f"{label} {container.get(key)!r} -> {value!r}")
            container[key] = value

    _write_back_states(sheet, status, put)
    values = totals(status)
    if "proficiency" not in values:
        return changes
    if not isinstance(sheet.get(EXPERTISE_FIELD), list):
        # Inferred from the stored values before the engine's replace them.
        inferred, _ = expertise_of(sheet)
        sheet[EXPERTISE_FIELD] = [_display(sid) for sid in inferred]
        changes.append(f"{EXPERTISE_FIELD} inferred {sheet[EXPERTISE_FIELD]}")
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
    saves = {a: values["save:" + a] for a in srd_stats.ABILITIES if ("save:" + a) in values}
    if len(saves) == len(srd_stats.ABILITIES):
        put(sheet, SAVES_FIELD, saves, SAVES_FIELD)
    put(sheet, ROLL_MODES_FIELD, roll_modes_of(status), ROLL_MODES_FIELD)
    if "xp:next" in values and "xp:pending" in values:
        # At level 20 the engine's "next" is 0 (no further level); the sheet keeps the level-20
        # total so the banner never reads "XP 400000/0".
        if values["xp:next"] > 0:
            put(sheet, XP_NEXT_FIELD, values["xp:next"], XP_NEXT_FIELD)
        put(sheet, LEVEL_UPS_FIELD, max(0, values["xp:pending"]), LEVEL_UPS_FIELD)
    return changes


def _write_back_states(sheet: Dict[str, Any], status: Dict[str, Any], put) -> None:
    """The engine's condition view onto status / condition / condition_affected.

    Unconscious is present when the engine holds it (hp at 0) or the sheet
    declared it; ``status`` follows it (unconscious, or alive again once it is
    gone). A dead character is the DM's word and is left alone.
    """
    if "conditions" not in status or sheet.get("status") == "dead":
        return
    put(sheet, EXHAUSTION_FIELD, exhaustion_of(status), "exhaustion")
    names = states_of(status)
    put(sheet, "condition_affected", names, "condition_affected")
    current = sheet.get("condition")
    put(sheet, "condition", current if current in names else (names[0] if names else "none"), "condition")
    if "unconscious" in names:
        put(sheet, "status", "unconscious", "status")
    elif sheet.get("status") == "unconscious":
        put(sheet, "status", "alive", "status")


def carry_states(engine_sheet: Dict[str, Any], target: Dict[str, Any]) -> List[str]:
    """Copy the engine's unconscious verdict from a written-back sheet onto a merged one.

    The merged sheet may carry the model's own condition edits (a grapple
    stated in the same delta as the damage), so only the engine's part moves:
    ``status`` (never dead) and the ``unconscious`` entry of the list.
    """
    changes: List[str] = []
    if target.get("status") == "dead" or engine_sheet.get("status") not in ("alive", "unconscious"):
        return changes
    held = "unconscious" in (engine_sheet.get("condition_affected") or [])
    listed = [c for c in target.get("condition_affected") or [] if isinstance(c, str)]
    names = sorted(set(listed) | {"unconscious"}) if held else [c for c in listed if c != "unconscious"]
    if names != listed:
        changes.append(f"condition_affected {listed!r} -> {names!r}")
        target["condition_affected"] = names
    condition = target.get("condition") if target.get("condition") in names else (names[0] if names else "none")
    if condition != target.get("condition"):
        changes.append(f"condition {target.get('condition')!r} -> {condition!r}")
        target["condition"] = condition
    status = "unconscious" if held else ("alive" if target.get("status") == "unconscious" else target.get("status"))
    if status != target.get("status"):
        changes.append(f"status {target.get('status')!r} -> {status!r}")
        target["status"] = status
    return changes


def drop_model_states(updates: Dict[str, Any]) -> List[str]:
    """Remove hit-point-driven state writes from a model-authored delta; return what was dropped.

    The engine sets unconscious at 0 hit points and alive on healing: a
    model-written ``status`` of unconscious or alive is dropped (``dead`` is
    the DM's and stays), and a delta that carries an hpDelta may not add or
    remove ``unconscious`` in ``condition`` / ``condition_affected`` either.
    Every other condition is a fact the model states.
    """
    dropped: List[str] = []
    if updates.get("status") in ("unconscious", "alive"):
        updates.pop("status")
        dropped.append("status")
    if "hpDelta" not in updates:
        return dropped
    if updates.get("condition") == "unconscious":
        updates.pop("condition")
        dropped.append("condition")
    listed = updates.get("condition_affected")
    if isinstance(listed, list) and "unconscious" in listed:
        updates["condition_affected"] = [c for c in listed if c != "unconscious"]
        dropped.append("condition_affected[unconscious]")
    return dropped


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


DERIVED_FIELDS = ("proficiencyBonus", "initiative", SAVES_FIELD, ROLL_MODES_FIELD, XP_NEXT_FIELD, LEVEL_UPS_FIELD)
FACT_FIELDS = ("level", "abilities", "skills", "savingThrows", EXPERTISE_FIELD, "feats", "classFeatures", "speed",
               EXHAUSTION_FIELD, XP_FIELD) + STATE_FIELDS


def facts_changed(before: Dict[str, Any], after: Dict[str, Any]) -> bool:
    """True when a fact the totals or states read differs between two sheets (values compared, not digests)."""
    for key in FACT_FIELDS:
        if before.get(key) != after.get(key):
            return True
    return casting_ability(before) != casting_ability(after)


def refresh(sheet: Dict[str, Any], *, location: str = "sheet", binary: Optional[str] = None) -> Optional[str]:
    """Ask the engine for this sheet's totals and store them; return a reason on failure, else None.

    Genesis plus a status view: no action, no model. Used after a change of
    facts that made no other engine request (a T079 delta adding a skill).
    """
    from core.nql import apply, genesis

    world = genesis.build_world([sheet], location)
    cid = genesis.character_id(sheet)
    try:
        response = apply.genesis(world.source, status=[cid], binary=binary)
    except apply.EngineUnavailable as error:
        return str(error)
    if not response.get("ok"):
        return f"engine refused the world at {response.get('phase')}: {response.get('diagnostics') or response.get('fault') or response.get('error')}"
    for status in response.get("status") or []:
        if isinstance(status.get("character"), dict) and status["character"].get("id") == cid:
            store(sheet, status)
            return None
    return "engine returned no status for the character"


def drop_model_totals(stored: Dict[str, Any], updates: Dict[str, Any]) -> List[str]:
    """Remove derived totals from a model-authored delta; return what was dropped.

    The engine derives proficiencyBonus, initiative, senses.passivePerception,
    the skill bonuses and spellSaveDC/spellAttackBonus from the sheet's facts.
    A value the model wrote for one of them is dropped here (the stored value
    stays until the engine's next write). A skill the sheet did not have is
    kept as a fact (a new proficiency) with its bonus left to the engine.
    """
    dropped: List[str] = []
    for key in DERIVED_FIELDS:
        if key in updates:
            updates.pop(key)
            dropped.append(key)
    # XP is a fact the engine changes by award (awardExperience -> core/nql/experience); a model-
    # written total is dropped so a delta sentence can never re-total the sheet.
    if XP_FIELD in updates and updates[XP_FIELD] != stored.get(XP_FIELD):
        updates.pop(XP_FIELD)
        dropped.append(XP_FIELD)
    # Concentration is a code-written fact (core/managers/concentration_runtime): never the model's.
    if CONCENTRATION_FIELD in updates:
        updates.pop(CONCENTRATION_FIELD)
        dropped.append(CONCENTRATION_FIELD)
    senses = updates.get("senses")
    if isinstance(senses, dict) and "passivePerception" in senses:
        senses.pop("passivePerception")
        dropped.append("senses.passivePerception")
        if not senses:
            updates.pop("senses")
    skills = updates.get("skills")
    stored_skills = stored.get("skills") if isinstance(stored.get("skills"), dict) else {}
    if isinstance(skills, dict):
        for key in list(skills):
            match = next((k for k in stored_skills if skill_id(k) == skill_id(key)), None)
            if match is not None:
                if skills[key] != stored_skills[match]:
                    dropped.append(f"skills.{key}")
                skills[key] = stored_skills[match]
            elif skill_id(key) is not None:
                skills[key] = 0  # a new proficiency: the engine writes the bonus
    casting = updates.get("spellcasting")
    stored_casting = stored.get("spellcasting") if isinstance(stored.get("spellcasting"), dict) else {}
    if isinstance(casting, dict):
        for key in ("spellSaveDC", "spellAttackBonus"):
            if key in casting and casting[key] != stored_casting.get(key):
                dropped.append(f"spellcasting.{key}")
            if key in casting:
                casting[key] = stored_casting.get(key, casting[key])
    return dropped
