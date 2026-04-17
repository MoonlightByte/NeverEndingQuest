#!/usr/bin/env python3
"""
Monster Generation Service for Module Toolkit
Handles image generation for monsters using different styles and AI models
"""

import os
import json
import time
import base64
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
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

class MonsterGenerator:
    """Service for generating monster images in various styles"""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the monster generator"""
        # Use provided key or fall back to config
        self.api_key = api_key or OPENAI_API_KEY
        if self.api_key and OPENAI_AVAILABLE:
            self.client = OpenAI(api_key=self.api_key)
        else:
            self.client = None
        
        # Load bestiary and style templates
        self.bestiary = self._load_bestiary()
        self.style_templates = self._load_style_templates()
        
        # Account validation cache
        self._account_validated = None
        
    def _load_bestiary(self) -> Dict:
        """Load the monster compendium"""
        bestiary_path = Path('data/bestiary/monster_compendium.json')
        if bestiary_path.exists():
            with open(bestiary_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"monsters": {}}
    
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
    
    def build_prompt(self, monster_id: str, style: str = "photorealistic") -> str:
        """Build a complete prompt for monster image generation"""
        # Get monster description
        monster_data = self.bestiary.get("monsters", {}).get(monster_id)
        if not monster_data:
            raise ValueError(f"Monster '{monster_id}' not found in bestiary")
        
        # Get style template - check both builtin and custom
        style_data = None
        if style in self.style_templates.get("builtin", {}):
            style_data = self.style_templates["builtin"][style]
        elif style in self.style_templates.get("custom", {}):
            style_data = self.style_templates["custom"][style]
        
        if not style_data:
            raise ValueError(f"Style '{style}' not found in templates")
        
        # Build complete prompt
        prompt_parts = []
        
        # Add base prompt (check both 'prompt' and 'base_prompt' keys for compatibility)
        base_prompt = style_data.get("prompt") or style_data.get("base_prompt", "")
        if base_prompt:
            prompt_parts.append(f"Create an ultra detailed {base_prompt} 5th edition roleplaying game monster portrait")
        
        # Add monster description
        prompt_parts.append(monster_data["description"])
        
        # Add style modifiers
        if style_data.get("modifiers"):
            modifiers_text = ", ".join(style_data["modifiers"])
            prompt_parts.append(modifiers_text)
        
        # Add suffix
        if style_data.get("suffix"):
            prompt_parts.append(style_data["suffix"])
        
        return "\n".join(prompt_parts)
    
    def generate_monster_image(
        self, 
        monster_id: str, 
        style: str = "photorealistic",
        model: str = "dall-e-3",
        pack_name: Optional[str] = None
    ) -> Dict:
        """
        Generate a single monster image
        
        Args:
            monster_id: ID of the monster from bestiary
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
        
        # Get style preferences - check both builtin and custom
        style_data = {}
        if style in self.style_templates.get("builtin", {}):
            style_data = self.style_templates["builtin"][style]
        elif style in self.style_templates.get("custom", {}):
            style_data = self.style_templates["custom"][style]
        
        # Determine model to use
        if model == "auto":
            model = style_data.get("model_preference", "dall-e-3")
        
        # Check account validation for GPT-Image
        if model == "gpt-image-1" and not self.validate_account_for_gpt_image():
            print(f"Account not validated for GPT-Image, falling back to DALL-E 3")
            model = "dall-e-3"
        
        # Build prompt
        prompt = self.build_prompt(monster_id, style)
        
        # Get model settings
        model_settings = style_data.get("model_settings", {})
        
        print(f"\nGenerating {monster_id} with {model} in {style} style...")
        print(f"Prompt preview: {prompt[:200]}...")
        
        try:
            start_time = time.time()
            
            # Generate image based on model
            if model == "dall-e-3":
                response = self.client.images.generate(
                    model="dall-e-3",
                    prompt=prompt,
                    size=model_settings.get("size", "1024x1024"),
                    quality=model_settings.get("quality", "standard"),
                    style=model_settings.get("style", "vivid"),
                    n=1
                )
            else:  # gpt-image-1
                response = self.client.images.generate(
                    model="gpt-image-1",
                    prompt=prompt,
                    size=model_settings.get("size", "1024x1024"),
                    quality=model_settings.get("quality", "auto"),
                    n=1
                )
            
            elapsed = time.time() - start_time
            
            # Get image data
            image_url = getattr(response.data[0], 'url', None)
            b64_json = getattr(response.data[0], 'b64_json', None)
            revised_prompt = getattr(response.data[0], 'revised_prompt', None)
            
            # Download/decode image
            if b64_json:
                image_data = base64.b64decode(b64_json)
                img = Image.open(BytesIO(image_data))
            elif image_url:
                img_response = requests.get(image_url)
                img = Image.open(BytesIO(img_response.content))
            else:
                raise Exception("No image data in response")
            
            # Save image
            save_path = self._save_image(img, monster_id, style, pack_name)
            
            # Generate thumbnail
            thumb_path = self._generate_thumbnail(img, monster_id, style, pack_name)
            
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
                            "endpoint": "monster_generator",
                            "purpose": "monster_portrait",
                            "monster_id": monster_id,
                            "n": 1
                        }
                    )
            except Exception:
                pass  # Fail open
            
            return {
                "success": True,
                "monster_id": monster_id,
                "style": style,
                "model": model,
                "image_path": str(save_path),
                "thumbnail_path": str(thumb_path),
                "generation_time": elapsed,
                "revised_prompt": revised_prompt,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "success": False,
                "monster_id": monster_id,
                "error": str(e)
            }
    
    def _save_image(
        self, 
        img: Image.Image, 
        monster_id: str, 
        style: str,
        pack_name: Optional[str] = None
    ) -> Path:
        """Save generated image to appropriate pack directory"""
        if pack_name:
            base_dir = Path(f"graphic_packs/{pack_name}/monsters")
        else:
            base_dir = Path(f"graphic_packs/temp_{style}/monsters")
        
        base_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = base_dir / f"{monster_id}.jpg"
        img.save(file_path, "JPEG", quality=95)
        
        return file_path
    
    def _generate_thumbnail(
        self,
        img: Image.Image,
        monster_id: str,
        style: str,
        pack_name: Optional[str] = None
    ) -> Path:
        """Generate and save thumbnail"""
        if pack_name:
            base_dir = Path(f"graphic_packs/{pack_name}/monsters")
        else:
            base_dir = Path(f"graphic_packs/temp_{style}/monsters")
        
        base_dir.mkdir(parents=True, exist_ok=True)
        
        # Create 60x60 thumbnail
        thumb = img.copy()
        thumb.thumbnail((60, 60), Image.Resampling.LANCZOS)
        
        file_path = base_dir / f"{monster_id}_thumb.jpg"
        thumb.save(file_path, "JPEG", quality=85)
        
        return file_path
    
    async def batch_generate_pack(
        self,
        pack_name: str,
        style: str = "photorealistic",
        monsters: Optional[List[str]] = None,
        model: str = "dall-e-3",
        progress_callback=None
    ) -> Dict:
        """
        Generate images for multiple monsters in batch
        
        Args:
            pack_name: Name of the pack to generate
            style: Style template to use
            monsters: List of monster IDs, or None for all
            model: AI model to use
            progress_callback: Optional callback for progress updates
            
        Returns:
            Dictionary with batch results
        """
        # Get list of monsters to generate
        if monsters is None:
            monsters = list(self.bestiary.get("monsters", {}).keys())
        
        results = {
            "pack_name": pack_name,
            "style": style,
            "total": len(monsters),
            "successful": [],
            "failed": [],
            "start_time": datetime.now().isoformat()
        }
        
        for i, monster_id in enumerate(monsters):
            # Progress callback
            if progress_callback:
                progress_callback({
                    "current": i + 1,
                    "total": len(monsters),
                    "monster": monster_id,
                    "percent": ((i + 1) / len(monsters)) * 100
                })
            
            # Generate image
            result = self.generate_monster_image(
                monster_id=monster_id,
                style=style,
                model=model,
                pack_name=pack_name
            )
            
            if result["success"]:
                results["successful"].append(monster_id)
            else:
                results["failed"].append({
                    "monster": monster_id,
                    "error": result.get("error", "Unknown error")
                })
            
            # Rate limiting (avoid hitting API limits)
            if i < len(monsters) - 1:
                await asyncio.sleep(2)  # 2 second delay between requests
        
        results["end_time"] = datetime.now().isoformat()
        results["success_rate"] = len(results["successful"]) / results["total"] * 100
        
        # Update pack manifest
        self._update_pack_manifest(pack_name, style, results["successful"])
        
        return results
    
    def _update_pack_manifest(
        self,
        pack_name: str,
        style: str,
        monsters: List[str]
    ):
        """Update the pack manifest with generated monsters"""
        manifest_path = Path(f"graphic_packs/{pack_name}/manifest.json")
        
        if manifest_path.exists():
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
        else:
            # Create new manifest
            manifest = {
                "name": pack_name,
                "version": "1.0.0",
                "author": "Module Toolkit",
                "style_template": style,
                "created_date": datetime.now().strftime("%Y-%m-%d"),
                "monsters_included": []
            }
        
        # Update monsters list
        existing = set(manifest.get("monsters_included", []))
        existing.update(monsters)
        manifest["monsters_included"] = sorted(list(existing))
        manifest["total_monsters"] = len(manifest["monsters_included"])
        manifest["last_modified"] = datetime.now().strftime("%Y-%m-%d")
        
        # Save updated manifest
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
    
    def get_available_styles(self) -> List[str]:
        """Get list of available style templates"""
        return list(self.style_templates.get("styles", {}).keys())
    
    def get_monster_list(self, pack_name: Optional[str] = "photorealistic") -> List[Dict]:
        """Get list of all monsters from bestiary and pack"""
        monsters_dict = {}
        pack_monster_ids = set()
        
        # First, scan pack folder to identify which monsters are in the pack
        if pack_name:
            pack_images_path = Path(f'graphic_packs/{pack_name}/monsters')
            if pack_images_path.exists():
                # Check JPG files
                for img_file in pack_images_path.glob('*.jpg'):
                    if not img_file.stem.endswith('_thumb'):
                        pack_monster_ids.add(img_file.stem)
                
                # Check PNG files
                for img_file in pack_images_path.glob('*.png'):
                    if not img_file.stem.endswith('_thumb'):
                        pack_monster_ids.add(img_file.stem)
        
        # Add bestiary monsters with correct source classification
        for monster_id, data in self.bestiary.get("monsters", {}).items():
            # Determine source based on whether monster is in pack
            if monster_id in pack_monster_ids:
                source = "bestiary"  # In both bestiary and pack (Green)
            else:
                source = "bestiary_only"  # In bestiary but not in pack (Red)
            
            monsters_dict[monster_id] = {
                "id": monster_id,
                "name": data.get("name", monster_id),
                "type": data.get("type", "unknown"),
                "tags": data.get("tags", []),
                "source": source
            }
        
        # Add pack-only monsters (not in bestiary)
        for monster_id in pack_monster_ids:
            if monster_id not in monsters_dict:
                # Format name from ID
                name = monster_id.replace('_', ' ').title()
                monsters_dict[monster_id] = {
                    "id": monster_id,
                    "name": name,
                    "type": "custom",
                    "tags": ["pack_only"],
                    "source": "pack_only"  # Only in pack, not in bestiary (Orange)
                }
        
        return sorted(monsters_dict.values(), key=lambda x: x["name"])


# CLI interface for testing
def main():
    """Command-line interface for monster generation"""
    import argparse
    from config import OPENAI_API_KEY
    
    parser = argparse.ArgumentParser(description="Generate monster images")
    parser.add_argument("monster", help="Monster ID from bestiary")
    parser.add_argument("--style", default="photorealistic", help="Style template")
    parser.add_argument("--model", default="auto", help="AI model (gpt-image-1, dall-e-3, auto)")
    parser.add_argument("--pack", help="Pack name to save to")
    
    args = parser.parse_args()
    
    generator = MonsterGenerator(api_key=OPENAI_API_KEY)
    
    result = generator.generate_monster_image(
        monster_id=args.monster,
        style=args.style,
        model=args.model,
        pack_name=args.pack
    )
    
    if result["success"]:
        print(f"\nSuccess! Image saved to: {result['image_path']}")
        print(f"Thumbnail: {result['thumbnail_path']}")
        print(f"Generation time: {result['generation_time']:.2f} seconds")
    else:
        print(f"\nFailed: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    main()