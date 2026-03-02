# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Homebrew Media Extract - Warn-only media extraction for Homebrew markdown ingest.

Parses markdown for image directives and direct URLs, downloads/copies to module
media folders with best-effort classification. Never blocks ingest; all media
failures are warnings with degraded status.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

# Retryable HTTP status codes
RETRYABLE_STATUS_CODES = {408, 425, 429, 500, 502, 503, 504}
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_BASE = 1.0  # seconds


def _sanitize_filename(name: str) -> str:
    """Create a filesystem-safe filename from a basename."""
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name).strip("._")


def _extract_image_urls(source_text: str) -> List[Dict[str, str]]:
    """
    Extract image URLs from markdown and raw URLs.
    Returns list of dicts with url, alt_text, source_line_num, context_window.
    """
    urls: List[Dict[str, str]] = []
    lines = source_text.splitlines()

    # Markdown image directives: ![alt](url) or ![alt](url){...}
    md_pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

    # HTML img src: <img src="url" ...>
    html_pattern = re.compile(r'<img[^>]+src=[\'"]([^\'"]+)[\'"][^>]*>', re.IGNORECASE)

    # Background image in CSS: url('url')
    css_pattern = re.compile(r"url\(['\"]?([^\)'\"]+)['\"]?\)")

    # Raw image URLs (jpg/jpeg/png/webp)
    raw_url_pattern = re.compile(r"(https?://[^\s)\"'<>]+\.(jpg|jpeg|png|webp))", re.IGNORECASE)

    seen_urls: set = set()

    for line_num, line in enumerate(lines, start=1):
        line_lower = line.lower()

        # Skip lines that are likely CSS/JS code blocks
        if line.strip().startswith("{") and line_lower.count("{") > line_lower.count("{"):
            continue

        def add_url(url: str, alt_text: str = ""):
            url_clean = url.strip().strip("'\"").split("{")[0].split(" ")[0]
            if url_clean in seen_urls:
                return
            seen_urls.add(url_clean)

            # Get context window (3 lines before)
            start = max(0, line_num - 4)
            context = "\n".join(lines[start:line_num])

            urls.append({
                "url": url_clean,
                "alt_text": alt_text,
                "source_line_num": line_num,
                "context_window": context[-500:]  # last 500 chars of context
            })

        # Markdown images
        for match in md_pattern.finditer(line):
            alt_text = match.group(1)
            url = match.group(2)
            add_url(url, alt_text)

        # HTML img tags
        for match in html_pattern.finditer(line):
            url = match.group(1)
            add_url(url, "")

        # CSS url() values
        for match in css_pattern.finditer(line):
            url = match.group(1)
            add_url(url, "")

        # Raw URLs (only if they look like image URLs and weren't caught above)
        for match in raw_url_pattern.finditer(line):
            url = match.group(1)
            if url not in seen_urls:
                add_url(url, "")

    return urls


def _classify_media(url_info: Dict[str, str], is_first_image: bool, prev_headings: List[str]) -> str:
    """
    Classify media based on context clues.
    Returns: 'title_image', 'map_image', or 'handout'
    """
    url = url_info.get("url", "").lower()
    alt_text = url_info.get("alt_text", "").lower()
    context = url_info.get("context_window", "").lower()

    # First image in document is likely title/hero (check this first)
    if is_first_image:
        # Only override if there's explicit DM map context in headings
        for heading in prev_headings[-3:]:
            heading_lower = heading.lower()
            if "dm map" in heading_lower or "map" in heading_lower:
                return "map_image"
        return "title_image"

    # Map-related detection
    map_keywords = [
        "dm map", "battle map", "dungeon map", "world map",
    ]

    # Check for explicit DM map heading context (strong signal)
    for heading in prev_headings[-3:]:  # last 3 headings
        heading_lower = heading.lower()
        if "dm map" in heading_lower:
            return "map_image"
        if "map" in heading_lower and ("exterior" in heading_lower or "interior" in heading_lower or "dm" in heading_lower):
            return "map_image"

    # Check alt text for explicit map keywords
    if any(kw in alt_text for kw in map_keywords):
        return "map_image"

    # Check context window for DM map sections (strong signal)
    if "dm map" in context or "dm maps" in context:
        return "map_image"

    # Check URL and alt text for "map" with location context
    if "map" in alt_text or "map" in url:
        if any(loc in context for loc in ["exterior", "interior", "keep", "dungeon"]):
            return "map_image"

    # Default to handout
    return "handout"


