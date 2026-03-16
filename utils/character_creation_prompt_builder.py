# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Character Creation Prompt Builder
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Shared prompt/context builder for DM-driven character creation.
Supports startup and mid-campaign adapters with one canonical contract.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import json
import os
from typing import Any, Dict, List

from utils.file_operations import safe_read_json
from utils.encoding_utils import safe_json_load
from utils.enhanced_logger import error


# Experience points required for each level (minimum)
XP_BY_LEVEL = {
    1: 0,
    2: 300,
    3: 900,
    4: 2700,
    5: 6500,
    6: 14000,
    7: 23000,
    8: 34000,
    9: 48000,
    10: 64000,
    11: 85000,
    12: 100000,
    13: 120000,
    14: 140000,
    15: 165000,
    16: 195000,
    17: 225000,
    18: 265000,
    19: 305000,
    20: 355000,
}


def _get_wealth_guidance_text(target_level: int) -> str:
    """Return deterministic wealth guidance text for higher-level joins."""
    if target_level <= 2:
        return "STARTING EQUIPMENT: Use standard class starting equipment plus background gear. No additional gold."
    if target_level <= 4:
        gp = {3: 150, 4: 375}.get(target_level, 150)
        return f"STARTING EQUIPMENT: Standard gear plus {gp}gp for additional equipment."
    if target_level <= 7:
        gp = {5: 650, 6: 900, 7: 1200}.get(target_level, 650)
        return f"STARTING EQUIPMENT: Standard gear plus {gp}gp. Consider uncommon magic items."
    if target_level <= 10:
        gp = {8: 1650, 9: 2250, 10: 3000}.get(target_level, 1650)
        return f"STARTING EQUIPMENT: Standard gear plus {gp}gp. Should have rare magic items (2-3)."
    if target_level <= 14:
        gp = {11: 4000, 12: 5250, 13: 6750, 14: 8750}.get(target_level, 4000)
        return f"STARTING EQUIPMENT: Standard gear plus {gp}gp. Should have very rare items (3-4)."
    gp = {15: 11250, 16: 14500, 17: 18750, 18: 24250, 19: 31250, 20: 40000}.get(target_level, 11250)
    return f"STARTING EQUIPMENT: Standard gear plus {gp}gp. Should have legendary items (4-5)."


def _load_text_file(file_path: str) -> str:
    """Load text content with fail-open empty-string fallback."""
    try:
        with open(file_path, "r", encoding="utf-8") as file_handle:
            return file_handle.read().strip()
    except Exception:
        return ""


def _strip_template_header(template_text: str) -> str:
    """Strip leading comment/blank lines before prompt delivery."""
    template_lines = template_text.splitlines()
    while template_lines:
        current_line = template_lines[0].strip()
        if not current_line or current_line.startswith("#"):
            template_lines.pop(0)
            continue
        break
    return "\n".join(template_lines).strip()


def _get_recent_summary() -> str:
    """Read bounded recent summary from conversation history when available."""
    recent_summary = "The adventure continues..."
    try:
        summary_file = "modules/conversation_history/conversation_history.json"
        if os.path.exists(summary_file):
            history = safe_read_json(summary_file)
            if history and isinstance(history, list):
                for message in reversed(history):
                    if isinstance(message, dict):
                        content = str(message.get("content", ""))
                        if "=== LOCATION SUMMARY ===" in content or "=== MODULE SUMMARY ===" in content:
                            return content[:500] + "..." if len(content) > 500 else content
    except Exception:
        pass
    return recent_summary


