#!/usr/bin/env python3
"""Startup author and reviewer prompts for the one shared wizard (#114)."""

import json
from pathlib import Path

from core.nql import creation_scope
from utils.encoding_utils import safe_json_load
from utils.startup_contract import STARTUP_REVIEW_SCHEMA, startup_response_schema


def _read_text_file(relative_path):
    path = Path(relative_path)
    if not path.exists():
        return ""
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


STARTUP_RULES_REFERENCE_PURPOSE = "startup_rules_reference"
ORIGINS_FILE = "data/srd_character_origins.json"


def _without(entries, *fields):
    """Entries without the typed keys the engine scope and build read (D-CREATE-COST-4/-5): the whole
    reference is the rollback profile and keeps #1278's bytes."""
    return [{k: v for k, v in e.items() if k not in fields} if isinstance(e, dict) else e for e in entries]


_typed_options = creation_scope.typed_options
_level_1_choices = creation_scope.level_1_choices
_level_1_features = creation_scope.level_1_features


def build_startup_rules_reference():
    """The creation reference both the author and the reviewer read, from typed data only.

    Returns None when a data file is missing; the interview then runs without it.
    """
    origins = safe_json_load(ORIGINS_FILE)
    choices = safe_json_load("data/srd/choices.json")
    items = safe_json_load("data/srd/item_catalog.json")
    if not origins or not choices or not items:
        return None
    # Fixed level-1 class features and class-table values (#682 E13). Optional: without the
    # progression file the reference keeps its earlier shape.
    progression = (safe_json_load("data/srd/progression.json") or {}).get("classes") or {}
    catalog = {e["id"]: e["name"] for e in items["entries"]}
    return {
        "task_purpose": STARTUP_RULES_REFERENCE_PURPOSE,
        "ruleset": "SRD 5.2.1",
        "attribution": choices["sources"]["attribution"],
        "use": ("This is the game's complete SRD 5.2.1 character-origin reference for this interview: "
                "backgrounds, species, Origin and Fighting Style feats, weapon mastery, the weapons table "
                "and each class's level-1 choices, fixed level-1 features and level-1 class-table values; "
                "the languages rule and the standard and rare languages, the armor table, the cantrip rule "
                "and the effects of each class order option. "
                "Each class's Starting Equipment choice (option_items) and each background "
                "(equipment_options) carry their typed options: the option key, the items with catalog ids, "
                "the coins and the slots a player picks. "
                "Use it for these facts instead of remembered rules. "
                "A fact absent here is not supplied."),
        "sheet_representation": (
            "SRD 5.2.1 backgrounds have no background feature: a background raises ability scores "
            "(background_ability_scores_rule) and grants an Origin feat, skills, a tool and equipment. "
            "Put the species name in race and the background name in background. Record the background's "
            "Origin feat in feats as {\"name\": \"<feat name>\", \"description\": \"<its text here>\", "
            "\"source\": \"<background> background (SRD 5.2.1)\"}, and set backgroundFeature to exactly "
            "{\"name\": \"Origin feat: <feat name>\", \"description\": \"<the same text>\", "
            "\"source\": \"<background> background (SRD 5.2.1)\"}. Other feats, such as a Human's "
            "Versatile Origin feat, also go in feats with their source. A chosen Fighting Style goes in "
            "classFeatures, not feats, as {\"name\": \"Fighting Style: <style name>\", \"description\": "
            "\"<its text here>\", \"source\": \"<class> level <level>\"}, the name level-up writes. "
            "Record the class's level-1 order choice as one classFeatures entry named exactly "
            "\"Divine Order: <option>\" or \"Primal Order: <option>\"."),
        "background_ability_scores_rule": origins["background_ability_scores_rule"],
        "backgrounds": [dict(b, equipment_options=_typed_options(b["equipment_options"], catalog))
                        if isinstance(b.get("equipment_options"), dict) else b
                        for b in _without(origins["backgrounds"], "feat_ref", "skill_keys", "tool_keys", "tool_choice",
                                           "ability_keys")],
        "species": _without(origins["species"], "key", "grants"),
        "origin_feats": _without(origins["origin_feats"], "key"),
        "fighting_style_feats": origins["fighting_style_feats"],
        "weapon_mastery_rule": origins["weapon_mastery_rule"],
        "weapon_mastery_properties": origins["weapon_mastery_properties"],
        "weapons": [{"name": e["name"], "description": e["description"]} for e in items["entries"]
                    if e.get("kind") == "weapon" and not e.get("magical")],
        # Each armor's description opens with its category ("Medium armor. ...").
        "armor": [{"name": e["name"], "description": e["description"]} for e in items["entries"]
                  if e.get("kind") == "armor" and not e.get("magical")],
        "languages": {"rule": origins["languages_rule"], "standard": choices["languages"]["standard"],
                      "rare": choices["languages"]["rare"]},
        "cantrip_rule": origins["cantrip_rule"],
        "class_order_options": origins["class_order_options"],
        "class_level_1": {name: dict({"primary_ability": choices["class_traits"][name]["primary_ability"],
                                      "choices": _level_1_choices(points, catalog)}, **_level_1_features(progression.get(name)))
                          for name, points in choices["choice_points"].items()},
    }


