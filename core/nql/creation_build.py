"""The engine-built level-1 character sheet (D-CREATE-COST-5).

The creation author declares typed intent (class, species, background, the ability-score method and
assignment, every issued choice id with its picks) and the creative fields; this module turns them into
the sheet from the data files. No mechanical field is taken from the author. A grant the data does not
type yet is left off the sheet and listed in the build's ``untyped`` provenance, so a creation measures
data completeness instead of trusting prose.

The numbers the existing finalize derives (hit points, armor class, every bonus total, gear, pools and
slots) are left to it: the sheet built here goes through ``_prepare_startup_proposal`` like an authored
one, from the startup repair onward.
"""
import random
from typing import Any, Dict, List, Optional, Tuple

from core.leveling import choices as leveling_choices
from core.nql import creation_scope
from core.nql.creation_scope import _Data, _ability_options, _class_points, _feat_spell_points, _slug

ABILITIES = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")
CREATIVE_FIELDS = ("name", "alignment", "personality_traits", "ideals", "bonds", "flaws")
OPTIONAL_CREATIVE_FIELDS = ("backstory", "appearance", "feature_descriptions")
ARMOR_LABELS = {"light": "Light armor", "medium": "Medium armor", "heavy": "Heavy armor", "shield": "Shields"}
SPELL_LEVELS = ["cantrips"] + ["level%d" % n for n in range(1, 10)]


class BuildRefusal(ValueError):
    """The intent or the creative fields cannot build a sheet; ``problems`` are typed."""

    def __init__(self, problems: List[Dict[str, Any]]):
        super().__init__("; ".join("%s: %s" % (p.get("field"), p.get("problem")) for p in problems))
        self.problems = problems


class _Build:
    def __init__(self, d: _Data, intent: Dict[str, Any]):
        self.d = d
        self.intent = intent
        self.picks = intent.get("choices") or {}
        self.issued = creation_scope.issued_points(intent)
        self.trace: List[Dict[str, Any]] = []
        self.untyped: List[Dict[str, Any]] = []

    def source(self, field: str, source: str, value: Any) -> Any:
        self.trace.append({"field": field, "source": source, "value": value})
        return value

    def gap(self, gid: str, grant: str, where: str) -> None:
        """A grant with no typed source: {id, grant, where}; id is species.<key>.<field or heading slug>,
        background.<key>.<field>, a choice id, or the data table's path."""
        self.untyped.append({"id": gid, "grant": grant, "where": where})

    def picked(self, cid: str) -> List[str]:
        return list(self.picks.get(cid) or [])


def _spell_names(b: _Build, keys: List[str]) -> List[str]:
    return [b.d.spell_name.get(k, k) for k in keys]


def roll_ability_scores(rng: Any = None) -> Dict[str, Any]:
    """The engine's random generation (p. 21): four d6, the highest three summed, six times.
    {"rolled": [6 totals], "dice": [[4 d6] x6]}; rng defaults to the system source."""
    rng = rng or random.SystemRandom()
    dice = [[rng.randint(1, 6) for _ in range(4)] for _ in range(6)]
    return {"rolled": [sum(sorted(d)[1:]) for d in dice], "dice": dice}


