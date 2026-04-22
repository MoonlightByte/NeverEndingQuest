# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Module Path Manager
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import json
import os
from .enhanced_logger import debug, info, warning, error, set_script_name

# Set script name for logging
set_script_name(__name__)

# ============================================================================
# MODULE_PATH_MANAGER.PY - FILE SYSTEM ABSTRACTION LAYER
# ============================================================================
# 
# ARCHITECTURE ROLE: Data Management Layer - File System Abstraction
# 
# This module provides a unified interface for all file operations across the
# 5e system, implementing our "Module-Centric Organization" principle.
# It abstracts file path resolution and handles legacy migration seamlessly.
# 
# KEY RESPONSIBILITIES:
# - Centralized file path resolution for all module resources
# - Handle legacy vs. unified file structure migration
# - Ensure consistent naming conventions and directory organization
# - Provide atomic file operations with backup and recovery
# - Cross-platform compatibility for file system operations
# 
# FILE ORGANIZATION STRATEGY:
# modules/[module_name]/
# |--- areas/              # Location files (HH001.json, G001.json)
# |--- characters/         # Unified player/NPC storage
# |--- monsters/           # Module-specific creatures
# |--- encounters/         # Combat encounters
# `--- meta files...       # Module plot, party tracker, etc.
# 
# ARCHITECTURAL INTEGRATION:
# - Used by all file operations throughout the system
# - Enables the Factory Pattern for content builders
# - Supports the "Data Integrity Above All" principle
# - Provides backward compatibility for legacy modules
# 
# DESIGN PATTERNS:
# - Factory Pattern: Creates proper file paths based on content type
# - Strategy Pattern: Different path strategies for legacy vs. unified structure
# - Singleton-like behavior: Shared path resolution across system
# 
# This module ensures our file system organization remains consistent
# and maintainable while supporting seamless legacy migration.
# ============================================================================