def _download_image(
    url: str,
    dest_path: Path,
    timeout_seconds: int,
    max_retries: int = DEFAULT_MAX_RETRIES
) -> Tuple[bool, Optional[str], int, Optional[int], bool]:
    """
    Download image from URL to destination path with retry/backoff.
    
    TABLETOP MODE: Hardened downloader with browser headers and bounded retry
    for transient HTTP errors (429 rate limits, 503 outages, etc.).
    
    Returns: (success: bool, error_message: Optional[str], attempts: int,
              http_status: Optional[int], retriable: bool)
    """
    try:
        import requests
    except ImportError:
        return False, "requests module not available", 0, None, False
    
    # Browser-like headers to avoid bot detection
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
    }
    
    attempts = 0
    last_error: Optional[str] = None
    last_status: Optional[int] = None
    
    for attempt in range(max_retries):
        attempts = attempt + 1
        try:
            response = requests.get(url, timeout=timeout_seconds, stream=True, headers=headers)
            last_status = response.status_code
            
            # Check for transient failures
            if response.status_code in RETRYABLE_STATUS_CODES:
                # Check for Retry-After header
                retry_after = response.headers.get('Retry-After')
                if retry_after:
                    try:
                        sleep_seconds = int(retry_after)
                    except ValueError:
                        sleep_seconds = DEFAULT_BACKOFF_BASE * (2 ** attempt)
                else:
                    sleep_seconds = DEFAULT_BACKOFF_BASE * (2 ** attempt)
                
                last_error = f"HTTP {response.status_code}: {response.reason}"
                if attempt < max_retries - 1:
                    time.sleep(min(sleep_seconds, 30))  # Cap at 30s
                    continue
                else:
                    # Exhausted retries
                    return False, last_error, attempts, last_status, True
            
            # Check for other HTTP errors
            response.raise_for_status()
            
            # Verify it looks like an image
            content_type = response.headers.get('content-type', '').lower()
            if not any(ct in content_type for ct in ['image/', 'application/octet-stream']):
                return False, f"Unexpected content-type: {content_type}", attempts, last_status, False
            
            # Atomic write via temp file
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            temp_fd, temp_path = tempfile.mkstemp(suffix=dest_path.suffix, dir=dest_path.parent)
            try:
                with os.fdopen(temp_fd, 'wb') as f:
                    shutil.copyfileobj(response.raw, f)
                os.rename(temp_path, dest_path)
                return True, None, attempts, last_status, False
            except Exception:
                os.remove(temp_path) if os.path.exists(temp_path) else None
                raise
        
        except requests.exceptions.Timeout:
            last_error = f"Timeout after {timeout_seconds}s"
            if attempt < max_retries - 1:
                time.sleep(DEFAULT_BACKOFF_BASE * (2 ** attempt))
                continue
            return False, last_error, attempts, None, True
        
        except requests.exceptions.HTTPError as e:
            last_status = e.response.status_code if e.response else None
            last_error = f"HTTP {last_status}: {e.response.reason if e.response else str(e)}"
            if last_status in RETRYABLE_STATUS_CODES and attempt < max_retries - 1:
                time.sleep(DEFAULT_BACKOFF_BASE * (2 ** attempt))
                continue
            return False, last_error, attempts, last_status, last_status in RETRYABLE_STATUS_CODES
        
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            if attempt < max_retries - 1:
                time.sleep(DEFAULT_BACKOFF_BASE * (2 ** attempt))
                continue
            return False, last_error, attempts, None, False
        
        except Exception as e:
            return False, f"Unexpected error: {e}", attempts, None, False
    
    # Should not reach here, but safety return
    return False, last_error or "Unknown error", attempts, last_status, False