def _ability_scores(b: _Build, background: Dict[str, Any], rolled: Optional[List[int]]) -> Dict[str, int]:
    """Base scores by the declared method, then the background's issued increase (max 20; p.21, p.83)."""
    spec = b.intent.get("ability_scores") or {}
    if "rolled" in spec:  # numbers never come from intent (S1)
        raise BuildRefusal([{"field": "intent.ability_scores.rolled", "problem": "the engine's roll item is the only source"}])
    methods = b.d.origins.get("ability_score_methods") or {}
    method = spec.get("method")
    assignment = spec.get("assignment") if isinstance(spec.get("assignment"), dict) else {}
    if set(assignment) != set(ABILITIES):  # the schema's six lowercase keys, matched exactly (N2)
        raise BuildRefusal([{"field": "intent.ability_scores.assignment", "problem": "keys must be %s" % ", ".join(ABILITIES)}])
    base = {a: assignment.get(a) for a in ABILITIES}
    if any(type(v) is not int for v in base.values()):
        raise BuildRefusal([{"field": "intent.ability_scores.assignment", "problem": "six whole-number scores"}])
    if method == "standard_array":
        if sorted(base.values()) != sorted(methods.get("standard_array") or []):
            raise BuildRefusal([{"field": "intent.ability_scores", "problem": "not a permutation of the standard array"}])
    elif method == "point_buy":
        costs = (methods.get("point_cost") or {}).get("costs") or {}
        if any(str(v) not in costs for v in base.values()):
            raise BuildRefusal([{"field": "intent.ability_scores", "problem": "a point-buy score outside 8-15"}])
        if sum(costs[str(v)] for v in base.values()) > (methods.get("point_cost") or {}).get("budget", 27):
            raise BuildRefusal([{"field": "intent.ability_scores", "problem": "point-buy cost over the budget"}])
    elif method == "random":
        # The engine's persisted roll item is the only source (N1); intent never carries numbers.
        if not isinstance(rolled, list) or sorted(base.values()) != sorted(rolled):
            raise BuildRefusal([{"field": "intent.ability_scores", "problem": "not the engine-rolled set"}])
    else:
        raise BuildRefusal([{"field": "intent.ability_scores.method", "problem": "not a listed method"}])
    scores = dict(b.source("abilities.base", "intent.ability_scores (%s)" % method, base))
    bid = "background.%s.ability-scores" % background["key"]
    choice = (b.picked(bid) or [None])[0]
    abilities = list(background.get("ability_keys") or [])
    increases: Dict[str, int] = {}
    if choice == "+1 each":
        increases = {a.lower(): 1 for a in abilities}
    else:
        # The option keys are the engine's own enum (_ability_options); match the key, never parse prose.
        for first in abilities:
            for second in abilities:
                if first != second and choice == "+2 %s, +1 %s" % (first, second):
                    increases = {first.lower(): 2, second.lower(): 1}
    if choice not in _ability_options(background):
        raise BuildRefusal([{"field": bid, "problem": "no issued ability increase picked"}])
    for ability, amount in increases.items():
        scores[ability] = min(20, scores[ability] + amount)
    b.source("abilities", bid, increases)
    return scores


def _class_picks(b: _Build, cls: str) -> Dict[str, Any]:
    """The class's issued picks sorted into sheet fields, by the points' typed fields."""
    out: Dict[str, Any] = {"skills": [], "expertise": [], "tools": [], "languages": [], "cantrips": [],
                           "prepared": [], "spellbook": [], "features": []}
    for cid, point in _class_points(cls, b.d):
        picks = b.picked(cid)
        if not picks or isinstance(point.get("option_items"), dict):
            continue  # nothing picked, or a starting package (starting_equipment carries the package)
        head = str(point.get("option_source") or "").split(":", 1)[0]
        kind = point.get("kind")
        if kind == "skill":
            out["skills"] += [b.source("skills", cid, p) for p in picks]
        elif kind == "expertise":
            out["expertise"] += [b.source("expertise", cid, p) for p in picks]
        elif kind == "cantrip":
            out["cantrips"] += [b.source("spellcasting.cantrips", cid, p) for p in picks]
        elif kind == "prepared_spells":
            out["prepared"] += [b.source("spellcasting.prepared", cid, p) for p in picks]
        elif point.get("key") == "wizard.spellbook":
            out["spellbook"] += [b.source("spellcasting.spellbook", cid, p) for p in picks]
        elif head == "tools":
            out["tools"] += [b.source("proficiencies.tools", cid, p) for p in picks]
        elif head == "languages":
            out["languages"] += [b.source("languages", cid, p) for p in picks]
        elif kind == "fighting_style":
            out["features"] += [(point.get("feature") or point["name"], "Fighting Style: %s" % p, cid) for p in picks]
        else:
            # An order (its exact name is what apply_order_grants matches), Weapon Mastery, an invocation:
            # "<choice>: <picks>", the form level-up writes.
            label = point["name"] if isinstance(point.get("option_grants"), dict) else (point.get("feature") or point["name"])
            out["features"].append((point.get("feature") or point["name"], "%s: %s" % (label, ", ".join(picks)), cid))
        for option, subs in (point.get("then") or {}).items():
            if option not in picks:
                continue
            for sub in subs:
                sid = "%s.%s.%s" % (cid, _slug(option), _slug(sub["name"]))
                if sub.get("kind") == "cantrip":
                    out["cantrips"] += [b.source("spellcasting.cantrips", sid, p) for p in b.picked(sid)]
    return out


