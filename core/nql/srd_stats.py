"""SRD 5.2.1 character-stat rules for the engine, copied verbatim from the NQL repository
(examples/srd-stats/world.nql, conditions block at 10a267e, guide docs/CHARACTER_STATS.md). Three blocks: the
proficiency Condition types a world declares once, the SRD condition states (state:<name>, C1), and the
derived-stat rules that go inside its equipment block.
Do not edit by hand; regenerate from the NQL example when the engine changes."""
NQL_COMMIT = "084cb0c"
STATES_COMMIT = "10a267e"
ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
# skill id -> ability, SRD 5.2.1
SKILLS = {
    "acrobatics": "dexterity", "animal-handling": "wisdom", "arcana": "intelligence", "athletics": "strength",
    "deception": "charisma", "history": "intelligence", "insight": "wisdom", "intimidation": "charisma",
    "investigation": "intelligence", "medicine": "wisdom", "nature": "intelligence", "perception": "wisdom",
    "performance": "charisma", "persuasion": "charisma", "religion": "intelligence", "sleight-of-hand": "dexterity",
    "stealth": "dexterity", "survival": "wisdom",
}
FEATURE_TYPES = {"jack of all trades": "feature:jack-of-all-trades"}  # classFeatures[].name, casefolded
FEAT_TYPES = {"alert": "feat:alert"}  # feats[].name, casefolded
# The 44 proficiency Condition types (srd-stats:conditions block).
CONDITION_TYPES = (
    'prof:save:strength',
    'prof:save:dexterity',
    'prof:save:constitution',
    'prof:save:intelligence',
    'prof:save:wisdom',
    'prof:save:charisma',
    'prof:skill:acrobatics',
    'prof:skill:animal-handling',
    'prof:skill:arcana',
    'prof:skill:athletics',
    'prof:skill:deception',
    'prof:skill:history',
    'prof:skill:insight',
    'prof:skill:intimidation',
    'prof:skill:investigation',
    'prof:skill:medicine',
    'prof:skill:nature',
    'prof:skill:perception',
    'prof:skill:performance',
    'prof:skill:persuasion',
    'prof:skill:religion',
    'prof:skill:sleight-of-hand',
    'prof:skill:stealth',
    'prof:skill:survival',
    'expertise:skill:acrobatics',
    'expertise:skill:animal-handling',
    'expertise:skill:arcana',
    'expertise:skill:athletics',
    'expertise:skill:deception',
    'expertise:skill:history',
    'expertise:skill:insight',
    'expertise:skill:intimidation',
    'expertise:skill:investigation',
    'expertise:skill:medicine',
    'expertise:skill:nature',
    'expertise:skill:perception',
    'expertise:skill:performance',
    'expertise:skill:persuasion',
    'expertise:skill:religion',
    'expertise:skill:sleight-of-hand',
    'expertise:skill:stealth',
    'expertise:skill:survival',
    'feature:jack-of-all-trades',
    'feat:alert',
)
# The 45 derive rules (srd-stats:derive block), one line each, for the equipment block.
# The 15 SRD condition states (srd-stats:srd-conditions block at 10a267e): the engine holds
# state:unconscious while hp is at its minimum, bounds speed for the immobilizing ones and
# prices exhaustion per instance. Names are the sheet's condition_affected vocabulary.
STATE_NAMES = (
    'blinded',
    'charmed',
    'deafened',
    'exhaustion',
    'frightened',
    'grappled',
    'incapacitated',
    'invisible',
    'paralyzed',
    'petrified',
    'poisoned',
    'prone',
    'restrained',
    'stunned',
    'unconscious',
)
STATE_TYPES = """\
condition type "state:blinded" { instances coexist; }
condition type "state:charmed" { instances coexist; }
condition type "state:deafened" { instances coexist; }
condition type "state:exhaustion" { instances coexist; modifier "d20" stat "bonus:d20" add -2; modifier "speed" stat "speed" add -5; }
condition type "state:frightened" { instances coexist; }
condition type "state:grappled" { instances coexist; modifier "speed" stat "speed" at most 0; }
condition type "state:incapacitated" { instances coexist; }
condition type "state:invisible" { instances coexist; }
condition type "state:paralyzed" { instances coexist; modifier "speed" stat "speed" at most 0; }
condition type "state:petrified" { instances coexist; modifier "speed" stat "speed" at most 0; }
condition type "state:poisoned" { instances coexist; }
condition type "state:prone" { instances coexist; }
condition type "state:restrained" { instances coexist; modifier "speed" stat "speed" at most 0; }
condition type "state:stunned" { instances coexist; }
condition type "state:unconscious" { instances coexist; held_at_minimum "hp"; modifier "speed" stat "speed" at most 0; }
"""

