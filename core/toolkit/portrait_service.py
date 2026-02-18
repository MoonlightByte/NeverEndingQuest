# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Portrait Service - Character portrait generation
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Provides prompt composition, image generation, and canonical file output
for character portraits using optional appearance metadata.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import os
import base64
import re
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

from PIL import Image
import requests

from utils.ai_client_factory import create_image_client
from utils.enhanced_logger import info, warning, error


def _normalize_character_name(name: str) -> str:
    """Convert character name to filesystem-safe normalized key.
    
    Examples:
        "Acheron" -> "acheron"
        "Sir Big-Bellied Night" -> "sir_big_bellied_night"
        "D'Artagnan" -> "d_artagnan"
    """
    lowered = str(name).strip().lower()
    normalized = re.sub(r"[^a-z0-9_]+", "_", lowered).strip("_")
    return normalized


def _sanitize_prompt_text(text: str, max_length: int = 200) -> str:
    """Sanitize and length-bound free-text for prompt context.
    
    Args:
        text: Raw text input
        max_length: Maximum characters after sanitation (default 200)
        
    Returns:
        Sanitized text safe for prompt insertion
    """
    if not text:
        return ""
    # Trim whitespace
    cleaned = str(text).strip()
    # Collapse repeated whitespace/newlines to single spaces
    cleaned = re.sub(r'\s+', ' ', cleaned)
    # Length bound
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length - 3] + "..."
    return cleaned


def build_character_portrait_prompt(character_data: Dict[str, Any]) -> str:
    """Build a portrait generation prompt from character data.
    
    Uses identity/core fields, optional appearance metadata, and
    personality/background context when available.
    Handles missing fields safely without errors.
    
    Args:
        character_data: Dictionary with character fields
        
    Returns:
        Formatted prompt string ready for image generation
    """
    name = character_data.get("name", "Character")
    race = character_data.get("race", "Human")
    char_class = character_data.get("class", "Adventurer")
    background = character_data.get("background", "")
    alignment = character_data.get("alignment", "neutral")
    
    # Optional appearance fields with defensive handling
    age = str(character_data.get("age", "")).strip()
    height = str(character_data.get("height", "")).strip()
    weight = str(character_data.get("weight", "")).strip()
    eyes = str(character_data.get("eyes", "")).strip()
    skin = str(character_data.get("skin", "")).strip()
    hair = str(character_data.get("hair", "")).strip()
    
    # Build appearance description from available fields
    appearance_parts = []
    if age:
        appearance_parts.append(f"{age} years old")
    if height:
        appearance_parts.append(f"height {height}")
    if weight:
        appearance_parts.append(f"build {weight}")
    if eyes:
        appearance_parts.append(f"{eyes} eyes")
    if skin:
        appearance_parts.append(f"{skin} skin")
    if hair:
        appearance_parts.append(f"{hair} hair")
    
    appearance_text = ", ".join(appearance_parts) if appearance_parts else "distinctive features"
    
    # Extract and sanitize personality/background context fields
    personality_traits = _sanitize_prompt_text(character_data.get("personality_traits", ""), max_length=200)
    ideals = _sanitize_prompt_text(character_data.get("ideals", ""), max_length=150)
    bonds = _sanitize_prompt_text(character_data.get("bonds", ""), max_length=200)
    flaws = _sanitize_prompt_text(character_data.get("flaws", ""), max_length=150)
    
    # Handle backgroundFeature object structure
    bg_feature = character_data.get("backgroundFeature", {})
    if isinstance(bg_feature, dict):
        bg_feature_name = _sanitize_prompt_text(bg_feature.get("name", ""), max_length=100)
        bg_feature_desc = _sanitize_prompt_text(bg_feature.get("description", ""), max_length=250)
    else:
        bg_feature_name = ""
        bg_feature_desc = ""
    
    # Build personality/background context block from available fields
    context_parts = []
    if personality_traits:
        context_parts.append(f"personality: {personality_traits}")
    if ideals:
        context_parts.append(f"ideals: {ideals}")
    if bonds:
        context_parts.append(f"bonds: {bonds}")
    if flaws:
        context_parts.append(f"flaws: {flaws}")
    if bg_feature_name:
        context_parts.append(f"background ability: {bg_feature_name}")
    if bg_feature_desc:
        context_parts.append(f"known for {bg_feature_desc}")
    
    context_text = "; ".join(context_parts) if context_parts else ""
    
    # Compose full prompt
    prompt = (
        f"Epic fantasy character art portrait of {name}, "
        f"a {race} {char_class}"
    )
    
    if background:
        prompt += f" with {background} background"
    
    prompt += f". {appearance_text}. "
    
    # Add personality/background context when available
    if context_text:
        prompt += f"Character details: {context_text}. "
    
    # Add alignment-inspired atmosphere
    alignment_lower = str(alignment).lower()
    if "evil" in alignment_lower:
        prompt += "Dark and menacing presence. "
    elif "good" in alignment_lower:
        prompt += "Noble and heroic bearing. "
    else:
        prompt += "Neutral balanced demeanor. "
    
    # Style guidance
    prompt += (
        "Digital fantasy painting style, half-body or full-body portrait, "
        "cinematic lighting, detailed fantasy character art. "
    )
    
    return prompt


