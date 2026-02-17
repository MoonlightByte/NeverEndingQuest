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


def build_character_portrait_prompt(character_data: Dict[str, Any]) -> str:
    """Build a portrait generation prompt from character data.
    
    Uses identity/core fields and optional appearance metadata.
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
    
    # Compose full prompt
    prompt = (
        f"Epic fantasy character art portrait of {name}, "
        f"a {race} {char_class}"
    )
    
    if background:
        prompt += f" with {background} background"
    
    prompt += f". {appearance_text}. "
    
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


__all__ = [
    "build_character_portrait_prompt",
    "generate_and_save_portrait",
    "_normalize_character_name",
]
