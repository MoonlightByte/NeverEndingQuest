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
import glob
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.effects.clock import DAYS_PER_MONTH, SECONDS_PER_DAY
from core.effects.effective import _effect_name_key
from core.effects.model import _MODIFIER_DIE
from core.leveling import tables as leveling_tables
from core.nql import class_conditions, item_catalog, srd_stats, stats

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
# The worn-mode member id of the style modifier in every body armor definition;
# the engine reports it as equipment_origin.member of the +1 (core/nql/armor_class.py).
DEFENSE_STYLE_MEMBER = "style"
# NUM-H3c: SRD 5.2.1 Archery ("+2 bonus to attack rolls you make with Ranged
# weapons"): one hit term on every ranged (ammunition) attack of a ported
# weapon, gated on this Condition, which the exact classFeatures name gives.
# Every character declares the amount as a stat, since a term names a stat.
ARCHERY_STYLE_FEATURE = "Fighting Style: Archery"
ARCHERY_STYLE_CONDITION = "feature:archery-style"
ARCHERY_STAT = "bonus:archery"
ARCHERY_BONUS = 2
ARCHERY_TERM = ' term stat "%s" offset 0 divide 1 requires "%s";' % (ARCHERY_STAT, ARCHERY_STYLE_CONDITION)
# #879: SRD 5.2.1 Great Weapon Fighting (treat a 1 or 2 on a damage die as a 3
# for a Melee weapon held with two hands). The engine takes damage totals only,
# so the swing treats the faces (core.combat.resolver.great_weapon_applies);
# this exact classFeatures name is the only one that grants it.
GREAT_WEAPON_STYLE_FEATURE = "Fighting Style: Great Weapon Fighting"
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

# Weapon definitions (NUM-H3a, srd-item-catalog/4 on NQL dafd508): the
# Martial Arts die by Condition type, declared by data/srd/attack_features.nql.
# A Monk weapon's attacks name these; genesis declares no instance of them yet.
MARTIAL_ARTS_CONDITION = "feature:martial-arts"
MARTIAL_ARTS_DICE = ((6, MARTIAL_ARTS_CONDITION), (8, "feature:martial-arts-d8"),
                     (10, "feature:martial-arts-d10"), (12, "feature:martial-arts-d12"))
UNARMORED_GATE = ' unless slot "body" unless slot "shield"'
WEAPON_ABILITY_TERM = 'term stat "%s" offset -10 divide 2;'
# The proficiency bonus as a term: a derived stat cannot feed another recipe,
# so the term reads the level fact as srd-stats' saves do, (level + 7) / 4.
WEAPON_PROFICIENCY_TERM = 'term stat "level" offset 7 divide 4 requires %s;'

