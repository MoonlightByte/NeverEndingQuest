# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Module Stitcher
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

# ============================================================================
# MODULE_STITCHER.PY - ORGANIC MODULE INTEGRATION AND WORLD BUILDING
# ============================================================================
# 
# ARCHITECTURE ROLE: Module Integration Layer - Automatic Community Module Stitching
# 
# This module implements an organic module integration system that automatically
# detects, analyzes, and connects adventure modules based on their actual content.
# It uses AI-driven analysis of area descriptions, plot themes, and existing
# connectivity to suggest natural narrative bridges between modules.
# 
# CORE DESIGN PHILOSOPHY - ISOLATED MODULE ARCHITECTURE:
# - Each module is self-contained and independent
# - AI generates travel narration for clean transitions between modules
# - No cross-module area connections to prevent state management issues
# - Uses current data structure (area files, plot files) not outdated module.json
# - Community-ready for player-made and downloaded modules
# 
# SAFETY & CONFLICT RESOLUTION:
# - Automatic ID conflict resolution (area IDs, location IDs)
# - File structure security validation (no executables, size limits)
# - AI content safety review (family-friendly validation)
# - Schema compliance checking (80% minimum pass rate)
# - Graceful error handling with detailed logging
# 
# ID CONFLICT RESOLUTION:
# - Detects duplicate area IDs (e.g., HH001 already exists)
# - Generates unique alternatives (HH001 → HH002)
# - Updates all references: area files, location IDs, map connections
# - Renames corresponding files automatically
# - Preserves data integrity throughout process
# 
# CONTENT SAFETY VALIDATION:
# - File security: blocks executables, oversized files, directory traversal
# - AI content review: checks for inappropriate themes or content
# - Schema validation: ensures JSON structure compliance
# - Rejects modules that fail security or safety checks
# 
# DATA SOURCES (CURRENT ARCHITECTURE):
# - Area files (HH001.json, G001.json, etc.) - area descriptions and connectivity
# - module_plot.json - story themes and main objectives  
# - map_*.json files - layout information (source of truth)
# - areaConnectivity fields - existing connections between areas
# 
# KEY RESPONSIBILITIES:
# - Scan modules/ directory for new modules on startup
# - Resolve ID conflicts automatically before integration
# - Validate module safety using multiple security layers
# - Extract area metadata from current file structure
# - AI analysis of area themes and compatibility
# - Generate simple narrative transition bridges
# - Build organic world registry that grows with each module
# - Auto-register valid modules in campaign system
# 
# INTEGRATION WORKFLOW:
# 1. Detect new modules by scanning directory structure
# 2. Check for ID conflicts and resolve automatically
# 3. Validate module safety (files, content, schemas)
# 4. Extract area data from *.json files (not module.json)
# 5. Analyze themes using module_plot.json content
# 6. Generate AI travel narration for clean module transitions
# 7. Update world registry with isolated modules
# 8. Store travel narration for seamless switching
# 
# EXAMPLE ISOLATED MODULES:
# Keep_of_Doom: Harrow's Hollow → Gloamwood → Shadowfall Keep (self-contained)
# + Crystal_Peaks: Frostspire Village → Ice Caverns (independent module)
# = AI Travel Narration: "The party travels through mountain passes to reach the frozen peaks where new dangers await..."
# 
# SAFETY CONFIGURATION:
# - MAX_FILE_SIZE: 10MB per file limit
# - MIN_SCHEMA_SUCCESS_RATE: 80% validation threshold
# - Dangerous patterns: executables, scripts, directory traversal blocked
# - AI safety model: Uses DM_SUMMARIZATION_MODEL for content review
# 
# This creates a safe, modular adventure system where each module is independent
# but connected through AI-generated travel narration, maintaining security and
# data integrity while preventing cross-module state management issues.
# ============================================================================

import json
import os
import glob
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from core.ai import api_client
import config
from utils.enhanced_logger import debug, info, warning, error, set_script_name
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T032", "core/generators/module_stitcher.py", 427)
register_callsite("T033", "core/generators/module_stitcher.py", 1095)

# Set script name for logging
set_script_name("module_stitcher")
from utils.encoding_utils import safe_json_load
from utils.file_operations import safe_write_json
from utils.module_path_manager import ModulePathManager

