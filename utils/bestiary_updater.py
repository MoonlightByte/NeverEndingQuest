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
register_callsite("T083", "utils/bestiary_updater.py", 202)

from utils.file_operations import safe_read_json, safe_write_json
from utils.encoding_utils import safe_json_load, safe_json_dump, sanitize_text
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set up logging
set_script_name("bestiary_updater")

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
                    mini_cfg = config.MINI_UTIL_GEMINI_FLASH_MINIMAL
                elif MODEL_PROVIDER == "lmstudio":
                    mini_cfg = config.MINI_UTIL_LMSTUDIO
                else:  # legacy
                    mini_cfg = config.MINI_UTIL_LEGACY

                response = capture_and_fanout("T083", api_client.create_completion,
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
                
                # Parse response
                response_text = response.choices[0].message.content
                
                # Try to parse JSON
                try:
                    result = json.loads(response_text)
                except json.JSONDecodeError as je:
                    warning(f"JSON decode error on attempt {attempt + 1}: {je}")
                    if attempt < max_retries - 1:
                        # Add more explicit instructions for next attempt
                        user_prompt = f"""{user_prompt}

IMPORTANT: You MUST return valid JSON with exactly these fields:
{{
    "name": "{monster_name}",
    "type": "one of: aberration, beast, celestial, construct, dragon, elemental, fey, fiend, giant, humanoid, monstrosity, ooze, plant, undead",
    "description": "detailed description text here",
    "tags": ["tag1", "tag2", "tag3"]
}}"""
                        continue
                    else:
                        raise je
                
                # Validate required fields
                required_fields = ["name", "type", "description"]
                missing_fields = [f for f in required_fields if f not in result]
                if missing_fields:
                    warning(f"Missing required fields on attempt {attempt + 1}: {missing_fields}")
                    if attempt < max_retries - 1:
                        continue
                    else:
                        # Try to patch missing fields
                        result.setdefault("name", monster_name)
                        result.setdefault("type", "monstrosity")
                        result.setdefault("description", f"A mysterious creature known as {monster_name}")
                        result.setdefault("tags", [])
                
                # Add metadata
                result["source_file"] = "bestiary_updater.py"
                result["generated_date"] = datetime.now().isoformat()
                
                # Sanitize text fields
                result["description"] = sanitize_text(result.get("description", ""))
                result["name"] = sanitize_text(result.get("name", monster_name))
                
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
    
    def update_bestiary_safe(self, new_monsters: Dict[str, Dict], test_mode: bool = False) -> bool:
        """
        Safely update the bestiary with new monster entries
        
        Args:
            new_monsters: Dictionary of monster_id -> monster data
            test_mode: If True, write to test file instead of actual bestiary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Determine target file
            if test_mode:
                bestiary_file = "data/bestiary/test_monster_additions.json"
                info("Running in TEST MODE - will not modify actual bestiary")
            else:
                bestiary_file = "data/bestiary/monster_compendium.json"
            
            # Read current bestiary
            bestiary = safe_read_json(bestiary_file)
            if not bestiary:
                warning(f"Could not read bestiary from {bestiary_file}, creating new one")
                bestiary = {
                    "version": "1.0.0",
                    "created": datetime.now().strftime("%Y-%m-%d"),
                    "total_monsters": 0,
                    "monsters": {}
                }
            
            # Track additions
            added_count = 0
            skipped_count = 0
            
            # Add new monsters
            for monster_id, monster_data in new_monsters.items():
                if monster_id in bestiary.get("monsters", {}):
                    info(f"Monster already exists, skipping: {monster_id}")
                    skipped_count += 1
                    continue
                
                # Add to bestiary
                bestiary["monsters"][monster_id] = monster_data
                added_count += 1
                info(f"Added monster to bestiary: {monster_id}")
            
            # Update total count
            bestiary["total_monsters"] = len(bestiary["monsters"])
            bestiary["last_updated"] = datetime.now().isoformat()
            
            # Write back to file
            if safe_write_json(bestiary_file, bestiary, create_backup=True):
                info(f"Successfully updated bestiary: {added_count} added, {skipped_count} skipped")
                return True
            else:
                error("Failed to write bestiary file")
                return False
                
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
        """
        info(f"Starting bestiary update process for {len(monster_names)} monsters from {module_name}")
        
        # Extract ALL context from module areas
        module_context = self.extract_all_area_context(module_name)
        if not module_context:
            error("Failed to extract module context")
            return
        
        info(f"Extracted {len(module_context)} characters of context from module")
        
        # Generate descriptions for each monster
        new_monsters = {}
        failed_monsters = []
        
        for i, monster_name in enumerate(monster_names, 1):
            try:
                info(f"Processing monster {i}/{len(monster_names)}: {monster_name}")
                
                # Normalize the monster ID for storage
                monster_id = monster_name.lower().replace(" ", "_").replace("-", "_").replace("'", "")
                
                # Generate description
                monster_data = await self.generate_monster_description(monster_name, module_context)
                if monster_data:
                    new_monsters[monster_id] = monster_data
                    info(f"Successfully generated description for: {monster_name} -> {monster_id}")
                else:
                    warning(f"Failed to generate description for {monster_name}")
                    failed_monsters.append(monster_name)
                    
            except Exception as e:
                error(f"Exception processing {monster_name}: {e}")
                failed_monsters.append(monster_name)
                continue
        
        # Update bestiary - only with successfully generated descriptions
        if new_monsters:
            success = self.update_bestiary_safe(new_monsters, test_mode)
            if success:
                info(f"Process complete! Added {len(new_monsters)} monsters to bestiary")
            else:
                error("Failed to update bestiary")
        else:
            warning("No new monsters to add - all descriptions failed to generate")
        
        # Generate summary report
        info("\n=== Bestiary Update Summary ===")
        info(f"Module scanned: {module_name}")
        info(f"Monsters requested: {len(monster_names)}")
        info(f"Descriptions generated: {len(new_monsters)}")
        info(f"Failed to generate: {len(failed_monsters)}")
        if failed_monsters:
            info(f"Failed monsters: {', '.join(failed_monsters[:5])}{'...' if len(failed_monsters) > 5 else ''}")
        info(f"Test mode: {test_mode}")
        info("================================\n")


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