def _feat_picks(b: _Build, background: Dict[str, Any]) -> Dict[str, Any]:
    """The background Origin feat's spell picks and spellcasting ability (Magic Initiate)."""
    out: Dict[str, Any] = {"cantrips": [], "spells": [], "ability": None}
    for sid, sub in _feat_spell_points(background, b.d):
        picks = b.picked(sid)
        if sub.get("kind") == "cantrip":
            out["cantrips"] += [b.source("spellcasting.cantrips", sid, p) for p in picks]
        elif str(sub.get("option_source") or "").startswith("spells:"):
            out["spells"] += [b.source("spellcasting.level1", sid, p) for p in picks]
        elif picks:
            out["ability"] = b.source("feats.spellcasting_ability", sid, picks[0])
    return out


def _species_grants(b: _Build, species: Dict[str, Any]) -> Dict[str, Any]:
    """The species' typed grants (``grants``: size, speed, darkvision, traits); each one missing is a gap."""
    grants = species.get("grants") if isinstance(species.get("grants"), dict) else {}
    out: Dict[str, Any] = {}
    for key in ("size", "speed", "darkvision", "traits"):  # a grant of 0 (no darkvision) is typed
        if key in grants:
            out[key] = b.source(key, "origins.species[%s].grants.%s" % (species["key"], key), grants[key])
        else:
            b.gap("species.%s.%s" % (species["key"], key), "species %s" % key, "origins.species[%s]" % species["key"])
    if grants.get("size_options"):
        cid = "species.%s.size" % species["key"]
        picked = b.picked(cid)
        if picked:
            out["size"] = b.source("size", cid, picked[0])
    return out


def _resistances(b: _Build, intent: Dict[str, Any]) -> List[str]:
    """Species damage resistances (#1280): the typed table's grants for the species and its picked options."""
    if not isinstance(b.d.choices.get("species_damage_resistances"), list):
        b.gap("choices.species_damage_resistances", "damage resistances", "choices.species_damage_resistances")
        return []
    out: List[str] = []
    for grant in leveling_choices.species_damage_resistances(intent):
        for value in grant["damage_resistances"]:
            if value.casefold() not in [v.casefold() for v in out]:
                out.append(b.source("damageResistances", grant.get("choice_id") or "choices.species_damage_resistances",
                                    value))
    return out


