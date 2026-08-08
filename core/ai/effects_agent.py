# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""T078 declarative-effects classifier.

The provider identifies an effect and its rules-facing semantics.  Code stamps
identity and owns every duration calculation and mutation.
"""

from copy import deepcopy
import hashlib
import json

from core.ai import api_client
from core.effects.clock import display_iso_from_scalar
from core.effects.model import normalize_effect, validate_effect
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
from utils.character_sheet_contract import extract_json_object


register_callsite("T078", "core/ai/effects_agent.py", 184)


class EffectsAgentContractError(ValueError):
    """T078 did not return a safe declarative classification."""


def _provider_config():
    import config
    from model_config import get_provider

    provider = get_provider()
    names = {
        "openai": "CHAR_EFFECTS_GPT52_NONE",
        "gemini": "CHAR_EFFECTS_GEMINI_FLASH_HIGH",
        "lmstudio": "CHAR_EFFECTS_LMSTUDIO",
        "legacy": "CHAR_EFFECTS_LEGACY",
    }
    return provider, dict(getattr(config, names[provider]))


def _system_prompt():
    return """You classify temporary effects for a deterministic 5th-edition fantasy RPG engine.
Return JSON only. The engine owns arithmetic, clocks, persistence, expiry, and removal.

Return exactly:
{
  "operation": "none|add|remove",
  "effect": {
    "name": "effect or spell name",
    "description": "concise mechanical description",
    "source": "caster, item, hazard, or feature",
    "modifiers": [{"stat":"...", "value":2, "affectsMax":false}],
    "conditions": ["paralyzed"],
    "incapacitates": false,
    "durationKind": "rounds|minutes|hours|days|until_rest|encounter|special",
    "durationValue": 10,
    "restKind": "short_rest|long_rest|none",
    "concentration": false,
    "onApply": [{"stat":"hitPoints", "delta":5}],
    "onRemove": []
  },
  "remove": {"effectId":"known id or empty", "name":"known effect name or empty"}
}

Use operation=none with effect={} and remove={} for instant damage/healing,
permanent changes, inventory/currency/resource changes, and ordinary narration.
Use operation=remove when the change explicitly ends, dispels, replaces, or
breaks concentration on an existing temporary effect. Copy its exact effectId
and name from currentEffectiveSheet. Do not guess a removal target.

Allowed modifier stats: armorClass, speed, maxHitPoints, abilities.strength,
abilities.dexterity, abilities.constitution, abilities.intelligence,
abilities.wisdom, abilities.charisma, attackRolls, damageRolls, abilityChecks,
savingThrows, savingThrow.<ability>, abilityCheck.<ability>, initiative,
spellSaveDC, spellAttackBonus.

Current hit points are a resource, not a derived modifier. For Aid-like effects
that raise maximum and current HP, use a maxHitPoints modifier plus matching
onApply hitPoints delta. Leave onRemove empty: when maximum HP falls, code
clamps current HP to the new maximum instead of subtracting real HP. Do not put
hitPoints in modifiers. Leave onApply/onRemove empty for normal effects.

