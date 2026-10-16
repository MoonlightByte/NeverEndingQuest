# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Selected player capability context for the tactical-intent role (T096)."""

from __future__ import annotations


SKILL_ABILITIES = {
    "Acrobatics": "dexterity",
    "Animal Handling": "wisdom",
    "Arcana": "intelligence",
    "Athletics": "strength",
    "Deception": "charisma",
    "History": "intelligence",
    "Insight": "wisdom",
    "Intimidation": "charisma",
    "Investigation": "intelligence",
    "Medicine": "wisdom",
    "Nature": "intelligence",
    "Perception": "wisdom",
    "Performance": "charisma",
    "Persuasion": "charisma",
    "Religion": "intelligence",
    "Sleight of Hand": "dexterity",
    "Stealth": "dexterity",
    "Survival": "wisdom",
}

def _normalized_text(value):
    return " ".join(str(value or "").split())


def _named_entries(value):
    if isinstance(value, dict):
        value = [
            {"name": name, "description": description}
            for name, description in value.items()
        ]
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, str):
            name = item.strip()
            description = ""
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("title") or "").strip()
            description = _normalized_text(item.get("description"))
        else:
            continue
        if not name:
            continue
        entry = {"name": name}
        if description:
            entry["description"] = description
        result.append(entry)
    return result


def _explicit_expertise(sheet):
    result = set()
    for key in ("expertise", "skillExpertise", "expertiseSkills"):
        value = (sheet or {}).get(key)
        if isinstance(value, dict):
            result.update(str(name).strip().lower() for name, enabled in value.items() if enabled)
        elif isinstance(value, list):
            result.update(str(name).strip().lower() for name in value if name)
    return result


def _skill_context(sheet):
    skills = (sheet or {}).get("skills")
    expertise = _explicit_expertise(sheet)
    result = []
    if isinstance(skills, dict):
        for name, modifier in skills.items():
            if not isinstance(name, str) or type(modifier) is not int:
                continue
            item = {
                "name": name,
                "modifier": modifier,
                "proficient": None,
            }
            if name.strip().lower() in expertise:
                item["expertise"] = True
            result.append(item)
    elif isinstance(skills, list):
        abilities = (sheet or {}).get("abilities")
        if not isinstance(abilities, dict):
            abilities = (sheet or {}).get("abilityScores") or {}
        proficiency = (sheet or {}).get("proficiencyBonus")
        for raw_name in skills:
            if not isinstance(raw_name, str) or not raw_name.strip():
                continue
            name = raw_name.strip()
            item = {
                "name": name,
                "proficient": True,
            }
            has_expertise = name.lower() in expertise
            if has_expertise:
                item["expertise"] = True
            ability = SKILL_ABILITIES.get(name)
            score = abilities.get(ability) if ability else None
            if type(score) is int and type(proficiency) is int:
                multiplier = 2 if has_expertise else 1
                item["modifier"] = (score - 10) // 2 + proficiency * multiplier
                item["ability"] = ability
            result.append(item)
    result.sort(key=lambda item: item["name"].lower())
    return result


def _proficiency_context(sheet):
    value = (sheet or {}).get("proficiencies")
    result = []
    if isinstance(value, dict):
        for category, names in value.items():
            if isinstance(names, str):
                names = [names]
            if not isinstance(names, list):
                continue
            clean = [str(name) for name in names if isinstance(name, str) and name.strip()]
            if clean:
                result.append({"category": str(category), "names": clean})
    elif isinstance(value, list):
        clean = [str(name) for name in value if isinstance(name, str) and name.strip()]
        if clean:
            result.append({"category": "general", "names": clean})
    return result


def build_player_capability_context(sheet, actor_name=None):
    """Return facts absent from the existing compact T096 sheet contract."""
    if not isinstance(sheet, dict):
        return {}
    context = {
        "actor": str(actor_name or sheet.get("name") or ""),
        "skills": _skill_context(sheet),
        "feats": _named_entries(sheet.get("feats")),
        "speciesTraits": _named_entries(
            sheet.get("speciesTraits", sheet.get("racialTraits"))
        ),
        "proficiencies": _proficiency_context(sheet),
    }
    return context