def _species_picks(b: _Build, species: Dict[str, Any]) -> Dict[str, Any]:
    """What the species' picked choices grant: lineage cantrips, speed and darkvision; Keen Senses and
    Skillful skills; the Versatile Origin feat and its sub-picks (Skilled: skills or tools)."""
    out: Dict[str, Any] = {"cantrips": [], "skills": [], "tools": [], "feats": [], "options": []}
    grants = species.get("grants") if isinstance(species.get("grants"), dict) else {}
    out["cantrips"] += [b.source("spellcasting.cantrips", "origins.species[%s].grants.cantrips" % species["key"], k)
                        for k in grants.get("cantrips") or []]
    skill_names = set(leveling_choices.resolve_options("skills:all", {}, "", 1) or [])
    for choice in grants.get("choices") or []:
        cid = "species.%s.%s" % (species["key"], _slug(choice["name"]))
        picks = b.picked(cid)
        out["options"] += picks
        for option in [o for o in choice.get("options") or [] if o.get("name") in picks]:
            out["cantrips"] += [b.source("spellcasting.cantrips", cid, k) for k in option.get("cantrips") or []]
            for key in ("speed", "darkvision"):
                if key in option:
                    out[key] = b.source(key, cid, option[key])
        if choice.get("spellcasting_ability") and b.picked("%s.spellcasting-ability" % cid):
            out["ability"] = b.source("spellcasting.ability", "%s.spellcasting-ability" % cid,
                                      b.picked("%s.spellcasting-ability" % cid)[0])
        if choice.get("kind") == "skill":
            out["skills"] += [b.source("skills", cid, p) for p in picks]
        elif choice.get("kind") == "feat":
            for name in picks:
                feat = next((f for f in b.d.choices["feats"] if f.get("name") == name), None) or {}
                for sub in feat.get("choices") or []:
                    if sub.get("then"):
                        b.gap("%s.%s" % (cid, _slug(name)), "%s spell picks" % name, cid)
                        continue
                    sid = "%s.%s.%s" % (cid, _slug(name), _slug(sub["name"]))
                    for p in b.picked(sid):
                        key = "skills" if p in skill_names else "tools"
                        out[key].append(b.source(key if key == "skills" else "proficiencies.tools", sid, p))
                text = next((f.get("text") for f in b.d.origins.get("origin_feats") or [] if f.get("name") == name), "")
                out["feats"].append({"name": b.source("feats", cid, name), "description": text or "",
                                     "source": "%s species: %s" % (species["name"], choice["name"])})
    return out


def _weapon_labels(traits: Dict[str, Any]) -> List[str]:
    rules = traits.get("weapon_proficiencies") or []
    if any(r.get("property_any") for r in rules):
        # A property-limited rule is read by the engine from class_traits; the sheet shows the printed SRD label.
        return [(traits.get("printed") or {}).get("Weapon Proficiencies")]
    return ["%s weapons" % r["category"] for r in rules if r.get("category")]


def _unique(values: List[str]) -> List[str]:
    out: List[str] = []
    for value in values:
        if value and value not in out:
            out.append(value)
    return out


