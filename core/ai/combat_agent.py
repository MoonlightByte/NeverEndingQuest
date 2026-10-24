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
from core.ai.combat_capabilities import build_player_capability_context
from core.ai.srd_reference import (
    SRDContextMatcher,
    SRDReferenceError,
    SRDReferenceIndex,
    load_srd_reference_index,
    normalize_rule_name,
)
from core.combat.down_scene import from_encounter as down_scene_rules_from_encounter
from core.managers.combat_state import combatant_by_id, resolve_creature_controller
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
from utils.capture.live_provider_call import LiveProviderSuperseded
from utils.character_sheet_contract import extract_json_object


register_callsite("T096", "core/ai/combat_agent.py", 142)
register_callsite("T097", "core/ai/combat_agent.py", 220)


class CombatAgentContractError(ValueError):
    """A provider response did not satisfy the combat role contract."""


class CombatNarrationAttemptError(CombatAgentContractError):
    """One T097 call failed before producing lintable narration."""

    def __init__(self, message, candidate="", failure_class="response_contract_error"):
        super().__init__(message)
        self.candidate = str(candidate or "")
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
        "temporaryHitPoints",
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
        "concentration",  # CC: the caster's record (name, group, targets)
        # D-242 (ruling 5): the tactical model chooses rescues from what the
        # sheets actually hold, so equipment, feats, skills and proficiencies
        # travel whole, for every combatant, every window. No filtering.
        "equipment",
        "feats",
        "skills",
        "proficiencies",
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


def build_contextual_spell_payload(
    characters,
    actor_names=None,
    encounter_context=None,
    index=None,
):
    """Build the typed T096 spell and capability context for the actor window.

    Nothing here reads the player's words or the scene prose (D-KW-5): every
    spell on a window actor's sheet travels in spellActionIndex with its
    guidance and resource keys, and every owned capability in the sheets and
    capabilityContexts.
    """
    index = index or load_srd_reference_index()
    matcher = SRDContextMatcher(index=index)
    names = list(actor_names or ())
    if not names:
        names = sorted((characters or {}).keys())
    actor_rows = [
        (name, (characters or {}).get(name))
        for name in names
        if isinstance((characters or {}).get(name), dict)
    ]
    return {
        "_contextVersion": 1,
        "encounterContext": encounter_context if isinstance(encounter_context, str) else "",
        "spellActionIndex": matcher.legal_spell_index(actor_rows),
        "capabilityContexts": {
            actor_name: build_player_capability_context(sheet, actor_name=actor_name)
            for actor_name, sheet in actor_rows
        },
    }


def _spell_attack_prompt():
    """#672: the paragraph for the spell attacks code asks for and scores,
    named from the typed records; empty when the records are unavailable
    (then every spell keeps the model's roll request)."""
    try:
        from core.ai import srd_spell_attacks

        records = srd_spell_attacks.load_spell_attacks()["attacks"]
        names = sorted(record["name"] for record in records.values())
    except Exception:
        return ""
    if not names:
        return ""
    listed = names[0] if len(names) == 1 else "%s or %s" % (", ".join(names[:-1]), names[-1])
    return (
        "A player's %s cast at one hostile creature is asked for and scored by\n"
        "code too: declare action='cast', the exact spell name as ability and\n"
        "targetId, targets empty, the spell's resources (its spell slot, if any)\n"
        "and no requiresPlayerInput. Code asks for the d20 and, on a hit, the\n"
        "damage dice, and deals the damage. An effect the spell grants only on a\n"
        "hit (Guiding Bolt's Advantage on the next attack roll against the\n"
        "target) gets applyOn 'hit'; code stages it only when the attack hits.\n"
        "A later attack of a spell that persists (Spiritual Weapon on later\n"
        "turns) is declared the same way and spends no slot: send slotLevel,\n"
        "the level it was cast at.\n"
        "Every other spell attack keeps requiresPlayerInput as below.\n\n" % listed
    )


