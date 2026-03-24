#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""
FINAL PRODUCTION - Combat message compressor for historical context.
Compresses verbose combat messages to reduce tokens in conversation history.
No validation needed since output is for AI context only, not actions.
"""

import json
import hashlib
import re
import config
from core.ai import api_client
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T017", "core/ai/combat_compression_engine.py", 169)
from typing import Dict, Optional
from pathlib import Path
import sys
import os

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
- @ROUND=<integer>
- @PLAYER=<exact player name from source>                     # keep spaces and punctuation as-is, but drop "(player)" suffix
- @PROCESS=[<id:initiative>, ...]                             # creatures to process NOW, in initiative order
                                                             # Format entries as id:initiative (e.g., G3:18) — do NOT use parentheses
                                                             # If source says ">>> PROCESS ALL OF THESE": list creatures to resolve before stop
                                                             # If source says ">>> CURRENT: <name> - PLAYER TURN": set @PROCESS=[player:init] ONLY
                                                             #   (the player is the ONLY creature to process; after_player creatures are NOT in @PROCESS)
- @STOP=<same exact value as @PLAYER>                         # MUST equal @PLAYER; if source gives a stop name, use that exact name
- @STATUS=acted[...],dead[...],after_player[...],waiting[...] # from tracker; ALL FOUR groups MUST always appear, even if empty (e.g., acted[],dead[])
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
- @ACTION=<player action text verbatim>                       # do not paraphrase; keep punctuation

OPTIONAL TAGS
- @BRIEF=<≤25 words of flavor>                                # omit first if tokens are tight
- @SAVES=[id:STR:#,DEX:#,CON:#,INT:#,WIS:#,CHA:#; ...]        # include only if likely needed THIS segment

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
- @STOP equals @PLAYER exactly.
- Every ID used in other tags exists in @ROSTER with role/type/canonical.
- @HP includes ALL living creatures (plus the player) from the tracker.
- @ATK MUST be present whenever @PROCESS has entries. It contains ONLY actors in @PROCESS. For the player (rolls own dice), use id:[] -- never a label or weapon name.
- @STATUS has exactly four groups: acted[], dead[], after_player[], waiting[]. All four MUST appear. @PLAYER MUST appear in exactly one group.
- No creature in more than one @STATUS group. Assign by precedence: dead > acted > after_player > waiting. A creature labeled "After Player" in source goes ONLY in after_player[], never also in waiting[].
- @DICE only contains plausible generic damage dice for THIS segment; values are within face ranges.
- @SLOTS contains only partially used slots; omit full ones.

FORMAT
- Output ONLY the tags, one per line, no extra text, no prefixes, no code fences."""

class CombatCompressor:
    """Production combat message compressor for historical context."""
    
    def __init__(self, enable_caching: bool = True):
        """Initialize compressor."""
        from model_config import MODEL_PROVIDER
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
        self.cache = self._load_cache() if enable_caching else {}
    
    def _load_cache(self) -> Dict[str, str]:
        """Load compression cache."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_cache(self):
        """Save compression cache."""
        if self.enable_caching:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2)
    
    def _get_content_hash(self, content: str) -> str:
        """Generate MD5 hash for caching."""
        return hashlib.md5(content.encode()).hexdigest()
    
    def compress(self, content: str) -> str:
        """Compress combat message content."""
        # Check cache
        if self.enable_caching:
            content_hash = self._get_content_hash(content)
            if content_hash in self.cache:
                cached_value = self.cache[content_hash]
                # Validate cached content is actually compressed
                if cached_value.startswith("@T=CS/v2"):
                    return cached_value
                else:
                    # Remove corrupted cache entry
                    print(f"[WARNING] Removing corrupted cache entry (not compressed format)")
                    del self.cache[content_hash]
                    self._save_cache()
        
        try:
            # Call AI for compression
            print(f"[DEBUG] Calling AI compression with model: {self._config['model']}")
            response = capture_and_fanout("T017", api_client.create_completion,
                messages=[
                    {"role": "system", "content": COMBAT_COMPRESSION_PROMPT},
                    {"role": "user", "content": content}
                ],
                model=self._config["model"],
                temperature=0.3,
                **{k: v for k, v in self._config.items() if k != "model"})
            
            # Track usage
            if USAGE_TRACKING_AVAILABLE:
                try:
                    track_response(response)
                except:
                    pass  # Silently ignore tracking errors
            
            compressed = response.choices[0].message.content.strip()
            
            # Strip code fences if present
            if compressed.startswith("```"):
                compressed = re.sub(r"^```.*?\n|```$", "", compressed, flags=re.MULTILINE).strip()
            
            # Validate compression actually happened
            if not compressed.startswith("@T=CS/v2"):
                print(f"[ERROR] AI returned invalid compression format")
                print(f"[ERROR] Expected @T=CS/v2, got: {compressed[:100]}...")
                return content  # Return original, don't cache
            
            # Validate compression actually reduced size
            if len(compressed) >= len(content):
                print(f"[WARNING] Compression didn't reduce size: {len(content)} -> {len(compressed)}")
                # Still cache if format is valid but size didn't reduce
            
            # Cache result ONLY if valid compression
            if self.enable_caching:
                content_hash = self._get_content_hash(content)
                self.cache[content_hash] = compressed
                self._save_cache()
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