def build_level_one_sheet(intent: Dict[str, Any], creative: Optional[Dict[str, Any]], data: Optional[_Data] = None,
                          *, rolled: Optional[List[int]] = None,
                          preview: bool = False) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """The level-1 sheet for a complete intent, and its provenance {engine_build, untyped}.

    Raises BuildRefusal when the intent has open or refused picks, an invalid ability-score assignment, or
    a creative field is missing or not creative. Hit points, AC, totals, gear, pools and slots are left to
    the startup finalize (``startup_mechanics``)."""
    d = data if data is not None else _Data()
    if not d.ok:
        raise BuildRefusal([{"field": "data", "problem": "the data files cannot be read"}])
    intent = intent or {}
    if preview:
        # The interview preview (startup_sheet_preview): the mechanics only, before any creative field exists.
        creative = {field: "" for field in CREATIVE_FIELDS}
        creative["alignment"] = "neutral"
    creative = creative or {}
    creative = {k: v for k, v in creative.items() if v is not None}  # an optional creative field may be null
    problems: List[Dict[str, Any]] = []
    extra = sorted(set(creative) - set(CREATIVE_FIELDS) - set(OPTIONAL_CREATIVE_FIELDS))
    if extra:
        problems.append({"field": "creative", "problem": "not creative fields: %s" % ", ".join(extra)})
    for field in CREATIVE_FIELDS if not preview else ():
        if not isinstance(creative.get(field), str) or not creative[field].strip():
            problems.append({"field": "creative.%s" % field, "problem": "missing"})
    problems += [dict(p, field=p["choice_id"]) for p in creation_scope.choice_problems(intent)]
    problems += [{"field": cid, "problem": "open"} for cid in creation_scope.open_choice_ids(intent)]
    cls, species_key, background_key = intent.get("class_key"), intent.get("species_key"), intent.get("background_key")
    if cls not in d.classes() or species_key not in d.species() or background_key not in d.backgrounds():
        problems.append({"field": "intent", "problem": "class, species and background must be named"})
    if problems:
        raise BuildRefusal(problems)

    b = _Build(d, intent)
    species, background = d.species()[species_key], d.backgrounds()[background_key]
    traits = d.choices["class_traits"][cls]
    prog = (d.progression.get("classes") or {}).get(cls) or {}
    class_name = prog.get("name") or cls.capitalize()
    picks = _class_picks(b, cls)
    feat = _feat_picks(b, background)

    # Background skills and tools: typed lists (``skill_keys``, ``tool_keys``); the printed strings are prose.
    background_skills = background.get("skill_keys")
    if not isinstance(background_skills, list):
        b.gap("background.%s.skill-keys" % background_key, "background skills", "origins.backgrounds[%s].skill_keys" % background_key)
        background_skills = []
    background_tools = background.get("tool_keys")
    if not isinstance(background_tools, list):
        b.gap("background.%s.tool-keys" % background_key, "background tools", "origins.backgrounds[%s].tool_keys" % background_key)
        background_tools = []
    tool_id = creation_scope.background_tool_id(background)
    tool_pick = [b.source("proficiencies.tools", tool_id, p) for p in b.picked(tool_id)]

    languages = list(d.choices["languages"].get("known") or [])
    languages += ((traits.get("languages") or {}).get("granted") or [])
    languages += b.picked("languages.standard") + picks["languages"]

    species_grants = _species_grants(b, species)
    species_picks = _species_picks(b, species)
    for key in ("speed", "darkvision"):  # a lineage that changes them (Wood Elf 35, Drow 120)
        if key in species_picks:
            species_grants[key] = species_picks[key]
    resistances = _resistances(b, intent)

    features = []
    by_feature = {}
    for feature, name, cid in picks["features"]:
        by_feature.setdefault(feature, []).append(name)
    descriptions = creative.get("feature_descriptions") or {}
    for feature in (prog.get("features_by_level") or {}).get("1") or []:
        for name in by_feature.pop(feature, [feature]):
            features.append({"name": b.source("classFeatures", "progression.%s.features_by_level.1" % cls, name),
                             "description": descriptions.get(name, ""), "source": "%s level 1" % class_name})
    for leftover in by_feature.values():  # a pick whose feature the table does not name
        for name in leftover:
            features.append({"name": name, "description": descriptions.get(name, ""),
                             "source": "%s level 1" % class_name})

    origin_feat = next((f for f in d.origins.get("origin_feats") or []
                        if f.get("key") == (background.get("feat_ref") or {}).get("feat_key")), None)
    feats, background_feature = list(species_picks["feats"]), None
    if origin_feat is not None:
        name = background.get("feat") or origin_feat["name"]
        source = "%s background (SRD 5.2.1)" % background["name"]
        text = origin_feat.get("text") or descriptions.get(name) or ""  # the SRD data text wins (N3)
        feats.append({"name": b.source("feats", "origins.backgrounds[%s].feat_ref" % background_key, name),
                      "description": text, "source": source})
        if feat["spells"]:
            feats[-1]["grantedSpells"] = [{"spell": key, "resource": name} for key in feat["spells"]]
        background_feature = {"name": "Origin feat: %s" % name, "description": text, "source": source}
    else:
        b.gap("background.%s.feat-ref" % background_key, "origin feat", "origins.backgrounds[%s].feat_ref" % background_key)

    always = [a["spell"] for a in d.choices.get("always_prepared") or []
              if (a.get("granted_by") or {}).get("class") == cls
              or ((a.get("granted_by") or {}).get("species_key") == species_key
                  and (a.get("granted_by") or {}).get("lineage") in species_picks["options"])]
    spells = {level: [] for level in SPELL_LEVELS}
    spells["cantrips"] = _unique(_spell_names(b, picks["cantrips"] + feat["cantrips"] + species_picks["cantrips"]))
    level1 = picks["spellbook"] or picks["prepared"]
    spells["level1"] = _unique(_spell_names(b, level1 + feat["spells"] + always))
    prepared = _unique(_spell_names(b, picks["prepared"] + feat["spells"] + always))
    # The class's ability; without class casting, the Origin feat's, then the species lineage's pick.
    ability = (traits.get("spellcasting_ability") or {}).get("ability") or feat["ability"] or species_picks.get("ability")
    spellcasting = {"ability": ability or "N/A", "spellSaveDC": 0, "spellAttackBonus": 0, "spells": spells}
    if prepared:
        spellcasting["preparedSpells"] = prepared

    racial = []
    for trait in species_grants.get("traits") or []:
        name = trait.get("name") if isinstance(trait, dict) else trait
        text = (trait.get("text") if isinstance(trait, dict) else None) or descriptions.get(name, "")
        racial.append({"name": name, "description": text, "source": "%s species" % species["name"]})
    # A picked species choice is shown as "<choice>: <option>" ("Draconic Ancestry: Red"). Display only: every
    # engine reader takes the typed choice id from the intent (N4).
    folded = []
    trait_names = {t.get("name") if isinstance(t, dict) else t for t in species_grants.get("traits") or []}
    for choice in [c for c in (species.get("grants") or {}).get("choices") or [] if not c.get("kind")]:
        cid = "species.%s.%s" % (species_key, _slug(choice["name"]))
        if b.picked(cid) and choice.get("trait") in trait_names:
            folded.append(choice["trait"])   # the authored trait the choice belongs to
        for option in b.picked(cid):
            name = b.source("racialTraits", cid, "%s: %s" % (choice["name"], option))
            racial.append({"name": name, "description": descriptions.get(name, ""),
                           "source": "%s species" % species["name"]})

    sheet: Dict[str, Any] = {
        "character_role": "player", "character_type": "player", "type": "player",
        "name": creative["name"].strip(), "alignment": creative["alignment"],
        "personality_traits": creative["personality_traits"], "ideals": creative["ideals"],
        "bonds": creative["bonds"], "flaws": creative["flaws"],
        "level": 1, "race": species["name"], "class": class_name, "background": background["name"],
        "subclass": None, "status": "alive", "condition": "none", "condition_affected": [],
        "experience_points": 0, "temporaryEffects": [], "injuries": [],
        "abilities": _ability_scores(b, background, rolled),
        "savingThrows": b.source("savingThrows", "choices.class_traits.%s.saving_throws" % cls,
                                 list(traits.get("saving_throws") or [])),
        "skills": _unique(background_skills + picks["skills"] + species_picks["skills"]),
        "expertise": _unique(picks["expertise"]),
        "proficiencies": {
            "armor": [ARMOR_LABELS[a] for a in traits.get("armor_training") or [] if a in ARMOR_LABELS],
            "weapons": _weapon_labels(traits),
            "tools": _unique(list(traits.get("tool_proficiencies") or []) + picks["tools"]
                             + background_tools + tool_pick + species_picks["tools"]),
        },
        "languages": _unique(languages),
        "damageResistances": resistances, "damageImmunities": [], "damageVulnerabilities": [],
        "conditionImmunities": [],
        "classFeatures": features, "racialTraits": racial, "feats": feats,
        "spellcasting": spellcasting,
        "equipment": [], "ammunition": [], "equipment_effects": [], "attacksAndSpellcasting": [],
        "currency": {"gold": 0, "silver": 0, "copper": 0},
        # Derived by the startup finalize (packages, startup_mechanics): placeholders it overwrites.
        "hitPoints": 0, "maxHitPoints": 0, "armorClass": 10, "initiative": 0, "proficiencyBonus": 2,
        "exp_required_for_next_level": 300,
    }
    # 10 + Dexterity modifier until the finalize projects armor class (armor_class.project: the packages'
    # armor, a shield, and Unarmored Defense for a Barbarian or Monk). With the engine unavailable this
    # base stays, disclosed as unchecked (D-PKG-1); it leaves out Unarmored Defense's second ability.
    sheet["armorClass"] = 10 + (sheet["abilities"]["dexterity"] - 10) // 2
    if background_feature is not None:
        sheet["backgroundFeature"] = background_feature
    for key in ("size", "speed"):
        if key in species_grants:
            sheet[key] = species_grants[key]
    # An untyped darkvision is left out (listed in untyped), never written as 0 (nql-c0 S3).
    sheet["senses"] = {"passivePerception": 10}
    if "darkvision" in species_grants:
        sheet["senses"]["darkvision"] = species_grants["darkvision"]
    # A class order's typed grants (Protector, Warden), the same pass the save repair runs (#888), so the
    # interview preview and the finalized sheet equal the saved one (all-class D1, dplay-AC-druid turn 9).
    for entry in leveling_choices.apply_order_grants(sheet):
        b.source("proficiencies", "choices.order_grants.%s" % entry["feature"], entry["added"])
    # char_schema is frozen (NEQ-SCHEMA-01) and has no backstory or appearance property: they stay in the
    # build's provenance (the startup_engine_build item) until the owner rules on a schema delta (D3).
    extra = {k: creative[k] for k in ("backstory", "appearance")
             if isinstance(creative.get(k), str) and creative[k].strip()}
    return sheet, {"engine_build": b.trace, "untyped": b.untyped, "creative_extra": extra, "folded_traits": folded}


