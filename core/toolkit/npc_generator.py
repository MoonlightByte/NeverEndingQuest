#!/usr/bin/env python3
"""
NPC Portrait Generation Service for Module Toolkit
Handles portrait generation for NPCs using different styles and AI models
Based on MonsterGenerator but optimized for NPC portraits
"""

import os
import json
import time
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
from PIL import Image
import requests
from io import BytesIO

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    print("Warning: OpenAI library not available")

# Import API key from config
try:
    from config import OPENAI_API_KEY
except ImportError:
    OPENAI_API_KEY = None
    print("Warning: Could not import OPENAI_API_KEY from config.py")

try:
    from utils.openai_usage_tracker import track_image_cost, get_dalle3_cost_usd
except ImportError:
    track_image_cost = None
    get_dalle3_cost_usd = None

class NPCGenerator:
    """Service for generating NPC portrait images in various styles"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the NPC generator"""
        # Use provided key or fall back to config
        self.api_key = api_key or OPENAI_API_KEY
        if self.api_key and OPENAI_AVAILABLE:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
        
        # Load style templates
        self.style_templates = self._load_style_templates()
        
        # Account validation cache
        self._account_validated = None
        
    def _load_style_templates(self) -> Dict:
        """Load style templates"""
        styles_path = Path('data/style_templates.json')
        if styles_path.exists():
            with open(styles_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"builtin": {}, "custom": {}}
    
    def validate_account_for_gpt_image(self) -> bool:
        """Check if account is validated for GPT-Image model"""
        if self._account_validated is not None:
            return self._account_validated
        
        if not self.client:
            self._account_validated = False
            return False
        
        try:
            # Try a minimal API call to check access
            response = self.client.models.list()
            available_models = [model.id for model in response.data]
            
            # Check for GPT-Image model availability
            self._account_validated = 'gpt-image-1' in available_models or 'gpt-4' in available_models
            return self._account_validated
        except Exception as e:
            print(f"Account validation failed: {e}")
            self._account_validated = False
            return False
    
    def build_prompt(self, npc_name: str, npc_description: str, style: str = "photorealistic") -> str:
        """Build a complete prompt for NPC portrait generation using a proven, modular structure."""
        
        # Get style template - check both builtin and custom
        style_data = None
        if style in self.style_templates.get("builtin", {}):
            style_data = self.style_templates["builtin"][style]
        elif style in self.style_templates.get("custom", {}):
            style_data = self.style_templates["custom"][style]
        
        if not style_data:
            print(f"Warning: Style '{style}' not found. Using a default fantasy art style.")
            style_data = { "prompt": "digital painting, fantasy character portrait, 5th edition roleplaying game art style" }

        prompt_parts = []

        # Part 1: The Core Artistic Style
        # This remains the most important instruction.
        base_style_prompt = style_data.get("prompt", "")
        prompt_parts.append(
            f"Epic fantasy character art portrait in the style of {base_style_prompt}."
        )

        # Part 2: The Full Description (which now includes the background)
        # We simply append the entire new description here.
        prompt_parts.append(npc_description)

        # Part 3: Reinforce Composition and Quality
        # A final instruction to ensure a high-quality, single-character result.
        prompt_parts.append(
            "A dynamic half-body or full-body portrait of a single character. Cinematic composition. Character expression and demeanor should match their personality and situation."
        )

        # Part 4: Add Style Modifiers
        if style_data.get("modifiers"):
            modifiers_text = ", ".join(style_data["modifiers"])
            prompt_parts.append(modifiers_text)
        
        # Join the parts with double newlines for clarity
        return "\n\n".join(prompt_parts)
    
    def generate_npc_portrait(
        self, 
        npc_id: str,
        npc_name: str,
        npc_description: str,
        style: str = "photorealistic",
        model: str = "dall-e-3",
        pack_name: Optional[str] = None
    ) -> Dict:
        """
        Generate a single NPC portrait image
        
        Args:
            npc_id: Unique ID for the NPC
            npc_name: Name of the NPC
            npc_description: Description of the NPC
            style: Style template to use
            model: 'gpt-image-1', 'dall-e-3', or 'auto'
            pack_name: Name of the graphic pack to save to
            
        Returns:
            Dictionary with generation results
        """
        if not self.client:
            return {
                "success": False,
                "error": "OpenAI client not initialized"
            }
        
        # Get style data
        style_data = None
        if style in self.style_templates.get("builtin", {}):
            style_data = self.style_templates["builtin"][style]
        elif style in self.style_templates.get("custom", {}):
            style_data = self.style_templates["custom"][style]
        else:
            style_data = {}
        
        # Determine model to use
        if model == "auto":
            model = style_data.get("model_preference", "dall-e-3")
        
        # Check account validation for GPT-Image
        if model == "gpt-image-1" and not self.validate_account_for_gpt_image():
            print(f"Account not validated for GPT-Image, falling back to DALL-E 3")
            model = "dall-e-3"
        
        # Build prompt
        prompt = self.build_prompt(npc_name, npc_description, style)
        
        # Get model settings
        model_settings = style_data.get("model_settings", {})
        
        print(f"\nGenerating portrait for {npc_name} with {model} in {style} style...")
        print(f"Prompt preview: {prompt[:200]}...")
        
        try:
            start_time = time.time()
            
            # Generate image based on model
            if model == "dall-e-3":
                response = self.client.images.generate(
                    model="dall-e-3",
                    prompt=prompt[:4000],  # DALL-E has character limit
                    size=model_settings.get("size", "1024x1024"),
                    quality=model_settings.get("quality", "standard"),
                    style=model_settings.get("style", "vivid"),
                    n=1
                )
            else:  # gpt-image-1
                response = self.client.images.generate(
                    model="gpt-image-1",
                    prompt=prompt[:4000],
                    size=model_settings.get("size", "1024x1024"),
                    quality=model_settings.get("quality", "auto"),
                    n=1
                )
            
            elapsed = time.time() - start_time
            
            # Get image data (handle both URL and base64 responses)
            image_url = getattr(response.data[0], 'url', None)
            b64_json = getattr(response.data[0], 'b64_json', None)
            
            # Download/decode image
            if b64_json:
                import base64
                image_data = base64.b64decode(b64_json)
                img = Image.open(BytesIO(image_data))
                # For consistency, set a placeholder URL
                image_url = "base64_image"
            elif image_url:
                img_response = requests.get(image_url)
                img = Image.open(BytesIO(img_response.content))
            else:
                return {
                    "success": False,
                    "error": "No image data in response (no URL or base64)"
                }
            
            # Save to pack if specified
            if pack_name:
                pack_dir = Path('graphic_packs') / pack_name / 'npcs'
                pack_dir.mkdir(parents=True, exist_ok=True)
                
                # Save original uncompressed PNG to raw_images folder
                raw_dir = Path('raw_images') / 'npcs' / pack_name
                raw_dir.mkdir(parents=True, exist_ok=True)
                raw_path = raw_dir / f'{npc_id}.png'
                img.save(raw_path, 'PNG')
                print(f"  Original saved to: {raw_path}")
                
                # Convert to RGB if needed (JPEG doesn't support transparency)
                if img.mode == 'RGBA':
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[3] if len(img.split()) > 3 else None)
                    img_to_save = rgb_img
                else:
                    img_to_save = img
                
                # Save compressed JPEG to pack (matching monster generator)
                portrait_path = pack_dir / f'{npc_id}.jpg'
                img_to_save.save(portrait_path, 'JPEG', quality=95)
                
                # Create and save thumbnail as JPEG
                thumb = img_to_save.copy()
                thumb.thumbnail((128, 128), Image.Resampling.LANCZOS)
                thumb_path = pack_dir / f'{npc_id}_thumb.jpg'
                thumb.save(thumb_path, 'JPEG', quality=85)
                
                # Also save to game's NPC media folder for live use
                game_npcs_dir = Path('web/static/media/npcs')
                game_npcs_dir.mkdir(parents=True, exist_ok=True)
                
                # Copy thumbnail to game folder (game uses JPG thumbnails)
                thumb_jpg = img.copy()
                thumb_jpg.thumbnail((128, 128), Image.Resampling.LANCZOS)
                if thumb_jpg.mode == 'RGBA':
                    # Convert RGBA to RGB for JPG
                    rgb_img = Image.new('RGB', thumb_jpg.size, (255, 255, 255))
                    rgb_img.paste(thumb_jpg, mask=thumb_jpg.split()[3] if len(thumb_jpg.split()) > 3 else None)
                    thumb_jpg = rgb_img
                game_thumb_path = game_npcs_dir / f'{npc_id}_thumb.jpg'
                thumb_jpg.save(game_thumb_path, 'JPEG', quality=85)
                
                print(f"[OK] Generated portrait for {npc_name} in {elapsed:.2f}s")
                print(f"  Saved to: {portrait_path}")
            
            # Track image cost (fail-open)
            try:
                if track_image_cost and get_dalle3_cost_usd:
                    size = model_settings.get("size", "1024x1024")
                    quality = model_settings.get("quality", "standard")
                    cost_usd = get_dalle3_cost_usd(size, quality)
                    track_image_cost(
                        cost_usd=cost_usd,
                        size=size,
                        quality=quality,
                        model=model,
                        context={
                            "endpoint": "npc_generator",
                            "purpose": "npc_portrait",
                            "npc_id": npc_id,
                            "npc_name": npc_name,
                            "n": 1
                        }
                    )
            except Exception:
                pass  # Fail open
            
            return {
                "success": True,
                "npc_id": npc_id,
                "npc_name": npc_name,
                "model": model,
                "style": style,
                "elapsed_time": elapsed,
                "image_url": image_url,
                "image_object": img if not pack_name else None,  # Return image object for web_interface to save
                "saved_to": str(portrait_path) if pack_name else None
            }
            
        except Exception as e:
            error_msg = str(e)
            print(f"[FAIL] Failed to generate {npc_name}: {error_msg}")
            
            # Check for content policy violation
            if "content_policy_violation" in error_msg.lower():
                return {
                    "success": False,
                    "error": "Content policy violation - description may contain inappropriate content",
                    "npc_id": npc_id
                }
            
            return {
                "success": False,
                "error": error_msg,
                "npc_id": npc_id
            }
    
    async def batch_generate_portraits(
        self,
        npcs: List[Dict],
        pack_name: str,
        style: str = "photorealistic",
        model: str = "dall-e-3",
        progress_callback = None
    ) -> Dict:
        """
        Generate portraits for multiple NPCs
        
        Args:
            npcs: List of NPC dictionaries with id, name, and description
            pack_name: Name of the graphic pack to save to
            style: Style template to use
            model: AI model to use
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with batch results
        """
        results = {
            "successful": [],
            "failed": [],
            "total": len(npcs),
            "style": style,
            "model": model,
            "pack": pack_name
        }
        
        for i, npc_data in enumerate(npcs):
            npc_id = npc_data.get('id')
            npc_name = npc_data.get('name')
            npc_description = npc_data.get('description', f'A fantasy NPC named {npc_name}')
            
            # Send progress update
            if progress_callback:
                progress_callback({
                    "current": i + 1,
                    "total": len(npcs),
                    "npc_name": npc_name,
                    "status": "generating"
                })
            
            # Generate portrait
            result = self.generate_npc_portrait(
                npc_id=npc_id,
                npc_name=npc_name,
                npc_description=npc_description,
                style=style,
                model=model,
                pack_name=pack_name
            )
            
            if result["success"]:
                results["successful"].append(result)
            else:
                results["failed"].append(result)
            
            # Rate limiting
            await asyncio.sleep(3)  # Wait 3 seconds between requests
        
        return results