def _build_startup_system_prompt() -> str:
    """Build startup-mode canonical system prompt aligned with startup wizard behavior."""
    schema = safe_json_load("schemas/char_schema.json")
    if not schema:
        schema = {}

    leveling_info = _load_text_file("prompts/leveling/leveling_info.txt")
    npc_rules = _load_text_file("prompts/generators/npc_builder_prompt.txt")

    base_system_content = (
        "You are a friendly and knowledgeable character creation guide for 5th edition fantasy adventures, "
        "using only SRD 5.2.1-compliant rules. You help players build their 1st-level characters step by step "
        "by asking questions, offering helpful choices, and reflecting their answers clearly. You do not assume "
        "anything without asking. You do not create the character sheet until the player explicitly confirms "
        "their choices.\n\n"
        "You will eventually output a finalized character sheet in a JSON format matching the provided schema, "
        "but ONLY after the player says they are ready.\n\n"
        "You MUST:\n"
        "1. Engage the player in a brief conversation to learn what kind of character they want to play "
        "(fantasy archetype, theme, race, class, personality, etc).\n"
        "2. Ask targeted follow-up questions to flesh out their background, class, abilities, race, and goals.\n"
        "3. Present summaries of each part of the character as it becomes clear, so the player can confirm or revise.\n"
        "4. Once the player explicitly confirms all choices and says they are ready, then and ONLY then, proceed "
        "to create the character using the provided JSON schema.\n\n"
        "NEVER output the final JSON unless the player says they are ready. If you're unsure of a choice, ask. "
        "Focus on helping the player make decisions they're excited about. Encourage fun, story-driven, "
        "rules-compliant choices. Keep it immersive, but not overwhelming."
    )

    return (
        f"{base_system_content}\n\n"
        "IMPORTANT FORMATTING RULES:\n"
        "- Do NOT use emojis or special characters in any responses\n"
        "- Write in plain text only\n"
        "- When generating the final JSON, use ONLY standard ASCII characters\n"
        "- Do NOT include any Unicode characters, emojis, or special symbols\n"
        "- Keep all text responses clean and readable without special formatting\n\n"
        "Use the following SRD 5.2.1 rules information when helping create the character:\n\n"
        "LEVELING INFORMATION:\n"
        f"{leveling_info}\n\n"
        "RACE AND CLASS RULES:\n"
        f"{npc_rules}\n\n"
        "JSON OUTPUT REQUIREMENTS:\n"
        "When the player confirms they are ready to finalize their character, you MUST respond with ONLY "
        "a valid JSON object that matches the provided character schema exactly.\n\n"
        "SKILL PROFICIENCY REQUIREMENTS:\n"
        "- The \"skills\" field MUST be an array of skill names, NOT an object with bonuses\n"
        "- Format example: [\"Athletics\", \"Perception\", \"Stealth\", \"Arcana\"]\n"
        "- Include ONLY skills the character is proficient in\n"
        "- During the interview, help the player select:\n"
        "  * Background skills (each background grants 2 specific skills)\n"
        "  * Class skills (number varies by class - Fighter: 2, Rogue: 4, Ranger: 3, Bard: 3, etc.)\n"
        "- Present skill choices naturally during character creation conversation\n"
        "- Example: \"As a Fighter, you can choose 2 skills from: Acrobatics, Animal Handling, Athletics, "
        "History, Insight, Intimidation, Perception, or Survival. What skills would fit your character?\"\n\n"
        "CRITICAL JSON FORMATTING RULES:\n"
        "- Use ONLY standard ASCII characters in the JSON\n"
        "- No emojis, Unicode symbols, or special characters anywhere in the JSON\n"
        "- No markdown formatting or additional text - just the raw JSON\n"
        "- All string values must use only plain text\n"
        "- Ensure all required schema fields are populated\n"
        "- Use proper JSON syntax with correct quotes and brackets\n"
        "- The \"skills\" field MUST be an array format: [\"Skill1\", \"Skill2\"]\n\n"
        "The character must be level 1 and have experience_points set to 0.\n"
        "The character should be marked as character_role: \"player\" and character_type: \"player\".\n"
        "All required schema fields must be populated appropriately.\n\n"
        "CHARACTER SCHEMA:\n"
        f"{json.dumps(schema, indent=2)}"
    )


