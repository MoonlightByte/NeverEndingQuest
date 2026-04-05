#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
"""
Combat user message compressor with parallel processing and caching.
Compresses combat messages in conversation history for AI consumption only.
Does NOT modify the stored conversation history JSON file.
"""

import json
import hashlib
import re
import copy
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from datetime import datetime

# Import the combat compression engine from same directory
from core.ai.combat_compression_engine import CombatCompressor

class CombatUserMessageCompressor:
    """Compress user combat messages in parallel for AI consumption."""
    
    def __init__(self, api_key: str = None, cache_file: str = "modules/conversation_history/combat_user_message_cache.json", max_workers: int = 4):
        """Initialize with cache file and thread pool settings."""
        self.cache_file = cache_file
        self.cache = self.load_cache()
        self.cache_lock = threading.Lock()  # Thread safety for cache
        self.max_workers = max_workers
        self.progress_lock = threading.Lock()  # Thread safety for progress tracking
        self.completed_count = 0
        self.total_messages = 0
        # CombatCompressor no longer accepts an API key; it reads provider config internally.
        self.combat_compressor = CombatCompressor(enable_caching=False)
        
    def load_cache(self) -> Dict[str, str]:
        """Load existing cache from file."""
        cache_path = Path(self.cache_file)
        if cache_path.exists():
            try:
                with open(cache_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_cache(self):
        """Save cache to file (thread-safe)."""
        with self.cache_lock:
            # Ensure directory exists
            cache_path = Path(self.cache_file)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, indent=2, ensure_ascii=False)
    
    def get_content_hash(self, content: str) -> str:
        """Generate MD5 hash of content for caching."""
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def should_compress_user_message(self, message: Dict, index: int, total_messages: int) -> bool:
        """
        Check if a user message should be compressed.
        
        Args:
            message: The message dict with role and content
            index: The index of this message in conversation
            total_messages: Total number of messages
            
        Returns:
            True if message should be compressed
        """
        # Only user messages
        if message.get("role") != "user":
            return False
        
        content = message.get("content", "")
        
        # Skip Dungeon Master Notes
        if content.startswith("Dungeon Master Note:"):
            return False
        
        # Skip the 5 most recent user messages for better fidelity
        if index >= total_messages - 5:
            return False
        
        # Check for combat markers
        has_round_info = "--- ROUND INFO ---" in content
        has_creature_states = "--- CREATURE STATES ---" in content
        has_dice_pools = "--- DICE POOLS ---" in content
        
        return has_round_info and has_creature_states and has_dice_pools
    
    def _update_progress(self, from_cache: bool):
        """Update progress tracking and emit status events."""
        with self.progress_lock:
            self.completed_count += 1
            if from_cache:
                print(f"  [{self.completed_count:3d}/{self.total_messages:3d}] [CACHE HIT]")
            else:
                print(f"  [{self.completed_count:3d}/{self.total_messages:3d}] [COMPRESSED]")
            
            # Try to emit progress event for UI
            try:
                from core.managers.status_manager import status_manager
                status_manager.emit_compression_event('compression_progress', {
                    'completed': self.completed_count,
                    'total': self.total_messages,
                    'from_cache': from_cache
                })
            except:
                pass  # Silently ignore if status manager not available
    
    def compress_message(self, message_data: Tuple[int, str]) -> Tuple[int, str, bool]:
        """
        Compress a single combat message.
        
        Args:
            message_data: Tuple of (index, content)
            
        Returns:
            Tuple of (index, compressed_content, from_cache)
        """
        idx, content = message_data
        
        content_hash = self.get_content_hash(content)
        
        # Check cache first (thread-safe)
        with self.cache_lock:
            if content_hash in self.cache:
                self._update_progress(from_cache=True)
                return (idx, self.cache[content_hash], True)
        
        # Compress using combat compressor
        try:
            compressed = self.combat_compressor.compress(content)
            
            # Cache the result (thread-safe)
            with self.cache_lock:
                self.cache[content_hash] = compressed
            
            self._update_progress(from_cache=False)
            
            # Calculate reduction for logging
            original_len = len(content)
            compressed_len = len(compressed)
            reduction = (1 - compressed_len/original_len) * 100 if original_len > 0 else 0
            print(f"      Reduced by {reduction:.1f}% ({original_len} -> {compressed_len} chars)")
            
            return (idx, compressed, False)
            
        except Exception as e:
            print(f"  [ERROR] Failed to compress message {idx}: {e}")
            self._update_progress(from_cache=False)
            return (idx, content, False)  # Return original on error
    
    def strip_combat_setup_messages(self, messages: List[Dict]) -> List[Dict]:
        """
        Strip down the initial combat setup message pair to save tokens.
        Only strips if we're deep enough into combat (past index 10).
        
        Args:
            messages: The conversation messages
            
        Returns:
            Messages with setup pair stripped if applicable
        """
        # Find the last system message
        last_system_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "system":
                last_system_idx = i
                break
        
        # If we found a system message and there are messages after it
        if last_system_idx >= 0 and last_system_idx < len(messages) - 2:
            # Check if the next message is the combat setup user message
            user_idx = last_system_idx + 1
            assistant_idx = last_system_idx + 2
            
            if (user_idx < len(messages) and 
                messages[user_idx].get("role") == "user" and
                assistant_idx < len(messages) and 
                messages[assistant_idx].get("role") == "assistant"):
                
                user_content = messages[user_idx].get("content", "")
                
                # Check if this is the combat setup message
                if ("Dungeon Master Note: Respond with valid JSON" in user_content and 
                    "This is the start of combat" in user_content):
                    
                    # Only strip if we have at least 4 more messages after the setup (2 message pairs)
                    if assistant_idx < len(messages) - 4:
                        print(f"  [INFO] Stripping combat setup messages at indices {user_idx}-{assistant_idx}")
                        
                        # Strip user message to essentials
                        messages[user_idx]["content"] = "Combat initiated. Player: Describe the combat situation and enemies."
                        
                        # Strip assistant message to essentials
                        # Try to extract key info from the assistant's response
                        assistant_content = messages[assistant_idx].get("content", "")
                        
                        # Default simplified message
                        simplified_response = "Combat started. Round 1 - Initial enemy positions set."
                        
                        # Try to extract enemy count/type if mentioned in narration
                        if "sahuagin" in assistant_content.lower():
                            if "three" in assistant_content.lower() or "3" in assistant_content:
                                simplified_response = "Combat started. Round 1 - Enemies: 3 sahuagin emerged from the sea at the docks."
                            else:
                                simplified_response = "Combat started. Round 1 - Enemies: Sahuagin attackers at the docks."
                        
                        messages[assistant_idx]["content"] = simplified_response
                        
                        print(f"      Reduced setup pair from ~2500 chars to ~170 chars")
        
        return messages
    
    def process_combat_conversation(self, conversation_history: List[Dict]) -> List[Dict]:
        """
        Process conversation history and return compressed version for AI.
        Does NOT modify the original conversation_history file.
        
        Args:
            conversation_history: The original conversation history
            
        Returns:
            Modified copy of conversation with combat messages compressed
        """
        start_time = datetime.now()
        
        # Create a deep copy to avoid modifying original
        messages_to_send = copy.deepcopy(conversation_history)
        
        # Strip combat setup messages first if applicable
        messages_to_send = self.strip_combat_setup_messages(messages_to_send)
        
        # Find messages to compress
        messages_to_compress = []
        total_messages = len(messages_to_send)
        
        for i, message in enumerate(messages_to_send):
            if self.should_compress_user_message(message, i, total_messages):
                messages_to_compress.append((i, message["content"]))
        
        if not messages_to_compress:
            print("No combat messages require compression.")
            return messages_to_send
        
        print(f"\nCompressing {len(messages_to_compress)} combat messages...")
        print(f"Using {self.max_workers} parallel workers")
        print(f"Skipping last 5 user messages for better fidelity")
        print("-" * 60)
        
        # Reset progress tracking
        self.completed_count = 0
        self.total_messages = len(messages_to_compress)
        
        # Emit compression start event for UI (only if there's work to do)
        try:
            from core.managers.status_manager import status_manager
            status_manager.emit_compression_event('compression_start', {
                'total_sections': self.total_messages
            })
        except:
            pass  # Silently ignore if status manager not available
        
        # Process messages in parallel
        results = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all compression tasks
            future_to_idx = {
                executor.submit(self.compress_message, item): item[0] 
                for item in messages_to_compress
            }
            
            # Process completed tasks
            for future in as_completed(future_to_idx):
                idx, compressed_content, from_cache = future.result()
                results[idx] = compressed_content
        
        # Replace content in messages_to_send with compressed versions
        replacements = 0
        for idx, compressed_content in results.items():
            if idx < len(messages_to_send):
                original_len = len(messages_to_send[idx]["content"])
                compressed_len = len(compressed_content)
                
                # Replace if we have valid compressed format (starts with @T=CS/v2)
                # Even if size didn't reduce much, the structured format is better for AI
                if compressed_content.startswith("@T=CS/v2"):
                    messages_to_send[idx]["content"] = compressed_content
                    replacements += 1
                    if compressed_len >= original_len:
                        print(f"  [INFO] Message {idx}: Using compressed format despite size ({original_len} -> {compressed_len})")
                elif compressed_len < original_len:
                    # Fallback: If not proper format but smaller, still use it
                    messages_to_send[idx]["content"] = compressed_content
                    replacements += 1
                    print(f"  [WARNING] Message {idx}: Non-standard compression used")
        
        # Save cache after all processing
        self.save_cache()
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        print("-" * 60)
        print(f"Compression complete in {elapsed:.1f} seconds")
        print(f"Replaced {replacements} messages with compressed versions")
        print(f"Cache entries: {len(self.cache)}")
        
        # Calculate overall statistics
        original_size = sum(len(json.dumps(m)) for m in conversation_history)
        compressed_size = sum(len(json.dumps(m)) for m in messages_to_send)
        
        if original_size > 0:
            reduction = (1 - compressed_size/original_size) * 100
            print(f"Overall reduction: {reduction:.1f}% ({original_size:,} -> {compressed_size:,} chars)")
        
        # Emit compression complete event for UI (only if compression occurred)
        if self.total_messages > 0:
            try:
                from core.managers.status_manager import status_manager
                reduction_pct = round((1 - compressed_size/original_size) * 100) if original_size > 0 else 0
                
                status_manager.emit_compression_event('compression_complete', {
                    'reduction_percentage': reduction_pct,
                    'original_size': original_size,
                    'compressed_size': compressed_size
                })
            except:
                pass  # Silently ignore if status manager not available
        
        return messages_to_send

