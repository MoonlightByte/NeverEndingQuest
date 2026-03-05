#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest CLI - Homebrew Media Handle Manifest Generator
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Generates deterministic media handle manifests for homebrew modules.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Optional imports with fail-open behavior
try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False


def _deterministic_hash(data: str) -> str:
    """Generate deterministic hash for handle_id."""
    return hashlib.sha256(data.encode('utf-8')).hexdigest()[:16]


def _build_handle_id(kind: str, source_ref: str, storage_relpath: str) -> str:
    """Build deterministic handle_id from composite key."""
    composite = f"{kind}:{source_ref}:{storage_relpath}"
    return _deterministic_hash(composite)


def _infer_kind_from_path(storage_relpath: str) -> str:
    """Infer media kind from storage path.
    
    Supports image and video files. Videos are identified by _video.mp4 suffix.
    """
    path_lower = storage_relpath.lower()
    
    if '/npcs/' in path_lower or 'npc_portrait' in path_lower:
        return "npc_portrait"
    elif '/monsters/' in path_lower or 'monster_portrait' in path_lower:
        # Check for video variant
        if path_lower.endswith('_video.mp4'):
            return "monster_video"
        return "monster_portrait"
    elif '/maps/' in path_lower:
        return "map_image"
    elif '/environment/' in path_lower:
        # Try to detect if this looks like a title/cover image
        basename = os.path.basename(storage_relpath).lower()
        title_indicators = ['title', 'cover', 'hero', 'banner', 'splash']
        if any(ind in basename for ind in title_indicators):
            return "title_image"
        return "handout"
    else:
        return "handout"


