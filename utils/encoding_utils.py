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
from typing import Any, Dict, Optional


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
    '\u00e2\u20ac\u2122': "'",      # Corrupted apostrophe
    '\u00e2\u20ac\u0153': '"',      # Corrupted left quote
    '\u00e2\u20ac': '"',       # Corrupted right quote
    '\u00e2\u20ac\u201d': '--',     # Corrupted em dash
    '\u00e2\u20ac\u201c': '-',      # Corrupted en dash
    '\u00e2\u20ac\u00a6': '...',    # Corrupted ellipsis
    
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


def safe_json_dump(data: Any, filepath: str, **kwargs) -> bool:
    """
    Save JSON file with proper encoding and sanitization.

    Uses the atomic file operation layer so JSON writes share the same
    cross-platform locking and Windows-safe replace semantics.
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

    from utils.file_operations import safe_write_json
    return safe_write_json(filepath, clean_data, json_kwargs=default_kwargs)


def fix_corrupted_location_name(name: str) -> str:
    """
    Specifically fix corrupted location names that have accumulated encoding errors.
    """
    # Common corruption patterns in location names
    corruption_fixes = {
        "Harrow\u00c3\u00a2\u00e2\u201a\u00ac\u00e2\u201e\u00a2s Hollow": "Harrow's Hollow",
        "Harrow\u00e2\u20ac\u2122s Hollow": "Harrow's Hollow",
        "Grimm\u00c3\u00a2\u00e2\u201a\u00ac\u00e2\u201e\u00a2s": "Grimm's",
        "Grimm\u00e2\u20ac\u2122s": "Grimm's",
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