_WHOLE_FACTS = """The interview carries the game's SRD 5.2.1 creation reference (task_purpose
startup_rules_reference). Use it for species, background, Origin feat, weapon
mastery and level-1 class choice facts, and follow its sheet_representation.
SRD 5.2.1 backgrounds have no background features from older editions.
Classes and backgrounds come from the reference. For a request outside it, such
as a noble, keep the concept in the backstory and recommend the closest
reference background for the player to choose.
"""

# The scoped path (D-CREATE-COST-4): engine scope items instead of the whole reference, and the intent contract.
_SCOPED_FACTS = """The interview carries the game's SRD 5.2.1 creation scope (task_purpose
startup_creation_scope), which the engine appends as the player's choices
narrow: a menu while the class, species or background is not yet named, then
the facts and level-1 choices of the ones named. The latest scope item is the
current one. Use it for species, background, Origin feat, weapon mastery, spell
and level-1 class choice facts, and follow its sheet_representation.
SRD 5.2.1 backgrounds have no background features from older editions.
Classes, species and backgrounds come from the scope. For a request outside it,
such as a noble, keep the concept in the backstory and recommend the closest
scope background for the player to choose.
INTENT, ON EVERY RESPONSE: set intent to what the player has chosen or approved
so far, never to your own suggestion. class_key, species_key and background_key
are the scope's keys, null until the player chooses. choices maps each choice id
of the current scope to the option keys picked, exactly as the scope gives them
(spells by their key); a pick the player delegated to you and then approved
counts as chosen. considering lists the class, species and background keys the
player is asking about but has not chosen. When the intent changes the scope,
the engine appends the new scope item and asks again for the same answer: answer
from the new scope. A startup_choices_dropped item lists picks a switch removed;
ask again for any the new build still needs. A startup_choice_refusal item names
picks outside the current scope; correct them from the scope.
Ids are for the typed fields only: catalog ids (itemdef:...), choice ids and
option keys go in intent and starting_equipment, never in narration. The scope
gives each its name; the player sees names only, such as "Chain Mail", not its id.
THE ENGINE BUILDS THE SHEET: you record choices; the engine builds the whole
character from intent and computes every number. A startup_open_choices item
lists the choice ids still open: for each, ask the player, or, only when the
player asks you to choose, pick from the scope's options yourself and record it
in intent. Never leave one open at finalize. A package or option the player has
already named is chosen: record it and do not ask it again.
Offer only a choice's option_keys from the scope; a skill the background grants
is never offered.
Set choice_turn on every response: asks lists each choice id your narration asks
the player about this turn, and refused each option your narration says the
player cannot pick. Refuse only an option the scope does not offer, and ask only
about open choice ids. To let the player change a choice already made, clear its
picks in intent, then ask it.
When the player says they are new or overwhelmed, ask one choice per turn and
say how many remain.
Record package and slot picks in starting_equipment as soon as the player gives
them, on every turn after; a package not yet chosen is null.
A background's package is recorded only in starting_equipment.background_package;
it has no choice id.
When the player approves the whole build, finalize with your proposed creative
fields; do not ask approval for details you add at finalize.
Set intent.ability_scores to the player's method and the base score for each
ability once the player has placed them. A startup_ability_roll item holds the
engine's roll, made once for the interview: show those numbers and record the
player's assignment of exactly them.
Once no choice id is open and the ability scores are set, the game shows the
player a summary rendered from the engine-built sheet after your narration (a
startup_sheet_preview item): that is the build the player approves.
An interview begun before the engine built sheets may lack typed intent: ask
again for any choice the intent does not hold. Earlier prose, sheets and rolls
are context, never recorded choices.
"""