DERIVE_RULES = """\
 derive stat "proficiency" { term stat "level" offset 7 divide 4; }
 derive stat "mod:strength" { term stat "strength" offset -10 divide 2; }
 derive stat "mod:dexterity" { term stat "dexterity" offset -10 divide 2; }
 derive stat "mod:constitution" { term stat "constitution" offset -10 divide 2; }
 derive stat "mod:intelligence" { term stat "intelligence" offset -10 divide 2; }
 derive stat "mod:wisdom" { term stat "wisdom" offset -10 divide 2; }
 derive stat "mod:charisma" { term stat "charisma" offset -10 divide 2; }
 derive stat "check:strength" {
  term stat "strength" offset -10 divide 2;
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "check:dexterity" {
  term stat "dexterity" offset -10 divide 2;
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "check:constitution" {
  term stat "constitution" offset -10 divide 2;
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "check:intelligence" {
  term stat "intelligence" offset -10 divide 2;
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "check:wisdom" {
  term stat "wisdom" offset -10 divide 2;
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "check:charisma" {
  term stat "charisma" offset -10 divide 2;
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "save:strength" {
  term stat "strength" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:save:strength";
  term stat "bonus:saves" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "save:dexterity" {
  term stat "dexterity" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:save:dexterity";
  term stat "bonus:saves" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "save:constitution" {
  term stat "constitution" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:save:constitution";
  term stat "bonus:saves" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "save:intelligence" {
  term stat "intelligence" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:save:intelligence";
  term stat "bonus:saves" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "save:wisdom" {
  term stat "wisdom" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:save:wisdom";
  term stat "bonus:saves" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "save:charisma" {
  term stat "charisma" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:save:charisma";
  term stat "bonus:saves" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "skill:acrobatics" {
  term stat "dexterity" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:skill:acrobatics";
  term stat "level" offset 7 divide 4 requires "expertise:skill:acrobatics";
  term stat "level" offset 7 divide 8 requires "feature:jack-of-all-trades" unless "prof:skill:acrobatics";
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "skill:animal-handling" {
  term stat "wisdom" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:skill:animal-handling";
  term stat "level" offset 7 divide 4 requires "expertise:skill:animal-handling";
  term stat "level" offset 7 divide 8 requires "feature:jack-of-all-trades" unless "prof:skill:animal-handling";
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "skill:arcana" {
  term stat "intelligence" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:skill:arcana";
  term stat "level" offset 7 divide 4 requires "expertise:skill:arcana";
  term stat "level" offset 7 divide 8 requires "feature:jack-of-all-trades" unless "prof:skill:arcana";
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "skill:athletics" {
  term stat "strength" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:skill:athletics";
  term stat "level" offset 7 divide 4 requires "expertise:skill:athletics";
  term stat "level" offset 7 divide 8 requires "feature:jack-of-all-trades" unless "prof:skill:athletics";
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "skill:deception" {
  term stat "charisma" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:skill:deception";
  term stat "level" offset 7 divide 4 requires "expertise:skill:deception";
  term stat "level" offset 7 divide 8 requires "feature:jack-of-all-trades" unless "prof:skill:deception";
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "skill:history" {
  term stat "intelligence" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:skill:history";
  term stat "level" offset 7 divide 4 requires "expertise:skill:history";
  term stat "level" offset 7 divide 8 requires "feature:jack-of-all-trades" unless "prof:skill:history";
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "skill:insight" {
  term stat "wisdom" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:skill:insight";
  term stat "level" offset 7 divide 4 requires "expertise:skill:insight";
  term stat "level" offset 7 divide 8 requires "feature:jack-of-all-trades" unless "prof:skill:insight";
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "skill:intimidation" {
  term stat "charisma" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:skill:intimidation";
  term stat "level" offset 7 divide 4 requires "expertise:skill:intimidation";
  term stat "level" offset 7 divide 8 requires "feature:jack-of-all-trades" unless "prof:skill:intimidation";
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "skill:investigation" {
  term stat "intelligence" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:skill:investigation";
  term stat "level" offset 7 divide 4 requires "expertise:skill:investigation";
  term stat "level" offset 7 divide 8 requires "feature:jack-of-all-trades" unless "prof:skill:investigation";
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "skill:medicine" {
  term stat "wisdom" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:skill:medicine";
  term stat "level" offset 7 divide 4 requires "expertise:skill:medicine";
  term stat "level" offset 7 divide 8 requires "feature:jack-of-all-trades" unless "prof:skill:medicine";
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "skill:nature" {
  term stat "intelligence" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:skill:nature";
  term stat "level" offset 7 divide 4 requires "expertise:skill:nature";
  term stat "level" offset 7 divide 8 requires "feature:jack-of-all-trades" unless "prof:skill:nature";
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "skill:perception" {
  term stat "wisdom" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:skill:perception";
  term stat "level" offset 7 divide 4 requires "expertise:skill:perception";
  term stat "level" offset 7 divide 8 requires "feature:jack-of-all-trades" unless "prof:skill:perception";
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "skill:performance" {
  term stat "charisma" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:skill:performance";
  term stat "level" offset 7 divide 4 requires "expertise:skill:performance";
  term stat "level" offset 7 divide 8 requires "feature:jack-of-all-trades" unless "prof:skill:performance";
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "skill:persuasion" {
  term stat "charisma" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:skill:persuasion";
  term stat "level" offset 7 divide 4 requires "expertise:skill:persuasion";
  term stat "level" offset 7 divide 8 requires "feature:jack-of-all-trades" unless "prof:skill:persuasion";
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "skill:religion" {
  term stat "intelligence" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:skill:religion";
  term stat "level" offset 7 divide 4 requires "expertise:skill:religion";
  term stat "level" offset 7 divide 8 requires "feature:jack-of-all-trades" unless "prof:skill:religion";
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "skill:sleight-of-hand" {
  term stat "dexterity" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:skill:sleight-of-hand";
  term stat "level" offset 7 divide 4 requires "expertise:skill:sleight-of-hand";
  term stat "level" offset 7 divide 8 requires "feature:jack-of-all-trades" unless "prof:skill:sleight-of-hand";
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "skill:stealth" {
  term stat "dexterity" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:skill:stealth";
  term stat "level" offset 7 divide 4 requires "expertise:skill:stealth";
  term stat "level" offset 7 divide 8 requires "feature:jack-of-all-trades" unless "prof:skill:stealth";
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "skill:survival" {
  term stat "wisdom" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:skill:survival";
  term stat "level" offset 7 divide 4 requires "expertise:skill:survival";
  term stat "level" offset 7 divide 8 requires "feature:jack-of-all-trades" unless "prof:skill:survival";
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "initiative" {
  term stat "dexterity" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "feat:alert";
  term stat "bonus:checks" offset 0 divide 1;
  term stat "bonus:d20" offset 0 divide 1;
 }
 derive stat "passive:perception" {
  term stat "wisdom" offset -10 divide 2;
  term stat "level" offset 7 divide 4 requires "prof:skill:perception";
  term stat "level" offset 7 divide 4 requires "expertise:skill:perception";
  term stat "level" offset 7 divide 8 requires "feature:jack-of-all-trades" unless "prof:skill:perception";
  term stat "bonus:checks" offset 0 divide 1;
 }
 derive stat "spell-dc:intelligence" {
  term stat "intelligence" offset -10 divide 2;
  term stat "level" offset 7 divide 4;
 }
 derive stat "spell-dc:wisdom" {
  term stat "wisdom" offset -10 divide 2;
  term stat "level" offset 7 divide 4;
 }
 derive stat "spell-dc:charisma" {
  term stat "charisma" offset -10 divide 2;
  term stat "level" offset 7 divide 4;
 }
 derive stat "spell-attack:intelligence" {
  term stat "intelligence" offset -10 divide 2;
  term stat "level" offset 7 divide 4;
 }
 derive stat "spell-attack:wisdom" {
  term stat "wisdom" offset -10 divide 2;
  term stat "level" offset 7 divide 4;
 }
 derive stat "spell-attack:charisma" {
  term stat "charisma" offset -10 divide 2;
  term stat "level" offset 7 divide 4;
 }
"""
