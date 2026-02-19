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
from utils.openai_usage_tracker import track_image_cost, get_dalle3_cost_usd


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


def _extract_first_int(text: str) -> Optional[int]:
    """Safely extract first integer from text.
    
    Args:
        text: Input text that may contain numbers
        
    Returns:
        First integer found, or None if no valid number
    """
    if not text:
        return None
    try:
        match = re.search(r'\d+', str(text))
        if match:
            return int(match.group())
    except (AttributeError, ValueError):
        pass
    return None


def _convert_age_to_descriptor(age: str) -> str:
    """Convert age value to visual descriptor.
    
    Args:
        age: Age value (string or numeric)
        
    Returns:
        Visual descriptor for age (for example, elderly, middle-aged, young)
    """
    if not age:
        return ""
    age_num = _extract_first_int(age)
    if age_num is None:
        # Return original if not parseable
        return str(age).strip()
    if age_num >= 60:
        return "elderly"
    elif age_num >= 40:
        return "middle-aged"
    elif age_num >= 25:
        return "adult"
    elif age_num >= 13:
        return "young"
    else:
        return "youthful"


def _get_article(word: str) -> str:
    """Return appropriate article ('a' or 'an') for a word.
    
    Args:
        word: The word to get article for
        
    Returns:
        'an' if word starts with vowel, 'a' otherwise
    """
    if not word:
        return "a"
    first_letter = str(word)[0].lower()
    if first_letter in 'aeiou':
        return "an"
    return "a"


def _normalize_personality_phrase(phrase: str) -> str:
    """Normalize personality phrase to avoid awkward duplication.
    
    Removes leading phrases like "Believes that...", "Sometimes..." to avoid
    output like "guided by Believes that..." or "yet sometimes Sometimes..."
    
    Args:
        phrase: Raw personality/ideals/bonds/flaws text
        
    Returns:
        Normalized phrase without redundant leading words
    """
    if not phrase:
        return ""
    
    phrase = phrase.strip()
    
    # Remove redundant leading phrases that would duplicate connector words
    redundant_starts = [
        "believes that ",
        "believes ",
        "belief that ",
        "loyal to ",
        "devoted to ",
        "sworn to ",
        "committed to ",
        "bound to ",
        "can be ",
        "sometimes ",
        "often ",
        "always ",
        "never ",
    ]
    
    lower_phrase = phrase.lower()
    for pattern in redundant_starts:
        if lower_phrase.startswith(pattern):
            phrase = phrase[len(pattern):].strip()
            break

    # Trim trailing punctuation so clause composition controls sentence endings.
    # Preserve ellipsis because it may come from bounded truncation.
    phrase = re.sub(r"[;,]\s*$", "", phrase)
    if phrase.endswith(".") and not phrase.endswith("..."):
        phrase = phrase[:-1].rstrip()
    
    return phrase


def _format_flaw_clause(flaws: str) -> str:
    """Format flaw phrase into natural prose.

    Args:
        flaws: Normalized flaw phrase

    Returns:
        Flaw clause suitable for sentence composition
    """
    if not flaws:
        return ""

    lower_flaws = flaws.lower()
    if lower_flaws.startswith("lets "):
        return f"and can let {flaws[5:]}"
    if lower_flaws.startswith("let "):
        return f"and can {flaws}"
    if lower_flaws.startswith("be "):
        return f"and can be {flaws[3:]}"
    return f"and can be {flaws}"


