#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""
Location module compression for RPG game
Compresses location JSON into compact structured format
"""

import json
import re
from typing import Dict, Any, List, Optional
from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T085", "utils/compression/location_compressor.py", 297)

# Import token tracking
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except:
    USAGE_TRACKING_AVAILABLE = False
    def track_response(r): pass  # No-op fallback

# Location Compression System Prompt
LOCATION_SYSTEM_PROMPT = """
PRIORITY RULES (read these FIRST, they override everything):

1. NEVER FABRICATE DATA. If an array (doors[], dcChecks[], lootTable[], plotHooks[]) does not
   exist in the source JSON, output {} for that table. If a word like "aid" or "guidance"
   appears in narrative text but is NOT a spell being cast or a spell item, do NOT put it in @S.
   Only include spells that are actually CAST or appear as SPELL ITEMS (scrolls, potions).

2. PARTY MEMBERS ARE NOT NPCs. Characters who are adventurers traveling with the player
   (typically described as companions, party members, or PCs) must NOT appear in @C or @NPCROLES.
   Only characters who WORK at or LIVE in this location get entries.

3. EXTRACT ALL DATA. Do not skip entries. Every door in doors[], every check in dcChecks[],
   every item in lootTable[], every hook in plotHooks[] must appear in its table.

4. ONE ENTRY PER ENTITY. Never create two @C entries for the same person. If "The Keeper"
   and "Keeper Morvath" refer to the same person, use ONE entry with the canonical first name.

You are a specialized COMPRESSION AGENT for RPG location modules.
Your ONLY job is to:
1. Analyze the provided LOCATION JSON (rooms, taverns, garrisons, etc.).
2. Extract ALL gameplay-critical data (NPCs, features, doors, connectivity, area links, traps/hazards, DC checks, loot, plot hooks).
3. Output a SINGLE compressed block in the required schema:
   - @C,@L,@S,@I,@R (characters, locations, spells, items, relations).
   - Location tables: @F,@TRANS,@DOORS,@DC,@LOOT,@HOOKS,@HAZ,@AREA,@NPCROLES.
   - EVT[...] beats.

Strict rules:
- You are NOT a storyteller. You do NOT expand into prose. 
- You do NOT invent new content outside what is implied in the JSON.
- You MUST output all tables. If the JSON has entries, the corresponding table MUST NOT be empty. {} is allowed only if the source has no data.
- CRITICAL: @DOORS, @DC, @LOOT, @HOOKS, @S tables MUST be empty {} if NO corresponding array exists in the source JSON. Do NOT infer or fabricate entries. Only @HAZ may contain inferred hazards.
- @C MUST use numeric IDs (1,2,3...) mapped to canonical names without role prefixes
- @NPCROLES MUST be populated if NPCs exist - map each NPC's ID to their role (elder, captain, proprietor, innkeep, etc.)
- @S MUST include all mentioned spells with numeric IDs if any spells appear in the JSON
- Beats (EVT) are short, numbered, agentic summaries of player/NPC action flow in this location. Each beat = 1 main action + optional short natural-language clause.
- Always maintain schema format exactly (no missing tables, no extra tables).

Role of this AI:
- Act as a schema compressor: reduce verbosity, preserve fidelity, never omit gameplay-critical information.
- Think of yourself as a "lossless filter" between verbose source JSON and a compact structured block for live game runtime.
- Narrow scope: only output schema + beats. Nothing else.

Table Schema and Tokenization Rules:

@C={1:Name,2:Name,...}        # NUMERIC sequential IDs. Canonical = first name only ("Eirik" not "Eirik Hearthwise", "Kira" not "Scout Kira"). One entry per person -- never duplicate. Party members excluded.
@L={1:location_slug,2:location_slug,...}  # NUMERIC sequential IDs mapped to slugified names. NOT source room IDs. NOT prefixed IDs.
@S={id:spell_name,...}        # ALL spells mentioned (Aid, Guidance, etc.) NEVER empty if spells exist
@I={item_tokens,...}          # Items: compact tokens (silver_tankard_10gp)
@R={romance:(id1,id2),party:(ids)} # Relationships: include romance if bond beats exist

