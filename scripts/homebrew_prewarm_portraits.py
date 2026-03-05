#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest CLI - Homebrew Portrait Prewarm
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Prewarms NPC and monster portraits for homebrew modules after strict ingest.
Fail-open on provider errors, skip existing portraits.
Explicit module targeting (not active runtime module).

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import argparse
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def _normalize_name(name: str) -> str:
    """Convert name to filesystem-safe normalized key."""
    lowered = str(name).strip().lower()
    normalized = re.sub(r"[^a-z0-9_]+", "_", lowered).strip("_")
    return normalized


def _load_monster_match_set() -> List[str]:
    """Load deterministic monster match set from bestiary plus common terms."""
    monster_names = set()
    bestiary_path = Path("data/bestiary/monster_compendium.json")

    try:
        if bestiary_path.exists():
            data = json.loads(bestiary_path.read_text(encoding="utf-8"))
            for key, entry in data.get("monsters", {}).items():
                name = entry.get("name", key)
                monster_names.add(str(name).lower())
                monster_names.add(str(key).replace("_", " ").lower())
    except Exception:
        pass

    # Conservative supplemental names commonly seen in imported prose
    monster_names.update({
        "bronze golem", "giant snake", "sea troll", "brown mold",
        "giant bird", "venomous snake", "shrieker mushroom", "banelar",
    })

    # Deterministic ordering: longer names first to prefer specific matches
    return sorted(monster_names, key=lambda n: (-len(n), n))


def _extract_monsters_from_text(text: str, monster_candidates: List[str]) -> List[str]:
    """Extract monster names from free text using deterministic matching."""
    text_norm = re.sub(r"\s+", " ", text.lower())
    found = set()

    for name in monster_candidates:
        # Conservative filter: fallback prose matching only for multi-word names
        if " " not in name:
            continue
        # word-boundary style matching with simple plural tolerance
        pattern = r"\b" + re.escape(name) + r"s?\b"
        if re.search(pattern, text_norm):
            found.add(name.title())

    return sorted(found)


def _discover_npcs(module_slug: str) -> List[Dict[str, Any]]:
    """Discover NPC entities from seed file or module context.
    
    TABLETOP MODE: Prioritizes npcs_seed.json as single source of truth.
    Falls back to module_context.json only when seed absent.
    """
    npcs = []
    module_path = Path(f"modules/{module_slug}")
    
    # Priority 1: Seed file (deterministic import extraction)
    seed_path = module_path / "npcs_seed.json"
    if seed_path.exists():
        try:
            seed_data = json.loads(seed_path.read_text())
            npc_data = seed_data.get("npcs", {})
            for npc_id, npc_info in npc_data.items():
                if isinstance(npc_info, dict):
                    name = npc_info.get("name", npc_id)
                    description = npc_info.get("description", "")
                else:
                    name = npc_id
                    description = str(npc_info) if npc_info else ""
                npcs.append({
                    "id": npc_id,
                    "name": name,
                    "description": description,
                    "type": "npc"
                })
            return npcs
        except Exception:
            pass
    
    # Priority 2: Module context fallback
    context_path = module_path / "module_context.json"
    if not context_path.exists():
        return npcs
    
    try:
        data = json.loads(context_path.read_text())
        npc_data = data.get("npcs", {})
        
        for npc_id, npc_info in npc_data.items():
            if isinstance(npc_info, dict):
                name = npc_info.get("name", npc_id)
                description = npc_info.get("description", "")
            else:
                name = npc_id
                description = str(npc_info) if npc_info else ""
            
            npcs.append({
                "id": npc_id,
                "name": name,
                "description": description,
                "type": "npc"
            })
    except Exception:
        pass
    
    return npcs