def _build_visual_brief(character_data: Dict[str, Any]) -> str:
    """Build a natural-language visual brief from structured character data.
    
    Converts structured profile fields into a concise prose paragraph
    without label-style formatting that could trigger card/sheet layouts.
    
    Args:
        character_data: Dictionary with character fields
        
    Returns:
        Visual brief paragraph (prose only, no field labels)
    """
    # Extract fields
    name = character_data.get("name", "Character")
    race = character_data.get("race", "Human")
    char_class = character_data.get("class", "Adventurer")
    background = character_data.get("background", "")
    alignment = character_data.get("alignment", "neutral")
    
    # Appearance fields
    age_raw = str(character_data.get("age", "")).strip()
    height = str(character_data.get("height", "")).strip()
    weight = str(character_data.get("weight", "")).strip()
    eyes = str(character_data.get("eyes", "")).strip()
    skin = str(character_data.get("skin", "")).strip()
    hair = str(character_data.get("hair", "")).strip()
    
    # Convert age to visual descriptor
    age_desc = _convert_age_to_descriptor(age_raw)
    
    # Build physical description as prose
    physical_parts = []
    if age_desc:
        physical_parts.append(age_desc)
    if height:
        # Extract numeric for stature hint (safely)
        height_num = _extract_first_int(height)
        if height_num and height_num <= 5:
            physical_parts.append("short-statured")
    if weight:
        # Extract numeric for build hint (safely)
        weight_num = _extract_first_int(weight)
        if weight_num and weight_num < 70 and "kg" in weight.lower():
            physical_parts.append("compact build")
    if eyes:
        physical_parts.append(f"{eyes} eyes")
    if skin:
        physical_parts.append(f"{skin} skin")
    if hair:
        physical_parts.append(f"{hair} hair")
    
    # Filter empty and join
    physical_parts = [p for p in physical_parts if p]
    
    # Build race/class clause with physical traits
    if physical_parts:
        identity_desc = f"{', '.join(physical_parts)} {race} {char_class}"
    else:
        identity_desc = f"{race} {char_class}"
    
    # Add background if present
    if background:
        identity_desc += f" with {background} roots"
    
    # Get appropriate article for the identity description
    article = _get_article(identity_desc.split()[0] if identity_desc else "a")
    identity_clause = f"{article} {identity_desc}"
    
    # Sanitize and normalize personality fields
    personality_traits = _normalize_personality_phrase(
        _sanitize_prompt_text(character_data.get("personality_traits", ""), max_length=120)
    )
    ideals = _normalize_personality_phrase(
        _sanitize_prompt_text(character_data.get("ideals", ""), max_length=100)
    )
    bonds = _normalize_personality_phrase(
        _sanitize_prompt_text(character_data.get("bonds", ""), max_length=120)
    )
    flaws = _normalize_personality_phrase(
        _sanitize_prompt_text(character_data.get("flaws", ""), max_length=100)
    )
    
    # Build demeanor as prose
    demeanor_parts = []
    if personality_traits:
        demeanor_parts.append(personality_traits)
    if ideals:
        demeanor_parts.append(f"guided by the idea that {ideals}")
    if bonds:
        demeanor_parts.append(f"deeply connected to {bonds}")
    if flaws:
        demeanor_parts.append(_format_flaw_clause(flaws))
    
    demeanor_clause = ""
    if demeanor_parts:
        demeanor_text = "; ".join(demeanor_parts)
        if demeanor_text.endswith("..."):
            demeanor_clause = f"Their expression shows {demeanor_text} "
        else:
            demeanor_clause = f"Their expression shows {demeanor_text}. "
    
    # Add background feature context
    bg_feature = character_data.get("backgroundFeature", {})
    bg_clause = ""
    if isinstance(bg_feature, dict):
        bg_name = _sanitize_prompt_text(bg_feature.get("name", ""), max_length=80)
        if bg_name:
            bg_clause = f"Known for {bg_name}. "
    
    # Add alignment atmosphere
    alignment_lower = str(alignment).lower()
    if "evil" in alignment_lower:
        alignment_clause = "They carry a dark, menacing presence."
    elif "good" in alignment_lower:
        alignment_clause = "They radiate noble, heroic bearing."
    else:
        alignment_clause = "They maintain a balanced, neutral demeanor."
    
    # Combine into complete sentence
    brief = f"{name} is {identity_clause}. {demeanor_clause}{bg_clause}{alignment_clause}"
    
    # Clean up any double spaces or leading/trailing issues
    brief = re.sub(r'\s+', ' ', brief).strip()
    # Guard against punctuation artifacts from truncated fields.
    brief = re.sub(r"\.{4,}", "...", brief)

    return brief


def build_character_portrait_prompt(character_data: Dict[str, Any]) -> str:
    """Build a portrait generation prompt from character data.
    
    Uses visual brief synthesis to convert structured data into natural-language
    prose, avoiding card/sheet layout triggers while preserving character identity.
    
    Args:
        character_data: Dictionary with character fields
        
    Returns:
        Formatted prompt string ready for image generation
    """
    # Build natural-language visual brief from structured data
    visual_brief = _build_visual_brief(character_data)
    
    # Compose final prompt using visual brief paragraph
    # visual_brief already ends with a period, so we don't add another
    prompt = (
        f"{visual_brief} "
        "Close head-and-shoulders portrait, face centered and clearly visible, "
        "soft natural lighting on face, eye-level camera angle. "
        "Ultra-realistic fantasy character art, photorealistic style with cinematic quality, "
        "detailed textures, natural skin tones and fabric rendering. "
        "Soft in-world environmental background with shallow depth of field, gentle bokeh, "
        "background elements blurred and atmospheric. "
        "Face is the clear focal subject. Simple upper-body clothing detail, no props. "
        "STRICT EXCLUSIONS: no text, no letters, no words, no captions, no typography, "
        "no runes, no glyphs, no logos, no watermarks, no UI, no HUD, no game interface, "
        "no character sheet, no stat card, no status panel, no info box, no document, "
        "no page, no form, no paper, no parchment, no borders, no frames."
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
        
        # Generate image with natural style to avoid poster/card-like outputs
        try:
            response = client.images.generate(
                model=model,
                prompt=prompt[:4000],  # DALL-E has character limit
                size=size,
                quality=quality,
                style="natural",
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
        
        # Track image cost (fail-open)
        try:
            cost_usd = get_dalle3_cost_usd(size, quality)
            track_image_cost(
                cost_usd=cost_usd,
                size=size,
                quality=quality,
                model=model,
                context={
                    "endpoint": "portrait_service",
                    "purpose": "character_portrait",
                    "character_name": name,
                    "n": 1
                }
            )
        except Exception:
            pass  # Fail open - don't block success on tracking failure
        
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
