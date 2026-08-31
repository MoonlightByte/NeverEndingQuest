# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Provider-facing roles for the agentic combat pipeline.

T096 chooses ordered tactical intents from authoritative state. T097 writes
narration only after those intents have been resolved and committed by code.
Neither role writes game state.
"""

import json
import time
from collections.abc import Mapping

from core.ai import api_client
from core.ai.combat_capabilities import (
    build_player_capability_context,
    match_owned_capabilities,
)
from core.ai.srd_reference import (
    SRDContextMatcher,
    SRDReferenceError,
    SRDReferenceIndex,
    compact_rule_reference,
    load_srd_reference_index,
    normalize_rule_name,
)
from core.managers.combat_state import combatant_by_id, resolve_creature_controller
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
from utils.character_sheet_contract import extract_json_object


register_callsite("T096", "core/ai/combat_agent.py", 142)
register_callsite("T097", "core/ai/combat_agent.py", 220)


class CombatAgentContractError(ValueError):
    """A provider response did not satisfy the combat role contract."""


class CombatNarrationAttemptError(CombatAgentContractError):
    """One T097 call failed before producing lintable narration."""

    def __init__(self, message, candidate="", failure_class="response_contract_error"):
        super().__init__(message)
        self.candidate = str(candidate or "")[:12000]
        self.failure_class = str(failure_class or "response_contract_error")


def _provider_config(role, attempt=1):
    from model_config import get_provider, resolve_callsite_config

    provider = get_provider()
    task_id = "T096" if role == "intent" else "T097"
    # Public combat call sites use one-based attempt numbers; the canonical
    # resolver uses zero-based indices and clamps beyond the final retry entry.
    return provider, resolve_callsite_config(task_id, provider, max(int(attempt) - 1, 0))


def combat_role_identity(role):
    """Return sanitized provider/model identifiers without making a call."""
    provider, call_config = _provider_config(role)
    return provider, str(call_config.get("model") or "unknown")


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
        "name",
        "class",
        "level",
        "hitPoints",
        "maxHitPoints",
        "armorClass",
        "status",
        "condition_affected",
        "abilities",
        "abilityScores",
        "proficiencyBonus",
        "savingThrows",
        "attacksAndSpellcasting",
        "actions",
        "specialAbilities",
        "spellcasting",
        "classFeatures",
        "ammunition",
        "temporaryEffects",
    )
    return {key: sheet[key] for key in keys if key in sheet}


def select_spell_references(characters, repository):
    """Return current SRD entries for spell names present on combatant sheets.

    Historical spell names and punctuation variants resolve through the
    repository aliases. Malformed legacy mappings fall back to exact normalized
    keys so optional context lookup cannot prevent combat from starting.
    """
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
    try:
        index = SRDReferenceIndex(repository)
    except SRDReferenceError:
        index = None
    references = {}
    for name in sorted(names):
        if index is not None:
            reference = index.reference(name)
            if reference:
                references[reference["key"]] = reference["entry"]
            continue
        key = normalize_rule_name(name)
        if key in repository and isinstance(repository[key], dict):
            references[key] = repository[key]
    return {key: references[key] for key in sorted(references)}


def _compact_spell_entry(entry):
    keys = (
        "name",
        "aliases",
        "level",
        "school",
        "casting_time",
        "range",
        "duration",
        "ritual",
        "concentration",
        "compactGuidance",
        "source",
        "version",
    )
    return {key: entry[key] for key in keys if key in entry}


def build_contextual_spell_payload(
    characters,
    player_input,
    actor_names=None,
    encounter_context=None,
    index=None,
    max_references=3,
    max_context_characters=4800,
):
    """Build bounded T096 spell guidance for only the current actor window."""
    index = index or load_srd_reference_index()
    matcher = SRDContextMatcher(
        index=index,
        max_references=max_references,
        max_context_characters=max_context_characters,
    )
    names = list(actor_names or ())
    if not names:
        names = sorted((characters or {}).keys())
    actor_rows = [
        (name, (characters or {}).get(name))
        for name in names
        if isinstance((characters or {}).get(name), dict)
    ]
    capability_contexts = {}
    capability_candidates = {}

    candidates = []
    for actor_order, (actor_name, sheet) in enumerate(actor_rows):
        for match in matcher.select(player_input, actor_sheet=sheet):
            value = dict(match)
            value["actor"] = actor_name
            value["actorOrder"] = actor_order
            candidates.append(value)
        context = build_player_capability_context(sheet, actor_name=actor_name)
        matches = match_owned_capabilities(sheet, player_input, actor_name=actor_name)
        capability_contexts[actor_name] = context
        capability_candidates[actor_name] = matches
        # Owned spells already appear in spellActionIndex. A unique fuzzy typo
        # only promotes that owned spell into the fuller reference budget.
        for capability in matches:
            if capability.get("kind") != "spell" or capability.get("matchSource") != "typo":
                continue
            reference = index.reference(capability.get("name"))
            if not reference:
                continue
            entry = reference["entry"]
            candidates.append(
                {
                    "key": reference["key"],
                    "ruleId": reference["id"],
                    "kind": "spell",
                    "entry": entry,
                    "matchedTerm": capability.get("matchedText"),
                    "matchSource": "typo",
                    "score": 260,
                    "span": None,
                    "actorAvailability": "listed",
                    "sheetSpellName": capability.get("name"),
                    "resourceHints": (),
                    "actor": actor_name,
                    "actorOrder": actor_order,
                }
            )
    # Static encounter evidence persists across automatic continuations. Only
    # general-rule matches are taken from it; a spell name in scene prose must
    # never be misread as the current actor casting that spell.
    if isinstance(encounter_context, str) and encounter_context.strip():
        for match in matcher.select(encounter_context):
            if match["kind"] != "rule":
                continue
            value = dict(match)
            value["actor"] = None
            value["actorOrder"] = len(actor_rows)
            value["matchSource"] = "encounter"
            candidates.append(value)
    # The first actor is the current actor. If more than one combatant knows an
    # explicitly named spell, attach availability/resources for the actor whose
    # turn is actually being resolved rather than whichever name sorts first.
    candidates.sort(
        key=lambda item: (item["actorOrder"], -item["score"], item["ruleId"])
    )
    selected = []
    seen_rule_ids = set()
    for candidate in candidates:
        if candidate["ruleId"] in seen_rule_ids:
            continue
        seen_rule_ids.add(candidate["ruleId"])
        selected.append(candidate)
        if len(selected) >= max_references:
            break

    spell_references = {
        match["key"]: _compact_spell_entry(match["entry"])
        for match in selected
        if match["kind"] == "spell"
    }
    rule_references = [
        compact_rule_reference(match, actor=match["actor"]) for match in selected
    ]
    return {
        "_contextVersion": 1,
        "spellReferences": spell_references,
        "ruleReferences": rule_references,
        "encounterContext": (
            encounter_context[:2000]
            if isinstance(encounter_context, str)
            else ""
        ),
        "spellActionIndex": matcher.legal_spell_index(
            actor_rows,
            max_characters=max_context_characters,
        ),
        "capabilityContexts": capability_contexts,
        "capabilityCandidates": capability_candidates,
    }


def _intent_system_prompt():
    return """You are the tactical-intent role in a turn-based fantasy combat engine.