_WHOLE_COMPLETE = """build presented as complete names every required level-1 choice in the
reference: background"""
_SCOPED_COMPLETE = """build presented as complete fills every choice id in the current scope with its
count of picks: background"""


# The engine-path author prompt (D-CREATE-COST-5): the whole prompt with the parts that ask the author to
# write a sheet replaced. Each old text must occur exactly once (the whole prompt stays #1278's bytes).
_ENGINE_EDITS = (
    ("""The player chooses the ability-score method. For player-rolled scores, ask them
to submit their actual results and allocation; never invent, replace, or reroll
them.""", """The player chooses the ability-score method: standard array, point buy, or random.
For random, the engine rolls once for the interview; never ask the player to roll,
and when a player states rolls of their own, offer the engine's roll, the standard
array or point buy instead."""),
    ("""finalize_character with the full sheet: fill derived values (hit points, armor
class, modifiers, proficiency bonus) from the approved choices. Set origin to
the class and background keys, and starting_equipment to""", """finalize_character with intent, creative and starting_equipment; the engine
builds the sheet and you never write one. Set starting_equipment to"""),
    ("""A whole-build summary that asks for approval:
- Start with one short lead sentence.
- Then these labelled sections in this order, each label alone on its own line
  and its items below it as "- " lines: "Ability scores:" (one line per
  ability, such as "- Strength 15 (+2)"), "Background & feats:", "Skills:",
  "Weapons & masteries:", "Equipment:", and "Spells:" (leave Spells out for a
  build with no spells). Put a blank line between sections.
- End with this line on its own: Approve this build, or tell me what to change.""", """A turn that asks for whole-build approval (no choice id open, ability scores set):
- Write one short lead sentence naming the character's concept; the game then
  shows the player the summary it renders from the engine-built sheet.
- Name the chosen starting packages and what is worn or held, on "- " lines.
- End with this line on its own: Approve this build, or tell me what to change."""),
    ("""Its character, origin and starting_equipment must be null
and whole_build_approved false.""", """Its creative must be null, starting_equipment holds the
package and slot picks given so far, and whole_build_approved is false."""),
    ("""build and you can provide its full character sheet.""", """build and no choice id is open."""),
    ("""It has character, origin and starting_equipment null, whole_build_approved
false,""", """It has creative null, starting_equipment as given so far, whole_build_approved
false,"""),
    ("""Use the frozen CHARACTER SCHEMA for character, not for the outer response.
Include ammunition (an empty array when none), all required fields, and valid
enum values. New characters start at level 1 with experience_points 0 and player
role/type. Preserve existing dictionary-form skills when supplied; do not turn
existing data into empty defaults. For new builds include chosen proficiencies,
consistent languages, attacks, modifiers and SRD features, and write
"currency": {"gold": 0, "silver": 0, "copper": 0}, "equipment": [] and
"ammunition": []: the game replaces all three from the chosen packages. Spell
attacks use type "spell"; the engine writes the weapon attack rows. No schema
metadata in a character object. Unused temporaryEffects, injuries and
equipment_effects are empty arrays, not invented timed effects.
Starting gear is represented once: the game merges the two packages, and an item
both list is one row with the quantities summed.
The attack list describes available options, not weapons wielded simultaneously.
Keep carried/stowed weapons and their attack statistics without falsely marking
them wielded or changing armor class; describe prerequisites when relevant.
Keep approved backstory in the existing descriptive fields or interview context;
do not distort a mechanical background name to satisfy an invented schema slot.
""", """CREATIVE, AT FINALIZE: name, alignment, personality_traits, ideals, bonds and
flaws, in the player's words or as you proposed and the player approved (none
may be empty: when the player gave no ideal or flaw, propose one and ask the
player to approve it before finalizing); and
optionally backstory, appearance and feature_descriptions (one short description
per class feature the engine names, written from that feature's scope text). The
engine copies them as written and never reads them for mechanics. Alignment is
the player's if given; otherwise propose one. The player never has to choose it.
"""),
)