def _compute_sha256(filepath: Path) -> str:
    """Compute SHA256 checksum of file."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)
    return sha256_hash.hexdigest()


def extract_media(
    source_path: str,
    module_slug: str,
    timeout_seconds: int = 10,
) -> Dict[str, Any]:
    """
    Extract media from Homebrew source markdown.
    Warn-only: never raises; returns structured result with status and warnings.
    """
    result: Dict[str, Any] = {
        "status": "success",
        "detected_urls": [],
        "extracted_count": 0,
        "warning_count": 0,
        "warnings": [],  # type: ignore
        "module_slug": module_slug,
        "source": source_path,
    }

    source_file = Path(source_path)
    if not source_file.exists() or not source_file.is_file():
        result["status"] = "failed"
        result["warnings"].append({
            "type": "source_missing",
            "severity": "error",
            "message": f"Source file not found: {source_path}",
        })
        result["warning_count"] = 1
        return result

    # Read source
    try:
        source_text = source_file.read_text(encoding="utf-8")
    except Exception as exc:
        result["status"] = "degraded"
        result["warnings"].append({
            "type": "read_error",
            "severity": "warning",
            "message": f"Failed to read source: {exc}",
        })
        result["warning_count"] = 1
        return result

    # Extract URLs
    url_infos = _extract_image_urls(source_text)
    result["detected_urls"] = [info["url"] for info in url_infos]

    if not url_infos:
        return result

    # Build heading index for classification context (with line numbers)
    heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
    headings: List[Tuple[int, str, int]] = []  # (level, text, line_num)
    for match in heading_pattern.finditer(source_text):
        level = len(match.group(1))
        text = match.group(2)
        # Calculate line number by counting newlines before match
        line_num = source_text[:match.start()].count('\n') + 1
        headings.append((level, text, line_num))

    # Prepare module media directories
    module_base = Path("modules") / module_slug / "media"
    env_dir = module_base / "environment"
    maps_dir = module_base / "maps"

    # Track per-URL outcomes for accurate logging
    url_outcomes: List[Dict[str, Any]] = []

    # Process each URL
    prev_headings: List[str] = []
    for idx, url_info in enumerate(url_infos):
        # Update prev_headings based on line position
        line_num = url_info.get("source_line_num", 0)
        prev_headings = [
            text for level, text, h_line in headings
            if text and h_line < line_num
        ][-10:]  # last 10 headings before this image

        is_first = (idx == 0)
        media_kind = _classify_media(url_info, is_first, prev_headings)

        # Determine destination directory
        if media_kind == "map_image":
            dest_dir = maps_dir
        else:
            dest_dir = env_dir

        # Determine filename from URL
        url = url_info["url"]
        parsed = urlparse(url)
        basename = Path(parsed.path).name
        if not basename or "." not in basename:
            # Fallback: hash-based name
            ext = ".jpg" if ".jpg" in url.lower() else ".png" if ".png" in url.lower() else ".webp"
            basename = f"media_{hashlib.sha256(url.encode()).hexdigest()[:12]}{ext}"
        else:
            basename = _sanitize_filename(basename)

        dest_path = dest_dir / basename
        target_relpath = str(dest_path.relative_to(module_base))

        # Track outcome for this URL
        outcome: Dict[str, Any] = {
            "url": url,
            "kind": media_kind,
            "target_path": target_relpath,
            "status": "planned",
            "attempts": 0,
            "http_status": None,
            "error": None,
        }

        # Skip if already exists
        if dest_path.exists():
            result["extracted_count"] += 1
            outcome["status"] = "existing"
            url_outcomes.append(outcome)
            continue

        # Download/copy
        success, error, attempts, http_status, retriable = _download_image(
            url, dest_path, timeout_seconds
        )

        # Record outcome
        outcome["attempts"] = attempts
        outcome["http_status"] = http_status
        outcome["error"] = error

        if success:
            result["extracted_count"] += 1
            outcome["status"] = "downloaded"
        else:
            result["warning_count"] += 1
            outcome["status"] = "failed"
            warning: Dict[str, Any] = {
                "type": "download_failed",
                "severity": "warning",
                "url": url,
                "target_path": str(dest_path),
                "message": error or "Unknown error",
                "attempts": attempts,
                "retriable": retriable,
            }
            if http_status is not None:
                warning["http_status"] = http_status
            result["warnings"].append(warning)

        url_outcomes.append(outcome)

    # Determine final status
    if result["warning_count"] > 0 and result["extracted_count"] == 0:
        result["status"] = "degraded"
    elif result["warning_count"] > 0:
        result["status"] = "degraded"

    # Persist extraction audit log
    _write_extraction_log(module_slug, url_outcomes)

    return result


def _write_extraction_log(
    module_slug: str,
    url_outcomes: List[Dict[str, Any]]
) -> bool:
    """Persist extraction audit log for handle reconciliation.

    TABLETOP MODE: Added to support reconciliation of failed downloads
    against existing local files in media_handles.py.
    """
    try:
        module_base = Path("modules") / module_slug / "media"
        module_base.mkdir(parents=True, exist_ok=True)
        log_path = module_base / ".extraction_log.json"

        log_data = {
            "module_slug": module_slug,
            "extracted_at": _get_timestamp(),
            "urls": url_outcomes,
        }

        # Atomic write
        tmp_path = log_path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(log_data, f, indent=2)
        tmp_path.replace(log_path)
        return True
    except Exception:
        return False


def _get_timestamp() -> str:
    """Get ISO timestamp."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="homebrew_media_extract",
        description="Extract media from Homebrew markdown (warn-only, never blocks ingest)",
    )
    parser.add_argument("--source", type=str, required=True, help="Source markdown file path")
    parser.add_argument("--module-slug", type=str, required=True, help="Target module slug (determines output path)")
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=10,
        help="Download timeout per image (default: 10)",
    )
    parser.add_argument("--json", action="store_true", default=False, help="Output JSON")
    return parser


def main() -> None:
    parser = _create_parser()
    args = parser.parse_args()

    result = extract_media(
        source_path=args.source,
        module_slug=args.module_slug,
        timeout_seconds=args.timeout_seconds,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=" * 60)
        print("HOMEBREW MEDIA EXTRACT")
        print("=" * 60)
        print(f"Source: {result['source']}")
        print(f"Module: {result['module_slug']}")
        print(f"Status: {result['status']}")
        print(f"Detected URLs: {len(result['detected_urls'])}")
        print(f"Extracted: {result['extracted_count']}")
        print(f"Warnings: {result['warning_count']}")
        if result['warnings']:
            print("Warning details:")
            for w in result['warnings']:
                print(f"- [{w.get('type')}] {w.get('message', '')}")

    # Exit codes: 0 = success/degraded, 1 = failed
    if result['status'] == 'failed':
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
