#!/usr/bin/env python3
"""
Bestiary Updater - Automatically generate monster descriptions from module context
Uses configured AI model to create rich 5th edition of the world's most popular roleplaying game style descriptions based on how monsters
appear in actual game modules.
"""

import json
import asyncio
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime

from core.ai import api_client
import config
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T083", "utils/bestiary_updater.py", 268)

from utils.compendium_store import (
    MONSTER_COMPENDIUM_PATH,
    compendium_entry_exists,
    merge_compendium_entries,
    validate_generated_prose,
)
from utils.encoding_utils import sanitize_text
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set up logging
set_script_name("bestiary_updater")

_MONSTER_TYPES = frozenset({
    "aberration", "beast", "celestial", "construct", "dragon",
    "elemental", "fey", "fiend", "giant", "humanoid", "monstrosity",
    "ooze", "plant", "undead",
})


def _monster_identity(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _validate_monster_response(
    monster_name: str, response_text: str
) -> Dict[str, Any]:
    """Validate T083's complete JSON contract before anything reaches disk."""
    result = json.loads(response_text)
    if not isinstance(result, dict):
        raise ValueError("Monster description response must be a JSON object")

    expected_fields = {"name", "type", "description", "tags"}
    if set(result) != expected_fields:
        raise ValueError(
            "Monster description response must contain exactly "
            f"{sorted(expected_fields)}"
        )

    generated_name = result["name"]
    if not isinstance(generated_name, str) or not generated_name.strip():
        raise ValueError("Monster description has no usable name")
    if _monster_identity(generated_name) != _monster_identity(monster_name):
        raise ValueError(
            f"Monster description identity {generated_name!r} does not match "
            f"requested monster {monster_name!r}"
        )

    monster_type = result["type"]
    if (
        not isinstance(monster_type, str)
        or monster_type.strip().lower() not in _MONSTER_TYPES
    ):
        raise ValueError(f"Unsupported monster type: {monster_type!r}")

    tags = result["tags"]
    if (
        not isinstance(tags, list)
        or len(tags) > 12
        or any(not isinstance(tag, str) or not tag.strip() for tag in tags)
    ):
        raise ValueError("Monster tags must be a list of non-empty strings")

    description = validate_generated_prose(
        sanitize_text(result["description"]), minimum_words=20
    )
    return {
        "name": sanitize_text(generated_name).strip(),
        "type": monster_type.strip().lower(),
        "description": description,
        "tags": [sanitize_text(tag).strip() for tag in tags],
    }


class BestiaryUpdater:
    """Handles automatic generation of monster descriptions from module context"""
    
    def __init__(self):
        """Initialize the bestiary updater"""
        # Rate limiting settings (being conservative)
        self.requests_per_minute = 30
        self.request_delay = 60.0 / self.requests_per_minute  # ~2 seconds between requests
        self.last_request_time = 0
    
    def extract_all_area_context(self, module_name: str) -> str:
        """
        Extract ALL context from module area files to send to GPT
        
        Args:
            module_name: Name of the module to scan
            
        Returns:
            Combined text of all area descriptions, monsters, NPCs, etc.
        """
        info(f"Extracting complete context from module: {module_name}")
        
        combined_context = []
        combined_context.append(f"=== MODULE: {module_name} ===\n")
        
        # Path to module areas
        areas_path = Path(f"modules/{module_name}/areas")
        if not areas_path.exists():
            error(f"Module areas directory not found: {areas_path}")
            return ""
        
        # Scan all backup area files
        for area_file in sorted(areas_path.glob("*_BU.json")):
            debug(f"Reading area file: {area_file.name}")
            
            # Read area data with explicit UTF-8 encoding
            try:
                with open(area_file, 'r', encoding='utf-8') as f:
                    area_data = json.load(f)
            except UnicodeDecodeError:
                # Try with utf-8-sig to handle BOM
                try:
                    with open(area_file, 'r', encoding='utf-8-sig') as f:
                        area_data = json.load(f)
                except Exception as e:
                    warning(f"Could not read area file {area_file}: {e}")
                    continue
            except Exception as e:
                warning(f"Could not read area file {area_file}: {e}")
                continue
            
            if not area_data:
                warning(f"Area file is empty: {area_file}")
                continue
            
            # Extract area information
            area_name = area_data.get("areaName", "Unknown Area")
            area_desc = area_data.get("areaDescription", "")
            area_type = area_data.get("areaType", "")
            
            combined_context.append(f"\n--- AREA: {area_name} ({area_type}) ---")
            combined_context.append(f"Description: {area_desc}")
            
            # Process locations
            locations = area_data.get("locations", [])
            for location in locations:
                loc_name = location.get("name", "Unknown")
                loc_desc = location.get("description", "")
                loc_dm_notes = location.get("dmInstructions", "")
                
                combined_context.append(f"\nLocation: {loc_name}")
                if loc_desc:
                    combined_context.append(f"  Description: {loc_desc[:500]}")
                if loc_dm_notes:
                    combined_context.append(f"  DM Notes: {loc_dm_notes[:300]}")
                
                # List monsters in this location
                monsters = location.get("monsters", [])
                if monsters:
                    combined_context.append("  Monsters:")
                    for monster in monsters:
                        # Handle both dict and string formats
                        if isinstance(monster, dict):
                            name = monster.get("name", "Unknown")
                            number = monster.get("number", 1)
                            disposition = monster.get("disposition", "unknown")
                            strategy = monster.get("strategy", "")
                            combined_context.append(f"    - {name} (x{number}, {disposition})")
                            if strategy:
                                combined_context.append(f"      Strategy: {strategy}")
                        elif isinstance(monster, str):
                            # Handle string format (e.g., "2 Goblins")
                            combined_context.append(f"    - {monster}")
                
                # NPCs
                npcs = location.get("npcs", [])
                if npcs:
                    combined_context.append("  NPCs:")
                    for npc in npcs:
                        # Handle both dict and string formats
                        if isinstance(npc, dict):
                            npc_name = npc.get("name", "Unknown")
                            npc_desc = npc.get("description", "")
                            combined_context.append(f"    - {npc_name}: {npc_desc[:200]}")
                        elif isinstance(npc, str):
                            combined_context.append(f"    - {npc}")
                
                # Plot hooks
                hooks = location.get("plotHooks", [])
                if hooks:
                    combined_context.append("  Plot Hooks:")
                    for hook in hooks[:3]:  # Limit to avoid too much text
                        combined_context.append(f"    - {hook[:200]}")
        
        return "\n".join(combined_context)
    
    async def generate_monster_description(self, monster_name: str, module_context: str) -> Optional[Dict]:
        """
        Generate a monster description using configured AI model
        
        Args:
            monster_name: The name of the monster to generate
            module_context: Complete context from all module areas
            
        Returns:
            Dictionary with monster data or None if failed
        """
        # Rate limiting
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_delay:
            await asyncio.sleep(self.request_delay - time_since_last)
        
        # Build the prompt
        system_prompt = """You are a 5th edition of the world's most popular roleplaying game monster description expert. Generate rich, atmospheric 
        descriptions for monsters based on how they appear in game modules. Your descriptions should:
        - Be vivid and detailed, painting a clear picture of the creature
        - Include physical appearance, behavior, and atmospheric elements
        - Be suitable for use in image generation prompts
        - Maintain consistency with 5th edition of the world's most popular roleplaying game lore while adding creative details
        - Be approximately 150-250 words
        - Use only standard ASCII characters -- no smart quotes, no em-dashes, no Unicode symbols

        Return your response as a JSON object with these fields:
        {
            "name": "Proper Name",
            "type": "creature type (aberration, beast, celestial, construct, dragon, elemental, fey, fiend, giant, humanoid, monstrosity, ooze, plant, undead)",
            "description": "Your detailed description here",
            "tags": ["tag1", "tag2", "tag3"]
        }"""
        
        user_prompt = f"""Generate a detailed 5th edition of the world's most popular roleplaying game monster description for: {monster_name}

Based on this adventure module context:
{module_context[:8000]}  

Focus on any mentions of '{monster_name}' in the module. If this specific creature isn't mentioned, 
infer its appearance based on the module's theme and any similar creatures. Create an atmospheric, 
image-generation-ready description that would fit this adventure."""
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                info(f"Generating description for: {monster_name} (attempt {attempt + 1}/{max_retries})")
                
                from model_config import MODEL_PROVIDER
                if MODEL_PROVIDER == "openai":
                    mini_cfg = config.MINI_UTIL_GPT54MINI_NONE
                elif MODEL_PROVIDER == "gemini":
                    mini_cfg = config.MINI_UTIL_GEMINI_FLASH_LOW
                elif MODEL_PROVIDER == "lmstudio":
                    mini_cfg = config.MINI_UTIL_LMSTUDIO
                else:  # legacy
                    mini_cfg = config.MINI_UTIL_LEGACY

                response = capture_and_fanout("T083", api_client.create_completion,
                    _request_provider=MODEL_PROVIDER,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    model=mini_cfg["model"],
                    temperature=0.7,
                    response_format={"type": "json_object"},
                    **{k: v for k, v in mini_cfg.items() if k != "model"})
                
                # Update last request time
                self.last_request_time = time.time()
                
                response_text = response.choices[0].message.content
                result = _validate_monster_response(monster_name, response_text)
                
                # Add metadata
                result["source_file"] = "bestiary_updater.py"
                result["generated_date"] = datetime.now().isoformat()
                
                info(f"Successfully generated description for: {result['name']}")
                return result
                
            except Exception as e:
                error(f"Failed to generate description for {monster_name} on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)  # Wait before retry
                    continue
                else:
                    return None
        
        return None
    
    def update_bestiary_safe(
        self,
        new_monsters: Dict[str, Dict],
        test_mode: bool = False,
        *,
        bestiary_file: Optional[str] = None,
    ) -> bool:
        """
        Safely update the bestiary with new monster entries
        
        Args:
            new_monsters: Dictionary of monster_id -> monster data
            test_mode: If True, write to test file instead of actual bestiary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if bestiary_file is None and test_mode:
                bestiary_file = "data/bestiary/test_monster_additions.json"
                info("Running in TEST MODE - will not modify actual bestiary")
            elif bestiary_file is None:
                bestiary_file = MONSTER_COMPENDIUM_PATH

            result = merge_compendium_entries(
                bestiary_file,
                "monsters",
                new_monsters,
                overwrite=False,
            )
            for monster_id in result.added:
                info(f"Added monster to bestiary: {monster_id}")
            for monster_id in result.skipped:
                info(f"Monster already exists, skipping: {monster_id}")
            info(
                "Successfully updated bestiary: "
                f"{len(result.added)} added, {len(result.skipped)} skipped"
            )
            return True
                
        except Exception as e:
            error(f"Error updating bestiary: {e}")
            return False
    
    async def process_missing_monsters(self, module_name: str, monster_names: List[str], test_mode: bool = True):
        """
        Main processing pipeline for adding missing monsters to bestiary
        
        Args:
            module_name: Name of the module to extract context from
            monster_names: List of monster names to process
            test_mode: If True, write to test file instead of actual bestiary

        Returns:
            A result object with requested, added, skipped, and failed counts,
            plus error and success fields. The counts always balance to requested.
        """
        requested = len(monster_names)
        result = {
            "requested": requested,
            "added": 0,
            "skipped": 0,
            "failed": 0,
            "error": None,
            "success": False,
        }
        info(
            f"Starting bestiary update process for {requested} monsters "
            f"from {module_name}"
        )

        bestiary_file = (
            "data/bestiary/test_monster_additions.json"
            if test_mode
            else MONSTER_COMPENDIUM_PATH
        )
        pending = []
        seen_ids = set()
        for monster_name in monster_names:
            if not isinstance(monster_name, str) or not monster_name.strip():
                result["failed"] += 1
                continue
            clean_name = monster_name.strip()
            monster_id = (
                clean_name.lower()
                .replace(" ", "_")
                .replace("-", "_")
                .replace("'", "")
            )
            if not monster_id or monster_id in seen_ids:
                result["skipped"] += 1
                continue
            seen_ids.add(monster_id)
            try:
                if compendium_entry_exists(
                    bestiary_file, "monsters", monster_id
                ):
                    result["skipped"] += 1
                    continue
            except Exception as exc:
                result["failed"] += 1
                result["error"] = f"Failed to inspect bestiary: {exc}"
                error(result["error"])
                continue
            pending.append((monster_id, clean_name))

        module_context = ""
        if pending:
            module_context = self.extract_all_area_context(module_name)
            if not module_context:
                result["failed"] += len(pending)
                result["error"] = "Failed to extract module context"
                error(result["error"])
                pending = []
            else:
                info(f"Extracted {len(module_context)} characters of context from module")

        new_monsters = {}
        failed_monsters = []
        for index, (monster_id, monster_name) in enumerate(pending, 1):
            try:
                info(
                    f"Processing monster {index}/{len(pending)}: "
                    f"{monster_name}"
                )
                monster_data = await self.generate_monster_description(
                    monster_name, module_context
                )
                if not monster_data:
                    raise ValueError("description generation returned no result")
                new_monsters[monster_id] = monster_data
                info(
                    f"Successfully generated description for: {monster_name} "
                    f"-> {monster_id}"
                )
            except Exception as exc:
                warning(f"Failed to generate description for {monster_name}: {exc}")
                failed_monsters.append(monster_name)
                result["failed"] += 1

        if new_monsters:
            try:
                merge_result = merge_compendium_entries(
                    bestiary_file,
                    "monsters",
                    new_monsters,
                    overwrite=False,
                )
                result["added"] += len(merge_result.added)
                result["skipped"] += len(merge_result.skipped)
                info(
                    "Bestiary persistence complete: "
                    f"{len(merge_result.added)} added, "
                    f"{len(merge_result.skipped)} skipped"
                )
            except Exception as exc:
                result["failed"] += len(new_monsters)
                result["error"] = f"Failed to update bestiary: {exc}"
                error(result["error"])

        if result["error"] is None and result["failed"]:
            result["error"] = (
                f"{result['failed']} monster description(s) failed"
            )
        result["success"] = result["error"] is None and result["failed"] == 0

        info("\n=== Bestiary Update Summary ===")
        info(f"Module scanned: {module_name}")
        info(f"Monsters requested: {result['requested']}")
        info(f"Monsters added: {result['added']}")
        info(f"Monsters skipped: {result['skipped']}")
        info(f"Monsters failed: {result['failed']}")
        if failed_monsters:
            info(
                f"Failed monsters: {', '.join(failed_monsters[:5])}"
                f"{'...' if len(failed_monsters) > 5 else ''}"
            )
        info(f"Test mode: {test_mode}")
        info("================================\n")
        return result


# Test function
async def test_with_keep_of_doom():
    """Test the bestiary updater with Keep of Doom monsters"""
    updater = BestiaryUpdater()
    
    # Test monsters - some from the module, some unique ones
    test_monsters = [
        "Animated Armor",
        "Bog Mummy",
        "Shadow of Sir Garran"
    ]
    
    # Process in test mode
    await updater.process_missing_monsters("Keep_of_Doom", test_monsters, test_mode=True)


if __name__ == "__main__":
    # Run test
    asyncio.run(test_with_keep_of_doom())