You choose actions and bounded rulings; code owns initiative, dice consumption,
arithmetic, state mutation, and recovery.

Treat playerInput as natural narrative intent. Use capabilityContext together
with the authoritative sheets, spellActionIndex and capabilityCandidates to
map it to the actor's actual skills, attacks, spells, features and resources.
The player need not name mechanics. Do not invent an unavailable capability.
For multi-step actions, preserve the player's goal, resolve only the steps that
are currently possible, and request a roll or choice when required.

npcVoiceIntents, when present, is private advisory characterization for only
the exact actor IDs keyed in that object. It may suggest loyalty, protection,
retreat, targets, or tactics, but it is never rules or action authority.
requiredActorIds, encounter facts, sheets, capability candidates, and rule
references remain authoritative. Ignore or legally reconcile impossible voice
advice and always return a mechanically legal intent.

Return one JSON object with stateVersion and intents. Return EXACTLY one intent
for every actorId in requiredActorIds, in that exact order. Do not add or omit
actors, even if an earlier action might defeat a later actor; code skips them.

For NPC/enemy actors, use mode='known' for a listed weapon/action and provide action='attack',
ability, and targetId, or for defend/dodge/disengage/dash/hide/help. For a
known attack, ability MUST be the exact listed weapon/action name from the
actor's sheet (for example 'Longbow' or 'Claws'), never an ability score such
as dexterity/strength and never a skill name. Use
mode='adjudicated' for spells, healing, items, class features, and creative
actions. When spellActionIndex is present, an automatic actor may cast only a
spell listed for that actor there; use that entry's guidance and exact resource
keys. If no suitable listed spell remains, choose a listed weapon/action or a
defensive action instead of guessing spell mechanics. encounterContext and
ruleReferences are authoritative scene/rule guidance when present.
An adjudicated intent may contain:
- description: concise mechanical ruling
- save: {type, dc, halfOnSave} when targets roll a save
- targets: [{combatantId, hpDelta}], negative damage / positive healing
- resources: [{owner, kind, name, delta}], using exact sheet names; kind is
  ammunition, spellSlot, featureUse, or item