def _compute_sha256(filepath: Path) -> str:
    """Compute SHA-256 hash of file contents."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def _get_image_dimensions(filepath: Path) -> Tuple[int, int]:
    """Get image dimensions, fail-open to 0,0 if unavailable."""
    if not HAS_PILLOW:
        return (0, 0)
    
    try:
        with Image.open(filepath) as img:
            return img.size
    except Exception:
        return (0, 0)


def _scan_media_files(module_slug: str) -> List[Dict[str, Any]]:
    """Scan module media directory for existing media files."""
    handles = []
    module_path = Path(f"modules/{module_slug}")
    media_path = module_path / "media"
    
    if not media_path.exists():
        return handles
    
    # Scan subdirectories
    media_dirs = {
        "environment": ["jpg", "jpeg", "png", "webp", "gif"],
        "maps": ["jpg", "jpeg", "png", "webp", "gif"],
        "npcs": ["jpg", "jpeg", "png", "webp"],
        "monsters": ["jpg", "jpeg", "png", "webp", "mp4"],
    }
    
    for subdir, extensions in media_dirs.items():
        subdir_path = media_path / subdir
        if not subdir_path.exists():
            continue
        
        for ext in extensions:
            for filepath in subdir_path.glob(f"*.{ext}"):
                storage_relpath = f"media/{subdir}/{filepath.name}"
                kind = _infer_kind_from_path(storage_relpath)
                
                # Compute checksum and dimensions
                try:
                    checksum = _compute_sha256(filepath)
                except Exception:
                    checksum = ""
                
                dimensions = _get_image_dimensions(filepath)
                
                # Determine source_ref (try to find from manifest or use filename)
                source_ref = _infer_source_ref(filepath.name, module_slug)
                
                handle = {
                    "handle_id": _build_handle_id(kind, source_ref, storage_relpath),
                    "kind": kind,
                    "source_ref": source_ref,
                    "storage_relpath": storage_relpath,
                    "download_status": "downloaded",
                    "checksum_sha256": checksum,
                    "dimensions": {"width": dimensions[0], "height": dimensions[1]},
                    "linked_area_ids": [],
                    "linked_location_ids": [],
                    "future_use": _build_future_use(kind),
                }
                handles.append(handle)
    
    return handles


def _infer_source_ref(filename: str, module_slug: str) -> str:
    """Infer source reference from filename and module context."""
    # Try to read from extraction log if available
    extraction_log_path = Path(f"modules/{module_slug}/media/.extraction_log.json")
    if extraction_log_path.exists():
        try:
            log_data = json.loads(extraction_log_path.read_text())
            for entry in log_data.get("urls", []):
                url_basename = os.path.basename(entry.get("url", ""))
                if url_basename == filename or url_basename.startswith(filename.split('.')[0]):
                    return entry.get("url", f"local:{filename}")
        except Exception:
            pass
    
    return f"local:{filename}"


def _build_future_use(kind: str) -> Dict[str, bool]:
    """Build future-use flags based on kind."""
    return {
        "chat_title_candidate": kind == "title_image",
        "map_tab_candidate": kind == "map_image",
    }


def _find_existing_file_by_stem(module_path: Path, target_path: str) -> Optional[Path]:
    """Find existing file by stem, checking extension variants.
    
    TABLETOP MODE: Added to reconcile failed download refs against
    existing local files with different extensions (.jpg vs .jpeg).
    """
    target = module_path / target_path
    if target.exists():
        return target
    
    # Check extension variants
    stem = target.stem
    parent = target.parent
    extensions = [".jpg", ".jpeg", ".png", ".webp"]
    
    for ext in extensions:
        variant = parent / f"{stem}{ext}"
        if variant.exists():
            return variant
    
    return None


def _load_unresolved_refs(module_slug: str) -> List[Dict[str, Any]]:
    """Load unresolved references from extraction stage with local file reconciliation."""
    unresolved = []
    module_path = Path(f"modules/{module_slug}")
    
    # Check for extraction log with failures
    extraction_log_path = module_path / "media" / ".extraction_log.json"
    if extraction_log_path.exists():
        try:
            log_data = json.loads(extraction_log_path.read_text())
            for entry in log_data.get("urls", []):
                url = entry.get("url", "")
                kind = entry.get("kind", "handout")
                storage_relpath = entry.get("target_path", f"media/environment/{os.path.basename(url)}")
                
                # Check if local file exists (with extension variants)
                existing_file = _find_existing_file_by_stem(module_path, storage_relpath)
                
                if existing_file:
                    # Local file exists - mark as downloaded
                    actual_relpath = str(existing_file.relative_to(module_path))
                    handle = {
                        "handle_id": _build_handle_id(kind, url, actual_relpath),
                        "kind": kind,
                        "source_ref": url,
                        "storage_relpath": actual_relpath,
                        "download_status": "downloaded",
                        "checksum_sha256": _compute_sha256(existing_file),
                        "dimensions": {"width": _get_image_dimensions(existing_file)[0], "height": _get_image_dimensions(existing_file)[1]},
                        "linked_area_ids": [],
                        "linked_location_ids": [],
                        "future_use": _build_future_use(kind),
                    }
                else:
                    # Truly failed
                    handle = {
                        "handle_id": _build_handle_id(kind, url, storage_relpath),
                        "kind": kind,
                        "source_ref": url,
                        "storage_relpath": storage_relpath,
                        "download_status": "failed",
                        "checksum_sha256": "",
                        "dimensions": {"width": 0, "height": 0},
                        "linked_area_ids": [],
                        "linked_location_ids": [],
                        "future_use": _build_future_use(kind),
                    }
                unresolved.append(handle)
        except Exception:
            pass
    
    # Also check for a failed_manifest.json that might have been created
    failed_manifest_path = module_path / "media" / ".failed_manifest.json"
    if failed_manifest_path.exists():
        try:
            failed_data = json.loads(failed_manifest_path.read_text())
            for entry in failed_data.get("failed_refs", []):
                url = entry.get("url", "")
                kind = entry.get("kind", "handout")
                storage_relpath = entry.get("storage_relpath", f"media/environment/{os.path.basename(url)}")
                
                # Check if local file exists
                existing_file = _find_existing_file_by_stem(module_path, storage_relpath)
                
                if existing_file:
                    actual_relpath = str(existing_file.relative_to(module_path))
                    handle = {
                        "handle_id": _build_handle_id(kind, url, actual_relpath),
                        "kind": kind,
                        "source_ref": url,
                        "storage_relpath": actual_relpath,
                        "download_status": "downloaded",
                        "checksum_sha256": _compute_sha256(existing_file),
                        "dimensions": {"width": _get_image_dimensions(existing_file)[0], "height": _get_image_dimensions(existing_file)[1]},
                        "linked_area_ids": [],
                        "linked_location_ids": [],
                        "future_use": _build_future_use(kind),
                    }
                else:
                    handle = {
                        "handle_id": _build_handle_id(kind, url, storage_relpath),
                        "kind": kind,
                        "source_ref": url,
                        "storage_relpath": storage_relpath,
                        "download_status": entry.get("status", "failed"),
                        "checksum_sha256": "",
                        "dimensions": {"width": 0, "height": 0},
                        "linked_area_ids": [],
                        "linked_location_ids": [],
                        "future_use": _build_future_use(kind),
                    }
                unresolved.append(handle)
        except Exception:
            pass
    
    return unresolved


def _dedupe_handles_by_source_ref(handles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate handles by source_ref with deterministic selection policy.
    
    TABLETOP MODE: Added to prevent duplicate entries for same source URL
    (e.g., .jpg and .jpeg variants, or different kind classifications).
    
    Selection priority:
    1) download_status: downloaded > failed/missing
    2) kind priority: title_image > map_image > handout > npc_portrait > monster_portrait > monster_video
    3) stable path tie-break (alphabetical by storage_relpath)
    """
    # Priority ordering for kinds (lower = better)
    kind_priority = {
        "title_image": 0,
        "map_image": 1,
        "handout": 2,
        "npc_portrait": 3,
        "monster_portrait": 4,
    }
    
    # Group by source_ref
    by_source: Dict[str, List[Dict[str, Any]]] = {}
    for handle in handles:
        source = handle.get("source_ref", "")
        if source not in by_source:
            by_source[source] = []
        by_source[source].append(handle)
    
    # Select best handle per source_ref
    deduped: List[Dict[str, Any]] = []
    for source, candidates in by_source.items():
        if len(candidates) == 1:
            deduped.append(candidates[0])
            continue
        
        # Sort by selection criteria
        def sort_key(h: Dict[str, Any]) -> Tuple[int, int, str]:
            # 1) downloaded first (1 for downloaded, 0 for others - we want downloaded first so reverse)
            is_downloaded = 0 if h.get("download_status") == "downloaded" else 1
            # 2) kind priority (lower is better)
            kind = h.get("kind", "handout")
            kind_order = kind_priority.get(kind, 99)
            # 3) stable tie-break
            path = h.get("storage_relpath", "")
            return (is_downloaded, kind_order, path)
        
        candidates_sorted = sorted(candidates, key=sort_key)
        best = candidates_sorted[0]
        deduped.append(best)
    
    return deduped


