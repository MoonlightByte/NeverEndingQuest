#!/usr/bin/python3
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Multi-PC Conversation Compressor - Tabletop Mode Plugin
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.

Multi-PC aware conversation compression for tabletop mode.
Extends ParallelConversationCompressor to tag messages by active PC
and maintain storyline continuity across party members.
"""

import json
import re
from typing import Dict, Any, List, Tuple, Optional
from pathlib import Path

from utils.compression.conversation_compressor_parallel import ParallelConversationCompressor
from utils.enhanced_logger import debug, info, warning
from utils.location_context_hygiene import inject_location_provenance


class MultiPCConversationCompressor(ParallelConversationCompressor):
    """
    Multi-PC aware conversation compressor for tabletop mode.
    
    Extends ParallelConversationCompressor to:
    1. Tag messages by active PC for context retention
    2. Group consecutive messages by active PC for coherent compression
    3. Preserve cross-party events (location transitions, combat, plot)
    4. Maintain per-PC storyline continuity
    
    TABLETOP MODE: This compressor activates when MULTIPLAYER_MODE is enabled
    and party has more than 1 member. It ensures each PC's narrative arc
    remains coherent even when rotating between active characters.
    """
    
    # Message retention settings
    RECENT_EXCHANGES_KEEP_RAW = 8  # Keep last 8 exchanges uncompressed
    COMPRESSION_THRESHOLD_CHARS = 500  # Compress messages longer than this
    
    # PC detection patterns for cross-PC event identification
    CROSS_PC_PATTERNS = [
        r'Location transition:',  # Group movement
        r'Module transition:',     # Module change
        r'Combat has (started|concluded|ended)',  # Combat events
        r'XP Awarded:',            # Shared XP
        r'party',                 # Party-wide actions
    ]
    
    def __init__(self, cache_file: Optional[str] = None, max_workers: Optional[int] = None, 
                 inject_module_creation: bool = False):
        """
        Initialize multi-PC aware compressor.
        
        Args:
            cache_file: Path to compression cache file
            max_workers: Number of parallel compression workers
            inject_module_creation: Whether to inject module creation prompts
        """
        # Use default cache location if not specified
        if cache_file is None:
            cache_file = "modules/conversation_history/multi_pc_compression_cache.json"
        
        super().__init__(cache_file, max_workers if max_workers is not None else 4, inject_module_creation)
        
        # Track compression statistics
        self.pc_stats = {
            'messages_tagged': 0,
            'messages_compressed': 0,
            'cross_pc_events_preserved': 0,
            'recent_exchanges_skipped': 0
        }
    
    def extract_all_sections(self, conversation: List[Dict[str, Any]]) -> Dict[int, List[Tuple]]:
        """
        Extract sections from conversation with multi-PC awareness.
        
        Overrides parent method to:
        1. Skip recent exchanges (keep uncompressed)
        2. Group by active_pc for context
        3. Extract compressible sections (campaign contexts, location summaries)
        
        TABLETOP MODE: Fixed recent-exchanges logic to use index-based filtering
        instead of mixed counting methods that caused no-op behavior.
        
        Args:
            conversation: List of conversation messages
            
        Returns:
            Dict mapping message index to list of sections
        """
        # First, identify message groups by active PC
        pc_groups = self._group_messages_by_active_pc(conversation)
        
        # Build list of compressible message indices (user/assistant, non-DM-note)
        compressible_indices = []
        for i, msg in enumerate(conversation):
            role = msg.get("role", "")
            content = msg.get("content", "")
            
            # Only user/assistant messages are compressible
            if role not in ["user", "assistant"]:
                continue
            
            # Skip DM Notes
            if role == "user" and self._is_dm_note(content):
                continue
            
            compressible_indices.append(i)
        
        # Keep last N exchanges raw (N user + N assistant = 2N messages)
        keep_raw_count = self.RECENT_EXCHANGES_KEEP_RAW * 2
        recent_indices = set()
        if len(compressible_indices) > keep_raw_count:
            recent_indices = set(compressible_indices[-keep_raw_count:])
        else:
            # If fewer than threshold, mark all as recent (no compression)
            recent_indices = set(compressible_indices)
        
        all_sections = {}
        section_counter = 0
        
        for i, message in enumerate(conversation):
            if "content" not in message or not isinstance(message.get("content"), str):
                continue
            
            content = message.get("content", "")
            role = message.get("role", "")
            
            # Get active PC from pc_groups (handles assistant messages too)
            active_pc = pc_groups.get(i)
            
            message_sections = []
            
            # Skip compression for recent exchanges (last N user+assistant pairs)
            if i in recent_indices:
                self.pc_stats['recent_exchanges_skipped'] += 1
                continue
            
            # Skip compression for system messages
            if role == "system":
                continue
            
            # Skip DM Notes (already excluded from compressible_indices, but double-check)
            if role == "user" and self._is_dm_note(content):
                continue
            
            # Extract campaign contexts (apply standard compression)
            context_pattern = r'===\s*CAMPAIGN\s+CONTEXT\s*===\n\n---\s*(.*?)\s*\(Chronicle\s+(\d+)\)\s*---\n(.*?)(?=\n\n===|\n\n\[AI-Generated|$)'
            for match in re.finditer(context_pattern, content, re.DOTALL):
                campaign_name = match.group(1).strip()
                chronicle_num = match.group(2)
                narrative = match.group(3).strip()
                
                # Tag with active PC if available, otherwise mark as shared
                pc_tag = active_pc if active_pc else "party"
                section_id = f"{campaign_name}_Chronicle_{chronicle_num}_PC_{pc_tag}"
                message_sections.append(("context", section_id, match.group(0), narrative))
                section_counter += 1
            
            # Extract location summaries with PC tagging
            summary_pattern = r'===\s*LOCATION\s+SUMMARY\s*===\n\n(.*?)(?=\n\n===|\n\n\[AI-Generated|$)'
            for match in re.finditer(summary_pattern, content, re.DOTALL):
                narrative = match.group(1).strip()
                
                # Extract location code
                loc_code_match = re.search(r'\(([A-Z]+\d+)\)', narrative[:200])
                if loc_code_match:
                    loc_code = loc_code_match.group(1)
                else:
                    loc_code = self.get_section_hash(narrative)[:8]
                
                # Tag with active PC or mark as party-wide
                pc_tag = active_pc if active_pc else "party"
                section_id = f"Location_{loc_code}_PC_{pc_tag}"
                message_sections.append(("summary", section_id, match.group(0), narrative))
                section_counter += 1
            
            # Note: Removed narrative and cross_pc section types to maintain
            # compatibility with parent reassembly logic
            
            if message_sections:
                all_sections[i] = message_sections
                self.pc_stats['messages_compressed'] += len(message_sections)
        
        # Log statistics
        if section_counter > 0:
            debug(f"MULTI_PC_COMPRESSION: Found {section_counter} sections across {len(all_sections)} messages", 
                  category="compression")
            debug(f"MULTI_PC_COMPRESSION: Stats - {self.pc_stats}", category="compression")
        
        return all_sections
    
    def _group_messages_by_active_pc(self, conversation: List[Dict[str, Any]]) -> Dict[int, str]:
        """
        Identify message groups by active PC.
        
        Args:
            conversation: List of conversation messages
            
        Returns:
            Dict mapping message index to PC name or None
        """
        pc_groups = {}
        current_pc = None
        
        for i, message in enumerate(conversation):
            role = message.get("role", "")
            active_pc = message.get("active_pc")
            
            if role == "user" and active_pc:
                current_pc = active_pc
                self.pc_stats['messages_tagged'] += 1
            
            # Associate assistant messages with current active PC
            if role == "assistant" and current_pc:
                pc_groups[i] = current_pc
            elif role == "user":
                pc_groups[i] = current_pc
        
        return pc_groups
    
    def _identify_cross_pc_events(self, conversation: List[Dict[str, Any]]) -> set:
        """
        Identify indices of cross-PC events.
        
        Args:
            conversation: List of conversation messages
            
        Returns:
            Set of message indices that are cross-PC events
        """
        cross_pc_indices = set()
        
        for i, message in enumerate(conversation):
            content = message.get("content", "")
            
            # Check if content matches cross-PC patterns
            for pattern in self.CROSS_PC_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    cross_pc_indices.add(i)
                    break
            
            # Also check if this mentions multiple party members
            if self._mentions_multiple_party_members(content):
                cross_pc_indices.add(i)
        
        return cross_pc_indices
    
    def _is_dm_note(self, content: str) -> bool:
        """
        Check if content is a DM Note.
        
        Args:
            content: Message content string
            
        Returns:
            True if this is a DM Note
        """
        dm_note_indicators = [
            "Dungeon Master Note:",
            "--- WORLD STATE ---",
            "--- ACTIVE PC",
            "DM Note:",
        ]
        
        return any(indicator in content for indicator in dm_note_indicators)
    
    def _get_exchange_number(self, conversation: List[Dict[str, Any]], target_index: int) -> int:
        """
        Calculate which exchange number a message is in.
        
        Args:
            conversation: List of conversation messages
            target_index: Index of target message
            
        Returns:
            Exchange number (0-based)
        """
        exchange_count = 0
        for i in range(min(target_index + 1, len(conversation))):
            msg = conversation[i]
            if msg.get("role") == "user" and not self._is_dm_note(msg.get("content", "")):
                exchange_count += 1
        
        return exchange_count - 1 if exchange_count > 0 else 0
    
    def _mentions_multiple_party_members(self, content: str) -> bool:
        """
        Check if content mentions multiple party members (heuristic).
        
        Args:
            content: Message content
            
        Returns:
            True if multiple party members likely mentioned
        """
        # This is a heuristic - in practice, we'd have party member names
        # For now, detect common multi-PC indicators
        multi_indicators = [
            r'the party',
            r'everyone',
            r'all of you',
            r'together',
            r'group',
        ]
        
        matches = sum(1 for pattern in multi_indicators if re.search(pattern, content, re.IGNORECASE))
        return matches >= 2  # Multiple indicators suggest cross-party event
    
    def compress_section(self, section_data: Tuple[int, str, str, str, str]) -> Tuple[int, str, str, Dict[str, Any], bool]:
        """
        Compress a single section with multi-PC awareness.
        
        Overrides parent to add PC-specific compression metadata.
        
        Args:
            section_data: (index, section_type, section_id, full_match, narrative)
            
        Returns:
            Tuple of (index, section_id, full_match, compressed_data, from_cache)
        """
        idx, section_type, section_id, full_match, narrative = section_data
        
        # Extract PC tag from section_id if present
        pc_tag = None
        if "_PC_" in section_id:
            pc_tag = section_id.split("_PC_")[-1]
        
        # Call parent compression
        result = super().compress_section(section_data)
        
        # Add multi-PC metadata to compressed data
        if len(result) >= 4 and isinstance(result[3], dict):
            result[3]['multi_pc_metadata'] = {
                'pc_tag': pc_tag,
                'section_type': section_type,
                'compression_method': 'multi_pc_aware'
            }
        
        return result
    
    def process_conversation_history(self, conversation_file: str) -> List[Dict[str, Any]]:
        """
        Process conversation history with multi-PC awareness and fixed header generation.
        
        TABLETOP MODE: Overrides parent to properly handle PC-tagged section IDs.
        Strips PC tags from section IDs in headers (adding them as comments instead)
        to maintain compatibility with upstream header parsing logic.
        
        Args:
            conversation_file: Path to conversation history JSON file
            
        Returns:
            Processed conversation history with compression
        """
        from datetime import datetime
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        start_time = datetime.now()
        start_stats = self.pc_stats.copy()
        
        with open(conversation_file, 'r', encoding='utf-8') as f:
            conversation = json.load(f)
        
        # Apply character sheet compression FIRST (before parallel processing)
        try:
            from utils.compression.character_sheet_conversation_compressor import CharacterSheetConversationCompressor
            char_compressor = CharacterSheetConversationCompressor()
            conversation = char_compressor.compress_conversation_history(conversation)
            print("Character sheets compressed successfully")
        except Exception as e:
            print(f"Warning: Character sheet compression failed: {e}")
        
        print(f"Processing {len(conversation)} messages (Multi-PC mode)...")
        print(f"Using {self.max_workers} parallel workers")
        print("=" * 60)
        
        # Step 1: Extract all sections (using our multi-PC aware method)
        all_sections = self.extract_all_sections(conversation)
        
        # Step 2: Prepare work items for parallel processing
        work_items = []
        work_index = 0
        for msg_idx, sections in all_sections.items():
            for section_type, section_id, full_match, narrative in sections:
                work_items.append((work_index, section_type, section_id, full_match, narrative))
                work_index += 1
        
        # Only proceed with compression if there are sections to compress
        if len(work_items) == 0:
            print("No sections require compression.")
            print("-" * 60)
            print("Using existing conversation without compression.")
        else:
            print(f"\nProcessing {len(work_items)} sections in parallel...")
            print("-" * 60)
        
        # Check if any work item is a cache miss before showing UI
        self.needs_active_compression = False
        if len(work_items) > 0:
            for item in work_items:
                _, _, section_id, _, narrative = item
                content_hash = self.get_section_hash(narrative)
                cache_key = f"{section_id}_{content_hash}"
                if cache_key not in self.cache:
                    self.needs_active_compression = True
                    print("Cache miss detected. Active compression is required.")
                    break
            if not self.needs_active_compression:
                print("All sections are cached. Compression will be silent.")
        
        # Reset progress tracking
        self.completed_count = 0
        self.total_sections = len(work_items)
        
        # Only emit start event if there's actual compression work
        if self.needs_active_compression:
            try:
                from core.managers.status_manager import status_manager
                status_manager.emit_compression_event('compression_start', {
                    'total_sections': self.total_sections
                })
            except:
                pass
        
        # Step 3: Process sections in parallel
        results = {}
        self.cache_hits = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_item = {executor.submit(self.compress_section, item): item for item in work_items}
            
            for future in as_completed(future_to_item):
                result = future.result()
                idx, section_id, full_match, compressed_data, from_cache = result
                results[idx] = (section_id, full_match, compressed_data)
        
        # Report cache hits
        if self.cache_hits:
            print(f"  [CACHE HITS] {len(self.cache_hits)} sections from cache: {', '.join(self.cache_hits[:5])}{' ...' if len(self.cache_hits) > 5 else ''}")
        
        # Save cache after all processing
        self.save_cache()
        
        print("-" * 60)
        print("Compression complete. Building output with fixed headers...")
        
        # Step 4: Reassemble conversation with fixed header generation
        new_conversation = []
        result_lookup = {}
        
        # Build lookup table for quick access
        work_index = 0
        for msg_idx, sections in all_sections.items():
            for section_type, section_id, full_match, narrative in sections:
                if work_index in results:
                    result_lookup[(msg_idx, full_match)] = results[work_index]
                work_index += 1
        
        # Process each message
        for i, message in enumerate(conversation):
            # First check if this is a system prompt that needs replacement
            if message.get("role") == "system":
                message = self.replace_system_prompt(message)
            
            if i in all_sections and "content" in message:
                # This message has sections to replace
                modified_content = message["content"]
                
                for section_type, section_id, full_match, narrative in all_sections[i]:
                    if (i, full_match) in result_lookup:
                        _, _, compressed_data = result_lookup[(i, full_match)]
                        compressed_text = compressed_data.get('compressed', narrative)
                        
                        # Extract PC tag from section_id if present
                        pc_tag = None
                        clean_section_id = section_id
                        if "_PC_" in section_id:
                            parts = section_id.rsplit("_PC_", 1)
                            clean_section_id = parts[0]
                            pc_tag = parts[1]
                        
                        # Create appropriate header based on type, with PC tag as comment
                        if "context" in section_type.lower():
                            # Extract module name and chronicle from clean_section_id
                            parts = clean_section_id.rsplit('_Chronicle_', 1)
                            if len(parts) == 2:
                                module_name = parts[0].replace('_', ' ')
                                chronicle_num = parts[1]
                                # TABLETOP MODE: Add PC tag as comment instead of embedding in chronicle number
                                pc_comment = f"  # PC: {pc_tag}" if pc_tag else ""
                                header = f"=== CAMPAIGN HISTORY: {module_name} (Chronicle {chronicle_num}) ==={pc_comment}\n\n[These events have already occurred and form the party's backstory.]"
                            else:
                                header = "=== CAMPAIGN HISTORY ===\n\n[These events have already occurred and form the party's backstory.]"
                        else:
                            # For location summaries
                            location_match = re.match(r'^(.*?\([A-Z]+\d+\)):', narrative)
                            if location_match:
                                location_info = location_match.group(1)
                                pc_comment = f"  # PC: {pc_tag}" if pc_tag else ""
                                header = f"=== LOCATION CHRONICLE: {location_info} ==={pc_comment}\n\n[IMPORTANT: This is the canonical record of actual events that occurred at this location. Reference these as historical fact when narrating.]"
                                if compressed_text.startswith(location_info):
                                    compressed_text = compressed_text[len(location_info):].lstrip(':').strip()
                            else:
                                header = "=== LOCATION CHRONICLE ===\n\n[IMPORTANT: This is the canonical record of actual events. Reference these as historical fact when narrating.]"
                        
                        compressed_replacement = f"{header}\n\n{compressed_text}"
                        if header.startswith("=== LOCATION CHRONICLE:"):
                            location_id_match = re.search(r'\(([A-Z]+\d+)\)', header)
                            location_id = location_id_match.group(1) if location_id_match else "unknown"
                            compressed_replacement = inject_location_provenance(
                                compressed_replacement,
                                "unknown",
                                "unknown",
                                location_id,
                                "location_chronicle",
                            )
                        modified_content = modified_content.replace(full_match, compressed_replacement)
                
                new_message = message.copy()
                new_message["content"] = modified_content
                new_conversation.append(new_message)
            else:
                # No other changes needed for this message
                new_conversation.append(message)
        
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\nTotal processing time: {elapsed:.1f} seconds")
        
        # Log multi-PC specific statistics
        debug(f"MULTI_PC_COMPRESSION: Completed processing", category="compression")
        debug(f"MULTI_PC_COMPRESSION: Messages tagged: {self.pc_stats['messages_tagged'] - start_stats['messages_tagged']}", 
              category="compression")
        debug(f"MULTI_PC_COMPRESSION: Recent exchanges kept raw: {self.pc_stats['recent_exchanges_skipped'] - start_stats['recent_exchanges_skipped']}", 
              category="compression")
        
        # Calculate compression statistics and emit completion event
        if self.total_sections > 0 and hasattr(self, 'needs_active_compression') and self.needs_active_compression:
            try:
                from core.managers.status_manager import status_manager
                original_size = sum(len(json.dumps(m)) for m in conversation)
                compressed_size = sum(len(json.dumps(m)) for m in new_conversation)
                reduction_pct = round((1 - compressed_size/original_size) * 100) if original_size > 0 else 0
                
                status_manager.emit_compression_event('compression_complete', {
                    'reduction_percentage': reduction_pct,
                    'original_size': original_size,
                    'compressed_size': compressed_size
                })
            except:
                pass
        
        return new_conversation


# Convenience function for direct usage
def compress_conversation_history_multi_pc(conversation_file: str, 
                                              inject_module_creation: bool = False) -> List[Dict[str, Any]]:
    """
    Convenience function to compress conversation history with multi-PC awareness.
    
    Args:
        conversation_file: Path to conversation history JSON file
        inject_module_creation: Whether to inject module creation prompts
        
    Returns:
        Processed conversation history
    """
    compressor = MultiPCConversationCompressor(inject_module_creation=inject_module_creation)
    return compressor.process_conversation_history(conversation_file)


def should_use_multi_pc_compression(party_tracker_data: Optional[Dict[str, Any]]) -> bool:
    """
    Determine if multi-PC compression should be used.
    
    Mirrors the logic in multi_pc_dm_note.py for consistency.
    
    Args:
        party_tracker_data: The party tracker data dict
        
    Returns:
        True if MULTIPLAYER_MODE is enabled AND party has more than 1 member
    """
    # Check global toggle first
    try:
        from config import MULTIPLAYER_MODE
        if not MULTIPLAYER_MODE:
            return False
    except ImportError:
        return False
    
    # Then check party size
    if not party_tracker_data:
        return False
    
    party_members = party_tracker_data.get('partyMembers', [])
    return len(party_members) > 1


if __name__ == "__main__":
    # Test the multi-PC compressor
    print("Multi-PC Conversation Compressor Test")
    print("=" * 60)
    
    conversation_file = "modules/conversation_history/conversation_history.json"
    
    if not Path(conversation_file).exists():
        print(f"Error: {conversation_file} not found")
        exit(1)
    
    # Load and analyze
    with open(conversation_file, 'r', encoding='utf-8') as f:
        conversation = json.load(f)
    
    # Count messages by role
    roles = {}
    active_pcs = {}
    for msg in conversation:
        role = msg.get('role', 'unknown')
        roles[role] = roles.get(role, 0) + 1
        
        if 'active_pc' in msg:
            pc = msg['active_pc']
            active_pcs[pc] = active_pcs.get(pc, 0) + 1
    
    print(f"\nConversation Statistics:")
    print(f"  Total messages: {len(conversation)}")
    print(f"  By role: {roles}")
    print(f"  Tagged with active_pc: {active_pcs if active_pcs else 'None'}")
    
    print("\nCompressor initialized successfully.")
    print("Ready for multi-PC conversation compression.")
