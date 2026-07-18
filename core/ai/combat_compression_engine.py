#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""
FINAL PRODUCTION - Combat message compressor for historical context.
Compresses verbose combat messages to reduce tokens in conversation history.
Validates every compressed tag block against its source before use or caching.
"""

import json
import hashlib
import re
import threading
import config
from core.ai import api_client
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T017", "core/ai/combat_compression_engine.py", 1337)
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import sys
import os
from utils.atomic_json_cache import merge_json_mapping, read_json_mapping

from model_config import NARRATIVE_COMPRESSION_MODEL

# Import usage tracking
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except:
    USAGE_TRACKING_AVAILABLE = False
    def track_response(r): pass  # No-op fallback

# Fully agentic combat compression prompt with self-contained @ROSTER for reversibility
COMBAT_COMPRESSION_PROMPT = """You are a 5th edition of the world's most popular roleplaying game combat data compressor. Transform a verbose combat block into compact @TAGS for LLM context.
Do ALL parsing yourself. Do NOT output code fences or commentary—ONLY the tags.

INPUT
A single combat message containing: round info, initiative tracker, "PROCESS … THEN STOP AT …" lines,
name hints, creature states (HP/slots), dice pools (generic, attacks, saves), rules, and a player action.

OUTPUT
Compact, deterministic @TAGS capturing exactly what's needed to resolve THIS segment (from the listed
"process" order up to the player's turn), plus a self-contained roster mapping so the block is reversible.

REQUIRED TAGS (each exactly once; if a datum is absent in source, omit its tag entirely)
- @T=CS/v2
- @ROUND=<exact combat_round integer copied from source>      # compression never resolves a turn or increments the round
- @PLAYER=<exact player name from source>                     # keep spaces and punctuation as-is, but drop "(player)" suffix
- @PROCESS=[<id:initiative>, ...]                             # creatures to process NOW, in initiative order
                                                             # Format entries as id:initiative (e.g., G3:18) — do NOT use parentheses
                                                             # If source says ">>> PROCESS ALL OF THESE": list creatures to resolve before stop
                                                             # If source says ">>> PROCESS TO END ROUND": list that exact end-round window
                                                             # If source says ">>> CURRENT: <name> - PLAYER TURN": set @PROCESS=[player:init] ONLY
                                                             #   (the player is the ONLY creature to process; after_player creatures are NOT in @PROCESS)
- @STOP=<same exact value as @PLAYER>                         # MUST equal @PLAYER; if source gives a stop name, use that exact name
- @STATUS=acted[...],dead[...],after_player[...],waiting[...] # from tracker; ALL FOUR groups MUST always appear, even if empty (e.g., acted[],dead[])
                                                             # exact syntax has NO '=' between any group name and '['
                                                             # Assign each creature to EXACTLY ONE group using this precedence: dead > acted > after_player > waiting
                                                             # after_player[] = creatures whose tracker line explicitly reads "- After Player"; do NOT also list in waiting[]
                                                             # waiting[] = all remaining alive creatures not yet acted, including @PLAYER during PLAYER TURN
                                                             # CRITICAL: @PLAYER MUST appear in exactly one group; never omit @PLAYER from @STATUS
- @ROSTER=[id:role:type:canonical, ...]                       # MUST include every actor referenced anywhere
                                                             # role ∈ {player, ally, enemy, neutral}
                                                             # type = monster species or class/archetype (e.g., Skeleton, Ranger, Scout, PC, unknown)
                                                             # canonical = exact name as it appears in source (spaces allowed)
- @HP=[<id:cur/max>, ...]                                     # include ALL living creatures from the tracker (not just @PROCESS) + the player
- @ATK=[<id:[r1,r2,...]>, ...]                                # MUST always appear when @PROCESS is non-empty; ONLY actors listed in @PROCESS
                                                             # For player (who rolls own dice): include player:[] (empty list, not a label or weapon name)
                                                             # For NPCs/monsters: include their pre-rolled attack values; preserve listed roll order
