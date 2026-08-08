# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Provider-facing roles for the agentic combat pipeline.

T096 chooses ordered tactical intents from authoritative state. T097 writes
narration only after those intents have been resolved and committed by code.
Neither role writes game state.
"""

import json

from core.ai import api_client
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
from utils.character_sheet_contract import extract_json_object


register_callsite("T096", "core/ai/combat_agent.py", 142)
register_callsite("T097", "core/ai/combat_agent.py", 220)


class CombatAgentContractError(ValueError):
    """A provider response did not satisfy the combat role contract."""


def _provider_config(role):
    import config
    from model_config import get_provider

    provider = get_provider()
    if role == "intent":
        names = {
            "openai": "COMBAT_INTENT_GPT54_NONE",
            "gemini": "COMBAT_INTENT_GEMINI_FLASH_LOW",
            "lmstudio": "COMBAT_INTENT_LMSTUDIO",
            "legacy": "COMBAT_INTENT_LEGACY",
        }
    else:
        names = {
            "openai": "COMBAT_NARRATE_GPT54MINI_NONE",
            "gemini": "COMBAT_NARRATE_GEMINI_FLASH_LOW",
            "lmstudio": "COMBAT_NARRATE_LMSTUDIO",
            "legacy": "COMBAT_NARRATE_LEGACY",
        }
    return provider, dict(getattr(config, names[provider]))


def _parse_object(content, label):
    blob = extract_json_object(content)
    if not blob:
        raise CombatAgentContractError("%s returned no JSON object" % label)
    try:
        value = json.loads(blob)
    except json.JSONDecodeError as exc:
        raise CombatAgentContractError("%s returned malformed JSON" % label) from exc
    if not isinstance(value, dict):
        raise CombatAgentContractError("%s response must be an object" % label)
    return value


def _relevant_sheet(sheet):
    if not isinstance(sheet, dict):
        return {}
    keys = (
        "name", "class", "level", "hitPoints", "maxHitPoints", "armorClass",
        "status", "condition_affected", "abilities", "abilityScores", "proficiencyBonus",
        "savingThrows", "attacksAndSpellcasting", "actions", "specialAbilities",
        "spellcasting", "classFeatures", "ammunition", "temporaryEffects",
    )
    return {key: sheet[key] for key in keys if key in sheet}


def select_spell_references(characters, repository):
    """Return only SRD spell entries actually present on combatant sheets."""
    if not isinstance(repository, dict):
        return {}
    names = set()
    for sheet in (characters or {}).values():
        spells = ((sheet or {}).get("spellcasting") or {}).get("spells") or {}
        if not isinstance(spells, dict):
            continue
        for entries in spells.values():
            if isinstance(entries, list):
                names.update(str(name).strip() for name in entries if name)
    references = {}
    for name in names:
        key = name.lower().replace(" ", "_").replace("-", "_")
        if key in repository:
            references[key] = repository[key]
    return references


def _intent_system_prompt():
    return """You are the tactical-intent role in a turn-based fantasy combat engine.
You choose actions and bounded rulings; code owns initiative, dice consumption,
arithmetic, state mutation, and recovery.

Return one JSON object with stateVersion and intents. Return EXACTLY one intent
for every actorId in requiredActorIds, in that exact order. Do not add or omit
actors, even if an earlier action might defeat a later actor; code skips them.

For NPC/enemy actors, use mode='known' for a listed weapon/action and provide action='attack',
ability, and targetId, or for defend/dodge/disengage/dash/hide/help. Use
mode='adjudicated' for spells, healing, items, class features, and creative
actions. An adjudicated intent may contain:
- description: concise mechanical ruling
- save: {type, dc, halfOnSave} when targets roll a save
- targets: [{combatantId, hpDelta}], negative damage / positive healing
- resources: [{owner, kind, name, delta}], using exact sheet names; kind is
  ammunition, spellSlot, featureUse, or item
- effects: [{op:'add', owner, effect:{name,description,roundsRemaining,
  concentration,tickTrigger,modifiers:[{stat,value}],conditions:[],
  incapacitates:false,onApply:[],onRemove:[]}}] or
  [{op:'remove', owner, name/effectId}]. Use owner with the exact character
  sheet name for players/allied NPCs. Use combatantId instead of owner for an
  enemy/encounter creature so the effect is stored on that unique creature.
  When a declared save controls whether an effect applies, set applyOn to
  'failedSave' or 'successfulSave'. A combatantId effect uses its own save;
  an owner-based sheet effect is matched to that named character's save (an
  explicit saveTargetId is optional). Code rolls damage and zero-damage control
  targets, not healing targets, and stages only effects whose save condition won.
  Example for a hostile control target:
  targets:[{combatantId:'cmb-enemy-bandit-1',hpDelta:0}],
  effects:[{op:'add',combatantId:'cmb-enemy-bandit-1',applyOn:'failedSave',
  effect:{name:'Restrained',description:'Held by vines',concentration:true}}].
  applyOn belongs on the effect OP, not inside effect. Do not add a separate
  concentration marker to the caster; the target effect records concentration.
  Use tickTrigger='end_of_round' for effects measured in combat rounds.
  For encounter-long effects omit roundsRemaining. Numeric bonuses must be
  declared in modifiers; never bake them into HP, AC, or abilities. Current HP
  is a resource: Aid-like max/current HP uses a maxHitPoints modifier plus
  an onApply hitPoints delta and an empty onRemove (code clamps to the new max
  when it ends). Set incapacitates=true only when
  the target cannot act. Code owns duration conversion, arithmetic, and expiry.
  Code stamps concentration source/group IDs from actorId and enforces one
  concentration spell (which may affect multiple targets) per caster.

