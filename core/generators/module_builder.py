# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Core Engine - Module Builder
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

#!/usr/bin/env python3
"""
Master Module Builder
Orchestrates the generation of a complete 5th edition module by calling generators in the proper sequence.
"""

import json
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# Add parent directories to Python path for imports when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Import all generators - handle both direct execution and module import
try:
    # Try relative imports first (when imported as module)
    from .module_generator import ModuleGenerator
    from .plot_generator import PlotGenerator
    from .location_generator import LocationGenerator
    from .area_generator import AreaGenerator, AreaConfig
except ImportError:
    # Fall back to absolute imports (when run directly)
    from core.generators.module_generator import ModuleGenerator
    from core.generators.plot_generator import PlotGenerator
    from core.generators.location_generator import LocationGenerator
    from core.generators.area_generator import AreaGenerator, AreaConfig

from utils.module_context import ModuleContext
from utils.enhanced_logger import debug, info, warning, error, set_script_name
from utils.npc_reconciler import NpcReconciler
from utils.file_operations import safe_write_json
from utils.path_transaction_lock import path_transaction_lock
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
from core.ai.module_creation_contract import (
    GAME_MODULE_POLICY,
    MODULE_ADVENTURE_TYPES,
    MODULE_SPEC_FIELDS,
    ModuleCreationCancelledError,
    ModuleCreationContractError,
    ModuleCreationFailedError,
    ModuleCreationPolicy,
    ModuleCreationRecoveryRequiredError,
    ModuleCreationSpec,
    extract_labeled_module_values,
    extract_typed_module_overrides,
    get_module_creation_policy,
)
register_callsite("T028", "core/generators/module_builder.py", 919)
register_callsite("T029", "core/generators/module_builder.py", 1217)
register_callsite("T030", "core/generators/module_builder.py", 1906)

# Set script name for logging
set_script_name("module_builder")


_AUTH_ERROR_TYPE_NAMES = {"AuthenticationError", "PermissionDeniedError"}
_STORY_FIRST_MODEL_FALLBACK_FAILURES = frozenset(
    {
        "empty_response",
        "duplicate_json_key",
        "malformed_json",
        "schema",
        "semantic",
        "capacity",
        "provider",
        "timeout",
    }
)
STORY_FIRST_MODEL_FALLBACK_MESSAGE = (
    "The selected model could not complete the advanced story-first format after "
    "3 attempts. This is a model-format limitation, so NeverEndingQuest is "
    "adjusting to a compatible generation process and will continue creating "
    "your adventure."
)
_STORY_FIRST_PROVIDER_FALLBACK_MESSAGE = (
    "The selected model provider does not support the advanced story-first "
    "format. NeverEndingQuest is adjusting to a compatible generation process "
    "and will continue creating your adventure."
)


def _run_managed_module_build(
    *,
    managed,
    requested_name,
    kind,
    story_first_candidate,
    compatible_candidate,
    prepare_candidate,
    defer_promotion,
    use_story_first,
    progress_callback,
):
    """Run story-first once, then safely dial down on model-format exhaustion.

    Each story-first model stage owns its three bounded response attempts.  A
    rejected hidden candidate is retired by ``ManagedModuleBuilder`` before the
    compatible generator receives a fresh workspace. Local durability,
    authentication, cancellation, interruption, and indeterminate lifecycle
    failures deliberately bypass this fallback.
    """

    def run(candidate):
        return managed.run(
            requested_name=requested_name,
            kind=kind,
            build_candidate=candidate,
            prepare_candidate=prepare_candidate,
            defer_promotion=defer_promotion,
            retain_story_first_failure=False,
        )

    if not use_story_first:
        return run(compatible_candidate)

    fallback_message = None
    try:
        return run(story_first_candidate)
    except BaseException as exc:
        from core.generators.story_first.pipeline import StoryFirstPipelineError
        from core.generators.story_first.settings import (
            StoryFirstProviderUnsupportedError,
        )

        if isinstance(exc, StoryFirstProviderUnsupportedError):
            fallback_message = _STORY_FIRST_PROVIDER_FALLBACK_MESSAGE
        elif isinstance(exc, StoryFirstPipelineError) and (
            exc.failure_class in _STORY_FIRST_MODEL_FALLBACK_FAILURES
        ):
            fallback_message = STORY_FIRST_MODEL_FALLBACK_MESSAGE
        else:
            raise

    warning(
        "Story-first generation reached a bounded model limitation; "
        "continuing with the compatible generator.",
        category="module_generation",
    )
    if progress_callback:
        progress_callback(
            {
                "stage": 6,
                "total_stages": 9,
                "stage_name": "Adjusting generator",
                "percentage": 66,
                "message": fallback_message,
            }
        )
    return run(compatible_candidate)


def _is_auth_error(exc):
    """True when a provider call failed over credentials rather than transport.

    Credential failures never succeed on retry, so they are reported straight
    away with an actionable message instead of being retried or collapsed into
    a generic failure (issue #132).
    """
    original = getattr(exc, "original_error", None) or exc
    if type(original).__name__ in _AUTH_ERROR_TYPE_NAMES:
        return True
    status = getattr(original, "status_code", None)
    if status in (401, 403):
        return True
    text = str(original).lower()
    return any(
        marker in text
        for marker in (
            "invalid_api_key",
            "incorrect api key",
            "invalid api key",
            "no api key",
            "missing api key",
            "unauthorized",
        )
    )


def _flag_unknown_plot_ids(plot_hooks, valid_ids):
    """Return the set of PP###/SQ### IDs referenced in plot_hooks but not in valid_ids.

    MED-5 (#127): T029 can bake hallucinated plot-point IDs into per-location
    plotHooks. This scans the hook strings and reports unknown IDs so the builder
    can warn (we do NOT silently drop the hook text -- it may be valid prose).
    """
    referenced = set()
    for hook in (plot_hooks or []):
        if isinstance(hook, str):
            referenced.update(re.findall(r"\b(?:PP|SQ)\d{3}\b", hook))
    return referenced - set(valid_ids or [])


def _looks_like_npc_name(value: Any) -> bool:
    """Reject prose paragraphs without trying to invent a replacement name."""
    if not isinstance(value, str):
        return False
    candidate = " ".join(value.split())
    return bool(candidate) and len(candidate) <= 120 and len(candidate.split()) <= 18


def _project_locations_into_context(context, area_id: str, locations) -> None:
    """Mirror accepted classic locations into the internal module context."""
    for location in locations or []:
        if not isinstance(location, dict):
            continue
        location_id = location.get("locationId")
        location_name = location.get("name")
        if not location_id or not location_name:
            continue

        context.add_location(location_id, location_name, area_id)
        connections = []
        for value in list(location.get("connectivity", []) or []) + list(
            location.get("areaConnectivityId", []) or []
        ):
            if isinstance(value, str) and value and value not in connections:
                connections.append(value)
        context.locations[location_id]["connections"] = connections

        for npc in location.get("npcs", []) or []:
            if not isinstance(npc, dict) or not npc.get("name"):
                continue
            canonical_name = context.add_npc(
                npc["name"],
                area_id,
                location_id,
                description=npc.get("description", ""),
            )
            if canonical_name not in context.locations[location_id]["npcs"]:
                context.locations[location_id]["npcs"].append(canonical_name)