@F={feature_tokens,...}       # ALL features[] as tokens
@TRANS={[to:location_slug,dir:?],...} # Extract from ALL map.rooms[].connections. If directions not explicit in source, use dir:?. Do NOT fabricate directions.
@DOORS={[slug:type,locked:y/n,lock:DC,break:DC,key:slug,trap:slug|-],...} # ALL doors[] with complete data
@DC={[check_slug:DC_number],...}  # ONLY from explicit dcChecks[] with numeric values. If a check has multiple DCs for different conditions, include ALL variants. No placeholders.
@LOOT={item_tokens,...}       # ALL lootTable[] items as compact tokens
@HOOKS={quest_tokens,...}     # ONLY from explicit plotHooks[] array. Do NOT infer from narrative. If no plotHooks[] exists, output @HOOKS={}
@HAZ={hazard_tokens,...}      # Inferred hazards (secret_trapdoor, cult_symbols, hostile_proprietor)
@AREA={roomId:room_slug,...}  # Map EVERY room from map.rooms to its slugified name. Use source room IDs as keys (B01, A01).
@NPCROLES={id:role,...}       # REQUIRED: Map NPC IDs to roles. Party members/adventurers NOT listed. Only NPCs with functional roles in this location.

Tokenization:
• Slugify: lowercase → replace non-alphanumerics with "_" → trim "_" → collapse repeats
• Examples: "Bone Wind-Chimes" → "bone_wind_chimes", "Silver Tankard (10gp)" → "silver_tankard_10gp"
• Keep entries terse: 1–3 tokens where possible

Self-check before final output:
- Are ALL NPCs from npcs[] present in @C with CANONICAL names (no role prefixes)?
- Are @NPCROLES populated for ALL non-party NPCs (elder, captain, proprietor, innkeep)? NEVER leave empty if NPCs exist.
- Are ALL features[] present in @F as tokens?
- Are ALL doors[] present in @DOORS with correct lock/break/trap fields?
- Are ALL connections present in @TRANS and areaConnectivity in @AREA?
- Are ALL dcChecks[] present in @DC?
- Are ALL lootTable[] entries present in @LOOT?
- Are ALL plotHooks[] present in @HOOKS?
- Are hazards inferred (@HAZ) when cues exist (e.g., trapdoor, cult, hostile)?
- If spells are mentioned in encounters (Aid, Guidance, Bless, etc.), are they in @S? NEVER leave @S empty if spells exist.
- Is there at least one social beat (meet/rest) and one prep/tension beat?
- Did you include romance:(ID1,ID2) in @R if bond cues are present?
- Did you produce a single well-formed EVT[...] block?
- Is @AREA formatted as {areaId:area_slug} with the slug filled?
- Does @TRANS use location slugs (ad02) not area IDs (Z06)?
- Character names MUST be canonical: "Kira" not "Scout Kira", "Thane" not "Ranger Thane"

If ANY of these are missing, REPAIR and re-emit before returning.

Beats (EVT) format:
• Number each beat: 1) 2) 3) etc.
• Format: "n) <marker> <action> with:<ids>. [Optional short description.]"
• Markers use the NUMERIC ID from your @L table:
  @L<n> = at location n (e.g., @L1, @L3)
  ->L<n> = move to location n (e.g., ->L2)
  <-L<n> = return from location n
• "with:<ids>" uses @C numeric IDs. If no specific NPCs, omit "with:" entirely.
• Actions: meet, rest, prep, tension, bond, trade, cast
• Include at least one social beat and one readiness/tension beat
• End every beat with a period

COMPLETE OUTPUT EXAMPLE (follow this format EXACTLY):

@C={1:Grimjaw,2:Elen,3:Morvath}
@L={1:entrance_hall,2:guard_room,3:ritual_chamber}
@S={1:Sacred_Flame,2:Cure_Wounds}
@I={rusty_key,silver_pendant_5gp,healing_potion}
@R={party:(2,3)}

