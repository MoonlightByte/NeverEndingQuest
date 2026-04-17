#!/usr/bin/env python3
"""
Pack Management System for Module Toolkit
Handles creation, import, export, and activation of graphic packs
"""

import os
import json
import shutil
import zipfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List
import hashlib

class PackManager:
    """Service for managing graphic packs"""
    
    ACTIVE_PACK_FILE = "data/active_pack.json"
    PACKS_DIRECTORY = "graphic_packs"
    
    def __init__(self):
        """Initialize the pack manager"""
        self.packs_dir = Path(self.PACKS_DIRECTORY)
        self.packs_dir.mkdir(exist_ok=True)
        
        # Load active pack configuration
        self.active_pack = self._load_active_pack()
    
    def _load_active_pack(self) -> Optional[str]:
        """Load the currently active pack"""
        active_file = Path(self.ACTIVE_PACK_FILE)
        if active_file.exists():
            with open(active_file, 'r') as f:
                data = json.load(f)
                return data.get("active_pack", "photorealistic")
        return "photorealistic"
    
    def _save_active_pack(self, pack_name: str):
        """Save the active pack configuration"""
        active_file = Path(self.ACTIVE_PACK_FILE)
        active_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(active_file, 'w') as f:
            json.dump({
                "active_pack": pack_name,
                "activated_at": datetime.now().isoformat()
            }, f, indent=2)
        
        self.active_pack = pack_name
    
    def create_pack(
        self,
        name: str,
        style_template: str,
        author: str = "Module Toolkit",
        description: str = "",
        display_name: str = None
    ) -> Dict:
        """
        Create a new graphic pack
        
        Args:
            name: Name of the pack (internal ID)
            style_template: Style template to use
            author: Pack author
            description: Pack description
            display_name: Display name for the pack
            
        Returns:
            Creation result dictionary
        """
        # Sanitize pack name
        safe_name = name.replace(" ", "_").lower()
        pack_dir = self.packs_dir / safe_name
        
        if pack_dir.exists():
            return {
                "success": False,
                "error": f"Pack '{safe_name}' already exists"
            }
        
        try:
            # Create directory structure
            (pack_dir / "monsters" / "videos").mkdir(parents=True)
            (pack_dir / "monsters" / "images").mkdir(parents=True)
            (pack_dir / "monsters" / "thumbnails").mkdir(parents=True)
            
            # Create manifest
            manifest = {
                "name": name,
                "safe_name": safe_name,
                "display_name": display_name or name,  # Use display_name if provided
                "version": "1.0.0",
                "author": author,
                "description": description,
                "style_template": style_template,
                "created_date": datetime.now().strftime("%Y-%m-%d"),
                "last_modified": datetime.now().strftime("%Y-%m-%d"),
                "total_monsters": 0,
                "monsters_included": [],
                "file_structure": {
                    "images": "monsters/images/",
                    "videos": "monsters/videos/",
                    "thumbnails": "monsters/thumbnails/"
                },
                "metadata": {
                    "license": "Custom",
                    "compatible_version": "0.2.0+",
                    "tags": [style_template],
                    "preview_image": None
                }
            }
            
            manifest_path = pack_dir / "manifest.json"
            with open(manifest_path, 'w') as f:
                json.dump(manifest, f, indent=2)
            
            # Create README
            readme_content = f"""# {name}

## Description
{description or 'A custom graphic pack for NeverEndingQuest'}

## Style
Based on: {style_template}

## Author
{author}

## Installation
1. Place this pack in the `graphic_packs` directory
2. Select it from the game settings

## Contents
- Images: monsters/images/
- Videos: monsters/videos/
- Thumbnails: monsters/thumbnails/

Created: {datetime.now().strftime("%Y-%m-%d")}
"""
            
            readme_path = pack_dir / "README.md"
            with open(readme_path, 'w') as f:
                f.write(readme_content)
            
            print(f"Created pack: {safe_name}")
            
            return {
                "success": True,
                "pack_name": safe_name,
                "pack_dir": str(pack_dir),
                "manifest": manifest
            }
            
        except Exception as e:
            # Clean up on failure
            if pack_dir.exists():
                shutil.rmtree(pack_dir)
            
            return {
                "success": False,
                "error": str(e)
            }
    
    def import_pack(self, zip_path: str, target_folder_name: Optional[str] = None, 
                   import_monsters: bool = True, import_npcs: bool = True) -> Dict:
        """
        Import a graphic pack from ZIP file with selective asset import
        
        Args:
            zip_path: Path to the ZIP file
            target_folder_name: Optional custom folder name for the pack
            import_monsters: Whether to import monster assets
            import_npcs: Whether to import NPC assets
            
        Returns:
            Import result dictionary
        """
        if not os.path.exists(zip_path):
            return {
                "success": False,
                "error": f"File not found: {zip_path}"
            }
        
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                # Check for manifest
                if 'manifest.json' not in zip_ref.namelist():
                    return {
                        "success": False,
                        "error": "Invalid pack: missing manifest.json"
                    }
                
                # Read manifest
                with zip_ref.open('manifest.json') as f:
                    manifest = json.load(f)
                
                # Use target_folder_name if provided, otherwise use name from manifest
                if target_folder_name:
                    # Sanitize the target folder name to prevent directory traversal
                    pack_name = target_folder_name.replace("..", "").replace("/", "").replace("\\", "")
                    pack_name = pack_name.replace(" ", "_").lower()
                else:
                    pack_name = manifest.get('safe_name', manifest.get('name', 'imported_pack'))
                    pack_name = pack_name.replace(" ", "_").lower()
                
                # Check if pack already exists
                pack_dir = self.packs_dir / pack_name
                if pack_dir.exists():
                    # Version check
                    existing_manifest_path = pack_dir / "manifest.json"
                    if existing_manifest_path.exists():
                        with open(existing_manifest_path, 'r') as f:
                            existing_manifest = json.load(f)
                        
                        if existing_manifest.get('version', '0') >= manifest.get('version', '0'):
                            return {
                                "success": False,
                                "error": f"Pack '{pack_name}' already exists with same or newer version"
                            }
                    
                    # Backup existing pack
                    backup_name = f"{pack_name}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    shutil.move(str(pack_dir), str(self.packs_dir / backup_name))
                    print(f"Backed up existing pack to {backup_name}")
                
                # Create pack directory
                pack_dir.mkdir(parents=True, exist_ok=True)
                
                # Selectively extract files based on import options
                monsters_imported = 0
                npcs_imported = 0
                
                for member in zip_ref.namelist():
                    # Always extract manifest and readme files
                    if member in ['manifest.json', 'README.md'] or member.endswith('/'):
                        zip_ref.extract(member, pack_dir)
                        continue
                    
                    # Check if we should import this file
                    should_extract = False
                    
                    if member.startswith('monsters/') and import_monsters:
                        should_extract = True
                        if not member.endswith('/') and '_thumb' not in member:
                            monsters_imported += 1
                    elif member.startswith('npcs/') and import_npcs:
                        should_extract = True
                        if not member.endswith('/') and '_thumb' not in member:
                            npcs_imported += 1
                    
                    if should_extract:
                        zip_ref.extract(member, pack_dir)
                
                # Ensure required directories exist
                if import_monsters:
                    required_dirs = ['monsters/videos', 'monsters/images', 'monsters/thumbnails']
                    for dir_path in required_dirs:
                        (pack_dir / dir_path).mkdir(parents=True, exist_ok=True)
                
                if import_npcs:
                    (pack_dir / 'npcs').mkdir(parents=True, exist_ok=True)
                
                # Update manifest with import info
                manifest['imported_date'] = datetime.now().strftime("%Y-%m-%d")
                manifest['imported_from'] = os.path.basename(zip_path)
                
                with open(pack_dir / 'manifest.json', 'w') as f:
                    json.dump(manifest, f, indent=2)
                
                # Log what was imported
                import_summary = []
                if monsters_imported > 0:
                    import_summary.append(f"{monsters_imported} monsters")
                if npcs_imported > 0:
                    import_summary.append(f"{npcs_imported} NPCs")
                
                if import_summary:
                    print(f"Imported pack: {pack_name} ({', '.join(import_summary)})")
                else:
                    print(f"Created pack structure: {pack_name} (no assets imported)")
                
                return {
                    "success": True,
                    "pack_name": pack_name,
                    "pack_dir": str(pack_dir),
                    "manifest": manifest,
                    "monsters_imported": monsters_imported,
                    "npcs_imported": npcs_imported,
                    "total_monsters": len(manifest.get('monsters_included', []))
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Import failed: {str(e)}"
            }
    
    def export_pack(self, pack_name: str, output_dir: Optional[str] = None) -> Dict:
        """
        Export a graphic pack to ZIP file
        
        Args:
            pack_name: Name of the pack to export
            output_dir: Optional output directory (defaults to current)
            
        Returns:
            Export result dictionary
        """
        pack_dir = self.packs_dir / pack_name
        
        if not pack_dir.exists():
            return {
                "success": False,
                "error": f"Pack '{pack_name}' not found"
            }
        
        try:
            # Prepare output path
            output_dir = Path(output_dir) if output_dir else Path.cwd()
            output_dir.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            zip_filename = f"{pack_name}_{timestamp}.zip"
            zip_path = output_dir / zip_filename
            
            # Create ZIP file
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
                # Add all files from pack directory
                for file_path in pack_dir.rglob('*'):
                    if file_path.is_file():
                        arcname = file_path.relative_to(pack_dir)
                        zip_ref.write(file_path, arcname)
                        print(f"  Added: {arcname}")
            
            # Calculate ZIP size
            zip_size_mb = zip_path.stat().st_size / (1024 * 1024)
            
            print(f"Exported pack to: {zip_path}")
            
            return {
                "success": True,
                "pack_name": pack_name,
                "zip_path": str(zip_path),
                "zip_size_mb": round(zip_size_mb, 2)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Export failed: {str(e)}"
            }
    
    def activate_pack(self, pack_name: str, create_backup: bool = False) -> Dict:
        """
        Activate a graphic pack for use in the game
        
        Args:
            pack_name: Name of the pack to activate
            
        Returns:
            Activation result dictionary
        """
        pack_dir = self.packs_dir / pack_name
        
        if not pack_dir.exists():
            return {
                "success": False,
                "error": f"Pack '{pack_name}' not found"
            }
        
        try:
            # Load pack manifest
            manifest_path = pack_dir / "manifest.json"
            if manifest_path.exists():
                with open(manifest_path, 'r') as f:
                    manifest = json.load(f)
            else:
                manifest = {"name": pack_name}
            
            # Create backup of current pack if requested
            backup_created = False
            backup_name = None
            
            if create_backup and self.active_pack and self.active_pack != pack_name:
                # Generate backup name with timestamp
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"{self.active_pack}_backup_{timestamp}"
                backup_dir = self.packs_dir / backup_name
                
                # Copy current pack to backup
                current_pack_dir = self.packs_dir / self.active_pack
                if current_pack_dir.exists():
                    try:
                        shutil.copytree(current_pack_dir, backup_dir)
                        
                        # Update backup manifest
                        backup_manifest_path = backup_dir / "manifest.json"
                        if backup_manifest_path.exists():
                            with open(backup_manifest_path, 'r') as f:
                                backup_manifest = json.load(f)
                            
                            # Update manifest with backup info
                            original_name = backup_manifest.get("display_name", backup_manifest.get("name", self.active_pack))
                            backup_manifest["name"] = backup_name
                            backup_manifest["display_name"] = f"{original_name} (Backup {datetime.now().strftime('%Y-%m-%d %H:%M')})"
                            backup_manifest["is_backup"] = True
                            backup_manifest["original_pack"] = self.active_pack
                            backup_manifest["backup_date"] = datetime.now().isoformat()
                            
                            with open(backup_manifest_path, 'w') as f:
                                json.dump(backup_manifest, f, indent=2)
                        
                        backup_created = True
                        print(f"Created backup: {backup_name}")
                    except Exception as e:
                        print(f"Warning: Could not create backup: {e}")
            
            # Handle game assets directories
            game_monsters_dir = Path("web/static/media/monsters")
            game_npcs_dir = Path("web/static/media/npcs")
            
            # Copy monster assets to game directory
            pack_monsters_dir = pack_dir / "monsters"
            if pack_monsters_dir.exists():
                # Ensure game assets directory exists
                game_monsters_dir.mkdir(parents=True, exist_ok=True)
                
                # Handle new structure: all files directly in monsters/ folder
                for file in pack_monsters_dir.glob("*"):
                    if file.is_file():
                        if file.suffix in ['.png', '.jpg', '.jpeg', '.mp4']:
                            shutil.copy2(file, game_monsters_dir / file.name)
                
                # Handle old structure: separate subdirectories
                # Copy thumbnails
                thumb_source = pack_monsters_dir / "thumbnails"
                if thumb_source.exists():
                    for thumb in thumb_source.glob("*.jpg"):
                        shutil.copy2(thumb, game_monsters_dir / thumb.name)
                
                # Copy videos
                video_source = pack_monsters_dir / "videos"
                if video_source.exists():
                    for video in video_source.glob("*.mp4"):
                        shutil.copy2(video, game_monsters_dir / video.name)
                
                # Copy images
                image_source = pack_monsters_dir / "images"
                if image_source.exists():
                    for image in image_source.glob("*"):
                        if image.suffix in ['.png', '.jpg', '.jpeg']:
                            shutil.copy2(image, game_monsters_dir / image.name)
            
            # Copy NPC assets to game directory
            pack_npcs_dir = pack_dir / "npcs"
            if pack_npcs_dir.exists():
                # Ensure game NPCs directory exists
                game_npcs_dir.mkdir(parents=True, exist_ok=True)
                
                # Copy all NPC files
                for file in pack_npcs_dir.glob("*"):
                    if file.is_file():
                        if file.suffix in ['.png', '.jpg', '.jpeg', '.mp4']:
                            shutil.copy2(file, game_npcs_dir / file.name)
            
            # Save as active pack
            self._save_active_pack(pack_name)
            
            print(f"Activated pack: {pack_name}")
            if pack_monsters_dir.exists():
                print(f"  - Copied monster assets to {game_monsters_dir}")
            if pack_npcs_dir.exists():
                print(f"  - Copied NPC assets to {game_npcs_dir}")
            
            return {
                "success": True,
                "pack_name": pack_name,
                "manifest": manifest,
                "previous_pack": self.active_pack,
                "assets_copied": True,
                "backup_created": backup_created,
                "backup_name": backup_name
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Activation failed: {str(e)}"
            }
    
    def list_available_packs(self) -> List[Dict]:
        """
        List all available graphic packs
        
        Returns:
            List of pack information dictionaries
        """
        packs = []
        
        for pack_dir in self.packs_dir.iterdir():
            if pack_dir.is_dir():
                manifest_path = pack_dir / "manifest.json"
                
                if manifest_path.exists():
                    with open(manifest_path, 'r') as f:
                        manifest = json.load(f)
                    
                    # Calculate pack size
                    pack_size = sum(
                        f.stat().st_size for f in pack_dir.rglob('*') if f.is_file()
                    ) / (1024 * 1024)  # MB
                    
                    # Count actual files (supporting both old and new structure)
                    monsters_dir = pack_dir / "monsters"
                    npcs_dir = pack_dir / "npcs"
                    video_count = 0
                    image_count = 0
                    thumb_count = 0
                    npc_count = 0
                    
                    # Count NPCs if directory exists
                    if npcs_dir.exists():
                        for file in npcs_dir.glob("*"):
                            if file.is_file():
                                if file.suffix in [".png", ".jpg", ".jpeg"]:
                                    if "_thumb" not in file.stem:
                                        npc_count += 1
                    
                    # Also check manifest for NPC count
                    npc_count = max(
                        npc_count,
                        manifest.get("total_npcs", 0),
                        len(manifest.get("npcs_included", []))
                    )
                    
                    if monsters_dir.exists():
                        # New structure: everything in monsters/ folder
                        for file in monsters_dir.glob("*"):
                            if file.is_file():
                                if file.suffix == ".mp4":
                                    video_count += 1
                                elif file.suffix in [".png", ".jpg", ".jpeg"]:
                                    if "_thumb" in file.stem or "_thumbnail" in file.stem:
                                        thumb_count += 1
                                    else:
                                        image_count += 1
                        
                        # Old structure: separate subdirectories
                        if (monsters_dir / "videos").exists():
                            video_count += len(list((monsters_dir / "videos").glob("*.mp4")))
                        if (monsters_dir / "images").exists():
                            image_count += len(list((monsters_dir / "images").glob("*")))
                        if (monsters_dir / "thumbnails").exists():
                            thumb_count += len(list((monsters_dir / "thumbnails").glob("*")))
                    
                    # Determine total monsters (unique count)
                    monster_count = max(
                        manifest.get("total_monsters", 0),
                        len(manifest.get("monsters", {})),
                        len(manifest.get("monsters_included", [])),
                        image_count  # Use image count as fallback
                    )
                    
                    packs.append({
                        "name": pack_dir.name,
                        "display_name": manifest.get("display_name", manifest.get("name", pack_dir.name)),
                        "version": manifest.get("version", "1.0.0"),
                        "author": manifest.get("author", "Unknown"),
                        "style": manifest.get("style", manifest.get("style_template", "unknown")),
                        "style_template": manifest.get("style_template", manifest.get("style", "unknown")),
                        "total_monsters": monster_count,
                        "total_npcs": npc_count,
                        "total_videos": video_count,
                        "monsters_count": monster_count,
                        "size_mb": round(pack_size, 2),
                        "created": manifest.get("created_at", manifest.get("created_date", "Unknown")),
                        "is_active": pack_dir.name == self.active_pack
                    })
                else:
                    # Basic info for packs without manifest
                    packs.append({
                        "name": pack_dir.name,
                        "display_name": pack_dir.name,
                        "version": "Unknown",
                        "author": "Unknown",
                        "style": "unknown",
                        "total_monsters": 0,
                        "total_npcs": 0,
                        "total_videos": 0,
                        "size_mb": 0,
                        "created": "Unknown",
                        "is_active": pack_dir.name == self.active_pack
                    })
        
        return sorted(packs, key=lambda x: x["name"])
    
    def get_pack_details(self, pack_name: str) -> Optional[Dict]:
        """
        Get detailed information about a specific pack
        
        Args:
            pack_name: Name of the pack
            
        Returns:
            Detailed pack information or None if not found
        """
        pack_dir = self.packs_dir / pack_name
        
        if not pack_dir.exists():
            return None
        
        manifest_path = pack_dir / "manifest.json"
        if not manifest_path.exists():
            return None
        
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        
        # Count actual files (supporting both old and new structure)
        monsters_dir = pack_dir / "monsters"
        video_count = 0
        image_count = 0
        thumb_count = 0
        
        if monsters_dir.exists():
            # New structure: everything in monsters/ folder
            for file in monsters_dir.glob("*"):
                if file.is_file():
                    if file.suffix == ".mp4":
                        video_count += 1
                    elif file.suffix in [".png", ".jpg", ".jpeg"]:
                        if "_thumb" in file.stem or "_thumbnail" in file.stem:
                            thumb_count += 1
                        else:
                            image_count += 1
            
            # Old structure: check separate subdirectories too
            if (monsters_dir / "videos").exists():
                video_count = len(list((monsters_dir / "videos").glob("*.mp4")))
            if (monsters_dir / "images").exists():
                image_count = len(list((monsters_dir / "images").glob("*")))
            if (monsters_dir / "thumbnails").exists():
                thumb_count = len(list((monsters_dir / "thumbnails").glob("*")))
        
        # Calculate sizes
        total_size = sum(
            f.stat().st_size for f in pack_dir.rglob('*') if f.is_file()
        ) / (1024 * 1024)  # MB
        
        return {
            "manifest": manifest,
            "stats": {
                "total_size_mb": round(total_size, 2),
                "video_count": video_count,
                "image_count": image_count,
                "thumbnail_count": thumb_count
            },
            "path": str(pack_dir),
            "is_active": pack_name == self.active_pack
        }
    
    def delete_pack(self, pack_name: str) -> Dict:
        """
        Delete a graphic pack
        
        Args:
            pack_name: Name of the pack to delete
            
        Returns:
            Deletion result dictionary
        """
        if pack_name == "photorealistic":
            return {
                "success": False,
                "error": "Cannot delete the default pack"
            }
        
        if pack_name == self.active_pack:
            return {
                "success": False,
                "error": "Cannot delete the active pack. Please activate another pack first."
            }
        
        pack_dir = self.packs_dir / pack_name
        
        if not pack_dir.exists():
            return {
                "success": False,
                "error": f"Pack '{pack_name}' not found"
            }
        
        try:
            # Create backup before deletion
            backup_dir = self.packs_dir / ".deleted"
            backup_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{pack_name}_{timestamp}"
            shutil.move(str(pack_dir), str(backup_path))
            
            print(f"Deleted pack: {pack_name} (backed up to {backup_path})")
            
            return {
                "success": True,
                "pack_name": pack_name,
                "backup_path": str(backup_path)
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Deletion failed: {str(e)}"
            }
    
    def get_active_pack(self) -> str:
        """Get the currently active pack name"""
        return self.active_pack


