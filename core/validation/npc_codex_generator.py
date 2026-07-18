#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
# ============================================================================
# NPC_CODEX_GENERATOR.PY - AI-POWERED CHARACTER VALIDATION SYSTEM
# ============================================================================
# 
# ARCHITECTURE ROLE: AI-Powered Content Analysis and Validation
# 
# This module solves the critical problem of AI narrative validation by automatically
# generating comprehensive NPC registries for each module using GPT-4 analysis.
# It prevents AI hallucination of non-existent characters during gameplay.
# 
# KEY RESPONSIBILITIES:
# - AI-powered extraction of legitimate NPCs from plot and area content
# - Context-aware analysis distinguishing NPCs from locations and monsters
# - Atomic file operations with concurrent access protection
# - Source attribution and categorization of character origins
# - Integration with module validation pipeline
# 
# DESIGN PHILOSOPHY:
# - AI-FIRST APPROACH: Uses GPT-4 context understanding vs rigid regex patterns
# - BULLETPROOF VALIDATION: Prevents AI from inventing non-existent characters
# - ATOMIC OPERATIONS: Concurrent-safe file operations with locking and backups
# - CACHING STRATEGY: Reuses existing codex until module content changes
# 
# INTEGRATION POINTS:
# - Called by main.py during module validation context creation
# - Integrates with ModulePathManager for consistent file access
# - Uses atomic file operations for concurrent safety
# - Provides NPC lists to validation prompt generation
# 
# DATA FLOW:
# Module Content -> AI Analysis -> NPC Extraction -> Atomic Save -> Validation Cache
# ============================================================================

Features atomic file operations, UTF-8 encoding safety, and comprehensive error handling.
"""

import json
import os
import glob
import time
import tempfile
import shutil
from datetime import datetime
from core.ai import api_client
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T059", "core/validation/npc_codex_generator.py", 306)
import config
from utils.module_path_manager import ModulePathManager
from utils.encoding_utils import safe_json_load, safe_json_dump, sanitize_text
from utils.file_operations import safe_write_json, safe_read_json


VALID_NPC_SOURCES = {
    "plot_character",
    "location_character",
    "character_file",
}


def _is_valid_npc_entry(npc):
    """Return whether an extracted NPC satisfies T059's output contract."""
    return (
        isinstance(npc, dict)
        and isinstance(npc.get("name"), str)
        and bool(npc["name"].strip())
        and npc.get("source") in VALID_NPC_SOURCES
    )


def _is_cacheable_codex(codex, module_name):
    """Reject failed or empty extraction results at every cache boundary.

    An empty codex cannot be distinguished from T059's historical silent
    failure result, so it remains retryable instead of becoming durable
    anti-hallucination context.
    """
    if not isinstance(codex, dict) or "error" in codex:
        return False
    if codex.get("module_name") != module_name:
        return False

    npcs = codex.get("npcs")
    if not isinstance(npcs, list) or not npcs:
        return False
    if not all(_is_valid_npc_entry(npc) for npc in npcs):
        return False

    total_npcs = codex.get("total_npcs", len(npcs))
    return type(total_npcs) is int and total_npcs == len(npcs)


