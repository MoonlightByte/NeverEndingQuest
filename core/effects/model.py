# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Canonical declarative effect-object contract."""

from copy import deepcopy
import re


EFFECTS_PIPELINE_VERSION = 2
AUTHORS = frozenset(("engine", "classifier", "legacy"))
DURATION_KINDS = frozenset(
    ("rounds", "minutes", "hours", "days", "until_rest", "encounter", "permanent", "special")
)
TICK_TRIGGERS = frozenset(("start_of_turn", "end_of_turn", "end_of_round"))
ABILITY_NAMES = frozenset(
    ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
)
DIRECT_STATS = frozenset(("armorClass", "speed", "hitPoints", "maxHitPoints"))
META_STATS = frozenset(
    (
        "attackRolls",
        "damageRolls",
        "abilityChecks",
        "savingThrows",
        "initiative",
        "spellSaveDC",
        "spellAttackBonus",
    )
)


_SKILL_STAT = re.compile(r"abilitycheck[._]skill[._](.+)", re.IGNORECASE)


def _skill_stat(value):
    """``abilityCheck.skill.<skill>`` for an SRD skill, in the engine's kebab
    form (``sleight_of_hand`` -> ``sleight-of-hand``); None for any other
    text (#889: Guidance's die on one skill)."""
    match = _SKILL_STAT.fullmatch(value)
    if match is None:
        return None
    from core.nql.stats import skill_id

    skill = skill_id(match.group(1).replace(".", "-"))
    return "abilityCheck.skill.%s" % skill if skill else None


def canonical_stat(stat):
    """Normalize legacy stat names into stable modifier paths."""
    if not isinstance(stat, str):
        return None
    value = stat.strip()
    if value in DIRECT_STATS or value in META_STATS:
        return value
    if _SKILL_STAT.fullmatch(value):
        return _skill_stat(value)
    lowered = value.lower().replace("_", ".")
    if lowered in ABILITY_NAMES:
        return "abilities.%s" % lowered
    for prefix in ("abilities.", "savingthrow.", "abilitycheck."):
        if lowered.startswith(prefix) and lowered.split(".", 1)[1] in ABILITY_NAMES:
            head, tail = lowered.split(".", 1)
            normalized_head = {
                "abilities": "abilities",
                "savingthrow": "savingThrow",
                "abilitycheck": "abilityCheck",
            }[head]
            return "%s.%s" % (normalized_head, tail)
    return None


def effect_identity(effect):
    """Return a conservative identity used to suppress stripped AI clones."""
    if not isinstance(effect, dict):
        return None
    effect_id = effect.get("effectId")
    if isinstance(effect_id, str) and effect_id.strip():
        return ("id", effect_id.strip())
    name = str(effect.get("name") or "").strip().casefold()
    source = str(effect.get("source") or "").strip().casefold()
    if not name:
        return None
    return ("legacy", re.sub(r"\s+", " ", name), re.sub(r"\s+", " ", source))


def preserve_engine_effects(current_effects, proposed_effects):
    """Keep exact engine objects and suppress AI-produced stripped clones."""
    protected = [
        deepcopy(effect)
        for effect in current_effects or []
        if isinstance(effect, dict) and effect.get("authoredBy") == "engine"
    ]
    protected_ids = {effect_identity(effect) for effect in protected}
    protected_labels = {
        (
            str(effect.get("name") or "").strip().casefold(),
            str(effect.get("source") or "").strip().casefold(),
        )
        for effect in protected
    }
    retained = []
    for effect in proposed_effects or []:
        if not isinstance(effect, dict):
            continue
        if effect_identity(effect) in protected_ids:
            continue
        proposed_name = str(effect.get("name") or "").strip().casefold()
        proposed_source = str(effect.get("source") or "").strip().casefold()
        if any(
            proposed_name == name
            and (not proposed_source or not source or proposed_source == source)
            for name, source in protected_labels
        ):
            continue
        retained_effect = deepcopy(effect)
        # This helper only accepts objects returned by legacy AI writers.
        # Provider output can never grant itself engine/classifier authority;
        # the exact protected engine objects above are the sole exception.
        retained_effect["authoredBy"] = "legacy"
        retained.append(retained_effect)
    return retained + protected


