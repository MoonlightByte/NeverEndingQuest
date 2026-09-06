#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Chunked Conversation Compression

Compresses conversation history in manageable 8-transition chunks:
1. Trigger at 15 transitions (location summaries)
2. Compress oldest 8 transitions
3. Preserve location transition messages
4. When hitting 15 again, compress next 8 after last chronicle
5. Build up multiple chronicle "chapters" over time
"""

import json
import shutil
from core.combat.invocation import InvocationSupersededError
from utils.capture.live_provider_call import LiveProviderSuperseded
from ..generators.location_summarizer import LocationSummarizer
from datetime import datetime
from .chunked_compression_config import COMPRESSION_TRIGGER, CHUNK_SIZE
from utils.enhanced_logger import debug, info, warning, error, set_script_name

# Set script name for logging
set_script_name("chunked_compression")

def find_all_summaries(conversation_data):
    """Find all location summaries and AI chronicles separately"""
    location_summaries = []
    ai_chronicles = []
    
    for i, message in enumerate(conversation_data):
        content = message.get('content', '')
        if '=== LOCATION SUMMARY ===' in content:
            # Check if it's an AI chronicle
            if '[AI-Generated Chronicle Summary]' in content:
                ai_chronicles.append({
                    'index': i,
                    'type': 'chronicle',
                    'preview': content[:100] + "..." if len(content) > 100 else content
                })
            else:
                # Regular location summary
                lines = content.split('\n')
                location_name = "Unknown"
                for line in lines:
                    if line.strip() and not line.startswith('===') and ':' in line:
                        location_name = line.split(':')[0].strip()
                        break
                
                location_summaries.append({
                    'index': i,
                    'location': location_name,
                    'type': 'location',
                    'preview': content[:100] + "..." if len(content) > 100 else content
                })
    
    return location_summaries, ai_chronicles

def count_summaries_after_last_chronicle(conversation_data):
    """Count location summaries that appear after the last AI chronicle"""
    location_summaries, ai_chronicles = find_all_summaries(conversation_data)
    
    if not ai_chronicles:
        # No chronicles yet, count all location summaries
        return len(location_summaries), location_summaries, None
    
    # Find the last chronicle
    last_chronicle_idx = ai_chronicles[-1]['index']
    
    # Count location summaries after last chronicle
    summaries_after_chronicle = [s for s in location_summaries if s['index'] > last_chronicle_idx]
    
    return len(summaries_after_chronicle), summaries_after_chronicle, last_chronicle_idx

def find_compression_range(conversation_data, summaries_after_chronicle, last_chronicle_idx):
    """Find the range of messages to compress"""
    if not summaries_after_chronicle or len(summaries_after_chronicle) < CHUNK_SIZE:
        warning(f"COMPRESSION: Not enough summaries to compress (need {CHUNK_SIZE})", category="compression")
        return None, None, []
    
    # Take the first CHUNK_SIZE location summaries
    summaries_to_compress = summaries_after_chronicle[:CHUNK_SIZE]
    
    # Find the message range
    first_summary_idx = summaries_to_compress[0]['index']
    last_summary_idx = summaries_to_compress[-1]['index']
    
    # If there's a previous chronicle, we need to preserve the location transition after it
    if last_chronicle_idx is not None:
        # Find the location transition message after the last chronicle
        for i in range(last_chronicle_idx + 1, first_summary_idx):
            msg = conversation_data[i]
            if msg.get('role') == 'user' and 'Location transition:' in msg.get('content', ''):
                # Start compression after this transition
                first_summary_idx = i + 1
                break
    
    return first_summary_idx, last_summary_idx, summaries_to_compress

def chunked_compression(conversation_file="modules/conversation_history/conversation_history.json"):
    """Perform chunked compression - 8 transitions at a time
    
    Args:
        conversation_file: Path to the conversation history file to compress
    """
    
    info("STATE_CHANGE: Starting Chunked Conversation Compression", category="compression")
    info("=" * 40, category="compression")
    
    # Load original conversation
    with open(conversation_file, 'r', encoding='utf-8') as f:
        conversation_data = json.load(f)
    
    info(f"Total messages: {len(conversation_data)}", category="compression")
    
    # Count summaries after last chronicle
    count, summaries_after_chronicle, last_chronicle_idx = count_summaries_after_last_chronicle(conversation_data)
    
    info("COMPRESSION_STATUS: Current state:", category="compression")
    debug(f"  AI Chronicles found: {len([m for m in conversation_data if '[AI-Generated Chronicle Summary]' in m.get('content', '')])}", category="compression")
    debug(f"  Location summaries after last chronicle: {count}", category="compression")
    debug(f"  Compression trigger: {COMPRESSION_TRIGGER} summaries", category="compression")
    debug(f"  Compression size: {CHUNK_SIZE} transitions per chunk", category="compression")
    
    if count < COMPRESSION_TRIGGER:
        info(f"COMPRESSION: No compression needed ({count} < {COMPRESSION_TRIGGER})", category="compression")
        return False
    
    info(f"COMPRESSION_TRIGGER: Compression triggered! Will compress oldest {CHUNK_SIZE} transitions.", category="compression")
    
    # Find compression range
    first_msg_idx, last_msg_idx, summaries_to_compress = find_compression_range(
        conversation_data, summaries_after_chronicle, last_chronicle_idx
    )
    
    if first_msg_idx is None:
        error("FAILURE: Failed to determine compression range", category="compression")
        return False
    
    info("COMPRESSION_DETAILS: Compression range:", category="compression")
    debug(f"  Messages to compress: {first_msg_idx} to {last_msg_idx}", category="compression")
    debug(f"  First location: {summaries_to_compress[0]['location']}", category="compression")
    debug(f"  Last location: {summaries_to_compress[-1]['location']}", category="compression")
    debug(f"  Transitions included: {len(summaries_to_compress)}", category="compression")
    
    # Extract messages to compress
    messages_to_compress = conversation_data[first_msg_idx:last_msg_idx + 1]
    debug(f"  Total messages in range: {len(messages_to_compress)}", category="compression")
    
    # Initialize AI summarizer
    summarizer = LocationSummarizer()
    
    try:
        # Generate AI chronicle for the 8 transitions
        result = summarizer.summarize_transition_group(
            start_location=summaries_to_compress[0]['location'],
            end_location=summaries_to_compress[-1]['location'],
            messages=messages_to_compress,
            intermediate_locations=[s['location'] for s in summaries_to_compress[1:-1]]
        )
        
        info("SUCCESS: AI Chronicle Generated!", category="compression")
        debug(f"COMPRESSION_STATS: Original tokens: {result['original_tokens']:,}", category="compression")
        debug(f"COMPRESSION_STATS: Summary tokens: {result['summary_tokens']:,}", category="compression")
        debug(f"COMPRESSION_STATS: Compression ratio: {result['compression_ratio']:.1%}", category="compression")
        debug(f"COMPRESSION_STATS: Events preserved: {result['events_preserved']}", category="compression")
        
        # Create the compressed conversation
        compressed_conversation = conversation_data.copy()
        
        # Create AI chronicle message
        ai_chronicle_message = {
            "role": "assistant",
            "content": f"=== LOCATION SUMMARY ===\n\n{result['summary']}"
        }
        
        # Find where to insert the chronicle
        # We want to preserve the location transition before our compression range
        insert_position = first_msg_idx
        
        # Look backwards for a location transition message
        for i in range(first_msg_idx - 1, max(0, first_msg_idx - 5), -1):
            if compressed_conversation[i].get('role') == 'user' and 'Location transition:' in compressed_conversation[i].get('content', ''):
                # Insert after this transition
                insert_position = i + 1
                break
        
        # Replace the range with the chronicle
        # But preserve any location transition at the end
        end_transition_idx = None
        for i in range(last_msg_idx + 1, min(len(compressed_conversation), last_msg_idx + 3)):
            if compressed_conversation[i].get('role') == 'user' and 'Location transition:' in compressed_conversation[i].get('content', ''):
                end_transition_idx = i
                break
        
        # Perform the replacement
        if end_transition_idx:
            # Keep the transition after our range
            compressed_conversation[insert_position:last_msg_idx + 1] = [ai_chronicle_message]
        else:
            # No transition to preserve
            compressed_conversation[insert_position:last_msg_idx + 1] = [ai_chronicle_message]
        
        # Save files
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        compressed_file = f"conversation_history_chunked_{timestamp}.json"
        summary_file = f"chunked_compression_summary_{timestamp}.md"
        
        # Save compressed conversation
        with open(compressed_file, 'w', encoding='utf-8') as f:
            json.dump(compressed_conversation, f, indent=2, ensure_ascii=False)
        
        # Create summary document
        summary_content = f"""# Chunked Compression Results