def _ensure_portrait_directories() -> tuple:
    """Ensure portrait directories exist and return paths.
    
    Returns:
        Tuple of (static_portraits_dir, module_portraits_func)
    """
    # Web static portraits directory
    static_dir = Path("web/static/portraits")
    static_dir.mkdir(parents=True, exist_ok=True)
    
    # Module portraits path builder
    def get_module_portraits_dir(module_name: Optional[str] = None) -> Optional[Path]:
        """Get module portraits directory if module context available."""
        if not module_name:
            # Try to get from party tracker
            try:
                import json
                with open("party_tracker.json", "r", encoding="utf-8") as f:
                    tracker = json.load(f)
                    module_name = tracker.get("module", "").replace(" ", "_")
            except Exception:
                return None
        
        if not module_name:
            return None
            
        module_dir = Path(f"modules/{module_name}/portraits")
        try:
            module_dir.mkdir(parents=True, exist_ok=True)
            return module_dir
        except Exception as e:
            warning(f"PORTRAIT_SERVICE: Could not create module portraits dir: {e}", category="portrait_generation")
            return None
    
    return static_dir, get_module_portraits_dir


def generate_and_save_portrait(
    character_data: Dict[str, Any],
    model: str = "dall-e-3",
    size: str = "1024x1024",
    quality: str = "standard"
) -> Dict[str, Any]:
    """Generate portrait for character and save to canonical locations.
    
    Args:
        character_data: Character data dictionary
        model: Image generation model (default dall-e-3)
        size: Image size (default 1024x1024)
        quality: Image quality (default standard)
        
    Returns:
        Result dictionary with keys:
        - success: bool
        - message: str
        - portrait_path: Optional[str] - web static path if saved
        - module_portrait_path: Optional[str] - module path if saved
        - prompt: str - the generated prompt
        - error: Optional[str] - error details if failed
    """
    result = {
        "success": False,
        "message": "",
        "portrait_path": None,
        "module_portrait_path": None,
        "prompt": "",
        "error": None
    }
    
    try:
        # Validate character data
        name = character_data.get("name")
        if not name:
            result["message"] = "Character name is required"
            result["error"] = "missing_name"
            return result
        
        # Normalize name for filename
        normalized_name = _normalize_character_name(name)
        if not normalized_name:
            result["message"] = "Invalid character name"
            result["error"] = "invalid_name"
            return result
        
        # Build prompt
        prompt = build_character_portrait_prompt(character_data)
        result["prompt"] = prompt
        
        info(f"PORTRAIT_SERVICE: Generating portrait for {name} with {model}", category="portrait_generation")
        
        # Get image client
        try:
            client = create_image_client()
        except Exception as client_error:
            error(f"PORTRAIT_SERVICE: Failed to create image client: {client_error}", category="portrait_generation")
            result["message"] = "Image service unavailable"
            result["error"] = "client_init_failed"
            return result
        
        # Generate image
        try:
            response = client.images.generate(
                model=model,
                prompt=prompt[:4000],  # DALL-E has character limit
                size=size,
                quality=quality,
                n=1
            )
        except Exception as gen_error:
            error(f"PORTRAIT_SERVICE: Generation failed for {name}: {gen_error}", category="portrait_generation")
            result["message"] = "Portrait generation failed"
            result["error"] = f"generation_error: {gen_error}"
            return result
        
        # Extract image data
        image_url = getattr(response.data[0], 'url', None)
        b64_json = getattr(response.data[0], 'b64_json', None)
        
        # Download/decode image
        try:
            if b64_json:
                image_data = base64.b64decode(b64_json)
                img = Image.open(BytesIO(image_data))
            elif image_url:
                img_response = requests.get(image_url, timeout=30)
                img = Image.open(BytesIO(img_response.content))
            else:
                result["message"] = "No image data in response"
                result["error"] = "no_image_data"
                return result
        except Exception as img_error:
            error(f"PORTRAIT_SERVICE: Image decode failed for {name}: {img_error}", category="portrait_generation")
            result["message"] = "Image processing failed"
            result["error"] = f"decode_error: {img_error}"
            return result
        
        # Process image (resize and format)
        try:
            # Resize to standard portrait size
            img = img.resize((256, 256), Image.Resampling.LANCZOS)
            
            # Convert to RGBA if needed
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
        except Exception as proc_error:
            error(f"PORTRAIT_SERVICE: Image processing failed for {name}: {proc_error}", category="portrait_generation")
            result["message"] = "Image processing failed"
            result["error"] = f"processing_error: {proc_error}"
            return result
        
        # Ensure directories exist
        static_dir, get_module_dir = _ensure_portrait_directories()
        
        # Save to web static portraits
        static_path = static_dir / f"{normalized_name}.png"
        try:
            img.save(static_path, 'PNG')
            result["portrait_path"] = str(static_path)
            info(f"PORTRAIT_SERVICE: Saved portrait to {static_path}", category="portrait_generation")
        except Exception as save_error:
            error(f"PORTRAIT_SERVICE: Failed to save static portrait for {name}: {save_error}", category="portrait_generation")
            result["message"] = "Failed to save portrait"
            result["error"] = f"save_error: {save_error}"
            return result
        
        # Save to module portraits (fail-open)
        try:
            module_dir = get_module_dir()
            if module_dir:
                module_path = module_dir / f"{normalized_name}.png"
                img.save(module_path, 'PNG')
                result["module_portrait_path"] = str(module_path)
                info(f"PORTRAIT_SERVICE: Saved portrait to module {module_path}", category="portrait_generation")
        except Exception as module_error:
            # Fail-open: log but don't fail the whole operation
            warning(f"PORTRAIT_SERVICE: Could not save to module portraits for {name}: {module_error}", category="portrait_generation")
        
        # Success
        result["success"] = True
        result["message"] = f"Portrait generated successfully for {name}"
        info(f"PORTRAIT_SERVICE: Successfully generated portrait for {name}", category="portrait_generation")
        return result
        
    except Exception as unexpected_error:
        error(f"PORTRAIT_SERVICE: Unexpected error generating portrait: {unexpected_error}", category="portrait_generation")
        result["message"] = "Unexpected error during portrait generation"
        result["error"] = f"unexpected: {unexpected_error}"
        return result