def _useful_string(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be useful text")
    return value.strip()


def _validate_unified_plot_contract(
    value: Any,
    area_ids: List[str],
    expected_plot_points: int,
    expected_side_quests: int,
) -> Dict[str, Any]:
    """Validate T028 identities/references before the unified plot is saved."""
    root_fields = {
        "plotTitle", "mainObjective", "plotPoints", "activeQuests",
        "completedQuests", "failedQuests", "worldEvents", "dmNotes",
    }
    if not isinstance(value, dict) or set(value) != root_fields:
        raise ValueError("T028 requires the exact unified-plot root fields")
    _useful_string(value["plotTitle"], "plotTitle")
    _useful_string(value["mainObjective"], "mainObjective")
    for field in root_fields - {"plotTitle", "mainObjective", "plotPoints"}:
        if not isinstance(value[field], list):
            raise ValueError(f"T028 {field} must be an array")

    plot_points = value["plotPoints"]
    if not isinstance(plot_points, list) or len(plot_points) != expected_plot_points:
        raise ValueError("T028 must preserve the exact plot-point cardinality")
    expected_pp_ids = [f"PP{index:03d}" for index in range(1, len(plot_points) + 1)]
    actual_pp_ids = [pp.get("id") if isinstance(pp, dict) else None for pp in plot_points]
    if actual_pp_ids != expected_pp_ids:
        raise ValueError("T028 plot IDs must be globally sequential")

    valid_areas = set(area_ids)
    side_quest_ids = []
    for pp in plot_points:
        required = {
            "id", "title", "description", "location", "nextPoints", "status",
            "plotImpact", "sideQuests",
        }
        if set(pp) != required:
            raise ValueError(f"T028 {pp.get('id')} has missing or extra fields")
        _useful_string(pp["title"], f"{pp['id']}.title")
        _useful_string(pp["description"], f"{pp['id']}.description")
        if pp["location"] not in valid_areas:
            raise ValueError(f"T028 {pp['id']} references an unknown area")
        if not isinstance(pp["nextPoints"], list) or not all(
            isinstance(item, str) for item in pp["nextPoints"]
        ):
            raise ValueError(f"T028 {pp['id']}.nextPoints must be an ID array")
        if any(item not in expected_pp_ids or item == pp["id"] for item in pp["nextPoints"]):
            raise ValueError(f"T028 {pp['id']} has an invalid nextPoints reference")
        if not isinstance(pp["status"], str) or not isinstance(pp["plotImpact"], str):
            raise ValueError(f"T028 {pp['id']} status/plotImpact types are invalid")
        if not isinstance(pp["sideQuests"], list):
            raise ValueError(f"T028 {pp['id']}.sideQuests must be an array")

        for sq in pp["sideQuests"]:
            sq_fields = {
                "id", "title", "description", "involvedLocations", "status",
                "plotImpact",
            }
            if not isinstance(sq, dict) or set(sq) != sq_fields:
                raise ValueError("T028 side quest has missing or extra fields")
            side_quest_ids.append(sq["id"])
            _useful_string(sq["title"], f"{sq['id']}.title")
            _useful_string(sq["description"], f"{sq['id']}.description")
            locations = sq["involvedLocations"]
            if not isinstance(locations, list) or not locations or any(
                location not in valid_areas for location in locations
            ):
                raise ValueError(f"T028 {sq['id']} references an unknown area")
            if not isinstance(sq["status"], str) or not isinstance(sq["plotImpact"], str):
                raise ValueError(f"T028 {sq['id']} status/plotImpact types are invalid")

    expected_sq_ids = [
        f"SQ{index:03d}" for index in range(1, expected_side_quests + 1)
    ]
    if side_quest_ids != expected_sq_ids:
        raise ValueError("T028 side-quest IDs/cardinality must be globally sequential")
    return value


def _validate_plot_hook_updates(value, area_data, valid_plot_ids):
    """Validate T029's exact location and plot references before merging."""
    if not isinstance(value, dict) or set(value) != {"plotHookUpdates"}:
        raise ValueError("T029 requires exactly plotHookUpdates")
    updates = value["plotHookUpdates"]
    if not isinstance(updates, list):
        raise ValueError("T029 plotHookUpdates must be an array")
    valid_locations = {
        location.get("locationId")
        for location in area_data.get("locations", [])
        if isinstance(location, dict) and location.get("locationId")
    }
    seen = set()
    for update in updates:
        if not isinstance(update, dict) or set(update) != {"locationId", "plotHooks"}:
            raise ValueError("T029 update requires exactly locationId and plotHooks")
        location_id = update["locationId"]
        if location_id not in valid_locations or location_id in seen:
            raise ValueError("T029 update has an unknown or duplicate locationId")
        seen.add(location_id)
        hooks = update["plotHooks"]
        if not isinstance(hooks, list) or not hooks or not all(
            isinstance(hook, str) and hook.strip() for hook in hooks
        ):
            raise ValueError("T029 plotHooks must contain useful strings")
        unknown = _flag_unknown_plot_ids(hooks, valid_plot_ids)
        if unknown:
            raise ValueError(f"T029 references unknown plot IDs: {sorted(unknown)}")
    return updates


@dataclass
class BuilderConfig:
    """Configuration for the module building process"""
    module_name: str = ""
    num_areas: int = 3
    locations_per_area: int = 15
    output_directory: str = "./modules"
    verbose: bool = True

class ModuleBuilder:
    """Orchestrates the complete module generation process"""
    
    def __init__(self, config: BuilderConfig):
        self.config = config
        self.module_data = {}
        self.areas_data = {}
        self.locations_data = {}
        self.plots_data = {}
        # The unified module plot (T028) once built. Cross-area connection
        # finalization reads its plot-ordered area sequence so the physical
        # route matches the story, instead of alphabetical area-ID order.
        self.unified_plot = None
        self.context = ModuleContext()
        self.progress_callback = None  # For progress reporting
        self.per_area_locations = None  # For custom locations per area
        
        # Initialize generators
        self.module_gen = ModuleGenerator()
        self.plot_gen = PlotGenerator()
        self.location_gen = LocationGenerator()
        self.area_gen = AreaGenerator()
        
        # Directory ownership belongs to ManagedModuleBuilder (production) or
        # to the explicit low-level caller.  Construction must never create a
        # discoverable public module path as a side effect.
    
    def log(self, message: str):
        """Log messages if verbose mode is enabled"""
        if self.config.verbose:
            timestamp = datetime.now().strftime("%H:%M:%S")
            print(f"DEBUG: [Module Generator] [{timestamp}] {message}")
    
    def _atomic_save_json(self, relative_filename: str, data: Dict[str, Any]) -> bool:
        """Atomic JSON write to self.config.output_directory/<relative_filename>.

        Argument order is intentionally (filename, data) to mirror the legacy
        save_json(data, filename) signature swap and minimize per-callsite
        cognitive load when migrating callers. The underlying
        utils.file_operations.safe_write_json takes (filepath, data).
        """
        filepath = os.path.join(self.config.output_directory, relative_filename)
        result = safe_write_json(filepath, data)
        if not result:
            raise OSError(f"Could not save generated module file: {relative_filename}")
        self.log(f"Saved: {relative_filename}")
        return True
    
    def create_context_header(self, party_members: List[str]) -> str:
        """Create a context header to prepend to all generator prompts"""
        header = """
CRITICAL CONTEXT INFORMATION:
===========================
"""
        if party_members:
            header += f"""PARTY MEMBERS (Heroes who will PLAY this adventure): {', '.join(party_members)}
- These are the PLAYER CHARACTERS, not NPCs
- Do NOT create NPCs with these names
- They are the protagonists traveling TO your locations

"""
        header += """LOCATION CONTEXT:
- The party is CURRENTLY elsewhere (not in your module)
- Create a NEW location they will TRAVEL TO
- This should be a completely different place from their current location
- Give it a unique name and identity

MODULE INDEPENDENCE RULES:
1. This module represents a NEW DESTINATION
2. Party members listed above are PLAYERS, not NPCs
3. Create all-new locations, not variations of existing ones
4. Never reuse character names from the party as NPCs
===========================

"""
        return header
    
    def build_module(self, initial_concept: str):
        """Build a complete module from an initial concept"""
        self.log("Starting module build process...")
        self.log(f"Initial concept: {initial_concept}")
        
        try:
            # Report progress if callback available
            if self.progress_callback:
                self.progress_callback('initializing', 'Getting party members...')
            
            # Get existing characters for context
            existing_characters = self.get_party_members()
            self.context_header = self.create_context_header(existing_characters)
            
            # Report progress
            if self.progress_callback:
                self.progress_callback('base_structure', 'Creating directory structure...')
            
            # Create required directory structure first
            self.create_module_directories()
            
            # Initialize context
            self.context.module_name = self.config.module_name.replace("_", " ")
            self.context.module_id = self.config.module_name
            
            # Step 1: Generate module overview with context
            self.log("Step 1: Generating module overview...")
            if self.progress_callback:
                self.progress_callback('base_structure', 'Generating module overview from AI...')
            
            # Add number of areas to the concept so AI generates the right amount
            contextualized_concept = self.context_header + initial_concept
            contextualized_concept += f"\n\nIMPORTANT: Generate exactly {self.config.num_areas} regions in the worldMap array."
            
            self.module_data = self.module_gen.generate_module(contextualized_concept, context=self.context)
        except Exception as e:
            self.log(f"ERROR in build_module: {e}")
            import traceback
            self.log(f"Traceback: {traceback.format_exc()}")
            raise
        
        # Extract NPCs and factions from module data
        self._extract_module_entities()
        
        # Step 2: Generate areas from the world map
        self.log("Step 2: Generating areas...")
        self.generate_areas()
        
        # Step 3: Generate locations for each area
        self.log("Step 3: Generating locations for each area...")
        self.generate_locations()
        
        # Step 4: Generate plots for each area
        self.log("Step 4: Generating plots for each area...")
        self.generate_plots()

        # Step 4.5: Unify plots into module_plot.json
        self.log("Step 4.5: Creating unified module plot...")
        self.unify_plots()

        # Step 4.55: Create cross-area connections in PLOT order (must run after
        # unify_plots so the physical route matches the story, not alphabetical
        # area-ID order). Location-ID prefixing already happened during generation.
        self.log("Step 4.55: Finalizing cross-area connections in plot order...")
        self.finalize_locations_and_connections()

        # Step 4.6: Update area plot hooks to reference unified plot
        self.log("Step 4.6: Updating area plot hooks...")
        self.update_area_plot_hooks()
        
        # Step 4.7: Inject the antagonist into the climactic location
        self.log("Step 4.7: Mandating antagonist placement...")
        self._inject_antagonist_into_climactic_location()
        
        # Step 5: Generate initial party tracker
        self.log("Step 5: Creating party tracker...")
        self.create_party_tracker()
        
        # Step 6: Create module summary
        self.log("Step 6: Creating module summary...")
        # B6: the summary is a cosmetic human-readable doc and reads many nested
        # fields (module_data/areas_data). A KeyError here -- after all areas, plots
        # and the party tracker are already generated and saved -- would propagate to
        # the cleanup wrapper and DELETE the finished module over a non-critical file.
        # Never let summary generation abort the build.
        try:
            self.create_module_summary()
        except Exception as e:
            warning(f"Module summary generation failed (non-fatal): {e}",
                    category="module_generation")
        
        # Steps 6.5-7 share one context transaction. This publishes the
        # builder's in-memory context before T088, reloads T088's committed
        # result, and prevents the later validation save from restoring the
        # stale pre-reconciliation object.
        self._reconcile_and_validate_context()
        
        # Step 8: Create _BU.json backup files for reset functionality
        self.log("Step 8: Creating _BU.json backup files...")
        self.create_bu_backups()
        
        self.log("Module generation complete!")
        self.log(f"Output saved to: {self.config.output_directory}")

    def _build_story_first_module(self, initial_concept: str, seed, provider: str):
        """Build the dev-flagged path without invoking legacy content stages."""
        from core.generators.story_first.contracts import mutable_copy
        from core.generators.story_first.compatibility import (
            context_npc_name,
            expected_context_projection,
            project_overview,
        )
        from core.generators.story_first.execution import production_completion_gateway
        from core.generators.story_first.pipeline import StoryFirstPipeline
        from core.generators.story_first.settings import (
            GOLD_PRIOR_BLOCKLIST,
            gold_model_config,
        )
        from core.generators.story_first.compilers import safe_filename

        stage_names = (
            "outline",
            "area_binding",
            "plot_derivation",
            "npc_repair",
            "candidate_hardening",
            "creature_compile",
        )
        # Resolve provider support before creating any candidate content. In
        # particular, the not-yet-supported LM Studio path must be side-effect free.
        stage_model_configs = {
            stage: gold_model_config(provider, stage) for stage in stage_names
        }

        self.log("Starting story-first module build process...")
        if self.progress_callback:
            self.progress_callback("initializing", "Preparing story-first workspace...")
        self.context_header = self.create_context_header(
            list(seed.campaign_context.get("partyNames", ()))
        )
        if self._is_resumable_story_first_workspace():
            self.log("Resuming the exact retained story-first workspace...")
        else:
            self.create_module_directories()
        self.context.module_name = self.config.module_name.replace("_", " ")
        self.context.module_id = self.config.module_name

        schema_names = {
            "map": "map_schema.json",
            "plot": "plot_schema.json",
            "location": "loca_schema.json",
            "locationfile": "locationfile_schema.json",
            "monster": "mon_schema.json",
        }
        schemas = {}
        for key, filename in schema_names.items():
            with open(os.path.join("schemas", filename), encoding="utf-8") as handle:
                schemas[key] = json.load(handle)
        pipeline = StoryFirstPipeline(
            candidate_dir=Path(self.config.output_directory),
            provider=provider,
            stage_model_configs=stage_model_configs,
            schemas=schemas,
            blocklist=GOLD_PRIOR_BLOCKLIST,
            gateway=production_completion_gateway,
        )

        if self.progress_callback:
            self.progress_callback(
                "base_structure", "Authoring accepted story outline..."
            )
        accepted_outline = pipeline.accept_outline(seed)
        if self.progress_callback:
            self.progress_callback(
                "base_structure", "Projecting compatible module overview..."
            )
        self.module_data = mutable_copy(project_overview(accepted_outline.value, seed))

        if self.progress_callback:
            self.progress_callback(
                "areas", "Compiling accepted story into game files..."
            )
        result = pipeline.run(seed)
        areas = mutable_copy(result.areas)
        maps = mutable_copy(result.maps)
        plot = mutable_copy(result.plot)
        monsters = mutable_copy(result.monsters)
        if len(areas) != len(maps):
            raise ValueError("story-first area/map cardinality mismatch")

        self.areas_data = {area["areaId"]: area for area in areas}
        self.locations_data = {
            area["areaId"]: {"locations": area["locations"]} for area in areas
        }
        location_to_area = {}
        for area, area_map in zip(areas, maps):
            area_id = area["areaId"]
            if not self._atomic_save_json(f"areas/{area_id}.json", area):
                raise OSError(f"Could not save story-first area {area_id}")
            if not self._atomic_save_json(f"map_{area_id}.json", area_map):
                raise OSError(f"Could not save story-first map {area_id}")
            self.context.add_area(area_id, area["areaName"], area.get("areaType", ""))
            for location in area["locations"]:
                location_id = location["locationId"]
                location_to_area[location_id] = area_id
                self.context.add_location(location_id, location["name"], area_id)
                self.context.locations[location_id]["connections"] = list(
                    location.get("connectivity", [])
                ) + list(location.get("areaConnectivityId", []))
                for npc in location.get("npcs", []):
                    self.context.add_npc(
                        npc["name"],
                        area_id,
                        location_id,
                        description=npc.get("description", ""),
                    )
                    canonical_name = context_npc_name(self.context, npc["name"])
                    if (
                        canonical_name
                        not in self.context.locations[location_id]["npcs"]
                    ):
                        self.context.locations[location_id]["npcs"].append(
                            canonical_name
                        )

        if not self._atomic_save_json("module_plot.json", plot):
            raise OSError("Could not save the story-first module plot")
        self.plots_data = {
            area_id: {
                "plotTitle": plot["plotTitle"],
                "mainObjective": plot["mainObjective"],
                "plotPoints": [],
            }
            for area_id in self.areas_data
        }
        for point in plot["plotPoints"]:
            area_id = location_to_area[point["location"]]
            self.plots_data[area_id]["plotPoints"].append(point)
            self.context.add_plot_point(point["id"], area_id, point["location"])

        for monster in monsters:
            if not self._atomic_save_json(
                f"monsters/{safe_filename(monster['name'])}.json", monster
            ):
                raise OSError(f"Could not save story-first monster {monster['name']}")

        entry = mutable_copy(result.entry)
        self.create_party_tracker(
            start_area_id=entry["entryAreaId"],
            start_location_id=entry["entryLocationId"],
        )
        self.create_module_summary(
            story_first_data={
                "outline": mutable_copy(result.outline),
                "plot": plot,
                "areas": areas,
                "monsters": monsters,
                "entry": entry,
            }
        )
        expected_context = expected_context_projection(
            module_name=self.config.module_name.replace("_", " "),
            module_id=self.config.module_name,
            areas=areas,
            plot=plot,
        )
        self._reconcile_and_validate_context(expected_context=expected_context)
        self.create_bu_backups()
        pipeline.cleanup_workspace()
        self.log("Story-first module generation complete!")
        self.log(f"Output saved to: {self.config.output_directory}")
    
    def _inject_antagonist_into_climactic_location(self):
        """
        Ensures the main antagonist is placed in the final location of the module.
        This works by reading the generated area files and updating them directly.
        """
        self.log("Injecting main antagonist into climactic location...")

        # 1. Identify the main antagonist from the module data
        antagonist_name = self.module_data.get("mainPlot", {}).get("antagonist")
        if not antagonist_name:
            self.log("  - WARNING: No antagonist found in module data. Skipping injection.")
            return
        if not _looks_like_npc_name(antagonist_name):
            warning(
                "Antagonist placement skipped because the antagonist field is "
                "paragraph-shaped rather than name-shaped; model-authored area "
                "content was left unchanged.",
                category="module_generation",
            )
            self.log(
                "  - WARNING: Antagonist field is paragraph-shaped. "
                "Skipping automatic NPC injection without rewriting it."
            )
            return

        # 2. Identify the climactic area by reading the unified plot file
        plot_file_path = os.path.join(self.config.output_directory, "module_plot.json")
        if not os.path.exists(plot_file_path):
            self.log(f"  - WARNING: module_plot.json not found. Cannot determine climactic location.")
            return

        from utils.file_operations import safe_read_json
        unified_plot = safe_read_json(plot_file_path)
        if not unified_plot:
            # safe_read_json returns None on unreadable/corrupt JSON (issue #128) --
            # guard before .get() so we degrade gracefully instead of crashing.
            self.log("  - WARNING: module_plot.json unreadable. Cannot determine climactic location.")
            return
        plot_points = unified_plot.get("plotPoints", [])
        if not plot_points:
            self.log("  - WARNING: No plot points found. Cannot determine climactic location.")
            return

        # The climactic plot point is the last one in the list
        climactic_plot_point = plot_points[-1]
        climactic_area_id = climactic_plot_point.get("location") # This gives us the area ID, e.g., "SD001"

        if not climactic_area_id:
            self.log(f"  - WARNING: No location specified in climactic plot point.")
            return

        # 3. Load the area file
        area_file_path = os.path.join(self.config.output_directory, "areas", f"{climactic_area_id}.json")
        if not os.path.exists(area_file_path):
            self.log(f"  - WARNING: Area file {area_file_path} not found.")
            return
            
        area_data = safe_read_json(area_file_path)
        if not area_data:
            self.log(f"  - WARNING: Could not read area file {area_file_path}.")
            return
        
        # 4. Find the last location in this area
        locations = area_data.get("locations", [])
        if not locations:
            self.log(f"  - WARNING: No locations found in area {climactic_area_id}.")
            return
            
        # The last location is our target
        climactic_location = locations[-1]
        climactic_location_id = climactic_location.get("locationId")

        # 5. Check if antagonist is already there
        npcs = climactic_location.get("npcs", [])
        if any(npc.get("name") == antagonist_name for npc in npcs):
            self.log(f"  - INFO: Antagonist '{antagonist_name}' already present in {climactic_area_id}:{climactic_location_id}.")
            return

        # 6. Create and inject the antagonist NPC
        antagonist_npc_entry = {
            "name": antagonist_name,
            "description": f"The main antagonist of the story, {antagonist_name}.",
            "attitude": "hostile"
        }
        
        climactic_location.setdefault("npcs", []).append(antagonist_npc_entry)
        
        # 7. Save the updated area file (check the atomic-write result -- issue #128:
        #    do not report SUCCESS if the write failed and the antagonist was not persisted)
        if not safe_write_json(area_file_path, area_data):
            self.log(f"  - ERROR: Failed to persist antagonist injection for {climactic_area_id}:{climactic_location_id}.")
            return
        self.log(f"  - SUCCESS: Mandated placement of '{antagonist_name}' in {climactic_area_id}:{climactic_location_id}.")

    def generate_areas(self):
        """Generate detailed area files from the module world map"""
        world_map = self.module_data.get("worldMap", [])
        
        self.log(f"Starting area generation for {self.config.num_areas} areas")
        self.log(f"Default locations per area: {self.config.locations_per_area}")
        if self.per_area_locations:
            self.log(f"Custom per_area_locations provided: {self.per_area_locations}")
        else:
            self.log(f"No custom per_area_locations - using defaults")
        
        for i, region in enumerate(world_map[:self.config.num_areas]):
            # B6: guard against AI-omitted keys in a world_map region. Any missing
            # key here would raise KeyError, propagate to ai_driven_module_creation()'s
            # cleanup wrapper, and DELETE the entire build. The worker already uses
            # this region.get() pattern (module_generator.py:719). Deterministic
            # fallbacks let generation proceed; the stitcher schema gate still flags
            # genuinely broken areas.
            region_name = region.get("regionName") or f"Area {i+1}"
            area_id = region.get("mapId") or f"AREA{i+1:02d}"
            danger_level = region.get("dangerLevel", "Medium")
            recommended_level = region.get("recommendedLevel", 1)

            # Determine area type based on region description
            area_type = self.determine_area_type(region)
            
            # Use custom per-area locations if provided, otherwise use default
            if self.per_area_locations and i < len(self.per_area_locations):
                num_locations_for_area = self.per_area_locations[i]
                self.log(f"Using custom locations for area {i+1}: {num_locations_for_area}")
            else:
                num_locations_for_area = self.config.locations_per_area
            
            config = AreaConfig(
                area_type=area_type,
                size="medium" if i == 0 else ["small", "medium", "large"][i % 3],
                complexity="moderate",
                danger_level=danger_level,
                recommended_level=recommended_level,
                num_locations=num_locations_for_area
            )

            # Add area to context
            self.context.add_area(area_id, region_name, area_type)
            
            # Determine the unique prefix for this area's locations
            prefix = self.get_location_prefix(i)
            
            # Generate area using AreaGenerator
            area_data = self.area_gen.generate_area(
                region_name,
                area_id,
                self.module_data,
                config,
                prefix=prefix
            )
            
            # Validate area consistency after generation
            self.validate_area_consistency(area_data, self.module_data)
            
            self.areas_data[area_id] = area_data
            self._atomic_save_json(f"areas/{area_id}.json", area_data)

            # Save the map separately
            if "map" in area_data:
                self._atomic_save_json(f"map_{area_id}.json", area_data["map"])
            
            # Context will be updated when locations are generated
            self.context.add_area(area_id, region_name, area_data.get("areaType", area_type))

            self.log(f"Generated area: {region_name} ({area_id})")
    
    def determine_area_type(self, region: Dict[str, Any]) -> str:
        """Determine area type based on region description with better pattern matching"""
        description = region.get("regionDescription", "").lower()
        name = region.get("regionName", "").lower()
        
        # Enhanced pattern matching
        if any(word in description + name for word in ["mine", "cave", "dungeon", "ruins", "tomb", "underground", "depths"]):
            return "dungeon"
        elif any(word in description + name for word in ["town", "city", "village", "settlement", "hollow", "borough"]):
            return "town"
        elif any(word in description + name for word in ["forest", "woods", "wilds", "grove", "emerald", "woodland"]):
            return "wilderness"
        elif any(word in description + name for word in ["mountain", "peaks", "marches", "highlands", "cliffs"]):
            return "wilderness" 
        elif any(word in description + name for word in ["swamp", "marsh", "bog", "mire"]):
            return "wilderness"
        else:
            return "mixed"
    
    def validate_area_consistency(self, area_data: Dict[str, Any], module_data: Dict[str, Any]):
        """Validate area descriptions match their names and themes"""
        area_name = area_data.get("areaName", "").lower()
        climate = area_data.get("climate", "")
        terrain = area_data.get("terrain", "")
        
        # Fix obvious mismatches
        if any(word in area_name for word in ["emerald", "wilds", "forest", "woods"]):
            if climate == "desert" or "desert" in terrain:
                self.log(f"WARNING: Fixed climate mismatch for {area_data['areaName']}")
                area_data["climate"] = "temperate"
                area_data["terrain"] = "dense forest with clearings and groves"
        
        if any(word in area_name for word in ["frostward", "marches", "winter", "ice"]):
            if climate == "temperate":
                self.log(f"WARNING: Fixed climate mismatch for {area_data['areaName']}")
                area_data["climate"] = "cold"
                area_data["terrain"] = "frozen tundra and icy peaks"
    
    def get_party_members(self):
        """Get list of existing character names to avoid conflicts"""
        character_names = []
        
        # Try to read from current module's character files first
        try:
            import glob
            # Check current module directory first
            current_module_chars = glob.glob(f"{self.config.output_directory}/characters/*.json")
            
            # If no characters in current module, check all modules
            if not current_module_chars:
                char_files = glob.glob("modules/*/characters/*.json")
            else:
                char_files = current_module_chars
                
            for char_file in char_files:
                try:
                    with open(char_file, 'r') as f:
                        char_data = json.load(f)
                        # Include both player characters and NPCs to avoid naming conflicts
                        char_role = char_data.get('character_role', '')
                        if char_role in ['player', 'npc']:
                            name = char_data.get('name', '').strip()
                            if name and name not in character_names:  # Avoid duplicates
                                character_names.append(name)
                except Exception:
                    continue
        except Exception:
            pass
        
        # No fallback - let each module work with actual characters or none
        if not character_names:
            character_names = []
            self.log("No existing characters detected - module will use generic references")
        
        return character_names
    
    def create_module_directories(self):
        """Initialize only the exact output directory assigned by the caller.

        Name allocation and collision handling belong to ManagedModuleBuilder,
        before this low-level writer runs.  This method never redirects output
        to a sibling path and never writes through pre-existing content.
        """
        output_path = self.config.output_directory
        if os.path.lexists(output_path):
            if os.path.islink(output_path) or not os.path.isdir(output_path):
                raise FileExistsError(
                    f"Explicit module output is not an owned directory: {output_path}"
                )
            try:
                existing_entries = os.listdir(output_path)
            except OSError as exc:
                raise FileExistsError(
                    f"Explicit module output cannot be inspected: {output_path}"
                ) from exc
            if existing_entries:
                raise FileExistsError(
                    f"Explicit module output is not empty: {output_path}"
                )
        else:
            os.makedirs(output_path, exist_ok=False)

        required_dirs = ["characters", "monsters", "encounters", "areas"]

        # Add media directories for module-specific assets
        media_dirs = ["media", "media/monsters", "media/npcs", "media/environment"]

        all_dirs = required_dirs + media_dirs

        for dir_name in all_dirs:
            dir_path = os.path.join(self.config.output_directory, dir_name)
            os.makedirs(dir_path, exist_ok=False)
            self.log(f"Created directory: {dir_name}/")
        
        # Create empty .gitkeep files to preserve directory structure
        for dir_name in all_dirs:
            gitkeep_path = os.path.join(self.config.output_directory, dir_name, ".gitkeep")
            if not os.path.exists(gitkeep_path):
                with open(gitkeep_path, 'w') as f:
                    f.write("# Keep this directory in git\n")

    def _is_resumable_story_first_workspace(self) -> bool:
        """Validate the narrow pre-file-emission tree retained by the pipeline."""
        output = Path(self.config.output_directory)
        if not output.is_dir() or output.is_symlink():
            return False
        entries = {entry.name for entry in output.iterdir()}
        if not entries:
            return False
        expected = {
            ".story_first",
            "areas",
            "characters",
            "encounters",
            "media",
            "monsters",
        }
        if entries != expected:
            raise FileExistsError(
                "Retained story-first workspace contains unexpected entries"
            )
        required_directories = (
            ".story_first",
            "areas",
            "characters",
            "encounters",
            "media",
            "media/environment",
            "media/monsters",
            "media/npcs",
            "monsters",
        )
        for relative in required_directories:
            path = output / relative
            if not path.is_dir() or path.is_symlink():
                raise FileExistsError(
                    "Retained story-first workspace directory is unsafe"
                )
        state = output / ".story_first/pipeline_state.json"
        if not state.is_file() or state.is_symlink():
            raise FileExistsError(
                "Retained story-first workspace has no safe pipeline state"
            )
        allowed_entries = {
            "areas": {".gitkeep"},
            "characters": {".gitkeep"},
            "encounters": {".gitkeep"},
            "media": {".gitkeep", "environment", "monsters", "npcs"},
            "media/environment": {".gitkeep"},
            "media/monsters": {".gitkeep"},
            "media/npcs": {".gitkeep"},
            "monsters": {".gitkeep"},
        }
        for relative, allowed in allowed_entries.items():
            directory = output / relative
            unexpected = [
                item.name for item in directory.iterdir() if item.name not in allowed
            ]
            if unexpected:
                raise FileExistsError(
                    "Retained story-first workspace contains emitted game files"
                )
        return True
    
    def generate_area_map(self, area_id: str) -> Dict[str, Any]:
        """Generate a map layout for an area"""
        # For now, create a simple grid map
        # This would be enhanced with the actual map generator
        return {
            "mapId": area_id,
            "mapName": f"Map of {area_id}",
            "totalRooms": self.config.locations_per_area,
            "layout": self.create_simple_layout(self.config.locations_per_area)
        }
    
    def create_simple_layout(self, num_rooms: int) -> List[List[str]]:
        """Create a simple grid layout for demonstration"""
        # This is a placeholder - real implementation would create
        # a proper dungeon layout
        grid_size = int((num_rooms ** 0.5) + 1)
        layout = []
        room_count = 1
        
        for y in range(grid_size):
            row = []
            for x in range(grid_size):
                if room_count <= num_rooms and (x + y) % 2 == 0:
                    row.append(f"R{room_count:02d}")
                    room_count += 1
                else:
                    row.append("   ")
            layout.append(row)
        
        return layout
    
    def generate_locations(self):
        """Generate detailed locations for each area"""
        # Get existing character names to avoid conflicts
        existing_characters = self.get_party_members()
        self.log(f"Avoiding character name conflicts with: {', '.join(existing_characters)}")
        
        for area_id, area_data in self.areas_data.items():
            self.log(f"Generating locations for area {area_id}...")
            
            # Get the plot data for this area
            plot_data = self.plots_data.get(area_id, {})
            
            # Generate locations using the LocationGenerator with context
            location_data = self.location_gen.generate_locations(
                area_data,
                plot_data,
                self.module_data,
                context=self.context,
                excluded_names=existing_characters,
                context_header=self.context_header
            )
            
            # Store locations data
            self.locations_data[area_id] = location_data

            # Classic generation registered NPC appearances but not their
            # containing locations. Mirror the accepted area data into context
            # exactly as the story-first path does.
            _project_locations_into_context(
                self.context, area_id, location_data.get("locations", [])
            )
            
            # Add locations to area data and save complete area file
            area_data["locations"] = location_data["locations"]
            self._atomic_save_json(f"areas/{area_id}.json", area_data)

            self.log(f"Generated {len(location_data['locations'])} locations for {area_id}")
    
    def generate_plots(self):
        """Generate plot files for each area"""
        # T037 is area-scoped, but legitimate side-quest links may cross
        # areas. Give generation and validation the same complete ID set.
        module_location_data = {
            "locations": [
                location
                for generated_area in self.locations_data.values()
                for location in (generated_area or {}).get("locations", [])
            ]
        }
        valid_location_ids = sorted(
            {
                str(location.get("locationId") or "").strip()
                for location in module_location_data["locations"]
                if str(location.get("locationId") or "").strip()
            }
        )

        for area_id in self.areas_data:
            self.log(f"Generating plot for area {area_id}...")
            
            area_data = self.areas_data[area_id]
            location_data = self.locations_data[area_id]
            
            # Create area-specific context for plot generation
            area_specific_context = f"""
PLOT GENERATION FOR SPECIFIC AREA:
===================================
AREA NAME: {area_data['areaName']}
AREA TYPE: {area_data.get('areaType', 'unknown')}
AREA DESCRIPTION: {area_data.get('areaDescription', '')}
TERRAIN: {area_data.get('terrain', 'unknown')}

IMPORTANT: This plot must be specific to the {area_data['areaName']} area.
The plot title should reference this specific area, not other locations.
Every plotPoints[].location and sideQuests[].involvedLocations value MUST
be one of these exact location IDs: {', '.join(valid_location_ids)}.
The area ID {area_id} is not a location ID and must never be used in those fields.
===================================

{self.context_header}"""

            errors = []
            plot_data = None
            for attempt in range(2):
                attempt_context = area_specific_context
                if errors:
                    attempt_context += (
                        "\nPREVIOUS PLOT VALIDATION ERRORS:\n- "
                        + "\n- ".join(errors)
                        + "\nRegenerate the complete plot. Correct every error and "
                        "use only the exact valid location IDs listed above.\n"
                    )

                plot_data = self.plot_gen.generate_plot(
                    self.module_data,
                    area_data,
                    location_data,
                    f"Create a plot specifically for {area_data['areaName']}, a {area_data.get('areaType', 'region')} area",
                    context=self.context,
                    context_header=attempt_context,
                )

                # MP-C2: reject dangling references before they reach disk.
                # One bounded semantic retry repairs ordinary model slips;
                # repeated invalid output still propagates to the existing
                # fail-closed candidate cleanup wrapper.
                errors = self.plot_gen.validate_plot(
                    plot_data, module_location_data
                )
                if not errors:
                    break
                self.log(
                    f"Plot validation failed for {area_id} "
                    f"(attempt {attempt + 1}/2): {'; '.join(errors)}"
                )

            if errors:
                # Last resort before discarding a fully generated module:
                # repair dangling references, then re-validate. Only a clean
                # re-validation is accepted (issue #133).
                repairs = self.plot_gen.repair_plot_locations(
                    plot_data, module_location_data
                )
                if repairs:
                    errors = self.plot_gen.validate_plot(
                        plot_data, module_location_data
                    )
                    if not errors:
                        self.log(
                            f"Plot for {area_id} repaired rather than discarded: "
                            + "; ".join(repairs)
                        )

            if errors:
                raise ValueError(
                    f"Plot validation failed for {area_id}: {'; '.join(errors)}"
                )

            self.plots_data[area_id] = plot_data
            # Individual plot files removed - using centralized module_plot.json instead

            # Update context with plot points
            for plot_point in plot_data.get("plotPoints", []):
                self.context.add_plot_point(
                    plot_point["id"],
                    area_id,
                    plot_point.get("location")
                )

            self.log(f"Generated plot for {area_id}")
    
    def unify_plots(self):
        """Unify individual area plots into a single module_plot.json using AI"""
        if not self.plots_data:
            self.log("Warning: No plots to unify")
            return
            
        from core.ai import api_client
        import config
        
        # Prepare context for unification
        area_summaries = []
        all_plot_points = []
        all_side_quests = []
        
        for area_id, plot_data in self.plots_data.items():
            area_data = self.areas_data[area_id]
            area_summaries.append({
                "area_id": area_id,
                "area_name": area_data["areaName"],
                "area_type": area_data.get("areaType", "unknown"),
                "recommended_level": area_data.get("recommendedLevel", 1),
                "plot_title": plot_data.get("plotTitle", ""),
                "main_objective": plot_data.get("mainObjective", ""),
                "num_plot_points": len(plot_data.get("plotPoints", []))
            })
            
            # Extract plot points and side quests with area context
            for pp in plot_data.get("plotPoints", []):
                pp_with_context = pp.copy()
                pp_with_context["source_area"] = area_id
                pp_with_context["area_name"] = area_data["areaName"]
                all_plot_points.append(pp_with_context)
                
                for sq in pp.get("sideQuests", []):
                    sq_with_context = sq.copy()
                    sq_with_context["source_area"] = area_id
                    sq_with_context["area_name"] = area_data["areaName"]
                    sq_with_context["parent_plot_point"] = pp["id"]
                    all_side_quests.append(sq_with_context)
        
        # Create AI prompt for unification
        prompt = f"""You are an expert 5th edition module designer. Combine these individual area plots into a single, coherent module-wide plot structure.

MODULE CONTEXT:
- Module Name: {self.module_data.get('moduleName', 'Unknown')}
- Module Description: {self.module_data.get('moduleDescription', '')}
- Total Areas: {len(self.areas_data)}

INDIVIDUAL AREA PLOTS TO UNIFY:
{json.dumps(area_summaries, indent=2)}

ALL PLOT POINTS TO REORGANIZE:
{json.dumps(all_plot_points, indent=2)}

UNIFICATION REQUIREMENTS:
1. Create a single overarching plot title that encompasses the entire module
2. Write a main objective that ties all areas together
3. Reorganize plot points into a logical progression that flows between areas
4. Maintain narrative coherence - each plot point should lead naturally to the next
5. Preserve all existing plot points but reorder/renumber them for better flow
6. Update plot point descriptions to reference connections between areas when appropriate
7. Ensure side quests remain attached to their appropriate plot points
8. Update nextPoints arrays to reflect the new unified progression
9. Consider level progression - easier areas should come before harder ones

RETURN FORMAT:
Return a JSON object with this exact structure:
{{
    "plotTitle": "Unified title for the entire module",
    "mainObjective": "Overarching goal that spans all areas",
    "plotPoints": [
        {{
            "id": "PP001",
            "title": "Plot point title",
            "description": "Detailed description that may reference travel between areas",
            "location": "area_id (like HG001, not R01)",
            "nextPoints": ["PP002"],
            "status": "not started",
            "plotImpact": "",
            "sideQuests": [
                {{
                    "id": "SQ001", 
                    "title": "Side quest title",
                    "description": "Side quest description",
                    "involvedLocations": ["area_id"],
                    "status": "not started",
                    "plotImpact": ""
                }}
            ]
        }}
    ],
    "activeQuests": [],
    "completedQuests": [],
    "failedQuests": [],
    "worldEvents": [],
    "dmNotes": []
}}

IMPORTANT: 
- Use area IDs (like HG001) for location fields, not room IDs (like R01)
- Renumber plot points sequentially starting from PP001
- Renumber side quests GLOBALLY and sequentially starting from SQ001 (SQ001, SQ002, SQ003, etc. across ALL plot points)
- Each side quest must have a unique number across the entire module, not restarting from SQ001 for each plot point
- Maintain all existing content but improve flow and connections"""

        try:
            from model_config import MODEL_PROVIDER
            if MODEL_PROVIDER == "openai":
                main_cfg = config.DM_MAIN_GPT52_NONE
            elif MODEL_PROVIDER == "gemini":
                main_cfg = config.DM_MAIN_GEMINI_PRO_LOW
            elif MODEL_PROVIDER == "lmstudio":
                main_cfg = config.DM_MAIN_LMSTUDIO
            else:  # legacy
                main_cfg = config.DM_MAIN_LEGACY

            last_error = None
            unified_plot = None
            for attempt in range(2):
                response = capture_and_fanout("T028", api_client.create_completion,
                    _request_provider=MODEL_PROVIDER,
                    messages=[
                        {"role": "system", "content": "You are an expert 5th edition module designer specializing in creating coherent, engaging adventure narratives."},
                        {"role": "user", "content": prompt}
                    ],
                    model=main_cfg["model"],
                    temperature=0.7,
                    response_format={"type": "json_object"},
                    **{k: v for k, v in main_cfg.items() if k != "model"})
                try:
                    unified_plot = _validate_unified_plot_contract(
                        json.loads(response.choices[0].message.content),
                        list(self.areas_data),
                        len(all_plot_points),
                        len(all_side_quests),
                    )
                    break
                except (json.JSONDecodeError, TypeError, ValueError) as exc:
                    last_error = exc
                    self.log(
                        f"T028 response failed contract (attempt {attempt + 1}/2): {exc}"
                    )
            if unified_plot is None:
                raise ValueError(f"T028 validation exhausted: {last_error}")

            # Save the unified plot
            output_path = os.path.join(self.config.output_directory, "module_plot.json")
            self._atomic_save_json("module_plot.json", unified_plot)
            # Retain the plot-ordered structure for cross-area connection finalization.
            self.unified_plot = unified_plot

            self.log(f"Created unified module plot with {len(unified_plot.get('plotPoints', []))} plot points")
            
        except Exception as e:
            self.log(f"Error during plot unification: {e}")
            # Fallback: create a simple unified structure
            self._create_fallback_unified_plot()
    
    def _create_fallback_unified_plot(self):
        """Create a simple unified plot if AI unification fails"""
        unified_plot = {
            "plotTitle": self.module_data.get('moduleName', 'Adventure Module'),
            "mainObjective": f"Complete the challenges across {len(self.areas_data)} interconnected areas",
            "plotPoints": [],
            "activeQuests": [],
            "completedQuests": [],
            "failedQuests": [],
            "worldEvents": [],
            "dmNotes": []
        }
        
        # Simple concatenation of all plot points
        plot_counter = 1
        side_quest_counter = 1
        
        for area_id, plot_data in self.plots_data.items():
            for pp in plot_data.get("plotPoints", []):
                new_pp = {
                    "id": f"PP{plot_counter:03d}",
                    "title": pp.get("title", f"Plot Point {plot_counter}"),
                    "description": pp.get("description", ""),
                    "location": area_id,
                    "nextPoints": [f"PP{plot_counter+1:03d}"] if plot_counter < sum(len(p.get("plotPoints", [])) for p in self.plots_data.values()) else [],
                    "status": "not started",
                    "plotImpact": "",
                    "sideQuests": []
                }
                
                # Add side quests
                for sq in pp.get("sideQuests", []):
                    new_sq = {
                        "id": f"SQ{side_quest_counter:03d}",
                        "title": sq.get("title", f"Side Quest {side_quest_counter}"),
                        "description": sq.get("description", ""),
                        "involvedLocations": [area_id],
                        "status": "not started",
                        "plotImpact": ""
                    }
                    new_pp["sideQuests"].append(new_sq)
                    side_quest_counter += 1
                
                unified_plot["plotPoints"].append(new_pp)
                plot_counter += 1

        # issue #128: surface (non-destructively) any cross-area location refs the
        # unified plot can't resolve against the module's real location IDs.
        self._warn_unified_plot_invalid_locations(unified_plot)

        self._atomic_save_json("module_plot.json", unified_plot)
        self.unified_plot = unified_plot
        self.log(f"Created fallback unified plot with {len(unified_plot['plotPoints'])} plot points")

    def _warn_unified_plot_invalid_locations(self, unified_plot):
        """Warn when the unified plot violates its area-ID reference contract."""
        valid_ids = set(self.areas_data)
        if not valid_ids:
            return
        for pp in unified_plot.get("plotPoints", []):
            loc = pp.get("location")
            if loc and loc not in valid_ids:
                self.log(f"  - WARNING: plot point {pp.get('id')} references unknown area '{loc}'")
            for sq in pp.get("sideQuests", []):
                for sloc in sq.get("involvedLocations", []):
                    if sloc and sloc not in valid_ids:
                        self.log(f"  - WARNING: side quest {sq.get('id')} references unknown area '{sloc}'")

    def update_area_plot_hooks(self):
        """Update area plot hooks to reference unified plot using atomic updates with safety guards"""
        # Load the unified plot we just created
        unified_plot_path = os.path.join(self.config.output_directory, "module_plot.json")
        try:
            with open(unified_plot_path, 'r', encoding='utf-8') as f:
                unified_plot = json.load(f)
        except Exception as e:
            self.log(f"Warning: Could not load unified plot for hook updates: {e}")
            return
        
        from core.ai import api_client
        import config

        # Update each area's plot hooks
        for area_id in self.areas_data:
            self._update_single_area_plot_hooks(area_id, unified_plot)

    def _update_single_area_plot_hooks(self, area_id, unified_plot):
        """Atomically update plot hooks for a single area with deep merge and safety guards"""
        from utils.file_operations import safe_read_json

        area_file_path = os.path.join(self.config.output_directory, "areas", f"{area_id}.json")
        
        # STEP 1: Create backup before any changes
        backup_path = f"{area_file_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            shutil.copy2(area_file_path, backup_path)
            self.log(f"Created backup: {backup_path}")
        except Exception as e:
            self.log(f"Warning: Could not create backup for {area_id}: {e}")
        
        # STEP 2: Load original area data with validation
        try:
            original_area_data = safe_read_json(area_file_path)
            if not original_area_data or not isinstance(original_area_data, dict):
                self.log(f"Error: Invalid area data for {area_id}")
                return
        except Exception as e:
            self.log(f"Error: Could not load area {area_id}: {e}")
            return
        
        # STEP 3: Create in-memory backup
        import copy
        area_backup = copy.deepcopy(original_area_data)
        
        # STEP 4: Extract relevant plot points for this area
        relevant_plot_points = []
        relevant_side_quests = []

        # MED-5 (#127): collect every known plot-point/side-quest ID across the
        # whole unified plot so we can warn on hallucinated references later.
        valid_plot_ids = set()
        for pp in unified_plot.get("plotPoints", []):
            pp_id = pp.get("id")
            if pp_id:
                valid_plot_ids.add(pp_id)
            for sq in pp.get("sideQuests", []):
                sq_id = sq.get("id")
                if sq_id:
                    valid_plot_ids.add(sq_id)

        for pp in unified_plot.get("plotPoints", []):
            if pp.get("location") == area_id:
                relevant_plot_points.append({
                    "id": pp["id"],
                    "title": pp["title"],
                    "description": pp["description"]
                })
                
                for sq in pp.get("sideQuests", []):
                    if area_id in sq.get("involvedLocations", []):
                        relevant_side_quests.append({
                            "id": sq["id"],
                            "title": sq["title"],
                            "description": sq["description"]
                        })
        
        if not relevant_plot_points:
            self.log(f"No plot points found for area {area_id}, skipping hook updates")
            return
        
        # STEP 5: Generate updated plot hooks using AI
        try:
            updated_hooks = self._generate_enhanced_plot_hooks(
                area_id,
                original_area_data,
                relevant_plot_points,
                relevant_side_quests
            )
            
            if not updated_hooks:
                self.log(f"No plot hook updates generated for {area_id}")
                return
                
        except Exception as e:
            self.log(f"Error generating plot hooks for {area_id}: {e}")
            return
        
        # STEP 6: Deep merge updates with original data (ATOMIC OPERATION)
        try:
            updated_area_data = self._deep_merge_area_updates(area_backup, updated_hooks, valid_plot_ids)
            
            # STEP 7: Validate critical fields preserved
            if not self._validate_area_integrity(area_backup, updated_area_data, area_id):
                self.log(f"Error: Area integrity check failed for {area_id}, rolling back")
                return
            
            # STEP 8: Atomic write with safety guards (check result -- issue #128:
            #         do not log success if the write failed)
            if not safe_write_json(area_file_path, updated_area_data):
                self.log(f"Error: Failed to persist plot hooks for {area_id}")
                return
            self.log(f"Successfully updated plot hooks for {area_id}")
            
            # STEP 9: Cleanup old backups (keep only 3 most recent)
            self._cleanup_area_backups(area_file_path)
            
        except Exception as e:
            self.log(f"Error during atomic update for {area_id}: {e}")
            # Restore from backup on failure
            try:
                shutil.copy2(backup_path, area_file_path)
                self.log(f"Restored {area_id} from backup due to update failure")
            except:
                self.log(f"Critical error: Could not restore {area_id} from backup")
    
    def _generate_enhanced_plot_hooks(self, area_id, area_data, plot_points, side_quests):
        """Generate enhanced plot hooks that reference specific plot points and side quests"""
        from core.ai import api_client
        import config
        
        # Extract existing plot hooks from all locations in the area
        existing_hooks = []
        for location in area_data.get("locations", []):
            hooks = location.get("plotHooks", [])
            if hooks:
                existing_hooks.extend(hooks)
        
        prompt = f"""You are updating plot hooks for a 5th edition area to reference specific unified plot points.

AREA: {area_data.get('areaName', area_id)} ({area_id})
AREA DESCRIPTION: {area_data.get('areaDescription', '')}

EXISTING PLOT HOOKS TO ENHANCE:
{json.dumps(existing_hooks, indent=2)}

RELEVANT PLOT POINTS FOR THIS AREA:
{json.dumps(plot_points, indent=2)}

RELEVANT SIDE QUESTS FOR THIS AREA:
{json.dumps(side_quests, indent=2)}

TASK: Update the existing plot hooks to specifically reference the unified plot points and side quests.

REQUIREMENTS:
1. Keep the essence and style of existing plot hooks
2. Add specific references to plot point IDs (PP001, PP002, etc.) where appropriate
3. Add references to side quest IDs (SQ001, SQ002, etc.) where appropriate
4. Maintain the narrative tone and area atmosphere
5. Make hooks actionable for DMs
6. Only update plot hooks - do NOT change other area data

RETURN FORMAT:
Return a JSON object with this structure:
{{
  "plotHookUpdates": [
    {{
      "locationId": "R01",
      "plotHooks": [
        "Enhanced hook that mentions PP001 or SQ001 specifically...",
        "Another enhanced hook referencing the unified plot..."
      ]
    }}
  ]
}}

IMPORTANT: 
- Only include locations that need plot hook updates
- Reference specific plot point/side quest IDs where it makes narrative sense
- Preserve the existing hook style and tone
- Make hooks more specific and actionable"""

        try:
            from model_config import MODEL_PROVIDER
            if MODEL_PROVIDER == "openai":
                main_cfg = config.DM_MAIN_GPT52_NONE
            elif MODEL_PROVIDER == "gemini":
                main_cfg = config.DM_MAIN_GEMINI_PRO_LOW
            elif MODEL_PROVIDER == "lmstudio":
                main_cfg = config.DM_MAIN_LMSTUDIO
            else:  # legacy
                main_cfg = config.DM_MAIN_LEGACY

            response = capture_and_fanout("T029", api_client.create_completion,
                _request_provider=MODEL_PROVIDER,
                messages=[
                    {"role": "system", "content": "You are an expert 5th edition module designer specializing in creating actionable plot hooks that reference specific plot elements."},
                    {"role": "user", "content": prompt}
                ],
                model=main_cfg["model"],
                temperature=0.6,
                response_format={"type": "json_object"},
                **{k: v for k, v in main_cfg.items() if k != "model"})

            result = json.loads(response.choices[0].message.content)
            valid_plot_ids = {
                item.get("id")
                for item in [*plot_points, *side_quests]
                if isinstance(item, dict) and item.get("id")
            }
            return _validate_plot_hook_updates(
                result, area_data, valid_plot_ids
            )
            
        except Exception as e:
            self.log(f"Error in AI plot hook generation: {e}")
            return []
    
    def _deep_merge_area_updates(self, original_data, hook_updates, valid_plot_ids=None):
        """Deep merge plot hook updates into area data, preserving all other data"""
        import copy
        result = copy.deepcopy(original_data)

        # Create a lookup for location updates
        location_updates = {}
        for update in hook_updates:
            location_id = update.get("locationId")
            if location_id and "plotHooks" in update:
                location_updates[location_id] = update["plotHooks"]

        # Update only the plot hooks in matching locations
        for location in result.get("locations", []):
            location_id = location.get("locationId")
            if location_id in location_updates:
                location["plotHooks"] = location_updates[location_id]
                # MED-5 (#127): warn on hallucinated plot IDs (non-destructive)
                if valid_plot_ids is not None:
                    try:
                        unknown_ids = _flag_unknown_plot_ids(location["plotHooks"], valid_plot_ids)
                        if unknown_ids:
                            warning(f"T029: location {location_id} references unknown plot IDs: "
                                    f"{sorted(unknown_ids)}", category="module_creation")
                    except Exception:
                        pass

        return result
    
    def _validate_area_integrity(self, original_data, updated_data, area_id):
        """Validate that critical area fields are preserved during update"""
        critical_fields = ["areaId", "areaName", "areaType", "locations", "map"]
        
        for field in critical_fields:
            if field in original_data and field not in updated_data:
                self.log(f"Critical field '{field}' missing in updated {area_id}")
                return False
            
            # Validate locations array structure
            if field == "locations":
                orig_locations = original_data.get("locations", [])
                updated_locations = updated_data.get("locations", [])
                
                if len(orig_locations) != len(updated_locations):
                    self.log(f"Location count mismatch in {area_id}")
                    return False
                
                # Check that each location preserves critical fields
                for orig_loc, updated_loc in zip(orig_locations, updated_locations):
                    location_critical = ["locationId", "name", "type", "description", "npcs", "monsters"]
                    for loc_field in location_critical:
                        if loc_field in orig_loc and loc_field not in updated_loc:
                            self.log(f"Critical location field '{loc_field}' missing in {area_id}")
                            return False
        
        return True
    
    def _cleanup_area_backups(self, area_file_path):
        """Clean up old area backups, keeping only the 3 most recent"""
        try:
            import glob
            backup_pattern = f"{area_file_path}.backup_*"
            backups = glob.glob(backup_pattern)
            
            if len(backups) > 3:
                # Sort by modification time, keep newest 3
                backups.sort(key=os.path.getmtime, reverse=True)
                for old_backup in backups[3:]:
                    os.remove(old_backup)
                    
        except Exception as e:
            self.log(f"Warning: Could not cleanup old backups: {e}")
    
    def create_party_tracker(self, start_area_id=None, start_location_id=None):
        """Create the initial party tracker file"""
        explicit_start = start_area_id is not None or start_location_id is not None
        if explicit_start:
            if not (
                isinstance(start_area_id, str)
                and start_area_id
                and isinstance(start_location_id, str)
                and start_location_id
            ):
                raise ValueError("explicit party start requires both accepted IDs")
            first_area_id = start_area_id
            first_area = self.areas_data.get(first_area_id)
            if (
                not isinstance(first_area, dict)
                or first_area.get("areaId") != first_area_id
            ):
                raise ValueError("explicit party start area is missing or ambiguous")
            first_locations_data = self.locations_data.get(first_area_id, {})
            locations_list = first_locations_data.get("locations", [])
            matches = [
                location
                for location in locations_list
                if isinstance(location, dict)
                and location.get("locationId") == start_location_id
            ]
            if len(matches) != 1:
                raise ValueError(
                    "explicit party start location is missing or ambiguous"
                )
            first_location = matches[0]
        else:
            # Use the first area as the starting location
            first_area_id = list(self.areas_data.keys())[0]
            first_area = self.areas_data[first_area_id]

            # Get the first location from the locations data
            first_locations_data = self.locations_data.get(first_area_id, {})
            locations_list = first_locations_data.get("locations", [])

            if not locations_list:
                # Fallback to a default location
                first_location = {"name": "Starting Location", "locationId": "R01"}
            else:
                first_location = locations_list[0]

        party_tracker = {
            "module": self.config.module_name.replace("_", " "),
            "partyMembers": [],  # Will be populated when players join
            "partyNPCs": [],
            "worldConditions": {
                "year": 1492,  # Standard Forgotten Realms year
                "month": "Firstmonth",  # Generic fantasy January equivalent
                "day": 1,
                "time": "08:00:00",
                "weather": "Clear",
                "season": "Winter",
                "dayNightCycle": "Day",
                "moonPhase": "New Moon",
                "currentLocation": first_location["name"],
                "currentLocationId": first_location["locationId"],
                "currentArea": first_area["areaName"],
                "currentAreaId": first_area["areaId"],
                "majorEventsUnderway": [],
                "politicalClimate": "",
                "activeEncounter": "",
                "activeCombatEncounter": "",
                "weatherConditions": "",
                "lastCompletedEncounter": "",
            },
            "activeQuests": [],
        }

        if explicit_start:
            import jsonschema

            with open("schemas/party_schema.json", encoding="utf-8") as handle:
                jsonschema.validate(party_tracker, json.load(handle))
        saved = self._atomic_save_json("party_tracker.json", party_tracker)
        if explicit_start and not saved:
            raise OSError("Could not save story-first party tracker")
        self.log("Created party tracker")
    
    def create_module_summary(self, story_first_data=None):
        """Create a human-readable module summary"""
        if story_first_data is not None:
            from core.generators.story_first.compatibility import (
                atomic_write_ascii,
                build_story_first_summary,
            )

            summary = build_story_first_summary(**story_first_data)
            summary_path = Path(self.config.output_directory) / "MODULE_SUMMARY.md"
            atomic_write_ascii(summary_path, summary)
            self.log("Created module summary")
            return

        summary = f"""# {self.module_data['moduleName']} - Module Summary

## Overview
{self.module_data['moduleDescription']}

## Module Conflicts
"""
        # Add module conflicts if they exist
        if "moduleConflicts" in self.module_data:
            for conflict in self.module_data["moduleConflicts"]:
                summary += f"- **{conflict['conflictName']}** ({conflict['scope']}): {conflict['description']}\n"

        summary += f"""

## Main Plot
**Objective**: {self.module_data['mainPlot']['mainObjective']}
**Antagonist**: {self.module_data['mainPlot']['antagonist']}

## Areas
"""

        for area_id, area_data in self.areas_data.items():
            plot_data = self.plots_data.get(area_id, {})
            summary += f"""
### {area_data['areaName']} ({area_id})
- **Description**: {area_data['areaDescription']}
- **Danger Level**: {area_data['dangerLevel']}
- **Recommended Level**: {area_data['recommendedLevel']}
- **Locations**: {len(area_data['locations'])}
- **Plot**: {plot_data.get('plotTitle', 'TBD')}
- **Objective**: {plot_data.get('mainObjective', 'TBD')}
"""

        summary += f"""
## Module Structure
- **Total Areas**: {len(self.areas_data)}
- **Total Locations**: {sum(len(area['locations']) for area in self.areas_data.values())}

## Getting Started
1. Players start in {list(self.areas_data.values())[0]['areaName']}
2. Initial quest hook: {self.plots_data[list(self.areas_data.keys())[0]].get('plotPoints', [{}])[0].get('description', 'TBD')}

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

        summary_path = os.path.join(self.config.output_directory, "MODULE_SUMMARY.md")
        with open(summary_path, "w") as f:
            f.write(summary)

        self.log("Created module summary")
    
    def _extract_module_entities(self):
        """Extract NPCs and other entities from module data"""
        # Extract NPCs from plot stages
        for stage in self.module_data.get("mainPlot", {}).get("plotStages", []):
            for npc_name in stage.get("keyNPCs", []):
                self.context.add_npc(npc_name)
                self.context.add_reference("npc", npc_name, "module:plotStages")
        
        # Note: Faction NPCs removed - location-generated NPCs are sufficient

    def _reconcile_and_validate_context(self, expected_context=None):
        """Publish, reconcile, reload, and validate one coherent context."""
        context_path = os.path.join(
            self.config.output_directory,
            "module_context.json",
        )
        reconciler = NpcReconciler(self.config.module_name)
        # ModuleBuilder can use an absolute/custom output directory. Keep the
        # reconciler on that exact directory rather than reconstructing it from
        # the process working directory.
        reconciler.path_manager.module_dir = self.config.output_directory
        reconciler.context_path = context_path

        if expected_context is not None:
            from core.generators.story_first.compatibility import (
                validate_reconciled_context,
            )
            from utils.module_refresh_lock import module_refresh_lock

            with module_refresh_lock() as refresh_acquired:
                if not refresh_acquired:
                    raise OSError("Module refresh is busy during story-first context")
                with path_transaction_lock(context_path):
                    recovery = reconciler._recover_pending_transaction()
                    if recovery:
                        self.log(
                            "Step 6.5: Recovered interrupted NPC reconciliation "
                            f"({recovery})."
                        )
                        self.context = ModuleContext.load(context_path)
                    elif not safe_write_json(context_path, self.context.to_dict()):
                        raise OSError(
                            "Could not publish module context before NPC reconciliation"
                        )

                    self.log("Step 6.5: Reconciling NPC names for consistency...")
                    if not reconciler._reconcile_all_areas_unlocked():
                        raise OSError("NPC identity reconciliation did not commit")
                    self.context = ModuleContext.load(context_path)
                    self.log("Step 7: Validating module consistency...")
                    self.validate_module()
                    validate_reconciled_context(
                        expected_context,
                        self.context.to_dict(),
                    )
            return

        # Lock order MUST be module_refresh -> context, matching the story-first
        # branch above. The reconciler's locked reconcile_all_areas() refuses a
        # caller that holds the context lock without refresh (a refresh->context
        # inversion, npc_reconciler.py:731-738), so a legacy build that took only
        # the context lock here would abort every time with "did not commit".
        # Acquire refresh first, then context, then call the UNLOCKED helper that
        # expects both locks already held.
        from utils.module_refresh_lock import module_refresh_lock

        with module_refresh_lock() as refresh_acquired:
            if not refresh_acquired:
                raise OSError("Module refresh is busy during NPC reconciliation")
            with path_transaction_lock(context_path):
                # Resolve a prior interrupted T088 before considering the builder's
                # in-memory snapshot. Overwriting a staged target first would turn
                # recoverable before/after state into an unsafe third state.
                recovery = reconciler._recover_pending_transaction()
                if recovery:
                    self.log(
                        "Step 6.5: Recovered interrupted NPC reconciliation "
                        f"({recovery})."
                    )
                    self.context = ModuleContext.load(context_path)
                else:
                    if not safe_write_json(context_path, self.context.to_dict()):
                        raise OSError(
                            "Could not publish module context before NPC reconciliation"
                        )

                self.log("Step 6.5: Reconciling NPC names for consistency...")
                if not reconciler._reconcile_all_areas_unlocked():
                    raise OSError("NPC identity reconciliation did not commit")

                # T088 owns a separate ModuleContext instance. Refresh the builder
                # before validation so Step 7 cannot overwrite its identity merge.
                self.context = ModuleContext.load(context_path)
                self.log("Step 7: Validating module consistency...")
                self.validate_module()

    def validate_module(self):
        """Validate module consistency and save results"""
        issues = self.context.validate_all()
        
        if issues:
            self.log(f"Found {len(issues)} validation issues:")
            for issue in issues:
                self.log(f"  - {issue}")
        else:
            self.log("All validation checks passed!")
        
        # Save context and validation report. The caller holds the same T088
        # path lock, and atomic replacement prevents a torn context document.
        context_path = os.path.join(
            self.config.output_directory,
            "module_context.json",
        )
        if not safe_write_json(context_path, self.context.to_dict()):
            raise OSError("Could not save validated module context")
        
        # Create validation report
        report = {
            "validation_date": datetime.now().isoformat(),
            "issues": issues,
            "context_summary": {
                "areas": len(self.context.areas),
                "npcs": len(self.context.npcs),
                "locations": len(self.context.locations),
                "plot_points": len(self.context.plot_scopes)
            }
        }
        self._atomic_save_json("validation_report.json", report)

    def create_bu_backups(self):
        """Create _BU.json backup files for all generated module files"""
        import shutil
        import glob
        
        # Get all JSON files in the module directory (excluding subdirectories first)
        module_files = []
        
        # Get files in root module directory
        root_files = glob.glob(os.path.join(self.config.output_directory, "*.json"))
        module_files.extend(root_files)
        
        # Get files in areas subdirectory
        areas_files = glob.glob(os.path.join(self.config.output_directory, "areas", "*.json"))
        module_files.extend(areas_files)
        
        # Get files in monsters subdirectory
        monsters_files = glob.glob(os.path.join(self.config.output_directory, "monsters", "*.json"))
        module_files.extend(monsters_files)
        
        # Get files in encounters subdirectory
        encounters_files = glob.glob(os.path.join(self.config.output_directory, "encounters", "*.json"))
        module_files.extend(encounters_files)
        
        # Create _BU.json backups for each file
        backup_count = 0
        for json_file in module_files:
            # Skip if it's already a backup file or a character file
            if json_file.endswith("_BU.json") or "/characters/" in json_file:
                continue
                
            # Create backup filename
            backup_file = json_file.replace(".json", "_BU.json")
            
            try:
                shutil.copy2(json_file, backup_file)
                backup_count += 1
                self.log(f"  Created backup: {os.path.relpath(backup_file, self.config.output_directory)}")
            except Exception as e:
                self.log(f"  WARNING: Failed to create backup for {json_file}: {e}")
        
        self.log(f"Created {backup_count} _BU.json backup files for reset functionality")
    
    def get_location_prefix(self, area_index: int) -> str:
        """Get a globally unique prefix for location IDs by checking existing modules"""
        from utils.encoding_utils import safe_json_load
        import os
        
        # Load world registry to check existing location IDs
        used_prefixes = set()
        world_registry_path = "modules/world_registry.json"
        
        if os.path.exists(world_registry_path):
            registry = safe_json_load(world_registry_path)
            if registry:
                # Check all areas in all modules for used location prefixes
                for area_id, area_info in registry.get('areas', {}).items():
                    module_name = area_info.get('module')
                    if module_name:
                        # Load the actual area file to get location IDs
                        area_path = f"modules/{module_name}/areas/{area_id}.json"
                        if os.path.exists(area_path):
                            area_data = safe_json_load(area_path)
                            if area_data and 'locations' in area_data:
                                for loc in area_data['locations']:
                                    loc_id = loc.get('locationId', '')
                                    if loc_id:
                                        # Extract prefix (letters before numbers)
                                        import re
                                        match = re.match(r'^([A-Z]+)\d+', loc_id)
                                        if match:
                                            used_prefixes.add(match.group(1))
        
        # Generate a unique prefix not in use
        candidate_index = area_index
        while True:
            if candidate_index < 26:
                prefix = chr(65 + candidate_index)  # A-Z
            else:
                first_letter = chr(65 + (candidate_index // 26) - 1)
                second_letter = chr(65 + (candidate_index % 26))
                prefix = first_letter + second_letter
            
            if prefix not in used_prefixes:
                self.log(f"Assigned unique location prefix '{prefix}' for area {area_index}")
                return prefix
            
            candidate_index += 1
            if candidate_index > 702:  # Safety limit (26 + 26*26 = 702 possible prefixes)
                # Fallback to module-specific prefix
                import random
                prefix = f"M{self.config.module_name[:3].upper()}{random.randint(1,99)}"
                self.log(f"Warning: Using fallback prefix '{prefix}' due to exhausted standard prefixes")
                return prefix
    
    
    def _create_bidirectional_connection(self, area_files: Dict[str, Any], from_area: str, to_area: str) -> bool:
        """Create a reciprocal cross-area connection between two areas.

        Returns True if a new link was created, False if skipped (missing area,
        no locations, missing IDs, or the link already exists -- idempotent).
        The connection is always written to BOTH endpoints so no one-way
        cross-area edge can ship.
        """
        if from_area not in area_files or to_area not in area_files:
            return False
        if from_area == to_area:
            return False

        # Get exit locations (prefer last locations for progression)
        from_locations = area_files[from_area].get("locations", [])
        to_locations = area_files[to_area].get("locations", [])

        if not from_locations or not to_locations:
            return False

        # Select exit points (use last location in from_area and first in to_area)
        exit_loc = from_locations[-1]
        entrance_loc = to_locations[0]

        # Validate that both locations have locationId
        if "locationId" not in exit_loc or "locationId" not in entrance_loc:
            print(f"DEBUG: [Module Generator] Warning: Missing locationId in connection between {from_area} and {to_area}")
            return False

        exit_loc.setdefault("areaConnectivity", [])
        exit_loc.setdefault("areaConnectivityId", [])
        entrance_loc.setdefault("areaConnectivity", [])
        entrance_loc.setdefault("areaConnectivityId", [])

        # Idempotent: if this exact reciprocal pair already exists, do nothing.
        if (entrance_loc["locationId"] in exit_loc["areaConnectivityId"]
                and exit_loc["locationId"] in entrance_loc["areaConnectivityId"]):
            return False

        # Get the final, refined names of the areas
        from_area_name = area_files[from_area].get("areaName")
        to_area_name = area_files[to_area].get("areaName")

        # from_area exit -> to_area entrance
        if entrance_loc["locationId"] not in exit_loc["areaConnectivityId"]:
            exit_loc["areaConnectivity"].append(to_area_name)
            exit_loc["areaConnectivityId"].append(entrance_loc["locationId"])
        # to_area entrance -> from_area exit (reciprocal)
        if exit_loc["locationId"] not in entrance_loc["areaConnectivityId"]:
            entrance_loc["areaConnectivity"].append(from_area_name)
            entrance_loc["areaConnectivityId"].append(exit_loc["locationId"])

        print(f"DEBUG: [Module Generator] Connected {from_area} location {exit_loc['locationId']} to {to_area} location {entrance_loc['locationId']}")
        return True

    def _plot_ordered_area_transitions(self) -> List[tuple]:
        """Derive ordered, distinct cross-area transitions from the unified plot.

        Walks plotPoints in story order, keeps only their area IDs (T028 stores
        area IDs in ``location``), collapses consecutive duplicates, then returns
        the ordered list of unique undirected (from_area, to_area) transitions.

        This encodes the intended forward route AND hub-and-spoke topology for
        free: a plot that returns to a hub between spokes yields the hub edges
        (A->B, B->A, A->C ... dedupes to {A,B}, {A,C}), while a linear plot
        yields the linear chain. Direction is taken from first appearance
        (the forward progression). Returns [] if the plot has < 2 distinct areas
        (caller then falls back to alphabetical linking).
        """
        plot = self.unified_plot or {}
        valid_areas = set(self.areas_data)
        # area sequence in plot order, restricted to real areas
        seq = []
        for pp in plot.get("plotPoints", []):
            loc = pp.get("location")
            if loc in valid_areas:
                if not seq or seq[-1] != loc:  # collapse consecutive duplicates
                    seq.append(loc)
        if len(set(seq)) < 2:
            return []
        transitions = []
        seen = set()
        for a, b in zip(seq, seq[1:]):
            if a == b:
                continue
            undirected = frozenset((a, b))
            if undirected in seen:
                continue
            seen.add(undirected)
            transitions.append((a, b))  # keep first-seen (forward) direction
        return transitions

    def finalize_locations_and_connections(self):
        """
        Create reciprocal connections between areas. Must run AFTER all locations
        are generated AND after the plot is unified (T028), so cross-area routing
        follows the STORY progression rather than alphabetical area-ID order.

        Root cause fixed here: the previous implementation linked areas in
        ``sorted(area_ids)`` order before any plot existed, which forced the
        physical route to disagree with the plot (e.g. plot SP->OR but doors
        linked OR->SP). We now link along the plot-ordered area transitions and
        fall back to alphabetical only when no usable plot order is available.
        """
        transitions = self._plot_ordered_area_transitions()

        if transitions:
            self.log(f"Finalizing {len(transitions)} cross-area connection(s) in plot order")
            source = "plot order"
        else:
            # Fallback: no usable plot-ordered area sequence (e.g. single-area
            # module, or plot lacked resolvable area references). Preserve the
            # historical alphabetical linear chain so builds never regress.
            sorted_area_ids = sorted(self.areas_data.keys())
            transitions = list(zip(sorted_area_ids, sorted_area_ids[1:]))
            if transitions:
                self.log(f"Finalizing {len(transitions)} cross-area connection(s) "
                         f"in alphabetical fallback order (no plot order available)")
            source = "alphabetical fallback"

        touched = set()
        for from_area_id, to_area_id in transitions:
            if from_area_id not in self.areas_data or to_area_id not in self.areas_data:
                continue
            area_files_for_connection = {
                from_area_id: self.areas_data[from_area_id],
                to_area_id: self.areas_data[to_area_id],
            }
            if self._create_bidirectional_connection(
                    area_files_for_connection, from_area_id, to_area_id):
                touched.add(from_area_id)
                touched.add(to_area_id)

        # Save every area whose connectivity changed (both endpoints of each link).
        for area_id in touched:
            self._atomic_save_json(f"areas/{area_id}.json", self.areas_data[area_id])
        if touched:
            self.log(f"Saved {len(touched)} area file(s) after {source} connection finalization")

def main():
    """Interactive module builder"""
    print("5th Edition Module Builder")
    print("=" * 50)
    
    # Get module configuration
    module_name = input("Module name: ").strip()
    if not module_name:
        module_name = "New_Module"
    
    module_name = module_name.replace(" ", "_")
    
    num_areas = input("Number of areas to generate (default 3): ").strip()
    num_areas = int(num_areas) if num_areas else 3
    
    locations_per_area = input("Locations per area (default 15): ").strip()
    locations_per_area = int(locations_per_area) if locations_per_area else 15
    
    # Get initial concept
    print("\nDescribe your module concept:")
    concept = input("> ").strip()
    if not concept:
        concept = "A classic fantasy adventure with dungeons, monsters, and ancient mysteries"
    
    try:
        success, generated_name = ai_driven_module_creation(
            {
                "concept": concept,
                "module_name": module_name,
                "num_areas": num_areas,
                "locations_per_area": locations_per_area,
            },
            policy="toolkit",
        )
    except ModuleCreationCancelledError:
        print("\nModule generation cancelled; no partial module was published.")
        return
    except ModuleCreationFailedError as build_error:
        print(f"\nModule generation failed: {build_error}")
        print("No partial module was published.")
        return
    if not success or not generated_name:
        print("\nModule generation failed; no partial module was published.")
        return

    print(f"\nModule '{generated_name}' has been generated!")
    print(f"Output directory: ./modules/{generated_name}")
    print("\nYou can now:")
    print("1. Review the MODULE_SUMMARY.md file")
    print("2. Edit any generated files as needed")
    print("3. Start your adventure with main.py")

_MODULE_PARAM_FIELDS = set(MODULE_SPEC_FIELDS)
_MODULE_ADVENTURE_TYPES = set(MODULE_ADVENTURE_TYPES)


def _validate_parsed_module_params(
    parsed: Any,
    policy: Any = GAME_MODULE_POLICY,
) -> Dict[str, Any]:
    """Enforce the exact T030 six-field contract for the selected policy."""

    return ModuleCreationSpec.from_mapping(parsed, policy).to_dict()


def _module_spec_json_schema(policy: ModuleCreationPolicy) -> Dict[str, Any]:
    """Return the provider-neutral strict schema for one T030 policy."""

    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "module_name": {
                "type": "string",
                "minLength": 1,
                "pattern": r"^[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*$",
            },
            "num_areas": {
                "type": "integer",
                "minimum": policy.min_areas,
                "maximum": policy.max_areas,
            },
            "locations_per_area": {
                "type": "integer",
                "minimum": policy.min_locations_per_area,
                "maximum": policy.max_locations_per_area,
            },
            "level_range": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "min": {"type": "integer", "minimum": 1, "maximum": 20},
                    "max": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["min", "max"],
            },
            "adventure_type": {
                "type": "string",
                "enum": sorted(MODULE_ADVENTURE_TYPES),
            },
            "plot_themes": {"type": "string", "minLength": 1},
        },
        "required": sorted(MODULE_SPEC_FIELDS),
    }


def _module_spec_gemini_schema(policy: ModuleCreationPolicy) -> Dict[str, Any]:
    """Return Gemini's schema dialect without weakening T030 bounds."""

    return {
        "type": "OBJECT",
        "properties": {
            "module_name": {"type": "STRING"},
            "num_areas": {
                "type": "INTEGER",
                "minimum": policy.min_areas,
                "maximum": policy.max_areas,
            },
            "locations_per_area": {
                "type": "INTEGER",
                "minimum": policy.min_locations_per_area,
                "maximum": policy.max_locations_per_area,
            },
            "level_range": {
                "type": "OBJECT",
                "properties": {
                    "min": {"type": "INTEGER", "minimum": 1, "maximum": 20},
                    "max": {"type": "INTEGER", "minimum": 1, "maximum": 20},
                },
                "required": ["min", "max"],
            },
            "adventure_type": {
                "type": "STRING",
                "enum": sorted(MODULE_ADVENTURE_TYPES),
            },
            "plot_themes": {"type": "STRING"},
        },
        "required": sorted(MODULE_SPEC_FIELDS),
    }


def parse_narrative_to_module_params(
    narrative: str,
    policy: Any = GAME_MODULE_POLICY,
) -> Dict[str, Any]:
    """Use AI to parse a narrative description into module parameters

    Args:
        narrative: The rich narrative description of the new module

    Returns:
        Dict containing parsed module parameters
    """
    from core.ai import api_client
    import config

    resolved_policy = get_module_creation_policy(policy)

    parsing_prompt = """You are a module configuration parser for the world's most popular 5th edition tabletop role-playing game. Extract adventure module parameters from a narrative description.

Look for these elements in the narrative text:
1. Module name - any title, location name, or adventure theme that could serve as the module title
   - Examples: "Shadows of...", "The Lost...", "Curse of...", or prominent location names
   - Convert to title case with underscores: "The_Lost_Temple", "Shadows_of_Darkwood"
   
2. Number of areas - count distinct locations, regions, or major zones described
   - Look for phrases like: "three regions", "explore the castle, the forest, and the caves" (=3)
   - Each major location mentioned is typically one area
   - If unclear, default to 3
   - The allowed range for this request is %d-%d
   
3. Adventure type - identify the primary environment or mix of environments:
   - "dungeon" = underground, caves, crypts, dungeons
   - "wilderness" = forests, mountains, outdoor exploration  
   - "urban" = cities, towns, political intrigue
   - "nautical" = sea-based, islands, ships
   - "mixed" = combination of above (use this if multiple types)
   
4. Character level range - extract from phrases like:
   - Direct: "for level 4-6 characters", "levels 3 to 5"
   - Indirect: "novice adventurers" (1-3), "seasoned heroes" (5-8), "legendary champions" (15+)
   - If vague or missing, default to 3-5
   
5. Plot themes - extract the main objectives, goals, or story elements:
   - Look for action words: "stop", "rescue", "discover", "defeat", "recover"
   - Keep it concise: "defeat the lich, save the kingdom"
   - Focus on 1-3 main goals, not full descriptions

Return this exact JSON structure:
{
  "module_name": "The_Module_Name_Here",
  "num_areas": 3,
  "locations_per_area": 6,
  "level_range": {"min": 3, "max": 5},
  "adventure_type": "mixed",
  "plot_themes": "defeat evil, rescue prisoners, discover artifact"
}

CRITICAL RULES:
- module_name MUST use underscores, not spaces
- num_areas MUST be a number (not a string)
- num_areas MUST be %d-%d
- locations_per_area MUST be %d-%d (default 6 when allowed)
- level_range MUST have both "min" and "max" as numbers
- adventure_type MUST be lowercase: "dungeon", "wilderness", "urban", "nautical", or "mixed"
- plot_themes must be useful 3-40 word text containing 1-3 comma-separated goals

Return ONLY the JSON object, no explanations or additional text.""" % (
        resolved_policy.min_areas,
        resolved_policy.max_areas,
        resolved_policy.min_areas,
        resolved_policy.max_areas,
        resolved_policy.min_locations_per_area,
        resolved_policy.max_locations_per_area,
    )

    max_retries = 3
    current_prompt = parsing_prompt

    # Select model config per provider (before retry loop)
    from model_config import MODEL_PROVIDER

    if MODEL_PROVIDER == "openai":
        summ_config = config.DM_SUMM_GPT54MINI_NONE
    elif MODEL_PROVIDER == "gemini":
        summ_config = config.DM_SUMM_GEMINI_FLASH_LOW
    elif MODEL_PROVIDER == "lmstudio":
        summ_config = config.DM_SUMM_LMSTUDIO
    else:  # legacy
        summ_config = config.DM_SUMM_LEGACY

    # T030 is constrained at the provider when supported, then checked again by
    # ModuleCreationSpec.  The deterministic check remains authoritative.
    json_schema = _module_spec_json_schema(resolved_policy)
    _extra = {k: v for k, v in summ_config.items() if k != "model"}
    if MODEL_PROVIDER == "gemini":
        _extra["response_schema"] = _module_spec_gemini_schema(resolved_policy)
    elif MODEL_PROVIDER in {"openai", "legacy"}:
        _extra["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "module_creation_spec",
                "strict": True,
                "schema": json_schema,
            },
        }

    last_error = None
    for attempt in range(max_retries):
        try:
            response = capture_and_fanout(
                "T030",
                api_client.create_completion,
                _request_provider=MODEL_PROVIDER,
                messages=[
                    {"role": "system", "content": current_prompt},
                    {
                        "role": "user",
                        "content": f"Parse this module narrative:\n\n{narrative}",
                    },
                ],
                model=summ_config["model"],
                temperature=0.3,
                **_extra,
            )

            result = response.choices[0].message.content.strip()
            # Clean up potential code blocks
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                result = result.split("```")[1].split("```")[0].strip()

            parsed = _validate_parsed_module_params(json.loads(result), resolved_policy)

            debug(
                f"AI_PROCESSING: AI parsed narrative into: {json.dumps(parsed, indent=2)}",
                category="module_creation",
            )
            return parsed

        except (json.JSONDecodeError, ValueError) as e:
            last_error = e
            if attempt < max_retries - 1:
                print(
                    f"DEBUG: [Module Generator] Parse attempt {attempt + 1} failed: {e}"
                )
                # Update prompt with error feedback for next attempt
                current_prompt = (
                    parsing_prompt
                    + f"\n\nPREVIOUS ERROR: {e}\nPlease ensure all fields are present with correct types."
                )
                continue
            else:
                print(
                    f"DEBUG: [Module Generator] ERROR: Failed to parse after {max_retries} attempts: {e}"
                )

        except api_client.ProviderCallError as e:
            # ProviderCallError subclasses RuntimeError, so it used to miss the
            # retry branch above and abort the build on the first blip
            # (issue #132).
            last_error = e
            if _is_auth_error(e):
                raise ModuleCreationFailedError(
                    "The AI provider rejected the request: the API key is "
                    "missing or invalid. Add a valid key in Settings, then "
                    "try again."
                ) from e
            if attempt < max_retries - 1:
                backoff = 2**attempt
                print(
                    f"DEBUG: [Module Generator] Provider error on attempt "
                    f"{attempt + 1}: {e}. Retrying in {backoff}s..."
                )
                time.sleep(backoff)
                continue
            print(
                f"DEBUG: [Module Generator] ERROR: Provider still failing after "
                f"{max_retries} attempts: {e}"
            )

        except Exception as e:
            last_error = e
            print(
                f"DEBUG: [Module Generator] ERROR: Unexpected error parsing narrative: {e}"
            )
            break

    if isinstance(last_error, api_client.ProviderCallError):
        # Do not blame the specification when the provider never answered.
        raise ModuleCreationFailedError(
            f"The AI provider failed after {max_retries} attempts: {last_error}"
        ) from last_error

    raise ModuleCreationContractError(
        f"T030 could not produce a valid module specification after {max_retries} attempts"
    ) from last_error


