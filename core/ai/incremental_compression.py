#!/usr/bin/env python3
"""
Apply incremental compression to actual conversation history.
Filters validation errors and preserves recent valid context.
"""

import json
import os
import sys
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from core.ai import api_client
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T020", "core/ai/incremental_compression.py", 198)
import shutil

# Add project root to path for standalone execution
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import config
from utils.encoding_utils import safe_json_load, safe_json_dump
from utils.enhanced_logger import info, debug, warning, error

class IncrementalLocationCompressor:
    """Handles incremental compression of messages at current location."""
    
    def __init__(self):
        # Model selection deferred to compress call; temperature stays at callsite
        self.COMPRESSION_TEMP = 0.3
        self.TRIGGER_THRESHOLD = 15  # Compress when reaching 15 pairs
        self.PRESERVE_RECENT = 5     # Always keep last 5 VALID pairs uncompressed
        
    def is_validation_error(self, msg: Dict) -> bool:
        """Check if a message is a validation error."""
        if msg.get("role") == "user":
            content = msg.get("content", "")
            return "Error Note: Your previous response failed validation" in content
        return False
    
    def filter_validation_errors(self, messages: List[Dict]) -> List[Dict]:
        """Remove validation error pairs from messages."""
        filtered = []
        i = 0
        while i < len(messages):
            # Check if this is a validation error message
            if self.is_validation_error(messages[i]):
                # Skip this message, but DON'T skip the previous assistant message
                # because we need to track what the assistant tried
                i += 1
                continue
            
            # Check if next message is a validation error
            if i + 1 < len(messages) and self.is_validation_error(messages[i + 1]):
                # Include this message but mark that next will be skipped
                filtered.append(messages[i])
                i += 1  # Move to the error message, which will be skipped in next iteration
            else:
                # Normal message, include it
                filtered.append(messages[i])
                i += 1
                
        return filtered
    
    def count_valid_conversation_pairs(self, messages: List[Dict]) -> int:
        """Count user-assistant pairs, excluding validation errors."""
        # First filter out validation errors
        valid_messages = self.filter_validation_errors(messages)
        
        pairs = 0
        i = 0
        while i < len(valid_messages) - 1:
            if valid_messages[i]["role"] == "user" and valid_messages[i + 1]["role"] == "assistant":
                pairs += 1
                i += 2
            else:
                i += 1
        return pairs
    
    def should_compress(self, messages: List[Dict]) -> bool:
        """Check if we should trigger compression based on VALID pairs."""
        valid_pairs = self.count_valid_conversation_pairs(messages)
        return valid_pairs >= self.TRIGGER_THRESHOLD
    
    def find_compression_range(self, messages: List[Dict]) -> Optional[Tuple[int, int, List[Dict]]]:
        """
        Find the range of messages to compress.
        Returns: (start_idx, end_idx, filtered_messages_to_compress)
        """
        # Filter validation errors for counting
        valid_messages = self.filter_validation_errors(messages)
        valid_pairs = self.count_valid_conversation_pairs(messages)
        
        if valid_pairs < self.TRIGGER_THRESHOLD:
            return None
        
        # Calculate how many pairs to compress
        pairs_to_compress = valid_pairs - self.PRESERVE_RECENT
        if pairs_to_compress <= 0:
            return None
        
        # Find the actual messages to compress (including any validation attempts)
        pairs_found = 0
        compress_until_idx = None
        
        # Walk through original messages to find compression boundary
        i = 0
        while i < len(messages) - 1 and pairs_found < pairs_to_compress:
            # Skip validation error messages for pair counting
            if self.is_validation_error(messages[i]):
                i += 1
                continue
                
            if messages[i]["role"] == "user" and i + 1 < len(messages) and messages[i + 1]["role"] == "assistant":
                pairs_found += 1
                if pairs_found == pairs_to_compress:
                    compress_until_idx = i + 2  # Include the assistant message
                    break
                i += 2
            else:
                i += 1
        
        if compress_until_idx is None:
            return None
            
        # Extract messages to compress and filter out validation errors
        messages_to_compress = messages[:compress_until_idx]
        filtered_to_compress = self.filter_validation_errors(messages_to_compress)
        
        return (0, compress_until_idx, filtered_to_compress)
    
    def compress_messages(self, messages: List[Dict], location_info: Dict) -> Optional[Dict]:
        """Compress a segment of messages into a summary."""
        
        # Build context for compression
        context_parts = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            if role == "user":
                # Skip location transition messages
                if "Location transition:" in content:
                    continue
                context_parts.append(f"Player: {content}")
            elif role == "assistant":
                # Extract narration from JSON responses if present
                if content.startswith("{") and "narration" in content:
                    try:
                        data = json.loads(content)
                        narration = data.get("narration", content)
                        context_parts.append(f"DM: {narration}")
                    except:
                        context_parts.append(f"DM: {content}")
                else:
                    context_parts.append(f"DM: {content}")
            elif role == "system":
                # Include important system messages
                if "arrived at" in content.lower() or "summary" in content.lower():
                    context_parts.append(f"System: {content}")
        
        if not context_parts:
            warning("No content to compress after filtering")
            return None
            
        full_context = "\n\n".join(context_parts)
        
        compression_prompt = f"""Compress this D&D 5e game segment into a narrative summary.

Location: {location_info.get('name', 'Unknown')} ({location_info.get('id', 'Unknown')})
Description: {location_info.get('description', 'No description')}

CONVERSATION TO COMPRESS:
{full_context}

Create a compressed narrative that:
1. Preserves all key events, decisions, and outcomes
2. Maintains story continuity and character development
3. Keeps track of items gained/lost and inventory changes
4. Notes all NPC interactions and important dialogue
5. Records combat results, damage taken, and resources used
6. Documents any plot revelations or quest progress
7. Maintains emotional beats and character relationships

Format as a flowing narrative in 2-3 paragraphs. Focus on what happened, not meta-game mechanics."""

        try:
            # Select model config per provider
            from model_config import MODEL_PROVIDER
            if MODEL_PROVIDER == "openai":
                compress_config = config.NARR_COMPRESS_GPT54MINI_NONE
            elif MODEL_PROVIDER == "gemini":
                compress_config = config.NARR_COMPRESS_GEMINI_FLASH_MINIMAL
            elif MODEL_PROVIDER == "lmstudio":
                compress_config = config.NARR_COMPRESS_LMSTUDIO
            else:  # legacy
                compress_config = config.NARR_COMPRESS_LEGACY

            api_response = capture_and_fanout("T020", api_client.create_completion,
                messages=[{"role": "user", "content": compression_prompt}],
                model=compress_config["model"],
                temperature=self.COMPRESSION_TEMP,
                **{k: v for k, v in compress_config.items() if k != "model"})
            response = api_response.choices[0].message.content
            
            if response and response.strip():
                location_id = location_info.get('id', 'Unknown')
                
                # Format as assistant message with clear context
                summary_content = (
                    f"[SUMMARY OF EVENTS AT THIS LOCATION]\n\n"
                    f"The following is a summary of your party's activities at the current location ({location_id}) "
                    f"up to this point:\n\n{response}"
                )
                
                return {
                    "role": "assistant",
                    "content": summary_content
                }
        except Exception as e:
            error(f"Compression failed: {e}")
        
        return None
    
    def apply_compression_to_list(self, messages: List[Dict]) -> Optional[List[Dict]]:
        """
        Apply compression to a list of messages and return compressed list.
        This version doesn't save to file, just returns the compressed messages.
        """
        if not messages:
            return None
            
        # Count valid pairs
        valid_pairs = self.count_valid_conversation_pairs(messages)
        debug(f"Valid conversation pairs (excluding errors): {valid_pairs}")
        
        if valid_pairs < self.TRIGGER_THRESHOLD:
            debug(f"Not enough valid pairs for compression (need {self.TRIGGER_THRESHOLD}, have {valid_pairs})")
            return None
        
        # Find last location transition
        last_transition_idx = 0
        for i, msg in enumerate(messages):
            if msg.get("role") == "system" and "arrived at" in msg.get("content", "").lower():
                last_transition_idx = i
            elif msg.get("role") == "user" and "Location transition:" in msg.get("content", ""):
                last_transition_idx = i
        
        # Get messages since last transition
        current_segment = messages[last_transition_idx:]
        debug(f"Messages at current location: {len(current_segment)}")
        
        # Get current location info
        party_data = safe_json_load("party_tracker.json")
        location_info = {
            "id": party_data.get("worldConditions", {}).get("currentLocationId", "Unknown"),
            "name": party_data.get("worldConditions", {}).get("currentLocationName", "Unknown Location"),
            "description": party_data.get("worldConditions", {}).get("currentDescription", "")
        }
        
        # Find compression range
        compress_result = self.find_compression_range(current_segment)
        if not compress_result:
            debug("Could not find enough valid pairs to compress")
            return None
        
        start, end, filtered_to_compress = compress_result
        debug(f"Compressing {len(filtered_to_compress)} messages")
        
        # Perform compression
        compressed = self.compress_messages(filtered_to_compress, location_info)
        if not compressed:
            return None
        
        # Build new message list
        new_messages = messages[:last_transition_idx]
        
        # Add location transition if exists
        if last_transition_idx > 0:
            new_messages.append(messages[last_transition_idx])
        
        # Add compressed summary
        new_messages.append(compressed)
        
        # Add remaining messages
        new_messages.extend(current_segment[end:])
        
        # Log compression stats
        original_length = sum(len(m.get("content", "")) for m in messages)
        new_length = sum(len(m.get("content", "")) for m in new_messages)
        compression_ratio = (1 - new_length / original_length) * 100
        
        info(f"Compressed {len(messages)} messages to {len(new_messages)} (ratio: {compression_ratio:.1f}%)")
        
        return new_messages
    
    def apply_compression(self, conversation_file: str = "modules/conversation_history/conversation_history.json"):
        """Apply incremental compression to actual conversation history."""
        
        # Create backup first
        backup_file = f"modules/conversation_history/conversation_history_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        info(f"Creating backup: {backup_file}")
        shutil.copy2(conversation_file, backup_file)
        
        # Load conversation
        messages = safe_json_load(conversation_file)
        if not messages:
            warning("No conversation history found")
            return False
        
        # Handle both list and dict formats
        if isinstance(messages, dict):
            messages = messages.get("messages", [])
        
        if not messages:
            warning("No messages in conversation history")
            return False
            
        info(f"Total messages: {len(messages)}")
        
        # Count valid pairs
        valid_pairs = self.count_valid_conversation_pairs(messages)
        info(f"Valid conversation pairs (excluding errors): {valid_pairs}")
        
        if not self.should_compress(messages):
            info(f"Not enough valid pairs for compression (need {self.TRIGGER_THRESHOLD}, have {valid_pairs})")
            return False
        
        # Find last location transition
        last_transition_idx = 0
        current_location_msg = None
        for i, msg in enumerate(messages):
            if msg.get("role") == "system" and "arrived at" in msg.get("content", "").lower():
                last_transition_idx = i
                current_location_msg = msg
            elif msg.get("role") == "user" and "Location transition:" in msg.get("content", ""):
                last_transition_idx = i
                current_location_msg = msg
        
        info(f"Last location transition at index: {last_transition_idx}")
        
        # Get messages since last transition
        current_segment = messages[last_transition_idx:]
        info(f"Messages at current location: {len(current_segment)}")
        
        # Get current location info
        party_data = safe_json_load("party_tracker.json")
        location_info = {
            "id": party_data.get("worldConditions", {}).get("currentLocationId", "Unknown"),
            "name": party_data.get("worldConditions", {}).get("currentLocationName", "Unknown Location"),
            "description": party_data.get("worldConditions", {}).get("currentDescription", "")
        }
        
        info(f"Current location: {location_info['name']} ({location_info['id']})")
        
        # Find compression range in current segment
        compress_result = self.find_compression_range(current_segment)
        if not compress_result:
            warning("Could not find enough valid pairs to compress")
            return False
        
        start, end, filtered_to_compress = compress_result
        info(f"Compressing messages {start} to {end} in current segment")
        info(f"Filtered {len(current_segment[:end]) - len(filtered_to_compress)} validation errors")
        
        # Perform compression
        info(f"Compressing {len(filtered_to_compress)} messages...")
        compressed = self.compress_messages(filtered_to_compress, location_info)
        if not compressed:
            error("Compression failed")
            return False
        
        # Build new message list
        new_messages = messages[:last_transition_idx]  # Keep everything before current location
        
        # Add location transition if it exists
        if current_location_msg and last_transition_idx > 0:
            new_messages.append(current_location_msg)
        
        # Add compressed summary
        new_messages.append(compressed)
        
        # Add remaining messages (those not compressed)
        new_messages.extend(current_segment[end:])
        
        # Calculate compression stats
        original_length = sum(len(m.get("content", "")) for m in messages)
        new_length = sum(len(m.get("content", "")) for m in new_messages)
        compression_ratio = (1 - new_length / original_length) * 100
        
        info(f"\n=== COMPRESSION RESULTS ===")
        info(f"Original messages: {len(messages)}")
        info(f"New messages: {len(new_messages)}")
        info(f"Messages compressed: {end}")
        info(f"Character reduction: {original_length} -> {new_length}")
        info(f"Compression ratio: {compression_ratio:.1f}%")
        
        # Save compressed version back to original file
        safe_json_dump(new_messages, conversation_file)
        info(f"\nCompressed conversation saved to: {conversation_file}")
        info(f"Backup preserved at: {backup_file}")
        
        # Show the compressed content
        print("\n" + "="*50)
        print("COMPRESSED SUMMARY:")
        print("="*50)
        print(compressed["content"])
        print("="*50)
        
        return True

def main():
    """Apply incremental compression to conversation history."""
    compressor = IncrementalLocationCompressor()
    
    print("\n=== APPLYING INCREMENTAL COMPRESSION ===")
    print(f"Settings:")
    print(f"  - Trigger at: {compressor.TRIGGER_THRESHOLD} valid pairs")
    print(f"  - Keep recent: {compressor.PRESERVE_RECENT} valid pairs uncompressed")
    print(f"  - Filter out: Validation error messages")
    print(f"\nStrategy: Compress all but the last 5 valid conversation pairs")
    print("="*50 + "\n")
    
    success = compressor.apply_compression()
    
    if success:
        print("\n=== COMPRESSION SUCCESSFUL ===")
        print("Conversation history has been compressed.")
        print("A backup was created before compression.")
    else:
        print("\n=== COMPRESSION NOT NEEDED ===")
        print("Not enough valid pairs to trigger compression.")

if __name__ == "__main__":
    main()