- @DICE={dX:[v1,v2,...], dY:[...]}                            # ONLY generic damage dice relevant to THIS segment; values must be within die faces
- @SLOTS=[<id:L#:curr/max>, ...]                              # ONLY partially used spell slots where curr < max
                                                             # NEVER include full slots (e.g., omit L3:2/2, L1:4/4, L2:3/3)
- @RULES=player_rolls,enforce_pools,inc_round_all             # abbreviated rules reminder
- @ACTION=<complete player action text>                       # do not paraphrase; keep punctuation and inventory context
                                                             # encode backslashes as \\\\ and embedded line breaks as literal \\n

OPTIONAL TAGS
- @BRIEF=<≤25 words of flavor>                                # non-authoritative; never interpreted as state or tags
                                                             # no @ characters or encoded/actual line breaks
- @SAVES=[id:STR:#,DEX:#,CON:#,INT:#,WIS:#,CHA:#; ...]        # only source-exact pools for actors needed THIS segment

NAME & ID RULES
- Player name: drop "(player)" suffix everywhere except optionally in @ROSTER canonical field
- Create short, unique IDs for compactness; reuse the same ID everywhere:
  - Numbered enemies: Zombie_3 → Z3, Bandit_2 → B2, Goblin_5 → G5
  - The base dead creature (no number) → id=Zom (for Zombie), Ban (for Bandit), Gob (for Goblin)
  - Normalize ally IDs to their given names: "Wizard Aldric" → id=Aldric, "Fighter Lyra" → id=Lyra
  - CRITICAL: Extract the actual name after the title. Do not modify or abbreviate the name portion
  - Never create variations - if the source says "Scout [Name]", use exactly "[Name]" as the ID
  - Player character: use their full name as ID (without "(player)" suffix)
  - If a type cannot be inferred, use type=unknown
- Every ID that appears in @PROCESS, @STATUS, @HP, @ATK, or @SAVES MUST appear exactly once in @ROSTER

DICE RULES
- Include only dice types actually relevant to THIS segment (e.g., skeleton shortbow/shortsword → d6; longbow → d8).
- When a processed NPC has multiple listed attack options and the action does not select one, include the die family for EVERY listed option.
- If PLAYER ACTION explicitly selects a processed NPC's listed attack option, include only that option's damage-die family.
- Do NOT include d4/d10/d12/d20 unless this segment clearly requires them now (e.g., a spell/effect that will be used).
- Provide enough values per die (≈5–6) for multi-hit turns.
- All values must be within the proper face range (e.g., d6 ∈ 1..6).

STOP LOGIC
- If the source includes ">>> THEN STOP AT: <name>", set @STOP to that exact name.
- Otherwise set @STOP to @PLAYER.
- @STOP MUST equal @PLAYER exactly.

SELF-CHECK (before you output -- reject and redo if ANY check fails)
- @PROCESS includes ONLY creatures that need resolution NOW. Dead creatures are NEVER in @PROCESS.
- If the input says "PLAYER TURN": @PROCESS has exactly ONE entry (the player). No enemies, no allies.
- If the input says "ROUND COMPLETE": @PROCESS lists ALL creatures marked [X] (Acted) in the tracker, excluding dead. This is NOT a player turn -- do NOT set @PROCESS to the player alone.
- @ROUND exactly equals the source combat_round even when the source says ROUND COMPLETE; the downstream resolver performs the increment.
- If the input says "PROCESS TO END ROUND": @PROCESS preserves that exact listed window and order.
- @STOP equals @PLAYER exactly.
- Every ID used in other tags exists in @ROSTER with role/type/canonical.
- @ROSTER role/type agree with source labels, name hints, and obvious canonical titles/species.
- @HP includes ALL living creatures (plus the player) from the tracker.
- @ATK MUST be present whenever @PROCESS has entries. It contains ONLY actors in @PROCESS. For the player (rolls own dice), use id:[] -- never a label or weapon name.
- @STATUS has exactly four groups: acted[], dead[], after_player[], waiting[]. All four MUST appear. @PLAYER MUST appear in exactly one group.
- No creature in more than one @STATUS group. Assign by precedence: dead > acted > after_player > waiting. A creature labeled "After Player" in source goes ONLY in after_player[], never also in waiting[].
- @DICE contains exactly the source-backed die families required by non-player actors in @PROCESS; use {} when none are deterministically required.
- @SLOTS contains only partially used slots; omit full ones.
- @ACTION preserves the entire PLAYER ACTION section, including any inventory-context line.
- @SAVES, when present, preserves source actor/ability order and values exactly; omit it unless the actor is needed now.
- @BRIEF is flavor only. It cannot contain tag syntax or line breaks and never overrides authoritative tags.

FORMAT
- Output ONLY the tags, one per line, no extra text, no prefixes, no code fences."""


_REQUIRED_COMPRESSION_TAGS = {
    "T",
    "ROUND",
    "PLAYER",
    "PROCESS",
    "STOP",
    "STATUS",
    "ROSTER",
    "HP",
    "ATK",
    "DICE",
    "RULES",
    "ACTION",
}
_OPTIONAL_COMPRESSION_TAGS = {"SLOTS", "BRIEF", "SAVES"}
_STATUS_GROUPS = ("acted", "dead", "after_player", "waiting")
_STATUS_PRECEDENCE = {
    "waiting": 0,
    "after_player": 1,
    "acted": 2,
    "dead": 3,
}
_RULES_VALUE = "player_rolls,enforce_pools,inc_round_all"
_SAVE_ABILITIES = ("STR", "DEX", "CON", "INT", "WIS", "CHA")
_CANONICAL_TITLE_TYPES = {
    "artificer": "Artificer",
    "barbarian": "Barbarian",
    "bard": "Bard",
    "captain": "Captain",
    "cleric": "Cleric",
    "druid": "Druid",
    "fighter": "Fighter",
    "guard": "Guard",
    "monk": "Monk",
    "paladin": "Paladin",
    "ranger": "Ranger",
    "rogue": "Rogue",
    "scout": "Scout",
    "sorcerer": "Sorcerer",
    "warlock": "Warlock",
    "wizard": "Wizard",
}
_OBVIOUS_MONSTER_TYPES = {
    "bandit": "Bandit",
    "bugbear": "Bugbear",
    "cultist": "Cultist",
    "demon": "Demon",
    "devil": "Devil",
    "dragon": "Dragon",
    "elemental": "Elemental",
    "ghoul": "Ghoul",
    "giant": "Giant",
    "gnoll": "Gnoll",
    "goblin": "Goblin",
    "golem": "Golem",
    "hobgoblin": "Hobgoblin",
    "kobold": "Kobold",
    "ogre": "Ogre",
    "orc": "Orc",
    "skeleton": "Skeleton",
    "specter": "Specter",
    "spider": "Spider",
    "troll": "Troll",
    "vampire": "Vampire",
    "wight": "Wight",
    "wolf": "Wolf",
    "wraith": "Wraith",
    "zombie": "Zombie",
}
_WEAPON_DIE_SIDES = {
    "battleaxe": 8,
    "club": 4,
    "dagger": 4,
    "dart": 4,
    "flail": 8,
    "glaive": 10,
    "greataxe": 12,
    "greatclub": 8,
    "greatsword": 6,
    "halberd": 10,
    "hand crossbow": 6,
    "handaxe": 6,
    "heavy crossbow": 10,
    "javelin": 6,
    "lance": 12,
    "light crossbow": 8,
    "light hammer": 4,
    "longbow": 8,
    "longsword": 8,
    "mace": 6,
    "maul": 6,
    "morningstar": 8,
    "pike": 10,
    "quarterstaff": 6,
    "rapier": 8,
    "scimitar": 6,
    "shortbow": 6,
    "shortsword": 6,
    "sickle": 4,
    "sling": 4,
    "spear": 6,
    "trident": 6,
    "war pick": 8,
    "warhammer": 8,
    "whip": 4,
}
_VERSATILE_WEAPON_DIE_SIDES = {
    "battleaxe": {8, 10},
    "longsword": {8, 10},
    "quarterstaff": {6, 8},
    "spear": {6, 8},
    "trident": {6, 8},
    "warhammer": {8, 10},
}
_FLAT_DAMAGE_WEAPONS = {"blowgun", "net"}


class _CompressionValidationError(ValueError):
    """Internal error carrying a safe explanation for rejected compression."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise _CompressionValidationError(message)


def _strip_player_suffix(name: str) -> str:
    """Remove source role annotations while preserving the character name."""
    normalized = name.strip()
    role_suffix = r"\s*\((?:player|npc|ally|enemy|neutral)\)\s*$"
    while re.search(role_suffix, normalized, flags=re.IGNORECASE):
        normalized = re.sub(
            role_suffix, "", normalized, flags=re.IGNORECASE
        ).strip()
    return normalized


def _section(source: str, heading: str, end_headings: Tuple[str, ...]) -> str:
    start_match = re.search(
        rf"(?m)^\s*{re.escape(heading)}\s*$", source
    )
    _require(start_match is not None, f"source is missing {heading}")
    start = start_match.end()
    end = len(source)
    for end_heading in end_headings:
        match = re.search(
            rf"(?m)^\s*{re.escape(end_heading)}.*$", source[start:]
        )
        if match is not None:
            end = min(end, start + match.start())
    return source[start:end].strip()


def extract_player_action(source: str) -> str:
    """Return the reversible one-line payload represented by ``@ACTION``."""
    section = _section(
        source,
        "--- PLAYER ACTION ---",
        ("--- REQUIRED RESPONSE ---",),
    )
    action = section.replace("\r\n", "\n").replace("\r", "\n").strip()
    _require(bool(action), "source player action is empty")
    return action.replace("\\", "\\\\").replace("\n", "\\n")


def _split_top_level(value: str) -> List[str]:
    """Split comma-delimited tag data without splitting nested lists/maps."""
    if not value.strip():
        return []
    parts = []
    start = 0
    square_depth = 0
    brace_depth = 0
    for index, character in enumerate(value):
        if character == "[":
            square_depth += 1
        elif character == "]":
            square_depth -= 1
        elif character == "{":
            brace_depth += 1
        elif character == "}":
            brace_depth -= 1
        _require(square_depth >= 0 and brace_depth >= 0, "unbalanced tag data")
        if character == "," and square_depth == 0 and brace_depth == 0:
            part = value[start:index].strip()
            _require(bool(part), "empty tag list entry")
            parts.append(part)
            start = index + 1
    _require(square_depth == 0 and brace_depth == 0, "unbalanced tag data")
    final = value[start:].strip()
    _require(bool(final), "empty tag list entry")
    parts.append(final)
    return parts


def _list_body(value: str, tag: str) -> str:
    _require(
        value.startswith("[") and value.endswith("]"),
        f"@{tag} must be a bracketed list",
    )
    return value[1:-1].strip()


def _parse_int_list(value: str, context: str) -> List[int]:
    if not value.strip():
        return []
    numbers = []
    for item in value.split(","):
        item = item.strip()
        _require(re.fullmatch(r"-?\d+", item) is not None, f"bad {context} value")
        numbers.append(int(item))
    return numbers


def _parse_tags(compressed: str) -> Dict[str, str]:
    _require(isinstance(compressed, str), "compressed output is not text")
    lines = compressed.strip().splitlines()
    _require(bool(lines), "compressed output is empty")
    _require(lines[0].strip() == "@T=CS/v2", "first tag must be @T=CS/v2")
    tags = {}
    known_tags = _REQUIRED_COMPRESSION_TAGS | _OPTIONAL_COMPRESSION_TAGS
    for raw_line in lines:
        line = raw_line.strip()
        _require(line.startswith("@") and "=" in line, "output contains non-tag text")
        tag, value = line[1:].split("=", 1)
        _require(tag in known_tags, f"unknown @{tag} tag")
        _require(tag not in tags, f"duplicate @{tag} tag")
        tags[tag] = value.strip()
    missing = sorted(_REQUIRED_COMPRESSION_TAGS - set(tags))
    _require(not missing, f"missing required tags: {', '.join(missing)}")
    _require(tags["T"] == "CS/v2", "wrong compression version")
    return tags


def _parse_source_round(source: str) -> int:
    rounds = [
        int(value)
        for value in re.findall(r"(?mi)^\s*combat_round\s*:\s*(\d+)\s*$", source)
    ]
    _require(bool(rounds), "source has no combat round")
    _require(len(set(rounds)) == 1, "source has conflicting combat rounds")
    return rounds[0]


def _parse_source_player(source: str) -> str:
    players = [
        _strip_player_suffix(value)
        for value in re.findall(r"(?mi)^\s*player_name\s*:\s*(.+?)\s*$", source)
    ]
    _require(bool(players), "source has no player name")
    _require(len(set(players)) == 1, "source has conflicting player names")
    _require(bool(players[0]), "source player name is empty")
    return players[0]


def _parse_tracker(source: str) -> Dict[str, Dict[str, object]]:
    tracker_section = _section(
        source,
        "--- LIVE TRACKER ---",
        ("--- NAME HINTS ---", "--- CREATURE STATES ---"),
    )
    tracker = {}
    pattern = re.compile(
        r"^\s*-\s*\[([^\]]*)\]\s*(?:\*\*)?(.+?)\s+\((-?\d+)\)"
        r"(?:\*\*)?\s*-\s*(.+?)(?:\*\*)?\s*$",
        flags=re.IGNORECASE,
    )
    for line in tracker_section.splitlines():
        match = pattern.match(line)
        if match is None:
            continue
        marker, raw_name, initiative_text, raw_state = match.groups()
        name = _strip_player_suffix(raw_name)
        state_text = raw_state.strip().lower().replace(" ", "_")
        if "d" in marker.lower() or state_text in {"dead", "defeated"}:
            state = "dead"
        elif "x" in marker.lower() or state_text.startswith("acted"):
            state = "acted"
        elif state_text.startswith("after_player"):
            state = "after_player"
        else:
            state = "waiting"
        initiative = int(initiative_text)
        existing = tracker.get(name)
        if existing is not None:
            _require(
                existing["initiative"] == initiative,
                f"source tracker has conflicting initiative for {name}",
            )
            if _STATUS_PRECEDENCE[state] > _STATUS_PRECEDENCE[existing["status"]]:
                existing["status"] = state
        else:
            tracker[name] = {"initiative": initiative, "status": state}
    _require(bool(tracker), "source live tracker has no actors")
    return tracker


def _parse_source_process(
    source: str, player: str, tracker: Dict[str, Dict[str, object]]
) -> List[Tuple[str, int]]:
    current = re.search(
        r"(?mi)^\s*>>>\s*CURRENT:\s*(.+?)\s+\((-?\d+)\)\s*-\s*"
        r"PLAYER TURN\b",
        source,
    )
    if current is not None:
        name = _strip_player_suffix(current.group(1))
        initiative = int(current.group(2))
        _require(name == player, "source current player does not match player_name")
        _require(name in tracker, "source current player is absent from tracker")
        _require(
            tracker[name]["initiative"] == initiative,
            "source current-player initiative conflicts with tracker",
        )
        return [(name, initiative)]

    process_block = re.search(
        r"(?ms)^\s*>>>\s*PROCESS ALL OF THESE[^\n]*\n(.*?)"
        r"(?=^\s*>>>\s*THEN STOP AT:)",
        source,
    )
    if process_block is not None:
        process = []
        for raw_name, initiative_text in re.findall(
            r"(?m)^\s*-\s*(.+?)\s+\((-?\d+)\)\s*$",
            process_block.group(1),
        ):
            name = _strip_player_suffix(raw_name)
            initiative = int(initiative_text)
            _require(name in tracker, f"source process actor {name} is absent from tracker")
            _require(
                tracker[name]["initiative"] == initiative,
                f"source process initiative conflicts for {name}",
            )
            _require(tracker[name]["status"] != "dead", "source processes a dead actor")
            process.append((name, initiative))
        _require(bool(process), "source process block is empty")
        _require(
            len({name for name, _ in process}) == len(process),
            "source process block contains duplicate actors",
        )
        return process

    end_round_block = re.search(
        r"(?ms)^\s*>>>\s*PROCESS TO END ROUND:\s*\n(.*?)"
        r"(?=^\s*>>>\s*THEN:\s*End Round\b)",
        source,
    )
    if end_round_block is not None:
        process = []
        for raw_name, initiative_text in re.findall(
            r"(?m)^\s*-\s*(.+?)\s+\((-?\d+)\)\s*$",
            end_round_block.group(1),
        ):
            name = _strip_player_suffix(raw_name)
            initiative = int(initiative_text)
            _require(name in tracker, f"source process actor {name} is absent from tracker")
            _require(
                tracker[name]["initiative"] == initiative,
                f"source process initiative conflicts for {name}",
            )
            _require(tracker[name]["status"] != "dead", "source processes a dead actor")
            process.append((name, initiative))
        _require(bool(process), "source end-round process block is empty")
        _require(
            len({name for name, _ in process}) == len(process),
            "source end-round process block contains duplicate actors",
        )
        return process

    if re.search(r"(?mi)^\s*>>>\s*ROUND COMPLETE\s*$", source):
        process = [
            (name, int(data["initiative"]))
            for name, data in tracker.items()
            if data["status"] == "acted"
        ]
        _require(bool(process), "round-complete source has no acted actors")
        return process
    raise _CompressionValidationError("source has no supported process marker")


def _parse_source_states(source: str) -> Dict[str, Dict[str, object]]:
    state_section = _section(
        source,
        "--- CREATURE STATES ---",
        ("=== ARMOR CLASS", "--- DICE POOLS ---"),
    )
    states = {}
    pattern = re.compile(
        r"^\s*(.+?)\s*:\s*HP\s*(-?\d+)\s*/\s*(\d+)\s*,\s*"
        r"(alive|dead)\b(.*)$",
        flags=re.IGNORECASE,
    )
    for line in state_section.splitlines():
        match = pattern.match(line)
        if match is None:
            continue
        raw_name, current_text, maximum_text, life_state, remainder = match.groups()
        name = _strip_player_suffix(raw_name)
        current = int(current_text)
        maximum = int(maximum_text)
        _require(maximum > 0, f"source has invalid maximum HP for {name}")
        slots = {}
        slot_match = re.search(r"Spell Slots\s*:\s*(.*)$", remainder, re.IGNORECASE)
        if slot_match is not None:
            for level_text, slot_current, slot_maximum in re.findall(
                r"L(\d+)\s*:\s*(\d+)\s*/\s*(\d+)", slot_match.group(1)
            ):
                level = int(level_text)
                slot_value = (int(slot_current), int(slot_maximum))
                _require(
                    slot_value[1] > 0 and 0 <= slot_value[0] <= slot_value[1],
                    f"invalid source L{level} slot for {name}",
                )
                _require(level not in slots, f"duplicate source L{level} slot for {name}")
                slots[level] = slot_value
        _require(name not in states, f"duplicate source creature state for {name}")
        states[name] = {
            "hp": (current, maximum),
            "alive": life_state.lower() == "alive",
            "slots": slots,
        }
    _require(bool(states), "source has no creature states")
    return states


def _parse_source_attacks(source: str) -> Dict[str, Dict[str, object]]:
    attack_header = "=== CREATURE ATTACKS (exact number per creature) ==="
    try:
        attack_section = _section(
            source,
            attack_header,
            ("=== SAVING THROWS ===", "--- RULES ---", "--- PLAYER ACTION ---"),
        )
    except _CompressionValidationError:
        return {}
    attacks = {}
    for line in attack_section.splitlines():
        match = re.match(r"^\s*(.+?)\s*:\s*(.*)$", line)
        if match is None or match.group(1).startswith("[PLAYER"):
            continue
        name = _strip_player_suffix(match.group(1))
        description = match.group(2).strip()
        rolls = [int(value) for value in re.findall(r"Attack\[(-?\d+)\]", description)]
        if rolls:
            _require(name not in attacks, f"duplicate source attack pool for {name}")
            attacks[name] = {"rolls": rolls, "description": description}
    return attacks


def _parse_source_saves(source: str) -> Dict[str, Tuple[Tuple[str, int], ...]]:
    try:
        save_section = _section(
            source,
            "=== SAVING THROWS ===",
            ("IMPORTANT:", "COMBAT TRACKING:", "--- RULES ---", "--- PLAYER ACTION ---"),
        )
    except _CompressionValidationError:
        return {}
    saves = {}
    for line in save_section.splitlines():
        match = re.match(r"^\s*(.+?)\s*:\s*(STR\s*:.*)$", line, re.IGNORECASE)
        if match is None:
            continue
        name = _strip_player_suffix(match.group(1))
        values = []
        for ability_value in match.group(2).split(","):
            ability_match = re.fullmatch(
                r"\s*(STR|DEX|CON|INT|WIS|CHA)\s*:\s*(-?\d+)\s*",
                ability_value,
                re.IGNORECASE,
            )
            if ability_match is None:
                values = []
                break
            values.append((ability_match.group(1).upper(), int(ability_match.group(2))))
        if tuple(ability for ability, _ in values) != _SAVE_ABILITIES:
            continue
        if not all(1 <= roll <= 20 for _, roll in values):
            continue
        _require(name not in saves, f"duplicate source saving-throw pool for {name}")
        saves[name] = tuple(values)
    return saves


def _parse_source_dice(source: str) -> Dict[int, List[int]]:
    generic_header = "=== GENERIC DICE (use for spells, abilities, improvisation) ==="
    generic_section = _section(
        source,
        generic_header,
        ("=== CREATURE ATTACKS", "=== SAVING THROWS", "--- RULES ---"),
    )
    dice = {}
    for sides_text, values_text in re.findall(
        r"\bd(\d+)\s*:\s*\[([^\]]*)\]", generic_section
    ):
        sides = int(sides_text)
        _require(sides not in dice, f"duplicate source d{sides} pool")
        dice[sides] = _parse_int_list(values_text, f"source d{sides}")
    _require(bool(dice), "source has no generic dice pools")
    return dice


def _parse_source_name_hints(source: str) -> Dict[str, str]:
    try:
        hints_section = _section(
            source,
            "--- NAME HINTS ---",
            ("--- CREATURE STATES ---",),
        )
    except _CompressionValidationError:
        return {}
    hints = {}
    for line in hints_section.splitlines():
        name, separator, hint = line.partition(":")
        if separator and name.strip() and hint.strip():
            hints[_strip_player_suffix(name)] = hint.strip()
    return hints


def _normalized_type(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _infer_obvious_actor_type(canonical: str) -> Optional[str]:
    without_number = re.sub(r"_\d+$", "", canonical).strip()
    words = re.findall(r"[A-Za-z]+", without_number)
    if not words:
        return None
    first_word = words[0].lower()
    if len(words) > 1 and first_word in _CANONICAL_TITLE_TYPES:
        return _CANONICAL_TITLE_TYPES[first_word]
    for word in reversed(words):
        if word.lower() in _OBVIOUS_MONSTER_TYPES:
            return _OBVIOUS_MONSTER_TYPES[word.lower()]
    if re.search(r"_\d+$", canonical):
        return without_number.replace("_", " ").title()
    return None


def _infer_source_role(source: str, canonical: str, hint: str) -> Optional[set]:
    label_match = re.search(
        rf"{re.escape(canonical)}\s*\((ally|enemy|npc|neutral)\)",
        source,
        re.IGNORECASE,
    )
    if label_match is not None:
        label = label_match.group(1).lower()
        if label == "npc":
            return {"ally", "neutral"}
        return {label}

    ally_hint = re.search(
        r"\b(ally|allied|friendly|companion|party|adventurer)\b",
        hint,
        re.IGNORECASE,
    )
    enemy_hint = re.search(
        r"\b(enemy|hostile|foe|monster|outlaw|raider|undead|attacker|opponent)\b",
        hint,
        re.IGNORECASE,
    )
    if ally_hint and not enemy_hint:
        return {"ally"}
    if enemy_hint and not ally_hint:
        return {"enemy"}
    obvious_type = _infer_obvious_actor_type(canonical)
    if obvious_type and _normalized_type(obvious_type) in {
        _normalized_type(value) for value in _OBVIOUS_MONSTER_TYPES.values()
    }:
        return {"enemy"}
    if re.search(r"_\d+$", canonical) and obvious_type:
        return {"enemy"}
    return None


def _validate_roster_source_metadata(
    source: str,
    source_player: str,
    roster: Dict[str, Dict[str, str]],
) -> None:
    hints = _parse_source_name_hints(source)
    for data in roster.values():
        canonical = data["canonical"]
        if canonical == source_player:
            continue
        inferred_type = _infer_obvious_actor_type(canonical)
        if inferred_type is not None:
            _require(
                _normalized_type(data["type"]) == _normalized_type(inferred_type),
                f"@ROSTER type for {canonical} conflicts with source identity",
            )
        allowed_roles = _infer_source_role(source, canonical, hints.get(canonical, ""))
        if allowed_roles is not None:
            _require(
                data["role"] in allowed_roles,
                f"@ROSTER role for {canonical} conflicts with source identity",
            )


def _parse_roster(value: str) -> Tuple[Dict[str, Dict[str, str]], Dict[str, str]]:
    roster = {}
    canonical_to_id = {}
    for entry in _split_top_level(_list_body(value, "ROSTER")):
        parts = [part.strip() for part in entry.split(":", 3)]
        _require(len(parts) == 4, "malformed @ROSTER entry")
        actor_id, role, actor_type, raw_canonical = parts
        canonical = _strip_player_suffix(raw_canonical)
        _require(bool(actor_id) and bool(actor_type) and bool(canonical), "empty @ROSTER field")
        _require(
            role in {"player", "ally", "enemy", "neutral"},
            f"invalid @ROSTER role for {actor_id}",
        )
        _require(actor_id not in roster, f"duplicate @ROSTER id {actor_id}")
        _require(canonical not in canonical_to_id, f"duplicate @ROSTER actor {canonical}")
        roster[actor_id] = {
            "role": role,
            "type": actor_type,
            "canonical": canonical,
        }
        canonical_to_id[canonical] = actor_id
    _require(bool(roster), "@ROSTER is empty")
    return roster, canonical_to_id


def _canonical_id(actor_id: str, roster: Dict[str, Dict[str, str]], context: str) -> str:
    _require(actor_id in roster, f"{context} id {actor_id} is absent from @ROSTER")
    return roster[actor_id]["canonical"]


def _parse_process(
    value: str, roster: Dict[str, Dict[str, str]]
) -> List[Tuple[str, int]]:
    process = []
    seen_ids = set()
    for entry in _split_top_level(_list_body(value, "PROCESS")):
        match = re.fullmatch(r"(.+):(-?\d+)", entry)
        _require(match is not None, "malformed @PROCESS entry")
        actor_id, initiative_text = match.groups()
        actor_id = actor_id.strip()
        _require(actor_id not in seen_ids, f"duplicate @PROCESS id {actor_id}")
        seen_ids.add(actor_id)
        process.append(
            (_canonical_id(actor_id, roster, "@PROCESS"), int(initiative_text))
        )
    return process


def _parse_status(
    value: str, roster: Dict[str, Dict[str, str]]
) -> Dict[str, List[str]]:
    groups = {}
    all_ids = set()
    for group_text in _split_top_level(value):
        match = re.fullmatch(r"(acted|dead|after_player|waiting)\[([^\[\]]*)\]", group_text)
        _require(match is not None, "malformed @STATUS group")
        group, body = match.groups()
        _require(group not in groups, f"duplicate @STATUS {group} group")
        raw_ids = body.split(",") if body else []
        _require(all(item.strip() for item in raw_ids), f"empty id in @STATUS {group}")
        ids = [item.strip() for item in raw_ids]
        _require(len(ids) == len(set(ids)), f"duplicate id within @STATUS {group}")
        for actor_id in ids:
            _require(actor_id not in all_ids, f"@STATUS id {actor_id} is in multiple groups")
            all_ids.add(actor_id)
        groups[group] = [
            _canonical_id(actor_id, roster, "@STATUS") for actor_id in ids
        ]
    _require(set(groups) == set(_STATUS_GROUPS), "@STATUS must contain all four groups")
    return groups


def _parse_hp(
    value: str, roster: Dict[str, Dict[str, str]]
) -> Dict[str, Tuple[int, int]]:
    hp = {}
    for entry in _split_top_level(_list_body(value, "HP")):
        match = re.fullmatch(r"(.+):(-?\d+)/(\d+)", entry)
        _require(match is not None, "malformed @HP entry")
        actor_id, current_text, maximum_text = match.groups()
        canonical = _canonical_id(actor_id.strip(), roster, "@HP")
        _require(canonical not in hp, f"duplicate @HP actor {canonical}")
        current, maximum = int(current_text), int(maximum_text)
        _require(maximum > 0 and current <= maximum, f"invalid @HP value for {canonical}")
        hp[canonical] = (current, maximum)
    return hp


def _parse_attacks(
    value: str, roster: Dict[str, Dict[str, str]]
) -> Dict[str, List[int]]:
    attacks = {}
    for entry in _split_top_level(_list_body(value, "ATK")):
        match = re.fullmatch(r"(.+):\[([^\[\]]*)\]", entry)
        _require(match is not None, "malformed @ATK entry")
        actor_id, values_text = match.groups()
        canonical = _canonical_id(actor_id.strip(), roster, "@ATK")
        _require(canonical not in attacks, f"duplicate @ATK actor {canonical}")
        attacks[canonical] = _parse_int_list(values_text, f"@ATK for {canonical}")
    return attacks


def _attack_option_die_sides(option: str) -> Tuple[set, bool]:
    sides = {
        int(value)
        for value in re.findall(r"(?i)(?:\d+)?d(\d+)", option)
    }
    lowered = option.lower()
    recognized = bool(sides)
    for weapon, versatile_sides in _VERSATILE_WEAPON_DIE_SIDES.items():
        if re.search(rf"\b{re.escape(weapon)}\b", lowered):
            sides.update(versatile_sides)
            recognized = True
    for weapon, weapon_sides in _WEAPON_DIE_SIDES.items():
        if weapon in _VERSATILE_WEAPON_DIE_SIDES:
            continue
        if re.search(rf"\b{re.escape(weapon)}\b", lowered):
            sides.add(weapon_sides)
            recognized = True
    if any(re.search(rf"\b{re.escape(weapon)}\b", lowered) for weapon in _FLAT_DAMAGE_WEAPONS):
        recognized = True
    return sides, recognized


def _attack_option_selected_by_action(option: str, action: str) -> bool:
    lowered_option = option.lower()
    lowered_action = action.lower()
    weapon_names = (
        set(_WEAPON_DIE_SIDES)
        | set(_VERSATILE_WEAPON_DIE_SIDES)
        | _FLAT_DAMAGE_WEAPONS
    )
    for weapon in weapon_names:
        weapon_pattern = rf"\b{re.escape(weapon)}\b"
        if re.search(weapon_pattern, lowered_option) and re.search(
            weapon_pattern, lowered_action
        ):
            return True
    option_dice = {
        int(value) for value in re.findall(r"(?i)(?:\d+)?d(\d+)", option)
    }
    action_dice = {
        int(value) for value in re.findall(r"(?i)(?:\d+)?d(\d+)", action)
    }
    return bool(option_dice & action_dice)


def _derive_relevant_dice(
    source: str,
    process_actors: List[str],
    source_player: str,
    source_attacks: Dict[str, Dict[str, object]],
    source_dice: Dict[int, List[int]],
) -> set:
    relevant_sides = set()
    action = extract_player_action(source)
    for actor in process_actors:
        if actor == source_player:
            continue
        _require(actor in source_attacks, f"source has no attack details for {actor}")
        description = source_attacks[actor]["description"]
        option_match = re.search(
            r"attacks? available\s*:\s*(.*)\)\s*$",
            description,
            re.IGNORECASE,
        )
        _require(
            option_match is not None and bool(option_match.group(1).strip()),
            f"source cannot determine relevant damage dice for {actor}",
        )
        options = [option.strip() for option in option_match.group(1).split(",")]
        _require(all(options), f"source has malformed attack options for {actor}")
        if _action_mentions_actor(source, actor):
            selected_options = [
                option
                for option in options
                if _attack_option_selected_by_action(option, action)
            ]
            if selected_options:
                options = selected_options
        for option in options:
            option_sides, recognized = _attack_option_die_sides(option)
            _require(
                recognized,
                f"source cannot determine damage dice for {actor} option {option}",
            )
            relevant_sides.update(option_sides)
    missing_pools = sorted(relevant_sides - set(source_dice))
    _require(
        not missing_pools,
        "source lacks required generic dice pools: "
        + ", ".join(f"d{sides}" for sides in missing_pools),
    )
    return relevant_sides


def build_compression_source_hints(source: str) -> str:
    """Return deterministic, source-derived constraints for the model call.

    The model still produces the compact identity mapping and tag block. Values
    that the validator can derive without inference are stated explicitly so a
    provider does not have to guess about round advancement or weapon dice.
    """
    hints = [
        "DETERMINISTIC COMPRESSION CONSTRAINTS (copied from the source):",
        (
            "@STATUS must use exactly "
            "acted[...],dead[...],after_player[...],waiting[...] with no "
            "equals signs inside the groups."
        ),
    ]
    try:
        source_round = _parse_source_round(source)
        hints.append(
            f"@ROUND must be exactly {source_round}; do not increment it while "
            "compressing."
        )
    except _CompressionValidationError:
        pass

    try:
        source_player = _parse_source_player(source)
        tracker = _parse_tracker(source)
        roster_types = [
            f"{actor}={actor_type}"
            for actor in tracker
            if actor != source_player
            for actor_type in [_infer_obvious_actor_type(actor)]
            if actor_type is not None
        ]
        if roster_types:
            hints.append(
                "@ROSTER must use these source-derived canonical actor types "
                "exactly (descriptive NAME HINTS do not override them): "
                + ", ".join(roster_types)
                + "."
            )
        process = _parse_source_process(source, source_player, tracker)
        source_attacks = _parse_source_attacks(source)
        source_dice = _parse_source_dice(source)
        relevant_sides = _derive_relevant_dice(
            source,
            [actor for actor, _initiative in process],
            source_player,
            source_attacks,
            source_dice,
        )
        if relevant_sides:
            required = ", ".join(f"d{sides}" for sides in sorted(relevant_sides))
            hints.append(
                f"@DICE must contain exactly these families: {required}; copy "
                "each listed pool prefix from the source."
            )
        else:
            hints.append("@DICE must be exactly {} because no NPC damage die is needed.")
        forbidden = sorted(set(source_dice) - relevant_sides)
        if forbidden:
            hints.append(
                "Do not include "
                + ", ".join(f"d{sides}" for sides in forbidden)
                + " in @DICE."
            )
    except _CompressionValidationError:
        hints.append(
            "The validator could not derive an exact @DICE set; do not guess "
            "or invent damage dice."
        )

    hints.append(
        "Omit optional @SAVES unless this segment explicitly consumes a saving "
        "throw; if included, preserve the source actor and ability order exactly."
    )
    return "\n".join(hints)


def _parse_dice(
    value: str,
    source_dice: Dict[int, List[int]],
    relevant_sides: set,
) -> Dict[int, List[int]]:
    _require(value.startswith("{") and value.endswith("}"), "@DICE must be a map")
    dice = {}
    for entry in _split_top_level(value[1:-1].strip()):
        match = re.fullmatch(r"d(\d+):\[([^\[\]]*)\]", entry)
        _require(match is not None, "malformed @DICE entry")
        sides = int(match.group(1))
        _require(sides >= 2, "invalid @DICE die")
        _require(sides not in dice, f"duplicate @DICE d{sides} pool")
        values = _parse_int_list(match.group(2), f"@DICE d{sides}")
        _require(bool(values), f"@DICE d{sides} pool is empty")
        _require(
            all(1 <= roll <= sides for roll in values),
            f"@DICE d{sides} contains an out-of-bounds value",
        )
        _require(sides in source_dice, f"@DICE d{sides} is absent from source")
        _require(
            values == source_dice[sides][: len(values)],
            f"@DICE d{sides} does not preserve the source pool order",
        )
        dice[sides] = values
    _require(
        set(dice) == relevant_sides,
        "@DICE families must exactly match source-relevant process attacks",
    )
    return dice


def _parse_slots(
    value: str, roster: Dict[str, Dict[str, str]]
) -> Dict[Tuple[str, int], Tuple[int, int]]:
    slots = {}
    for entry in _split_top_level(_list_body(value, "SLOTS")):
        match = re.fullmatch(r"(.+):L(\d+):(\d+)/(\d+)", entry)
        _require(match is not None, "malformed @SLOTS entry")
        actor_id, level_text, current_text, maximum_text = match.groups()
        canonical = _canonical_id(actor_id.strip(), roster, "@SLOTS")
        key = (canonical, int(level_text))
        _require(key not in slots, f"duplicate @SLOTS value for {canonical} L{level_text}")
        current, maximum = int(current_text), int(maximum_text)
        _require(
            maximum > 0 and 0 <= current < maximum,
            f"@SLOTS contains a non-partial slot for {canonical} L{level_text}",
        )
        slots[key] = (current, maximum)
    return slots


def _action_mentions_actor(source: str, canonical: str) -> bool:
    action = extract_player_action(source)
    return re.search(
        rf"(?<![A-Za-z0-9_]){re.escape(canonical)}(?![A-Za-z0-9_])",
        action,
        re.IGNORECASE,
    ) is not None


def _validate_optional_tags(
    tags: Dict[str, str],
    roster: Dict[str, Dict[str, str]],
    source: str,
    source_player: str,
    process_actors: List[str],
    source_saves: Dict[str, Tuple[Tuple[str, int], ...]],
) -> None:
    if "BRIEF" in tags:
        # Envelope validation only: BRIEF is never interpreted or merged into
        # any authoritative combat field.
        _require(bool(tags["BRIEF"]), "@BRIEF is empty")
        _require(len(tags["BRIEF"].split()) <= 25, "@BRIEF exceeds 25 words")
        _require("@" not in tags["BRIEF"], "@BRIEF cannot contain tag syntax")
        _require(
            "\\n" not in tags["BRIEF"] and "\\r" not in tags["BRIEF"],
            "@BRIEF cannot contain encoded line breaks",
        )
    if "SAVES" in tags:
        saves_body = _list_body(tags["SAVES"], "SAVES")
        _require(bool(saves_body), "@SAVES must be omitted when no saves are needed")
        saves = {}
        actor_order = []
        for entry in saves_body.split(";"):
            actor_id, separator, values = entry.strip().partition(":")
            _require(separator == ":" and bool(values), "malformed @SAVES entry")
            canonical = _canonical_id(actor_id.strip(), roster, "@SAVES")
            _require(canonical != source_player, "player cannot consume a source @SAVES pool")
            _require(canonical not in saves, f"duplicate @SAVES actor {canonical}")
            parsed_values = []
            for ability_value in values.split(","):
                match = re.fullmatch(
                    r"(STR|DEX|CON|INT|WIS|CHA):(-?\d+)", ability_value.strip()
                )
                _require(match is not None, "malformed @SAVES ability")
                parsed_values.append((match.group(1), int(match.group(2))))
            _require(
                tuple(ability for ability, _ in parsed_values) == _SAVE_ABILITIES,
                "@SAVES abilities must preserve source order",
            )
            _require(canonical in source_saves, f"source has no usable @SAVES pool for {canonical}")
            _require(
                tuple(parsed_values) == source_saves[canonical],
                f"@SAVES values differ from source pool for {canonical}",
            )
            actor_needed = (
                canonical in process_actors
                or _action_mentions_actor(source, canonical)
            )
            _require(actor_needed, f"@SAVES actor {canonical} is not needed this segment")
            saves[canonical] = tuple(parsed_values)
            actor_order.append(canonical)
        expected_order = [actor for actor in source_saves if actor in saves]
        _require(actor_order == expected_order, "@SAVES actors must preserve source order")


def validate_combat_compression(source: str, compressed: str) -> Tuple[bool, str]:
    """Validate a T017 tag block against the combat source it represents."""
    try:
        _require(isinstance(source, str) and bool(source.strip()), "source is empty")
        tags = _parse_tags(compressed)
        source_round = _parse_source_round(source)
        source_player = _parse_source_player(source)
        tracker = _parse_tracker(source)
        states = _parse_source_states(source)
        source_process = _parse_source_process(source, source_player, tracker)
        source_attacks = _parse_source_attacks(source)
        source_saves = _parse_source_saves(source)
        source_dice = _parse_source_dice(source)

        _require(re.fullmatch(r"\d+", tags["ROUND"]) is not None, "@ROUND is not an integer")
        _require(int(tags["ROUND"]) == source_round, "@ROUND differs from source")
        _require(tags["PLAYER"] == source_player, "@PLAYER differs from source")
        _require(tags["STOP"] == source_player, "@STOP must exactly equal @PLAYER")
        explicit_stop = re.search(r"(?mi)^\s*>>>\s*THEN STOP AT:\s*(.+?)\s*$", source)
        if explicit_stop is not None:
            stop_name = _strip_player_suffix(explicit_stop.group(1))
            _require(stop_name == source_player, "source stop marker conflicts with player")
        _require(tags["ACTION"] == extract_player_action(source), "@ACTION differs from source")
        _require(tags["RULES"] == _RULES_VALUE, "@RULES has the wrong contract value")

        roster, canonical_to_id = _parse_roster(tags["ROSTER"])
        _require(
            set(canonical_to_id) == set(tracker),
            "@ROSTER actors must exactly match the source tracker",
        )
        player_ids = [
            actor_id
            for actor_id, data in roster.items()
            if data["role"] == "player"
        ]
        _require(len(player_ids) == 1, "@ROSTER must contain exactly one player role")
        _require(
            roster[player_ids[0]]["canonical"] == source_player,
            "@ROSTER player role differs from source player",
        )
        _validate_roster_source_metadata(source, source_player, roster)

        process = _parse_process(tags["PROCESS"], roster)
        _require(process == source_process, "@PROCESS differs from source turn order")

        status = _parse_status(tags["STATUS"], roster)
        expected_status = {
            group: {
                name for name, data in tracker.items() if data["status"] == group
            }
            for group in _STATUS_GROUPS
        }
        for group in _STATUS_GROUPS:
            _require(
                set(status[group]) == expected_status[group],
                f"@STATUS {group} differs from source tracker",
            )
        player_status_count = sum(
            source_player in status[group] for group in _STATUS_GROUPS
        )
        _require(player_status_count == 1, "@PLAYER must appear in exactly one @STATUS group")

        for actor in tracker:
            _require(actor in states, f"source is missing creature state for {actor}")
            tracker_dead = tracker[actor]["status"] == "dead"
            _require(
                states[actor]["alive"] != tracker_dead,
                f"source tracker and creature state disagree for {actor}",
            )
        expected_hp = {
            actor: states[actor]["hp"]
            for actor in tracker
            if states[actor]["alive"] or actor == source_player
        }
        hp = _parse_hp(tags["HP"], roster)
        _require(hp == expected_hp, "@HP differs from living source creature states")

        attacks = _parse_attacks(tags["ATK"], roster)
        process_actors = [actor for actor, _ in process]
        _require(
            set(attacks) == set(process_actors),
            "@ATK actors must exactly match @PROCESS actors",
        )
        for actor in process_actors:
            if actor == source_player:
                _require(attacks[actor] == [], "player @ATK pool must be empty")
            else:
                _require(actor in source_attacks, f"source has no attack pool for {actor}")
                _require(
                    attacks[actor] == source_attacks[actor]["rolls"],
                    f"@ATK does not preserve source pool for {actor}",
                )

        relevant_dice = _derive_relevant_dice(
            source,
            process_actors,
            source_player,
            source_attacks,
            source_dice,
        )
        _parse_dice(tags["DICE"], source_dice, relevant_dice)

        expected_slots = {}
        for actor in tracker:
            for level, (current, maximum) in states[actor]["slots"].items():
                if 0 <= current < maximum:
                    expected_slots[(actor, level)] = (current, maximum)
        if expected_slots:
            _require("SLOTS" in tags, "@SLOTS is required for partially used source slots")
        slots = _parse_slots(tags.get("SLOTS", "[]"), roster)
        _require(slots == expected_slots, "@SLOTS differs from partial source slots")

        _validate_optional_tags(
            tags,
            roster,
            source,
            source_player,
            process_actors,
            source_saves,
        )
        return True, "valid"
    except _CompressionValidationError as exc:
        return False, str(exc)
    except Exception as exc:
        return False, f"malformed compression: {exc}"

class CombatCompressor:
    """Production combat message compressor for historical context."""
    
    def __init__(self, enable_caching: bool = True):
        """Initialize compressor."""
        from model_config import MODEL_PROVIDER
        self._provider = MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            self._config = config.COMBAT_COMPRESS_GPT5MINI_LOW
        elif MODEL_PROVIDER == "gemini":
            self._config = config.COMBAT_COMPRESS_GEMINI_FLASH_LOW
        elif MODEL_PROVIDER == "lmstudio":
            self._config = config.COMBAT_COMPRESS_LMSTUDIO
        else:  # legacy
            self._config = config.COMBAT_COMPRESS_LEGACY

        self.enable_caching = enable_caching
        self.cache_file = Path("modules/conversation_history/combat_compression_cache.json")
        self.cache_lock = threading.RLock()
        self.cache = self._load_cache() if enable_caching else {}
    
    def _load_cache(self) -> Dict[str, str]:
        """Load compression cache."""
        return read_json_mapping(self.cache_file)
    
    def _save_cache(self, updates=None, remove_keys=()):
        """Merge cache changes without erasing entries from other workers."""
        if self.enable_caching:
            with self.cache_lock:
                self.cache = merge_json_mapping(
                    self.cache_file,
                    updates=updates,
                    remove_keys=remove_keys,
                )
    
    def _get_content_hash(self, content: str) -> str:
        """Key by content plus the provider/model/prompt contract."""
        payload = json.dumps(
            {
                "version": "combat-compression-v3-source-hints",
                "provider": self._provider,
                "model": self._config["model"],
                "prompt": hashlib.sha256(
                    COMBAT_COMPRESSION_PROMPT.encode("utf-8")
                ).hexdigest(),
                "content": content,
            },
            sort_keys=True,
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def validate_compression(self, content: str, compressed: str) -> Tuple[bool, str]:
        """Apply the same source-aware contract at every cache boundary."""
        return validate_combat_compression(content, compressed)
    
    def compress(self, content: str) -> str:
        """Compress combat message content."""
        # Check cache
        if self.enable_caching:
            content_hash = self._get_content_hash(content)
            with self.cache_lock:
                cached_value = self.cache.get(content_hash)
            if cached_value is not None:
                valid, reason = self.validate_compression(content, cached_value)
                if valid:
                    return cached_value
                print(f"[WARNING] Removing invalid combat compression cache entry: {reason}")
                self._save_cache(remove_keys=(content_hash,))
        
        try:
            messages = [
                {"role": "system", "content": COMBAT_COMPRESSION_PROMPT},
                {"role": "user", "content": content},
                {
                    "role": "user",
                    "content": build_compression_source_hints(content),
                },
            ]
            compressed = None
            last_reason = "unknown validation failure"
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                print(
                    f"[DEBUG] Calling AI compression with model: "
                    f"{self._config['model']} (attempt {attempt}/{max_attempts})"
                )
                response = capture_and_fanout(
                    "T017",
                    api_client.create_completion,
                    _request_provider=self._provider,
                    messages=messages,
                    model=self._config["model"],
                    temperature=0.3,
                    **{k: v for k, v in self._config.items() if k != "model"},
                )

                if USAGE_TRACKING_AVAILABLE:
                    try:
                        track_response(response)
                    except Exception:
                        pass

                candidate = response.choices[0].message.content.strip()
                if candidate.startswith("```"):
                    candidate = re.sub(
                        r"^```.*?\n|```$",
                        "",
                        candidate,
                        flags=re.MULTILINE,
                    ).strip()

                valid, last_reason = self.validate_compression(content, candidate)
                if valid:
                    compressed = candidate
                    break

                print(
                    f"[ERROR] AI returned invalid combat compression on attempt "
                    f"{attempt}: {last_reason}"
                )
                if attempt < max_attempts:
                    messages.extend(
                        [
                            {"role": "assistant", "content": candidate},
                            {
                                "role": "user",
                                "content": (
                                    "VALIDATION ERROR: "
                                    f"{last_reason}. Regenerate the complete tag "
                                    "block from the original source. Preserve every "
                                    "source value exactly and obey the required "
                                    "grammar; output tags only.\n"
                                    + build_compression_source_hints(content)
                                ),
                            },
                        ]
                    )

            if compressed is None:
                print(
                    "[ERROR] Combat compression validation exhausted retries: "
                    f"{last_reason}"
                )
                return content
            
            # Validate compression actually reduced size
            if len(compressed) >= len(content):
                print(f"[WARNING] Compression didn't reduce size: {len(content)} -> {len(compressed)}")
                # Still cache if format is valid but size didn't reduce
            
            # Cache result ONLY if valid compression
            if self.enable_caching:
                content_hash = self._get_content_hash(content)
                self._save_cache(updates={content_hash: compressed})
                print(f"[DEBUG] Cached compressed content: {len(content)} -> {len(compressed)} chars")
            
            return compressed
            
        except Exception as e:
            # Log the error for debugging
            print(f"[ERROR] Combat compression failed: {e}")
            print(f"[ERROR] Model: {self._config['model']}")
            print(f"[ERROR] Content length: {len(content)} chars")
            
            # Check if it's an API key issue
            if "api_key" in str(e).lower() or "authentication" in str(e).lower():
                print(f"[ERROR] API key issue detected - check OPENAI_API_KEY")
            elif "rate" in str(e).lower():
                print(f"[ERROR] Rate limit issue - compression will be skipped")
            
            # DO NOT cache failed compressions!
            # Return original without caching
            return content

def compress_combat_message(content: str) -> str:
    """Simple function to compress a combat message."""
    compressor = CombatCompressor()
    return compressor.compress(content)

# Integration point for combat_manager.py
def should_compress_message(message: Dict) -> bool:
    """Check if a message should be compressed."""
    if message.get("role") != "user":
        return False
    
    content = message.get("content", "")
    
    # Look for combat round markers
    return ("--- ROUND INFO ---" in content and 
            "--- CREATURE STATES ---" in content and
            "--- DICE POOLS ---" in content)

def compress_combat_history(conversation_history: list) -> list:
    """Compress combat messages in conversation history."""
    compressor = CombatCompressor()
    compressed_history = []
    
    for message in conversation_history:
        if should_compress_message(message):
            # Compress this combat message
            compressed_content = compressor.compress(message["content"])
            compressed_history.append({
                "role": message["role"],
                "content": compressed_content
            })
        else:
            # Keep as-is
            compressed_history.append(message)
    
    return compressed_history

if __name__ == "__main__":
    from datetime import datetime
    
    # EXACT user message from actual game
    sample = """--- ROUND INFO ---
combat_round: 2
player_name: Eirik Hearthwise
--- ROUND INFO ---
combat_round: 2
player_name: Eirik Hearthwise (player)

--- LIVE TRACKER ---
**Live Initiative Tracker:**
- [D] Skeleton_3 (20) - Dead
- [X] Scout Elen (20) - Acted
- [D] Skeleton (18) - Dead
- [ ] Skeleton_5 (18) - Waiting
- [ ] Skeleton_2 (14) - Waiting
- [ ] Ranger Thane (12) - Waiting
- [ ] Skeleton_4 (6) - Waiting
- [ ] Eirik Hearthwise (player) (5) - Waiting
- [ ] Scout Kira (4) - Waiting

>>> PROCESS ALL OF THESE IN ONE RESPONSE (Initiative Order):
- Skeleton_5 (18)
- Skeleton_2 (14)
- Ranger Thane (12)
- Skeleton_4 (6)
>>> THEN STOP AT: Eirik Hearthwise (player) (Player)

- [ ] Scout Kira (4) - After Player

--- NAME HINTS ---
Skeleton_2: the nearly destroyed skeleton (HP 1/13)
Skeleton_5: the uninjured skeleton (HP 13/13)
Skeleton_4: the wounded skeleton (HP 9/13)
Scout Elen: bloodied party scout (HP 29/36)
Scout Kira: party archer
Ranger Thane: party ranger

--- CURRENT TURN ---
See initiative tracker above

--- CREATURE STATES ---
Eirik Hearthwise: HP 45/45, alive, Spell Slots: L1:2/4 L2:2/3 L3:2/2
Skeleton: HP -3/13, dead
Skeleton_2: HP 1/13, alive
Skeleton_3: HP -1/13, dead
Skeleton_4: HP 9/13, alive
Skeleton_5: HP 13/13, alive
Scout Kira: HP 45/45, alive
Scout Elen: HP 29/36, alive, Spell Slots: L1:3/4 L2:2/2
Ranger Thane: HP 55/55, alive, Spell Slots: L1:4/4 L2:2/2

--- DICE POOLS ---
Rules:
- Player characters always roll their own dice
- NPCs/monsters use pre-rolled dice pools exactly
- Do not reuse dice; consume in order
- For NPC/Monster ATTACK: use CREATURE ATTACKS list
- For NPC/Monster SAVES: use SAVING THROWS list  
- For damage/spells/other: use GENERIC DICE pool

DM Note: COMBAT ROUND 2 - DICE AVAILABLE:
Preroll Set ID: 2-4036 (Generated at round start)

CRITICAL DICE USAGE:
- For NPC/Monster ATTACKS, you MUST use a die from the "CREATURE ATTACKS" list for that specific creature.
- For NPC/Monster SAVING THROWS, you MUST use a die from the "SAVING THROWS" list.
- The "GENERIC DICE" pool is ONLY for damage rolls, spell effects, or other non-attack/non-save rolls.
- FAILURE TO USE THE CORRECT POOL IS A CRITICAL ERROR.

=== GENERIC DICE (use for spells, abilities, improvisation) ===
d4: [3,1,4,3,2,4,1,1] | d6: [4,2,3,3,2,3,5,3] | d8: [4,1,3,6,2,1] | d10: [1,3,2,7,1,6] | d12: [5,3,12,3] | d20: [2,20,1,15,11,12,2,8,11,1]

=== CREATURE ATTACKS (exact number per creature) ===
[PLAYER: Eirik Hearthwise] Must make own rolls
Skeleton: Attack[15], Attack[5] (2 attacks available: Shortsword, Shortbow)
Skeleton_2: Attack[3], Attack[9] (2 attacks available: Shortsword, Shortbow)
Skeleton_3: Attack[18], Attack[15] (2 attacks available: Shortsword, Shortbow)
Skeleton_4: Attack[10], Attack[11] (2 attacks available: Shortsword, Shortbow)
Skeleton_5: Attack[14], Attack[17] (2 attacks available: Shortsword, Shortbow)
Scout Kira: Attack[7] (1 attack available: Shortbow Shot)
Scout Elen: Attack[5], Attack[1] (2 attacks available: Longbow, Shortsword)
Ranger Thane: Attack[8], Attack[14] (2 attacks available: Longbow, Shortsword)

=== SAVING THROWS ===
Skeleton: STR:11, DEX:9, CON:1, INT:8, WIS:12, CHA:9
Skeleton_2: STR:20, DEX:6, CON:8, INT:1, WIS:20, CHA:13
Skeleton_3: STR:6, DEX:19, CON:17, INT:13, WIS:9, CHA:11
Skeleton_4: STR:17, DEX:2, CON:7, INT:4, WIS:19, CHA:12
Skeleton_5: STR:19, DEX:8, CON:15, INT:6, WIS:12, CHA:12
Scout Kira: STR:15, DEX:1, CON:16, INT:3, WIS:10, CHA:15
Scout Elen: STR:5, DEX:10, CON:18, INT:7, WIS:15, CHA:6
Ranger Thane: STR:17, DEX:13, CON:18, INT:18, WIS:18, CHA:7

IMPORTANT: Each creature can only make the number of attacks listed above.
Use generic dice pool for damage rolls, spells, and other abilities.
Apply all appropriate modifiers (ability scores, proficiency, weapon bonuses, etc.).
Note: Eirik Hearthwise must make their own rolls.

COMBAT TRACKING: You MUST include "combat_round" field in your JSON response.
Track combat rounds: increment ONLY when ALL alive creatures have completed their turns in initiative order.
These dice remain constant throughout the current round.

--- RULES ---
- Initiative must be followed strictly
- Only increment combat_round after all alive creatures have acted
- Status updates must be reflected in JSON "actions"
- Do not narrate beyond current round

--- PLAYER ACTION ---
Im ready, let's do this!

--- REQUIRED RESPONSE ---
1. Narrate and resolve actions for all NPCs/monsters in initiative order until:
   - The LAST creature in this round has acted, OR
   - Initiative returns to the player
2. Stop narration at that point
3. Return structured JSON with plan, narration, combat_round, and actions"""
    
    print("Testing combat compression...")
    print(f"Original: {len(sample)} chars")
    
    compressed = compress_combat_message(sample)
    print(f"\nCompressed:\n{compressed}")
    print(f"\nCompressed: {len(compressed)} chars")
    print(f"Reduction: {(1 - len(compressed)/len(sample))*100:.1f}%")
    
    # Save to file for review
    output_file = "combat_compression_final_output.json"
    results = {
        "timestamp": datetime.now().isoformat(),
        "model": NARRATIVE_COMPRESSION_MODEL,
        "original": {
            "content": sample,
            "length": len(sample)
        },
        "compressed": {
            "content": compressed,
            "length": len(compressed)
        },
        "reduction": {
            "chars_saved": len(sample) - len(compressed),
            "percent": (1 - len(compressed)/len(sample))*100,
            "ratio": len(sample)/len(compressed) if len(compressed) > 0 else 0
        }
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n[SAVED] Full output saved to: {output_file}")