def main():
    """Test the combat message compressor on actual conversation history."""
    
    # Test with combat conversation history
    conversation_file = "modules/conversation_history/combat_conversation_history.json"
    
    if not Path(conversation_file).exists():
        print(f"Error: {conversation_file} not found")
        print("Trying alternative file...")
        conversation_file = "modules/conversation_history/conversation_history.json"
        
        if not Path(conversation_file).exists():
            print(f"Error: No conversation history found")
            return
    
    print("Combat User Message Compressor Test")
    print("=" * 60)
    print(f"Input: {conversation_file}")
    
    # Load original conversation
    with open(conversation_file, 'r', encoding='utf-8') as f:
        original_conversation = json.load(f)
    
    print(f"Loaded {len(original_conversation)} messages")
    
    # Create compressor and process
    compressor = CombatUserMessageCompressor()
    messages_to_send = compressor.process_combat_conversation(original_conversation)
    
    # Save compressed version for review (but this is just for testing)
    output_file = "combat_conversation_compressed_test.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(messages_to_send, f, indent=2, ensure_ascii=False)
    
    print(f"\nTest output saved to: {output_file}")
    print("Note: In production, this would be sent to AI, not saved to file")
    
    # Show sample of compressed message
    print("\nSample compressed message:")
    print("-" * 60)
    
    for i, msg in enumerate(messages_to_send):
        if msg.get("role") == "user" and "@T=CS/v2" in msg.get("content", ""):
            sample = msg["content"][:500] + "..." if len(msg["content"]) > 500 else msg["content"]
            print(f"Message {i}:")
            print(sample)
            break

if __name__ == "__main__":
    main()
