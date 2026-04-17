#!/usr/bin/env python3
"""
Video Processing Pipeline for Module Toolkit
Handles monster video import, compression, and organization into graphic packs
"""

import os
import json
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple
import hashlib

class VideoProcessor:
    """Service for processing and managing monster videos"""
    
    # Standard compression settings matching existing pipeline
    COMPRESSION_SETTINGS = {
        "codec": "libx264",
        "preset": "fast",  # Fast preset for quick processing
        "bitrate": "1000k",
        "resolution": "640x640",
        "fps": 24
        # No audio settings - videos are processed without audio
    }
    
    THUMBNAIL_SIZE = (60, 60)
    
    def __init__(self):
        """Initialize the video processor"""
        self.ffmpeg_available = self._check_ffmpeg()
        if not self.ffmpeg_available:
            print("Warning: ffmpeg not available - video processing disabled")
    
    def _check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available"""
        try:
            subprocess.run(['ffmpeg', '-version'], 
                         capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def process_monster_video(
        self,
        input_path: str,
        monster_id: str,
        pack_name: str,
        custom_settings: Optional[Dict] = None,
        skip_compression: bool = False,
        copy_to_monsters: bool = False,
        copy_to_npcs: bool = False
    ) -> Dict:
        """
        Process a monster video file
        
        Args:
            input_path: Path to input video file
            monster_id: ID of the monster
            pack_name: Name of the graphic pack
            custom_settings: Optional custom compression settings
            skip_compression: Skip video compression
            copy_to_monsters: Copy to web/static/media/monsters for immediate monster use
            copy_to_npcs: Copy to web/static/media/npcs for immediate NPC use
            
        Returns:
            Dictionary with processing results
        """
        if not self.ffmpeg_available:
            return {
                "success": False,
                "error": "ffmpeg not available"
            }
        
        if not os.path.exists(input_path):
            return {
                "success": False,
                "error": f"Input file not found: {input_path}"
            }
        
        # Prepare output paths - simplified structure with all files in monsters folder
        # Ensure monster_id is lowercase for consistent file naming
        monster_id_lower = monster_id.lower()
        pack_dir = Path(f"graphic_packs/{pack_name}")
        monsters_dir = pack_dir / "monsters"
        
        monsters_dir.mkdir(parents=True, exist_ok=True)
        
        output_video = monsters_dir / f"{monster_id_lower}_video.mp4"
        output_thumb = monsters_dir / f"{monster_id_lower}_thumb.jpg"
        
        print(f"\nProcessing video for {monster_id}...")
        print(f"Input: {input_path}")
        print(f"Pack: {pack_name}")
        
        try:
            # Get original file size
            original_size = os.path.getsize(input_path) / (1024 * 1024)  # MB
            
            if skip_compression:
                # Just copy the video without compression
                print(f"[INFO] Skipping compression, copying video directly...")
                shutil.copy2(input_path, str(output_video))
                compressed_path = str(output_video)
            else:
                # Compress video
                compressed_path = self.compress_video(
                    input_path, 
                    str(output_video),
                    custom_settings or self.COMPRESSION_SETTINGS
                )
                
                if not compressed_path:
                    # No fallback - compression must work
                    input_exists = os.path.exists(input_path)
                    input_size = os.path.getsize(input_path) if input_exists else 0
                    error_msg = f"Video compression failed. Input exists: {input_exists}, Size: {input_size} bytes"
                    print(f"[ERROR] {error_msg}")
                    raise Exception(error_msg)
            
            # Get compressed size
            compressed_size = os.path.getsize(compressed_path) / (1024 * 1024)  # MB
            compression_ratio = (1 - compressed_size/original_size) * 100
            
            # Generate thumbnail
            thumb_path = self.generate_thumbnail(
                compressed_path,
                str(output_thumb)
            )
            
            if not thumb_path:
                raise Exception("Thumbnail generation failed")
            
            # Calculate video hash for deduplication
            video_hash = self._calculate_file_hash(compressed_path)
            
            result = {
                "success": True,
                "monster_id": monster_id,
                "pack_name": pack_name,
                "video_path": str(output_video),
                "thumbnail_path": str(output_thumb),
                "original_size_mb": round(original_size, 2),
                "compressed_size_mb": round(compressed_size, 2),
                "compression_ratio": round(compression_ratio, 1),
                "video_hash": video_hash,
                "timestamp": datetime.now().isoformat()
            }
            
            # Update pack manifest
            self._update_pack_manifest(pack_name, monster_id, "video")
            
            # Copy to game folders if requested
            if copy_to_monsters:
                game_monsters_dir = Path("web/static/media/monsters")
                game_monsters_dir.mkdir(parents=True, exist_ok=True)
                
                # Copy video
                game_video_path = game_monsters_dir / f"{monster_id_lower}_video.mp4"
                shutil.copy2(str(output_video), str(game_video_path))
                
                # Copy thumbnail
                game_thumb_path = game_monsters_dir / f"{monster_id_lower}_thumb.jpg"
                shutil.copy2(str(output_thumb), str(game_thumb_path))
                
                print(f"  Copied to monsters folder: {game_video_path}")
                result["copied_to_monsters"] = True
            
            if copy_to_npcs:
                game_npcs_dir = Path("web/static/media/npcs")
                game_npcs_dir.mkdir(parents=True, exist_ok=True)
                
                # Copy video
                game_video_path = game_npcs_dir / f"{monster_id_lower}_video.mp4"
                shutil.copy2(str(output_video), str(game_video_path))
                
                # Copy thumbnail
                game_thumb_path = game_npcs_dir / f"{monster_id_lower}_thumb.jpg"
                shutil.copy2(str(output_thumb), str(game_thumb_path))
                
                print(f"  Copied to NPCs folder: {game_video_path}")
                result["copied_to_npcs"] = True
            
            print(f"[OK] Successfully processed {monster_id}")
            print(f"  Compression: {compression_ratio:.1f}% reduction")
            print(f"  Output: {output_video}")
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "monster_id": monster_id,
                "error": str(e)
            }
    
    def compress_video(
        self,
        input_path: str,
        output_path: str,
        settings: Dict
    ) -> Optional[str]:
        """
        Compress video using ffmpeg
        
        Args:
            input_path: Input video file
            output_path: Output video file
            settings: Compression settings
            
        Returns:
            Path to compressed video or None if failed
        """
        # Build proper ffmpeg command with correct settings
        resolution = settings.get('resolution', '640x640')
        width, height = resolution.split('x') if 'x' in resolution else resolution.split(':')
        
        print(f"[DEBUG] Running ffmpeg command:")
        print(f"  Input: {input_path}")
        print(f"  Output: {output_path}")
        
        # Build command as list for better handling
        cmd = [
            'ffmpeg',
            '-i', input_path,
            '-c:v', settings.get('codec', 'libx264'),
            '-preset', settings.get('preset', 'fast'),  # Use preset from settings
            '-b:v', settings.get('bitrate', '1000k'),
            '-vf', f'scale={width}:{height}',  # Simple scale
            '-r', str(settings.get('fps', 24)),
            '-an',  # No audio
            '-movflags', '+faststart',  # Optimize for web streaming
            '-y',  # Overwrite output
            output_path
        ]
        
        cmd_str = ' '.join([f'"{arg}"' if ' ' in arg else arg for arg in cmd])
        
        print(f"  Full command: {cmd_str}")
        
        try:
            # Use subprocess.run for simpler execution
            print(f"[INFO] Starting ffmpeg compression...")
            
            # Run ffmpeg directly with the command list
            result = subprocess.run(
                cmd,  # Use the list directly, not string
                capture_output=True,
                text=True
                # No timeout - it should work immediately
            )
            
            if result.returncode != 0:
                print(f"[ERROR] Compression failed with code {result.returncode}")
                if result.stderr:
                    print(f"[ERROR] ffmpeg stderr output:")
                    print(result.stderr[:1000])
                if result.stdout:
                    print(f"[DEBUG] ffmpeg stdout output:")
                    print(result.stdout[:500])
                return None
            
            print(f"[INFO] Compression successful")
            return output_path
            
        except Exception as e:
            print(f"[ERROR] Compression failed: {e}")
            return None
    
    def generate_thumbnail(
        self,
        video_path: str,
        output_path: str,
        timestamp: str = "00:00:01"
    ) -> Optional[str]:
        """
        Generate thumbnail from video
        
        Args:
            video_path: Input video file
            output_path: Output thumbnail file
            timestamp: Time to extract frame from
            
        Returns:
            Path to thumbnail or None if failed
        """
        cmd = [
            'ffmpeg',
            '-i', video_path,
            '-ss', timestamp,
            '-vf', f'scale={self.THUMBNAIL_SIZE[0]}:{self.THUMBNAIL_SIZE[1]}:force_original_aspect_ratio=increase,crop={self.THUMBNAIL_SIZE[0]}:{self.THUMBNAIL_SIZE[1]}',
            '-frames:v', '1',
            '-q:v', '5',
            '-y',
            output_path
        ]
        
        try:
            # Use Popen for better process control on Windows
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                print(f"[ERROR] Thumbnail generation failed with code {process.returncode}")
                if stderr:
                    print(f"Error details: {stderr[:200]}")
                return None
            
            # Ensure process is fully terminated
            process.wait()
            return output_path
            
        except Exception as e:
            print(f"[ERROR] Thumbnail generation failed: {e}")
            return None
    
    def batch_process_videos(
        self,
        video_files: List[Tuple[str, str]],
        pack_name: str,
        progress_callback=None,
        copy_to_monsters: bool = False,
        copy_to_npcs: bool = False
    ) -> Dict:
        """
        Process multiple video files in batch
        
        Args:
            video_files: List of (input_path, monster_id) tuples
            pack_name: Name of the graphic pack
            progress_callback: Optional callback for progress updates
            copy_to_monsters: Copy to web/static/media/monsters for immediate use
            copy_to_npcs: Copy to web/static/media/npcs for immediate use
            
        Returns:
            Dictionary with batch results
        """
        results = {
            "pack_name": pack_name,
            "total": len(video_files),
            "successful": [],
            "failed": [],
            "start_time": datetime.now().isoformat()
        }
        
        for i, (input_path, monster_id) in enumerate(video_files):
            # Progress callback
            if progress_callback:
                progress_callback({
                    "current": i + 1,
                    "total": len(video_files),
                    "monster": monster_id,
                    "percent": ((i + 1) / len(video_files)) * 100
                })
            
            # Process video
            result = self.process_monster_video(
                input_path=input_path,
                monster_id=monster_id,
                pack_name=pack_name,
                copy_to_monsters=copy_to_monsters,
                copy_to_npcs=copy_to_npcs
            )
            
            if result["success"]:
                results["successful"].append({
                    "monster": monster_id,
                    "compression_ratio": result.get("compression_ratio", 0)
                })
            else:
                results["failed"].append({
                    "monster": monster_id,
                    "error": result.get("error", "Unknown error")
                })
        
        results["end_time"] = datetime.now().isoformat()
        results["success_rate"] = len(results["successful"]) / results["total"] * 100 if results["total"] > 0 else 0
        
        return results
    
    def import_video_from_url(
        self,
        url: str,
        monster_id: str,
        pack_name: str
    ) -> Dict:
        """
        Download and process video from URL
        
        Args:
            url: URL of the video
            monster_id: ID of the monster
            pack_name: Name of the graphic pack
            
        Returns:
            Processing results
        """
        import requests
        import tempfile
        
        try:
            # Download video to temp file
            print(f"Downloading video from {url}...")
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tmp:
                for chunk in response.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                temp_path = tmp.name
            
            # Process the downloaded video
            result = self.process_monster_video(
                input_path=temp_path,
                monster_id=monster_id,
                pack_name=pack_name
            )
            
            # Clean up temp file
            os.unlink(temp_path)
            
            return result
            
        except Exception as e:
            return {
                "success": False,
                "monster_id": monster_id,
                "error": f"Download failed: {str(e)}"
            }
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calculate SHA256 hash of file for deduplication"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()[:16]  # Use first 16 chars
    
    def _update_pack_manifest(
        self,
        pack_name: str,
        monster_id: str,
        media_type: str
    ):
        """Update pack manifest with processed media"""
        manifest_path = Path(f"graphic_packs/{pack_name}/manifest.json")
        
        if manifest_path.exists():
            with open(manifest_path, 'r') as f:
                manifest = json.load(f)
        else:
            manifest = {
                "name": pack_name,
                "version": "1.0.0",
                "created_date": datetime.now().strftime("%Y-%m-%d"),
                "monsters_included": [],
                "media_stats": {}
            }
        
        # Update monsters list
        if monster_id not in manifest.get("monsters_included", []):
            manifest.setdefault("monsters_included", []).append(monster_id)
            manifest["monsters_included"] = sorted(manifest["monsters_included"])
        
        # Update media stats
        stats = manifest.setdefault("media_stats", {})
        stats.setdefault(media_type + "s", [])
        if monster_id not in stats[media_type + "s"]:
            stats[media_type + "s"].append(monster_id)
        
        manifest["total_monsters"] = len(manifest["monsters_included"])
        manifest["last_modified"] = datetime.now().strftime("%Y-%m-%d")
        
        # Save updated manifest
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
    
    def get_pack_video_stats(self, pack_name: str) -> Dict:
        """Get statistics about videos in a pack"""
        pack_dir = Path(f"graphic_packs/{pack_name}/monsters")
        
        if not pack_dir.exists():
            return {
                "total_videos": 0,
                "total_size_mb": 0,
                "videos": []
            }
        
        videos = []
        total_size = 0
        
        for video_file in pack_dir.glob("*_video.mp4"):
            size_mb = video_file.stat().st_size / (1024 * 1024)
            total_size += size_mb
            
            # Extract monster_id (already lowercase from filename)
            monster_id = video_file.stem.replace("_video", "")
            videos.append({
                "monster_id": monster_id,
                "file": video_file.name,
                "size_mb": round(size_mb, 2)
            })
        
        return {
            "total_videos": len(videos),
            "total_size_mb": round(total_size, 2),
            "average_size_mb": round(total_size / len(videos), 2) if videos else 0,
            "videos": sorted(videos, key=lambda x: x["monster_id"])
        }


# CLI interface for testing
def main():
    """Command-line interface for video processing"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Process monster videos")
    parser.add_argument("input", help="Input video file")
    parser.add_argument("monster", help="Monster ID")
    parser.add_argument("--pack", default="default_photorealistic", help="Pack name")
    parser.add_argument("--bitrate", help="Custom bitrate (e.g., 1500k)")
    parser.add_argument("--copy-to-monsters", action="store_true", 
                        help="Copy to web/static/media/monsters for immediate use")
    parser.add_argument("--copy-to-npcs", action="store_true", 
                        help="Copy to web/static/media/npcs for immediate use")
    
    args = parser.parse_args()
    
    processor = VideoProcessor()
    
    # Custom settings if provided
    custom_settings = None
    if args.bitrate:
        custom_settings = VideoProcessor.COMPRESSION_SETTINGS.copy()
        custom_settings["bitrate"] = args.bitrate
    
    result = processor.process_monster_video(
        input_path=args.input,
        monster_id=args.monster,
        pack_name=args.pack,
        custom_settings=custom_settings,
        copy_to_monsters=args.copy_to_monsters,
        copy_to_npcs=args.copy_to_npcs
    )
    
    if result["success"]:
        print(f"\nSuccess!")
        print(f"Video: {result['video_path']}")
        print(f"Thumbnail: {result['thumbnail_path']}")
        print(f"Compression: {result['compression_ratio']}% reduction")
    else:
        print(f"\nFailed: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    main()