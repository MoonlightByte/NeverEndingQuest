# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

# ============================================================================
# ENCODING_UTILS.PY - CROSS-PLATFORM ENCODING SAFETY
# ============================================================================
#
# ARCHITECTURE ROLE: Data Management Layer - Encoding Safety and Text Processing
#
# This module provides critical cross-platform text encoding safety for Windows
# console compatibility, preventing Unicode encoding crashes that would break
# the entire game system through comprehensive character sanitization.
#
# KEY RESPONSIBILITIES:
# - Unicode character sanitization for Windows console (cp1252) compatibility
# - Comprehensive character mapping and replacement for problematic Unicode
# - Text encoding and decoding utilities for cross-platform compatibility
# - JSON data sanitization to prevent encoding-related crashes
# - ASCII character enforcement for game output and logging
# - Integration with all output systems to ensure encoding safety
#

"""
Encoding utilities for handling character encoding issues throughout the system.
Provides consistent text sanitization and encoding/decoding functions.
"""

import unicodedata
import json
import codecs
import os
import threading
import time
from typing import Any, Dict, List, Optional
from uuid import uuid4


# Comprehensive character mapping for problematic Unicode characters
CHARACTER_REPLACEMENTS = {
    # Smart quotes
    '\u2018': "'",  # Left single quote
    '\u2019': "'",  # Right single quote (apostrophe)
    '\u201C': '"',  # Left double quote
    '\u201D': '"',  # Right double quote
    
    # Dashes and spaces
    '\u2013': '-',   # En dash
    '\u2014': '--',  # Em dash
    '\u2026': '...',  # Ellipsis
    '\u00A0': ' ',   # Non-breaking space
    
    # Other problematic characters
    '\u009D': "'",   # Another quote character
    '\u0092': "'",   # Windows-1252 apostrophe
    '\u0093': '"',   # Windows-1252 left quote
    '\u0094': '"',   # Windows-1252 right quote
    '\u0096': '-',   # Windows-1252 en dash
    '\u0097': '--',  # Windows-1252 em dash
    
    # Arrow characters
    '\u2192': '->',  # Right arrow
    '\u2190': '<-',  # Left arrow
    '\u2194': '<->',  # Left-right arrow
    '\u21D2': '=>',  # Right double arrow
    '\u21D0': '<=',  # Left double arrow
    
    # Common corrupted sequences (these appear when UTF-8 is misinterpreted)
    'â€™': "'",      # Corrupted apostrophe
    'â€œ': '"',      # Corrupted left quote
    'â€': '"',       # Corrupted right quote
    'â€"': '--',     # Corrupted em dash
    'â€"': '-',      # Corrupted en dash
    'â€¦': '...',    # Corrupted ellipsis
    
    # Additional Windows-1252 characters
    '\u0080': '',    # Euro symbol (remove)
    '\u0081': '',    # Undefined (remove)
    '\u008D': '',    # Reverse line feed (remove)
    '\u008F': '',    # Single shift three (remove)
    '\u0090': '',    # Device control string (remove)
    '\u009C': '',    # String terminator (remove)
}


def sanitize_text(text: str) -> str:
    """
    Sanitize text by replacing problematic Unicode characters with ASCII equivalents.
    Also normalizes Unicode and removes control characters.
    """
    if not isinstance(text, str):
        return text
    
    # First, normalize Unicode to decomposed form
    text = unicodedata.normalize('NFKD', text)
    
    # Replace known problematic characters
    for old_char, new_char in CHARACTER_REPLACEMENTS.items():
        text = text.replace(old_char, new_char)
    
    # Remove any remaining control characters except newlines and tabs
    cleaned = []
    for char in text:
        if ord(char) < 32 and char not in '\n\r\t':
            continue  # Skip control characters
        elif ord(char) > 126 and ord(char) < 160:
            continue  # Skip more control characters
        else:
            cleaned.append(char)
    
    text = ''.join(cleaned)
    
    # Final normalization to composed form
    text = unicodedata.normalize('NFC', text)
    
    return text


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively sanitize all string values in a dictionary.
    """
    if isinstance(data, dict):
        return {k: sanitize_dict(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_dict(item) for item in data]
    elif isinstance(data, str):
        return sanitize_text(data)
    else:
        return data


def normalize_typography_deep(value: Any):
    """Deep-walk a JSON value, replacing ONLY known-lossless typography.

    The canonical ASCII-typography normalizer for model-generated content at a
    generation response boundary. Applies CHARACTER_REPLACEMENTS (curly quotes ->
    straight, en/em dash -> -/--, ellipsis -> ..., non-breaking space, arrows,
    Windows-1252 and corrupted-UTF8 sequences) to every string.

    Unlike sanitize_text, it does NOT run NFKD or drop code points, so it never
    mangles a proper noun. Unlike compilers.normalize_ascii_typography, it uses
    the fuller map (including the ellipsis it omits). Returns
    ``(normalized_value, replacement_count, residual_paths)`` where
    ``residual_paths`` are dotted paths of strings that STILL contain a non-ASCII
    code point (> 126) after replacement -- the caller decides whether to warn or
    fail/retry rather than silently deleting a character.
    """
    count = 0
    residual: List[str] = []

    def visit(item: Any, path: str) -> Any:
        nonlocal count
        if isinstance(item, dict):
            return {
                key: visit(child, f"{path}.{key}" if path else str(key))
                for key, child in item.items()
            }
        if isinstance(item, list):
            return [visit(child, f"{path}[{index}]") for index, child in enumerate(item)]
        if not isinstance(item, str):
            return item
        text = item
        for old_char, new_char in CHARACTER_REPLACEMENTS.items():
            if old_char in text:
                text = text.replace(old_char, new_char)
                count += 1
        if any(ord(char) > 126 for char in text):
            residual.append(path or "<root>")
        return text

    normalized = visit(value, "")
    return normalized, count, residual


def safe_json_load(filepath: str) -> Any:
    """
    Load JSON file with proper encoding and error handling.
    Returns None if file doesn't exist.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Sanitize the loaded data
            return sanitize_dict(data)
    except FileNotFoundError:
        return None
    except UnicodeDecodeError:
        # Try with different encoding if UTF-8 fails
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            data = json.load(f)
            return sanitize_dict(data)
    except Exception as e:
        print(f"Error loading JSON from {filepath}: {e}")
        raise