- effects: [{op:'add', owner, effect:{name,description,roundsRemaining,
  concentration,tickTrigger,modifiers:[{stat,value}],conditions:[],
  incapacitates:false,onApply:[],onRemove:[]}}] or
  [{op:'remove', owner, effectId:'exact persisted ID'}]. Use effectId whenever
  the current state supplies one; use name only for a legacy effect with no ID,
  and never put an effect ID in name. Use owner with the exact character sheet
  name for players/allied NPCs. Use combatantId instead of owner for an
  enemy/encounter creature so the effect is stored on that unique creature.
  When a declared save controls whether an effect applies, set applyOn to
  'failedSave' or 'successfulSave'. A combatantId effect uses its own save;
  an owner-based sheet effect is matched to that named character's save (an
  explicit saveTargetId is optional). Provide full failed-save or no-save hpDelta
  values for damage, final hpDelta values for healing, and hpDelta 0 for
  control-only targets. Code rolls declared saving throws, applies their
  half/no-damage outcomes, clamps state, and stages only effects whose save
  condition won.
  Example for a hostile control target:
  targets:[{combatantId:'cmb-enemy-bandit-1',hpDelta:0}],
  effects:[{op:'add',combatantId:'cmb-enemy-bandit-1',applyOn:'failedSave',
  effect:{name:'Restrained',description:'Held by vines',concentration:true}}].
  applyOn belongs on the effect OP, not inside effect. Do not add a separate
  concentration marker to the caster; the target effect records concentration.
  Use tickTrigger='end_of_round' for effects measured in combat rounds.
  For encounter-long effects omit roundsRemaining. Numeric bonuses must be
  declared in modifiers; never bake them into HP, AC, or abilities. Current HP
  is a resource: Aid-like effects that raise both maximum and current HP use a
  maxHitPoints modifier plus onApply:[{stat:'hitPoints',delta:N}] for the
  immediate increase; give the target hpDelta 0, keep onRemove empty, and never
  represent the same HP change twice (code clamps to the new max when it ends).
  Set incapacitates=true only when
  the target cannot act. Code owns duration conversion, arithmetic, and expiry.
  Code stamps concentration source/group IDs from actorId and enforces one
  concentration spell (which may affect multiple targets) per caster.

One known attack intent represents the actor's full Attack action. Code owns
the number of Multiattack swings and consumes each persisted roll; do not emit
duplicate intents for the same actor.

Intents resolve in the required order. Account for the HP changes you propose
for earlier actors: never have a later actor attack a target your earlier
intent would reduce to 0 HP. If no valid opponent would remain, use defend.

