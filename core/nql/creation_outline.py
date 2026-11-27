# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""The local-model outline of character creation (#2090, owner 2026-11-27).

A short directory of the creation steps, classes, species and backgrounds, read from the data files at each call
(the ones the creation scope reads), never typed by hand. It goes only to a Local/Custom server's T092 interview
(core/ai/api_client.py); the OpenAI request never carries it. The same data gives the same bytes, so a server's
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


def outline_text() -> str:
    d = creation_scope._Data()
    if not d.ok:
        raise ValueError("creation data unavailable")
    attribution = d.origins.get("_srd_attribution")
    if not isinstance(attribution, str) or "CC BY 4.0" not in attribution:
        raise ValueError("no attribution")
    methods = list(_METHODS)
    out: List[str] = [
        "LOCAL OUTLINE: a short directory of character creation, for orientation only. The creation scope message "
        "holds the full facts; pick options by its keys.",
        "Source: %s." % attribution.rstrip("."),
        "The usual flow (the player may give any part at any time; keep whatever they give): 1 %s; 2 the level-1 "
        "choices these open (intent.choices, by the ids the scope issues); the class gear is one of them; "
        "3 ability_scores: the player picks the method (%s or %s), then the assignment; 4 starting gear: %s, and the "
        "items inside the packages; 5 %s. Before approval, also propose and tell: %s." % (
            ", ".join(IDENTITY), ", ".join(methods[:-1]), methods[-1], PACKAGES[0], CREATIVE_FIELDS[0],
            ", ".join(CREATIVE_FIELDS[1:])),
        "The package value is the bare letter: starting_equipment.%s \"A\" and starting_equipment.%s \"A\", never an "
        "id or a list of items. An item inside a package (holy symbol, gaming set) goes in starting_equipment.slot_picks "
        "by its slot id; what is worn or held goes in starting_equipment.equipped." % (PACKAGES[1], PACKAGES[0]),
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
