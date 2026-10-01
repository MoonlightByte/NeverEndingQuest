# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""Build an NQL world from character sheets and storage containers (genesis).

Only typed fields are read: ``abilities.dexterity``, ``proficiencies.armor``,
``classFeatures[].name`` (exact feature names), and the equipment entries'
``item_name``, ``nql_id``, ``item_type``, ``armor_category``, ``ac_base``,
``ac_bonus``, ``dex_limit``, ``quantity`` and ``equipped``. Descriptions and any
other prose are never inspected. Anything the engine cannot represent is
reported in ``Genesis.gaps`` rather than silently approximated.

Every item and character carries a stable identity. ``assign_ids`` writes a
``nql_id`` onto each equipment entry that lacks one (schema field, owner
decision D8); ``build_world`` uses that id, or mints a temporary one for an
entry that still lacks it, and returns the id of every entry so callers can map
engine facts back to sheet entries. Display names are not identities.
"""
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.nql import srd_stats, stats

EQUIPMENT_VERSION = "nql-equipment-v1"
# Typed values an item effect may use to name armor class as its target. This
# is a fixed vocabulary of field values, not a search over prose.
AC_EFFECT_TARGETS = ("AC", "armorClass", "armor class", "Armor Class")
# Coins are engine resources on the character: exact integer balances with a
# floor of zero, so an overdraft is refused rather than clamped or reset.
COIN_TYPES = ("gold", "silver", "copper")
COIN_MAX = 1_000_000_000_000
# Temporary hit points: an engine buffer pool in front of hp (no maximum in the
# rules; damage drains it first, a grant replaces a smaller one, a long rest
# clears it). Declared for every character that declares hp.
TEMP_HP_RESOURCE = "temp-hp"
TEMP_HP_MAX = 1_000_000_000
DEFENSE_STYLE_FEATURE = "Fighting Style: Defense"
DEFENSE_STYLE_CONDITION = "feature:defense-style"
# Temporary effects (E12): a live classifier or combat-engine effect whose
# armor class or maximum hit point modifiers the engine holds is marked
# engineOwned on the sheet; its numbers are then inside the stored armorClass
# and maxHitPoints, and genesis declares it as a condition instance the engine
# takes as already applied. An effect without the mark is still rendered by
# the read-time overlay (core/effects/effective.py). expiresTick is the engine
# clock tick (game seconds) at which a timed effect ends.
EFFECT_ENGINE_OWNED = "engineOwned"
EFFECT_EXPIRES_TICK = "expiresTick"
EFFECT_AUTHORS = ("engine", "classifier")

_ARMOR_TRAINING = {
    "light": "training:light",
    "medium": "training:medium",
    "heavy": "training:heavy",
    "shield": "training:shield",
    "shields": "training:shield",
}


@dataclass
class Genesis:
    source: str
    location: str
    character_ids: Dict[str, str] = field(default_factory=dict)          # sheet name -> char id
    item_ids: Dict[str, Dict[int, str]] = field(default_factory=dict)      # char id -> equipment index -> item id
    container_ids: Dict[str, str] = field(default_factory=dict)           # storage id -> container item id
    content_ids: Dict[str, Dict[int, str]] = field(default_factory=dict)   # storage id -> contents index -> item id
    effect_names: Dict[str, str] = field(default_factory=dict)            # condition instance id -> effect name
    gaps: List[str] = field(default_factory=list)


def _q(value: str) -> str:
    """NQL strings use JSON escapes."""
    return json.dumps(str(value), ensure_ascii=True)


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return s or "x"


def _int(value: Any) -> Optional[int]:
    return value if type(value) is int else None


def character_id(sheet: Dict[str, Any]) -> str:
    return "char:" + slug(sheet.get("name", ""))


def location_id(location: str) -> str:
    return "loc:" + slug(location)


def container_id(storage_id: str) -> str:
    return "container:" + slug(storage_id)


def _mint(entry: Dict[str, Any], scope: str, index: int) -> str:
    return f"item:{slug(entry.get('item_name', ''))}:{scope}:{index}"


def _entry_id(entry: Dict[str, Any], scope: str, index: int) -> str:
    existing = entry.get("nql_id")
    if isinstance(existing, str) and existing.startswith("item:"):
        return existing
    return _mint(entry, scope, index)


def assign_ids(sheet: Dict[str, Any]) -> bool:
    """Write a nql_id onto every equipment entry that lacks one. Returns True if any was added."""
    changed = False
    seen = set()
    scope = slug(sheet.get("name", ""))
    for index, entry in enumerate(sheet.get("equipment") or []):
        if not isinstance(entry, dict) or not entry.get("item_name"):
            continue
        current = entry.get("nql_id")
        if not (isinstance(current, str) and current.startswith("item:")) or current in seen:
            candidate = _mint(entry, scope, index)
            while candidate in seen:
                index += 1000
                candidate = _mint(entry, scope, index)
            entry["nql_id"] = candidate
            changed = True
        seen.add(entry["nql_id"])
    return changed


def feature_resource_id(name: str) -> str:
    return "use:" + slug(name)


def slot_resource_id(level_key: str) -> str:
    """spellSlots key 'level3' -> 'slot:3'."""
    return "slot:" + str(level_key)[5:]


def _pool(cid: str, label: str, current: Any, maximum: Any, gaps: List[str]) -> Optional[Tuple[int, int]]:
    cur, mx = _int(current), _int(maximum)
    if cur is None or mx is None or cur < 0 or mx < 0:
        gaps.append(f"{cid}: {label} current/max are not non-negative integers; not an engine resource")
        return None
    if cur > mx:
        gaps.append(f"{cid}: {label} current {cur} above max {mx}; clamped to max at genesis")
        cur = mx
    return cur, mx


def pool_resources(sheet: Dict[str, Any], gaps: List[str]) -> List[Tuple[str, int, int]]:
    """(resource id, current, max) for hit points, spell slots and feature use pools.

    Typed fields only: ``hitPoints``/``maxHitPoints``, ``spellcasting.spellSlots.levelN``
    ``{current, max}`` and ``classFeatures[].usage {current, max}``. A pool the sheet
    does not carry is simply absent; a spend against it is then a compile refusal.
    """
    cid = character_id(sheet)
    out: List[Tuple[str, int, int]] = []
    if "hitPoints" in sheet or "maxHitPoints" in sheet:
        hp = _pool(cid, "hitPoints", sheet.get("hitPoints"), sheet.get("maxHitPoints"), gaps)
        if hp is not None:
            out.append(("hp", hp[0], hp[1]))
            temp = _int(sheet.get("temporaryHitPoints"))
            if temp is None or temp < 0:
                if "temporaryHitPoints" in sheet:
                    gaps.append(f"{cid}: temporaryHitPoints is not a non-negative integer; treated as 0")
                temp = 0
            out.append((TEMP_HP_RESOURCE, min(temp, TEMP_HP_MAX), TEMP_HP_MAX))
    slots = (sheet.get("spellcasting") or {}).get("spellSlots") if isinstance(sheet.get("spellcasting"), dict) else None
    for key, pool in sorted((slots or {}).items()) if isinstance(slots, dict) else []:
        if not (isinstance(pool, dict) and str(key).startswith("level")):
            continue
        p = _pool(cid, f"spellSlots.{key}", pool.get("current"), pool.get("max"), gaps)
        if p is not None:
            out.append((slot_resource_id(key), p[0], p[1]))
    seen: set = set()
    for feature in sheet.get("classFeatures") or []:
        if not isinstance(feature, dict) or not isinstance(feature.get("usage"), dict) or not feature.get("name"):
            continue
        rid = feature_resource_id(feature["name"])
        if rid in seen:
            gaps.append(f"{cid}: feature {feature['name']!r} shares a resource id with another feature; skipped")
            continue
        p = _pool(cid, f"usage of {feature['name']!r}", feature["usage"].get("current"), feature["usage"].get("max"), gaps)
        if p is not None:
            seen.add(rid)
            out.append((rid, p[0], p[1]))
    return out


def live_effects(sheet: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The sheet's temporary effects that the runtime renders (typed author field)."""
    return [e for e in sheet.get("temporaryEffects") or []
            if isinstance(e, dict) and e.get("authoredBy") in EFFECT_AUTHORS
            and isinstance(e.get("modifiers"), list) and isinstance(e.get("effectId"), str) and e["effectId"]]