# #889: an added die on a modifier (Bless: 1d4 to attack rolls and saving
# throws), held as written in place of a flat value.
_MODIFIER_DIE = re.compile(r"[1-4]d(?:4|6|8|10|12)")


def _die_stat(stat):
    """The stats an added die may name (#889): attack rolls and saves (Bless),
    every ability check, or one skill's checks (Guidance)."""
    return (stat in ("attackRolls", "savingThrows", "abilityChecks")
            or stat.startswith(("savingThrow.", "abilityCheck.")))


def _normalize_set(stat, rule, value, die, at_least=None):
    """The typed set rule of a modifier: {"base": 0-30, "plusAbility": ability or None}."""
    if value is not None or die is not None or at_least is not None:
        raise ValueError("effect modifier needs exactly one of value, die, set or atLeast")
    if stat != "armorClass":
        raise ValueError("effect modifier set applies only to armorClass")
    if not isinstance(rule, dict) or set(rule) - {"base", "plusAbility"}:
        raise ValueError('effect modifier set must be {"base": a whole number, "plusAbility": an ability or null}')
    base = rule.get("base")
    if type(base) is not int or not 0 <= base <= 30:
        raise ValueError("effect modifier set base must be a whole number from 0 to 30")
    ability = rule.get("plusAbility")
    if ability is not None and ability not in ABILITY_NAMES:
        raise ValueError("effect modifier set plusAbility must be an ability name or null")
    return {"base": base, "plusAbility": ability}


def _normalize_at_least(stat, amount, value, die):
    """#1434: the typed armor class floor of a modifier (Barkskin: 17), a whole number 1-30."""
    if value is not None or die is not None:
        raise ValueError("effect modifier needs exactly one of value, die, set or atLeast")
    if stat != "armorClass":
        raise ValueError("effect modifier atLeast applies only to armorClass")
    if type(amount) is not int or not 1 <= amount <= 30:
        raise ValueError("effect modifier atLeast must be a whole number from 1 to 30")
    return amount


def normalize_modifier(modifier):
    if not isinstance(modifier, dict):
        raise ValueError("effect modifier must be an object")
    stat = canonical_stat(modifier.get("stat"))
    if stat is None:
        raise ValueError("effect modifier has an unsupported stat")
    if stat == "hitPoints":
        raise ValueError("current hitPoints cannot be a derived effect modifier")
    value = modifier.get("value")
    die = modifier.get("die")
    if "set" in modifier:
        # #1322: armor class becomes a base plus an ability modifier (Mage
        # Armor: 13 + Dexterity). The engine derives it as a gated recipe;
        # no number is computed here.
        return {"stat": stat, "set": _normalize_set(stat, modifier["set"], value, die, modifier.get("atLeast"))}
    if "atLeast" in modifier:
        # #1434: armor class can't fall below a number (Barkskin: 17). The
        # engine applies it as an `at least` bound after every other term.
        return {"stat": stat, "atLeast": _normalize_at_least(stat, modifier["atLeast"], value, die)}
    if die is not None or value is None:
        # Exactly one of value (a whole number) or die (#889).
        if value is not None or not isinstance(die, str) or not _MODIFIER_DIE.fullmatch(die):
            raise ValueError("effect modifier needs value (a whole number) or die (such as 1d4)")
        if not _die_stat(stat):
            raise ValueError("effect modifier die applies only to attackRolls, savingThrows, "
                             "savingThrow.<ability>, abilityChecks or abilityCheck.skill.<skill>")
        return {"stat": stat, "die": die}
    if type(value) not in (int, float):
        raise ValueError("effect modifier value must be numeric")
    if isinstance(value, float) and not value.is_integer():
        raise ValueError("effect modifier value must be a whole number")
    result = {"stat": stat, "value": int(value)}
    if modifier.get("affectsMax") is True or modifier.get("affects_max") is True:
        result["affectsMax"] = True
    return result