def engine_prompt_drift(prompt, schema):
    """The rewrite anchors the whole prompt no longer holds exactly once (empty when none drifted)."""
    anchors = [old for old, _ in _ENGINE_EDITS] + ["CHARACTER SCHEMA:\n%s\n\n" % json.dumps(schema, indent=2)]
    return [old[:60] for old in anchors if prompt.count(old) != 1]


# The fallback's one override line (Sentinel N9): the drifted prompt may still ask for a sheet.
ENGINE_CONTRACT_OVERRIDE = (
    "ENGINE CONTRACT (overrides any line above that asks you to write a character sheet, character or origin): "
    "the engine builds the sheet. finalize_character carries only intent, creative and starting_equipment, "
    "exactly as the STARTUP RESPONSE SCHEMA gives them; never send character or origin.\n\n")


def _engine_prompt(prompt, schema):
    """The engine-path author prompt. On drift (Sentinel N8, N9) the interview goes on with the whole prompt
    unedited except that its CHARACTER SCHEMA block is dropped and one override line states the engine
    contract before the response schema, so a finalize still builds; a warning is logged and a tracked test
    pins the anchors."""
    block = "CHARACTER SCHEMA:\n%s\n\n" % json.dumps(schema, indent=2)
    drift = engine_prompt_drift(prompt, schema)
    if drift:
        from utils.enhanced_logger import warning
        warning("STARTUP: engine prompt rewrite skipped, the whole prompt changed near %r" % drift,
                category="startup")
        prompt = prompt.replace(block, "")
        head, marker, tail = prompt.rpartition("STARTUP RESPONSE SCHEMA:")
        return head + ENGINE_CONTRACT_OVERRIDE + marker + tail if marker else prompt + "\n" + ENGINE_CONTRACT_OVERRIDE
    for old, new in _ENGINE_EDITS:
        prompt = prompt.replace(old, new)
    return prompt.replace(block, "")


