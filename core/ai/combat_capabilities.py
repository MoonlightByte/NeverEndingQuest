# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root

"""Selected player capability context and conservative narrative matching."""

from __future__ import annotations

from difflib import SequenceMatcher

from core.ai.srd_reference import (
    fuzzy_rule_candidate_allowed,
    normalize_rule_name,
    tokenize_rule_text,
)


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

COMMON_ACTIONS = (
    "Defend",
    "Dodge",
    "Disengage",
    "Dash",
    "Hide",
    "Help",
    "Flee",
    "Yield",
)

NARRATIVE_SYNONYMS = {
    "Sneak Attack": (
        "backstab",
        "strike from hiding",
        "hit a weak point",
        "hit where it hurts",
    ),
    "Cunning Action": ("duck away", "slip free"),
    "Disengage": ("duck away", "slip free", "get out safely"),
    "Stealth": (
        "sneak",
        "move unseen",
        "blend into the crowd",
        "slip through the crowd unseen",
    ),
    "Hide": ("move unseen", "blend into the crowd", "strike from hiding"),
    "Help": ("protect them", "help them", "give them an opening"),
    "Defend": ("protect them", "draw attention", "guard them"),
}


def _tokens(value):
    # Spans passed to the SRD guard must use its exact Unicode normalization;
    # otherwise a guarded short-spell window can inspect the wrong tokens.
    return tokenize_rule_text(value)


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


def _candidate_rows(sheet, context):
    rows = []
    seen = set()

    def add(kind, name, aliases=()):
        if not isinstance(name, str) or not name.strip():
            return
        marker = (kind, normalize_rule_name(name))
        if not marker[1] or marker in seen:
            return
        seen.add(marker)
        rows.append(
            {
                "kind": kind,
                "name": name.strip(),
                "aliases": tuple(
                    alias for alias in aliases if isinstance(alias, str) and alias.strip()
                ),
            }
        )

    for skill in context.get("skills", []):
        add("skill", skill.get("name"))
    for key in ("attacksAndSpellcasting", "actions"):
        for entry in (sheet.get(key) or []):
            if isinstance(entry, dict):
                add("attack", entry.get("name"), entry.get("aliases") or ())
    for key in ("classFeatures", "specialAbilities"):
        for entry in (sheet.get(key) or []):
            if isinstance(entry, dict):
                add("feature", entry.get("name"), entry.get("aliases") or ())
            elif isinstance(entry, str):
                add("feature", entry)
    for entry in context.get("feats", []):
        add("feat", entry.get("name"))
    for entry in context.get("speciesTraits", []):
        add("speciesTrait", entry.get("name"))
    for group in context.get("proficiencies", []):
        for name in group.get("names", []):
            add("proficiency", name)
    spells = ((sheet.get("spellcasting") or {}).get("spells") or {})
    if isinstance(spells, dict):
        for values in spells.values():
            if isinstance(values, list):
                for name in values:
                    add("spell", name)
    for name in COMMON_ACTIONS:
        add("commonAction", name)
    return rows


def _phrase_spans(text_tokens, term_tokens):
    if not term_tokens or len(term_tokens) > len(text_tokens):
        return ()
    return tuple(
        (index, index + len(term_tokens))
        for index in range(len(text_tokens) - len(term_tokens) + 1)
        if text_tokens[index : index + len(term_tokens)] == term_tokens
    )


def _fuzzy_score(text_tokens, name_tokens):
    if not name_tokens or not text_tokens:
        return None
    width = len(name_tokens)
    best = None
    for size in sorted(set((max(1, width - 1), width, width + 1))):
        if size > len(text_tokens):
            continue
        for start in range(len(text_tokens) - size + 1):
            end = start + size
            phrase = " ".join(text_tokens[start:end])
            score = SequenceMatcher(None, phrase, " ".join(name_tokens)).ratio()
            if best is None or score > best[0]:
                best = (score, start, end, phrase)
    return best