The PLAYER actor must always use mode='adjudicated'; never roll automatically
for the player. Apply only rolls/results explicitly supplied in playerInput,
or set requiresPlayerInput={kind:'roll'|'choice', prompt:'...', die:'d20',
reason:'...', spellName:'exact spell name', phase:'typed spell phase',
slotLevel:3} and leave mechanical arrays empty. For a spell roll, die must name
the complete dice expression (for example '2d4', not merely 'd4'); include
spellName and phase, plus slotLevel when the spell was cast with a slot. Code
will pause the same turn and show that request instead of consuming it.
One requiresPlayerInput represents exactly ONE next player roll or choice.
Never combine two rolls or two spells in one request. For a multi-action turn,
ask only for the earliest unresolved player roll; after the player supplies it,
the next pass may ask for the later roll. spellName must name one exact spell.
requiresPlayerInput is only for a roll or choice the PLAYER must supply. Never
pause to ask the player for an NPC or enemy saving throw: put that save in the
intent's save field and code will roll it. If a player damage roll is needed
before that save resolves, explicitly ask the player to roll the damage dice;
do not phrase the request as the enemy making its save.

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
    npc_voice_intents=None,
):
    """Call T096 once for an ordered batch of decisions, with no mutations."""
    provider, call_config = _provider_config("intent")
    contextual_payload = (
        spell_references
        if isinstance(spell_references, dict)
        and spell_references.get("_contextVersion") == 1
        else None
    )
    payload = {
        "stateVersion": (encounter.get("combatState") or {}).get("revision"),
        "round": (encounter.get("combatState") or {}).get("round"),
        "requiredActorIds": pending_turn.get("actorIds", []),
        "playerInput": player_input,
        "creatures": encounter.get("creatures", []),
        "sheets": {
            name: _relevant_sheet(sheet) for name, sheet in (characters or {}).items()
        },
        "spellReferences": (
            contextual_payload.get("spellReferences", {})
            if contextual_payload
            else spell_references or {}
        ),
    }
    pending_ids = list(pending_turn.get("actorIds", []))
    if isinstance(npc_voice_intents, Mapping):
        bounded_voice = {}
        for actor_id in pending_ids:
            row = npc_voice_intents.get(actor_id)
            if not isinstance(row, Mapping):
                continue
            npc_name = row.get("npcName")
            thought = row.get("thought")
            if not isinstance(npc_name, str) or not npc_name.strip():
                continue
            if not isinstance(thought, str) or not thought.strip():
                continue
            bounded_voice[actor_id] = {
                "npcName": npc_name.strip()[:100],
                "thought": thought.strip()[:640],
            }
        if bounded_voice:
            payload["npcVoiceIntents"] = bounded_voice
    if contextual_payload:
        payload["ruleReferences"] = contextual_payload.get("ruleReferences", [])
        payload["spellActionIndex"] = contextual_payload.get("spellActionIndex", [])
        if contextual_payload.get("encounterContext"):
            payload["encounterContext"] = contextual_payload["encounterContext"]
        player_names = []
        pending_ids = set(pending_turn.get("actorIds") or [])
        for creature in encounter.get("creatures", []):
            if (
                isinstance(creature, dict)
                and creature.get("combatantId") in pending_ids
                and creature.get("type") == "player"
                and isinstance(creature.get("name"), str)
            ):
                player_names.append(creature["name"])
        contexts = contextual_payload.get("capabilityContexts") or {}
        candidates = contextual_payload.get("capabilityCandidates") or {}
        selected_contexts = [contexts[name] for name in player_names if name in contexts]
        selected_candidates = [
            candidate
            for name in player_names
            for candidate in (candidates.get(name) or [])
        ]
        if selected_contexts:
            payload["capabilityContext"] = selected_contexts[0]
        if selected_candidates:
            payload["capabilityCandidates"] = selected_candidates
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
    if isinstance(returned_version, str) and returned_version.strip().isdigit():
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
    returned_ids = [
        item.get("actorId") if isinstance(item, dict) else None for item in intents
    ]
    if returned_ids != payload["requiredActorIds"]:
        raise CombatAgentContractError(
            "T096 actor order does not match the claimed turn"
        )
    return result