def safe_json_dump(data: Any, filepath: str, **kwargs) -> None:
    """
    Save JSON with sanitization and an atomic same-directory replacement.

    A unique temporary file keeps concurrent writers from sharing scratch
    state.  Flushing the file before ``os.replace`` means readers observe the
    complete old document or the complete new one, never a partially-written
    JSON document.
    """
    # Sanitize data before saving
    clean_data = sanitize_dict(data) if isinstance(data, (dict, list)) else data
    
    # Default kwargs for consistent JSON formatting
    default_kwargs = {
        'ensure_ascii': False,
        'indent': 2,
        'separators': (',', ': ')
    }
    default_kwargs.update(kwargs)
    
    filepath = os.fspath(filepath)
    absolute_path = os.path.abspath(filepath)
    parent = os.path.dirname(absolute_path)
    os.makedirs(parent, exist_ok=True)
    temporary_path = os.path.join(
        parent,
        (
            f".{os.path.basename(absolute_path)}.{os.getpid()}."
            f"{threading.get_ident()}.{uuid4().hex}.tmp"
        ),
    )

    try:
        with open(temporary_path, 'w', encoding='utf-8') as f:
            json.dump(clean_data, f, **default_kwargs)
            f.flush()
            os.fsync(f.fileno())
        # Windows can transiently refuse the rename (WinError 5/32)
        # while an antivirus scan, indexer, or reader briefly holds
        # the destination. One blip must not fail the write (a live
        # acceptance run lost a combat to this class in the sibling
        # writer). Retry patiently; persistent locks still raise.
        _replace_attempt = 0
        while True:
            try:
                os.replace(temporary_path, filepath)
                break
            except (PermissionError, OSError) as replace_error:
                winerror = getattr(replace_error, 'winerror', None)
                if winerror not in (5, 32) or _replace_attempt >= 100:
                    raise
                _replace_attempt += 1
                time.sleep(0.1)

        # Persist the directory entry where the platform supports fsync on a
        # directory. Windows does not expose an equivalent through os.open.
        if os.name != 'nt':
            directory_fd = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        if os.path.exists(temporary_path):
            os.remove(temporary_path)


def fix_corrupted_location_name(name: str) -> str:
    """
    Specifically fix corrupted location names that have accumulated encoding errors.
    """
    # Common corruption patterns in location names
    corruption_fixes = {
        "Harrow\u00c3\u00a2\u00e2\u201a\u00ac\u00e2\u201e\u00a2s Hollow": "Harrow's Hollow",
        "Harrowâ€™s Hollow": "Harrow's Hollow",
        "Grimm\u00c3\u00a2\u00e2\u201a\u00ac\u00e2\u201e\u00a2s": "Grimm's",
        "Grimmâ€™s": "Grimm's",
    }
    
    # Check for known corruptions first
    for corrupted, fixed in corruption_fixes.items():
        if corrupted in name:
            name = name.replace(corrupted, fixed)
    
    # Then apply general sanitization
    return sanitize_text(name)


def setup_utf8_console():
    """
    Set UTF-8 encoding for stdout to handle special characters on Windows.
    This should only be called from main.py when running directly.
    """
    import sys
    if sys.platform == 'win32':
        try:
            if hasattr(sys.stdout, 'buffer'):
                sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
                sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')
        except AttributeError:
            # Already wrapped or in a different environment
            pass