def match_owned_capabilities(sheet, text, actor_name=None):
    """Return deterministic hints only from capabilities owned by the actor."""
    context = build_player_capability_context(sheet, actor_name=actor_name)
    rows = _candidate_rows(sheet or {}, context)
    text_tokens = _tokens(text)
    selected = {}

    def keep(row, source, score, phrase):
        marker = (row["kind"], normalize_rule_name(row["name"]))
        if row["kind"] == "spell":
            for existing_marker in tuple(selected):
                if existing_marker[1] == marker[1] and existing_marker[0] != "spell":
                    selected.pop(existing_marker, None)
        elif ("spell", marker[1]) in selected:
            return
        value = {
            "kind": row["kind"],
            "name": row["name"],
            "matchSource": source,
            "score": score,
        }
        if phrase:
            value["matchedText"] = phrase
        current = selected.get(marker)
        if current is None or score > current["score"]:
            selected[marker] = value

    for row in rows:
        terms = (row["name"],) + tuple(row.get("aliases") or ())
        for term_index, term in enumerate(terms):
            for start, end in _phrase_spans(text_tokens, _tokens(term)):
                if row["kind"] == "spell" and not fuzzy_rule_candidate_allowed(
                    text, term, "spell", (start, end)
                ):
                    continue
                keep(
                    row,
                    "exact" if term_index == 0 else "alias",
                    1000 - term_index * 10,
                    " ".join(text_tokens[start:end]),
                )

    by_name = {row["name"].lower(): row for row in rows}
    normalized_text = " ".join(text_tokens)
    for capability_name, phrases in NARRATIVE_SYNONYMS.items():
        row = by_name.get(capability_name.lower())
        if row is None:
            continue
        for phrase in phrases:
            if " ".join(_tokens(phrase)) in normalized_text:
                keep(row, "synonym", 850, phrase)

    fuzzy_rows = []
    for row in rows:
        fuzzy = None
        matched_reference = row["name"]
        for reference_term in (row["name"],) + tuple(
            NARRATIVE_SYNONYMS.get(row["name"], ())
        ):
            candidate_fuzzy = _fuzzy_score(text_tokens, _tokens(reference_term))
            if candidate_fuzzy is not None and (
                fuzzy is None or candidate_fuzzy[0] > fuzzy[0]
            ):
                fuzzy = candidate_fuzzy
                matched_reference = reference_term
        if fuzzy is None:
            continue
        score, start, end, phrase = fuzzy
        reference_tokens = _tokens(matched_reference)
        # Very short fuzzy terms are disproportionately collision-prone in
        # ordinary narration (for example target "blight" vs proficiency
        # "Light"). Exact aliases and reviewed synonyms still work.
        if len(reference_tokens) == 1 and len(reference_tokens[0]) <= 5:
            continue
        compact_length = len("".join(_tokens(matched_reference)))
        # Actor ownership, a unique-best margin and the SRD verb/blocklist
        # guards carry the safety boundary. These thresholds intentionally
        # admit common transpositions (sheild) and the owner's observed
        # Fireball -> furball typo without enabling broad global fuzzy lookup.
        threshold = 0.80 if compact_length <= 6 else 0.75
        if score < threshold:
            continue
        if row["kind"] == "spell" and not fuzzy_rule_candidate_allowed(
            text, row["name"], "spell", (start, end)
        ):
            continue
        fuzzy_rows.append((score, row, phrase, start, end))

    by_span = {}
    for value in fuzzy_rows:
        by_span.setdefault((value[3], value[4]), []).append(value)
    for span_rows in by_span.values():
        # A spell candidate survives its conservative guard only when the text
        # explicitly indicates spell use. In that case, prefer the owned spell
        # over an item/proficiency with the same approximate words.
        if any(value[1]["kind"] == "spell" for value in span_rows):
            span_rows = [value for value in span_rows if value[1]["kind"] == "spell"]
        span_rows.sort(
            key=lambda value: (-value[0], value[1]["kind"], value[1]["name"])
        )
        best_score = span_rows[0][0]
        unique_best = [value for value in span_rows if best_score - value[0] < 0.05]
        unique_markers = {
            (value[1]["kind"], normalize_rule_name(value[1]["name"]))
            for value in unique_best
        }
        if len(unique_markers) == 1:
            score, row, phrase, _start, _end = span_rows[0]
            keep(row, "typo", int(score * 800), phrase)

    return sorted(
        selected.values(),
        key=lambda item: (-item["score"], item["kind"], item["name"].lower()),
    )
