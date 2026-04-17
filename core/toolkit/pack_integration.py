#!/usr/bin/env python3
"""
Pack Integration for Main Game
Provides functions to retrieve assets from the active graphic pack
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict

class PackIntegration:
    """Integration layer between graphic packs and main game"""
    
    ACTIVE_PACK_FILE = "data/active_pack.json"
    DEFAULT_PACK = "default_photorealistic"
    
    def __init__(self):
        """Initialize pack integration"""
        self.active_pack = self._load_active_pack()
    
    def _load_active_pack(self) -> str:
        """Load the currently active pack"""
        active_file = Path(self.ACTIVE_PACK_FILE)
        if active_file.exists():
            try:
                with open(active_file, 'r') as f:
                    data = json.load(f)
                    return data.get("active_pack", self.DEFAULT_PACK)
            except:
                pass
        return self.DEFAULT_PACK
    
    def get_monster_image_path(self, monster_id: str) -> Optional[str]:
        """
        Get the path to a monster's image from the active pack
        
        Args:
            monster_id: ID of the monster
            
        Returns:
            Path to the image file or None if not found
        """
        # Convert monster_id to lowercase for consistent file naming
        monster_id_lower = monster_id.lower()
        # Check active pack first
        image_path = Path(f"graphic_packs/{self.active_pack}/monsters/images/{monster_id_lower}.png")
        if image_path.exists():
            return str(image_path)
        
        # Fall back to default pack
        if self.active_pack != self.DEFAULT_PACK:
            default_path = Path(f"graphic_packs/{self.DEFAULT_PACK}/monsters/images/{monster_id_lower}.png")
            if default_path.exists():
                return str(default_path)
        
        # Check legacy location in web/static/monsters
        legacy_path = Path(f"web/static/monsters/{monster_id_lower}.png")
        if legacy_path.exists():
            return str(legacy_path)
        
        return None
    
    def get_monster_video_path(self, monster_id: str) -> Optional[str]:
        """
        Get the path to a monster's video from the active pack
        
        Args:
            monster_id: ID of the monster
            
        Returns:
            Path to the video file or None if not found
        """
        # Convert monster_id to lowercase for consistent file naming
        monster_id_lower = monster_id.lower()
        # Check active pack first
        video_path = Path(f"graphic_packs/{self.active_pack}/monsters/videos/{monster_id_lower}_video.mp4")
        if video_path.exists():
            return str(video_path)
        
        # Fall back to default pack
        if self.active_pack != self.DEFAULT_PACK:
            default_path = Path(f"graphic_packs/{self.DEFAULT_PACK}/monsters/videos/{monster_id_lower}_video.mp4")
            if default_path.exists():
                return str(default_path)
        
        # Check legacy location in web/static/media/monsters
        legacy_path = Path(f"web/static/media/monsters/{monster_id_lower}_video.mp4")
        if legacy_path.exists():
            return str(legacy_path)
        
        return None
    
    def get_monster_thumbnail_path(self, monster_id: str) -> Optional[str]:
        """
        Get the path to a monster's thumbnail from the active pack
        
        Args:
            monster_id: ID of the monster
            
        Returns:
            Path to the thumbnail file or None if not found
        """
        # Convert monster_id to lowercase for consistent file naming
        monster_id_lower = monster_id.lower()
        # Check active pack first
        thumb_path = Path(f"graphic_packs/{self.active_pack}/monsters/thumbnails/{monster_id_lower}_thumb.jpg")
        if thumb_path.exists():
            return str(thumb_path)
        
        # Fall back to default pack
        if self.active_pack != self.DEFAULT_PACK:
            default_path = Path(f"graphic_packs/{self.DEFAULT_PACK}/monsters/thumbnails/{monster_id_lower}_thumb.jpg")
            if default_path.exists():
                return str(default_path)
        
        # Check legacy location
        legacy_path = Path(f"web/static/media/monsters/{monster_id_lower}_thumb.jpg")
        if legacy_path.exists():
            return str(legacy_path)
        
        return None
    
    def get_pack_info(self) -> Dict:
        """
        Get information about the active pack
        
        Returns:
            Dictionary with pack information
        """
        manifest_path = Path(f"graphic_packs/{self.active_pack}/manifest.json")
        
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        # Return basic info if manifest not found
        return {
            "name": self.active_pack,
            "version": "unknown",
            "style_template": "unknown",
            "total_monsters": 0
        }
    
    def refresh_active_pack(self):
        """Reload the active pack configuration"""
        self.active_pack = self._load_active_pack()
    
    def get_available_packs(self) -> list:
        """Get list of available packs"""
        packs_dir = Path("graphic_packs")
        packs = []
        
        if packs_dir.exists():
            for pack_dir in packs_dir.iterdir():
                if pack_dir.is_dir():
                    manifest_path = pack_dir / "manifest.json"
                    if manifest_path.exists():
                        try:
                            with open(manifest_path, 'r') as f:
                                manifest = json.load(f)
                                packs.append({
                                    "name": pack_dir.name,
                                    "display_name": manifest.get("name", pack_dir.name),
                                    "style": manifest.get("style_template", "unknown"),
                                    "is_active": pack_dir.name == self.active_pack
                                })
                        except:
                            pass
        
        return packs


# Global instance for easy import
pack_integration = PackIntegration()

# Convenience functions
def get_monster_image(monster_id: str) -> Optional[str]:
    """Get monster image path from active pack"""
    return pack_integration.get_monster_image_path(monster_id)

def get_monster_video(monster_id: str) -> Optional[str]:
    """Get monster video path from active pack"""
    return pack_integration.get_monster_video_path(monster_id)

def get_monster_thumbnail(monster_id: str) -> Optional[str]:
    """Get monster thumbnail path from active pack"""
    return pack_integration.get_monster_thumbnail_path(monster_id)

def refresh_pack():
    """Refresh the active pack configuration"""
    pack_integration.refresh_active_pack()

def get_active_pack_info() -> Dict:
    """Get information about the active pack"""
    return pack_integration.get_pack_info()