def materialize_npc_media_from_portrait(
    npc_name: str,
    module_name: Optional[str] = None
) -> Dict[str, Any]:
    """Materialize NPC media variants from existing portrait sources (reuse-first).
    
    Checks for existing portrait files in canonical locations and converts them
    into the NPC media variants required by /media/npcs serving path.
    
    Args:
        npc_name: The NPC character name
        module_name: Optional module context; if None, reads from party_tracker.json
        
    Returns:
        Result dictionary with keys:
        - success: bool - True if any media was materialized
        - reused: bool - True if existing portrait was reused (no provider call needed)
        - source_path: Optional[str] - Path to the source portrait that was reused
        - paths_written: List[str] - List of output file paths written
        - error: Optional[str] - Error message if failed
    """
    result = {
        "success": False,
        "reused": False,
        "source_path": None,
        "paths_written": [],
        "error": None
    }
    
    try:
        # Normalize name for filename matching
        normalized_name = _normalize_character_name(npc_name)
        if not normalized_name:
            result["error"] = "invalid_npc_name"
            return result
        
        # Determine module context if not provided
        if not module_name:
            try:
                import json
                with open("party_tracker.json", "r", encoding="utf-8") as f:
                    tracker = json.load(f)
                    module_name = tracker.get("module", "").replace(" ", "_")
            except Exception:
                pass
        
        # Search for existing portrait sources in priority order:
        # 1. web/static/portraits/<name>.png
        # 2. modules/<module>/portraits/<name>.png
        source_image = None
        source_path = None
        
        static_portrait_path = Path(f"web/static/portraits/{normalized_name}.png")
        if static_portrait_path.exists():
            try:
                source_image = Image.open(static_portrait_path)
                source_path = str(static_portrait_path)
            except Exception:
                pass
        
        if source_image is None and module_name:
            module_portrait_path = Path(f"modules/{module_name}/portraits/{normalized_name}.png")
            if module_portrait_path.exists():
                try:
                    source_image = Image.open(module_portrait_path)
                    source_path = str(module_portrait_path)
                except Exception:
                    pass
        
        # No reusable source found
        if source_image is None:
            result["error"] = "no_reusable_source"
            return result
        
        # We have a reusable source
        result["reused"] = True
        result["source_path"] = source_path
        
        info(
            f"PORTRAIT_SERVICE: Reusing existing portrait for {npc_name} from {source_path}",
            category="portrait_generation"
        )
        
        # Ensure output directories exist
        if module_name:
            module_npcs_dir = Path(f"modules/{module_name}/media/npcs")
            module_npcs_dir.mkdir(parents=True, exist_ok=True)
        
        static_npcs_dir = Path("web/static/media/npcs")
        static_npcs_dir.mkdir(parents=True, exist_ok=True)
        
        # Convert to RGB for JPEG output
        if source_image.mode == 'RGBA':
            rgb_image = Image.new('RGB', source_image.size, (255, 255, 255))
            rgb_image.paste(source_image, mask=source_image.split()[3] if len(source_image.split()) > 3 else None)
        else:
            rgb_image = source_image.convert('RGB') if source_image.mode != 'RGB' else source_image
        
        # Create thumbnail version
        thumb_image = rgb_image.copy()
        thumb_image.thumbnail((128, 128), Image.Resampling.LANCZOS)
        
        # Write outputs to all required locations
        paths_written = []
        
        # Module media paths
        if module_name:
            # Full-size JPG
            module_full_path = module_npcs_dir / f"{normalized_name}.jpg"
            try:
                rgb_image.save(module_full_path, 'JPEG', quality=95)
                paths_written.append(str(module_full_path))
                info(
                    f"PORTRAIT_SERVICE: Saved NPC media to {module_full_path}",
                    category="portrait_generation"
                )
            except Exception as e:
                warning(
                    f"PORTRAIT_SERVICE: Failed to save module NPC full image for {npc_name}: {e}",
                    category="portrait_generation"
                )
            
            # Thumbnail JPG
            module_thumb_path = module_npcs_dir / f"{normalized_name}_thumb.jpg"
            try:
                thumb_image.save(module_thumb_path, 'JPEG', quality=85)
                paths_written.append(str(module_thumb_path))
                info(
                    f"PORTRAIT_SERVICE: Saved NPC thumbnail to {module_thumb_path}",
                    category="portrait_generation"
                )
            except Exception as e:
                warning(
                    f"PORTRAIT_SERVICE: Failed to save module NPC thumbnail for {npc_name}: {e}",
                    category="portrait_generation"
                )
        
        # Static fallback paths
        static_full_path = static_npcs_dir / f"{normalized_name}.jpg"
        try:
            rgb_image.save(static_full_path, 'JPEG', quality=95)
            paths_written.append(str(static_full_path))
            info(
                f"PORTRAIT_SERVICE: Saved NPC media to {static_full_path}",
                category="portrait_generation"
            )
        except Exception as e:
            warning(
                f"PORTRAIT_SERVICE: Failed to save static NPC full image for {npc_name}: {e}",
                category="portrait_generation"
            )
        
        static_thumb_path = static_npcs_dir / f"{normalized_name}_thumb.jpg"
        try:
            thumb_image.save(static_thumb_path, 'JPEG', quality=85)
            paths_written.append(str(static_thumb_path))
            info(
                f"PORTRAIT_SERVICE: Saved NPC thumbnail to {static_thumb_path}",
                category="portrait_generation"
            )
        except Exception as e:
            warning(
                f"PORTRAIT_SERVICE: Failed to save static NPC thumbnail for {npc_name}: {e}",
                category="portrait_generation"
            )
        
        result["success"] = len(paths_written) > 0
        result["paths_written"] = paths_written
        
        if result["success"]:
            info(
                f"PORTRAIT_SERVICE: Successfully materialized {len(paths_written)} NPC media files for {npc_name}",
                category="portrait_generation"
            )
        else:
            result["error"] = "no_files_written"
        
        return result
        
    except Exception as e:
        error(
            f"PORTRAIT_SERVICE: Unexpected error materializing NPC media for {npc_name}: {e}",
            category="portrait_generation"
        )
        result["error"] = f"unexpected: {e}"
        return result


__all__ = [
    "build_character_portrait_prompt",
    "generate_and_save_portrait",
    "_normalize_character_name",
    "materialize_npc_media_from_portrait",
]
