# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""A sheet's Fighting Style recorded the way level-up writes it (#569, #760).

The engine grants a style only for the exact classFeatures name
"Fighting Style: <name>" (core.nql.genesis). ``canonicalize`` rewrites the
entries that record an SRD 5.2.1 style by exact name ("Defense",
"Fighting Style (Defense)") into that one entry; startup runs it on a new
character and level-up on a saved one. ``pending_note`` says, at an AC
projection, that a saved sheet's style is not applied until then. Moved from
utils/startup_wizard.py, which keeps its private names as aliases.
"""
import copy
import os
from typing import Any, Dict, Optional

from utils.encoding_utils import safe_json_load

# The startup origins file (utils.startup_prompt_builder.ORIGINS_FILE), read from the repo root.
ORIGINS_BASENAME = "srd_character_origins.json"


FEATURE = "fighting style"


def style_texts():
    """The SRD Fighting Style feats named by data/srd/choices.json feats[]
    (category "Fighting Style"), as casefolded name -> (name, text); the text is
    the startup origins file's fighting_style_feats entry of that name."""
    from core.leveling import choices, tables
    origins = safe_json_load(os.path.join(os.path.dirname(os.path.dirname(tables._DATA)), ORIGINS_BASENAME)) or {}
    texts = {str(feat.get("name", "")).strip().casefold(): feat.get("text", "")
             for feat in origins.get("fighting_style_feats") or [] if isinstance(feat, dict)}
    out = {}
    for feat in choices.data().get("feats") or []:
        if isinstance(feat, dict) and feat.get("category") == "Fighting Style" and feat.get("name"):
            key = str(feat["name"]).strip().casefold()
            out[key] = (feat["name"], texts.get(key, ""))
    return out


def styles_allowed(class_name, level):
    """How many Fighting Style features the class has gained by this level, from
    the progression tables' features_by_level; 0 for an unknown class."""
    from core.leveling import tables
    entry = (tables.tables().get("classes") or {}).get(str(class_name).strip().casefold())
    by_level = entry.get("features_by_level") if isinstance(entry, dict) else None
    if not isinstance(by_level, dict) or type(level) is not int:
        return 0
    return sum(1 for n in range(1, level + 1) for feature in by_level.get(str(n), [])
               if str(feature).strip().casefold() == FEATURE)


def style_named(name, styles):
    """The style an entry's exact name records ("Defense", "Fighting Style: Defense"
    or "Fighting Style (Defense)") as a casefolded key; "" for a Fighting Style name
    that records no typed style; None for any other entry."""
    text = str(name or "").strip()
    if text.casefold() in styles:
        return text.casefold()
    if not text.casefold().startswith(FEATURE):
        return None
    rest = text[len(FEATURE):].strip()
    if rest.startswith(":"):
        rest = rest[1:]
    elif rest.startswith("(") and rest.endswith(")"):
        rest = rest[1:-1]
    elif rest:
        return None
    rest = rest.strip().casefold()
    return rest if rest in styles else ""


def canonicalize(character, provenance=None, *, source):
    """Record a new character's chosen Fighting Style the way level-up writes it:
    one classFeatures entry "Fighting Style: <name>" (#569). The engine grants
    Defense's +1 only for that exact name (core.nql.genesis). Entries are matched
    by exact name, never by description; the entries recording the chosen style
    are replaced by that one entry. A style the class has not gained by its
    level, more styles than it has gained, or a name recording no typed style is
    left as written and noted for the reviewer."""
    notes = []
    styles = style_texts()
    found = []
    for field in ("classFeatures", "feats"):
        for index, entry in enumerate(character.get(field) or []):
            if not isinstance(entry, dict):
                continue
            key = style_named(entry.get("name"), styles)
            if key:
                found.append((field, index, key))
            elif key == "":
                notes.append(f"{field} {entry.get('name')!r} records no SRD 5.2.1 Fighting Style; "
                             "left as written, not applied")
    chosen = sorted({key for _, _, key in found})
    if not chosen:
        return notes
    class_name = character.get("class")
    level = character.get("level")
    allowed = styles_allowed(class_name, level)
    sources = [f"{field} {character[field][index].get('name')!r}" for field, index, _ in found]
    record = {
        "source": source,
        "style": None, "moved_from": [], "left_as_written": [],
        "policy": ("One classFeatures entry 'Fighting Style: <name>' per chosen SRD style, as level-up "
                   "writes it; untyped or surplus entries are left and noted."),
    }
    if provenance is not None:
        provenance["fighting_style"] = record
    names = ", ".join(styles[key][0] for key in chosen)
    if allowed < 1:
        record["left_as_written"] = sources
        notes.append(f"Fighting Style {names} is listed, but {class_name} level {level} has no "
                     "Fighting Style feature; left as written, not applied")
        return notes
    if len(chosen) > allowed:
        record["left_as_written"] = sources
        notes.append(f"Fighting Styles {names} listed; {class_name} level {level} has {allowed}; "
                     "left as written, not applied")
        return notes
    name, text = styles[chosen[0]]
    canonical = f"Fighting Style: {name}"
    record["style"] = name
    field, index, _ = found[0]
    if len(found) == 1 and field == "classFeatures" and character[field][index].get("name") == canonical:
        return notes
    entry = {"name": canonical, "description": text,
             "source": character[field][index].get("source") or f"{class_name} level {level}"}
    drop = {(f, i) for f, i, _ in found}
    for each in ("classFeatures", "feats"):
        if not isinstance(character.get(each), list):
            continue
        kept = []
        for i, item in enumerate(character[each]):
            if (each, i) == (field, index) and each == "classFeatures":
                kept.append(entry)
            elif (each, i) not in drop:
                kept.append(item)
        character[each] = kept
    if field != "classFeatures":
        character.setdefault("classFeatures", []).append(entry)
    record["moved_from"] = sources
    notes.append(f"{canonical} set in classFeatures (was {', '.join(sources)})")
    return notes


def pending_note(sheet: Dict[str, Any]) -> Optional[str]:
    """The note for a saved sheet whose Fighting Style a level-up would rewrite
    (#760); None for a canonical or style-less sheet, one left as written, or
    when the style data cannot be read (a projection never fails for a note)."""
    record: Dict[str, Any] = {}
    try:
        canonicalize(copy.deepcopy(sheet), record, source="core.leveling.fighting_style.pending_note")
    except (OSError, ValueError):
        return None
    style = record.get("fighting_style") or {}
    if not style.get("moved_from"):
        return None
    return (f"{', '.join(style['moved_from'])} records Fighting Style: {style['style']} in a non-canonical form; "
            f"its effect is not applied until a level-up records it as 'Fighting Style: {style['style']}'")