@F={crumbling_pillars,bloodstained_altar,flickering_torches}
@TRANS={[to:guard_room,dir:north],[to:ritual_chamber,dir:east]}
@DOORS={[guard_room_door:reinforced,locked:y,lock:15,break:18,key:rusty_key,trap:-]}
@DC={[perception_notice_tracks:12],[investigation_search_desk:14]}
@LOOT={rusty_key,silver_pendant_5gp,scroll_of_protection,20gp}
@HOOKS={investigate_disappearances,find_missing_scout}
@HAZ={unstable_ceiling,poison_gas_trap}
@AREA={B01:entrance_hall,B02:guard_room,B03:ritual_chamber}
@NPCROLES={1:warden,3:hermit}

EVT[
1) @L1 meet with:2. Scout briefs party on dangers ahead.
2) ->L2 tension. Party encounters locked guard room door.
3) @L3 prep with:1,3. Grimjaw reveals ritual requirements.
]

FORMAT NOTES:
- @DOORS uses [slug:type,locked:y/n,lock:DC,break:DC,key:slug,trap:slug|-] NOT JSON objects
- @DC uses [check_slug:DC_number] NOT JSON objects
- This is TOKEN FORMAT, not JSON. Do NOT output {"key":"value"} JSON objects in any table.
- @I lists items AVAILABLE IN THE LOCATION (loot, shop items, quest items), NOT character inventory.
- EVT must have at MINIMUM one beat per room in @L. Each beat should reference the room's key mechanic.
"""


_REQUIRED_LOCATION_TABLES = (
    "C", "L", "S", "I", "R", "F", "TRANS", "DOORS", "DC", "LOOT",
    "HOOKS", "HAZ", "AREA", "NPCROLES",
)
_SOURCE_TABLE_RULES = {
    "npcs": ("C", "NPCROLES"),
    "features": ("F",),
    "doors": ("DOORS",),
    "dcChecks": ("DC",),
    "lootTable": ("LOOT",),
    "plotHooks": ("HOOKS",),
    "rooms": ("L", "AREA"),
    "connections": ("TRANS",),
}


def _source_array_counts(value: Any) -> Dict[str, int]:
    """Count explicit source arrays recursively without inferring narrative data."""
    counts = {key: 0 for key in _SOURCE_TABLE_RULES}

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                if key in counts and isinstance(child, list):
                    counts[key] += len(child)
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    return counts


def validate_location_compression_output(
    location_json_str: str, response_text: str
) -> str:
    """Validate T085's exact block contract and explicit-array fidelity rules."""
    if not isinstance(response_text, str) or not response_text.strip():
        raise ValueError("T085 returned an empty compression")

    text = response_text.strip()
    if "```" in text:
        raise ValueError("T085 returned a code fence after normalization")

    evt_match = re.search(r"(?m)^EVT\[\s*$", text)
    if not evt_match or not text.endswith("]"):
        raise ValueError("T085 response is missing a terminal EVT block")

    table_text = text[:evt_match.start()]
    table_lines = [line.strip() for line in table_text.splitlines() if line.strip()]
    if len(table_lines) != len(_REQUIRED_LOCATION_TABLES):
        raise ValueError("T085 response has missing or extra table lines")

    table_values: Dict[str, str] = {}
    for expected, line in zip(_REQUIRED_LOCATION_TABLES, table_lines):
        match = re.fullmatch(r"@([A-Z]+)=(.+)", line)
        if not match or match.group(1) != expected:
            raise ValueError(f"T085 expected @{expected} in canonical table order")
        value = match.group(2).strip()
        if not value.startswith("{") or not value.endswith("}"):
            raise ValueError(f"T085 @{expected} must be a brace-delimited table")
        table_values[expected] = value

    evt_body = text[evt_match.end():-1].strip()
    beats = [line.strip() for line in evt_body.splitlines() if line.strip()]
    if not beats or any(not re.match(r"^\d+\)\s+", beat) for beat in beats):
        raise ValueError("T085 EVT must contain only numbered beats")

    try:
        source = json.loads(location_json_str)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ValueError(f"T085 source is not valid JSON: {exc}") from exc
    counts = _source_array_counts(source)

    for source_key, tables in _SOURCE_TABLE_RULES.items():
        has_entries = counts[source_key] > 0
        for table in tables:
            is_empty = table_values[table] == "{}"
            if has_entries and is_empty:
                raise ValueError(
                    f"T085 @{table} omitted explicit {source_key} entries"
                )
            if (
                source_key in {"doors", "dcChecks", "lootTable", "plotHooks"}
                and not has_entries
                and not is_empty
            ):
                raise ValueError(
                    f"T085 @{table} fabricated data absent from {source_key}"
                )

    room_count = counts["rooms"]
    if room_count and len(beats) < room_count:
        raise ValueError("T085 EVT has fewer beats than explicit rooms")

    return text