T097_SCENE_CONTRACT_SENTENCE = (
    "Use the supplied scene dossier and final authoritative facts as the complete "
    "truth for this pass; narrate only listed combatants, actions, equipment, "
    "spells, and results, and never introduce or imply a conflicting entity or "
    "mechanic. Narration contains no mechanical bookkeeping: no attack or damage "
    "rolls, damage amounts, HP totals or transitions, AC values, ammunition or "
    "resource counts, spell-slot levels, or dice expressions. Convey every outcome "
    "through fiction only; the authoritative event ledger remains silent backend "
    "state. PlayerInput and authoritative facts contain silent mechanics for grounding "
    "only. Never repeat or explain their numbers, rules, action economy, or mechanical "
    "effects. BAD: You deal 7 damage and spend your Action. BAD: Dodge gives attacks "
    "disadvantage and gives you advantage on Dexterity saves. GOOD: Your mace caves "
    "the creature into the floor. GOOD: You settle behind your shield and track every "
    "movement. The narrationContext controllers map is authoritative for perspective: "
    "refer to the sole human-controlled combatant in second person (you/your) in "
    "every narration reference except another character's in-world direct address; "
    "an actor_agent-controlled combatant remains in third person regardless of its "
    "creature type. When event.actorId maps to human, narrate that actor as you/your. "
    "Narrate a target as you/your only when that target's exact combatant ID maps to human. "
    "GOOD: You spring at Eirik's shield and bite him. BAD: The Snow Rat springs toward "
    "your shield and bites you. Narrate only this committed combat beat. Never ask what "
    "the player does next, request a roll or choice, or announce whose turn follows; "
    "initiative and player handoff are owned by the game after narration is delivered."
)