def effect_engine_modifiers(effect: Dict[str, Any]) -> Optional[List[Tuple[str, int]]]:
    """The engine-representable modifiers of one effect: [("defense" | "hp-max", amount)].

    Stored modifiers are normalized (``armorClass``, ``maxHitPoints``, or
    ``hitPoints`` with ``affectsMax``); other stats are not the engine's here.
    A negative maximum (a drain or curse) is held since engine aa49438; the
    engine refuses a drain larger than the room the maximum has after active
    raises, so ``core/nql/effects`` sizes it from the sheet before applying.
    None is reserved for an effect the engine cannot hold at all.
    """
    out: List[Tuple[str, int]] = []
    hp_max_total = 0
    for modifier in effect.get("modifiers") or []:
        if not isinstance(modifier, dict) or type(modifier.get("value")) is not int or modifier["value"] == 0:
            continue
        stat = modifier.get("stat")
        if stat == "armorClass":
            out.append(("defense", modifier["value"]))
        elif stat == "maxHitPoints" or (stat == "hitPoints" and modifier.get("affectsMax") is True):
            out.append(("hp-max", modifier["value"]))
            hp_max_total += modifier["value"]
    if hp_max_total and any(k == "hp-max" and (v > 0) != (hp_max_total > 0) for k, v in out):
        # One instance's maximum modifiers must all raise or all drain.
        return None
    return out