def generate_npc_codex(module_name):
    """
    Generate an NPC codex for the specified module by analyzing plot and area files
    using GPT-4 to extract legitimate NPC names.
    
    Uses atomic file operations and comprehensive error handling for data integrity.
    
    Args:
        module_name (str): Name of the module to analyze
        
    Returns:
        dict: NPC codex with extracted NPC names and their sources
    """
    try:
        print(f"Starting NPC codex generation for module: {module_name}")
        
        # Validate module name for safety
        if not module_name or not isinstance(module_name, str):
            raise ValueError(f"Invalid module name: {module_name}")
        
        # Sanitize module name to prevent path traversal
        safe_module_name = sanitize_text(module_name)
        if safe_module_name != module_name:
            print(f"Warning: Module name sanitized from '{module_name}' to '{safe_module_name}'")
            module_name = safe_module_name
        
        # Initialize path manager
        path_manager = ModulePathManager(module_name)
        
        # Verify module directory exists
        if not os.path.exists(path_manager.module_dir):
            raise FileNotFoundError(f"Module directory does not exist: {path_manager.module_dir}")
        
        # Collect all text content from module files with error handling
        module_content = {
            "plot_content": "",
            "area_content": "",
            "character_files": []
        }
        
        # 1. Extract plot content with atomic read
        try:
            plot_file = path_manager.get_plot_path()
            if os.path.exists(plot_file):
                print(f"Loading plot file: {plot_file}")
                plot_data = safe_read_json(plot_file)
                module_content["plot_content"] = json.dumps(plot_data, indent=2, ensure_ascii=False)
                print(f"Successfully loaded plot data ({len(module_content['plot_content'])} characters)")
        except Exception as e:
            print(f"Warning: Could not load plot file: {e}")
            module_content["plot_content"] = "No plot content available"
        
        # 2. Extract area content with atomic reads
        try:
            area_files = glob.glob(f"{path_manager.module_dir}/areas/*.json")
            print(f"Found {len(area_files)} area files to analyze")
            area_texts = []
            
            for area_file in area_files:
                try:
                    print(f"Loading area file: {os.path.basename(area_file)}")
                    area_data = safe_read_json(area_file)
                    area_json = json.dumps(area_data, indent=2, ensure_ascii=False)
                    area_texts.append(area_json)
                except Exception as e:
                    print(f"Warning: Could not load area file {area_file}: {e}")
                    continue
            
            module_content["area_content"] = "\n\n".join(area_texts)
            print(f"Successfully loaded area data ({len(module_content['area_content'])} characters)")
        except Exception as e:
            print(f"Warning: Could not load area files: {e}")
            module_content["area_content"] = "No area content available"
        
        # 3. Get existing character file names for reference with atomic reads
        try:
            character_files = glob.glob(f"{path_manager.module_dir}/characters/*.json")
            print(f"Found {len(character_files)} existing character files")
            
            for char_file in character_files:
                try:
                    char_data = safe_read_json(char_file)
                    char_name = char_data.get("name", "")
                    if char_name:
                        sanitized_name = sanitize_text(char_name)
                        module_content["character_files"].append(sanitized_name)
                        print(f"Found existing character: {sanitized_name}")
                except Exception as e:
                    print(f"Warning: Could not load character file {char_file}: {e}")
                    continue
        except Exception as e:
            print(f"Warning: Could not scan character files: {e}")
        
        # 4. Use GPT-4 to extract NPC names with retry logic
        print("Extracting NPCs using AI analysis...")
        npc_list = extract_npcs_with_ai(module_content, module_name)
        
        if npc_list is None:
            raise ValueError("T059 returned unusable NPC extraction output")
        
        # 5. Create codex structure with validation
        current_time = datetime.now().isoformat()
        codex = {
            "module_name": module_name,
            "generated_timestamp": current_time,
            "generation_method": "AI_extraction_GPT4",
            "npcs": npc_list,
            "total_npcs": len(npc_list),
            "content_stats": {
                "plot_content_length": len(module_content["plot_content"]),
                "area_content_length": len(module_content["area_content"]),
                "existing_character_files": len(module_content["character_files"])
            }
        }
        
        print(f"Successfully generated codex with {len(npc_list)} NPCs")
        return codex
        
    except Exception as e:
        error_msg = f"Error generating NPC codex for {module_name}: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        
        return {
            "module_name": module_name,
            "generated_timestamp": datetime.now().isoformat(),
            "generation_method": "AI_extraction_GPT4",
            "npcs": [],
            "total_npcs": 0,
            "error": str(e),
            "error_type": type(e).__name__
        }