One known attack intent represents the actor's full Attack action. Code owns
the number of Multiattack swings and consumes each persisted roll; do not emit
duplicate intents for the same actor.

The PLAYER actor must always use mode='adjudicated'; never roll automatically
for the player. Apply only rolls/results explicitly supplied in playerInput,
or set requiresPlayerInput={kind:'roll'|'choice', prompt:'...', die:'d20',
reason:'...'} and leave mechanical arrays empty. Code will pause the same turn
and show that request instead of consuming it.

Never provide resulting HP totals, round numbers, cursor changes, narration, or prose
outside JSON. Do not invent spell slots, ammunition, abilities, targets, or
actors. For a player actor, honor the submitted player action; adjudicate it
fairly rather than replacing it with a tactically preferred action. For NPCs
and enemies, choose tactically appropriate actions from their actual sheets.
If an action has no HP/resource/effect change, use empty arrays."""


def request_intent_batch(
    encounter,
    characters,
    pending_turn,
    player_input,
    spell_references=None,
    correction=None,
):
    """Call T096 once for an ordered batch of decisions, with no mutations."""
    provider, call_config = _provider_config("intent")
    payload = {
        "stateVersion": (encounter.get("combatState") or {}).get("revision"),
        "round": (encounter.get("combatState") or {}).get("round"),
        "requiredActorIds": pending_turn.get("actorIds", []),
        "playerInput": player_input,
        "creatures": encounter.get("creatures", []),
        "sheets": {name: _relevant_sheet(sheet) for name, sheet in (characters or {}).items()},
        "spellReferences": spell_references or {},
    }
    if correction:
        payload["correction"] = correction
    messages = [
        {"role": "system", "content": _intent_system_prompt()},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    response = capture_and_fanout(
        "T096",
        api_client.create_completion,
        _request_provider=provider,
        messages=messages,
        model=call_config.pop("model"),
        temperature=0.2,
        **call_config,
    )
    result = _parse_object(response.choices[0].message.content, "T096")
    returned_version = result.get("stateVersion")
    if (
        isinstance(returned_version, str)
        and returned_version.strip().isdigit()
    ):
        returned_version = int(returned_version.strip())
        result["stateVersion"] = returned_version
    if type(returned_version) is not int or returned_version != payload["stateVersion"]:
        raise CombatAgentContractError(
            "T096 returned stale stateVersion %r; expected exact value %r"
            % (returned_version, payload["stateVersion"])
        )
    intents = result.get("intents")
    if not isinstance(intents, list):
        raise CombatAgentContractError("T096 requires an intents array")
    returned_ids = [item.get("actorId") if isinstance(item, dict) else None for item in intents]
    if returned_ids != payload["requiredActorIds"]:
        raise CombatAgentContractError("T096 actor order does not match the claimed turn")
    return result


def _fallback_narration(events):
    parts = []
    for event in events or []:
        actor = event.get("actorId", "A combatant")
        description = (event.get("intent") or {}).get("description")
        if description:
            parts.append("%s: %s" % (actor, description))
            continue
        outcome = event.get("outcome") or {}
        if outcome.get("kind") == "attack":
            parts.append("%s attacks and %s." % (
                actor,
                "hits" if outcome.get("hit") else "misses",
            ))
        else:
            parts.append("%s takes a combat action." % actor)
    return " ".join(parts) or "The combatants hold position, watching for the next move."


def narrate_committed_events(encounter, events, player_input):
    """Call T097 after commit; deterministic fallback never changes mechanics."""
    provider, call_config = _provider_config("narration")
    messages = [
        {
            "role": "system",
            "content": (
                "You narrate already-resolved fantasy combat events. The event data is "
                "authoritative. Return JSON {\"narration\":\"...\"}. Do not change, "
                "invent, or recalculate mechanics; do not announce actions beyond these "
                "events. Keep the prose vivid, clear, and concise."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(
                {
                    "round": (encounter.get("combatState") or {}).get("round"),
                    "playerInput": player_input,
                    "events": events,
                },
                ensure_ascii=False,
            ),
        },
    ]
    try:
        response = capture_and_fanout(
            "T097",
            api_client.create_completion,
            _request_provider=provider,
            messages=messages,
            model=call_config.pop("model"),
            temperature=0.5,
            **call_config,
        )
        result = _parse_object(response.choices[0].message.content, "T097")
        narration = result.get("narration")
        if not isinstance(narration, str) or not narration.strip():
            raise CombatAgentContractError("T097 narration is empty")
        return narration.strip(), False
    except Exception:
        return _fallback_narration(events), True