def _discover_monsters(module_slug: str) -> List[Dict[str, Any]]:
    """Discover monster entities from seed file, context, or area files.
    
    TABLETOP MODE: Prioritizes monsters_seed.json as single source of truth.
    Falls back to module_context.json, then explicit encounter creatures.
    Conservative prose scan only as last resort (multi-word only).
    """
    monsters = []
    module_path = Path(f"modules/{module_slug}")
    monster_names: set = set()
    
    # Priority 1: Seed file (deterministic import extraction)
    seed_path = module_path / "monsters_seed.json"
    if seed_path.exists():
        try:
            seed_data = json.loads(seed_path.read_text())
            seed_monsters = seed_data.get("monsters", [])
            for name in seed_monsters:
                if isinstance(name, str):
                    monster_names.add(name)
            # If seed has monsters, use only seed (don't merge with broader scans)
            if monster_names:
                for name in sorted(monster_names):
                    monsters.append({
                        "id": _normalize_name(name),
                        "name": name,
                        "description": f"A {name}",
                        "type": "monster"
                    })
                return monsters
        except Exception:
            pass
    
    # Priority 2: Module context references
    context_path = module_path / "module_context.json"
    context_npcs_empty = True
    context_monsters_empty = True
    
    if context_path.exists():
        try:
            data = json.loads(context_path.read_text())
            context_npcs_empty = not bool(data.get("npcs", {}))
            refs = data.get("references", {})
            monster_list = refs.get("monsters", [])
            context_monsters_empty = not bool(monster_list)
            for m in monster_list:
                if isinstance(m, str):
                    monster_names.add(m)
                elif isinstance(m, dict):
                    name = m.get("name") or m.get("id")
                    if name:
                        monster_names.add(name)
        except Exception:
            pass
    
    # Priority 3: Explicit encounter creatures in area files
    areas_path = module_path / "areas"
    if areas_path.exists():
        for area_file in areas_path.glob("*.json"):
            try:
                area_data = json.loads(area_file.read_text())
                locations = area_data.get("locations", [])
                for loc in locations:
                    encounters = loc.get("encounters", [])
                    for enc in encounters:
                        creatures = enc.get("creatures", [])
                        for creature in creatures:
                            name = creature.get("name") if isinstance(creature, dict) else creature
                            if name:
                                monster_names.add(name)
            except Exception:
                pass
    
    # Priority 4 (Last resort): Conservative prose scan only when context/seed empty
    # and only for multi-word monster names to avoid false positives
    if context_npcs_empty and context_monsters_empty and areas_path.exists():
        candidates = _load_monster_match_set()
        for area_file in areas_path.glob("*.json"):
            try:
                area_data = json.loads(area_file.read_text(encoding="utf-8"))
                for loc in area_data.get("locations", []):
                    prose = " ".join([
                        str(loc.get("name", "")),
                        str(loc.get("description", "")),
                        str(loc.get("creatures", "")),
                    ])
                    for name in _extract_monsters_from_text(prose, candidates):
                        monster_names.add(name)
            except Exception:
                pass
    
    # Convert to structured list
    for name in sorted(monster_names):
        monsters.append({
            "id": _normalize_name(name),
            "name": name,
            "description": f"A {name}",
            "type": "monster"
        })
    
    return monsters


def _portrait_exists(module_slug: str, entity_name: str, entity_type: str) -> bool:
    """Check if portrait already exists for entity in target module media paths."""
    module_path = Path(f"modules/{module_slug}")
    normalized = _normalize_name(entity_name)
    
    if entity_type == "npc":
        portrait_dir = module_path / "media" / "npcs"
    else:
        portrait_dir = module_path / "media" / "monsters"
    
    if not portrait_dir.exists():
        return False
    
    # Check for .jpg or .png in module media directory
    for ext in [".jpg", ".jpeg", ".png"]:
        if (portrait_dir / f"{normalized}{ext}").exists():
            return True
        # Also check _full variants
        if (portrait_dir / f"{normalized}_full{ext}").exists():
            return True
    
    return False