def _species_trait_names(sheet: Dict[str, Any], built: Optional[Dict[str, Any]]) -> List[str]:
    """The summary's species traits, a trait with a picked option once, as "<choice>: <option>"
    (dplay-AC-difficult turn 18): the build names the folded base traits by the species choice it picked.
    Display only; the sheet keeps both entries."""
    folded = set((built or {}).get("folded_traits") or [])
    return [t.get("name") for t in sheet.get("racialTraits") or [] if isinstance(t, dict) and t.get("name") not in folded]


def render_sheet_summary(sheet: Dict[str, Any], built: Optional[Dict[str, Any]] = None) -> str:
    """The build summary the player approves, rendered from the engine-built sheet (D2, #1275): names and
    numbers only, never an id. Gear comes from the chosen packages when the character is saved."""
    def mod(score: int) -> str:
        return "%+d" % ((score - 10) // 2)
    abilities = sheet.get("abilities") or {}
    casting = sheet.get("spellcasting") if isinstance(sheet.get("spellcasting"), dict) else {}
    spells = casting.get("spells") or {}
    proficiencies = sheet.get("proficiencies") or {}
    senses = sheet.get("senses") or {}
    lines = ["%s %s, %s background" % (sheet.get("race"), sheet.get("class"), sheet.get("background")),
             "Size %s, speed %s ft%s" % (sheet.get("size"), sheet.get("speed"),
                                         ", darkvision %s ft" % senses["darkvision"] if senses.get("darkvision") else ""),
             "", "Ability scores:"]
    lines += ["- %s %d (%s)" % (a.capitalize(), abilities[a], mod(abilities[a])) for a in ABILITIES if a in abilities]
    if sheet.get("maxHitPoints"):  # the finalized sheet; a preview's are not derived yet
        lines += ["", "Hit points %s, armor class %s" % (sheet["maxHitPoints"], sheet.get("armorClass"))]
    elif (built or {}).get("hit_points"):
        # The preview's level-1 maximum from the typed derivation (dplay-AC-difficult turn 18); armor class
        # needs the granted gear, so it comes with the saved sheet.
        lines += ["", "Hit points %s" % built["hit_points"]]
    sections = [
        ("Saving throws:", sheet.get("savingThrows")),
        ("Skills:", sheet.get("skills")),
        ("Expertise:", sheet.get("expertise")),
        ("Armor and weapons:", (proficiencies.get("armor") or []) + (proficiencies.get("weapons") or [])),
        ("Tools:", proficiencies.get("tools")),
        ("Languages:", sheet.get("languages")),
        ("Resistances:", sheet.get("damageResistances")),
        ("Class features:", [f.get("name") for f in sheet.get("classFeatures") or []]),
        ("Species traits:", _species_trait_names(sheet, built)),
        ("Feats:", [f.get("name") for f in sheet.get("feats") or []]),
        ("Cantrips:", spells.get("cantrips")),
        ("Level 1 spells:", spells.get("level1")),
    ]
    for label, items in sections:
        items = [str(i) for i in items or [] if i]
        if items:
            lines += ["", label] + ["- %s" % i for i in items]
    lines += ["", "Starting gear comes from your chosen packages when the character is saved."]
    return "\n".join(lines)