def build_character_creation_system_prompt(*, scoped=False):
    """Build module-independent character authorship instructions. scoped: the engine-scope
    author prompt (D-CREATE-COST-4); otherwise the whole-reference prompt, byte for byte."""
    schema = safe_json_load("schemas/char_schema.json")
    if not schema:
        raise ValueError("Could not load character schema")
    leveling_info = _read_text_file("prompts/leveling/leveling_info.txt")
    facts = _SCOPED_FACTS if scoped else _WHOLE_FACTS
    complete = _SCOPED_COMPLETE if scoped else _WHOLE_COMPLETE
    prompt = f"""You are a friendly character creation guide for a fifth edition
fantasy adventure, using SRD 5.2.1. The installed adventure and its real context
are supplied by the wizard; never assume a particular campaign or destination.

Conduct a natural, concise interview. Ask about major identity choices (name,
race, class, background), offer appropriate choices, summarize the developing
build, and honor revisions. Do not choose those major decisions for the player.
The player chooses the ability-score method. For player-rolled scores, ask them
to submit their actual results and allocation; never invent, replace, or reroll
them. Use supplied rules for mechanics and preserve accepted choices.
{facts}Extra gear is bought or found in play; a keepsake from the backstory stays in
the backstory text.
After the player approves the whole current build, the next step is
finalize_character with the full sheet: fill derived values (hit points, armor
class, modifiers, proficiency bonus) from the approved choices. Set origin to
the class and background keys, and starting_equipment to the chosen package
keys, one slot_picks entry per slot of those packages (catalog_id for a
choose_one slot, the player's own display_name for a slot without one) and
equipped. Code and the
rules engine then set level-1 hit points, armor class and engine attack rows
and starting gold and gear: the gear comes from the packages; name what is worn
or held, by catalog id, in starting_equipment.equipped. If a real player
choice is still open, such as a gaming set or a skill pick, ask only that once
and keep everything approved; never invent a player choice.
When the player delegates open choices to you, decide each one and present a
single recommended pick per choice for approval, never a menu of options. A
{complete} ability increases, every skill, tool or gaming set pick,
each Origin feat and its own choices, class choices, both the class and the
background starting equipment, each package choice (holy symbol, instrument,
gaming set) and what is worn or held.

ONE WIRE CONTRACT, ON EVERY RESPONSE:
Return only one JSON object matching STARTUP RESPONSE SCHEMA below.
All player-facing text belongs in narration, as plain text, no code fences
or machine instructions. Address the player in second person. The application
displays only accepted narration, never this wire object or its character data.
Write the player's names exactly as the player spells them, accents and
non-Latin letters included.

NARRATION LAYOUT (presentation only; every rule above and below still applies):
The game shows narration line by line, exactly as written. Never write one long
paragraph of choices or of build details. Use plain lines only: no Markdown
headings (#), tables, bold or italic markers, and no numbered choices inside a
sentence. Put a blank line between the lead sentence and the list.
A turn that asks for choices:
- Start with one short lead sentence.
- Put each pending decision on its own line starting with "- ", naming the
  decision and then all of its options after a colon, in this shape:
  - <decision>: <option>, <option> or <option>
- Ask at most three or four decisions per turn, grouped in this order:
  background decisions first, then species decisions, then class decisions.
  Ask the remaining decisions in later turns and keep every answered one.
- When the player has delegated choices, use the same lines with your single
  recommended pick after each decision's colon.
A whole-build summary that asks for approval:
- Start with one short lead sentence.
- Then these labelled sections in this order, each label alone on its own line
  and its items below it as "- " lines: "Ability scores:" (one line per
  ability, such as "- Strength 15 (+2)"), "Background & feats:", "Skills:",
  "Weapons & masteries:", "Equipment:", and "Spells:" (leave Spells out for a
  build with no spells). Put a blank line between sections.
- End with this line on its own: Approve this build, or tell me what to change.
Other turns, such as a single question or a correction, may be one short
paragraph; still put any list of options on separate "- " lines.

Use continue_interview while collecting choices, summarizing, or asking for
whole-build approval. Its character, origin and starting_equipment must be null
and whole_build_approved false.
Understand approval from the complete conversation and latest real user input,
not a required phrase or keyword. Approval of one detail, negation, uncertainty,
or an outstanding requested change is not whole-build approval.
Use finalize_character only when the player has approved the complete current
build and you can provide its full character sheet. Copy the actual latest user
message index supplied by the wizard into confirmation.player_message_index.
Never use the index of a system correction or an earlier approval for a changed
build. Missing consequential choices require clarification. Starting-equipment
choices (each package and each package pick) are asked before the summary, or
offered as one recommended pick when the player delegates. Resolve only other
minor mechanical details with consistent SRD defaults after whole-build approval.
Use pause_setup only when the latest real user input asks to stop or leave
character setup for now; cancelling, undoing or changing a choice is not a pause.
It has character, origin and starting_equipment null, whole_build_approved
false, and the latest user message
index; its narration briefly says their choices are kept for next time. When
the player returns after a pause, continue the interview.

A proposal is NOT a saved character. Narration must stay true to the supplied
committed facts: do not claim successful creation, saving, arrival, a scene or
an NPC interaction before the engine verifies those facts. At finalization,
offer only honest progress narration. The main DM narrates the actual opening
after durable creation and location verification. If reviewing resumed history,
retain actual choices and rolls; prior assistant success prose is not disk proof.

Use the frozen CHARACTER SCHEMA for character, not for the outer response.
Include ammunition (an empty array when none), all required fields, and valid
enum values. New characters start at level 1 with experience_points 0 and player
role/type. Preserve existing dictionary-form skills when supplied; do not turn
existing data into empty defaults. For new builds include chosen proficiencies,
consistent languages, attacks, modifiers and SRD features, and write
"currency": {{"gold": 0, "silver": 0, "copper": 0}}, "equipment": [] and
"ammunition": []: the game replaces all three from the chosen packages. Spell
attacks use type "spell"; the engine writes the weapon attack rows. No schema
metadata in a character object. Unused temporaryEffects, injuries and
equipment_effects are empty arrays, not invented timed effects.
Starting gear is represented once: the game merges the two packages, and an item
both list is one row with the quantities summed.
The attack list describes available options, not weapons wielded simultaneously.
Keep carried/stowed weapons and their attack statistics without falsely marking
them wielded or changing armor class; describe prerequisites when relevant.
Keep approved backstory in the existing descriptive fields or interview context;
do not distort a mechanical background name to satisfy an invented schema slot.
Rejected proposals are correction context, not approved choices. Correct the
specific errors while retaining the latest player input and accepted choices.
Correction context separates rejected_proposal (your authored wire object) from
canonical_candidate (the game's normalized private copy). Correct the authored
object; do not copy engine-generated fields back from canonical_candidate.
normalization_provenance describes actual game derivations, not player choices
or extra author requirements. Do not attempt to remove fields the engine writes.

STARTUP RESPONSE SCHEMA:
{json.dumps(startup_response_schema(scoped=scoped), indent=2)}

CHARACTER SCHEMA:
{json.dumps(schema, indent=2)}

LEVELING INFORMATION:
{leveling_info}
"""
    return _engine_prompt(prompt, schema) if scoped else prompt