def extract_npcs_with_ai(module_content, module_name):
    """
    Use GPT-4 to intelligently extract NPC names from module content.
    
    Args:
        module_content (dict): Dictionary containing plot, area, and character content
        module_name (str): Name of the module being analyzed
        
    Returns:
        list | None: Valid non-empty NPC dictionaries, or None when the model
            response does not satisfy T059's output contract
    """
    try:
        # Create extraction prompt - avoid f-string issues with JSON content
        plot_content = module_content.get('plot_content', 'No plot content found')
        area_content = module_content.get('area_content', 'No area content found')
        character_files = ', '.join(module_content.get('character_files', [])) if module_content.get('character_files') else 'No character files found'
        
        extraction_prompt = f"""You are analyzing a 5th edition of the world's most popular roleplaying game module called "{module_name}" to extract NPC (Non-Player Character) names for validation purposes.

Your task is to identify legitimate NPC names mentioned in the module content. An NPC is a character that players can interact with, talk to, or encounter during gameplay.

IMPORTANT DISTINCTIONS:
- NPCs are PEOPLE with names (like "Fenrick", "Mira the Moorwise", "Captain Veylan")
- Locations are PLACES (like "Harrow's Hollow", "Shadowfall Keep", "Riverside Outpost") 
- Monsters are creatures without personal names (like "goblin", "skeleton", "wolf")
- Spirits/entities can be NPCs if they have personal names and can be interacted with

EXTRACTION RULES:
1. Extract full NPC names as they appear (e.g., "Mira the Moorwise", not just "Mira")
2. Include titles if they're part of the name (e.g., "Old Fenrick", "Sister Amara")
3. Do NOT include generic titles without names (e.g., "the blacksmith", "a guard")
4. Do NOT include location names, area names, or place names
5. Do NOT include unnamed creatures or monster types
6. Include spirits/entities only if they have personal names

For each NPC found, determine the source:
- "plot_character" = mentioned in plot points or side quests
- "location_character" = mentioned in area/location descriptions  
- "character_file" = has a full character sheet file

Respond with a JSON array of objects in this format:
[
  {{
    "name": "Full NPC Name",
    "source": "plot_character|location_character|character_file"
  }}
]

MODULE CONTENT TO ANALYZE:

PLOT CONTENT:
{plot_content}

AREA CONTENT:
{area_content}

EXISTING CHARACTER FILES:
{character_files}

Extract all legitimate NPC names now:"""

        from model_config import MODEL_PROVIDER
        if MODEL_PROVIDER == "openai":
            main_cfg = config.DM_MAIN_GPT52_NONE
        elif MODEL_PROVIDER == "gemini":
            main_cfg = config.DM_MAIN_GEMINI_PRO_LOW
        elif MODEL_PROVIDER == "lmstudio":
            main_cfg = config.DM_MAIN_LMSTUDIO
        else:  # legacy
            main_cfg = config.DM_MAIN_LEGACY

        response = capture_and_fanout("T059", api_client.create_completion,
            _request_provider=MODEL_PROVIDER,
            messages=[
                {"role": "system", "content": "You are an expert at analyzing 5th edition of the world's most popular roleplaying game module content and extracting NPC names. You understand the difference between NPCs, locations, and monsters."},
                {"role": "user", "content": extraction_prompt}
            ],
            model=main_cfg["model"],
            temperature=0.1,
            response_format=None,
            **{k: v for k, v in main_cfg.items() if k != "model"})
        
        # Parse the response
        response_text = response.choices[0].message.content.strip()
        
        # Try to extract JSON from the response
        try:
            # Find JSON array in the response
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_text = response_text[start_idx:end_idx]
                npc_list = json.loads(json_text)

                if not isinstance(npc_list, list) or not npc_list:
                    print("Warning: AI response contained no usable NPC entries")
                    return None
                
                # Validate structure
                validated_npcs = []
                for npc in npc_list:
                    if _is_valid_npc_entry(npc):
                        validated_npcs.append(npc)
                    else:
                        print(f"Warning: Invalid NPC entry format: {npc}")
                        return None
                
                print(f"Successfully extracted {len(validated_npcs)} NPCs from {module_name}")
                return validated_npcs
            else:
                print(f"Warning: Could not find JSON array in AI response")
                return None
                
        except json.JSONDecodeError as e:
            print(f"Warning: Could not parse AI response as JSON: {e}")
            print(f"Raw response: {response_text[:500]}...")
            return None
        
    except Exception as e:
        print(f"Error extracting NPCs with AI: {e}")
        return None