def _resolve_monster_media(
    module_slug: str,
    monster_name: str
) -> Tuple[Optional[str], Optional[Path]]:
    """Resolve monster media from ordered source chain.
    
    Source order:
    1) module media (modules/<slug>/media/monsters/)
    2) static media (web/static/media/monsters/)
    3) graphic-pack/toolkit assets (if available)
    4) None (requires provider generation)
    
    Video-first: prefers *_video.mp4 over images.
    
    Returns: (source_type, media_path) where source_type is one of:
        'reused_module', 'reused_static', 'reused_pack', or None
    """
    normalized = _normalize_name(monster_name)
    
    # Source 1: Module media (highest priority)
    module_media_path = Path(f"modules/{module_slug}/media/monsters")
    if module_media_path.exists():
        # Video-first check
        video_path = module_media_path / f"{normalized}_video.mp4"
        if video_path.exists():
            return ("reused_module", video_path)
        # Image fallback
        for ext in [".jpg", ".jpeg", ".png"]:
            img_path = module_media_path / f"{normalized}{ext}"
            if img_path.exists():
                return ("reused_module", img_path)
            # Also check _full variants
            full_path = module_media_path / f"{normalized}_full{ext}"
            if full_path.exists():
                return ("reused_module", full_path)
    
    # Source 2: Static media
    static_media_path = Path("web/static/media/monsters")
    if static_media_path.exists():
        # Video-first check
        video_path = static_media_path / f"{normalized}_video.mp4"
        if video_path.exists():
            return ("reused_static", video_path)
        # Image fallback
        for ext in [".jpg", ".jpeg", ".png"]:
            img_path = static_media_path / f"{normalized}{ext}"
            if img_path.exists():
                return ("reused_static", img_path)
            full_path = static_media_path / f"{normalized}_full{ext}"
            if full_path.exists():
                return ("reused_static", full_path)
    
    # Source 3: Graphic-pack/toolkit assets (bestiary)
    bestiary_media_path = Path("data/bestiary/media/monsters")
    if bestiary_media_path.exists():
        # Video-first check
        video_path = bestiary_media_path / f"{normalized}_video.mp4"
        if video_path.exists():
            return ("reused_pack", video_path)
        # Image fallback
        for ext in [".jpg", ".jpeg", ".png"]:
            img_path = bestiary_media_path / f"{normalized}{ext}"
            if img_path.exists():
                return ("reused_pack", img_path)
    
    # No existing media found - requires generation
    return (None, None)


def _generate_and_materialize_portrait(
    module_slug: str,
    entity: Dict[str, Any],
    timeout_seconds: int = 120,
    suppress_output: bool = True
) -> Tuple[bool, Optional[str]]:
    """Generate portrait and materialize to target module. Returns (success, error_message)."""
    import io
    import contextlib
    
    try:
        # Import here to handle import errors gracefully
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from core.toolkit.portrait_service import (
            generate_and_save_portrait,
            materialize_npc_media_from_portrait,
            materialize_monster_media_from_portrait,
        )
        
        # Build minimal character data
        character_data = {
            "name": entity["name"],
            "description": entity.get("description", ""),
            "type": entity["type"],
        }
        
        # Add appearance hints if available
        if entity["type"] == "monster":
            character_data["appearance"] = entity.get("description", "")
        
        # Suppress stdout to keep JSON output clean
        if suppress_output:
            stdout_buffer = io.StringIO()
            with contextlib.redirect_stdout(stdout_buffer):
                # Generate portrait (goes to static portraits + active module portraits via service)
                result = generate_and_save_portrait(
                    character_data=character_data,
                    model="dall-e-3",
                    size="1024x1024",
                    quality="standard"
                )
        else:
            result = generate_and_save_portrait(
                character_data=character_data,
                model="dall-e-3",
                size="1024x1024",
                quality="standard"
            )
        
        if not result.get("success"):
            return False, result.get("error", "Unknown generation error")
        
        # Now materialize to target module with explicit module_slug
        # This ensures portrait ends up in modules/<slug>/media/... not active module
        if suppress_output:
            stdout_buffer = io.StringIO()
            with contextlib.redirect_stdout(stdout_buffer):
                if entity["type"] == "npc":
                    mat_result = materialize_npc_media_from_portrait(
                        npc_name=entity["name"],
                        module_name=module_slug  # Explicit target, not active module
                    )
                else:
                    mat_result = materialize_monster_media_from_portrait(
                        monster_name=entity["name"],
                        module_name=module_slug  # Explicit target, not active module
                    )
        else:
            if entity["type"] == "npc":
                mat_result = materialize_npc_media_from_portrait(
                    npc_name=entity["name"],
                    module_name=module_slug
                )
            else:
                mat_result = materialize_monster_media_from_portrait(
                    monster_name=entity["name"],
                    module_name=module_slug
                )
        
        if mat_result.get("success"):
            return True, None
        else:
            # Materialization failed but generation succeeded - degraded but not failure
            return True, f"Generated but materialization issue: {mat_result.get('error', 'unknown')}"
    
    except ImportError as e:
        return False, f"Import error: {e}"
    except Exception as e:
        return False, f"Generation error: {e}"


def _process_entity(
    module_slug: str,
    entity: Dict[str, Any],
    skip_existing: bool = True
) -> Dict[str, Any]:
    """Process a single entity. Returns result dict."""
    entity_type = entity["type"]
    entity_name = entity["name"]
    
    result = {
        "entity_type": entity_type,
        "name": entity_name,
        "status": "planned",
        "error": None
    }
    
    # Check if exists in target module (skip-if-exists)
    if skip_existing and _portrait_exists(module_slug, entity_name, entity_type):
        result["status"] = "skipped"
        return result
    
    # Generate and materialize to target module
    success, error = _generate_and_materialize_portrait(module_slug, entity)
    
    if success:
        result["status"] = "done"
        if error:
            # Degraded success (generated but materialization had issues)
            result["warning"] = error
    else:
        result["status"] = "failed"
        result["error"] = error
    
    return result