def effect_type_id(effect: Dict[str, Any]) -> str:
    return "effect:" + str(effect.get("effectId"))


def effect_instance_id(effect: Dict[str, Any]) -> str:
    return "fx:" + str(effect.get("effectId"))


def effect_type_line(effect: Dict[str, Any], modifiers: List[Tuple[str, int]]) -> str:
    parts = []
    for index, (kind, amount) in enumerate(modifiers):
        if kind == "defense":
            parts.append(f'modifier "m{index}" stat "defense" add {amount};')
        else:
            parts.append(f'modifier "m{index}" resource "hp" maximum add {amount};')
    return f"condition type {_q(effect_type_id(effect))} {{ instances unique; {' '.join(parts)} }}"


def _effect_lines(sheet: Dict[str, Any], cid: str, gaps: List[str],
                  names: Dict[str, str], clock_tick: Optional[int] = None) -> Tuple[List[str], List[str]]:
    """(condition type lines, instance lines) for the sheet's effects.

    A type is declared for every live effect the engine can hold, so a later
    ``apply condition`` in the same world has it; an instance is declared only
    for an effect marked engineOwned (already inside the stored numbers). With
    a ``clock_tick`` (the world's clock), an owned effect with an expiresTick
    is timed: ``ticks expiresTick - clock_tick`` (at least 1, so an effect
    already due ends on the first advance).
    """
    types: List[str] = []
    instances: List[str] = []
    seen: set = set()
    for effect in live_effects(sheet):
        modifiers = effect_engine_modifiers(effect)
        if modifiers is None:
            if effect.get(EFFECT_ENGINE_OWNED):
                gaps.append(f"{cid}: effect {effect.get('name')!r} is marked engineOwned but the engine cannot hold its modifiers")
            continue
        # An effect with no engine numbers (a potion's temp hit points, a
        # condition, a speed bonus) is still an instance: the engine clock
        # owns its expiry and a rest or removal ends it like any other.
        tid = effect_type_id(effect)
        if tid in seen:
            gaps.append(f"{cid}: effect {effect.get('name')!r} repeats effectId {effect.get('effectId')!r}; second declaration skipped")
            continue
        seen.add(tid)
        types.append(effect_type_line(effect, modifiers))
        iid = effect_instance_id(effect)
        names[iid] = str(effect.get("name") or effect.get("effectId"))
        if effect.get(EFFECT_ENGINE_OWNED) is True:
            expires = effect.get(EFFECT_EXPIRES_TICK)
            timed = clock_tick is not None and type(expires) is int and effect.get("roundsRemaining") is None
            ticks = f" ticks {max(1, expires - clock_tick)}" if timed else ""
            instances.append(f"condition {_q(iid)} of {_q(tid)} to {_q(cid)}{ticks};")
    return types, instances