def get_or_create_npc_codex(module_name):
    """
    Get the NPC codex for a module, creating it if it doesn't exist.
    
    Uses atomic file operations and file locking for concurrent access safety.
    
    Args:
        module_name (str): Name of the module
        
    Returns:
        dict: NPC codex data
    """
    try:
        # Validate and sanitize module name
        if not module_name or not isinstance(module_name, str):
            raise ValueError(f"Invalid module name: {module_name}")
        
        safe_module_name = sanitize_text(module_name)
        if safe_module_name != module_name:
            print(f"Warning: Module name sanitized from '{module_name}' to '{safe_module_name}'")
            module_name = safe_module_name
        
        path_manager = ModulePathManager(module_name)
        codex_file = os.path.join(path_manager.module_dir, "npc_codex.json")
        lock_file = codex_file + ".lock"
        
        # Acquire file lock for concurrent access protection
        max_wait_time = 30  # seconds
        wait_start = time.time()
        
        while os.path.exists(lock_file):
            if time.time() - wait_start > max_wait_time:
                print(f"Warning: Lock file timeout for {lock_file}, proceeding anyway")
                try:
                    os.remove(lock_file)
                except:
                    pass
                break
            time.sleep(0.1)
        
        # Create lock file
        try:
            with open(lock_file, 'w', encoding='utf-8') as f:
                f.write(f"locked_by_npc_codex_generator_{os.getpid()}_{datetime.now().isoformat()}")
        except Exception as e:
            print(f"Warning: Could not create lock file: {e}")
        
        try:
            # Check if codex exists and is valid
            if os.path.exists(codex_file):
                try:
                    print(f"Loading existing NPC codex from: {codex_file}")
                    codex = safe_read_json(codex_file)
                    
                    # Validate codex structure and reject historical failed or
                    # empty results so a later T059 call can heal the cache.
                    if _is_cacheable_codex(codex, module_name):
                        
                        npc_count = codex.get('total_npcs', len(codex.get('npcs', [])))
                        print(f"Loaded existing NPC codex for {module_name}: {npc_count} NPCs")
                        return codex
                    else:
                        print("Warning: Existing codex has invalid structure, regenerating")
                        
                except Exception as e:
                    print(f"Warning: Could not load existing codex, regenerating: {e}")
            
            # Generate new codex with comprehensive logging
            print(f"Generating new NPC codex for {module_name}...")
            codex = generate_npc_codex(module_name)
            
            # Validate generated codex
            if not _is_cacheable_codex(codex, module_name):
                raise ValueError("Generated codex has invalid structure")
            
            # Save codex using atomic write operations
            try:
                print(f"Saving NPC codex to: {codex_file}")
                write_success = safe_write_json(codex_file, codex, create_backup=True, acquire_lock=False)
                
                if not write_success:
                    raise ValueError("Failed to write codex file")
                
                # Verify the save worked
                verification = safe_read_json(codex_file)
                if verification is None:
                    raise ValueError("Could not read back saved codex file")
                    
                if not _is_cacheable_codex(verification, module_name):
                    raise ValueError("Codex verification failed after save")
                
                print(f"Successfully saved NPC codex for {module_name} with {codex.get('total_npcs', 0)} NPCs")
                
            except Exception as e:
                print(f"Error: Could not save codex file: {e}")
                # Don't fail completely, return the generated codex even if save failed
            
            return codex
            
        finally:
            # Always remove lock file
            try:
                if os.path.exists(lock_file):
                    os.remove(lock_file)
            except Exception as e:
                print(f"Warning: Could not remove lock file: {e}")
        
    except Exception as e:
        error_msg = f"Error getting/creating NPC codex for {module_name}: {str(e)}"
        print(error_msg)
        import traceback
        traceback.print_exc()
        
        return {
            "module_name": module_name,
            "generated_timestamp": datetime.now().isoformat(),
            "generation_method": "AI_extraction_GPT4",
            "npcs": [],
            "total_npcs": 0,
            "error": str(e),
            "error_type": type(e).__name__
        }


def get_valid_npc_names(module_name):
    """
    Get a simple list of valid NPC names for validation purposes.
    
    Uses safe string handling and validation.
    
    Args:
        module_name (str): Name of the module
        
    Returns:
        list: List of sanitized NPC name strings
    """
    try:
        codex = get_or_create_npc_codex(module_name)
        
        npc_names = []
        for npc in codex.get("npcs", []):
            if isinstance(npc, dict) and "name" in npc:
                npc_name = str(npc["name"]).strip()
                if npc_name:  # Only add non-empty names
                    # Sanitize NPC name for safety
                    sanitized_name = sanitize_text(npc_name)
                    npc_names.append(sanitized_name)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_names = []
        for name in npc_names:
            if name not in seen:
                seen.add(name)
                unique_names.append(name)
        
        return unique_names
        
    except Exception as e:
        print(f"Error getting valid NPC names for {module_name}: {e}")
        return []


if __name__ == "__main__":
    # Test with Silver_Vein_Whispers
    test_module = "Silver_Vein_Whispers"
    print(f"Testing NPC codex generation for {test_module}")
    
    codex = get_or_create_npc_codex(test_module)
    print(f"\nGenerated codex:")
    print(json.dumps(codex, indent=2))
    
    print(f"\nValid NPC names:")
    names = get_valid_npc_names(test_module)
    for name in names:
        print(f"- {name}")