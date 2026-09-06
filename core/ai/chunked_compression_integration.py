#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Integration module for chunked compression with the main game system.
This module adds chunked compression checks after location transitions.
"""

import json
import os
from core.combat.invocation import InvocationSupersededError
from utils.capture.live_provider_call import LiveProviderSuperseded
from .chunked_compression import chunked_compression
from utils.encoding_utils import safe_json_load, safe_json_dump
from .chunked_compression_config import (
    COMPRESSION_TRIGGER, 
    ENABLE_AUTO_COMPRESSION,
    CREATE_BACKUPS
)
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set script name for logging
set_script_name("chunked_compression_integration")

def check_and_perform_chunked_compression(conversation_file="modules/conversation_history/conversation_history.json"):
    """
    Check if chunked compression is needed and perform it if necessary.
    This is called after location transitions when new location summaries are added.
    
    Args:
        conversation_file: Path to the conversation history file (default: modules/conversation_history/conversation_history.json)
    
    Returns:
        bool: True if compression was performed, False otherwise
    """
    debug("COMPRESSION_CHECK: Checking if chunked compression is needed", category="compression")
    
    # Check if auto compression is enabled
    if not ENABLE_AUTO_COMPRESSION:
        debug("CONFIG: Auto compression is disabled in configuration", category="compression")
        return False
    
    try:
        # Load conversation history
        conversation_history = safe_json_load(conversation_file)
        if not conversation_history:
            debug("FILE_CHECK: No conversation history found", category="compression")
            return False
        
        # Count location summaries
        location_summary_count = 0
        last_chronicle_idx = -1
        
        for i, msg in enumerate(conversation_history):
            content = msg.get('content', '')
            if '=== LOCATION SUMMARY ===' in content:
                if '[AI-Generated Chronicle Summary]' in content:
                    last_chronicle_idx = i
                else:
                    # Only count summaries after the last chronicle
                    if i > last_chronicle_idx:
                        location_summary_count += 1
        
        debug(f"SUMMARY_COUNT: Found {location_summary_count} location summaries after last chronicle", category="compression")
        
        # Check if we've hit the trigger threshold
        if location_summary_count >= COMPRESSION_TRIGGER:
            info(f"COMPRESSION_TRIGGER: Compression trigger reached ({location_summary_count} >= {COMPRESSION_TRIGGER})! Performing chunked compression", category="compression")
            
            # Create a backup before compression if enabled
            if CREATE_BACKUPS:
                backup_file = f"conversation_history_backup_{os.path.getmtime(conversation_file)}.json"
                safe_json_dump(conversation_history, backup_file)
                info(f"BACKUP_CREATED: Created backup: {backup_file}", category="compression")
            
            # Perform compression
            success = chunked_compression(conversation_file)
            
            if success:
                info("SUCCESS: Chunked compression completed successfully", category="compression")
                
                # Load the compressed file that was created
                import glob
                compressed_files = sorted(glob.glob("conversation_history_chunked_*.json"))
                if compressed_files:
                    latest_compressed = compressed_files[-1]
                    debug(f"COMPRESSED_FILE: Using compressed file: {latest_compressed}", category="compression")
                    
                    # Copy the compressed version back to the main file
                    compressed_data = safe_json_load(latest_compressed)
                    if compressed_data:
                        safe_json_dump(compressed_data, conversation_file)
                        info(f"SUCCESS: Updated {conversation_file} with compressed version", category="compression")
                        return True
                    else:
                        error("FAILURE: Failed to load compressed data", category="compression")
                        return False
                else:
                    warning("COMPRESSION: No compressed file found", category="compression")
                    return False
            else:
                error("FAILURE: Chunked compression failed", category="compression")
                return False
        else:
            debug(f"COMPRESSION_CHECK: No compression needed yet ({location_summary_count} < {COMPRESSION_TRIGGER})", category="compression")
            return False
            
    except (LiveProviderSuperseded, InvocationSupersededError):
        raise
    except Exception as e:
        error(f"FAILURE: Failed to check/perform chunked compression: {e}", exception=e, category="compression")
        return False

def integrate_with_cumulative_summary():
    """
    This function should be called at the end of compress_conversation_history_on_transition
    in cumulative_summary.py to check if chunked compression is needed.
    """
    return check_and_perform_chunked_compression()