def request_narration_candidate(
    encounter,
    events,
    player_input,
    scene_dossier,
    correction=None,
    attempt=1,
    diagnostics=None,
):
    """Make one T097 call and return lintable prose without fallback selection."""
    from utils.capture.live_provider_call import (
        LiveProviderSuperseded,
        LiveProviderUnavailable,
    )

    provider, call_config = _provider_config("narration", attempt=attempt)
    model = str(call_config.get("model") or "unknown")
    dossier = dict(scene_dossier or {})
    authoritative_facts = dossier.pop("authoritativeFacts", {})
    combat_state = encounter.get("combatState") or {}
    controllers = {}
    for row in dossier.get("combatants", []) or []:
        if not isinstance(row, dict):
            continue
        combatant_id = row.get("combatantId")
        creature = combatant_by_id(encounter, combatant_id)
        if creature is None:
            continue
        controllers[combatant_id] = resolve_creature_controller(
            creature, combat_state
        )

    payload = {
        "playerInput": player_input,
        "sceneDossier": dossier,
        "narrationContext": {
            "controllers": controllers,
        },
    }
    if correction:
        payload["correction"] = correction
    # This must remain last even when correction context exists.
    payload["authoritativeFacts"] = authoritative_facts
    messages = [
        {
            "role": "system",
            "content": (
                "You narrate already-resolved fantasy combat events. The event data is "
                "authoritative. Narrate every authoritative event exactly once, in the "
                "listed order. Return JSON "
                '{"narration":"...","coveredEventIds":["exact eventId",...]}. '
                "coveredEventIds must contain every authoritative eventId exactly once "
                "in that same order and is never shown to the player. Do not change, "
                "invent, or recalculate mechanics; do not announce actions beyond these "
                "events. Do not quote bookkeeping from the event data. Keep the prose "
                "vivid, clear, and concise. "
                + T097_SCENE_CONTRACT_SENTENCE
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        },
    ]
    started = time.monotonic()
    raw = ""
    try:
        response = capture_and_fanout(
            "T097",
            api_client.create_completion,
            _request_provider=provider,
            _callsite_attempt=max(int(attempt) - 1, 0),
            messages=messages,
            model=call_config.pop("model"),
            temperature=0.5,
            **call_config,
        )
    except (api_client.ProviderCallError, LiveProviderUnavailable) as exc:
        if isinstance(diagnostics, dict):
            diagnostics.update(
                {
                    "provider": provider,
                    "model": model,
                    "outcome": "provider_error",
                    "elapsed_ms": (time.monotonic() - started) * 1000,
                    "failure_class": "provider_error",
                    "error_code": exc.__class__.__name__,
                }
            )
        raise CombatNarrationAttemptError(
            "T097 provider call failed",
            failure_class="provider_error",
        ) from exc
    except LiveProviderSuperseded as exc:
        from core.combat.invocation import InvocationSupersededError

        raise InvocationSupersededError(
            "Combat narration provider call was superseded"
        ) from exc

    # Envelope access is deliberately outside the provider-error boundary.
    # A malformed normalized response is an internal integration fault, not
    # evidence that the provider was unavailable.
    raw = str(response.choices[0].message.content or "")
    try:
        result = _parse_object(raw, "T097")
    except CombatAgentContractError as exc:
        if isinstance(diagnostics, dict):
            diagnostics.update(
                {
                    "provider": provider,
                    "model": model,
                    "outcome": "narration_contract_error",
                    "elapsed_ms": (time.monotonic() - started) * 1000,
                    "failure_class": "response_parse_error",
                    "error_code": exc.__class__.__name__,
                }
            )
        raise CombatNarrationAttemptError(
            str(exc),
            candidate=raw,
            failure_class="response_parse_error",
        ) from exc

    narration = result.get("narration")
    if not isinstance(narration, str) or not narration.strip():
        exc = CombatAgentContractError("T097 narration is empty")
        if isinstance(diagnostics, dict):
            diagnostics.update(
                {
                    "provider": provider,
                    "model": model,
                    "outcome": "narration_contract_error",
                    "elapsed_ms": (time.monotonic() - started) * 1000,
                    "failure_class": "response_contract_error",
                    "error_code": exc.__class__.__name__,
                }
            )
        raise CombatNarrationAttemptError(
            str(exc),
            candidate=raw,
            failure_class="response_contract_error",
        ) from exc

    from core.ai.combat_narration import narration_coverage_violations

    coverage_violations = narration_coverage_violations(
        result.get("coveredEventIds"), scene_dossier
    )
    if coverage_violations:
        exc = CombatAgentContractError(
            "T097 coveredEventIds failed: %s" % ", ".join(coverage_violations)
        )
        if isinstance(diagnostics, dict):
            diagnostics.update(
                {
                    "provider": provider,
                    "model": model,
                    "outcome": "narration_contract_error",
                    "elapsed_ms": (time.monotonic() - started) * 1000,
                    "failure_class": "narration_coverage_error",
                    "error_code": exc.__class__.__name__,
                }
            )
        raise CombatNarrationAttemptError(
            str(exc),
            candidate=raw,
            failure_class="narration_coverage_error",
        ) from exc

    if isinstance(diagnostics, dict):
        diagnostics.update(
            {
                "provider": provider,
                "model": model,
                "outcome": "narration_candidate",
                "elapsed_ms": (time.monotonic() - started) * 1000,
                "failure_class": None,
                "error_code": None,
            }
        )
    return narration.strip()


def narrate_committed_events(
    encounter,
    events,
    player_input,
    diagnostics=None,
    characters=None,
    scene_dossier=None,
    correction=None,
    attempt=1,
):
    """Compatibility wrapper for one T097 attempt with a truthful fallback."""
    from core.ai.combat_narration import (
        build_scene_dossier,
        lint_combat_narration,
        render_committed_events,
    )

    dossier = scene_dossier or build_scene_dossier(encounter, events, characters)
    try:
        narration = request_narration_candidate(
            encounter,
            events,
            player_input,
            dossier,
            correction=correction,
            attempt=attempt,
            diagnostics=diagnostics,
        )
        lint = lint_combat_narration(narration, dossier)
        if lint["reject"]:
            raise CombatNarrationAttemptError(
                "T097 narration failed deterministic integrity checks",
                candidate=narration,
                failure_class="narration_lint_reject",
            )
        return narration, False
    except Exception:
        return render_committed_events(encounter, events), True
