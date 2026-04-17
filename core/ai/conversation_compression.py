# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""
Real-time conversation compression before API calls.
Compresses specific elements in the conversation history to reduce token usage.
"""

import json
import re
from typing import List, Dict, Any, Optional
from utils.enhanced_logger import debug, info, warning, error
from dynamic_compressor import DynamicCompressor
from compressor_spec_location import SPEC as LOCATION_SPEC

# Import compression settings from config
try:
    from model_config import (
        COMPRESSION_ENABLED,
        COMPRESS_LOCATION_ENCOUNTERS, 
        COMPRESS_LOCATION_SUMMARIES
    )
except ImportError:
    # Fallback if config not updated yet
    COMPRESSION_ENABLED = True
    COMPRESS_LOCATION_ENCOUNTERS = True
    COMPRESS_LOCATION_SUMMARIES = False

def extract_location_from_conversation(conversation_history: List[Dict]) -> Optional[Dict]:
    """
    Extract the current location JSON from the conversation history.
    Looks for the most recent "Current Location:" entry in system messages.
    """
    for message in reversed(conversation_history):
        if message.get("role") == "system":
            content = message.get("content", "")
            if "Current Location:" in content:
                # Try to extract JSON from the content
                try:
                    # Find the JSON part
                    start = content.find("{")
                    if start != -1:
                        json_str = content[start:]
                        # Handle escaped JSON if needed
                        if '\\"' in json_str:
                            json_str = json_str.replace('\\"', '"').replace('\\\\', '\\')
                        location_data = json.loads(json_str)
                        return location_data
                except (json.JSONDecodeError, ValueError) as e:
                    debug(f"Failed to extract location JSON: {e}")
    return None

def compress_location_encounters(location_data: Dict) -> str:
    """
    Compress location encounter data using the dynamic compressor.
    Returns compressed string representation.
    """
    try:
        compressor = DynamicCompressor(LOCATION_SPEC)
        compressed = compressor.compress(location_data)
        return compressed
    except Exception as e:
        warning(f"Failed to compress location data: {e}")
        # Return original JSON if compression fails
        return json.dumps(location_data, ensure_ascii=True)

def replace_location_in_conversation(conversation_history: List[Dict], compressed_location: str) -> List[Dict]:
    """
    Replace the location data in conversation history with compressed version.
    Returns a new conversation history list with the replacement.
    """
    new_history = []
    
    for message in conversation_history:
        if message.get("role") == "system":
            content = message.get("content", "")
            if "Current Location:" in content:
                # Find where the JSON starts
                json_start = content.find("{")
                if json_start != -1:
                    # Replace with compressed version
                    prefix = content[:json_start]
                    # Create new message with compressed location
                    new_content = f"{prefix.rstrip()}\n{compressed_location}"
                    new_history.append({
                        "role": "system",
                        "content": new_content
                    })
                else:
                    # No JSON found, keep original
                    new_history.append(message)
            else:
                # Not a location message, keep as-is
                new_history.append(message)
        else:
            # Not a system message, keep as-is
            new_history.append(message)
    
    return new_history

def compress_for_api_call(conversation_history: List[Dict]) -> List[Dict]:
    """
    Main compression function called before OpenAI API calls.
    Applies various compression techniques based on config flags.
    
    Args:
        conversation_history: The full conversation history
        
    Returns:
        Compressed conversation history ready for API call
    """
    # Check if compression is enabled at all
    if not COMPRESSION_ENABLED:
        return conversation_history
    
    # Start with original history
    compressed_history = conversation_history.copy()
    
    # Track compression stats
    original_length = sum(len(msg.get("content", "")) for msg in conversation_history)
    
    # Apply location encounter compression if enabled
    if COMPRESS_LOCATION_ENCOUNTERS:
        location_data = extract_location_from_conversation(compressed_history)
        if location_data:
            try:
                # Check if we have encounters to compress
                if "encounters" in location_data and location_data["encounters"]:
                    debug(f"Compressing location with {len(location_data.get('encounters', []))} encounters")
                    compressed_location = compress_location_encounters(location_data)
                    compressed_history = replace_location_in_conversation(compressed_history, compressed_location)
                    info("Location encounter compression applied")
            except Exception as e:
                warning(f"Location encounter compression failed: {e}")
    
    # Apply location summaries compression if enabled
    if COMPRESS_LOCATION_SUMMARIES:
        try:
            from block_location_compressor import (
                rewrite_conversation_with_compressed_blocks,
                get_compression_summary
            )
            
            # Get compression summary for logging
            summary = get_compression_summary(compressed_history)
            
            if summary['blocks_found'] > 0:
                debug(f"Compressing {summary['blocks_found']} location summary blocks")
                
                # Compress each block individually
                compressed_history = rewrite_conversation_with_compressed_blocks(
                    compressed_history,
                    include_stats=False,  # Don't include stats in production
                    keep_original=False,  # Replace blocks, don't keep originals
                    label_blocks=True     # Label blocks for clarity
                )
                
                info(f"Location summaries compression applied: {summary['blocks_found']} blocks compressed")
                debug(f"Summary reduction: {summary['overall_reduction']:.1f}% ({summary['total_original_size']} -> {summary['total_compressed_size']} chars)")
                
        except Exception as e:
            warning(f"Location summaries compression failed: {e}")
    
    # Calculate compression ratio
    compressed_length = sum(len(msg.get("content", "")) for msg in compressed_history)
    if original_length > 0:
        compression_ratio = (1 - compressed_length / original_length) * 100
        if compression_ratio > 0:
            info(f"Conversation compressed by {compression_ratio:.1f}% ({original_length} -> {compressed_length} chars)")
    
    return compressed_history

# Compression flags are now managed in model_config.py
# To change settings, edit COMPRESS_LOCATION_ENCOUNTERS and COMPRESS_LOCATION_SUMMARIES there