def _training(sheet: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for label in (sheet.get("proficiencies") or {}).get("armor") or []:
        cond = _ARMOR_TRAINING.get(str(label).strip().lower())
        if cond and cond not in out:
            out.append(cond)
    return out


def _has_defense_style(sheet: Dict[str, Any]) -> bool:
    return any(f.get("name") == DEFENSE_STYLE_FEATURE for f in sheet.get("classFeatures") or [] if isinstance(f, dict))


def _armor_definition(def_id: str, entry: Dict[str, Any], gaps: List[str]) -> Optional[str]:
    """One immutable definition per armor entry, from its typed fields only."""
    category = entry.get("armor_category")
    base = _int(entry.get("ac_base"))
    bonus = _int(entry.get("ac_bonus")) or 0
    name = entry.get("item_name", "")
    if category == "shield":
        amount = (base if base is not None else 2) + bonus
        return (
            f' definition {_q(def_id)} named {_q(name)} {{\n'
            f'  description "Shield.";\n  default "held";\n'
            f'  mode "held" {{ occupy "hand" by 1; occupy "shield" by 1; '
            f'modifier "defense" stat "defense" add {amount} requires "training:shield"; }}\n }}\n'
        )
    if base is None:
        gaps.append(f"armor without ac_base: {name!r}; treated as a worn item with no defense")
        return None
    constant = base + bonus
    style = f'   modifier "style" stat "defense" add 1 requires {_q(DEFENSE_STYLE_CONDITION)};\n'
    if category == "light":
        term = '   term stat "dexterity" offset -10 divide 2;\n'
    elif category == "medium":
        limit = _int(entry.get("dex_limit"))
        term = f'   term stat "dexterity" offset -10 divide 2 ceiling {limit if limit is not None else 2};\n'
    elif category == "heavy":
        term = ""
    else:
        gaps.append(f"armor with unknown armor_category {category!r}: {name!r}; treated as light")
        term = '   term stat "dexterity" offset -10 divide 2;\n'
    return (
        f' definition {_q(def_id)} named {_q(name)} {{\n'
        f'  description "Body armor.";\n  default "worn";\n'
        f'  mode "worn" {{\n   occupy "body" by 1;\n'
        f'   base stat "defense" {{\n    constant {constant};\n{term}   }}\n{style}  }}\n }}\n'
    )


def ac_effect_lines(iid: str, entry: Dict[str, Any]) -> List[str]:
    """Worn-item defense effects from the entry's typed effects list.

    An effect of type "bonus" whose target names armor class and whose value is
    an integer becomes a while-worn engine effect on the item, so a ring of
    protection counts only while worn and is explained by its item.
    """
    out: List[str] = []
    for index, effect in enumerate(entry.get("effects") or []):
        if (isinstance(effect, dict) and effect.get("type") == "bonus"
                and effect.get("target") in AC_EFFECT_TARGETS and type(effect.get("value")) is int
                and effect["value"] != 0):
            eid = f"effect:{iid.split(':', 1)[1]}:ac:{index}"
            out.append(f'effect {_q(eid)} from item {_q(iid)} on worn {_q(iid)} stat "defense" add {effect["value"]};')
    return out


def _item_line(iid: str, entry: Dict[str, Any], owner: str, custody: str, worn: bool,
               definitions: List[str], gaps: List[str], cid: str) -> Tuple[str, Optional[str]]:
    """One item declaration. Returns (line, mode-if-held)."""
    quantity = _int(entry.get("quantity"))
    item_type = entry.get("item_type")
    definition = None
    mode = None
    if ac_effect_lines(iid, entry) and item_type not in ("armor", "weapon"):
        # An item with a while-worn defense effect must be a typed worn item.
        definition, mode = "gear:worn", "worn"
    if item_type == "armor":
        def_id = "gear:" + iid.split(":", 1)[1]
        text = _armor_definition(def_id, entry, gaps)
        if text is not None:
            definitions.append(text)
            definition, mode = def_id, ("held" if entry.get("armor_category") == "shield" else "worn")
        else:
            definition, mode = "gear:worn", "worn"
    elif item_type == "weapon":
        definition, mode = "gear:held", "held"
    elif definition is None:
        # Every other item can be worn or carried ready (a lantern, a holy
        # symbol, a cloak): it occupies no slot. Declared whether or not it is
        # equipped now, so a later equip has a typed definition to use.
        definition, mode = "gear:worn", "worn"
    if worn and quantity not in (None, 1):
        gaps.append(f"{cid}: {entry.get('item_name')!r} is equipped with quantity {quantity}; the engine wears exactly one, item left unworn")
        worn = False
    fields = [f"owner {_q(owner)};", custody]
    if worn:
        fields.append(f"wearer {_q(cid)};")
    if definition:
        fields.append(f"definition {_q(definition)};")
    if worn and mode:
        fields.append(f"mode {_q(mode)};")
    if quantity is not None and quantity != 1:
        fields.append(f"quantity {quantity};")
    return f"item {_q(iid)} named {_q(entry['item_name'])} {{ {' '.join(fields)} }}", (mode if worn else None)


def build_world(sheets: List[Dict[str, Any]], location: str, location_name: str = "",
                containers: Optional[List[Dict[str, Any]]] = None, contents_owner: Optional[str] = None,
                definition_entries: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
                clock_tick: Optional[int] = None, dice_seed: Optional[Tuple[int, int]] = None) -> Genesis:
    """Return the NQL world source for these sheets and storage containers at one location.

    ``containers`` are player_storage.json container records at this location. Their
    contents are declared in the container's custody and owned by ``contents_owner``
    (a character id; legacy storage records no owner and the acting character is the
    only party that can retrieve, so the caller passes that character).
    ``clock_tick`` declares the world clock (game seconds) so owned timed effects
    carry their remaining ticks and ``advance time`` can end them; without it the
    world has no clock and every instance is untimed (coin, item and rest flows).
    """
    gaps: List[str] = []
    loc = location_id(location)
    lines: List[str] = [
        "// Generated by core/nql/genesis.py from character sheets. Typed fields only.",
        "rules { transfer unequips; wear any; }",
    ]
    if clock_tick is not None:
        lines.append(f'clock "second" at {int(clock_tick)};')
    if dice_seed is not None:
        # The world's dice (C2): a check without the player's faces rolls from
        # this seed; the host draws a fresh one from os.urandom per genesis.
        lines.append(f'dice seed {int(dice_seed[0])} {int(dice_seed[1])};')
    lines.append(f"location {_q(loc)} named {_q(location_name or location)};")
    character_ids: Dict[str, str] = {}
    item_ids: Dict[str, Dict[int, str]] = {}
    container_ids: Dict[str, str] = {}
    content_ids: Dict[str, Dict[int, str]] = {}
    conditions: List[str] = []
    # Declared for every world: armor definitions reference these with
    # `requires`, which is legal only for a declared type, and a character may
    # carry armor it is not trained for (a shield handed to an untrained
    # companion). A character gets an instance only when the sheet lists the
    # proficiency or the exact feature name.
    condition_types: List[str] = [DEFENSE_STYLE_CONDITION]
    for cond in _ARMOR_TRAINING.values():
        if cond not in condition_types:
            condition_types.append(cond)
    definitions: List[str] = [
        ' definition "gear:held" named "Held item" { description "Occupies one hand."; default "held"; mode "held" { occupy "hand" by 1; } }\n',
        ' definition "gear:worn" named "Worn item" { description "Worn, occupies no slot."; default "worn"; mode "worn" { } }\n',
    ]
    items: List[str] = []
    effects: List[str] = []
    effect_types: List[str] = []
    effect_names: Dict[str, str] = {}
    all_ids: set = set()

    for sheet in sheets:
        cid = character_id(sheet)
        if cid in character_ids.values():
            gaps.append(f"duplicate character id {cid}; second sheet skipped")
            continue
        character_ids[sheet.get("name", "")] = cid
        dex = _int((sheet.get("abilities") or {}).get("dexterity"))
        if dex is None:
            gaps.append(f"{cid}: abilities.dexterity is not an integer; defense recipe uses 10")
            dex = 10
        coins = sheet.get("currency") if isinstance(sheet.get("currency"), dict) else {}
        resources = []
        for coin in COIN_TYPES:
            amount = _int(coins.get(coin))
            if amount is None or amount < 0:
                gaps.append(f"{cid}: currency.{coin} is not a non-negative integer; resource starts at 0")
                amount = 0
            resources.append(f' resource {_q(coin)} = {amount} min 0 max {COIN_MAX};')
        pools = pool_resources(sheet, gaps)
        for rid, current, maximum in pools:
            resources.append(f' resource {_q(rid)} = {current} min 0 max {maximum};')
        if any(rid == TEMP_HP_RESOURCE for rid, _, _ in pools):
            resources.append(f' buffer {_q(TEMP_HP_RESOURCE)} before "hp";')
        # E13: the sheet's facts (abilities, level, speed) and every SRD total
        # at its base; the engine derives the totals (core/nql/srd_stats.py).
        lines.append(
            f"character {_q(cid)} named {_q(sheet.get('name', ''))} at {_q(loc)} {{\n"
            f' stat "dexterity" = {dex};\n stat "defense" = 10;\n'
            + "\n".join(stats.stat_lines(sheet, gaps)) + "\n"
            + "\n".join(resources) + "\n}"
        )
        for cond in _training(sheet) + stats.condition_types(sheet, gaps):
            if cond not in condition_types:
                condition_types.append(cond)
            conditions.append(f"condition {_q(cond + ':' + cid.split(':', 1)[1])} of {_q(cond)} to {_q(cid)};")
        # C1: the SRD conditions the sheet states, one instance each
        # (unconscious at 0 hp is held by the engine, not declared).
        for prefix, kind in stats.state_instances(sheet, gaps):
            conditions.append(f"condition {_q(prefix + ':' + cid.split(':', 1)[1])} of {_q(kind)} to {_q(cid)};")
        # CN: the caster's one concentration instance (none while incapacitated or at
        # 0 hp: the engine would refuse the world, and the host ends the spell instead).
        focus = stats.concentration_instance(sheet)
        if focus:
            conditions.append(f"condition {_q(focus)} of {_q(srd_stats.CONCENTRATION_TYPE)} to {_q(cid)};")
        if _has_defense_style(sheet):
            conditions.append(
                f"condition {_q(DEFENSE_STYLE_CONDITION + ':' + cid.split(':', 1)[1])} of {_q(DEFENSE_STYLE_CONDITION)} to {_q(cid)};"
            )
        types, instances = _effect_lines(sheet, cid, gaps, effect_names, clock_tick)
        effect_types.extend(types)
        conditions.extend(instances)
        ids: Dict[int, str] = {}
        hands = 0
        scope = cid.split(":", 1)[1]
        for index, entry in enumerate(sheet.get("equipment") or []):
            if not isinstance(entry, dict) or not entry.get("item_name"):
                gaps.append(f"{cid}: equipment[{index}] has no item_name; skipped")
                continue
            iid = _entry_id(entry, scope, index)
            if iid in all_ids:
                gaps.append(f"{cid}: duplicate item id {iid} at equipment[{index}]; skipped")
                continue
            all_ids.add(iid)
            ids[index] = iid
            line, held = _item_line(iid, entry, cid, f"custody character {_q(cid)};",
                                    entry.get("equipped") is True, definitions, gaps, cid)
            items.append(line)
            effects.extend(ac_effect_lines(iid, entry))
            if held == "held":
                hands += 1
        if hands > 2:
            gaps.append(f"{cid}: {hands} held items equipped; the engine allows two hands, genesis will be refused")
        item_ids[cid] = ids

    owner = contents_owner or next(iter(character_ids.values()), None)
    for container in containers or []:
        sid = str(container.get("id", ""))
        if not sid:
            gaps.append("storage container without id skipped")
            continue
        conid = container_id(sid)
        container_ids[sid] = conid
        items.append(f"item {_q(conid)} named {_q(container.get('deviceName') or sid)} {{ container true; custody location {_q(loc)}; }}")
        ids = {}
        for index, entry in enumerate(container.get("contents") or []):
            if not isinstance(entry, dict) or not entry.get("item_name"):
                gaps.append(f"{sid}: contents[{index}] has no item_name; skipped")
                continue
            iid = _entry_id(entry, slug(sid), index)
            if iid in all_ids:
                gaps.append(f"{sid}: duplicate item id {iid} at contents[{index}]; skipped")
                continue
            if owner is None:
                gaps.append(f"{sid}: contents need an owner character; none in world")
                break
            all_ids.add(iid)
            ids[index] = iid
            line, _ = _item_line(iid, entry, owner, f"custody item {_q(conid)};", False, definitions, gaps, owner)
            items.append(line)
        content_ids[sid] = ids

    # Definitions for items that do not exist yet (a later create item in the
    # same world needs its equipment definition declared at genesis).
    for iid, entry in definition_entries or []:
        if isinstance(entry, dict) and entry.get("item_type") == "armor":
            text = _armor_definition("gear:" + iid.split(":", 1)[1], entry, gaps)
            if text is not None:
                definitions.append(text)

    for cond in condition_types:
        lines.append(f"condition type {_q(cond)} {{ instances unique; }}")
    # The SRD proficiency types are declared for every world: the derive rules
    # below name them with `requires`, legal only for a declared type.
    for cond in srd_stats.CONDITION_TYPES:
        if cond not in condition_types:
            lines.append(f"condition type {_q(cond)} {{ instances unique; }}")
    # The SRD condition states (C1): declared for every world so a later
    # `apply condition` has them and the engine can hold unconscious at 0 hp.
    lines.append(srd_stats.STATE_TYPES.rstrip("\n"))
    # Concentration (CN): the type, and the damage-triggered Constitution save.
    lines.append(srd_stats.CONCENTRATION_RULES.rstrip("\n"))
    lines.extend(effect_types)
    lines.extend(conditions)
    lines.append(f"equipment {_q(EQUIPMENT_VERSION)} {{")
    lines.append(' slot "hand" capacity 2;\n slot "body" capacity 1;\n slot "shield" capacity 1;')
    lines.append(' derive stat "defense" { term stat "dexterity" offset -10 divide 2; }')
    lines.append(srd_stats.DERIVE_RULES.rstrip("\n"))
    lines.append(srd_stats.XP_RULES.rstrip("\n"))
    lines.extend(d.rstrip("\n") for d in definitions)
    lines.append("}")
    lines.extend(items)
    lines.extend(effects)
    return Genesis(source="\n".join(lines) + "\n", location=loc, character_ids=character_ids, item_ids=item_ids,
                   container_ids=container_ids, content_ids=content_ids, effect_names=effect_names, gaps=gaps)


def expected_armor_class(sheet: Dict[str, Any]) -> Tuple[Optional[int], List[str]]:
    """The armor class the SRD rule gives for this sheet's typed fields.

    Used only as a test oracle next to the engine's explanation; it is not a
    gameplay writer and must never replace the engine's value.
    """
    dex = _int((sheet.get("abilities") or {}).get("dexterity"))
    if dex is None:
        return None, ["no dexterity"]
    mod = (dex - 10) // 2
    parts = [f"dex {mod}"]
    body = None
    shield = 0
    for entry in sheet.get("equipment") or []:
        if not isinstance(entry, dict) or entry.get("equipped") is not True or entry.get("item_type") != "armor":
            continue
        cat = entry.get("armor_category")
        base = _int(entry.get("ac_base"))
        bonus = _int(entry.get("ac_bonus")) or 0
        if cat == "shield":
            shield += (base if base is not None else 2) + bonus
        elif base is not None:
            if body is not None:
                return None, ["two body armors equipped"]
            limit = _int(entry.get("dex_limit"))
            if cat == "medium":
                body = base + bonus + min(mod, limit if limit is not None else 2)
            elif cat == "heavy":
                body = base + bonus
            else:
                body = base + bonus + mod
            parts.append(f"{entry.get('item_name')} {base}+{bonus}")
    total = (body if body is not None else 10 + mod) + shield
    if shield:
        parts.append(f"shield {shield}")
    if _has_defense_style(sheet) and body is not None:
        total += 1
        parts.append("style 1")
    for effect in live_effects(sheet):
        if effect.get(EFFECT_ENGINE_OWNED) is not True:
            continue
        for kind, amount in effect_engine_modifiers(effect) or []:
            if kind == "defense":
                total += amount
                parts.append(f"{effect.get('name')} {amount:+d}")
    return total, parts