def _process_monster(
    module_slug: str,
    monster: Dict[str, Any],
    allow_provider: bool = False,
    timeout_seconds: int = 120
) -> Dict[str, Any]:
    """Process a single monster with reuse-first resolution.
    
    TABLETOP MODE: Monsters use dedicated bestiary resolution chain,
    never character portrait lanes.
    
    Returns result dict with source tracking:
        - status: 'reused', 'generated', 'missing', or 'failed'
        - source: 'reused_module', 'reused_static', 'reused_pack', or None
        - error: error message if failed
    """
    monster_name = monster["name"]
    
    result = {
        "entity_type": "monster",
        "name": monster_name,
        "status": "planned",
        "source": None,
        "error": None
    }
    
    # Step 1: Resolve existing media from source chain
    source_type, media_path = _resolve_monster_media(module_slug, monster_name)
    
    if source_type:
        # Found existing media - mark as reused
        result["status"] = "reused"
        result["source"] = source_type
        return result
    
    # Step 2: No existing media - check if provider generation allowed
    if not allow_provider:
        result["status"] = "missing"
        result["error"] = "No existing media found and provider generation disabled (use --allow-provider)"
        return result
    
    # Step 3: Provider generation fallback (monster-specific, not portrait)
    # TABLETOP MODE: Use monster generator, not character portrait service
    success, error = _generate_monster_media(module_slug, monster)
    
    if success:
        result["status"] = "generated"
        result["source"] = "generated"
        if error:
            result["warning"] = error
    else:
        result["status"] = "failed"
        result["error"] = error
    
    return result


def _generate_monster_media(
    module_slug: str,
    monster: Dict[str, Any],
    timeout_seconds: int = 120
) -> Tuple[bool, Optional[str]]:
    """Generate monster media using monster-specific generator.
    
    TABLETOP MODE: Never uses character portrait service.
    Only generates to monster media paths (no portrait lanes).
    
    Returns: (success, error_message)
    """
    import io
    import contextlib
    import shutil
    
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent))
        
        # Import MonsterGenerator class (not portrait service)
        from core.toolkit.monster_generator import MonsterGenerator
        try:
            from config import OPENAI_API_KEY
        except ImportError:
            OPENAI_API_KEY = None
        
        monster_name = monster["name"]
        normalized = _normalize_name(monster_name)
        
        # Target directory: module media/monsters (never portraits/)
        target_dir = Path(f"modules/{module_slug}/media/monsters")
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize generator
        if not OPENAI_API_KEY:
            return False, "OPENAI_API_KEY not configured"
        
        generator = MonsterGenerator(api_key=OPENAI_API_KEY)
        
        # Generate to temporary graphic pack location (not final module yet)
        # Use deterministic temp pack name for this module
        temp_pack = f"__prewarm_{module_slug}"
        
        # Suppress stdout for clean CLI output
        stdout_buffer = io.StringIO()
        with contextlib.redirect_stdout(stdout_buffer):
            result = generator.generate_monster_image(
                monster_id=normalized,
                style="photorealistic",
                model="dall-e-3",
                pack_name=temp_pack
            )
        
        if not result.get("success"):
            return False, result.get("error", "Unknown generation error")
        
        # Copy generated files from graphic pack to module media/monsters
        pack_dir = Path(f"graphic_packs/{temp_pack}/monsters")
        if not pack_dir.exists():
            return False, "Generated pack directory not found"
        
        copied_count = 0
        for src_file in pack_dir.glob(f"{normalized}*"):
            # Skip thumbnails - we only want main images
            if src_file.stem.endswith("_thumb"):
                continue
            
            # Determine destination filename (standardize to .jpg)
            if src_file.suffix.lower() in (".jpg", ".jpeg", ".png"):
                dest_name = f"{normalized}.jpg"
                dest_path = target_dir / dest_name
                
                try:
                    shutil.copy2(src_file, dest_path)
                    copied_count += 1
                except Exception:
                    # Continue copying other files even if one fails
                    pass
        
        if copied_count == 0:
            return False, "No image files copied from generated pack"
        
        # Cleanup temporary pack directory
        try:
            if pack_dir.exists():
                shutil.rmtree(pack_dir.parent)  # Remove entire pack folder
        except Exception:
            pass  # Fail open - temp files are not critical
        
        return True, None
    
    except ImportError as e:
        return False, f"Import error: {e}"
    except Exception as e:
        return False, f"Generation error: {e}"


