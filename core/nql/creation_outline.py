# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""The local-model outline of character creation (#2090, owner 2026-11-27).

A short directory of the creation steps, classes, species and backgrounds, read from the data files at each call
(the ones the creation scope reads), never typed by hand. It goes only to a Local/Custom server's T092 interview
and its handed-back turn's plain words request (core/ai/api_client.py); the OpenAI request never carries it. The same data gives the same bytes, so a server's
prefix cache keeps it from turn to turn. ``outline_text()`` raises when the data cannot be read; the caller then
sends without it.
"""
import re
from typing import List

from core.nql import creation_scope
from core.nql.creation_blocks import IDENTITY, PACKAGES, _METHODS
from core.nql.creation_build import CREATIVE_FIELDS


def _size_word(size: str) -> str:
    """"Medium (about 4-7 feet tall) or Small (...), chosen when ..." -> "Medium or Small"."""
    return " ".join(re.sub(r"\([^)]*\)", "", size).split(",")[0].split())


# The worked example's weapons (the player's words in the S1.2 live runs); their properties are read from the data.
EXAMPLE = ("Greatsword", "Flail", "Javelin")


def _weapon_free_picks(d) -> List[tuple]:
    """(class_key, point) of each level-1 Weapon Mastery pick: a free pick whose option source is weapons:..."""
    out = []
    for key in d.classes():
        for _cid, p in creation_scope._class_points(key, d):
            if str(p.get("option_source") or "").split(":", 1)[0] == "weapons":
                if p.get("name") != "Weapon Mastery":
                    raise ValueError("weapons pick")
                out.append((key, p))
    return out


def outline_text() -> str:
    d = creation_scope._Data()
    if not d.ok:
        raise ValueError("creation data unavailable")
    attribution = d.origins.get("_srd_attribution")
    if not isinstance(attribution, str) or "CC BY 4.0" not in attribution:
        raise ValueError("no attribution")
    methods = list(_METHODS)
    if methods != ["standard_array", "point_buy", "random"]:
        raise ValueError("methods")
    sm = d.origins.get("ability_score_methods") or {}
    array, budget = sm["standard_array"], sm["point_cost"]["budget"]
    costs = [int(k) for k in sm["point_cost"]["costs"]]
    raised = sorted(d.origins["backgrounds"], key=lambda b: b["key"])[0]["ability_keys"]
    mastery = sorted(key for key, _p in _weapon_free_picks(d))
    if not mastery:
        raise ValueError("no weapon free pick")
    # Each non-magical weapon of the catalog with its one mastery property (the weapons list the scope sends).
    mastery_of = {}
    for e in d.items:
        w = e.get("weapon") if isinstance(e.get("weapon"), dict) else {}
        if e.get("kind") == "weapon" and not e.get("magical") and w.get("mastery"):
            mastery_of[e["name"]] = w["mastery"]
    props = [p["name"] for p in d.origins.get("weapon_mastery_properties") or []]
    if not mastery_of or set(mastery_of.values()) - set(props):
        raise ValueError("weapon masteries")
    by_property = [(p, [n for n, m in mastery_of.items() if m == p]) for p in props]
    by_property = [(p, names) for p, names in by_property if names]
    if any(w not in mastery_of for w in EXAMPLE) or len({mastery_of[w] for w in EXAMPLE}) != 3:
        raise ValueError("example weapons")
    # FINISHING (#2090 r8): the reply's decision values, from the contract, and a worn-and-held example from the data:
    # the armor and the first example weapon of the fighter's class package A.
    from utils.startup_contract import _scoped_reply_schema, creation_alignments

    decisions = _scoped_reply_schema()["properties"]["decision"]["enum"]
    if decisions != ["continue_interview", "finalize_character", "pause_setup"]:
        raise ValueError("decisions")
    kinds = {e.get("id"): e.get("kind") for e in d.items}
    ids = {e.get("name"): e.get("id") for e in d.items}
    package = [p for _cid, p in creation_scope._class_points("fighter", d) if isinstance(p.get("option_items"), dict)]
    held = [i.get("catalog_id") for i in package[0]["option_items"]["A"]["items"]] if len(package) == 1 else []
    worn = [i for i in held if kinds.get(i) == "armor"][:1] + [i for i in held if i == ids.get(EXAMPLE[0])]
    if len(worn) != 2:
        raise ValueError("equipped example")
    # r9: the alignment values (the character schema's enum, the one the engine writes) and a choice id example.
    alignments = creation_alignments()
    if not alignments or not all(isinstance(a, str) and a.isascii() for a in alignments):
        raise ValueError("alignments")
    style = [cid for cid, p in creation_scope._class_points("fighter", d) if p.get("name") == "Fighting Style"]
    if len(style) != 1:
        raise ValueError("choice id example")
    out: List[str] = [
        "LOCAL OUTLINE: a short directory of character creation. The creation scope message holds the full facts; "
        "pick options by its keys.",
        "Source: %s." % attribution.rstrip("."),
        "The usual flow (the player may give any part at any time; keep whatever they give): 1 %s; 2 the level-1 "
        "choices these open (intent.choices, by the ids the scope issues); the class gear is one of them; "
        "3 ability_scores: the player's method, then the assignment; 4 starting gear: %s, and the items inside the "
        "packages; 5 %s. Before approval, also propose and tell: %s." % (
            ", ".join(IDENTITY), PACKAGES[0], CREATIVE_FIELDS[0], ", ".join(CREATIVE_FIELDS[1:])),
        "The package value is the bare letter: starting_equipment.%s \"A\" and starting_equipment.%s \"A\", never an "
        "id or a list of items. An item inside a package (holy symbol, gaming set) goes in starting_equipment.slot_picks "
        "by its slot id; what is worn or held goes in starting_equipment.equipped." % (PACKAGES[1], PACKAGES[0]),
        "Ability scores: the assignment holds all six abilities, each the method's own value before any increase "
        "(%s: %s, each once; %s: %s to %s within %s points; %s: the engine's roll). The background's increase is its "
        "own open choice, intent.choices[\"background.<background_key>.ability-scores\"] = [one listed option], such as "
        "[\"+2 %s, +1 %s\"]; never add it into the assignment." % (
            methods[0], ", ".join(map(str, array)), methods[1], min(costs), max(costs), budget, methods[2],
            raised[0], raised[1]),
        "For %s, the note's ability_roll.rolled are the only base scores: the player places exactly these six (or asks "
        "you to), and the assignment records only them, never other numbers. The background increase is added by the "
        "engine; tell the totals from the sheet. They are never rolled again: a request to reroll keeps them. %s is "
        "called the standard array only for the %s method." % (
            methods[2], ", ".join(map(str, array)), methods[0]),
        "Every open choice takes one of its own options, written exactly as the scope or the note's open_choices lists "
        "it (a spell by its key or its name).",
        "A choice id is copied exactly from the scope or the note's open_choices, such as \"%s\"; never build one from "
        "the pattern of other ids." % style[0],
        "When the player names a choice's picks, send them in intent.choices in that same reply; saying them is not "
        "recording them.",
        "WEAPON MASTERY (%s; a free_pick, so the scope gives no list): the player picks WEAPONS. Each weapon has exactly "
        "one fixed mastery property that comes with it; the pick records the weapon name, and the property follows by "
        "itself. So when the player names weapons, write those names; when the player names a property, offer the "
        "weapons your class can master that have it, and write the weapon they choose." % ", ".join(mastery),
        "MASTERY PROPERTIES (property: the weapons that have it)",
    ] + ["%s: %s" % (prop, ", ".join(names)) for prop, names in by_property] + [
        "Example: the player says \"%s, %s and %s\" -> intent.choices[\"<class_key>.weapon-mastery.weapon-mastery\"] = "
        "[\"%s\", \"%s\", \"%s\"]; never [\"%s\", \"%s\", \"%s\"]." % (
            tuple(EXAMPLE) + tuple(EXAMPLE) + tuple(mastery_of[w] for w in EXAMPLE)),
        "Kept is what the note's blocks.filled shows, plus what you send in this reply. A value the player gave in an "
        "earlier message that blocks.filled lacks is not kept: say so plainly and ask for it again. Never tell the "
        "player a value is set, locked in or recorded unless blocks.filled shows it or you send it now; a plain-words "
        "reply sends nothing.",
        "FINISHING (decision: %s, %s or %s):" % tuple(decisions),
        "1 While blocks.needed lists anything, ask for it; never give a whole-build summary and never send %s." % (
            decisions[1]),
        "2 When blocks.needed is empty, the engine builds the character and gives its summary as the note's \"sheet\". "
        "If the note shows no sheet, answer %s: the engine adds the sheet and asks again. While the note's "
        "engine_answer says the engine built this character, answer %s, even when the player already said they "
        "approve: tell the whole build from the sheet, in your own words with its names and numbers, and ask for "
        "approval." % (decisions[0], decisions[0]),
        "3 A summary states only what the sheet and blocks.filled show; never add a number of your own (an Armor "
        "Class, a gold total, a bonus).",
        "4 When the player's latest message approves the build you told from the sheet: %s, "
        "confirmation.whole_build_approved true, confirmation.player_message_index = the note's latest_user_index. "
        "Leave out what blocks.filled already holds; never resend ability_scores with the increase added." % (
            decisions[1]),
        "5 starting_equipment.equipped lists the catalog id of every item the player wears or holds, from their "
        "packages' items, such as [\"%s\", \"%s\"]; the sheet's Worn and Held lines show what is written." % tuple(worn),
        "6 A plain-words reply records nothing and finalizes nothing: never say the character is finalized, saved or "
        "ready to begin; ask the player to approve the summary or to say what to change.",
        "7 creative.alignment is exactly one of: %s." % ", ".join(alignments),
        "CLASSES (class_key: hit die; primary; armor; casting; class_package letters)",
    ]
    for key in sorted(d.classes()):
        traits = d.choices["class_traits"][key]
        prog = (d.progression.get("classes") or {}).get(key) or {}
        primary = traits.get("primary_ability") or {}
        abilities = " or ".join(primary.get("any_of") or []) or " and ".join(primary.get("all_of") or [])
        armor = ", ".join(traits.get("armor_training") or []) or "none"
        kind = prog.get("caster_kind")
        casting = "%s caster" % kind if kind not in (None, "none") else "no spells"
        gear = [p for _cid, p in creation_scope._class_points(key, d) if isinstance(p.get("option_items"), dict)]
        if len(gear) != 1:
            raise ValueError("class package count")
        out.append("%s: %s; %s; %s; %s; %s" % (key, prog.get("hit_die"), abilities, armor, casting,
                                               ", ".join(gear[0]["option_source"])))
    out.append("SPECIES (species_key: size; speed; traits)")
    for key, s in sorted(d.species().items()):
        names = [t.get("name") for t in (s.get("grants") or {}).get("traits") or [] if isinstance(t, dict)]
        out.append("%s: %s; %s; %s" % (key, _size_word(s.get("size", "")), s.get("speed"), ", ".join(names)))
    out.append("BACKGROUNDS (background_key: the three abilities it raises; skills; feat; background_package letters)")
    for key, b in sorted(d.backgrounds().items()):
        out.append("%s: %s; %s; %s; %s" % (key, ", ".join(b.get("ability_keys") or []),
                                           " and ".join(b.get("skill_keys") or []), b.get("feat"),
                                           ", ".join(sorted(b.get("equipment_options") or {}))))
    out.append(
        "The lines above are enough to present every option. intent.considering is for depth: put a key there only "
        "for an option the player wants to hear about in detail, two or three at a time. Each key adds that option's "
        "full facts to every later request, and a list stays as sent until you send that kind again. Drop a key once "
        "the player is no longer asking about it; send [] for a kind once the player has chosen it and is not weighing "
        "another. The note's considering is what is kept, not what to send back.")
    text = "\n".join(out) + "\n"
    if not text.isascii():
        raise ValueError("not ASCII")
    return text
