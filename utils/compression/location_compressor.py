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
from openai import OpenAI

# Load configuration
try:
    import config
    from model_config import LOCATION_COMPRESSION_MODEL
    client = OpenAI(api_key=config.OPENAI_API_KEY)
except ImportError:
    raise ImportError("Missing config.py or model_config.py")

# Import token tracking
try:
    from utils.openai_usage_tracker import track_response
    USAGE_TRACKING_AVAILABLE = True
except:
    USAGE_TRACKING_AVAILABLE = False
    def track_response(r): pass  # No-op fallback

# Location Compression System Prompt
LOCATION_SYSTEM_PROMPT = """
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

@C={id:name,...}              # NUMERIC IDs to CANONICAL names ("1:Kira" not "1:Scout Kira")
@L={id:location_name,...}     # Locations referenced 
@S={id:spell_name,...}        # ALL spells mentioned (Aid, Guidance, etc.) NEVER empty if spells exist
@I={item_tokens,...}          # Items: compact tokens (silver_tankard_10gp)
@R={romance:(id1,id2),party:(ids)} # Relationships: include romance if bond beats exist

@F={feature_tokens,...}       # ALL features[] as tokens
@TRANS={[to:location_slug,dir:?],...} # connectivity[] entries (use location slugs like ad02, NOT area IDs)
@DOORS={[slug:type,locked:y/n,lock:DC,break:DC,key:slug,trap:slug|-],...} # ALL doors[] with complete data
@DC={[check_slug:DC],...}     # ALL dcChecks[] (e.g., insight_grimjaw:15)
@LOOT={item_tokens,...}       # ALL lootTable[] items as compact tokens
@HOOKS={quest_tokens,...}     # ALL plotHooks[] as intent tokens (investigate_abbey)
@HAZ={hazard_tokens,...}      # Inferred hazards (secret_trapdoor, cult_symbols, hostile_proprietor)
@AREA={areaId:area_slug,...}  # areaConnectivity (e.g., Z06:sanctum_of_silent_kings)
@NPCROLES={id:role,...}       # REQUIRED: Map NPC IDs to roles (3:elder, 4:captain, 5:proprietor, etc.)

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
• Markers: @L1 (at location), ->L2 (move to), <-L1 (return from)
• Actions: meet, rest, prep, tension, bond, trade, cast
• Include at least one social beat and one readiness/tension beat
• End every beat with a period
"""

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
@L must be present: {1:Location_Name}
@S must include ALL mentioned spells: {1:Aid,2:Guidance} if any spells appear
@R must include romance if bond beats exist: {romance:(id1,id2),party:(ids)}
@NPCROLES maps NPC IDs to roles: {1:elder,2:captain,4:proprietor}

Remove ALL role prefixes: "Kira" not "Scout_Kira", "Dorun" not "Elder_Dorun", "Thane" not "Ranger_Thane"

"""
            user_message = f"{example_format}This is a LOCATION MODULE requiring all location tables. Compress this location data:\n\n{location_json_str}"
            
            response = client.chat.completions.create(
                model=LOCATION_COMPRESSION_MODEL,
                messages=[
                    {"role": "system", "content": LOCATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.1  # Lower temperature for more deterministic output
            )
            
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
            
            # Try to parse as JSON first to see if it's wrapped
            try:
                result = json.loads(response_text)
                if "blocks" in result and result["blocks"]:
                    return result["blocks"][0]["text"]
                else:
                    return response_text
            except json.JSONDecodeError:
                # If not JSON, return the text directly
                return response_text
                
        except Exception as e:
            print(f"Error calling OpenAI: {e}")
            attempts += 1
            if attempts > max_retries:
                return None
    
    return None