def prewarm_portraits(
    module_slug: str,
    max_concurrent: int = 4,
    skip_npc: bool = False,
    skip_monster: bool = False,
    timeout_seconds: int = 120,
    allow_provider: bool = False,
) -> Dict[str, Any]:
    """Prewarm portraits for module entities with explicit module targeting.
    
    TABLETOP MODE: Provider generation is opt-in only (--allow-provider).
    By default, prewarm operates in metadata-only mode (no paid API calls).
    
    Monsters use reuse-first resolution chain:
        1) module media -> 2) static media -> 3) pack assets -> 4) provider (if allowed)
    """
    
    # Discover entities
    npcs = [] if skip_npc else _discover_npcs(module_slug)
    monsters = [] if skip_monster else _discover_monsters(module_slug)
    
    if not npcs and not monsters:
        return {
            "status": "skipped",
            "module_slug": module_slug,
            "npcs": {"planned": 0, "done": 0, "failed": 0, "skipped": 0},
            "monsters": {
                "planned": 0, "reused_module": 0, "reused_static": 0, 
                "reused_pack": 0, "generated": 0, "missing": 0, "failed": 0
            },
            "warnings": [{"type": "no_entities", "message": "No NPCs or monsters discovered"}]
        }
    
    # Ensure target directories exist (NPCs only - monsters handled in their processing)
    module_media = Path(f"modules/{module_slug}/media")
    if npcs:
        (module_media / "npcs").mkdir(parents=True, exist_ok=True)
    
    # Process NPCs (traditional portrait path - only if provider enabled)
    npc_results = []
    warnings = []
    
    if npcs and allow_provider:
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            future_to_entity = {
                executor.submit(_process_entity, module_slug, entity): entity
                for entity in npcs
            }
            
            for future in as_completed(future_to_entity):
                entity = future_to_entity[future]
                try:
                    result = future.result(timeout=timeout_seconds)
                    npc_results.append(result)
                    if result.get("warning"):
                        warnings.append({
                            "type": "degraded_success",
                            "entity_type": "npc",
                            "name": entity["name"],
                            "message": result["warning"]
                        })
                except Exception as e:
                    npc_results.append({
                        "entity_type": "npc",
                        "name": entity["name"],
                        "status": "failed",
                        "error": str(e)
                    })
                    warnings.append({
                        "type": "processing_error",
                        "entity_type": "npc",
                        "name": entity["name"],
                        "message": str(e)
                    })
    elif npcs and not allow_provider:
        # NPCs skipped when provider disabled
        for entity in npcs:
            npc_results.append({
                "entity_type": "npc",
                "name": entity["name"],
                "status": "skipped",
                "error": None
            })
        warnings.append({
            "type": "provider_disabled",
            "entity_type": "npc",
            "message": "NPC generation disabled without --allow-provider"
        })
    
    # Process monsters (reuse-first chain - works without provider)
    monster_results = []
    
    if monsters:
        # Monsters can be processed without provider (reuse chain)
        with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
            future_to_monster = {
                executor.submit(
                    _process_monster, module_slug, monster, allow_provider, timeout_seconds
                ): monster
                for monster in monsters
            }
            
            for future in as_completed(future_to_monster):
                monster = future_to_monster[future]
                try:
                    result = future.result(timeout=timeout_seconds)
                    monster_results.append(result)
                    if result.get("warning"):
                        warnings.append({
                            "type": "degraded_success",
                            "entity_type": "monster",
                            "name": monster["name"],
                            "message": result["warning"]
                        })
                except Exception as e:
                    monster_results.append({
                        "entity_type": "monster",
                        "name": monster["name"],
                        "status": "failed",
                        "source": None,
                        "error": str(e)
                    })
                    warnings.append({
                        "type": "processing_error",
                        "entity_type": "monster",
                        "name": monster["name"],
                        "message": str(e)
                    })
    
    # Calculate NPC counters (traditional)
    def count_status(results_list, status):
        return sum(1 for r in results_list if r.get("status") == status)
    
    npc_counters = {
        "planned": len(npc_results),
        "done": count_status(npc_results, "done"),
        "failed": count_status(npc_results, "failed"),
        "skipped": count_status(npc_results, "skipped")
    }
    
    # Calculate monster counters (reuse-first with source tracking)
    monster_counters = {
        "planned": len(monster_results),
        "reused_module": sum(1 for r in monster_results if r.get("source") == "reused_module"),
        "reused_static": sum(1 for r in monster_results if r.get("source") == "reused_static"),
        "reused_pack": sum(1 for r in monster_results if r.get("source") == "reused_pack"),
        "generated": sum(1 for r in monster_results if r.get("status") == "generated"),
        "missing": sum(1 for r in monster_results if r.get("status") == "missing"),
        "failed": sum(1 for r in monster_results if r.get("status") == "failed")
    }
    
    # Collect warnings from failed entities
    all_results = npc_results + monster_results
    for r in all_results:
        if r.get("status") in ("failed", "missing") and r.get("error"):
            warnings.append({
                "type": "processing_failed",
                "entity_type": r.get("entity_type", "unknown"),
                "name": r.get("name", "unknown"),
                "message": r["error"]
            })
    
    # Determine overall status
    total_failed = npc_counters["failed"] + monster_counters["failed"]
    total_missing = monster_counters["missing"]
    total_done = npc_counters["done"] + monster_counters["generated"]
    total_reused = (
        monster_counters["reused_module"] + 
        monster_counters["reused_static"] + 
        monster_counters["reused_pack"]
    )
    
    if total_failed > 0:
        status = "degraded"
    elif total_done > 0 or total_reused > 0:
        status = "success"
    elif total_missing > 0:
        status = "skipped"  # Missing media without provider
    else:
        status = "skipped"
    
    return {
        "status": status,
        "module_slug": module_slug,
        "npcs": npc_counters,
        "monsters": monster_counters,
        "warnings": warnings
    }


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="homebrew_prewarm_portraits",
        description="Prewarm NPC and monster portraits for homebrew modules",
    )
    parser.add_argument("--slug", type=str, required=True, help="Module slug (e.g., The_Secrets_of_Mangrove_Keep)")
    parser.add_argument("--json", action="store_true", default=False, help="Output JSON")
    parser.add_argument("--no-npc", action="store_true", default=False, help="Skip NPC portraits")
    parser.add_argument("--no-monster", action="store_true", default=False, help="Skip monster portraits")
    parser.add_argument("--max-concurrent", type=int, default=4, help="Max concurrent generations (default: 4)")
    parser.add_argument(
        "--allow-provider",
        action="store_true",
        default=False,
        help="Allow paid provider image generation (default: disabled for safety)",
    )
    return parser