def _build_mid_campaign_system_prompt(
    module_name: str,
    character_name: str,
    level: int,
    party_tracker: Dict[str, Any],
    is_mid_campaign: bool,
    active_pc: str,
    current_location: str,
) -> str:
    """Build mid-campaign prompt text from the shared template contract."""
    prompt_file = "prompts/character_creation/dm_interview_prompt.txt"

    if not os.path.exists(prompt_file):
        return (
            f"[SYSTEM] A new player '{character_name}' is joining the table at Level {level}! "
            "Please guide them through 5e character creation. "
            "Ask for Race, Class, Background, Ability Scores, Skills, Equipment, and Personality. "
            "When complete, output the full character as JSON."
        )

    try:
        template = _load_text_file(prompt_file)
        template = _strip_template_header(template)
    except Exception as prompt_error:
        error(f"Failed to load character creation prompt template: {prompt_error}")
        return (
            f"[SYSTEM] A new player '{character_name}' is joining the table at Level {level}! "
            "Please guide them through 5e character creation."
        )

    world = party_tracker.get("worldConditions", {})
    party_members = party_tracker.get("partyMembers", [])
    existing_members = [
        member_name
        for member_name in party_members
        if member_name.lower().replace(" ", "_") != character_name.lower().replace(" ", "_")
    ]

    xp_for_level = XP_BY_LEVEL.get(level, 0)
    xp_next = XP_BY_LEVEL.get(level + 1, XP_BY_LEVEL[20]) if level < 20 else 0

    level_context = (
        f"\nCHARACTER LEVEL: {level}\n"
        f"EXPERIENCE POINTS: {xp_for_level} (minimum for level {level})\n"
        f"EXPERIENCE FOR NEXT LEVEL: {xp_next}\n"
    )

    if is_mid_campaign and level > 1:
        level_context += f"\n{_get_wealth_guidance_text(level)}"

    mid_campaign_context = ""
    if is_mid_campaign:
        member_text = ", ".join(existing_members) if existing_members else "no one yet"
        context_location = current_location or world.get("currentLocation", "the current location")
        mid_campaign_context = (
            "\nMID-CAMPAIGN ADDITION:\n"
            f"This character is joining an ongoing adventure. The party currently consists of: {member_text}.\n\n"
            f"{active_pc} is currently the active party member at {context_location}.\n\n"
            "CONNECTION OPPORTUNITY:\n"
            f"During creation, ask if {character_name} recognizes any existing party members from their past "
            "(friend, rival, former comrade, etc.) or if they are a complete stranger. "
            "This will be woven into their entrance narrative.\n\n"
            "IMPORTANT: This character is NOT exhausted, injured, or debilitated. "
            "They are fresh and ready for adventure at full capacity.\n"
        )

    try:
        return template.format(
            character_name=character_name,
            module_name=module_name,
            location_name=current_location or world.get("currentLocation", "the current location"),
            area_name=world.get("currentArea", "the current area"),
            party_members=", ".join(existing_members) if existing_members else "none yet",
            level=level,
            experience_points=xp_for_level,
            exp_next=xp_next,
            recent_summary=_get_recent_summary(),
            level_context=level_context,
            mid_campaign_context=mid_campaign_context,
            active_pc=active_pc or "The party",
        )
    except Exception as format_error:
        error(f"Failed to format character creation prompt template: {format_error}")
        existing_party_text = ", ".join(existing_members) if existing_members else "none yet"
        return (
            f"You are a friendly and knowledgeable character creation guide for 5th edition fantasy adventures. "
            f"Help create '{character_name}' for the {module_name} adventure at level {level}. "
            f"Current location: {current_location or world.get('currentLocation', 'the current location')}. "
            f"Existing party members: {existing_party_text}. "
            "Ask one question at a time, guide the player through race, class, background, abilities, skills, "
            "equipment, personality, and backstory, and only output a complete JSON character sheet when the "
            "player says they are ready to finalize. "
            f"Set experience_points to {xp_for_level} and exp_required_for_next_level to {xp_next}."
        )


def build_dm_creation_prompt_bundle(
    mode: str,
    module_name: str,
    character_name: str,
    level: int = 1,
    party_tracker: Dict[str, Any] = None,
    is_mid_campaign: bool = False,
    active_pc: str = "",
    current_location: str = "",
) -> Dict[str, str]:
    """Build canonical prompt bundle for startup and mid-campaign DM creation adapters."""
    if party_tracker is None:
        party_tracker = {}

    normalized_mode = str(mode or "").strip().lower()
    if normalized_mode not in {"startup", "mid_campaign"}:
        raise ValueError(f"Unsupported creation prompt mode: {mode}")

    if normalized_mode == "startup":
        module_display_name = module_name or "the current adventure"
        startup_system_prompt = _build_startup_system_prompt()
        kickoff_user_prompt = (
            "You are helping a new player create their first level 1 character for the "
            f"{module_display_name} adventure. Welcome them to the adventure, set an immersive tone that brings "
            "them into the game world, and begin the character creation process. Start by finding out what kind "
            "of hero they want to become. Use phrases like 'Let's get you started by finding out a little bit "
            "about you' to engage them in the process."
        )
        return {
            "system_prompt": startup_system_prompt,
            "kickoff_user_prompt": kickoff_user_prompt,
        }

    mid_campaign_system_prompt = _build_mid_campaign_system_prompt(
        module_name=module_name,
        character_name=character_name,
        level=level,
        party_tracker=party_tracker,
        is_mid_campaign=is_mid_campaign,
        active_pc=active_pc,
        current_location=current_location,
    )
    return {
        "system_prompt": mid_campaign_system_prompt,
        "kickoff_user_prompt": "",
    }


__all__: List[str] = [
    "build_dm_creation_prompt_bundle",
]
