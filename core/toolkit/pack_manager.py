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
from typing import Optional, Dict, List, Set
import hashlib

class PackManager:
    """Service for managing graphic packs"""
    
    ACTIVE_PACK_FILE = "data/active_pack.json"
    PACKS_DIRECTORY = "graphic_packs"
    STATIC_MEDIA_ROOT = Path("web/static/media")
    STATIC_MEDIA_TARGETS = {
        "monsters": "monsters",
        "npcs": "npcs",
    }
    
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

    def get_active_pack_names(self) -> List[str]:
        """Return active packs in deterministic order.

        Supports either legacy `active_pack` (single string) or newer
        `active_packs` (ordered list) payloads in ACTIVE_PACK_FILE.
        """
        active_file = Path(self.ACTIVE_PACK_FILE)
        if not active_file.exists():
            return [self.active_pack] if self.active_pack else []

        try:
            with open(active_file, "r") as handle:
                data = json.load(handle)
        except Exception:
            return [self.active_pack] if self.active_pack else []

        ordered: List[str] = []
        seen: Set[str] = set()

        listed = data.get("active_packs", [])
        if isinstance(listed, list):
            for raw in listed:
                value = str(raw or "").strip()
                if not value or value in seen:
                    continue
                seen.add(value)
                ordered.append(value)

        single = str(data.get("active_pack", self.active_pack) or "").strip()
        if single and single not in seen:
            ordered.append(single)

        return ordered

    def _iter_pack_media_files(self, pack_name: str, media_type: str) -> Dict[str, Path]:
        """List source files for one pack/media type keyed by filename."""
        media_key = str(media_type or "").strip().lower()
        if media_key not in self.STATIC_MEDIA_TARGETS:
            raise ValueError(f"Unsupported media type: {media_type}")

        pack_dir = self.packs_dir / pack_name
        if not pack_dir.exists():
            return {}

        files: Dict[str, Path] = {}

        if media_key == "npcs":
            candidates = [pack_dir / "npcs"]
        else:
            monsters_dir = pack_dir / "monsters"
            candidates = [
                monsters_dir,
                monsters_dir / "images",
                monsters_dir / "thumbnails",
                monsters_dir / "videos",
            ]

        for folder in candidates:
            if not folder.exists() or not folder.is_dir():
                continue
            for entry in folder.iterdir():
                if not entry.is_file():
                    continue
                files[entry.name] = entry

        return files

    def _list_live_static_files(self, media_type: str) -> List[str]:
        """List current runtime static files for media type."""
        media_key = str(media_type or "").strip().lower()
        target_name = self.STATIC_MEDIA_TARGETS.get(media_key)
        if not target_name:
            raise ValueError(f"Unsupported media type: {media_type}")

        target_dir = self.STATIC_MEDIA_ROOT / target_name
        if not target_dir.exists():
            return []

        return sorted([item.name for item in target_dir.iterdir() if item.is_file()])

    def audit_static_runtime_cache(
        self,
        active_packs: Optional[List[str]] = None,
    ) -> Dict:
        """Dry-run audit for strict-cache rebuild diagnostics."""
        resolved_packs = [p for p in (active_packs or self.get_active_pack_names()) if p]

        targets: Dict[str, Dict] = {}
        for media_type in self.STATIC_MEDIA_TARGETS:
            live_files = self._list_live_static_files(media_type)
            active_source_files: Dict[str, List[str]] = {}
            active_source_by_pack: Dict[str, List[str]] = {}

            for pack_name in resolved_packs:
                pack_files = sorted(self._iter_pack_media_files(pack_name, media_type).keys())
                active_source_by_pack[pack_name] = pack_files
                for filename in pack_files:
                    active_source_files.setdefault(filename, []).append(pack_name)

            active_union = sorted(active_source_files.keys())
            live_set = set(live_files)
            active_set = set(active_union)

            orphans = sorted(list(live_set - active_set))
            missing_in_live = sorted(list(active_set - live_set))
            collisions = {
                name: packs
                for name, packs in sorted(active_source_files.items())
                if len(packs) > 1
            }

            targets[media_type] = {
                "live_files": live_files,
                "active_pack_files": active_source_by_pack,
                "active_union": active_union,
                "orphaned_files": orphans,
                "missing_in_live": missing_in_live,
                "collisions": collisions,
                "counts": {
                    "live": len(live_files),
                    "active_union": len(active_union),
                    "orphaned": len(orphans),
                    "collisions": len(collisions),
                },
            }

        sibling_dirs = []
        if self.STATIC_MEDIA_ROOT.exists():
            for entry in self.STATIC_MEDIA_ROOT.iterdir():
                if not entry.is_dir():
                    continue
                if entry.name in self.STATIC_MEDIA_TARGETS.values():
                    continue
                sibling_dirs.append(entry.name)

        return {
            "success": True,
            "mode": "dry_run",
            "active_packs": resolved_packs,
            "targets": targets,
            "out_of_scope_sibling_dirs": sorted(sibling_dirs),
            "contract": {
                "module_media_authoritative": True,
                "static_media_is_runtime_cache": True,
                "scope": sorted(list(self.STATIC_MEDIA_TARGETS.values())),
            },
        }

    def snapshot_live_static_media(self, backup_name: Optional[str] = None) -> Dict:
        """Create reversible backup pack from current live static targets."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        resolved_name = str(backup_name or f"live_backup_{timestamp}").strip()
        backup_dir = self.packs_dir / resolved_name

        if backup_dir.exists():
            return {
                "success": False,
                "error": f"Backup pack already exists: {resolved_name}",
            }

        backup_dir.mkdir(parents=True, exist_ok=False)

        counts = {"monsters": 0, "npcs": 0}
        try:
            for media_type, folder_name in self.STATIC_MEDIA_TARGETS.items():
                source_dir = self.STATIC_MEDIA_ROOT / folder_name
                dest_dir = backup_dir / folder_name
                if not source_dir.exists() or not source_dir.is_dir():
                    continue
                dest_dir.mkdir(parents=True, exist_ok=True)
                for entry in source_dir.iterdir():
                    if not entry.is_file():
                        continue
                    shutil.copy2(entry, dest_dir / entry.name)
                    counts[media_type] += 1

            manifest = {
                "name": resolved_name,
                "display_name": f"Live Assets Backup ({datetime.now().strftime('%Y-%m-%d %H:%M')})",
                "description": (
                    "Automatic backup of live runtime static cache for strict-cache rebuild "
                    f"({counts['monsters']} monster files, {counts['npcs']} npc files)."
                ),
                "is_backup": True,
                "backup_type": "live_assets",
                "backup_date": datetime.now().isoformat(),
                "monster_count": counts["monsters"],
                "npc_count": counts["npcs"],
                "created_by": "PackManager.snapshot_live_static_media",
            }
            with open(backup_dir / "manifest.json", "w") as handle:
                json.dump(manifest, handle, indent=2)
        except Exception as exc:
            shutil.rmtree(backup_dir, ignore_errors=True)
            return {"success": False, "error": str(exc)}

        return {
            "success": True,
            "backup_name": resolved_name,
            "backup_path": str(backup_dir),
            "counts": counts,
        }

    def rebuild_static_runtime_cache(
        self,
        active_packs: Optional[List[str]] = None,
        create_backup: bool = False,
        dry_run: bool = True,
    ) -> Dict:
        """Clear/repopulate runtime static cache from active packs only."""
        audit = self.audit_static_runtime_cache(active_packs=active_packs)
        if dry_run:
            return {
                "success": True,
                "action": "dry_run",
                "audit": audit,
                "backup": None,
            }

        resolved_packs = list(audit.get("active_packs", []))
        backup_result = None
        if create_backup:
            backup_result = self.snapshot_live_static_media()
            if not backup_result.get("success"):
                return {
                    "success": False,
                    "error": "Failed to create pre-rebuild backup",
                    "backup": backup_result,
                    "audit": audit,
                }

        targets_result: Dict[str, Dict] = {}
        for media_type, folder_name in self.STATIC_MEDIA_TARGETS.items():
            target_dir = self.STATIC_MEDIA_ROOT / folder_name
            if target_dir.exists():
                shutil.rmtree(target_dir)
            target_dir.mkdir(parents=True, exist_ok=True)

            copied = 0
            overwritten = []
            seen_names: Set[str] = set()

            for pack_name in resolved_packs:
                pack_files = self._iter_pack_media_files(pack_name, media_type)
                for filename in sorted(pack_files.keys()):
                    source_path = pack_files[filename]
                    dest_path = target_dir / filename
                    if filename in seen_names:
                        overwritten.append(filename)
                    shutil.copy2(source_path, dest_path)
                    seen_names.add(filename)
                    copied += 1

            targets_result[media_type] = {
                "copied": copied,
                "overwritten": sorted(list(set(overwritten))),
                "final_file_count": len(list(target_dir.glob("*"))),
                "orphaned_removed": len(
                    audit.get("targets", {})
                    .get(media_type, {})
                    .get("orphaned_files", [])
                ),
            }

        return {
            "success": True,
            "action": "rebuild",
            "active_packs": resolved_packs,
            "backup": backup_result,
            "audit": audit,
            "targets": targets_result,
        }
    
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
            previous_pack = self.active_pack

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
            
            # Save as active pack
            self._save_active_pack(pack_name)

            # TABLETOP MODE: Strict-cache rebuild replaces additive drift.
            rebuild_result = self.rebuild_static_runtime_cache(
                active_packs=[pack_name],
                create_backup=False,
                dry_run=False,
            )
            if not rebuild_result.get("success"):
                return {
                    "success": False,
                    "error": "Activation failed during static cache rebuild",
                    "rebuild": rebuild_result,
                }
            
            print(f"Activated pack: {pack_name}")
            print("  - Rebuilt runtime static cache from selected active pack")
            
            return {
                "success": True,
                "pack_name": pack_name,
                "manifest": manifest,
                "previous_pack": previous_pack,
                "assets_copied": True,
                "backup_created": backup_created,
                "backup_name": backup_name,
                "rebuild": rebuild_result,
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