class ModulePathManager:
    """Manages file paths for module-specific resources"""
    
    # Class-level variable to track last logged module across all instances
    _last_module_logged = None
    
    # Centralized encounters directory
    ENCOUNTERS_DIR = "modules/encounters"
    
    def __init__(self, module_name=None):
        self.module_name = module_name or self._get_active_module()
        self.module_dir = f"modules/{self.module_name}"
        
    def _get_active_module(self):
        """Read the active module from party_tracker.json"""
        try:
            with open("party_tracker.json", 'r', encoding='utf-8') as file:
                data = json.load(file)
                module = data.get("module", "Keep_of_Doom")
                # Only log if module changes or on first load
                if ModulePathManager._last_module_logged != module:
                    info(f"INITIALIZATION: Switched to module '{module}'", category="module_loading")
                    ModulePathManager._last_module_logged = module
                return module
        except Exception as e:
            error(f"FILE_OP: Could not load party_tracker.json", exception=e, category="file_operations")
            debug("INITIALIZATION: Using default module 'Keep_of_Doom'", category="module_loading")
            return "Keep_of_Doom"  # Default fallback
    
    def format_filename(self, name):
        """Convert a name to a filesystem-safe filename format
        
        Uses the centralized normalize_character_name() function to ensure
        consistent character name handling across the entire system.
        
        Examples:
        - "Mike's Magical Minion" -> "mike_s_magical_minion"
        - "Sir Big-Bellied Night" -> "sir_big_bellied_night"  
        - "D'Artagnan the Bold" -> "d_artagnan_the_bold"
        - "Sir Mac'Davier" -> "sir_mac_davier"
        """
        from updates.update_character_info import normalize_character_name
        return normalize_character_name(name)
    
    # Monster and NPC paths
    def get_monster_path(self, monster_name):
        """Get the path to a monster file"""
        return f"{self.module_dir}/monsters/{self.format_filename(monster_name)}.json"
    
    def get_npc_path(self, npc_name):
        """Get the path to an NPC file (legacy support)"""
        return f"{self.module_dir}/npcs/{self.format_filename(npc_name)}.json"
    
    # Area-related paths
    def get_area_path(self, area_id):
        """Get the path to an area file"""
        # First try the new areas/ subdirectory structure
        areas_path = f"{self.module_dir}/areas/{area_id}.json"
        if os.path.exists(areas_path):
            return areas_path
        
        # Fall back to legacy root directory structure during migration
        legacy_path = f"{self.module_dir}/{area_id}.json"
        if os.path.exists(legacy_path):
            return legacy_path
        
        # Return the preferred path for new files
        return areas_path
    
    def get_plot_path(self, area_id=None):
        """Get the path to the module plot file (no longer area-specific)"""
        return f"{self.module_dir}/module_plot.json"
    
    def get_map_path(self, area_id):
        """Get the path to a map file"""
        return f"{self.module_dir}/map_{area_id}.json"
    
    def get_area_ids(self):
        """Discover all area IDs in the current module by scanning directory"""
        import re
        import os
        
        area_ids = []
        
        if not os.path.exists(self.module_dir):
            return area_ids
            
        # Pattern to match area files: starts with letters, followed by numbers, ends with .json
        # Examples: HH001.json, G001.json, SK001.json, TBM001.json, TCD001.json
        area_pattern = re.compile(r'^([A-Z]+[0-9]+)\.json$')
        
        # First check the new areas/ subdirectory structure
        areas_dir = f"{self.module_dir}/areas"
        if os.path.exists(areas_dir):
            for filename in os.listdir(areas_dir):
                # Skip backup files
                if filename.endswith('_BU.json') or filename.endswith('_backup.json'):
                    continue
                    
                match = area_pattern.match(filename)
                if match:
                    area_id = match.group(1)
                    area_ids.append(area_id)
        
        # Also check legacy root directory structure during migration
        for filename in os.listdir(self.module_dir):
            # Skip backup files
            if filename.endswith('_BU.json') or filename.endswith('_backup.json'):
                continue
                
            # Skip non-area files
            if filename in ['party_tracker.json', 'module_plot.json', 'module_context.json']:
                continue
            if filename.startswith('map_') or filename.endswith('_module.json'):
                continue
                
            match = area_pattern.match(filename)
            if match:
                area_id = match.group(1)
                # Only add if not already found in areas/ directory
                if area_id not in area_ids:
                    area_ids.append(area_id)
        
        # Sort for consistent ordering
        area_ids.sort()
        return area_ids
    
    # Module-specific paths
    def get_module_file_path(self):
        """Get the path to the main module file"""
        return f"{self.module_dir}/{self.module_name}_module.json"
    
    def get_context_path(self):
        """Get the path to the module context file"""
        return f"{self.module_dir}/module_context.json"
    
    # Player character paths
    def get_player_path(self, player_name):
        """Get the path to a player character file (legacy support)"""
        return f"{self.module_dir}/{self.format_filename(player_name)}.json"
    
    # Unified character paths with fallback support
    def get_character_path(self, character_name):
        """
        Get the path to a character file - now using root characters directory for all characters
        """
        # All characters are now stored in the root characters directory
        return f"characters/{self.format_filename(character_name)}.json"
    
    def _determine_character_role(self, character_name):
        """Determine character role from party_tracker.json"""
        try:
            with open("party_tracker.json", 'r', encoding='utf-8') as f:
                data = json.load(f)
                party_members = data.get("partyMembers", [])
                party_npcs = data.get("partyNPCs", [])
                
                if character_name.lower() in [name.lower() for name in party_members]:
                    return 'player'
                elif character_name.lower() in [name.lower() for name in party_npcs]:
                    return 'npc'
                else:
                    # Default to NPC if not in party members
                    return 'npc'
        except Exception:
            # If we can't read party_tracker, default to NPC
            return 'npc'
    
    def get_character_unified_path(self, character_name):
        """Get the unified path (whether file exists or not) - now using root characters directory"""
        return f"characters/{self.format_filename(character_name)}.json"
    
    def get_character_legacy_path(self, character_name, character_role=None):
        """Get the legacy path for a character based on role"""
        if character_role is None:
            character_role = self._determine_character_role(character_name)
            
        if character_role == 'player':
            return self.get_player_path(character_name)
        else:
            return self.get_npc_path(character_name)
    
    # Encounter paths
    def get_encounter_path(self, location_id, encounter_num):
        """Get the path to an encounter file in the centralized encounters directory"""
        return f"{self.ENCOUNTERS_DIR}/encounter_{location_id}-E{encounter_num}.json"
    
    def get_encounter_path_from_id(self, encounter_id):
        """Get the path to an encounter file using a full encounter ID"""
        return f"{self.ENCOUNTERS_DIR}/encounter_{encounter_id}.json"
    
    # Random encounter paths
    def get_random_encounter_path(self):
        """Get the path to the random encounter file"""
        return "random_encounter.json"
    
    # Directory creation methods
    def ensure_module_dirs(self):
        """Ensure all necessary module directories exist"""
        os.makedirs(f"{self.module_dir}/areas", exist_ok=True)  # Area files
        os.makedirs(f"{self.module_dir}/monsters", exist_ok=True)
        os.makedirs(f"{self.module_dir}/npcs", exist_ok=True)
        # Note: Characters are now stored in root characters/ directory
    
    def ensure_areas_directory(self):
        """Ensure the areas/ subdirectory exists for the current module"""
        areas_dir = f"{self.module_dir}/areas"
        os.makedirs(areas_dir, exist_ok=True)
        return areas_dir
    
    def ensure_encounters_directory(self):
        """Ensure the centralized encounters directory exists"""
        os.makedirs(self.ENCOUNTERS_DIR, exist_ok=True)
        return self.ENCOUNTERS_DIR
    
    # Check if a file exists
    def file_exists(self, path):
        """Check if a file exists"""
        return os.path.exists(path)
    
    # Get list of files in a directory
    def list_monsters(self):
        """List all monster files in the module"""
        monster_dir = f"{self.module_dir}/monsters"
        if os.path.exists(monster_dir):
            return [f for f in os.listdir(monster_dir) if f.endswith('.json')]
        return []
    
    def list_npcs(self):
        """List all NPC files in the module"""
        npc_dir = f"{self.module_dir}/npcs"
        if os.path.exists(npc_dir):
            return [f for f in os.listdir(npc_dir) if f.endswith('.json')]
        return []