def build_startup_review_prompt():
    """Independent semantic review; no authority to write or invent choices."""
    return f"""You independently validate a startup proposal against the complete
relevant interview, latest actual player input/index, selected adventure,
character rules/schema, and code-supplied committed-state facts.
Determine whether the latest player input approves the complete proposed build
in context. Approval of one attribute, a negation, or an outstanding requested
change is not whole-build approval. Do not require an exact approval phrase.
Check identity, agreed ability method/results/allocation, class/background,
proficiencies, languages, the starting packages and package picks, features, and
rules consistency. Reject an origin or package pick that is in neither the
player's words nor the approved summary. A class or background that the
conversation or summary states plainly but the proposal mistypes is
author-correctable; set needs_player_clarification false.
When starting_packages.status is engine_unavailable or data_unavailable, missing
gold, starting gear, weapon attack rows and armor from that gear are the game's
disclosed outcome under the owner's ruling, not a lost choice; still check the
picks. Preserve
existing player data and distinguish defaults from choices requiring consent.
Check proposed narration against committed facts. An unsaved proposal cannot
truthfully claim saved, created, placed, or adventure events. Review meaning,
not a success-word blacklist. Never treat old assistant prose as disk proof.
For an incomplete build, a truthful continue_interview question can be accepted.
A continue_interview recommendation that asks for approval is not a character
sheet. Check its stated rules facts against the startup_rules_reference in the
interview, that it keeps approved choices, and that it asks honestly. Do not
require full equipment lists, mastery property text or other sheet details in
a recommendation; they are checked when the author finalizes. When a stated fact
is absent from the reference, tell the author to drop or hedge it, not to add
more detail.
A feature named in a class's class_level_1 features is a supplied level-1 fact,
as are its class_table_at_level_1 values: never ask the author to remove it
from a sheet; hedge only mechanics the reference does not give.
Response contract: continue_interview always has whole_build_approved false and
character null; finalize_character carries the full sheet. After a whole-build
approval the correct next step is finalize_character. Never ask for a separate
sheet approval, and never tell the author to set whole_build_approved on a
continue_interview. A continue_interview that asks once for a still-open player
choice after approval is valid. Check the background's Origin feat and skills,
by name, against the startup_rules_reference.
Accept pause_setup only when the latest player input asks to stop setup for
now; reject it when the player cancels, undoes or changes a choice, and reject
a continue_interview that ignores a clear request to stop.
A proposal that reaches you has already passed the game's schema validation.
Do not request schema fields, placeholders or null values. The proposal shown
(the canonical candidate) is authoritative over any memory of earlier drafts;
normalization_provenance lists what the game dropped or derived.
Reject a proposal that loses approved choices, claims uncommitted facts or
finalizes without whole-build approval. Give precise corrective feedback.
Set needs_player_clarification true only on a rejection that the author cannot
correct without new player input. A continue_interview that asks the player a
question does not need clarification: accept it with needs_player_clarification
false.
Ground every rejection in a concrete contradiction with the supplied rules,
schema, approved choices, or committed facts. Equivalent representations are
valid; stylistic preferences and speculative missing fields are not blockers.
Narration layout is presentation: line breaks, "- " list lines, labelled
summary sections, and a turn that asks only three or four of the open
decisions (leaving the rest for later turns) are never reasons to reject.
Before prescribing a rules correction, verify the proposed replacement against
the actual reference in the interview and identify its supporting passage or
calculation in feedback. Do not call a rule "supplied" when it is absent there,
or replace a consistent value solely because of uncertain remembered rules.
Earlier rejection feedback is an allegation to verify, not a rules authority;
recheck it independently rather than treating repetition as proof.
The payload separates authored_proposal (the untouched model response) from
proposal (the normalized canonical candidate to be saved if accepted).
Apply author-only restrictions, such as not inventing equipment_effects, to
authored_proposal. Attribute a field to the author only when authored_proposal
itself contains it. When normalization_provenance reports
an applied engine_projection, its AC-target effects and matching status totals
are engine output, even when armorClass and hit points did not change. Do not
attribute those additions to the author or demand their removal on retry.
Fields named in engine_projection.engine_owned_fields are engine-written: never
an author change, even when absent from authored_proposal.
Attack rows listed in normalization_provenance.engine_rows.written are engine
output, like the AC entries: never an author change or a reason to reject.
engine_rows.replaced names the author rows they took the place of.
engine_rows.not_usable_now names carried-mode rows whose hands are taken now;
the row stays, and drawing the weapon is a story or equipment action.
damageDice "flat" means no damage dice: the row deals its damageBonus as a
flat total, as an SRD Unarmed Strike does (1 + Strength modifier).
engine_rows.untyped_equipment lists weapon and armor rows the catalog did not
type; equipment notes in mechanics_notes are code changes, not author claims.
An unavailable or incomplete projection does not certify fields as engine output.
Still check actual typed equipment/features, approved choices, schema, arithmetic,
and narration against the canonical candidate. Provenance is not whole-build
approval or proof that all mechanics are correct. Level-1 hit points are code
output, set exactly as normalization_provenance.hit_points states.
An owned but stowed weapon can have an available attack entry. That does not
claim it is currently wielded, nor allow simultaneous incompatible equipment.
A pack row (Explorer's Pack, Dungeoneer's Pack, ...) represents the contents its
description lists; do not require them as separate rows.
Distinguish a mechanical background from narrative history: retain the approved
history in existing description/context, without requiring new schema fields or
renaming the mechanical background. Accept a valid proposal once substantive
requirements are met; do not invent a new representation requirement on retry.
An accepted proposal has needs_player_clarification false.
Return only this review object, no narration, state changes or new character:
{json.dumps(STARTUP_REVIEW_SCHEMA, indent=2)}
"""