# Exact sheet labels (lowercased) -> the training Conditions they give. The
# short keys are data/srd/choices.json class_traits armor_training values; the
# long forms are the SRD 5.2.1 printed labels, and "all armor" is the three
# body-armor trainings, not the shield (#896). Exact keys, never a pattern.
_ARMOR_TRAINING = {
    "light": ("training:light",),
    "medium": ("training:medium",),
    "heavy": ("training:heavy",),
    "shield": ("training:shield",),
    "shields": ("training:shield",),
    "light armor": ("training:light",),
    "medium armor": ("training:medium",),
    "heavy armor": ("training:heavy",),
    "all armor": ("training:light", "training:medium", "training:heavy"),
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
    # #1408: (char id, effectId) -> (condition type id, instance id) of each declared effect; a repeat
    # holder of a shared effectId has its own scoped ids.
    effect_ids: Dict[Tuple[str, str], Tuple[str, str]] = field(default_factory=dict)
    gaps: List[str] = field(default_factory=list)
    # NUM-H3a: item id -> character id for an equipped catalog weapon the hand
    # rule declared carried. Its sheet row stays equipped: a write that reads
    # the engine's wearer back keeps the row's flag (no sheet change).
    carried: Dict[str, str] = field(default_factory=dict)
    # NUM-H3b: observations that do not bear on defense (an off-vocabulary
    # weapon proficiency, a multiclass sheet's Martial Arts die or second
    # Unarmored Defense). Unlike gaps, they never stop an AC projection.
    notes: List[str] = field(default_factory=list)


ABILITY_NAMES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")


def _q(value: str) -> str:
    """NQL strings use JSON escapes."""
    return json.dumps(str(value), ensure_ascii=True)


def slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    return s or "x"


def _int(value: Any) -> Optional[int]:
    return value if type(value) is int else None


CHARGES_MAX = 1000  # the engine's bound for an item definition's charges
TYPE_DESCRIPTION_MAX = 4096  # the catalog's bound for an item type description, in bytes
TYPE_KIND_MAX = 256  # the catalog's bound for a type's kind and for its id, in bytes
ENGINE_ID_MAX = 256  # the engine's bound for an entity id, in bytes (#566)
# A minted item id leaves room for its per-row charged type id
# ("itemdef:row/" + the id after "item:", 7 bytes longer) under TYPE_KIND_MAX.
ITEM_ID_MAX = TYPE_KIND_MAX - len("itemdef:row/") + len("item:")  # 249
# A character's scope ends every condition instance id it holds ("<kind>:<scope>",
# at most 36 bytes over the scope) and the engine's own event id for each "add"
# modifier of such an instance ("condition:<len>:<instance>:<len>:<label>"). The
# longest is a Long Rest removing exhaustion, 41 bytes over the scope; a longer
# kind or modifier label must lower this bound (#1022).
CHARACTER_SCOPE_MAX = ENGINE_ID_MAX - len("condition:256:state:exhaustion:6::5:speed")  # 215


def _item_type_text(type_id: str, name: str, description: str, kind: Any, magical: bool, consumable: bool,
                    equipment: Optional[str], extra: str = "") -> str:
    """One ``item type`` declaration; every string goes through ``_q()``. No
    equipment line when ``equipment`` is None."""
    return (f"item type {_q(type_id)} named {_q(name)} {{\n"
            f" description {_q(description)};\n"
            f" kind {_q(str(kind))}; magical {'true' if magical is True else 'false'}; "
            f"consumable {'true' if consumable is True else 'false'};\n"
            + (f" equipment {_q(equipment)};\n" if equipment is not None else "")
            + f"{extra}}}")


def _module_type_source(ids: List[str]) -> str:
    """The item types of these module catalog ids (P3a); an id the catalog does
    not resolve (module removed, namespace collision, entry refused) is skipped,
    and its row takes the unknown-id path."""
    texts = []
    for type_id in ids:
        found = item_catalog.entry(type_id)
        if found is not None:
            texts.append(_item_type_text(type_id, found["name"], found["description"], found["kind"],
                                         found["magical"], found["consumable"], found["equipment"]))
    return "\n".join(texts)


def _module_row_id(entry: Dict[str, Any]) -> Optional[str]:
    catalog_id = entry.get("catalog_id")
    return catalog_id if isinstance(catalog_id, str) and catalog_id.startswith(item_catalog.MODULE_ID_PREFIX) else None


def _type_description(entry: Dict[str, Any]) -> str:
    """Display text for a per-row item type, within the catalog's byte bound
    (a longer one refuses the whole world at compile time)."""
    text = str(entry.get("description") or entry.get("item_name") or "")
    raw = text.encode("utf-8")
    if len(raw) <= TYPE_DESCRIPTION_MAX:
        return text
    return raw[:TYPE_DESCRIPTION_MAX - 3].decode("utf-8", errors="ignore") + "..."


def charges_fields(entry: Dict[str, Any]) -> Tuple[Optional[Tuple[int, int]], Optional[str]]:
    """((current, max), None) for a sheet row whose ``charges`` object the engine
    accepts, (None, reason) for one it would refuse, (None, None) for a row
    without charges.

    The engine refuses the WHOLE world at compile time on one bad charges row,
    so the host mirrors every rule here (NQL docs/ITEM_CHARGES.md, data
    contract) and the caller declares a refused row without charges instead.
    """
    charges = entry.get("charges")
    if not isinstance(charges, dict):
        return None, None
    current, maximum = charges.get("current"), charges.get("max")
    if type(current) is not int or type(maximum) is not int:
        return None, "charges.current and charges.max must be whole numbers"
    if not 1 <= maximum <= CHARGES_MAX:
        return None, f"charges.max must be between 1 and {CHARGES_MAX}"
    if not 0 <= current <= maximum:
        return None, "charges.current must be between 0 and charges.max"
    quantity = entry.get("quantity")
    if type(quantity) is bool or quantity not in (None, 0, 1):
        return None, "a charged item is one physical unit (quantity 0 or 1)"
    if entry.get("item_type") == "armor" and item_catalog.row_entry(entry)[0] is None:
        return None, "armor keeps its armor definition; charges on an armor row are not declared in this slice"
    if not str(entry.get("item_name") or "").strip():
        return None, "a charged item needs a name"
    return (current, maximum), None


def charged_type_id(iid: str) -> str:
    """The per-row item type a charged sheet row is declared from."""
    return "itemdef:row/" + iid.split(":", 1)[1]


# Item charges H2: the recharge rule of a per-row type comes from the row's
# typed ``rechargeRate`` value (char_schema.json enum), never from prose. The
# boundaries are calendar-fixed on the game's absolute seconds
# (core/effects/clock.py: day = 86400 s, 06:00 = 21600, 18:00 = 64800; a week
# is days 1/8/15/22 of the 28-day month, a month is its 1st). A per-row type
# never rolls dice, so a per-row item never carries a seed; the sheet has no
# amount field, so a per-row recharge is always ``all``.
RECHARGE_DAWN = 6 * 3600
RECHARGE_DUSK = 18 * 3600
RECHARGE_RULES = {
    "daily": (SECONDS_PER_DAY, RECHARGE_DAWN),
    "dawn": (SECONDS_PER_DAY, RECHARGE_DAWN),
    "dusk": (SECONDS_PER_DAY, RECHARGE_DUSK),
    "weekly": (7 * SECONDS_PER_DAY, RECHARGE_DAWN),
    "monthly": (DAYS_PER_MONTH * SECONDS_PER_DAY, RECHARGE_DAWN),
}


def recharge_rule(entry: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """(rule line, None) for a row whose typed ``rechargeRate`` names a rate,
    (None, None) for ``never`` or no rate, (None, reason) for an unknown value
    (the row then recharges nothing, as before)."""
    rate = entry.get("rechargeRate")
    if rate is None or rate == "never":
        return None, None
    period = RECHARGE_RULES.get(rate) if isinstance(rate, str) else None
    if period is None:
        return None, f"rechargeRate {rate!r} is not a known rate; no recharge declared"
    return f" recharge every {period[0]} at {period[1]} all;\n", None


def charge_state(entry: Dict[str, Any], current: int, maximum: int, recharging: bool,
                 gaps: List[str], label: str) -> str:
    """The item's ``charges`` field. The anchor ``since`` is stated only when
    the TYPE recharges, and a per-row type never rolls, so a stored seed is
    never stated: either on the wrong type refuses the WHOLE world (engine
    rule), so a stale value is dropped with a gap and the item is declared
    unanchored (the engine anchors it at its next spend, no back credit)."""
    charges = entry.get("charges") or {}
    since = ""
    as_of = charges.get("asOf")
    if as_of is not None:
        if not recharging:
            gaps.append(f"{label} carries charges.asOf but no recharge rule; anchor dropped")
        elif type(as_of) is not int or as_of < 0:
            gaps.append(f"{label} has a charges.asOf that is not a whole number of game seconds; anchor dropped")
        else:
            since = f" since {as_of}"
    if charges.get("seed") is not None:
        gaps.append(f"{label} carries a charges.seed but its per-row type never rolls; seed not declared")
    return f"charges {current} of {maximum}{since};"


# Item charges H2b: a catalog row on a charged pack type takes its rule from
# the PACK (the row carries no rechargeRate); a per-row charged item takes it
# from its typed rate. One answer to "does this item's type recharge, and does
# it roll dice" serves genesis, the refresh, the expend guard and the summary.
SEED_MAX = 2 ** 64 - 1
MINT_REASON = "needs a minted seed"


@dataclass
class ChargeRule:
    source: str                    # "pack" (catalog type) or "row" (per-row type)
    maximum: int
    recharges: bool
    uses_dice: bool                # initial dice, recharge dice or an exhausted roll
    period: Optional[int] = None
    offset: Optional[int] = None
    rate: Optional[str] = None     # dawn/dusk/weekly/monthly (or the row's typed rate)
    initial_dice: bool = False


def valid_seed(value: Any) -> Optional[Tuple[int, int]]:
    """(s1, s2) when ``value`` is two whole numbers 0..2^64-1 (the engine's
    seed words), else None: anything else is treated as no seed, because a
    bad word refuses the whole world at compile time."""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    if any(type(word) is not int or not 0 <= word <= SEED_MAX for word in value):
        return None
    return int(value[0]), int(value[1])


def pack_charge_rule(catalog_entry: Any) -> Optional[ChargeRule]:
    """The charge rule of a pack entry (item_catalog.json ``charges``), or None
    for an uncharged type."""
    rule = catalog_entry.get("charges") if isinstance(catalog_entry, dict) else None
    if not isinstance(rule, dict) or type(rule.get("max")) is not int:
        return None
    recharge = rule.get("recharge") if isinstance(rule.get("recharge"), dict) else None
    exhausted = rule.get("exhausted") if isinstance(rule.get("exhausted"), dict) else None
    initial_dice = isinstance(rule.get("initial_dice"), dict)
    uses_dice = (initial_dice or (recharge is not None and isinstance(recharge.get("dice"), dict))
                 or (exhausted is not None and exhausted.get("roll") is not None))
    period = offset = rate = None
    if recharge is not None:
        period, offset = recharge.get("every"), recharge.get("at")
        rate = next((name for name, pair in RECHARGE_RULES.items() if name != "daily" and pair == (period, offset)), None)
        rate = rate or f"every {period} game seconds"
    return ChargeRule("pack", rule["max"], recharge is not None, bool(uses_dice), period, offset, rate, initial_dice)


def charge_rule(entry: Dict[str, Any]) -> Optional[ChargeRule]:
    """How this row's TYPE handles charges: the pack rule for a catalog row,
    the typed rate for a per-row charged item, None for an uncharged row."""
    catalog, _ = item_catalog.row_entry(entry)
    if catalog is not None:
        return pack_charge_rule(catalog)
    charges = entry.get("charges")
    if not isinstance(charges, dict):
        return None
    line, _ = recharge_rule(entry)
    rate = entry.get("rechargeRate") if line else None
    period, offset = RECHARGE_RULES.get(rate, (None, None)) if isinstance(rate, str) else (None, None)
    maximum = charges.get("max")
    return ChargeRule("row", maximum if type(maximum) is int else 0, line is not None, False, period, offset, rate)


def catalog_charge_state(entry: Dict[str, Any], rule: ChargeRule, gaps: List[str],
                         label: str) -> Tuple[Optional[str], Optional[str]]:
    """The charges clause of a row on a charged catalog type, from the row's
    own ``charges`` object (H2b-1): (clause, None) states it; ("", None)
    declares the row from the type without a clause (the engine then uses the
    definition's count: a count-only or uses-per-dawn type starts full,
    unanchored); (None, reason) when the row stands on a DICE type and cannot
    be declared from it yet (no valid seed, a bad object, a max that differs):
    the caller declares it from its own fields (present, held, uncharged) and
    item_charges mints its state in one engine call (M1, M2, S3)."""
    charges = entry.get("charges")
    if rule.uses_dice:
        fallback: Tuple[Optional[str], Optional[str]] = (None, MINT_REASON)
    else:
        fallback = ("", None)
    if not isinstance(charges, dict):
        return fallback
    pair, reason = charges_fields(entry)
    if reason:
        gaps.append(f"{label} {reason}; " + (MINT_REASON if rule.uses_dice else "declared from its type without a count"))
        return fallback
    current, maximum = pair
    if maximum != rule.maximum:
        gaps.append(f"{label} charges.max {maximum} differs from its catalog type's {rule.maximum}; "
                    + (MINT_REASON if rule.uses_dice else "declared from its type without a count"))
        return fallback
    since = ""
    as_of = charges.get("asOf")
    if as_of is not None:
        if not rule.recharges:
            gaps.append(f"{label} carries charges.asOf but its catalog type has no recharge rule; anchor dropped")
        elif type(as_of) is not int or as_of < 0:
            gaps.append(f"{label} has a charges.asOf that is not a whole number of game seconds; anchor dropped")
        else:
            since = f" since {as_of}"
    seed = ""
    if rule.uses_dice:
        words = valid_seed(charges.get("seed"))
        if words is None:
            if charges.get("seed") is not None:
                gaps.append(f"{label} has a charges.seed that is not two whole numbers below 2^64; {MINT_REASON}")
            return None, MINT_REASON
        seed = f" seed {words[0]} {words[1]}"
    elif charges.get("seed") is not None:
        gaps.append(f"{label} carries a charges.seed but its catalog type never rolls; seed not declared")
    return f"charges {current} of {maximum}{since}{seed};", None


def mint_reason(entry: Dict[str, Any]) -> Optional[str]:
    """Why this row's charge state must be minted by the engine before the
    world can declare it from its catalog type, or None (declarable, or not a
    catalog charged row). Value checks only; no gap is recorded."""
    catalog, _ = item_catalog.row_entry(entry)
    rule = pack_charge_rule(catalog) if catalog is not None else None
    if rule is None:
        return None
    return catalog_charge_state(entry, rule, [], "")[1]


def bounded_id(prefix: str, text: str, limit: int = ENGINE_ID_MAX) -> str:
    """``prefix + text`` within ``limit`` bytes (#1004). An id that fits is
    returned unchanged; a longer one keeps the first bytes of ``text`` that
    fit, with trailing "-" stripped."""
    whole = prefix + text
    if len(whole.encode("utf-8")) <= limit:
        return whole
    room = limit - len(prefix.encode("utf-8"))
    return prefix + (text.encode("utf-8")[:room].decode("utf-8", errors="ignore").rstrip("-") or "x")


def character_scope(name: Any) -> str:
    """The slug a character's engine ids carry: its id after "char:", at most
    CHARACTER_SCOPE_MAX bytes so every id it ends fits (#1022). A name with no
    ASCII letter or digit takes "xn--" and the punycode of its file stem (#894),
    so such names no longer all share "x" (#948); a slug never holds "--"."""
    scope = slug(name)
    if scope == "x" and not re.search(r"[a-z0-9]", str(name).lower()):
        from utils.encoding_utils import unicode_name_stem
        stem = unicode_name_stem(name)
        if stem:
            scope = "xn--" + stem.replace("_", "-").encode("punycode").decode("ascii")
    return bounded_id("", scope, CHARACTER_SCOPE_MAX)


def character_id(sheet: Dict[str, Any]) -> str:
    return "char:" + character_scope(sheet.get("name", ""))


def location_id(location: str) -> str:
    return bounded_id("loc:", slug(location))


def container_id(storage_id: str) -> str:
    return bounded_id("container:", slug(storage_id))


def bounded_item_id(iid: str, limit: int = ITEM_ID_MAX) -> str:
    """``iid`` within ``limit`` bytes (#566). An id that fits is returned
    unchanged. A longer one keeps its last two fields (the scope and row
    index that make it unique) and shortens the name part before them. When
    the tail alone cannot fit, the scope is shortened too and the index kept
    (#1004)."""
    if len(iid.encode("utf-8")) <= limit:
        return iid
    parts = iid.split(":")
    if len(parts) < 4:
        return iid
    scope, index = parts[-2], parts[-1]
    tail = ":" + scope + ":" + index
    room = limit - len(tail.encode("utf-8"))
    if room < len("item:x"):
        scope_room = limit - len("item:x") - len(("::" + index).encode("utf-8"))
        if scope_room < 1:
            return iid
        scope = scope.encode("utf-8")[:scope_room].decode("utf-8", errors="ignore").rstrip("-") or "x"
        tail = ":" + scope + ":" + index
        room = limit - len(tail.encode("utf-8"))
    head = ":".join(parts[:-2]).encode("utf-8")[:room].decode("utf-8", errors="ignore").rstrip("-")
    return head + tail


def split_id(base: str, count: int, taken: set) -> str:
    """The id of a part split off ``base``: ``<base>:part:<count>``, or with a
    numbered tail while that id is taken (#1037). ``taken`` holds, as values,
    every id the game holds where the caller could read it (every sheet and
    container) and this request's earlier splits: a part travels between
    sheets and chests that no one world declares together (#1039). The id is
    compared and returned in the bounded form genesis declares, and is added
    to ``taken``."""
    candidate = bounded_item_id(f"{base}:part:{count}", ENGINE_ID_MAX)
    suffix = 1
    while candidate in taken:
        suffix += 1
        candidate = bounded_item_id(f"{base}:part:{count}:{suffix}", ENGINE_ID_MAX)
    taken.add(candidate)
    return candidate


def held_ids(sheets: List[Any], containers: List[Any]) -> set:
    """Every item id these sheets and storage containers hold, as values: each
    sheet row's stored id and ammunition stock, and each container entry's
    stored id (#1039). A row with no stored id is left out: its minted id names
    its own sheet, and that mint steps past the ids held elsewhere (#1060).
    An equipment, ammunition or contents value that is not a list, or a
    container that is not an object, holds nothing: one malformed file never
    stops another sheet's save."""
    def rows(value):
        return value if isinstance(value, list) else []

    held: set = set()
    for sheet in sheets:
        if not isinstance(sheet, dict):
            continue
        for entry in rows(sheet.get("equipment")):
            if isinstance(entry, dict) and isinstance(entry.get("nql_id"), str):
                held.add(bounded_item_id(entry["nql_id"], ENGINE_ID_MAX))
        if isinstance(sheet.get("ammunition"), list):
            held.update(aid for aid, _ in ammunition_rows(sheet, []))
    for container in containers:
        for entry in rows(container.get("contents")) if isinstance(container, dict) else []:
            if isinstance(entry, dict) and isinstance(entry.get("nql_id"), str):
                held.add(bounded_item_id(entry["nql_id"], ENGINE_ID_MAX))
    return held


def held_ids_on_disk(characters_dir: str = "characters", storage_file: str = "player_storage.json") -> set:
    """Every item id the saved game holds, read as values: each sheet in
    ``characters_dir`` (a backup, whose name has a second dot, is not a sheet)
    and every container in ``storage_file``. A new split or minted id is none
    of them (#1039, #1060)."""
    from utils.file_operations import safe_read_json
    sheets = []
    paths = glob.glob(os.path.join(characters_dir, "*.json"))
    # glob never matches a dotfile; a sheet saved before #894 is characters/.json (#1074)
    legacy = os.path.join(characters_dir, ".json")
    if os.path.isfile(legacy):
        paths.append(legacy)
    for path in sorted(paths):
        if "." not in os.path.basename(path)[:-len(".json")]:
            sheets.append(safe_read_json(path))
    data = safe_read_json(storage_file) if os.path.exists(storage_file) else None
    containers = data.get("playerStorage") if isinstance(data, dict) else None
    return held_ids(sheets, containers if isinstance(containers, list) else [])


def ac_effect_id(iid: str, index: int) -> str:
    """The engine id of a worn item's index-th AC effect (#1023):
    effect:<item id after "item:">:ac:<index>. An id that fits is returned
    unchanged; a longer one keeps its ":ac:<index>" tail and shortens the item
    part as bounded_item_id does (scope and row index kept), or by its first
    bytes when the item id has no scope fields."""
    tail = ":ac:%d" % index
    eid = "effect:" + iid.split(":", 1)[1] + tail
    if len(eid.encode("utf-8")) <= ENGINE_ID_MAX:
        return eid
    room = ENGINE_ID_MAX - len(tail)
    item = bounded_item_id(iid, room - len("effect:") + len("item:"))
    if len(("effect:" + item.split(":", 1)[1]).encode("utf-8")) > room:
        return bounded_id("effect:", iid.split(":", 1)[1], room) + tail
    return "effect:" + item.split(":", 1)[1] + tail


def _mint(entry: Dict[str, Any], scope: str, index: int) -> str:
    return bounded_item_id(f"item:{slug(entry.get('item_name', ''))}:{scope}:{index}")


def ammunition_id(sheet: Dict[str, Any], name: str) -> str:
    """The engine stock id of one ammunition row (AM): ammo:<slug(name)>:<scope>.
    Over the engine's bound, the name part is shortened, and the scope only
    when it alone cannot fit (#1004)."""
    scope = character_id(sheet).split(":", 1)[1]
    iid = f"ammo:{slug(name)}:{scope}"
    if len(iid.encode("utf-8")) <= ENGINE_ID_MAX:
        return iid
    if len(f"ammo:x:{scope}".encode("utf-8")) > ENGINE_ID_MAX:
        scope = bounded_id("ammo:x:", scope)[len("ammo:x:"):]
    return bounded_id("ammo:", slug(name), ENGINE_ID_MAX - len(":" + scope)) + ":" + scope


def ammunition_rows(sheet: Dict[str, Any], gaps: List[str]) -> List[Tuple[str, Dict[str, Any]]]:
    """(stock id, row) for every typed ammunition row; a row without a name or integer quantity is a gap."""
    out: List[Tuple[str, Dict[str, Any]]] = []
    seen: set = set()
    cid = character_id(sheet)
    for index, row in enumerate(sheet.get("ammunition") or []):
        if not isinstance(row, dict) or not isinstance(row.get("name"), str) or not row["name"]:
            gaps.append(f"{cid}: ammunition[{index}] has no name; skipped")
            continue
        if _int(row.get("quantity")) is None or row["quantity"] < 0:
            gaps.append(f"{cid}: ammunition {row['name']!r} has no non-negative integer quantity; skipped")
            continue
        iid = ammunition_id(sheet, row["name"])
        if iid in seen:
            gaps.append(f"{cid}: duplicate ammunition row {row['name']!r}; skipped")
            continue
        seen.add(iid)
        out.append((iid, row))
    return out


def _entry_id(entry: Dict[str, Any], scope: str, index: int) -> str:
    existing = entry.get("nql_id")
    if isinstance(existing, str) and existing.startswith("item:"):
        # Every stored id the engine takes is returned as it is (#566).
        return bounded_item_id(existing, ENGINE_ID_MAX)
    return _mint(entry, scope, index)


def assign_ids(sheet: Dict[str, Any], reserved: Optional[set] = None) -> bool:
    """Write a nql_id onto every equipment entry that lacks one. Returns True if any was added.

    A minted id also steps past ``reserved``, the ids held where this sheet
    cannot see them (every sheet and chest, read as values): a row index is
    reused once a row leaves the sheet, and its old id may sit in a chest or
    on another sheet (#1060)."""
    held = reserved or ()
    changed = False
    seen = set()
    scope = character_scope(sheet.get("name", ""))
    for index, entry in enumerate(sheet.get("equipment") or []):
        if not isinstance(entry, dict) or not entry.get("item_name"):
            continue
        current = entry.get("nql_id")
        if isinstance(current, str) and current.startswith("item:"):
            # A stored id over the engine's bound refuses the whole world;
            # it is shortened in place, and a clash is reminted below (#566).
            bounded = bounded_item_id(current, ENGINE_ID_MAX)
            if bounded != current:
                entry["nql_id"] = current = bounded
                changed = True
        if not (isinstance(current, str) and current.startswith("item:")) or current in seen:
            candidate = _mint(entry, scope, index)
            while candidate in seen or candidate in held:
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


HIT_DICE_FIELD = "hitDice"  # {"d<N>": remaining}; written only from the engine's status


def hit_dice_resource_id(die: int) -> str:
    return f"hitdice:d{die}"


def hit_die(sheet: Dict[str, Any]) -> Optional[int]:
    """The sheet's class hit die size (leveling tables), or None without a known class."""
    cls = leveling_tables.class_key(sheet)
    return leveling_tables.hit_die(cls) if cls else None


def pool_resources(sheet: Dict[str, Any], gaps: List[str]) -> List[Tuple[str, int, int]]:
    """(resource id, current, max) for hit points, spell slots, feature use and hit dice pools.

    Typed fields only: ``hitPoints``/``maxHitPoints``, ``spellcasting.spellSlots.levelN``
    ``{current, max}``, ``classFeatures[].usage {current, max}`` and then
    ``feats[].usage`` (#891; a feat whose id a class feature holds is a gap), and
    ``hitDice {"d<N>": remaining}`` for the class hit die with the level as its maximum
    (a sheet without the field starts full). A pool the sheet does not carry is simply
    absent; a spend against it is then a compile refusal.
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
    for feature in list(sheet.get("classFeatures") or []) + list(sheet.get("feats") or []):
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
    die, level = hit_die(sheet), _int(sheet.get("level"))
    if die and level and level > 0:
        stored = sheet.get(HIT_DICE_FIELD) if isinstance(sheet.get(HIT_DICE_FIELD), dict) else {}
        p = _pool(cid, f"{HIT_DICE_FIELD}.d{die}", stored.get(f"d{die}", level), level, gaps)
        if p is not None:
            out.append((hit_dice_resource_id(die), p[0], p[1]))
    return out



def hit_die_ability_id(die: int) -> str:
    return f"hit-die-d{die}"


# The hit-die world (7b-host). A rolled Ability needs a native Battle profile,
# which the full world cannot hold (its ammunition recovery rule, ranged weapon
# pack and concentration check are world-level policies a Battle declares
# itself), so the hit dice a short rest spends are rolled in this small world:
# per character the Constitution stat and the hit point and hit dice pools,
# the party relation, the Battle (health "hp", the party root, a fresh seed per
# request) and one Ability per die size. The Ability spends one die from the
# target's pool and heals the target 1d<N> + Constitution modifier, at least 1.
HIT_DIE_ABILITY = """ability %(id)s named %(name)s {
 parameter "actor" character;
 parameter "target" character;
 action actor param "actor" phase exploration;
 spend param "target" resource %(pool)s by 1;
 roll heal param "target" resource "hp" dice 1 sides %(die)d min 1 bonus from param "target" {
  constant 0;
  term stat "constitution" offset -10 divide 2;
 };
}"""


def hit_die_world(sheets: List[Dict[str, Any]], root: str, location: str, clock_tick: int,
                  seed: Tuple[int, int]) -> Genesis:
    """The hit-die world for these sheets; ``root`` is the party root's character id (the player)."""
    gaps: List[str] = []
    loc = location_id(location)
    lines: List[str] = [
        "// Generated by core/nql/genesis.py for a short rest's hit dice. Typed fields only.",
        "rules { transfer unequips; wear any; }",
        f'clock "second" at {int(clock_tick)};',
        f"location {_q(loc)} named {_q(location)};",
    ]
    character_ids: Dict[str, str] = {}
    dice: set = set()
    for sheet in sheets:
        cid = character_id(sheet)
        con = _int((sheet.get("abilities") or {}).get("constitution"))
        die = hit_die(sheet)
        pool = hit_dice_resource_id(die) if die else None
        pools = [(rid, cur, mx) for rid, cur, mx in pool_resources(sheet, gaps) if rid in ("hp", pool)]
        if con is None or not any(rid == "hp" for rid, _, _ in pools):
            gaps.append(f"{cid}: no Constitution score or hit points; not in the hit-die world")
            continue
        character_ids[sheet.get("name", "")] = cid
        if any(rid == pool for rid, _, _ in pools):
            dice.add(die)
        lines.append(f"character {_q(cid)} named {_q(sheet.get('name', ''))} at {_q(loc)} {{\n"
                     f' stat "constitution" = {con};\n'
                     + "".join(f" resource {_q(rid)} = {cur} min 0 max {mx};\n" for rid, cur, mx in pools) + "}")
    for cid in sorted(set(character_ids.values()) - {root}):
        lines.append(f'relation character {_q(cid)} "party-member" character {_q(root)} = 1;')
    lines.append(f"equipment {_q(EQUIPMENT_VERSION)} {{ slot \"hand\" capacity 2; }}")
    lines.append('battle "nql-battle-v1" {\n health "hp";\n defense "defense";\n initiative "initiative";\n'
                 f' party {_q(root)} relation "party-member" strength 1;\n'
                 ' roll sides 20 miss 1 critical 20 multiply 2;\n grid "feet" square 5;\n clock "second" round 6;\n'
                 f" seed {int(seed[0])} {int(seed[1])};\n zero protected stable_down opposition dead;\n"
                 + "".join(f" action {_q(hit_die_ability_id(die))};\n" for die in sorted(dice)) + "}")
    for die in sorted(dice):
        lines.append(HIT_DIE_ABILITY % {"id": _q(hit_die_ability_id(die)), "name": _q(f"Hit die (d{die})"),
                                        "pool": _q(hit_dice_resource_id(die)), "die": die})
    return Genesis(source="\n".join(lines) + "\n", location=loc, character_ids=character_ids, gaps=gaps)


def live_effects(sheet: Dict[str, Any]) -> List[Dict[str, Any]]:
    """The sheet's temporary effects that the runtime renders (typed author field)."""
    return [e for e in sheet.get("temporaryEffects") or []
            if isinstance(e, dict) and e.get("authoredBy") in EFFECT_AUTHORS
            and isinstance(e.get("modifiers"), list) and isinstance(e.get("effectId"), str) and e["effectId"]]


def effect_engine_modifiers(effect: Dict[str, Any]) -> Optional[List[Tuple[str, int]]]:
    """The engine-representable modifiers of one effect: [("defense" | "defense-floor" | "hp-max" | "saves" |
    "save:<ability>", amount)]. A "defense-floor" is an armor class floor (#1434), never an addend.

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
        if isinstance(modifier, dict) and modifier.get("stat") == "armorClass" and type(modifier.get("atLeast")) is int:
            out.append(("defense-floor", modifier["atLeast"]))  # #1434: Barkskin's `at least` bound
            continue
        if not isinstance(modifier, dict) or type(modifier.get("value")) is not int or modifier["value"] == 0:
            continue
        stat = modifier.get("stat")
        if stat == "armorClass":
            out.append(("defense", modifier["value"]))
        elif stat == "maxHitPoints" or (stat == "hitPoints" and modifier.get("affectsMax") is True):
            out.append(("hp-max", modifier["value"]))
            hp_max_total += modifier["value"]
        elif stat == "savingThrows":
            # CS: a flat bonus to every saving throw reaches the engine's save totals.
            out.append(("saves", modifier["value"]))
        elif isinstance(stat, str) and stat.startswith("savingThrow.") and stat[12:] in ABILITY_NAMES:
            out.append(("save:" + stat[12:], modifier["value"]))
    if hp_max_total and any(k == "hp-max" and (v > 0) != (hp_max_total > 0) for k, v in out):
        # One instance's maximum modifiers must all raise or all drain.
        return None
    return out


AC_SET_RECIPE_PREFIX = "ac-set:"


def ac_set_recipe_name(type_id: str) -> str:
    """The defense recipe of a declared set effect type: effect:<id>[:<scope>] -> ac-set:<id>[:<scope>]."""
    return AC_SET_RECIPE_PREFIX + type_id[len("effect:"):]


def ac_set_instance_id(recipe_name: str) -> Optional[str]:
    """The holder's condition instance behind a chosen set recipe (#1408: scoped for a repeat holder):
    ac-set:<id>[:<scope>] -> fx:<id>[:<scope>]; None for any other recipe name."""
    if not (isinstance(recipe_name, str) and recipe_name.startswith(AC_SET_RECIPE_PREFIX)):
        return None
    return "fx:" + recipe_name[len(AC_SET_RECIPE_PREFIX):]


def ac_recipe(name: str, base: int, abilities: List[str], requires: str, shield_allowed: bool = True) -> str:
    """#1433: one gated alternative recipe of the defense derive, eligible while its holder has
    ``requires`` and wears no body armor (nor a shield when the rule forbids one): base plus each
    ability's modifier. The engine picks the highest total and adds modifiers once (D-KW-8)."""
    gate = ' unless slot "body"' + ('' if shield_allowed else ' unless slot "shield"')
    terms = "".join(f' term stat {_q(a)} offset -10 divide 2;' for a in abilities)
    return f' recipe {_q(name)} base {base} requires {_q(requires)}{gate} {{{terms} }}'


def feature_defense_recipes(declared: List[str]) -> str:
    """#1433: the alternative recipe of each class formula outside Unarmored Defense (Draconic
    Resilience) whose condition type this world declares, which it does only when a sheet holds it."""
    out = []
    for cls, _, feature, _, base, abilities, shield_allowed in class_conditions.recipe_formulas():
        tid = class_conditions.ac_formula_type(cls, feature)
        if tid in declared:
            out.append(ac_recipe(class_conditions.ac_formula_recipe(cls, feature), base, abilities, tid, shield_allowed))
    return "".join(out)


def effect_defense_recipes(sheets: List[Dict[str, Any]], gaps: Optional[List[str]] = None,
                           ids: Optional[Dict[Tuple[str, str], Tuple[str, str]]] = None) -> str:
    """#1322: the defense derive's gated alternative recipe for each live set effect (Mage Armor:
    base AC 13 + Dexterity while no body armor is worn), eligible while its holder has the effect's
    own condition. The engine picks the highest total and adds modifiers once, so Mage Armor never
    stacks with Unarmored Defense or armor (D-KW-8). Empty when no set effect is live, so every
    other world is unchanged. A live set rule that is not {base 0-30, plusAbility ability or null}
    declares no recipe and is reported in ``gaps``, never dropped silently.

    #1408: one recipe per declared condition type. ``ids`` is the world's (char id, effectId) -> (type
    id, instance id) map, so a repeat holder of a shared effectId gets its own recipe
    ``ac-set:<id>:<scope>`` requiring its own scoped type; an effect the world did not declare gets none.
    Without ``ids`` (a direct call on one sheet) the type id is main's ``effect:<id>``."""
    out: List[str] = []
    seen: set = set()
    for sheet in sheets:
        cid = character_id(sheet)
        for effect in live_effects(sheet):
            if effect_engine_modifiers(effect) is None:
                continue  # _effect_lines declares no type for it
            rule = next((m["set"] for m in effect["modifiers"] if isinstance(m, dict) and "set" in m), None)
            if ids is None:
                tid = effect_type_id(effect)
            elif (cid, effect["effectId"]) in ids:
                tid = ids[(cid, effect["effectId"])][0]
            else:
                continue  # not declared in this world (a colon id, an in-sheet repeat)
            if rule is None or tid in seen:
                continue
            ability = rule.get("plusAbility") if isinstance(rule, dict) else None
            if not (isinstance(rule, dict) and not set(rule) - {"base", "plusAbility"}
                    and type(rule.get("base")) is int and 0 <= rule["base"] <= 30
                    and (ability is None or ability in ABILITY_NAMES)):
                if gaps is not None:
                    gaps.append(f"{character_id(sheet)}: effect {effect.get('name')!r} has a malformed armorClass "
                                f"set rule {rule!r}; no recipe declared")
                continue
            seen.add(tid)
            out.append(ac_recipe(ac_set_recipe_name(tid), rule["base"], [ability] if ability else [], tid))
    return "".join(out)


def _die_engine_stat(stat: Any) -> Optional[str]:
    """The engine stat an added die names (#889): saves and ability checks.
    Attack-roll dice are not the engine's: code rolls them in combat."""
    if not isinstance(stat, str):
        return None
    if stat == "savingThrows":
        return "bonus:saves"
    if stat == "abilityChecks":
        return "bonus:checks"
    if stat.startswith("savingThrow.") and stat[12:] in ABILITY_NAMES:
        return "save:" + stat[12:]
    if stat.startswith("abilityCheck.skill.") and stat[19:] in srd_stats.SKILLS:
        return "skill:" + stat[19:]
    return None


def unrolled_die_stats(effect: Dict[str, Any]) -> List[str]:
    """The stats an effect's added dice name that nobody rolls (#889 fail forward: the effect
    applies without them). Attack-roll dice are code's, so they are not listed."""
    return [str(m.get("stat")) for m in effect.get("modifiers") or []
            if isinstance(m, dict) and isinstance(m.get("die"), str)
            and m.get("stat") != "attackRolls" and _die_engine_stat(m.get("stat")) is None]


def effect_engine_dice(effect: Dict[str, Any]) -> List[Tuple[str, int, int]]:
    """[(engine stat, count, sides)] for the effect's added dice (#889: Bless
    1d4 on saves, Guidance 1d4 on one skill). effect_engine_modifiers never
    reads them, so every flat-number consumer is unchanged."""
    out: List[Tuple[str, int, int]] = []
    for modifier in effect.get("modifiers") or []:
        if not isinstance(modifier, dict) or not isinstance(modifier.get("die"), str):
            continue
        engine_stat = _die_engine_stat(modifier.get("stat"))
        if engine_stat is not None and _MODIFIER_DIE.fullmatch(modifier["die"]):
            count, sides = modifier["die"].split("d")
            out.append((engine_stat, int(count), int(sides)))
    return out


def effect_type_id(effect: Dict[str, Any], scope: Optional[str] = None) -> str:
    return "effect:" + str(effect.get("effectId")) + (":" + scope if scope else "")


def effect_instance_id(effect: Dict[str, Any], scope: Optional[str] = None) -> str:
    return "fx:" + str(effect.get("effectId")) + (":" + scope if scope else "")


def world_effect_ids(world: "Genesis", cid: str, effect: Dict[str, Any]) -> Tuple[str, str]:
    """(type id, instance id) the world declared for this holder's effect (#1408); main's ids for an
    effect the world did not declare (an in-sheet repeat, which is skipped)."""
    return world.effect_ids.get((cid, str(effect.get("effectId"))),
                                (effect_type_id(effect), effect_instance_id(effect)))


def effect_first_holders(sheets: List[Dict[str, Any]]) -> Dict[str, str]:
    """#1408: effectId -> the first holder among the world's sheets, by sorted character id (never the
    caller's order), so the same sheets give every holder the same ids in any order. Sheets with a
    repeated character id count once, as build_world declares them."""
    holders: Dict[str, set] = {}
    cids: set = set()
    for sheet in sheets:
        cid = character_id(sheet)
        if cid in cids:
            continue
        cids.add(cid)
        for effect in live_effects(sheet):
            holders.setdefault(effect["effectId"], set()).add(cid)
    return {eid: min(found) for eid, found in holders.items()}


def effect_type_line(effect: Dict[str, Any], modifiers: List[Tuple[str, int]],
                     dice: Tuple[Tuple[str, int, int], ...] = (), type_id: Optional[str] = None) -> str:
    parts = []
    for index, (kind, amount) in enumerate(modifiers):
        if kind == "defense":
            parts.append(f'modifier "m{index}" stat "defense" add {amount};')
        elif kind == "defense-floor":
            parts.append(f'modifier "m{index}" stat "defense" at least {amount};')
        elif kind == "saves":
            parts.append(f'modifier "m{index}" stat "bonus:saves" add {amount};')
        elif kind.startswith("save:"):
            parts.append(f'modifier "m{index}" stat {_q(kind)} add {amount};')
        else:
            parts.append(f'modifier "m{index}" resource "hp" maximum add {amount};')
    for index, (stat, count, sides) in enumerate(dice):
        parts.append(f'modifier "d{index}" stat {_q(stat)} die {count} {sides};')
    return f"condition type {_q(type_id or effect_type_id(effect))} {{ instances unique; {' '.join(parts)} }}"


def _effect_lines(sheet: Dict[str, Any], cid: str, gaps: List[str],
                  names: Dict[str, str], clock_tick: Optional[int] = None,
                  first_holders: Optional[Dict[str, str]] = None,
                  ids: Optional[Dict[Tuple[str, str], Tuple[str, str]]] = None,
                  notes: Optional[List[str]] = None) -> Tuple[List[str], List[str]]:
    """(condition type lines, instance lines) for the sheet's effects.

    A type is declared for every live effect the engine can hold, so a later
    ``apply condition`` in the same world has it; an instance is declared only
    for an effect marked engineOwned (already inside the stored numbers). With
    a ``clock_tick`` (the world's clock), an owned effect with an expiresTick
    is timed: ``ticks expiresTick - clock_tick`` (at least 1, so an effect
    already due ends on the first advance).

    #1408: an effectId another sheet in the world also holds keeps main's ids for its first holder
    (``first_holders``, by sorted character id); every other holder declares its own scoped type and
    instance, ``effect:<id>:<scope>`` and ``fx:<id>:<scope>``, so the world boots and each holder keeps
    its own numbers. The ids go into ``ids``.
    """
    types: List[str] = []
    instances: List[str] = []
    seen: set = set()
    dice_names: set = set()
    for effect in live_effects(sheet):
        modifiers = effect_engine_modifiers(effect)
        if modifiers is None:
            if effect.get(EFFECT_ENGINE_OWNED):
                gaps.append(f"{cid}: effect {effect.get('name')!r} is marked engineOwned but the engine cannot hold its modifiers")
            continue
        # An effect with no engine numbers (a potion's temp hit points, a
        # condition, a speed bonus) is still an instance: the engine clock
        # owns its expiry and a rest or removal ends it like any other.
        eid = effect["effectId"]
        if ":" in eid:
            # A scoped id is "<effectId>:<scope>"; an effectId with a colon could collide with one.
            gaps.append(f"{cid}: effect {effect.get('name')!r} has effectId {eid!r} with a colon; not declared")
            continue
        if eid in seen:
            gaps.append(f"{cid}: effect {effect.get('name')!r} repeats effectId {eid!r}; second declaration skipped")
            continue
        seen.add(eid)
        first = (first_holders or {}).get(eid, cid)
        scope = cid.split(":", 1)[1] if first != cid else None
        if scope and notes is not None:
            notes.append(f"{cid}: effect {effect.get('name')!r} shares effectId {eid!r} with {first}; "
                         f"declared under its own scoped ids")
        tid = effect_type_id(effect, scope)
        # #889: an engineOwned effect's added dice; the same spell's effects
        # do not combine, so among one name only the first carries them
        # (owner D-889b-neq-1, as core.effects.effective.modifier_dice).
        dice: Tuple[Tuple[str, int, int], ...] = ()
        if effect.get(EFFECT_ENGINE_OWNED) is True:
            dice = tuple(effect_engine_dice(effect))
            unrolled = unrolled_die_stats(effect)
            if unrolled:
                # Fail forward: the effect applies without that die.
                gaps.append(f"{cid}: effect {effect.get('name')!r} adds a die on {', '.join(unrolled)}, "
                            "which the engine does not roll; the effect applies without it")
            key = _effect_name_key(effect)
            if dice and key is not None:
                if key in dice_names:
                    dice = ()
                else:
                    dice_names.add(key)
        types.append(effect_type_line(effect, modifiers, dice, tid))
        iid = effect_instance_id(effect, scope)
        if ids is not None:
            ids[(cid, eid)] = (tid, iid)
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
        for cond in _ARMOR_TRAINING.get(str(label).strip().lower(), ()):
            if cond not in out:
                out.append(cond)
    return out


def _has_defense_style(sheet: Dict[str, Any]) -> bool:
    return any(f.get("name") == DEFENSE_STYLE_FEATURE for f in sheet.get("classFeatures") or [] if isinstance(f, dict))


def has_great_weapon_style(sheet: Dict[str, Any]) -> bool:
    return isinstance(sheet, dict) and any(
        f.get("name") == GREAT_WEAPON_STYLE_FEATURE for f in sheet.get("classFeatures") or [] if isinstance(f, dict))


def _has_archery_style(sheet: Dict[str, Any]) -> bool:
    return any(f.get("name") == ARCHERY_STYLE_FEATURE for f in sheet.get("classFeatures") or [] if isinstance(f, dict))


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
    style = f'   modifier {_q(DEFENSE_STYLE_MEMBER)} stat "defense" add 1 requires {_q(DEFENSE_STYLE_CONDITION)};\n'
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


def ac_effect_lines(iid: str, entry: Dict[str, Any], seen: Optional[set] = None,
                    gaps: Optional[List[str]] = None, cid: str = "") -> List[str]:
    """Worn-item defense effects from the entry's typed effects list.

    An effect of type "bonus" whose target names armor class and whose value is
    an integer becomes a while-worn engine effect on the item, so a ring of
    protection counts only while worn and is explained by its item. With
    ``seen``, an effect id already in the world is a gap and is skipped (#1023).
    """
    out: List[str] = []
    for index, effect in enumerate(entry.get("effects") or []):
        if (isinstance(effect, dict) and effect.get("type") == "bonus"
                and effect.get("target") in AC_EFFECT_TARGETS and type(effect.get("value")) is int
                and effect["value"] != 0):
            eid = ac_effect_id(iid, index)
            if seen is not None:
                if eid in seen:
                    if gaps is not None:
                        gaps.append(f"{cid}: duplicate AC effect id {eid} for {iid}; effect skipped")
                    continue
                seen.add(eid)
            out.append(f'effect {_q(eid)} from item {_q(iid)} on worn {_q(iid)} stat "defense" add {effect["value"]};')
    return out


def weapon_proficiency_condition(entry: Dict[str, Any]) -> str:
    """prof:weapon:<slug>, the Condition type a catalog weapon's attacks name
    for proficiency; a magic weapon uses its base weapon's (``weapon_base``)."""
    return "prof:weapon:" + str(entry.get("weapon_base") or entry["id"]).split("/", 1)[1]


def _monk_weapon(entry: Dict[str, Any], rules: List[Dict[str, Any]]) -> bool:
    """True when one of the Monk's typed rules (category, kind, optional
    property_any) matches the weapon block."""
    weapon = entry["weapon"]
    names = {p["name"] for p in weapon["properties"]}
    return any(r.get("category") == weapon["category"] and r.get("kind") == weapon["kind"]
               and (not r.get("property_any") or names & set(r["property_any"])) for r in rules)


def _martial_arts_upgrades(indent: str) -> str:
    return "".join("%sor dice 1 sides %d requires %s%s\n" % (indent, sides, _q(kind), UNARMORED_GATE)
                   for sides, kind in MARTIAL_ARTS_DICE)


def _weapon_profile(mode: Dict[str, Any], ability: str) -> str:
    if mode["attack"] == "melee":
        return "melee reach %d stat %s;" % (mode["reach"], _q(ability))
    reach = mode["range"]
    if mode["attack"] == "thrown":
        return "thrown normal %d maximum %d stat %s;" % (reach["normal"], reach["long"], _q(ability))
    return "ranged normal %d maximum %d stat %s ammunition from %s;" % (
        reach["normal"], reach["long"], _q(ability), _q(mode["ammunition_type"]))


def _weapon_attack(attack_id: str, name: str, mode: Dict[str, Any], ability: str, bonus: int,
                   prof: str, gate: str, monk: bool) -> str:
    damage = mode["damage"]
    hit = "constant %d; %s %s" % (bonus, WEAPON_ABILITY_TERM % ability, WEAPON_PROFICIENCY_TERM % _q(prof))
    if mode["attack"] == "ranged":
        hit += ARCHERY_TERM
    if "flat" in damage:
        roll = "damage %s flat { constant %d; %s }" % (_q(damage["kind"]), damage["flat"] + bonus, WEAPON_ABILITY_TERM % ability)
    else:
        roll = "damage %s dice %d sides %d { constant %d; %s }" % (
            _q(damage["kind"]), damage["count"], damage["sides"], bonus, WEAPON_ABILITY_TERM % ability)
    return ("   attack %s named %s%s {\n    hit { %s }\n    %s\n%s    %s\n   }\n"
            % (_q(attack_id), _q(name), gate, hit, roll, _martial_arts_upgrades("     ") if monk else "",
               _weapon_profile(mode, ability)))


def _weapon_definition(entry: Dict[str, Any], monk_rules: List[Dict[str, Any]]) -> str:
    """One immutable definition per catalog weapon, from its typed weapon block
    (the pack's catalog_equipment.weapon_definition, ported): a mode per hand
    use, with an attack per ability for each attack mode. A Monk weapon's
    attacks take the Martial Arts die as upgrades, and a mode without a
    Dexterity attack gains one gated on Martial Arts. Raises ValueError on a
    block the engine cannot take (two hand counts for one mode, an attack mode
    that is not an engine grant)."""
    weapon = entry["weapon"]
    bonus = (entry.get("magic_bonus") or {}).get("attack", 0)
    prof = weapon_proficiency_condition(entry)
    monk = _monk_weapon(entry, monk_rules)
    modes: Dict[str, Dict[str, Any]] = {}
    for mode in weapon["attack_modes"]:
        modes.setdefault(mode["mode"], {"hands": mode["hands"], "attacks": []})
        if modes[mode["mode"]]["hands"] != mode["hands"]:
            raise ValueError("%s: mode %s with two hand counts" % (entry["id"], mode["mode"]))
        if mode["engine"] != "shared":
            raise ValueError("%s: attack mode %s is not an engine grant" % (entry["id"], mode["attack"]))
        abilities = list(mode["abilities"])
        gated = ["dexterity"] if monk and "dexterity" not in abilities else []
        for ability in abilities + gated:
            attack_id = "%s-%s" % (mode["attack"], ability)
            parts = (([] if mode["attack"] == "melee" else [mode["attack"]]) + [ability.capitalize()]
                     + (["two-handed"] if mode["mode"] == "two-handed" else [])
                     + (["Martial Arts"] if ability in gated else []))
            label = "%s (%s)" % (entry["name"], ", ".join(parts))
            gate = (" requires %s%s" % (_q(MARTIAL_ARTS_CONDITION), UNARMORED_GATE)) if ability in gated else ""
            modes[mode["mode"]]["attacks"].append(_weapon_attack(attack_id, label, mode, ability, bonus, prof, gate, monk))
    text = ' definition %s named %s {\n  description "Weapon.";\n  default "held";\n' % (_q(entry["equipment"]), _q(entry["name"]))
    for mode_id, mode in modes.items():
        text += '  mode %s {\n   occupy "hand" by %d;\n%s  }\n' % (_q(mode_id), mode["hands"], "".join(mode["attacks"]))
    return text + " }\n"


def _hands_taken(worn: bool, mode: Optional[str], hands_free: Optional[int], iid: str, entry: Dict[str, Any],
                 cid: str, gaps: List[str], carried: Optional[Dict[str, str]]) -> bool:
    """#960: an equipped untyped held row (a weapon or a shield) when both hands
    are already taken is declared carried, not worn, with a gap naming it, and
    recorded in ``carried`` (the sheet row stays equipped). Returns ``worn``."""
    if worn and mode == "held" and hands_free is not None and hands_free < 1:
        gaps.append(f"{cid}: {entry.get('item_name')!r} is equipped but both hands are taken; "
                    "declared carried, not worn")
        if carried is not None:
            carried[iid] = cid
        return False
    return worn


def _item_line(iid: str, entry: Dict[str, Any], owner: str, custody: str, worn: bool,
               definitions: List[str], gaps: List[str], cid: str,
               charged: Optional[Tuple[List[str], set]] = None,
               hands_free: Optional[int] = None,
               carried: Optional[Dict[str, str]] = None) -> Tuple[str, Optional[str], int]:
    """One item declaration. Returns (line, mode-if-held, hands it holds).

    ``hands_free`` (NUM-H3a) is the hands left for an equipped catalog weapon,
    whose held mode states its own hand count: one that would overfill them is
    declared carried (custody kept, not worn), with a gap naming it, and
    recorded in ``carried``. An untyped held row holds one hand; with none
    free it is declared carried the same way (#960, _hands_taken).

    ``charged`` is (item type lines, type ids already used) for the world; a
    non-catalog row with an acceptable ``charges`` object (charges_fields) is
    declared ``from`` a per-row item type that carries ``charges max`` (item
    charges H1). Everything else is declared exactly as before.
    """
    quantity = _int(entry.get("quantity"))
    item_type = entry.get("item_type")
    definition = None
    mode = None
    catalog, catalog_gap = item_catalog.row_entry(entry)
    clause = ""
    own_fields = False
    if catalog is not None:
        # H2b: a row on a charged catalog type states its own count, anchor
        # and seed from its charges object; a row on a DICE type that has no
        # valid state yet cannot be declared from the type (that refuses the
        # whole world), so it is declared from its own fields below, present
        # and held, until item_charges mints its state (M1, M2).
        rule = pack_charge_rule(catalog)
        if rule is not None:
            clause, mint = catalog_charge_state(entry, rule, gaps, f"{cid}: {entry.get('item_name')!r}")
            if mint:
                gaps.append(f"{cid}: {entry.get('item_name')!r} ({catalog['id']}) {mint}; declared from its own fields")
                catalog, clause, own_fields = None, "", True
    if catalog is not None:
        # A catalog row (GP): the pack's type supplies name, description and
        # equipment, and an item `from` a type may not add a definition of
        # its own. A catalog armor row therefore gets no per-row definition;
        # the shared gear:srd/<slug> one declared for every world carries its AC.
        mode = item_catalog.equipment_mode(catalog)
        if worn and mode is None:
            gaps.append(f"{cid}: {entry.get('item_name')!r} ({catalog['id']}) is equipped but its catalog type has no equipment; item left unworn")
            worn = False
        if worn and quantity not in (None, 1):
            gaps.append(f"{cid}: {entry.get('item_name')!r} is equipped with quantity {quantity}; the engine wears exactly one, item left unworn")
            worn = False
        hands = item_catalog.held_hands(catalog) if mode == "held" else 0
        if worn and hands_free is not None and mode == "held" and catalog.get("kind") == "weapon" and hands > hands_free:
            gaps.append(f"{cid}: {entry.get('item_name')!r} ({catalog['id']}) is equipped but holds in {hands} hands "
                        f"and {max(hands_free, 0)} are free; declared carried, not worn")
            worn = False
            if carried is not None:
                carried[iid] = cid
        fields = [f"owner {_q(owner)};", custody]
        if worn:
            fields.append(f"wearer {_q(cid)};")
            fields.append(f"mode {_q(mode)};")
        if quantity is not None and quantity != 1:
            fields.append(f"quantity {quantity};")
        if clause:
            fields.append(clause)
        return (f"item {_q(iid)} from {_q(catalog['id'])} {{ {' '.join(fields)} }}", (mode if worn else None),
                (hands if worn and mode == "held" else 0))
    if catalog_gap:
        gaps.append(f"{cid}: {entry.get('item_name')!r} {catalog_gap}; declared from its own fields")
    # A row awaiting its mint keeps its charges object for the mint, but it is
    # not declared as a per-row charged type (its rule is the pack's).
    if charged is not None and isinstance(entry.get("charges"), dict) and not own_fields:
        pair, reason = charges_fields(entry)
        type_id = charged_type_id(iid)
        if reason:
            gaps.append(f"{cid}: {entry.get('item_name')!r} {reason}; declared without charges")
        elif pair is not None and type_id in charged[1]:
            gaps.append(f"{cid}: {entry.get('item_name')!r} repeats charged type {type_id}; declared without charges")
        elif pair is not None and len(type_id.encode("utf-8")) > TYPE_KIND_MAX:
            gaps.append(f"{cid}: {entry.get('item_name')!r} has a name too long for a charged type id; declared without charges")
        elif pair is not None:
            current, maximum = pair
            mode = "held" if item_type == "weapon" else "worn"
            kind = entry.get("item_subtype") or item_type or "other"
            if len(str(kind).encode("utf-8")) > TYPE_KIND_MAX:
                kind = item_type if item_type and len(str(item_type).encode("utf-8")) <= TYPE_KIND_MAX else "other"
            label = f"{cid}: {entry.get('item_name')!r}"
            rule, rule_gap = recharge_rule(entry)
            if rule_gap:
                gaps.append(f"{label} {rule_gap}")
            charged[1].add(type_id)
            charged[0].append(_item_type_text(type_id, entry['item_name'], _type_description(entry), kind,
                                              entry.get('magical') is True, False, 'gear:' + mode,
                                              f" charges {maximum};\n{rule or ''}"))
            if worn and quantity not in (None, 1):
                gaps.append(f"{cid}: {entry.get('item_name')!r} is equipped with quantity {quantity}; the engine wears exactly one, item left unworn")
                worn = False
            worn = _hands_taken(worn, mode, hands_free, iid, entry, cid, gaps, carried)
            fields = [f"owner {_q(owner)};", custody]
            if worn:
                fields.append(f"wearer {_q(cid)};")
                fields.append(f"mode {_q(mode)};")
            if quantity is not None and quantity != 1:
                fields.append(f"quantity {quantity};")
            fields.append(charge_state(entry, current, maximum, rule is not None, gaps, label))
            return (f"item {_q(iid)} from {_q(type_id)} {{ {' '.join(fields)} }}", (mode if worn else None),
                    (1 if worn and mode == "held" else 0))
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
    worn = _hands_taken(worn, mode, hands_free, iid, entry, cid, gaps, carried)
    fields = [f"owner {_q(owner)};", custody]
    if worn:
        fields.append(f"wearer {_q(cid)};")
    if definition:
        fields.append(f"definition {_q(definition)};")
    if worn and mode:
        fields.append(f"mode {_q(mode)};")
    if quantity is not None and quantity != 1:
        fields.append(f"quantity {quantity};")
    return (f"item {_q(iid)} named {_q(entry['item_name'])} {{ {' '.join(fields)} }}", (mode if worn else None),
            (1 if worn and mode == "held" else 0))


DAMAGE_TRAITS_LAW = 'attacks { defense "defense"; health "hp"; die 20; miss 1; critical 20; critical dice 2; }'


def _trait_lines(sheet: Dict[str, Any]) -> List[str]:
    from core.nql import attacks
    return attacks.trait_lines(sheet)


def build_world(sheets: List[Dict[str, Any]], location: str, location_name: str = "",
                containers: Optional[List[Dict[str, Any]]] = None, contents_owner: Optional[str] = None,
                definition_entries: Optional[List[Tuple[str, Dict[str, Any]]]] = None,
                clock_tick: Optional[int] = None, dice_seed: Optional[Tuple[int, int]] = None,
                damage_traits: bool = False, reserved: Optional[set] = None,
                *, module_ids: Optional[List[str]] = None) -> Genesis:
    """Return the NQL world source for these sheets and storage containers at one location.

    ``containers`` are player_storage.json container records at this location. Their
    contents are declared in the container's custody and owned by ``contents_owner``
    (a character id; legacy storage records no owner and the acting character is the
    only party that can retrieve, so the caller passes that character).
    ``clock_tick`` declares the world clock (game seconds) so owned timed effects
    carry their remaining ticks and ``advance time`` can end them; without it the
    world has no clock and every instance is untimed (coin, item and rest flows).
    ``damage_traits`` (K1, a rider's typed damage) declares the world `attacks`
    law and each sheet's resist/vulnerable/immune lines, so a `damage ... kind`
    meets them; without it the world text is unchanged.
    ``reserved`` holds the ids stored on other sheets and in other chests (read
    as values); a chest entry with no stored id is minted past them (#1073).
    ``module_ids`` (P3a) names module catalog ids a later ``create item ... from``
    in this world needs; with them, and with every module id a row carries, the
    world declares those module item types. A world with none reads no module file.
    """
    gaps: List[str] = []
    loc = location_id(location)
    lines: List[str] = [
        "// Generated by core/nql/genesis.py from character sheets. Typed fields only.",
        "rules { transfer unequips; wear any; recovery 1 of 2; }",
    ]
    if clock_tick is not None:
        lines.append(f'clock "second" at {int(clock_tick)};')
    if damage_traits:
        # K1: X8 traits exist only under the attacks law. `defense` only names
        # the AC stat; no request in this world scores an attack.
        lines.append(DAMAGE_TRAITS_LAW)
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
    condition_types: List[str] = [DEFENSE_STYLE_CONDITION, ARCHERY_STYLE_CONDITION]
    # NUM-H3b: the Unarmored Defense types the defense derive's terms require.
    for cond in class_conditions.condition_types():
        if cond not in condition_types:
            condition_types.append(cond)
    for conds in _ARMOR_TRAINING.values():
        for cond in conds:
            if cond not in condition_types:
                condition_types.append(cond)
    definitions: List[str] = [
        ' definition "gear:held" named "Held item" { description "Occupies one hand."; default "held"; mode "held" { occupy "hand" by 1; } }\n',
        ' definition "gear:worn" named "Worn item" { description "Worn, occupies no slot."; default "worn"; mode "worn" { } }\n',
    ]
    # GP: the pack's armor types name gear:srd/<slug>; one definition each from
    # the entry's typed neq_armor fields (a shield is ac_base 2, ac_bonus 0).
    for catalog_armor in item_catalog.armor_entries():
        text = _armor_definition(item_catalog.armor_definition_id(catalog_armor),
                                 dict(catalog_armor["neq_armor"], item_name=catalog_armor.get("name", "")), gaps)
        if text is not None:
            definitions.append(text)
    # NUM-H3a: the pack's weapon types (srd-item-catalog/4) name gear:srd/<slug>;
    # one definition each from the entry's typed weapon block, and the
    # proficiency Condition type its attacks name. No character gets an
    # instance here, so no grant gains proficiency or a Monk die (NUM-H3b).
    monk_rules = item_catalog.monk_weapon_rules()
    for catalog_weapon in item_catalog.weapon_entries():
        try:
            text = _weapon_definition(catalog_weapon, monk_rules)
        except (KeyError, TypeError, ValueError) as error:
            gaps.append(f"catalog weapon {catalog_weapon.get('id')!r} has no engine definition: {error}")
            continue
        definitions.append(text)
        prof = weapon_proficiency_condition(catalog_weapon)
        if prof not in condition_types:
            condition_types.append(prof)
    # NUM-H3b: per-character instances of the pack's types need the pack's
    # weapon definitions and attack_features.nql in this world.
    with_pack = bool(item_catalog.weapon_entries()) and bool(item_catalog.features_source().strip())
    notes: List[str] = []
    items: List[str] = []
    module_types = set(module_ids or ())
    effects: List[str] = []
    effect_types: List[str] = []
    effect_names: Dict[str, str] = {}
    effect_ids: Dict[Tuple[str, str], Tuple[str, str]] = {}
    first_holders = effect_first_holders(sheets)
    all_ids: set = set()
    carried: Dict[str, str] = {}
    # Item charges (H1): one item type per charged sheet row, declared after the pack.
    charged: Tuple[List[str], set] = ([], set())

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
            f' stat "dexterity" = {dex};\n stat "defense" = 10;\n stat {_q(ARCHERY_STAT)} = {ARCHERY_BONUS};\n'
            + "\n".join(stats.stat_lines(sheet, gaps)) + "\n"
            + "\n".join(resources) + "\n"
            + ("".join(" %s\n" % line for line in _trait_lines(sheet)) if damage_traits else "")
            + "}"
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
        if _has_archery_style(sheet):
            conditions.append(
                f"condition {_q(ARCHERY_STYLE_CONDITION + ':' + cid.split(':', 1)[1])} of {_q(ARCHERY_STYLE_CONDITION)} to {_q(cid)};"
            )
        # NUM-H3b: Unarmed Strike, weapon proficiency, the Monk's Martial Arts die
        # and Unarmored Defense, from the sheet's typed class, level and
        # proficiencies (core/nql/class_conditions.py).
        for kind in class_conditions.instances(sheet, notes, cid, with_pack):
            if kind.startswith("prof:weapon:") and kind not in condition_types:
                continue  # no catalog weapon declares this type in this world
            if kind.startswith(class_conditions.AC_FORMULA_PREFIX) and kind not in condition_types:
                condition_types.append(kind)  # #1433: declared only in a world whose sheet holds it
            conditions.append(f"condition {_q(kind + ':' + cid.split(':', 1)[1])} of {_q(kind)} to {_q(cid)};")
        types, instances = _effect_lines(sheet, cid, gaps, effect_names, clock_tick, first_holders, effect_ids, notes)
        effect_types.extend(types)
        conditions.extend(instances)
        ids: Dict[int, str] = {}
        hands = 0
        scope = cid.split(":", 1)[1]
        declared: Dict[int, Tuple[str, List[str]]] = {}
        # NUM-H3a: an equipped catalog weapon is declared after every other row,
        # so the hands it may take are what the shield and other held items
        # leave; the world keeps the sheet's row order. #960: an untyped held
        # row that finds both hands taken (a saved sheet) is declared carried.
        weapons_last: List[Tuple[int, str, Dict[str, Any]]] = []
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
            if _module_row_id(entry):
                module_types.add(_module_row_id(entry))
            catalog = item_catalog.row_entry(entry)[0]
            if entry.get("equipped") is True and catalog is not None and catalog.get("kind") == "weapon":
                weapons_last.append((index, iid, entry))
                continue
            line, _, held_hands = _item_line(iid, entry, cid, f"custody character {_q(cid)};",
                                             entry.get("equipped") is True, definitions, gaps, cid, charged,
                                             hands_free=2 - hands, carried=carried)
            declared[index] = (line, ac_effect_lines(iid, entry, all_ids, gaps, cid))
            hands += held_hands
        for index, iid, entry in weapons_last:
            line, _, held_hands = _item_line(iid, entry, cid, f"custody character {_q(cid)};",
                                             True, definitions, gaps, cid, charged, hands_free=2 - hands,
                                             carried=carried)
            declared[index] = (line, ac_effect_lines(iid, entry, all_ids, gaps, cid))
            hands += held_hands
        for index in sorted(declared):
            items.append(declared[index][0])
            effects.extend(declared[index][1])
        if hands > 2:
            gaps.append(f"{cid}: {hands} held items equipped; the engine allows two hands, genesis will be refused")
        item_ids[cid] = ids
        # AM: every ammunition row is one engine stock; a pending count of
        # recoverable shots rides on the item so a per-call world keeps it.
        for iid, row in ammunition_rows(sheet, gaps):
            if iid in all_ids:
                gaps.append(f"{cid}: ammunition id {iid} collides with an equipment id; skipped")
                continue
            all_ids.add(iid)
            fields = [f"owner {_q(cid)};", f"custody character {_q(cid)};", f"quantity {row['quantity']};"]
            pending = _int(row.get("recoverable"))
            if pending is not None and pending > 0:
                fields.append(f"recoverable {pending};")
            items.append(f"item {_q(iid)} named {_q(row['name'])} {{ {' '.join(fields)} }}")

    owner = contents_owner or next(iter(character_ids.values()), None)
    reserved_ids = reserved or ()
    for container in containers or []:
        sid = str(container.get("id", ""))
        if not sid:
            gaps.append("storage container without id skipped")
            continue
        conid = container_id(sid)
        if conid in container_ids.values():
            # Two storage ids that bound to one engine id (#1004).
            gaps.append(f"duplicate container id {conid}; second container skipped")
            continue
        container_ids[sid] = conid
        items.append(f"item {_q(conid)} named {_q(container.get('deviceName') or sid)} {{ container true; custody location {_q(loc)}; }}")
        ids = {}
        contents = container.get("contents") or []
        # A stored id is kept as it is, so a minted one must not take the id
        # another entry stores (a new split part listed ahead of an older
        # entry would hide it, #971); it is reminted instead.
        stored = {_entry_id(e, slug(sid), i) for i, e in enumerate(contents)
                  if isinstance(e, dict) and str(e.get("nql_id") or "").startswith("item:")}
        for index, entry in enumerate(contents):
            if not isinstance(entry, dict) or not entry.get("item_name"):
                gaps.append(f"{sid}: contents[{index}] has no item_name; skipped")
                continue
            iid = _entry_id(entry, slug(sid), index)
            spare = index
            while (iid in stored or iid in reserved_ids) and not str(entry.get("nql_id") or "").startswith("item:"):
                spare += 1000
                iid = _mint(entry, slug(sid), spare)
            if iid in all_ids:
                gaps.append(f"{sid}: duplicate item id {iid} at contents[{index}]; skipped")
                continue
            if owner is None:
                gaps.append(f"{sid}: contents need an owner character; none in world")
                break
            all_ids.add(iid)
            ids[index] = iid
            if _module_row_id(entry):
                module_types.add(_module_row_id(entry))
            line, _, _ = _item_line(iid, entry, owner, f"custody item {_q(conid)};", False, definitions, gaps, owner, charged)
            items.append(line)
        content_ids[sid] = ids

    # Definitions for items that do not exist yet (a later create item in the
    # same world needs its equipment definition declared at genesis).
    for iid, entry in definition_entries or []:
        if isinstance(entry, dict) and item_catalog.row_entry(entry)[0] is not None:
            continue  # a catalog row takes its equipment from the pack's type
        if isinstance(entry, dict) and entry.get("item_type") == "armor":
            text = _armor_definition("gear:" + iid.split(":", 1)[1], entry, gaps)
            if text is not None:
                definitions.append(text)

    for cond in condition_types:
        lines.append(f"condition type {_q(cond)} {{ {srd_stats.TYPE_BODIES.get(cond, 'instances unique;')} }}")
    # The SRD proficiency types are declared for every world: the derive rules
    # below name them with `requires`, legal only for a declared type.
    for cond in srd_stats.CONDITION_TYPES:
        if cond not in condition_types:
            lines.append(f"condition type {_q(cond)} {{ {srd_stats.TYPE_BODIES.get(cond, 'instances unique;')} }}")
    # The SRD condition states (C1): declared for every world so a later
    # `apply condition` has them and the engine can hold unconscious at 0 hp.
    lines.append(srd_stats.STATE_TYPES.rstrip("\n"))
    # Concentration (CN): the type, and the damage-triggered Constitution save.
    lines.append(srd_stats.CONCENTRATION_RULES.rstrip("\n"))
    lines.extend(effect_types)
    lines.extend(conditions)
    lines.append(f"equipment {_q(EQUIPMENT_VERSION)} {{")
    lines.append(' slot "hand" capacity 2;\n slot "body" capacity 1;\n slot "shield" capacity 1;')
    # NUM-H3b: Unarmored Defense terms from progression.json ac_formulas, gated
    # on the class Condition and on the slots the formula excludes.
    # #1322: a live set effect (Mage Armor) adds its gated alternative recipe.
    # #1433: a held class formula (Draconic Resilience) adds its own, declared
    # first so a permanent feature keeps a tie with a spell.
    lines.append(' derive stat "defense" { term stat "dexterity" offset -10 divide 2;'
                 + class_conditions.defense_terms() + feature_defense_recipes(condition_types)
                 + effect_defense_recipes(sheets, gaps, effect_ids) + ' }')
    lines.append(srd_stats.DERIVE_RULES.rstrip("\n"))
    lines.append(srd_stats.XP_RULES.rstrip("\n"))
    lines.extend(d.rstrip("\n") for d in definitions)
    lines.append("}")
    lines.extend(items)
    lines.extend(effects)
    # GP: every world carries the SRD item pack, so a row `from` a catalog type
    # and a later `create item ... from` resolve in any call's world.
    pack = item_catalog.pack_source().rstrip("\n")
    if pack:
        lines.append(pack)
        # NUM-H3a: the Condition types the weapon definitions name (Unarmed
        # Strike, the Martial Arts dice), part of the same pack.
        features = item_catalog.features_source().rstrip("\n")
        if features:
            lines.append(features)
    # P3a: module item types, outside the SRD pack block, so a module row
    # still resolves when the SRD pack is absent.
    if module_types:
        module_source = _module_type_source(sorted(module_types))
        if module_source:
            lines.append(module_source)
    lines.extend(charged[0])
    return Genesis(source="\n".join(lines) + "\n", location=loc, character_ids=character_ids, item_ids=item_ids,
                   container_ids=container_ids, content_ids=content_ids, effect_names=effect_names, gaps=gaps,
                   carried=carried, notes=notes, effect_ids=effect_ids)


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