def normalize_resource_operation(operation):
    """Normalize the deliberately tiny one-shot resource-operation contract."""
    if not isinstance(operation, dict):
        raise ValueError("effect resource operation must be an object")
    stat = canonical_stat(operation.get("stat"))
    if stat != "hitPoints":
        raise ValueError("effect resource operation has an unsupported stat")
    if type(operation.get("delta")) is not int:
        raise ValueError("effect resource operation delta must be an integer")
    result = {"stat": "hitPoints", "delta": operation["delta"]}
    for bound in ("minimum", "maximum"):
        if bound in operation:
            if type(operation.get(bound)) is not int:
                raise ValueError(
                    "effect resource operation %s must be an integer" % bound
                )
            result[bound] = operation[bound]
    if (
        "minimum" in result
        and "maximum" in result
        and result["minimum"] > result["maximum"]
    ):
        raise ValueError("effect resource operation bounds are reversed")
    return result


def normalize_effect(effect, *, default_author=None):
    """Copy and normalize an effect without inventing missing semantics."""
    if not isinstance(effect, dict):
        raise ValueError("effect must be an object")
    result = deepcopy(effect)
    if default_author and not result.get("authoredBy"):
        result["authoredBy"] = default_author
    if "modifiers" in result:
        if not isinstance(result["modifiers"], list):
            raise ValueError("effect modifiers must be an array")
        result["modifiers"] = [normalize_modifier(item) for item in result["modifiers"]]
    if "conditions" in result:
        if not isinstance(result["conditions"], list):
            raise ValueError("effect conditions must be an array")
        result["conditions"] = list(
            dict.fromkeys(
                str(item).strip().lower() for item in result["conditions"] if str(item).strip()
            )
        )
    for field in ("onApply", "onRemove"):
        if field in result:
            if not isinstance(result[field], list):
                raise ValueError("effect %s must be an array" % field)
            result[field] = [
                normalize_resource_operation(item) for item in result[field]
            ]
    if result.get("roundsRemaining") is None:
        result.pop("roundsRemaining", None)
    if result.get("durationKind") == "rounds" and "roundsRemaining" not in result:
        raise ValueError("round duration requires roundsRemaining")
    return result


def validate_effect(effect, *, require_managed=False):
    """Return contract problems; an empty list means safe to persist."""
    problems = []
    if not isinstance(effect, dict):
        return ["effect must be an object"]
    for field in ("name", "description"):
        if not isinstance(effect.get(field), str) or not effect[field].strip():
            problems.append("effect %s must be useful text" % field)
    authored_by = effect.get("authoredBy")
    if authored_by is not None and authored_by not in AUTHORS:
        problems.append("effect authoredBy is invalid")
    if require_managed:
        if not isinstance(effect.get("effectId"), str) or not effect["effectId"].strip():
            problems.append("managed effect requires effectId")
        if authored_by not in ("engine", "classifier"):
            problems.append("managed effect requires an engine/classifier author")
    modifiers = effect.get("modifiers", [])
    if not isinstance(modifiers, list) or len(modifiers) > 16:
        problems.append("effect modifiers must contain at most 16 records")
    else:
        for modifier in modifiers:
            try:
                normalize_modifier(modifier)
            except ValueError as exc:
                problems.append(str(exc))
    conditions = effect.get("conditions", [])
    if not isinstance(conditions, list) or not all(
        isinstance(item, str) and item.strip() for item in conditions
    ):
        problems.append("effect conditions must contain useful strings")
    kind = effect.get("durationKind")
    if kind is not None and kind not in DURATION_KINDS:
        problems.append("effect durationKind is invalid")
    rounds = effect.get("roundsRemaining")
    if rounds is not None and (type(rounds) is not int or rounds < 0):
        problems.append("effect roundsRemaining must be a nonnegative integer")
    trigger = effect.get("tickTrigger")
    if trigger is not None and trigger not in TICK_TRIGGERS:
        problems.append("effect tickTrigger is invalid")
    if "incapacitates" in effect and type(effect.get("incapacitates")) is not bool:
        problems.append("effect incapacitates must be a boolean")
    if "concentration" in effect and type(effect.get("concentration")) is not bool:
        problems.append("effect concentration must be a boolean")
    for field in ("onApply", "onRemove"):
        operations = effect.get(field, [])
        if not isinstance(operations, list) or len(operations) > 8:
            problems.append("effect %s must contain at most 8 records" % field)
            continue
        for operation in operations:
            try:
                normalize_resource_operation(operation)
            except ValueError as exc:
                problems.append(str(exc))
    return problems