*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*

## Compression Strategy
- **Trigger**: {COMPRESSION_TRIGGER}+ location summaries after last chronicle
- **Action**: Compress oldest {CHUNK_SIZE} transitions
- **Result**: New AI chronicle chapter added

## This Compression
- **Original messages**: {len(conversation_data)}
- **Compressed messages**: {len(compressed_conversation)}
- **Messages removed**: {len(messages_to_compress) - 1}
- **Compression range**: Messages {first_msg_idx}-{last_msg_idx}

## Journey Compressed
- **From**: {summaries_to_compress[0]['location']}
- **To**: {summaries_to_compress[-1]['location']}
- **Transitions compressed**: {len(summaries_to_compress)}

## Compression Stats
- **Original tokens**: {result['original_tokens']:,}
- **Summary tokens**: {result['summary_tokens']:,}
- **Compression ratio**: {result['compression_ratio']:.1%}
- **Events preserved**: {result['events_preserved']}

## Chronicle Status
- **Total AI chronicles**: {len([m for m in compressed_conversation if '[AI-Generated Chronicle Summary]' in m.get('content', '')])}
- **Remaining location summaries**: {count - len(summaries_to_compress)}

## AI-Generated Chronicle

{result['summary']}

---

## Files Generated
- `{compressed_file}` - Complete conversation with compression applied
- `{summary_file}` - This summary document

The compression created a new chronicle chapter covering {CHUNK_SIZE} transitions while preserving location transition messages for continuity.
"""
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(summary_content)
        
        info("FILES_CREATED: Files created:", category="compression")
        info(f"  - {compressed_file}", category="compression")
        info(f"  - {summary_file}", category="compression")
        
        # Show chronicle count
        chronicles_after = len([m for m in compressed_conversation if '[AI-Generated Chronicle Summary]' in m.get('content', '')])
        info(f"CHRONICLE_STATUS: Chronicle chapters: {chronicles_after}", category="compression")
        
        return True
        
    except (LiveProviderSuperseded, InvocationSupersededError):
        raise
    except Exception as e:
        error(f"COMPRESSION_ERROR: Error during compression: {e}", category="compression")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = chunked_compression()
    if success:
        info("SUCCESS: Chunked compression completed successfully!", category="compression")
    else:
        error("FAILURE: Chunked compression failed!", category="compression")