def _sort_handles(handles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort handles deterministically for stable output."""
    # Sort by kind, then source_ref, then storage_relpath
    kind_order = {"title_image": 0, "map_image": 1, "handout": 2, "npc_portrait": 3, "monster_portrait": 4, "monster_video": 5}
    
    def sort_key(handle: Dict[str, Any]) -> Tuple[int, str, str]:
        kind = handle.get("kind", "handout")
        order = kind_order.get(kind, 99)
        return (
            order,
            handle.get("source_ref", "").lower(),
            handle.get("storage_relpath", "").lower(),
        )
    
    return sorted(handles, key=sort_key)


def _atomic_write_json(filepath: Path, data: Dict[str, Any]) -> bool:
    """Atomically write JSON file."""
    tmp_path = filepath.with_suffix('.tmp')
    try:
        tmp_path.write_text(json.dumps(data, indent=2))
        tmp_path.replace(filepath)
        return True
    except Exception:
        # Cleanup tmp on failure
        if tmp_path.exists():
            tmp_path.unlink()
        return False


def generate_manifest(module_slug: str, include_generated_at: bool = False) -> Dict[str, Any]:
    """Generate media handle manifest for a module."""
    module_path = Path(f"modules/{module_slug}")
    media_path = module_path / "media"
    manifest_path = media_path / "media_handles.json"
    
    # Scan existing media files
    handles = _scan_media_files(module_slug)
    
    # Load unresolved references (preserved from failed downloads)
    unresolved = _load_unresolved_refs(module_slug)
    
    # Merge and deduplicate by source_ref, using deterministic selection policy
    # Selection priority:
    # 1) download_status: downloaded > failed/missing
    # 2) kind priority: title_image > map_image > handout > npc_portrait > monster_portrait
    # 3) stable path tie-break
    handles = _dedupe_handles_by_source_ref(handles + unresolved)
    
    # Sort deterministically
    handles = _sort_handles(handles)
    
    # Build manifest (omit generated_at by default for idempotency)
    manifest: Dict[str, Any] = {
        "module_slug": module_slug,
        "manifest_version": "1.0.0",
        "handle_count": len(handles),
        "handles": handles,
    }
    
    # Conditionally include timestamp only when requested
    if include_generated_at:
        manifest["generated_at"] = _get_timestamp()
    
    # Determine status
    has_downloaded = any(h["download_status"] == "downloaded" for h in handles)
    has_failed = any(h["download_status"] == "failed" for h in handles)
    has_missing = any(h["download_status"] == "missing" for h in handles)
    
    if has_failed or has_missing:
        status = "degraded"
    elif has_downloaded:
        status = "success"
    else:
        status = "degraded"  # No handles at all
    
    # Ensure media directory exists
    media_path.mkdir(parents=True, exist_ok=True)
    
    # Atomic write
    success = _atomic_write_json(manifest_path, manifest)
    
    return {
        "status": status,
        "manifest_path": str(manifest_path),
        "handle_count": len(handles),
        "downloaded_count": sum(1 for h in handles if h["download_status"] == "downloaded"),
        "failed_count": sum(1 for h in handles if h["download_status"] == "failed"),
        "missing_count": sum(1 for h in handles if h["download_status"] == "missing"),
        "write_success": success,
        "module_slug": module_slug,
    }


def _get_timestamp() -> str:
    """Get ISO timestamp for manifest generation."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="homebrew_media_handles",
        description="Generate deterministic media handle manifest for homebrew modules",
    )
    parser.add_argument("--slug", type=str, required=True, help="Module slug (e.g., The_Secrets_of_Mangrove_Keep)")
    parser.add_argument("--json", action="store_true", default=False, help="Output JSON")
    parser.add_argument("--include-generated-at", action="store_true", default=False,
                        help="Include generation timestamp in manifest (default: false for idempotency)")
    return parser


def main() -> None:
    parser = _create_parser()
    args = parser.parse_args()
    
    result = generate_manifest(args.slug, include_generated_at=args.include_generated_at)
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=" * 60)
        print("MEDIA HANDLE MANIFEST")
        print("=" * 60)
        print(f"Module: {result['module_slug']}")
        print(f"Status: {result['status']}")
        print(f"Path: {result['manifest_path']}")
        print(f"Handles: {result['handle_count']}")
        print(f"  Downloaded: {result['downloaded_count']}")
        print(f"  Failed: {result['failed_count']}")
        print(f"  Missing: {result['missing_count']}")
        print(f"Write success: {result['write_success']}")
    
    # Exit code: 0 for success or degraded, 1 only for write failure
    if not result["write_success"]:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