# CLI interface for testing
def main():
    """Command-line interface for pack management"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Manage graphic packs")
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Create pack
    create_parser = subparsers.add_parser('create', help='Create new pack')
    create_parser.add_argument('name', help='Pack name')
    create_parser.add_argument('--style', default='photorealistic', help='Style template')
    create_parser.add_argument('--author', default='Module Toolkit', help='Author name')
    
    # List packs
    list_parser = subparsers.add_parser('list', help='List available packs')
    
    # Activate pack
    activate_parser = subparsers.add_parser('activate', help='Activate a pack')
    activate_parser.add_argument('name', help='Pack name')
    
    # Export pack
    export_parser = subparsers.add_parser('export', help='Export pack to ZIP')
    export_parser.add_argument('name', help='Pack name')
    export_parser.add_argument('--output', help='Output directory')
    
    # Import pack
    import_parser = subparsers.add_parser('import', help='Import pack from ZIP')
    import_parser.add_argument('file', help='ZIP file path')
    
    args = parser.parse_args()
    
    manager = PackManager()
    
    if args.command == 'create':
        result = manager.create_pack(
            name=args.name,
            style_template=args.style,
            author=args.author
        )
        if result['success']:
            print(f"Created pack: {result['pack_name']}")
        else:
            print(f"Failed: {result['error']}")
    
    elif args.command == 'list':
        packs = manager.list_available_packs()
        print("\nAvailable Graphic Packs:")
        print("-" * 60)
        for pack in packs:
            active = " [ACTIVE]" if pack['is_active'] else ""
            print(f"{pack['name']}{active}")
            print(f"  Version: {pack['version']}")
            print(f"  Author: {pack['author']}")
            print(f"  Style: {pack['style']}")
            print(f"  Monsters: {pack['monsters']}")
            print(f"  Size: {pack['size_mb']} MB")
            print()
    
    elif args.command == 'activate':
        result = manager.activate_pack(args.name)
        if result['success']:
            print(f"Activated pack: {result['pack_name']}")
        else:
            print(f"Failed: {result['error']}")
    
    elif args.command == 'export':
        result = manager.export_pack(args.name, args.output)
        if result['success']:
            print(f"Exported to: {result['zip_path']}")
            print(f"Size: {result['zip_size_mb']} MB")
        else:
            print(f"Failed: {result['error']}")
    
    elif args.command == 'import':
        result = manager.import_pack(args.file)
        if result['success']:
            print(f"Imported pack: {result['pack_name']}")
            print(f"Monsters: {result['total_monsters']}")
        else:
            print(f"Failed: {result['error']}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()