def _resolve_module_creation_spec(
    narrative: str,
    params: Dict[str, Any],
    policy: Any,
) -> ModuleCreationSpec:
    """Resolve labels and inference into one validated specification."""

    resolved_policy = get_module_creation_policy(policy)
    explicit = extract_labeled_module_values(narrative, resolved_policy)

    typed_fields = MODULE_SPEC_FIELDS.intersection(params)
    if typed_fields and resolved_policy.name != "toolkit":
        raise ModuleCreationContractError(
            "typed module overrides are available only to the toolkit policy"
        )
    if resolved_policy.name == "toolkit":
        # Explicit toolkit controls are authoritative, including falsey invalid
        # values, because extraction uses `is not None` rather than `or`.
        explicit.update(extract_typed_module_overrides(params, resolved_policy))

    if set(explicit) == MODULE_SPEC_FIELDS:
        return ModuleCreationSpec.from_mapping(explicit, resolved_policy)

    inferred = parse_narrative_to_module_params(narrative, resolved_policy)
    resolved = dict(inferred)
    resolved.update(explicit)
    return ModuleCreationSpec.from_mapping(resolved, resolved_policy)


def _ai_driven_module_creation_impl(
    params: Dict[str, Any],
    progress_callback=None,
    *,
    policy: Any = "game",
    prepare_candidate: Optional[Callable[[Path, str], Any]] = None,
) -> tuple[bool, Optional[str]]:
    """Build one validated module through the hidden managed lifecycle.

    Args:
        params: Narrative plus optional snake-case typed toolkit values.
        progress_callback: Optional callback function for progress updates
        policy: ``game`` for the DM action or ``toolkit`` for manual builds.

    Returns:
        tuple[bool, Optional[str]]: (success_status, module_name)
        The returned name is the lifecycle's exact allocated final name. Game
        builds remain hidden in READY until the publication owner commits them.
    """
    module_name = None
    try:
        if not isinstance(params, dict):
            raise ModuleCreationContractError(
                "module creation parameters must be an object"
            )
        resolved_policy = get_module_creation_policy(policy)

        # Report progress if callback provided
        if progress_callback:
            progress_callback(
                {
                    "stage": 0,
                    "total_stages": 9,
                    "stage_name": "Initializing",
                    "percentage": 0,
                    "message": "Starting module creation...",
                }
            )
        # Check if we have a narrative to parse
        narrative = params.get("narrative") or params.get("concept")
        if not narrative:
            raise ModuleCreationFailedError(
                "A module concept or narrative is required."
            )

        # Resolve labeled values before inference.  A complete explicit block
        # skips T030; otherwise validated explicit values override inference.
        if progress_callback:
            progress_callback(
                {
                    "stage": 1,
                    "total_stages": 9,
                    "stage_name": "Parsing narrative",
                    "percentage": 11,
                    "message": "Analyzing narrative to extract module parameters...",
                }
            )
        spec = _resolve_module_creation_spec(narrative, params, resolved_policy)
        from core.generators.story_first.settings import story_first_enabled

        use_story_first = story_first_enabled()
        story_first_provider = None
        if use_story_first:
            from model_config import get_provider

            story_first_provider = get_provider()
        module_name = spec.module_name
        num_areas = spec.num_areas
        locations_per_area = spec.locations_per_area
        level_range = spec.level_range
        adventure_type = spec.adventure_type
        plot_themes = spec.plot_themes
        per_area_locations = params.get("per_area_locations")
        if per_area_locations is not None:
            if resolved_policy.name != "toolkit":
                raise ModuleCreationContractError(
                    "per_area_locations is available only to the toolkit policy"
                )
            if (
                not isinstance(per_area_locations, list)
                or len(per_area_locations) != num_areas
                or any(
                    type(value) is not int
                    or not (
                        resolved_policy.min_locations_per_area
                        <= value
                        <= resolved_policy.max_locations_per_area
                    )
                    for value in per_area_locations
                )
            ):
                raise ModuleCreationContractError(
                    "per_area_locations must contain one valid integer per area"
                )
            if use_story_first:
                raise ModuleCreationContractError(
                    "per_area_locations is not supported by the story-first path yet"
                )

        # Enhance the concept with AI-provided context
        enhanced_concept = f"{narrative}"
        if adventure_type:
            enhanced_concept += f" This is primarily a {adventure_type} adventure."
        if level_range:
            enhanced_concept += f" Designed for characters level {level_range.get('min', 3)} to {level_range.get('max', 5)}."
        if plot_themes:
            enhanced_concept += f" Key themes include: {plot_themes}."

        debug(
            f"MODULE_CREATION: AI-driven module creation starting for '{module_name}'",
            category="module_creation",
        )

        from core.generators.managed_module_builder import ManagedModuleBuilder
        from utils.module_lifecycle import LifecycleIndeterminateError, LifecycleKind

        kind = (
            LifecycleKind.ACTION
            if resolved_policy.name == "game"
            else LifecycleKind.TOOLKIT
        )

        def build_candidate(
            candidate_path: Path,
            final_name: str,
            *,
            story_first_path: bool,
        ) -> Dict[str, Any]:
            if progress_callback:
                progress_callback(
                    {
                        "stage": 2,
                        "total_stages": 9,
                        "stage_name": "Configuring builder",
                        "percentage": 22,
                        "message": f"Setting up module: {final_name}...",
                    }
                )

            config = BuilderConfig(
                module_name=final_name,
                num_areas=num_areas,
                locations_per_area=locations_per_area,
                output_directory=os.fspath(candidate_path),
                verbose=True,
            )
            if progress_callback:
                progress_callback(
                    {
                        "stage": 3,
                        "total_stages": 9,
                        "stage_name": "Creating builder",
                        "percentage": 33,
                        "message": "Initializing module builder...",
                    }
                )
            builder = ModuleBuilder(config)
            if per_area_locations is not None:
                builder.per_area_locations = list(per_area_locations)

            if progress_callback:

                def wrapped_callback(status, message):
                    """Convert the low-level callback to the web progress shape."""
                    stage_map = {
                        "initializing": 4,
                        "base_structure": 5,
                        "areas": 5,
                        "plot": 6,
                        "npcs": 6,
                        "finalizing": 7,
                    }
                    stage = stage_map.get(status, 5)
                    progress_callback(
                        {
                            "stage": stage,
                            "total_stages": 9,
                            "stage_name": status.title(),
                            "percentage": int((stage / 9) * 100),
                            "message": message,
                        }
                    )

                builder.progress_callback = wrapped_callback

            if progress_callback:
                progress_callback(
                    {
                        "stage": 4,
                        "total_stages": 9,
                        "stage_name": "Building module",
                        "percentage": 44,
                        "message": "Starting module generation process...",
                    }
                )
            if story_first_path:
                from core.generators.story_first.contracts import StorySeed

                story_seed = StorySeed(
                    seed_id=final_name,
                    concept=narrative,
                    module_controls={
                        "numAreas": num_areas,
                        "locationsPerArea": locations_per_area,
                        "levelMin": level_range.get("min", 3),
                        "levelMax": level_range.get("max", 5),
                        "adventureType": adventure_type,
                        "plotThemes": plot_themes,
                    },
                    campaign_context={
                        "partyNames": builder.get_party_members(),
                    },
                )
                builder._build_story_first_module(
                    enhanced_concept,
                    story_seed,
                    story_first_provider,
                )
            else:
                builder.build_module(enhanced_concept)

            assigned_path = candidate_path.resolve(strict=False)
            actual_path = Path(builder.config.output_directory).resolve(strict=False)
            if builder.config.module_name != final_name or actual_path != assigned_path:
                raise LifecycleIndeterminateError(
                    "Low-level module builder escaped its assigned identity"
                )

            if progress_callback:
                progress_callback(
                    {
                        "stage": 7,
                        "total_stages": 9,
                        "stage_name": "Finalizing",
                        "percentage": 77,
                        "message": "Finalizing module data...",
                    }
                )

            plot_file_path = candidate_path / "module_plot.json"
            if not plot_file_path.exists():
                unified_plot = {
                    "plotTitle": builder.module_data.get(
                        "moduleName", final_name.replace("_", " ")
                    ),
                    "mainObjective": builder.module_data.get("mainPlot", {}).get(
                        "mainObjective", "Complete the adventure"
                    ),
                    "plotPoints": [],
                }
                plot_id_counter = 1
                for area_id, plot_data in builder.plots_data.items():
                    for source_point in plot_data.get("plotPoints", []):
                        plot_point = dict(source_point)
                        plot_point["id"] = f"PP{plot_id_counter:03d}"
                        plot_point["areaId"] = area_id
                        unified_plot["plotPoints"].append(plot_point)
                        plot_id_counter += 1
                if not safe_write_json(str(plot_file_path), unified_plot):
                    raise OSError("Could not create the unified module plot")
                info(
                    "SUCCESS: Created unified module_plot.json with "
                    f"{len(unified_plot['plotPoints'])} plot points",
                    category="module_creation",
                )
            return {"output_directory": os.fspath(candidate_path)}

        managed = ManagedModuleBuilder(modules_dir=Path("modules"))
        result = _run_managed_module_build(
            managed=managed,
            requested_name=module_name,
            kind=kind,
            story_first_candidate=lambda candidate_path, final_name: build_candidate(
                candidate_path,
                final_name,
                story_first_path=True,
            ),
            compatible_candidate=lambda candidate_path, final_name: build_candidate(
                candidate_path,
                final_name,
                story_first_path=False,
            ),
            prepare_candidate=prepare_candidate,
            defer_promotion=(kind is LifecycleKind.ACTION),
            use_story_first=use_story_first,
            progress_callback=progress_callback,
        )
        module_name = result.module_name
        info(
            f"SUCCESS: Module '{module_name}' generated with status "
            f"{result.status.value}",
            category="module_creation",
        )

        if progress_callback:
            progress_callback(
                {
                    "stage": 8,
                    "total_stages": 9,
                    "stage_name": "Generated",
                    "percentage": 88,
                    "status": "running",
                    "terminal": False,
                    "message": f"Module {module_name} generated; awaiting publication...",
                }
            )

        return True, module_name

    except (ModuleCreationRecoveryRequiredError, ModuleCreationCancelledError):
        raise
    except Exception as e:
        print(
            f"DEBUG: [Module Generator] ERROR: AI-driven module creation failed: {str(e)}"
        )
        import traceback

        traceback.print_exc()
        error(
            f"Module creation failed for '{module_name}': {e}",
            exception=e,
            category="module_creation",
        )
        # ManagedModuleBuilder retires only its exact UUID-owned workspace.
        # No path-derived recursive cleanup is permitted here.
        #
        # Carry the reason out instead of returning (False, None): callers used
        # to receive a bare failure and could only report "Module generation
        # failed" (issue #130).
        raise ModuleCreationFailedError(str(e)) from e


def ai_driven_module_creation(
    params: Dict[str, Any],
    progress_callback=None,
    *,
    policy: Any = "game",
    prepare_candidate: Optional[Callable[[Path, str], Any]] = None,
) -> tuple[bool, Optional[str]]:
    """Run a module build inside exactly one nested-safe usage scope.

    The in-game action owns a wider scope that continues through publication,
    so this wrapper must not record a premature terminal event when a context is
    already active.  Direct toolkit callers receive their own build-only scope
    and a sanitized ``generated`` or ``failed`` terminal outcome.
    """

    from utils.openai_usage_tracker import (
        get_module_build_usage_context,
        mark_module_build_outcome,
        module_build_usage_scope,
    )

    owns_usage_scope = get_module_build_usage_context() is None
    with module_build_usage_scope():
        try:
            result = _ai_driven_module_creation_impl(
                params,
                progress_callback=progress_callback,
                policy=policy,
                prepare_candidate=prepare_candidate,
            )
        except Exception:
            if owns_usage_scope:
                mark_module_build_outcome("failed")
            raise

        if owns_usage_scope:
            mark_module_build_outcome("generated" if result[0] else "failed")
        return result


if __name__ == "__main__":
    main()