def main() -> None:
    parser = _create_parser()
    args = parser.parse_args()
    
    result = prewarm_portraits(
        module_slug=args.slug,
        max_concurrent=args.max_concurrent,
        skip_npc=args.no_npc,
        skip_monster=args.no_monster,
        allow_provider=args.allow_provider,
    )
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=" * 60)
        print("PORTRAIT PREWARM")
        print("=" * 60)
        print(f"Module: {result['module_slug']}")
        print(f"Status: {result['status']}")
        print()
        print("NPCs:")
        print(f"  Planned: {result['npcs']['planned']}")
        print(f"  Done: {result['npcs']['done']}")
        print(f"  Failed: {result['npcs']['failed']}")
        print(f"  Skipped: {result['npcs']['skipped']}")
        print()
        print("Monsters:")
        monsters = result['monsters']
        print(f"  Planned: {monsters['planned']}")
        print(f"  Reused (module): {monsters.get('reused_module', 0)}")
        print(f"  Reused (static): {monsters.get('reused_static', 0)}")
        print(f"  Reused (pack): {monsters.get('reused_pack', 0)}")
        print(f"  Generated: {monsters.get('generated', 0)}")
        print(f"  Missing: {monsters.get('missing', 0)}")
        print(f"  Failed: {monsters.get('failed', 0)}")
        
        if result['warnings']:
            print()
            print(f"Warnings ({len(result['warnings'])}):")
            for w in result['warnings'][:5]:
                print(f"  - {w.get('type', 'warning')}: {w.get('message', '')}")
            if len(result['warnings']) > 5:
                print(f"  ... and {len(result['warnings']) - 5} more")
    
    # Exit code: 0 for success/degraded/skipped (fail-open)
    sys.exit(0)


if __name__ == "__main__":
    main()