Conditions use standard lowercase names. Set incapacitates=true only when the
target cannot take actions. For concentration, use the effect's maximum stated
duration. Do not calculate timestamps. Do not invent an effectId. Do not include
fields outside this contract."""


_REQUIRED_EFFECT_FIELDS = {
    "name",
    "description",
    "source",
    "modifiers",
    "conditions",
    "incapacitates",
    "durationKind",
    "durationValue",
    "restKind",
    "concentration",
    "onApply",
    "onRemove",
}


def _parse(content):
    blob = extract_json_object(content)
    if not blob:
        raise EffectsAgentContractError("T078 returned no JSON object")
    try:
        result = json.loads(blob)
    except json.JSONDecodeError as exc:
        raise EffectsAgentContractError("T078 returned malformed JSON") from exc
    if not isinstance(result, dict) or set(result) != {"operation", "effect", "remove"}:
        raise EffectsAgentContractError("T078 requires exactly operation, effect, and remove")
    if (
        result["operation"] not in ("none", "add", "remove")
        or not isinstance(result["effect"], dict)
        or not isinstance(result["remove"], dict)
    ):
        raise EffectsAgentContractError("T078 returned invalid field types")
    if result["operation"] == "none":
        if result["effect"] or result["remove"]:
            raise EffectsAgentContractError("T078 none result must use empty objects")
        return result
    if result["operation"] == "remove":
        if result["effect"] or set(result["remove"]) != {"effectId", "name"}:
            raise EffectsAgentContractError("T078 remove result has an invalid shape")
        if not any(
            isinstance(result["remove"].get(field), str)
            and result["remove"][field].strip()
            for field in ("effectId", "name")
        ):
            raise EffectsAgentContractError("T078 remove result requires an identity")
        return result
    if result["remove"]:
        blank_remove = (
            set(result["remove"]) == {"effectId", "name"}
            and all(
                isinstance(result["remove"].get(field), str)
                and not result["remove"][field].strip()
                for field in ("effectId", "name")
            )
        )
        if not blank_remove:
            raise EffectsAgentContractError(
                "T078 add result must use an empty remove object"
            )
        result["remove"] = {}
    if set(result["effect"]) != _REQUIRED_EFFECT_FIELDS:
        raise EffectsAgentContractError("T078 effect has missing or extra fields")
    effect = result["effect"]
    if effect["restKind"] not in ("short_rest", "long_rest", "none"):
        raise EffectsAgentContractError("T078 restKind is invalid")
    kind = effect["durationKind"]
    value = effect["durationValue"]
    if kind == "rounds":
        if type(value) is not int or value <= 0:
            raise EffectsAgentContractError(
                "T078 round durationValue must be a positive integer"
            )
    elif kind in ("minutes", "hours", "days"):
        if type(value) not in (int, float) or value <= 0:
            raise EffectsAgentContractError("T078 durationValue must be positive")
    elif kind == "until_rest":
        if effect["restKind"] == "none":
            raise EffectsAgentContractError("until_rest requires a restKind")
    elif kind in ("encounter", "special"):
        if not isinstance(value, (str, int, float)):
            raise EffectsAgentContractError("T078 special duration is invalid")
    else:
        raise EffectsAgentContractError("T078 durationKind is invalid")
    return result


def _finalize(effect, now_scalar, owner, change_description):
    value = effect.pop("durationValue")
    rest_kind = effect.get("restKind")
    if rest_kind == "none":
        effect.pop("restKind", None)
    kind = effect.get("durationKind")
    if kind == "rounds":
        effect["roundsRemaining"] = int(value)
        effect["tickTrigger"] = "end_of_round"
    elif kind in ("minutes", "hours", "days"):
        multiplier = {"minutes": 60, "hours": 3600, "days": 86400}[kind]
        effect["expiration"] = display_iso_from_scalar(
            int(now_scalar) + int(float(value) * multiplier)
        )
    effect["duration"] = "%s %s" % (value, kind.replace("_", " "))
    identity_material = json.dumps(
        {
            "owner": owner,
            "change": str(change_description),
            "gameTimeScalar": int(now_scalar),
            "name": effect.get("name"),
            "source": effect.get("source"),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    effect["effectId"] = "FX-%s" % hashlib.sha256(
        identity_material.encode("utf-8")
    ).hexdigest()[:24]
    effect["authoredBy"] = "classifier"
    effect["created"] = {
        "gameTimeScalar": int(now_scalar),
        "owner": owner,
        "change": str(change_description)[:500],
    }
    normalized = normalize_effect(effect)
    problems = validate_effect(normalized, require_managed=True)
    if problems:
        raise EffectsAgentContractError("T078 effect failed validation: %s" % "; ".join(problems))
    return normalized


def classify_effect(character_name, change_description, sheet, now_scalar, max_attempts=2):
    """Return ``{shouldTrack, effect}`` without mutating any state."""
    provider, call_config = _provider_config()
    payload = {
        "characterName": character_name,
        "currentEffectiveSheet": deepcopy(sheet or {}),
        "change": change_description,
    }
    correction = None
    last_error = None
    for _attempt in range(max(1, int(max_attempts))):
        messages = [
            {"role": "system", "content": _system_prompt()},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]
        if correction:
            messages.append({"role": "system", "content": correction})
        try:
            options = dict(call_config)
            response = capture_and_fanout(
                "T078",
                api_client.create_completion,
                _request_provider=provider,
                messages=messages,
                model=options.pop("model"),
                temperature=0.1,
                **options
            )
            result = _parse(response.choices[0].message.content.strip())
            if result["operation"] == "add":
                result["effect"] = _finalize(
                    result["effect"], now_scalar, character_name, change_description
                )
            return result
        except Exception as exc:
            last_error = exc
            correction = (
                "Your previous response failed the strict contract: %s. "
                "Return a corrected complete JSON object only." % exc
            )
    raise EffectsAgentContractError("T078 failed after retries: %s" % last_error)