class ModuleStitcher:
    """Manages automatic module integration and organic world building"""
    
    def __init__(self):
        """Initialize module stitcher"""
        # Use absolute paths to ensure consistency regardless of working directory
        self.modules_dir = os.path.abspath("modules")
        self.root_dir = os.path.dirname(self.modules_dir)
        self.world_registry_file = os.path.join(self.modules_dir, "world_registry.json")
        self.party_tracker_file = os.path.join(self.root_dir, "party_tracker.json")

        # Ensure directories exist
        os.makedirs(self.modules_dir, exist_ok=True)

        # Load or create world registry
        self.world_registry = self._load_world_registry()
        
        # Clean up old connections if they exist (migration to isolated modules)
        if 'connections' in self.world_registry:
            print("Migrating to isolated module architecture - removing cross-module connections")
            del self.world_registry['connections']
            self.world_registry['isolatedModules'] = True
            safe_write_json(self.world_registry_file, self.world_registry)
    
    def _load_world_registry(self) -> Dict[str, Any]:
        """Load world registry or create default"""
        if os.path.exists(self.world_registry_file):
            return safe_json_load(self.world_registry_file)
        else:
            # Create default world registry
            default_registry = {
                "worldName": "Fantasy Adventure World",
                "registryVersion": "1.0.0",
                "lastUpdated": datetime.now().isoformat(),
                "modules": {},
                "areas": {},
                "themes": {},
                "isolatedModules": True
            }
            safe_write_json(self.world_registry_file, default_registry)
            return default_registry
    
    def detect_new_modules(self) -> List[str]:
        """Detect new modules in the modules directory"""
        try:
            detected_modules = []
            
            if not os.path.exists(self.modules_dir):
                return detected_modules
            
            # Scan for module directories
            for item in os.listdir(self.modules_dir):
                item_path = os.path.join(self.modules_dir, item)
                
                # Skip files and hidden directories
                if not os.path.isdir(item_path) or item.startswith('.'):
                    continue
                    
                # Skip system directories
                if item in ['campaign_archives', 'campaign_summaries']:
                    continue
                
                # Check if module has area files (current data structure)
                if self._has_area_files(item_path):
                    # Check if already registered
                    if item not in self.world_registry.get('modules', {}):
                        detected_modules.append(item)
                        print(f"Detected new module: {item}")
            
            return detected_modules
            
        except Exception as e:
            print(f"Error detecting modules: {e}")
            return []
    
    def _has_area_files(self, module_path: str) -> bool:
        """Check if module directory contains area files (current structure)"""
        try:
            # Look for area files in areas/ subdirectory
            areas_folder = os.path.join(module_path, "areas")
            if not os.path.exists(areas_folder):
                return False
            
            pattern = os.path.join(areas_folder, "*.json")
            json_files = glob.glob(pattern)
            
            area_files = []
            for file_path in json_files:
                filename = os.path.basename(file_path)
                
                # Skip system files and backup files
                if (filename.startswith('module_') or 
                    filename.startswith('party_') or
                    filename.startswith('campaign_') or
                    filename.startswith('map_') or
                    filename.startswith('plot_') or
                    filename.endswith('_BU.json')):
                    continue
                
                # Check if it's an area file by loading and checking structure
                try:
                    data = safe_json_load(file_path)
                    if (data and 'areaId' in data and 'areaName' in data and
                        'locations' in data):
                        area_files.append(filename)
                except Exception as e:
                    warning(f"Skipped malformed area file {file_path}: {e}", category="module_integration")
                    continue
            
            return len(area_files) > 0
            
        except Exception as e:
            print(f"Error checking area files in {module_path}: {e}")
            return False
    
    def analyze_module(self, module_name: str) -> Optional[Dict[str, Any]]:
        """Analyze a module's areas, themes, and connectivity"""
        try:
            module_path = os.path.join(self.modules_dir, module_name)
            if not os.path.exists(module_path):
                return None
            
            module_data = {
                "moduleName": module_name,
                "areas": {},
                "themes": [],
                "plotObjective": "",
                "levelRange": {"min": 1, "max": 1},
                "connections": {}
            }
            
            # Extract area data from area files
            areas_data = self._extract_areas_data(module_path)
            if areas_data:
                module_data["areas"] = areas_data
                
                # Calculate level range from actual area data
                levels = []
                for area_data in areas_data.values():
                    if 'recommendedLevel' in area_data:
                        levels.append(area_data['recommendedLevel'])
                
                if levels:
                    module_data["levelRange"] = {
                        "min": min(levels),
                        "max": max(levels)
                    }
            
            # Extract plot themes and objectives
            plot_data = self._extract_plot_data(module_path)
            if plot_data:
                module_data["themes"] = plot_data.get("themes", [])
                module_data["plotObjective"] = plot_data.get("objective", "")
                # Override with plot level range if provided, otherwise keep calculated range
                if "levelRange" in plot_data:
                    module_data["levelRange"] = plot_data["levelRange"]
            
            # Generate travel narration for this module (instead of connections)
            travel_narration = self._generate_travel_narration(module_data)
            module_data["travelNarration"] = travel_narration
            
            return module_data
            
        except Exception as e:
            print(f"Error analyzing module {module_name}: {e}")
            return None
    
    def _extract_areas_data(self, module_path: str) -> Dict[str, Any]:
        """Extract area data from area files in module"""
        areas_data = {}
        
        try:
            # Find all area files in the areas/ subdirectory
            areas_folder = os.path.join(module_path, "areas")
            if not os.path.exists(areas_folder):
                print(f"Warning: No areas/ folder found in {module_path}")
                return {}
            
            pattern = os.path.join(areas_folder, "*.json")
            json_files = glob.glob(pattern)
            
            for file_path in json_files:
                filename = os.path.basename(file_path)
                
                # Skip system files and backup files
                if (filename.startswith('module_') or 
                    filename.startswith('party_') or
                    filename.startswith('campaign_') or
                    filename.startswith('map_') or
                    filename.startswith('plot_') or
                    filename.endswith('_BU.json')):
                    continue
                
                try:
                    data = safe_json_load(file_path)
                    if (data and 'areaId' in data and 'areaName' in data):
                        area_id = data['areaId']
                        areas_data[area_id] = {
                            "areaName": data.get('areaName', ''),
                            "areaDescription": data.get('areaDescription', ''),
                            "areaType": data.get('areaType', ''),
                            "dangerLevel": data.get('dangerLevel', 'unknown'),
                            "recommendedLevel": data.get('recommendedLevel', 1),
                            "climate": data.get('climate', ''),
                            "terrain": data.get('terrain', ''),
                            "areaConnectivity": data.get('areaConnectivity', []),
                            "areaConnectivityId": data.get('areaConnectivityId', []),
                            "locationCount": len(data.get('locations', []))
                        }
                except Exception as e:
                    print(f"Error processing area file {file_path}: {e}")
                    continue
            
            return areas_data
            
        except Exception as e:
            print(f"Error extracting areas data from {module_path}: {e}")
            return {}
    
    def _extract_plot_data(self, module_path: str) -> Optional[Dict[str, Any]]:
        """Extract plot themes and objectives from module_plot.json"""
        try:
            plot_file = os.path.join(module_path, "module_plot.json")
            if not os.path.exists(plot_file):
                return None
            
            plot_data = safe_json_load(plot_file)
            if not plot_data:
                return None
            
            # Extract key information
            extracted = {
                "objective": plot_data.get('mainObjective', ''),
                "plotTitle": plot_data.get('plotTitle', ''),
                "themes": []
            }
            
            # Analyze plot points for themes
            plot_points = plot_data.get('plotPoints', [])
            
            for point in plot_points:
                # Extract themes from descriptions
                description = point.get('description', '')
                if description:
                    extracted["themes"].append(description)  # Full description for analysis
            
            # Level range should be calculated from actual area data, not from plot points
            # This function no longer sets levelRange - it's calculated from areas in analyze_module()
            
            return extracted
            
        except Exception as e:
            print(f"Error extracting plot data from {module_path}: {e}")
            return None
    
    def _generate_travel_narration(self, module_data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate AI travel narration for transitioning to this module"""
        try:
            # Generate travel narration for this module
            system_prompt = """You are a fantasy adventure narrator. Generate brief, atmospheric travel narration for when a party transitions to a new adventure module. This should be 2-3 sentences that:

1. Describe the journey/travel to the new region
2. Set the mood and atmosphere for the new adventure
3. Provide DM guidance for presenting the transition
4. Keep it generic enough to work from any previous location

Examples:
- "The party travels for several days through winding country roads, eventually reaching the mist-shrouded village of..."
- "Word of strange happenings draws the adventurers northward, where rumors speak of..."
- "Following ancient trade routes, the party arrives at a region where..."

Use only standard ASCII characters in all text -- no smart quotes, no em-dashes, no Unicode. Use straight quotes and regular dashes only.

Return JSON with:
{
  "travelNarration": "atmospheric description for players",
  "dmGuidance": "instructions for DM on presenting the transition"
}"""
            
            # Prepare module data for narration
            module_name = module_data.get('moduleName', '')
            plot_objective = module_data.get('plotObjective', '')
            level_range = module_data.get('levelRange', {})
            
            # Get first area for setting context
            first_area_name = ""
            first_area_type = ""
            if module_data.get('areas'):
                first_area = list(module_data['areas'].values())[0]
                first_area_name = first_area.get('areaName', '')
                first_area_type = first_area.get('areaType', '')
            
            user_prompt = f"""Generate travel narration for transitioning to this module:

MODULE: {module_name}
OBJECTIVE: {plot_objective}
LEVEL RANGE: {level_range.get('min', 1)}-{level_range.get('max', 5)}
FIRST AREA: {first_area_name} ({first_area_type})

Create atmospheric travel narration that leads into this adventure."""
            
            from model_config import MODEL_PROVIDER
            if MODEL_PROVIDER == "openai":
                summ_config = config.DM_SUMM_GPT54MINI_NONE
            elif MODEL_PROVIDER == "gemini":
                summ_config = config.DM_SUMM_GEMINI_FLASH_LOW
            elif MODEL_PROVIDER == "lmstudio":
                summ_config = config.DM_SUMM_LMSTUDIO
            else:  # legacy
                summ_config = config.DM_SUMM_LEGACY

            response = capture_and_fanout("T032", api_client.create_completion,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model=summ_config["model"],
                temperature=0.8,
                **{k: v for k, v in summ_config.items() if k != "model"})

            # Parse AI response
            ai_response = response.choices[0].message.content
            try:
                narration_data = json.loads(ai_response)
                return {
                    "travelNarration": narration_data.get('travelNarration', ''),
                    "dmGuidance": narration_data.get('dmGuidance', ''),
                    "generatedDate": datetime.now().isoformat()
                }
            except json.JSONDecodeError:
                print(f"Warning: Could not parse AI travel narration: {ai_response[:200]}...")
                return {
                    "travelNarration": f"The party travels to the {first_area_name} region, where new adventures await.",
                    "dmGuidance": "Present this as a clean transition to the new module.",
                    "generatedDate": datetime.now().isoformat()
                }
                
        except Exception as e:
            print(f"Error generating travel narration: {e}")
            return {
                "travelNarration": "The party travels to a new region where fresh adventures await.",
                "dmGuidance": "Present this as a transition to the new module.",
                "generatedDate": datetime.now().isoformat()
            }
    
    def _create_module_backup(self, module_name: str) -> str:
        """Create backup of all module files before integration.

        Backups are stored OUTSIDE the module being backed up, under
        modules/.integration_backups/<module_name>_<timestamp>/. This
        prevents two failure modes (INT-C2):

          1. A backup placed inside the module directory means a rollback
             would restore from a path that may itself have been mutated
             (or whose parent dir is the corruption target).
          2. Module-discovery walks would see the backup directory as a
             candidate module. (Discovery already skips dotted-name dirs
             at line ~171, which is why the parent is `.integration_backups`.)

        The backup is cleaned up by `_cleanup_backup` once the
        integration commits successfully -- it is only useful during the
        narrow integrate_module window.

        Returns:
            str: Path to backup directory if successful, None otherwise
        """
        try:
            module_path = os.path.join(self.modules_dir, module_name)
            if not os.path.exists(module_path):
                return None

            # Create backup directory with timestamp, OUTSIDE the module dir.
            # The dotted parent name (`.integration_backups`) ensures the
            # discovery filter at _detect_new_modules skips this tree.
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backups_root = os.path.join(self.modules_dir, ".integration_backups")
            os.makedirs(backups_root, exist_ok=True)
            backup_dir = os.path.join(backups_root, f"{module_name}_{timestamp}")
            os.makedirs(backup_dir, exist_ok=True)

            # List all files to backup
            files_backed_up = 0

            # Backup all JSON files in module root
            for filename in os.listdir(module_path):
                file_path = os.path.join(module_path, filename)

                # Skip directories and non-JSON files, but backup everything else for safety
                if os.path.isfile(file_path) and filename.endswith('.json'):
                    backup_path = os.path.join(backup_dir, filename)

                    try:
                        import shutil
                        shutil.copy2(file_path, backup_path)
                        files_backed_up += 1
                    except Exception as e:
                        print(f"    - Warning: Could not backup {filename}: {e}")

            # Backup subdirectories (characters, monsters, etc.)
            for subdir in ['characters', 'monsters', 'encounters', 'areas']:
                subdir_path = os.path.join(module_path, subdir)
                if os.path.exists(subdir_path) and os.path.isdir(subdir_path):
                    backup_subdir = os.path.join(backup_dir, subdir)
                    os.makedirs(backup_subdir, exist_ok=True)

                    for filename in os.listdir(subdir_path):
                        if filename.endswith('.json'):
                            src_file = os.path.join(subdir_path, filename)
                            dst_file = os.path.join(backup_subdir, filename)

                            try:
                                import shutil
                                shutil.copy2(src_file, dst_file)
                                files_backed_up += 1
                            except Exception as e:
                                print(f"    - Warning: Could not backup {subdir}/{filename}: {e}")

            print(f"    - Backed up {files_backed_up} files to {backup_dir}")
            return backup_dir if files_backed_up > 0 else None

        except Exception as e:
            print(f"Error creating module backup: {e}")
            return None

    def _cleanup_backup(self, backup_path: str):
        """Remove an integration backup directory.

        The integration backup is only useful during the narrow window of
        integrate_module. Once the world_registry has been committed (or
        once rollback has consumed the backup), the directory is dead
        weight and must be removed so modules/.integration_backups/ does
        not grow unbounded.

        Idempotent and best-effort: safe to call with an empty/None path
        or with a path that no longer exists. T3-5 wires this same
        helper into the rollback path, which may legitimately call
        cleanup after the backup has already been consumed.
        """
        if not backup_path:
            return
        if not os.path.exists(backup_path):
            return
        try:
            import shutil
            shutil.rmtree(backup_path, ignore_errors=True)
        except Exception as e:
            # Best-effort cleanup -- never let a stale backup dir crash
            # the integration that just succeeded.
            print(f"    - Warning: Could not clean up backup {backup_path}: {e}")

    def _rollback_module(self, module_name: str, backup_path: str) -> bool:
        """Restore a module directory from its integration backup.

        Used by `integrate_module` when EITHER the safety-check fails
        AFTER mutations have already been applied, OR a helper raises
        mid-mutation and the outer `except Exception` catches it.
        Without this, the module dir would be left in a half-mutated
        Frankenstein state (some files renamed, others not).

        Strategy: wipe the current module dir, then copy the backup
        tree back into place. We do NOT attempt a per-file merge --
        the backup is the canonical pre-integration snapshot, and a
        bulk copy is the simplest safe restore.

        Returns True on success. Returns False on any failure
        (missing backup path, IOError during restore, etc.). When this
        returns False, the caller is expected to write a `.corrupted`
        sentinel and RETAIN the backup for forensics.
        """
        if not backup_path or not os.path.exists(backup_path):
            error(
                f"Rollback failed for {module_name}: backup path missing or "
                f"empty (path={backup_path!r})",
                category="module_integration",
            )
            return False
        try:
            import shutil
            module_path = os.path.join(self.modules_dir, module_name)
            # Wipe the (potentially mutated) live module dir before
            # restoring. copytree() refuses to overwrite, so we must
            # remove first. ignore_errors=False here so we surface a
            # genuine permission failure rather than silently swallowing
            # it and proceeding to copytree() over an inconsistent tree.
            if os.path.exists(module_path):
                shutil.rmtree(module_path)
            shutil.copytree(backup_path, module_path)
            info(
                f"Successfully rolled back module {module_name} from backup",
                category="module_integration",
            )
            return True
        except Exception as e:
            error(
                f"Rollback failed for module {module_name}: {e}",
                exception=e,
                category="module_integration",
            )
            return False

    def _write_corrupted_sentinel(self, module_name: str, reason: str) -> None:
        """Write a `.corrupted` marker file into the module directory.

        Called when rollback ITSELF fails -- the module is in an
        unknown half-restored state. The sentinel:
          - Signals operators / subsequent runs that this module is
            broken and must not be loaded.
          - Documents the reason for forensics.

        Best-effort: writing the sentinel must never raise, since by
        the time we're here something has already gone badly wrong.
        """
        try:
            module_path = os.path.join(self.modules_dir, module_name)
            if not os.path.isdir(module_path):
                # If even the module dir is gone, write to the parent
                # so the marker isn't lost entirely.
                os.makedirs(module_path, exist_ok=True)
            sentinel = os.path.join(module_path, ".corrupted")
            with open(sentinel, "w", encoding="utf-8") as fh:
                fh.write(reason + "\n")
        except Exception:
            # Never raise from the sentinel writer -- the caller is
            # already on the failure path.
            pass

    def integrate_module(self, module_name: str) -> bool:
        """Integrate a new module into the world registry with conflict resolution.

        Rollback contract (T3-5 / INT-C3):
          - `backup_dir` is created BEFORE any mutation.
          - `mutations_applied` flips True the moment we call
            `_resolve_id_conflicts` (which may rename files / rewrite
            JSON). From that point on, any failure path -- whether
            the safety check returns False OR the outer
            `except Exception` fires -- MUST roll the module back
            from the backup. Without this, partial mutations linger
            on disk and the module is half-renamed.
          - If rollback succeeds, the backup is cleaned up.
          - If rollback FAILS, the backup is RETAINED and a
            `.corrupted` sentinel is written into the module dir so
            operators / subsequent runs see the breakage.
          - Failures BEFORE the first mutation (e.g. analyze_module
            returns None) do NOT trigger rollback -- nothing changed
            so there's nothing to restore. The backup is still
            cleaned up to avoid leaking entries in
            modules/.integration_backups/.
        """
        backup_dir = None
        mutations_applied = False
        try:
            print(f"Integrating module: {module_name}")

            # Create backup of all module files before any modifications
            backup_dir = self._create_module_backup(module_name)
            if backup_dir:
                print(f"  - Created backup for module {module_name}")

            # Analyze the module
            module_data = self.analyze_module(module_name)
            if not module_data:
                print(f"Failed to analyze module: {module_name}")
                # Pre-mutation failure -- no rollback needed. Clean up
                # the backup to avoid leaking entries.
                self._cleanup_backup(backup_dir)
                return False

            # Check for conflicts and resolve them.
            # NOTE: _resolve_id_conflicts may rename area files and
            # rewrite location IDs in place. Once we enter this call,
            # we are committed to the rollback contract.
            mutations_applied = True
            conflicts_resolved = self._resolve_id_conflicts(module_name, module_data, backup_dir)
            if conflicts_resolved:
                print(f"  - Resolved {conflicts_resolved} ID conflicts")

                # Update BU files with the corrected location IDs
                bu_updated = self._update_bu_files_after_conflict_resolution(module_name)
                if bu_updated:
                    print(f"  - Updated {bu_updated} BU files with corrected location IDs")

                # Re-analyze module after ID changes
                module_data = self.analyze_module(module_name)
                if not module_data:
                    print(f"Failed to re-analyze module after conflict resolution: {module_name}")
                    # Mutations have already been applied at this
                    # point -- rollback.
                    self._handle_integration_failure(
                        module_name, backup_dir,
                        reason="Failed to re-analyze module after conflict resolution",
                    )
                    return False

            # Validate module safety
            if not self._validate_module_safety(module_name, module_data):
                print(f"Module {module_name} failed safety validation - skipping integration")
                # PATH A: safety check rejected the module AFTER
                # mutations were applied. Restore from backup.
                self._handle_integration_failure(
                    module_name, backup_dir,
                    reason="Module failed safety validation",
                )
                return False

            # Add module to registry
            self.world_registry['modules'][module_name] = {
                "moduleName": module_name,
                "addedDate": datetime.now().isoformat(),
                "themes": module_data.get('themes', []),
                "plotObjective": module_data.get('plotObjective', ''),
                "levelRange": module_data.get('levelRange', {"min": 1, "max": 1}),
                "areaCount": len(module_data.get('areas', {})),
                "travelNarration": module_data.get('travelNarration', {})
            }

            # Add areas to registry
            for area_id, area_data in module_data.get('areas', {}).items():
                self.world_registry['areas'][area_id] = {
                    **area_data,
                    "module": module_name,
                    "addedDate": datetime.now().isoformat()
                }

            # Note: Cross-module connections disabled for clean module isolation
            # Each module is self-contained and transitions are handled by AI narration

            # Update registry metadata
            self.world_registry['lastUpdated'] = datetime.now().isoformat()

            # Save registry (atomic write: world_registry is the single source
            # of truth for inter-module world state; interruption mid-write
            # would corrupt it).
            safe_write_json(self.world_registry_file, self.world_registry)

            print(f"Successfully integrated module: {module_name}")
            print(f"  - Added {len(module_data.get('areas', {}))} areas")
            travel_text = module_data.get('travelNarration', {}).get('travelNarration', '')
            if travel_text:
                print(f"  - Generated travel narration: {travel_text[:60]}...")

            # Integration committed -- rollback is no longer meaningful.
            # Remove the backup so modules/.integration_backups/ does not
            # accumulate one entry per successful integration.
            self._cleanup_backup(backup_dir)

            return True

        except Exception as e:
            # PATH B: a helper raised mid-integration. If mutations
            # were applied before the crash, restore the module from
            # backup; otherwise it's safe to just leave things alone.
            print(f"Error integrating module {module_name}: {e}")
            # Drop the partially-built registry entries so we don't
            # write them on the next integrate call.
            self.world_registry.get('modules', {}).pop(module_name, None)
            if mutations_applied:
                self._handle_integration_failure(
                    module_name, backup_dir,
                    reason=f"Integration error: {e}",
                )
            else:
                # Nothing was mutated -- just clean up the backup.
                self._cleanup_backup(backup_dir)
            return False

    def _handle_integration_failure(self, module_name: str,
                                     backup_dir: str, reason: str) -> None:
        """Centralised rollback-and-cleanup for integration failures.

        Tries to restore from `backup_dir`. On rollback success,
        cleans up the backup. On rollback failure, RETAINS the
        backup for forensics and writes a `.corrupted` sentinel
        into the module directory so operators see the breakage.

        Used by both the safety-check-fail path and the outer
        `except Exception` path in `integrate_module`.
        """
        rollback_ok = self._rollback_module(module_name, backup_dir)
        if rollback_ok:
            self._cleanup_backup(backup_dir)
        else:
            self._write_corrupted_sentinel(module_name, reason)
            # Backup deliberately NOT cleaned up -- needed for forensics.
    
    def _resolve_id_conflicts(self, module_name: str, module_data: Dict[str, Any], backup_dir: str) -> int:
        """Resolve area ID and location ID conflicts by modifying the new module"""
        try:
            conflicts_resolved = 0
            existing_areas = self.world_registry.get('areas', {})
            module_path = os.path.join(self.modules_dir, module_name)

            # Check for area ID conflicts
            conflicting_areas = []
            for area_id in module_data.get('areas', {}):
                if area_id in existing_areas:
                    conflicting_areas.append(area_id)

            if conflicting_areas:
                print(f"  - Found {len(conflicting_areas)} area ID conflicts: {conflicting_areas}")

                # Generate new unique area IDs
                for old_area_id in conflicting_areas:
                    new_area_id = self._generate_unique_area_id(old_area_id, existing_areas, module_name)

                    # Update area file
                    if self._update_area_id_in_files(module_path, old_area_id, new_area_id):
                        print(f"    - Renamed area {old_area_id} -> {new_area_id}")
                        conflicts_resolved += 1

                        # Update existing areas registry for future conflict checks
                        existing_areas[new_area_id] = {"module": module_name}

            # Check for location ID conflicts globally
            location_conflicts = self._resolve_and_reprefix_location_ids(module_name, module_path, backup_dir)
            conflicts_resolved += location_conflicts

            return conflicts_resolved

        except Exception as e:
            print(f"DEBUG: [Module Stitcher] ERROR: Error resolving ID conflicts: {e}")
            return 0
    
    def _generate_unique_area_id(self, original_id: str, existing_areas: Dict[str, Any], module_name: str) -> str:
        """Generate a unique area ID by appending suffix"""
        # Extract base and number if present
        base_match = re.match(r'^([A-Z]+)(\d*)$', original_id)
        if base_match:
            base = base_match.group(1)
            num = base_match.group(2)
            start_num = int(num) if num else 1
        else:
            base = original_id
            start_num = 1
        
        # Find next available number
        for i in range(start_num + 1, start_num + 1000):  # Reasonable limit
            new_id = f"{base}{i:03d}"
            if new_id not in existing_areas:
                return new_id
        
        # Fallback: append module name
        return f"{original_id}_{module_name}"
    
    def _update_area_id_in_files(self, module_path: str, old_id: str, new_id: str) -> bool:
        """Update area ID in area file and any references"""
        try:
            # Track location ID mappings for party tracker update
            location_id_mapping = {}

            # Find and update the area file
            area_file = os.path.join(module_path, f"{old_id}.json")
            if os.path.exists(area_file):
                # Load, update, and save area file
                area_data = safe_json_load(area_file)
                if area_data and 'areaId' in area_data:
                    area_data['areaId'] = new_id

                    # Update location IDs within the area
                    for location in area_data.get('locations', []):
                        old_loc_id = location.get('locationId', '')
                        if old_loc_id.startswith(old_id):
                            new_loc_id = old_loc_id.replace(old_id, new_id, 1)
                            location['locationId'] = new_loc_id
                            # Track the mapping for party_tracker update
                            location_id_mapping[old_loc_id] = new_loc_id

                        # Note: areaConnectivityId contains location IDs which are independent
                        # of area IDs/names, so we do NOT update them when renaming areas

                    # Update map room IDs if map exists
                    map_data = area_data.get('map', {})
                    if map_data and 'rooms' in map_data:
                        for room in map_data['rooms']:
                            old_room_id = room.get('id', '')
                            if old_room_id.startswith(old_id):
                                new_room_id = old_room_id.replace(old_id, new_id, 1)
                                room['id'] = new_room_id

                                # Update connections
                                if 'connections' in room:
                                    updated_connections = []
                                    for conn in room['connections']:
                                        if conn.startswith(old_id):
                                            updated_connections.append(conn.replace(old_id, new_id, 1))
                                        else:
                                            updated_connections.append(conn)
                                    room['connections'] = updated_connections

                    # Save updated area file
                    new_area_file = os.path.join(module_path, f"{new_id}.json")
                    safe_write_json(new_area_file, area_data)

                    # Remove old file
                    os.remove(area_file)

                    # Update corresponding map file if it exists
                    old_map_file = os.path.join(module_path, f"map_{old_id}.json")
                    if os.path.exists(old_map_file):
                        new_map_file = os.path.join(module_path, f"map_{new_id}.json")
                        os.rename(old_map_file, new_map_file)

                    # Update party_tracker.json if location IDs were changed
                    if location_id_mapping:
                        self._update_party_tracker_location_ids(location_id_mapping, module_path)

                    return True

            return False

        except Exception as e:
            print(f"Error updating area ID from {old_id} to {new_id}: {e}")
            return False
    
    def _update_party_tracker_location_ids(self, location_id_mapping: Dict[str, str], module_path: str) -> bool:
        """
        Update party_tracker.json with new location IDs after area ID changes.

        Args:
            location_id_mapping: Dictionary mapping old location IDs to new location IDs
            module_path: Path to the module being updated

        Returns:
            True if party_tracker was updated, False otherwise
        """
        try:
            # Extract module name from module path
            module_name = os.path.basename(module_path)

            # Load party_tracker.json from root directory using absolute path
            party_tracker_path = self.party_tracker_file
            if not os.path.exists(party_tracker_path):
                return False

            party_tracker = safe_json_load(party_tracker_path)
            if not party_tracker:
                return False

            # Get the active module name (normalize spaces to underscores)
            active_module = party_tracker.get('module', '').replace(' ', '_')

            # Only update if the party is currently in this module
            if active_module != module_name:
                return False

            # Get current location ID
            world_conditions = party_tracker.get('worldConditions', {})
            current_location_id = world_conditions.get('currentLocationId')

            # Check if current location ID needs to be updated
            if current_location_id and current_location_id in location_id_mapping:
                new_location_id = location_id_mapping[current_location_id]
                world_conditions['currentLocationId'] = new_location_id
                party_tracker['worldConditions'] = world_conditions

                # Save updated party tracker
                safe_write_json(party_tracker_path, party_tracker)
                print(f"DEBUG: [Module Stitcher] Updated party_tracker.json: {current_location_id} -> {new_location_id} (area ID change)")
                return True

            return False

        except Exception as e:
            print(f"DEBUG: [Module Stitcher] ERROR: Failed to update party_tracker.json: {e}")
            return False

    def _resolve_and_reprefix_location_ids(self, module_name: str, module_path: str, backup_dir: str) -> int:
        """
        Ensures all location IDs in a new module are globally unique.
        If any conflict is found, it re-prefixes ALL locations in the new module.

        Args:
            module_name: Name of the module being integrated
            module_path: Path to the module directory
            backup_dir: Path to the backup directory created before integration
        """
        print(f"DEBUG: [Module Stitcher] Validating global uniqueness of location IDs for {module_name}...")

        # 1. Get all existing location IDs from the world registry
        all_existing_loc_ids = set()
        for area_id in self.world_registry.get('areas', {}):
            # To get actual location IDs, we must load the area file
            try:
                area_info = self.world_registry['areas'][area_id]
                existing_module_name = area_info.get('module')
                if not existing_module_name:
                    continue
                
                path_manager = ModulePathManager(existing_module_name)
                area_file_path = path_manager.get_area_path(area_id)
                area_data = safe_json_load(area_file_path)
                if area_data:
                    for loc in area_data.get('locations', []):
                        if loc.get('locationId'):
                            all_existing_loc_ids.add(loc.get('locationId'))
            except Exception:
                continue # Skip if file can't be read

        # 2. Get all location IDs from the NEW module
        new_module_loc_ids = set()
        new_module_areas_path = os.path.join(module_path, "areas")
        if not os.path.exists(new_module_areas_path):
            return 0
            
        for area_file in os.listdir(new_module_areas_path):
            if area_file.endswith(".json"):
                area_data = safe_json_load(os.path.join(new_module_areas_path, area_file))
                if area_data:
                    for loc in area_data.get('locations', []):
                        if loc.get('locationId'):
                            new_module_loc_ids.add(loc.get('locationId'))

        # 3. Check for any overlap
        conflicting_ids = all_existing_loc_ids.intersection(new_module_loc_ids)
        
        if not conflicting_ids:
            print(f"DEBUG: [Module Stitcher] All location IDs in {module_name} are unique.")
            return 0

        print(f"DEBUG: [Module Stitcher] WARNING: Found {len(conflicting_ids)} conflicting location IDs: {list(conflicting_ids)[:5]}...")

        # 4. If conflict exists, re-prefix the ENTIRE new module
        print(f"DEBUG: [Module Stitcher] Conflict found. Re-prefixing all locations in {module_name} to ensure uniqueness.")
        
        # Find the highest existing letter prefix to start from
        last_prefix_char_code = 64 # Start before 'A'
        for loc_id in all_existing_loc_ids:
            if loc_id and loc_id[0].isalpha():
                last_prefix_char_code = max(last_prefix_char_code, ord(loc_id[0].upper()))
        
        start_index = last_prefix_char_code - 64 
        
        # We need the helper functions from ModuleBuilder
        # Import here to avoid circular dependency
        from core.generators.module_builder import ModuleBuilder, BuilderConfig
        temp_builder = ModuleBuilder(BuilderConfig(module_name=module_name)) # Create a temporary instance to access methods
        
        sorted_new_area_files = sorted(os.listdir(new_module_areas_path))
        conflicts_resolved = 0
        
        for i, area_filename in enumerate(sorted_new_area_files):
            if not area_filename.endswith(".json") or area_filename.endswith("_BU.json"):
                continue

            # Generate a new, globally unique prefix
            new_prefix = temp_builder.get_location_prefix(start_index + i)
            area_file_path = os.path.join(new_module_areas_path, area_filename)
            area_data = safe_json_load(area_file_path)
            
            if area_data:
                print(f"DEBUG: [Module Stitcher] Applying new prefix '{new_prefix}' to area {area_data.get('areaId')}")
                # Use ModuleGenerator instead of ModuleBuilder for update_area_with_prefix
                from core.generators.module_generator import ModuleGenerator
                temp_generator = ModuleGenerator()
                updated_area_data = temp_generator.update_area_with_prefix(area_data, new_prefix)
                safe_write_json(area_file_path, updated_area_data)
                conflicts_resolved += len(updated_area_data.get('locations', []))

        # After re-prefixing, we need to update all references to the old IDs
        self._update_all_location_references(module_name, backup_dir)

        return conflicts_resolved
    
    def _recursively_update_ids_in_json(self, data: Any, id_mapping: Dict[str, str], exclude_keys: List[str] = None) -> Any:
        """
        Safely traverses a JSON structure (dict/list) and applies the id_mapping to string values,
        while skipping any keys specified in exclude_keys.
        """
        if exclude_keys is None:
            exclude_keys = []

        if isinstance(data, dict):
            new_dict = {}
            for key, value in data.items():
                if key in exclude_keys:
                    new_dict[key] = value  # Keep original value without recursion
                else:
                    new_dict[key] = self._recursively_update_ids_in_json(value, id_mapping, exclude_keys)
            return new_dict
        elif isinstance(data, list):
            return [self._recursively_update_ids_in_json(item, id_mapping, exclude_keys) for item in data]
        elif isinstance(data, str):
            # Apply mapping if the string is an ID that needs mapping
            return id_mapping.get(data, data)
        else:
            # Return non-string, non-collection types as is
            return data

    def _update_all_location_references(self, module_name: str, backup_dir: str) -> None:
        """
        Update all internal references to location IDs after re-prefixing using a safe, recursive JSON traversal.
        This function avoids blind text replacement to prevent corrupting external references like 'areaConnectivityId'.
        """
        try:
            module_path = os.path.join(self.modules_dir, module_name)
            id_mapping = {}

            # Build ID mapping by comparing backup (before integration) to current files
            backup_areas_path = os.path.join(backup_dir, "areas") if backup_dir else None
            if not backup_areas_path or not os.path.exists(backup_areas_path):
                print(f"DEBUG: [Module Stitcher] WARNING: No backup directory found for {module_name}, cannot build ID mapping for reference updates.")
                return

            current_areas_path = os.path.join(module_path, "areas")

            # Compare backup files (original IDs) with current files (re-prefixed IDs)
            for filename in os.listdir(backup_areas_path):
                if filename.endswith('.json') and not filename.endswith('_BU.json'):
                    backup_file = os.path.join(backup_areas_path, filename)
                    # The filename in the current dir should be the same
                    current_file = os.path.join(current_areas_path, filename)

                    if os.path.exists(current_file):
                        backup_data = safe_json_load(backup_file)
                        current_data = safe_json_load(current_file)

                        if backup_data and current_data:
                            # Map old to new based on matching location names, which are assumed to be stable
                            backup_locs = {loc.get('name'): loc.get('locationId') for loc in backup_data.get('locations', []) if loc.get('name') and loc.get('locationId')}
                            current_locs = {loc.get('name'): loc.get('locationId') for loc in current_data.get('locations', []) if loc.get('name') and loc.get('locationId')}

                            for name, old_id in backup_locs.items():
                                if name in current_locs:
                                    new_id = current_locs[name]
                                    if old_id != new_id:
                                        id_mapping[old_id] = new_id
            
            if not id_mapping:
                print(f"DEBUG: [Module Stitcher] No location ID changes detected for {module_name}. Skipping reference update.")
                return
            
            print(f"DEBUG: [Module Stitcher] Built ID mapping with {len(id_mapping)} entries for {module_name}. Applying updates...")

            # Walk through all JSON files in the module and apply the mapping safely
            for root, _, files in os.walk(module_path):
                for filename in files:
                    if filename.endswith('.json') and not filename.endswith('.bak') and not filename.endswith('_BU.json'):
                        file_path = os.path.join(root, filename)
                        try:
                            data = safe_json_load(file_path)
                            if not data:
                                continue
                            
                            # Apply the recursive update (id_mapping only contains current module IDs, so external links are safe)
                            updated_data = self._recursively_update_ids_in_json(data, id_mapping)
                            
                            # Check if any changes were made before writing
                            if data != updated_data:
                                safe_write_json(file_path, updated_data)
                                print(f"DEBUG: [Module Stitcher] Updated location ID references in {os.path.relpath(file_path, module_path)}")
                        
                        except Exception as e:
                            print(f"DEBUG: [Module Stitcher] WARNING: Could not process {file_path} for ID updates: {e}")

            # CRITICAL: Update party_tracker.json if this module is currently active
            party_tracker_path = self.party_tracker_file
            if os.path.exists(party_tracker_path):
                try:
                    party_tracker = safe_json_load(party_tracker_path)
                    if party_tracker:
                        active_module = party_tracker.get('module', '').replace(' ', '_')

                        if active_module == module_name:
                            world_conditions = party_tracker.get('worldConditions', {})
                            current_location_id = world_conditions.get('currentLocationId')

                            if current_location_id and current_location_id in id_mapping:
                                new_location_id = id_mapping[current_location_id]
                                world_conditions['currentLocationId'] = new_location_id
                                party_tracker['worldConditions'] = world_conditions
                                safe_write_json(party_tracker_path, party_tracker)
                                print(f"DEBUG: [Module Stitcher] Updated party_tracker.json: {current_location_id} -> {new_location_id}")
                except Exception as tracker_error:
                    print(f"DEBUG: [Module Stitcher] WARNING: Could not update party_tracker.json: {tracker_error}")

        except Exception as e:
            print(f"DEBUG: [Module Stitcher] ERROR: Failed to update location references for {module_name}: {e}")
    
    def _validate_module_safety(self, module_name: str, module_data: Dict[str, Any]) -> bool:
        """Validate module for safety issues using AI content filtering"""
        try:
            # Basic structural validation
            if not module_data.get('areas'):
                print(f"  - Warning: Module {module_name} has no areas")
                return False
            
            # Check for malicious file names or paths
            module_path = os.path.join(self.modules_dir, module_name)
            if not self._validate_file_structure(module_path):
                return False
            
            # AI-powered content validation
            if not self._ai_validate_content_safety(module_data):
                return False
            
            # Schema validation using existing validator
            if not self._validate_against_schemas(module_path):
                return False
            
            return True
            
        except Exception as e:
            print(f"Error validating module safety: {e}")
            return False
    
    def _validate_file_structure(self, module_path: str) -> bool:
        """Validate file structure for safety"""
        try:
            # Check for suspicious file patterns
            dangerous_patterns = [
                r'\.\./',  # Directory traversal
                r'^/',     # Absolute paths
                r'\.exe$', r'\.bat$', r'\.sh$',  # Executables
                r'\.dll$', r'\.so$',  # Libraries
            ]
            
            for root, dirs, files in os.walk(module_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, self.modules_dir)
                    
                    for pattern in dangerous_patterns:
                        if re.search(pattern, relative_path, re.IGNORECASE):
                            print(f"  - Security risk: Suspicious file pattern '{relative_path}'")
                            return False
                    
                    # Check file size (prevent extremely large files)
                    try:
                        file_size = os.path.getsize(file_path)
                        if file_size > 10 * 1024 * 1024:  # 10MB limit
                            print(f"  - Security risk: File too large '{relative_path}' ({file_size} bytes)")
                            return False
                    except:
                        continue
            
            return True
            
        except Exception as e:
            print(f"Error validating file structure: {e}")
            return False
    
    def _ai_validate_content_safety(self, module_data: Dict[str, Any]) -> bool:
        """Use AI to validate content for inappropriate material"""
        try:
            # Prepare content summary for AI review
            content_summary = {
                "plotObjective": module_data.get('plotObjective', ''),
                "themes": module_data.get('themes', []),  # All themes
                "areaDescriptions": []
            }
            
            # Add area descriptions (full content)
            for area_id, area_data in module_data.get('areas', {}).items():
                desc = area_data.get('areaDescription', '')
                if desc:
                    content_summary["areaDescriptions"].append(desc)
            
            # AI content safety prompt
            safety_prompt = f"""Review this fantasy adventure module content for safety and appropriateness:

{json.dumps(content_summary, indent=2)}

Check for:
1. Excessively violent or graphic content
2. Inappropriate adult themes
3. Hate speech or discriminatory content
4. Malicious instructions or code
5. Copyright violations

Respond with JSON:
{{"safe": true/false, "reason": "explanation if unsafe"}}"""
            
            from model_config import MODEL_PROVIDER
            if MODEL_PROVIDER == "openai":
                summ_config = config.DM_SUMM_GPT54MINI_NONE
            elif MODEL_PROVIDER == "gemini":
                summ_config = config.DM_SUMM_GEMINI_FLASH_LOW
            elif MODEL_PROVIDER == "lmstudio":
                summ_config = config.DM_SUMM_LMSTUDIO
            else:  # legacy
                summ_config = config.DM_SUMM_LEGACY

            response = capture_and_fanout("T033", api_client.create_completion,
                messages=[
                    {"role": "system", "content": "You are a content safety reviewer for family-friendly fantasy gaming content. Be strict but reasonable in your assessment."},
                    {"role": "user", "content": safety_prompt}
                ],
                model=summ_config["model"],
                temperature=0.1,
                **{k: v for k, v in summ_config.items() if k != "model"})

            ai_response = response.choices[0].message.content
            try:
                safety_result = json.loads(ai_response)
                if not safety_result.get('safe', False):
                    print(f"  - Content safety issue: {safety_result.get('reason', 'Unspecified')}")
                    return False
                return True
            except json.JSONDecodeError as e:
                # INT-M4: Fail CLOSED. A submitter cannot bypass content
                # safety by inducing a parse failure -- unparseable means
                # the validation did not occur, so the content is rejected.
                warning(
                    f"Safety check returned invalid JSON ({e}); failing closed (unsafe)",
                    category="module_integration",
                )
                print(f"  - AI safety validation failed to parse response (failing closed)")
                return False

        except Exception as e:
            # INT-M4: Fail CLOSED. An API/runtime failure during safety
            # validation means the check did not occur. Reject rather than
            # silently approve.
            error(
                f"Safety check API call failed: {e}; failing closed (unsafe)",
                category="module_integration",
            )
            print(f"Warning: AI content validation failed: {e} (failing closed)")
            return False
    
    def _validate_against_schemas(self, module_path: str) -> bool:
        """Validate module files against schemas"""
        try:
            # Use the existing validator
            from core.validation.validate_module_files import ModuleValidator
            
            validator = ModuleValidator(module_path, "schemas")

            # Run validation (suppress output)
            import sys
            from io import StringIO

            old_stdout = sys.stdout
            sys.stdout = StringIO()

            try:
                # VAL-C2: newly stitched modules must satisfy the full
                # per-location contract from loca_schema (21 fields),
                # not just the 3-field legacy locationfile_schema.
                # validate_all_files(strict=True) loads
                # locationfile_schema_strict.json for area validation.
                results = validator.validate_all_files(strict=True)
                success_rate = validator.get_success_rate()
            finally:
                sys.stdout = old_stdout
            
            # Check if validation passed (allow some failures for non-critical files)
            if success_rate < 0.8:  # 80% success rate minimum
                print(f"  - Schema validation failed: {success_rate:.1%} success rate")
                return False
            
            return True
            
        except Exception as e:
            print(f"Warning: Schema validation failed: {e}")
            return True  # Default to valid if validation fails
    
    def scan_and_integrate_new_modules(self) -> List[str]:
        """Scan for new modules and integrate them automatically"""
        integrated_modules = []
        
        try:
            # Detect new modules
            new_modules = self.detect_new_modules()
            
            if not new_modules:
                info("STATE: No new modules detected.", category="module_integration")
                return integrated_modules
            
            print(f"Found {len(new_modules)} new modules to integrate...")
            
            # Integrate each new module
            for module_name in new_modules:
                try:
                    if self.integrate_module(module_name):
                        integrated_modules.append(module_name)
                except Exception as e:
                    print(f"Failed to integrate module {module_name}: {e}")
                    continue
            
            if integrated_modules:
                print(f"Successfully integrated {len(integrated_modules)} modules: {', '.join(integrated_modules)}")
            
            return integrated_modules
            
        except Exception as e:
            print(f"Error during module scanning and integration: {e}")
            return integrated_modules
    
    def get_world_overview(self) -> Dict[str, Any]:
        """Get overview of the current world state"""
        try:
            modules = self.world_registry.get('modules', {})
            areas = self.world_registry.get('areas', {})
            
            overview = {
                "totalModules": len(modules),
                "totalAreas": len(areas),
                "moduleList": list(modules.keys()),
                "areasByModule": {},
                "moduleDetails": {},
                "isolatedModules": True  # Flag indicating modules are isolated
            }
            
            # Group areas by module
            for area_id, area_data in areas.items():
                module = area_data.get('module', 'Unknown')
                if module not in overview["areasByModule"]:
                    overview["areasByModule"][module] = []
                overview["areasByModule"][module].append({
                    "areaId": area_id,
                    "areaName": area_data.get('areaName', ''),
                    "areaType": area_data.get('areaType', '')
                })
            
            # Add module details with travel narration
            for module_name, module_data in modules.items():
                overview["moduleDetails"][module_name] = {
                    "plotObjective": module_data.get('plotObjective', ''),
                    "levelRange": module_data.get('levelRange', {}),
                    "areaCount": module_data.get('areaCount', 0),
                    "travelNarration": module_data.get('travelNarration', {}).get('travelNarration', '')
                }
            
            return overview
            
        except Exception as e:
            print(f"Error getting world overview: {e}")
            return {}
    
    def get_module_travel_narration(self, module_name: str) -> Dict[str, Any]:
        """Get travel narration for a specific module"""
        try:
            modules = self.world_registry.get('modules', {})
            module_data = modules.get(module_name, {})
            
            travel_narration = module_data.get('travelNarration', {})
            if not travel_narration:
                # Generate fallback narration
                return {
                    "travelNarration": f"The party travels to the {module_name.replace('_', ' ')} region, where new adventures await.",
                    "dmGuidance": "Present this as a clean transition to the new module.",
                    "generatedDate": datetime.now().isoformat()
                }
            
            return travel_narration
            
        except Exception as e:
            print(f"Error getting travel narration for {module_name}: {e}")
            return {}
    
    def get_available_modules(self) -> List[Dict[str, Any]]:
        """Get list of all available modules with basic info"""
        try:
            modules = self.world_registry.get('modules', {})
            all_areas = self.world_registry.get('areas', {})  # Get all areas once
            module_list = []
            
            for module_name, module_data in modules.items():
                # Get total location count for this module
                total_locations = 0
                module_areas = 0
                for area_id, area_data in all_areas.items():
                    if area_data.get('module') == module_name:
                        module_areas += 1
                        total_locations += area_data.get('locationCount', 0)
                
                # Get plot point count from themes or plotPoints
                plot_point_count = 0
                # Check for themes (plot hooks)
                themes = module_data.get('themes', [])
                if themes:
                    plot_point_count = len(themes)
                
                # Also check for plotPoints if themes is empty
                if plot_point_count == 0:
                    plot_points = module_data.get('plotPoints', [])
                    plot_point_count = len(plot_points)
                
                module_list.append({
                    "moduleName": module_name,
                    "plotObjective": module_data.get('plotObjective', ''),
                    "levelRange": module_data.get('levelRange', {}),
                    "areaCount": module_areas if module_areas > 0 else module_data.get('areaCount', 0),
                    "locationCount": total_locations,  # Add new data
                    "plotPointCount": plot_point_count,  # Add new data
                    "addedDate": module_data.get('addedDate', ''),
                    "hasTravel": bool(module_data.get('travelNarration'))
                })
            
            return sorted(module_list, key=lambda x: x['addedDate'])
            
        except Exception as e:
            print(f"Error getting available modules: {e}")
            return []
    
    def _update_bu_files_after_conflict_resolution(self, module_name: str) -> int:
        """
        Update BU (backup) files with corrected location IDs after conflict resolution.
        This ensures BU files match the corrected files for all JSON files that have BU versions.
        """
        try:
            module_path = os.path.join(self.modules_dir, module_name)
            updated_count = 0
            
            # Walk through all directories in the module
            for root, dirs, files in os.walk(module_path):
                for filename in files:
                    if filename.endswith('.json') and not filename.endswith('_BU.json'):
                        json_file = os.path.join(root, filename)
                        bu_file = os.path.join(root, filename.replace('.json', '_BU.json'))
                        
                        # Check if a BU version exists
                        if os.path.exists(bu_file):
                            # Copy the corrected file to its BU version
                            try:
                                import shutil
                                shutil.copy2(json_file, bu_file)
                                updated_count += 1
                                rel_path = os.path.relpath(bu_file, module_path)
                                print(f"DEBUG: [Module Stitcher] Updated BU file: {rel_path}")
                            except Exception as e:
                                print(f"DEBUG: [Module Stitcher] ERROR: Failed to update BU file {bu_file}: {e}")
            
            return updated_count
            
        except Exception as e:
            print(f"DEBUG: [Module Stitcher] ERROR: Failed to update BU files: {e}")
            return 0


# Utility functions for integration
def get_module_stitcher():
    """Get or create module stitcher instance"""
    return ModuleStitcher()

def scan_for_new_modules():
    """Utility function to scan for new modules"""
    stitcher = get_module_stitcher()
    return stitcher.scan_and_integrate_new_modules()

def get_world_status():
    """Get current world registry status"""
    stitcher = get_module_stitcher()
    return stitcher.get_world_overview()

def get_module_travel_info(module_name: str):
    """Get travel narration for a specific module"""
    stitcher = get_module_stitcher()
    return stitcher.get_module_travel_narration(module_name)

def list_available_modules():
    """Get list of all available modules"""
    stitcher = get_module_stitcher()
    return stitcher.get_available_modules()

if __name__ == "__main__":
    # Command line interface for testing
    print("=== Module Stitcher ===")
    stitcher = ModuleStitcher()
    
    # Scan for new modules
    print("\nScanning for new modules...")
    integrated = stitcher.scan_and_integrate_new_modules()
    
    # Show world overview
    print("\nWorld Overview:")
    overview = stitcher.get_world_overview()
    print(json.dumps(overview, indent=2))