def _intent_system_prompt():
    return """You are the tactical-intent role in a turn-based fantasy combat engine.
You choose actions and structured rulings; code owns initiative, dice consumption,
arithmetic, state mutation, and recovery.

Treat playerInput as natural narrative intent. Use capabilityContext together
with the authoritative sheets and spellActionIndex to map it to the actor's
actual skills, attacks, spells, features and resources.
The player need not name mechanics. Do not invent an unavailable capability.
Words that describe a creature ("the crossbow bandit", "the archer", "the one
with the axe") name the target, never the player's weapon. When the player
names none of their own weapons, the verb picks one from their sheet ("shoot"
is their listed ranged weapon, the one they used last when several fit); never
ask about or refuse a weapon the player did not say they were using. "The one
they used last" is the actor's creatures[].lastWeaponRows entry for that kind
(melee, ranged for shots, thrown); when it is absent, pick from the sheet.
For multi-step actions, preserve the player's goal, resolve only the steps that
are currently possible, and request a roll or choice when required.

npcVoiceIntents, when present, is private advisory characterization for only the exact actor IDs keyed in that object. For an advised companion, treat 'do' as the primary characterization when selecting a mechanically legal action, target, posture, and tactical purpose. Use 'say' and 'want' to preserve the companion's voice and motive in that legal choice. 'thought' is secondary subtext: it may refine a compatible choice but must not displace a legal, scene-compatible do. The encounter, requiredActorIds, sheets, capabilities, resources, and rule references remain authoritative. Ignore or reconcile impossible advice without inventing mechanics. If an advised NPC's proposed action or target has become stale because the ordered scene changed, you may adjust that NPC's action or target to a mechanically legal, scene-compatible expression of the same motive and voice; never alter the player's submitted action, invent a capability, or reorder actors. For every advised companion intent, include a description that preserves the chosen action intent and any scene-compatible line or motive needed by downstream narration; never quote or reveal private thought.

Return one JSON object with stateVersion and intents. Return EXACTLY one intent
for every actorId in requiredActorIds, in that exact order. Do not add or omit
actors, even if an earlier action might defeat a later actor; code skips them.

Any actor may end its part in the fight: action='yield' (surrenders, stands
down, accepts a demand) or action='flee' (leaves the fight on its feet). Choose
one when the scene calls for it: broken morale, a demand the actor accepts, a
goal already won or lost, no reason left to fight. Mindless, bound or driven
creatures rarely do either. A player whose input is to run, withdraw, escape,
surrender or stand down gets action='flee' or action='yield'. Code marks that
actor out of the fight and keeps its hit points; the fight ends when every
hostile that can act is down or has left, or when the whole party has left.

Every listed row on a sheet (attacksAndSpellcasting, actions,
specialAbilities) carries a rowRef {combatantId, family, index}. To use a row,
copy that actor's own rowRef exactly as abilityRow and its name as ability;
code finds the row by abilityRow only, and ability is display text.
For NPC/enemy actors, use mode='known' for a listed weapon/action and provide action='attack',
abilityRow, ability, and targetId, or for defend/dodge/disengage/dash/hide/help/flee/yield. For a
known attack, abilityRow MUST be the rowRef of a listed weapon/action row of
that actor (for example its 'Longbow' or 'Claws' row), never an ability score
such as dexterity/strength and never a skill name. Use
mode='adjudicated' for spells, healing, items, class features, and creative
actions. A listed entry with kind 'save' (a web, a breath weapon, a gaze: its
save object states ability, dc, halfOnSave and onFail) is also adjudicated:
mode='adjudicated', abilityRow set to that entry's rowRef and ability to its name, save copied
from the entry, one target record per creature it reaches (hpDelta 0 when it
only imposes conditions) and, for its onFail conditions, an effect op gated
applyOn 'failedSave'. Code takes the save's type and dc, the onFail damage
dice and the onFail conditions from the stat block itself and corrects what
you wrote, so use such an ability whenever the scene calls for it. Entries of
kind 'trait' (Web Sense, Spider Climb, Pack Tactics) are never actions; an
entry's description is its rule text (range, area, escape DC) for your ruling.
A creature's `recharge` record (on its creatures entry) lists abilities it has
spent, for example {Web: {state:'spent', rechargesOn:'5-6'}}: code rolls the
d6 at the start of that creature's turn and clears the record when it
returns; never declare an ability the record shows as spent. A listed attack
with a `rider` (a venomous bite) is a plain known attack: on a hit code rolls
the target's rider save, its damage and its conditions from the stat block.
When spellActionIndex is present, an automatic actor may cast only a
spell listed for that actor there; use that entry's guidance and exact resource
keys. If no suitable listed spell remains, choose a listed weapon/action or a
defensive action instead of guessing spell mechanics. encounterContext and
ruleReferences are authoritative scene/rule guidance when present.
An adjudicated intent may contain:
- description: mechanical ruling
- save: {type, dc, halfOnSave} when targets roll a save
- targets: [{combatantId, hpDelta}], negative damage / positive healing
- featureName: when the intent heals with a class feature's pooled use (a
  featureUse resource such as Channel Divinity or Second Wind), the option
  used, exactly as featureNames lists it for that actor; code takes the
  heal's limit from it
- resources: [{owner, kind, name, delta}], using exact sheet names; kind is
  ammunition, spellSlot, featureUse, or item (a feat's use, FEAT ... uses, is
  kind featureUse with the feat's exact name, and a spell cast with it spends
  no spellSlot). owner is the sheet that HOLDS
  the resource, which need not be the actor: an ally administering a potion
  from the downed character's own pack lists owner as that downed character
  and name as the item exactly as that sheet lists it. Read the sheets before
  choosing: for an NPC or enemy whose slot or feature use is spent and no
  party sheet holds the item, do not declare the spell, feature or potion at
  all; take a real listed action. The PLAYER's spent slot or feature use is
  never a reason to choose another action for them: set requiresPlayerInput
  {kind:'choice', prompt} saying it cannot be used (no slot of that level or
  no use left) and asking what they do instead.
  Every shot from a bow, crossbow, or sling in an adjudicated intent declares
  the ammunition it fires: kind 'ammunition', the ammunition name exactly as
  the shooter's sheet lists it, delta -1 per shot. Every player shot is
  adjudicated, so every player shot declares it; only a mode='known' attack
  spends ammunition by itself. The rules engine spends the declared delta;
  never write a quantity, and after the fight the engine returns the
  recoverable share.
  A wand, staff, rod or any equipment row with a `charges` object spends
  charges, never quantity: kind 'charges', name exactly as the holder's sheet
  lists it, delta = minus the count the item's text costs for ONE use of
  it (1 unless it says more; a staff spending 3 for one spell is delta -3).
  The cost is per use, never per dart, missile or target: one casting of a
  wand's spell, all its darts included, costs what the text says for that
  casting. owner is the sheet that holds it. The rules engine spends exactly
  or refuses; a row whose charges.current is 0 and whose text promises
  recharge may still be spent after a dawn has passed, so declare the use
  and let the engine answer. Never add charges in combat, never write a
  count, and never spend a charged item as kind 'item'. When the engine
  reports the item destroyed (its last charge gone), the narration says so.
  The PLAYER chooses the player's action. When the player asks to use an
  item that cannot pay for it (the sheet shows it destroyed, or its count
  too low and nothing promises a recharge), never resolve a null action and
  never choose another action for the player: set requiresPlayerInput
  {kind:'choice', prompt} narrating the attempt failing (the item flares
  with no effect or stays dark, and the bearer remembers it is spent) and
  asking what they do instead. An NPC may simply take another action.
  Do not refuse a use the count can still pay: when charges.current is at
  least the cost of ONE use, declare the use and let the rules engine
  answer; only a count below that cost with no recharge promised, or a
  destroyed item, is a failure.
- effects: [{op:'add', owner, effect:{name,description,roundsRemaining,
  concentration,tickTrigger,modifiers:[{stat,value}|{stat,die}],conditions:[],
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
  condition won. A party member's save is rolled by the rules engine with
  the sheet's total and the roll mode its conditions impose (a Restrained
  target has disadvantage on Dexterity saves, a Paralyzed one fails Strength
  and Dexterity saves): declare the save's type and dc only, never pre-apply
  disadvantage, a bonus or an automatic failure yourself. A save repeated at
  the end of the target's turn is an intent for that target with the same
  save and effects:[{op:'remove', ..., applyOn:'successfulSave'}]. Code does NOT roll adjudicated damage or healing dice: the
  engine never turns '2d8+3' in a description into a number. You roll those
  dice in the ruling and put the resulting integer in hpDelta. A heal left at
  hpDelta 0 restores nothing and still spends the slot or potion, so a
  healing spell, potion, or feature must always carry a positive hpDelta.
  Second Wind restores 1d10 + Fighter level: on the actor's own target also
  give rolled, the d10 face alone (the player's typed die, or your own roll
  for an NPC fighter); code sets the heal to rolled + the Fighter level.
  The sign rule above is absolute: damage is a NEGATIVE hpDelta (a 9-point
  sword hit is hpDelta -9), healing is positive; a positive hpDelta on a
  hostile heals it. The rules engine applies the value to the sheet:
  temporary hit points absorb damage first, totals clamp at 0 and at the
  maximum, and the engine sets unconscious at 0 and alive on healing. Never
  pre-subtract temporaryHitPoints from a damage hpDelta.
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
  the target cannot act; paralyzed, stunned, petrified and unconscious
  incapacitate by themselves. An effect's conditions (SRD names: restrained,
  paralyzed, poisoned...) are written to the target's condition list by code
  while the effect lasts and leave with it; the rules engine then applies
  them (speed, saving-throw modes, a held caster's concentration ends), so
  never restate or clear them yourself. A condition the sheet lists (the
  AFFECTED line) with no effect behind it ends with
  {op:'remove', owner or combatantId, condition:'restrained'} when the scene
  ends it (a successful escape, the webbing cut). Code owns duration conversion, arithmetic, and expiry.
  Code stamps concentration source/group IDs from actorId and enforces one
  concentration spell (which may affect multiple targets) per caster. A
  concentration save on damage is made by the rules engine and its result is
  already applied to the sheets you see: never roll that save, never remove a
  concentration effect because its caster was hit, and treat a caster whose
  sheet shows no concentration record as free to cast another.

One known attack intent represents the actor's full Attack action. Code owns
the number of Multiattack swings and consumes each persisted roll; do not emit
duplicate intents for the same actor. Never set a known attack's ability to
'Multiattack' itself or to any listed entry whose damageDice is 0d0: those
are containers or traits, not attacks (a kind 'save' entry is declared in
mode 'adjudicated' as described above). Give the rowRef of the single
weapon/action the Multiattack is made of (for example the 'Slam' row) and code
applies the extra swings.

Intents resolve in the required order. Account for the HP changes you propose
for earlier actors: never have a later actor attack a target your earlier
intent would reduce to 0 HP. If no valid opponent would remain, use defend.
A correction that says a target is already down reports the state projected
after the earlier intents in your own batch resolve with this round's dice;
creatures still shows the HP from the start of the window. Answer it by
keeping validatedIntents exactly as given and changing only the rejected
actor's targetId or action. Never redirect earlier actors onto the legal
target: that moves the same damage onto it and repeats the rejection.

Action names are typed facts. action='dodge' is the Dodge action for any
actor, the player included (mode='adjudicated', no targets, no effects): code
marks the actor and attack rolls against it have disadvantage until the start
of its next turn, so declare no effect for it. dash, disengage, hide and help
are their own action names too. defend means only that the actor holds its
position or cannot act; it has no mechanical effect. A `dodging` record on a
creatures entry is set and cleared by code; never declare or remove it.

An actor may also take ONE Bonus Action in the same turn, beside its Action:
put it in the intent's bonusAction, never in action, targets or resources.
For a feature, bonusAction.featureName is exactly one name from bonusActionNames
for that actor; an unlisted feature never goes in bonusAction.
Code resolves the bonus action first,
then the Action, which keeps its own rules (a dodge still has no targets);
only an Off-hand Attack comes after the Action.
Second Wind: bonusAction {featureName:'Second Wind', targets:[{combatantId:
the actor, hpDelta, rolled}]}, rolled the d10 face as above; code spends the
use and sets the heal. For the player, ask the d10 first with the intent's
requiresPlayerInput (phase 'healing', die '1d10') and give bonusAction once
it is answered. Cunning Action: bonusAction {featureName:'Cunning Action',
option:'dash'|'disengage'|'hide'}. Off-hand Attack (two Light melee weapons in
hand): after an Attack action made with one of them, one extra attack with
the other: bonusAction {featureName:'Off-hand Attack', abilityRow: the other
weapon's attack rowRef, ability: its name, targetId}, with no targets, rolls or request for
it; code rolls it (the player's dice are asked by code) and scores it. The
Action's own attack count never includes it.

A healing potion listed in bonusActionItems is a Bonus Action: emit bonusAction {item:{nqlId:the listed equipment id}, targetId:the drinker}, or item:{catalog_id:the listed catalog id} when no nqlId exists. Use only these typed ids, never an item name. It may accompany a leveled spell Action; the engine consumes one potion, rolls its catalog healing and caps HP before resolving the Action. The target must be a present living participant; you rule whether another participant is within reach and omit the potion use with an explanation if not. Represent every part of the turn as its Action or single bonusAction, or ask a choice when incompatible; never narrate a potion as already drunk while a roll is pending. Recorded spell attacks, including Ray of Frost, are scored by code: supply the cast and target, without deciding hit/miss or requesting damage yourself. Narrate only typed operations that resolved.

A player's plain swing with one listed melee weapon at one hostile creature
is asked for and scored by code: declare action='attack', the weapon row's
rowRef as abilityRow, its name as ability, and targetId, with targets and
resources empty. A plain shot
with one listed ranged weapon that fires ammunition (bow, crossbow, sling) is
declared the same way; code spends the ammunition. Any other player attack at
a creature states its outcome from the player's rolls in targets (hpDelta 0 on
a miss) or asks for the next roll it needs; it never ends with neither. Only for a
situational edge (cover, an unseen attacker, a clever setup) add
attackMode='advantage'|'disadvantage' with a short attackModeReason. When
the actor makes more than one attack this turn, set attacks to that number.

When the player's intent is a weapon attack or a spell that deals damage,
also give two short strings in your DM voice, second person, ASCII:
rollLead, one or two sentences showing the attempt as it begins (the
weapon or spell and the target as the player has seen it, never an id),
and hitLead, one sentence for the moment it lands. Neither states dice,
numbers, damage, saves, whether rollLead hits, or whether the target
falls. End each with asking the player for this roll in your own words,
or offer to roll it for them. Code shows the dice as a record beside your
words; your words carry the ask.

When the correction carries openRollReply, a roll is open. Write
requiresPlayerInput.prompt only: answer the player's line and ask again for
this same roll in your own words, offering to roll it. Only when
openRollReply carries dropAllowed: if the player's line gives this roll up
(they take the action back, change their mind, or name a different action to
take instead), set dropRoll: true on the player's intent instead of asking
again. Code then drops the roll and rules the line as a new plan; your
prompt in that reply is not shown, and only the new plan's turn speaks.
Never set dropRoll for a question, a remark or numbers, without dropAllowed,
or outside openRollReply. If
unfitting is set, say those numbers do not fit the dice. If
readerUnavailable is set, the game could not read the line as an answer:
ask for the roll again and never say a roll was made. State nothing about
the swing beyond mainSwing. If mainSwing is set, the off-hand attack is
already under way and only its dice are open: if the player wants to stop,
tell them plainly that only its dice remain and offer to roll it. This
takes precedence over the rules for a plain swing, a recorded spell attack
and the off-hand attack.

""" + _spell_attack_prompt() + """The PLAYER actor must always use mode='adjudicated'. Never invent a roll for
the player. The player asks the game to roll when they ask the DM or the game
to make this roll for them; then return playerRoll={gameRolls: true}, code
rolls the requested dice, and you rule again with the faces. A 'Game roll for
the DM's request' line is a roll supplied for the player: apply it as the
player's roll. Apply only rolls/results explicitly supplied in playerInput,
or set requiresPlayerInput={kind:'roll'|'choice', prompt:'...', die:'d20',
phase:'attack', reason:'...', spellName:'exact spell name',
slotLevel:3} and leave mechanical arrays empty. For EVERY roll, die must name
the complete unmodified dice expression (for example '2d8' for two damage dice,
not merely 'd8'); give only the currently requested phase, accounting for any
confirmed critical hit. Rider dice join the main die with + after it (for
example '1d8+1d6'). For EVERY roll, phase names that roll: a spell's typed
phase, otherwise 'attack' (main die 1d20, or 2d20 with advantage or
disadvantage), 'damage', 'healing', 'save' or 'check'. Keep flat bonuses out
of die and apply them once when
adjudicating the returned raw dice. Put the dice expression in prompt as well
as the weapon/action name so the player knows what to roll; write the request
in your own words and offer to roll it for them. For a spell include
spellName, plus slotLevel when the spell was cast with a slot (the level of
the spellSlot resource it spends). Code
will pause the same turn and show that request instead of consuming it.
When the request is about a weapon, set weaponName to the exact item or
action name from the player's sheet; leave weaponName out when the player
uses something not on their sheet (an improvised or picked-up weapon). A
roll with phase 'save' sets saverId to the combatantId of the creature
making the save, which is always the player actor itself, and dc, the
save's DC as an integer; code scores the player's answer at that dc.
One requiresPlayerInput represents exactly ONE next player roll or choice.
Never combine two rolls or two spells in one request. For a multi-action turn,
ask only for the earliest unresolved player roll; after the player supplies it,
the next pass may ask for the later roll. spellName must name one exact spell.
requiresPlayerInput is only for a roll or choice the PLAYER must supply. An
NPC or enemy actor never carries requiresPlayerInput: for an NPC spell, heal,
potion, or feature, roll its dice yourself in the ruling and supply the final
hpDelta and resources, so a companion's healing lands the moment it resolves.
Never pause to ask the player for an NPC or enemy saving throw: put that save
in the intent's save field and code will roll it. If a player damage roll is needed
before that save resolves, explicitly ask the player to roll the damage dice;
do not phrase the request as the enemy making its save.
A 'Withdrawn player action' line holds an action the player took back
before its roll: the withdrawn attack is not made from that roll; anything
the player did not take back may stand. Rule the player's lines after it;
if they name no new action, return the player's intent with empty targets,
resources and effects and requiresPlayerInput {kind:'choice', prompt}
asking in your own words what they do instead.
When a Player follow-up answers the roll in the DM requested line before it,
the player's intent carries playerRoll={phase: the phase of that request,
faces:[[...]]}: one list of integers per die term of the requested dice, in
order ('2d6' gives [[4,2]], '1d8+1d6' gives [[5],[3]]), holding exactly the
numbers the player gave, even a number the die cannot show; code checks them
against the request. Never add, drop or change a number, and never put a flat
bonus in faces. If the follow-up gives no number for the request and does
not ask the game to roll, omit playerRoll. When the game rolled for the
player, code fills playerRoll itself.
For the player's own saving throw (phase 'save'), put its type and dc in the
intent's save field and list the player in targets with the hpDelta a failed
save costs (0 if none): code scores that save from the player's d20, so do not
decide it yourself.

Never provide resulting HP totals, round numbers, cursor changes, narration other
than rollLead and hitLead, or prose outside JSON. Do not invent spell slots, ammunition, abilities, targets, or
actors. For a player actor, honor the submitted player action; adjudicate it
fairly rather than replacing it with a tactically preferred action. A player's
attack on any creature in creatures, an ally or a bystander included, is
honored: declare it with that creature's combatantId as targetId and adjudicate
it like any attack; never refuse it or ask the player to pick another target.
Code decides what follows (a bystander joins the fight as a hostile). For NPCs
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
    from core.combat.resolver import with_row_refs
    payload = {
        "stateVersion": (encounter.get("combatState") or {}).get("revision"),
        "round": (encounter.get("combatState") or {}).get("round"),
        "requiredActorIds": pending_turn.get("actorIds", []),
        "playerInput": player_input,
        "creatures": encounter.get("creatures", []),
        # K1: each listed row carries its rowRef (on copies; P-2), which the
        # reply returns as abilityRow.
        "sheets": with_row_refs({
            name: _relevant_sheet(sheet) for name, sheet in (characters or {}).items()
        }, encounter),
    }
    # D-242 consumer 1: the one rules string while any party member is down.
    down_rules = down_scene_rules_from_encounter(encounter)
    if down_rules:
        payload["downScene"] = down_rules
    pending_ids = list(pending_turn.get("actorIds", []))
    if isinstance(npc_voice_intents, Mapping):
        selected_voice = {}
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
            entry = {
                "npcName": npc_name,
                "thought": thought,
            }
            for field in ("say", "do", "want"):
                value = row.get(field)
                if isinstance(value, str) and value.strip():
                    entry[field] = value
            selected_voice[actor_id] = entry
        if selected_voice:
            payload["npcVoiceIntents"] = selected_voice
    # 8b: the featureName values each window actor may use (the heal
    # options its sheet qualifies for), typed from the sheet.
    from core.combat.resolver import feature_heal_names
    feature_names = {}
    for actor_id in pending_ids:
        creature = combatant_by_id(encounter, actor_id)
        names = feature_heal_names((characters or {}).get((creature or {}).get("name")))
        if names:
            feature_names[actor_id] = names
    if feature_names:
        payload["featureNames"] = feature_names
    # R2: the Bonus Actions each window actor may take beside its Action:
    # its class features whose SRD activation is a Bonus Action (typed data,
    # data/srd/progression.json feature_activation), from the sheet.
    from core.combat.bonus_actions import bonus_action_names
    from core.nql.item_use import available as available_items
    bonus_items = {}
    bonus_names = {}
    for actor_id in pending_ids:
        creature = combatant_by_id(encounter, actor_id)
        sheet = (characters or {}).get((creature or {}).get("name"))
        names = bonus_action_names(sheet)
        items = available_items(sheet)
        if items:
            bonus_items[actor_id] = items
        if names:
            bonus_names[actor_id] = names
    if bonus_names:
        payload["bonusActionNames"] = bonus_names
    if bonus_items:
        payload["bonusActionItems"] = bonus_items
    if contextual_payload:
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
        selected_contexts = [contexts[name] for name in player_names if name in contexts]
        if selected_contexts:
            payload["capabilityContext"] = selected_contexts[0]
    if correction:
        payload["correction"] = correction
    messages = [
        {"role": "system", "content": _intent_system_prompt()},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    try:
        response = capture_and_fanout(
            "T096",
            api_client.create_completion,
            _request_provider=provider,
            messages=messages,
            model=call_config.pop("model"),
            temperature=0.2,
            **call_config,
        )
    except LiveProviderSuperseded as exc:
        from core.combat.invocation import InvocationSupersededError

        raise InvocationSupersededError("Combat intent request was superseded") from exc
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


# #1423: read only when the dossier carries the hour (sceneDossier.scene).
T097_SCENE_TIME_SENTENCE = (
    " sceneDossier.scene.timeOfDay is the hour outside. It governs outdoor "
    "daylight only: a place's own darkness - underground, indoors, a cave, a "
    "moonless forest, or magical darkness - still applies whatever the hour, and "
    "a fallen character's dimming senses are neither."
)
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
    "initiative and player handoff are owned by the game after narration is delivered. "
    "NPC dialogue is characterization, not a source of equipment facts. Before "
    "repeating advice about a specific weapon or ability, verify it belongs to "
    "the addressed actor in the authoritative dossier. Rewrite unsupported advice "
    "as a grounded tactic; never attribute the companion's gear to the player. "
    "Give companions a distinct voice and an observable reaction appropriate to "
    "the committed outcome and their supplied personality, without repeating "
    "generic warnings or inventing additional actions, healing, or resources. "
    "A resource of kind charges states the item's count before and after; when "
    "its exhausted.outcome is destroyed the item is gone (narrate it crumbling, "
    "cracking or burning out), when it is regained the item flared back to life. "
    "A bonusAction with itemName is an item the actor used this turn before the "
    "Action; narrate the use and its applied hp change."
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
    npc_voice_intents = dossier.pop("npcVoiceIntents", None)
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
    if isinstance(npc_voice_intents, Mapping) and npc_voice_intents:
        payload["npcVoiceIntents"] = dict(npc_voice_intents)
    # D-242 consumer 2: the same rules string (rules only; facts stay with T096).
    down_rules = down_scene_rules_from_encounter(encounter)
    if down_rules:
        payload["downScene"] = down_rules
    # This must remain last even when correction context exists.
    payload["authoritativeFacts"] = authoritative_facts
    messages = [
        {
            "role": "system",
            "content": (
                "You narrate already-resolved fantasy combat events. The event data is "
                "authoritative. Narrate every authoritative event exactly once. Return JSON "
                '{"narration":"...","coveredEventIds":["exact eventId",...]}. '
                "coveredEventIds must contain every authoritative eventId exactly once "
                "in that same order and is never shown to the player. Do not change, "
                "invent, or recalculate mechanics; do not announce actions beyond these "
                "events. Do not quote bookkeeping from the event data. Keep the prose "
                "vivid and clear. You are the storyteller for this round, not its clerk. "
                "Write the round as a scene: group volleys and simultaneous blows into "
                "beats, let cause and consequence carry the order, and keep every outcome "
                "exactly as the events state. Narrate ONLY the events listed in "
                "authoritativeFacts for this beat. A wound, bolt, arrow, or blow that is "
                "not in those events did not happen this beat -- never mention it. "
                "One arrow is one arrow; "
                "a companion with one action this beat takes one action. npcVoiceIntents "
                "are the companions' own suggestions for what they would say, do, and "
                "want this beat, keyed by actor ID. Treat them as a cast handing you their "
                "lines: use the ones that serve the scene. Each suggestion belongs to "
                "exactly one companion -- check the actor ID before you quote, and never "
                "give one companion another's words. A suggestion that names the player "
                "in the third person is spoken TO the player: 'I'll keep the nearest "
                "blade off you, Eirik', never 'off Eirik' said to his face. Trim or "
                "reword rather than paste; terse characters get fragments. Let a "
                "companion act without speaking when that reads better, and show private "
                "thought only as demeanor. You may overrule a suggestion when the "
                "committed events or the player's moment call for it. Companions should "
                "sound like themselves -- terse ones stay terse, schemers stay sly. In a "
                "large fight the companions are part of the scene, heard and seen in "
                "their own manner as the story warrants, not listed by their attacks. "
                "Do not close the round with a roll call of who held their ground "
                "-- once a companion has been felt, let them be. End on the beat that "
                "matters most to the player. GOOD: Oswin steps into the gap without a "
                "word, his sword opening a warrior's arm, and only then speaks, low and "
                "even: 'I'll keep the nearest blade off you, Eirik.' "
                + T097_SCENE_CONTRACT_SENTENCE
                + (T097_SCENE_TIME_SENTENCE if dossier.get("scene") else "")
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
        party_scene_time,
        render_committed_events,
    )

    dossier = scene_dossier or build_scene_dossier(
        encounter, events, characters, scene_time=party_scene_time()
    )
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
        return narration, False
    except Exception:
        return render_committed_events(encounter, events), True