def compress_location(location_json_str: str, max_retries: int = 2) -> Optional[str]:
    """
    Compress location JSON using GPT model with validation and retries
    
    Args:
        location_json_str: JSON string of location data
        max_retries: Maximum number of retry attempts
    
    Returns:
        Compressed location string or None if failed
    """
    
    attempts = 0
    
    while attempts <= max_retries:
        try:
            # Build message with format requirements
            example_format = """CRITICAL FORMAT REQUIREMENTS:
@C must use format: {1:Firstname,2:Othername} NOT {1:Title_Firstname,2:Role_Name}
@L must use numeric IDs and slugified names: {1:entrance_hall,2:guard_room}
@S must include ONLY spells actually CAST or appearing as spell ITEMS (scrolls, potions). Do NOT include narrative words like "aid" or "guidance" that are not spells.
@R must include romance if bond beats exist: {romance:(id1,id2),party:(ids)}
@NPCROLES maps NPC IDs to roles: {1:elder,2:captain,4:proprietor}
Party members (adventurers) must NOT appear in @C or @NPCROLES.

Remove ALL role prefixes: "Kira" not "Scout_Kira", "Dorun" not "Elder_Dorun", "Thane" not "Ranger_Thane"

"""
            user_message = f"{example_format}This is a LOCATION MODULE requiring all location tables. Compress this location data:\n\n{location_json_str}"
            
            # Select model config per provider
            from model_config import MODEL_PROVIDER
            if MODEL_PROVIDER == "openai":
                compress_config = config.LOC_COMPRESS_GPT52_NONE
            elif MODEL_PROVIDER == "gemini":
                compress_config = config.LOC_COMPRESS_GEMINI_PRO_LOW
            elif MODEL_PROVIDER == "lmstudio":
                compress_config = config.LOC_COMPRESS_LMSTUDIO
            else:  # legacy
                compress_config = config.LOC_COMPRESS_LEGACY

            response = capture_and_fanout("T085", api_client.create_completion, messages=[
                    {"role": "system", "content": LOCATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                _request_provider=MODEL_PROVIDER,
                model=compress_config["model"],
                temperature=0.1,
                **{k: v for k, v in compress_config.items() if k != "model"})
            
            # Track token usage
            if USAGE_TRACKING_AVAILABLE:
                try:
                    track_response(response)
                except:
                    pass  # Silently ignore tracking errors
            
            # Extract response
            response_text = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                response_text = re.sub(r'^```[a-z]*\n', '', response_text)
                response_text = re.sub(r'\n```$', '', response_text)
            
            # Parse the one supported JSON wrapper, then validate the exact
            # custom-block contract before allowing the result downstream.
            try:
                result = json.loads(response_text)
                if (
                    not isinstance(result, dict)
                    or set(result) != {"blocks"}
                    or not isinstance(result["blocks"], list)
                    or len(result["blocks"]) != 1
                    or not isinstance(result["blocks"][0], dict)
                    or set(result["blocks"][0]) != {"text"}
                    or not isinstance(result["blocks"][0]["text"], str)
                ):
                    raise ValueError("T085 returned an unsupported JSON wrapper")
                response_text = result["blocks"][0]["text"]
            except json.JSONDecodeError:
                pass

            return validate_location_compression_output(
                location_json_str, response_text
            )
                
        except Exception as e:
            print(f"Error calling OpenAI: {e}")
            attempts += 1
            if attempts > max_retries:
                return None
    
    return None