#!/usr/bin/env python3
"""
Character Sheet Conversation Compressor
Replaces character sheet entries in conversation history with compressed versions.

This module finds and replaces both player character sheets and NPC sheets
in the conversation history with their compressed equivalents using the
character_sheet_compressor format.
"""

import json
import re
import os
import sys
from typing import List, Dict, Any, Optional
from pathlib import Path

# Add parent directories to path for imports
sys.path.append('/mnt/c/dungeon_master_v1')
from core.ai.character_sheet_compressor import format_flatlist
from utils.enhanced_logger import debug, info, warning, error

class CharacterSheetConversationCompressor:
    """Compress character sheets within conversation history"""
    
    def __init__(self, characters_dir: str = "characters"):
        """
        Initialize the compressor with character directory location
        
        Args:
            characters_dir: Directory containing character JSON files
        """
        self.characters_dir = characters_dir
        self._character_cache = {}  # Cache loaded character data
        self._compression_cache = {}  # Cache compressed outputs
        
    def _load_character_data(self, character_name: str) -> Optional[Dict[str, Any]]:
        """
        Load character JSON data from file
        
        Args:
            character_name: Name of character (e.g., "eirik_hearthwise")
            
        Returns:
            Character data dict or None if not found
        """
        # Check cache first
        if character_name in self._character_cache:
            return self._character_cache[character_name]
            
        # Try to load from file
        char_file = os.path.join(self.characters_dir, f"{character_name}.json")
        if os.path.exists(char_file):
            try:
                with open(char_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._character_cache[character_name] = data
                    return data
            except Exception as e:
                warning(f"Failed to load character file {char_file}: {e}")
                return None
        return None
        
    def _get_compressed_character(self, character_name: str) -> Optional[str]:
        """
        Get compressed character sheet using the flatlist format
        
        Args:
            character_name: Name of character
            
        Returns:
            Compressed character string or None
        """
        # Check compression cache
        if character_name in self._compression_cache:
            return self._compression_cache[character_name]
            
        # Load character data
        char_data = self._load_character_data(character_name)
        if not char_data:
            return None
            
        try:
            # Use the flatlist formatter
            compressed = format_flatlist(char_data)
            self._compression_cache[character_name] = compressed
            return compressed
        except Exception as e:
            error(f"Failed to compress character {character_name}: {e}")
            return None
            
    def compress_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compress character sheets in a single message
        
        Args:
            message: Message dict with role and content
            
        Returns:
            Message with compressed character sheets
        """
        if message.get("role") != "system":
            return message
            
        content = message.get("content", "")
        
        # Pattern for player character sheets
        player_pattern = r"Here's the updated character data for (\w+):\n\n(.+?)(?=\n\n(?:Here's|$)|$)"
        
        # Pattern for NPC sheets  
        npc_pattern = r"Here's the NPC data for ([^:]+):\n\n(.+?)(?=\n\n(?:Here's|$)|$)"
        
        modified = False
        new_content = content
        
        # Process player character sheets
        for match in re.finditer(player_pattern, content, re.DOTALL):
            character_name = match.group(1)
            original_sheet = match.group(2)
            
            # Get compressed version
            compressed = self._get_compressed_character(character_name)
            if compressed:
                # Replace with compressed version
                replacement = f"Here's the updated character data for {character_name}:\n\n{compressed}"
                new_content = new_content.replace(match.group(0), replacement)
                modified = True
                debug(f"Compressed player character sheet for {character_name}")
                
        # Process NPC sheets
        for match in re.finditer(npc_pattern, new_content, re.DOTALL):
            npc_name = match.group(1).strip()
            original_sheet = match.group(2)
            
            # Convert NPC name to file format (e.g., "Ranger Thane" -> "ranger_thane")
            npc_filename = npc_name.lower().replace(" ", "_")
            
            # Get compressed version
            compressed = self._get_compressed_character(npc_filename)
            if compressed:
                # Replace with compressed version
                replacement = f"Here's the NPC data for {npc_name}:\n\n{compressed}"
                new_content = new_content.replace(match.group(0), replacement)
                modified = True
                debug(f"Compressed NPC sheet for {npc_name}")
                
        if modified:
            return {
                "role": message["role"],
                "content": new_content
            }
        return message
        
    def compress_conversation_history(self, conversation: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Compress all character sheets in a conversation history
        
        Args:
            conversation: List of message dicts
            
        Returns:
            Conversation with compressed character sheets
        """
        compressed_conversation = []
        compression_count = 0
        
        for message in conversation:
            compressed_msg = self.compress_message(message)
            if compressed_msg.get("content") != message.get("content"):
                compression_count += 1
            compressed_conversation.append(compressed_msg)
            
        if compression_count > 0:
            info(f"Compressed {compression_count} character sheet messages")
            
        return compressed_conversation
        
    def process_file(self, input_file: str, output_file: str = None) -> bool:
        """
        Process a conversation history file
        
        Args:
            input_file: Path to input JSON file
            output_file: Path to output file (optional, defaults to overwrite)
            
        Returns:
            True if successful
        """
        try:
            # Load conversation
            with open(input_file, 'r', encoding='utf-8') as f:
                conversation = json.load(f)
                
            # Compress character sheets
            compressed = self.compress_conversation_history(conversation)
            
            # Save output
            output_path = output_file or input_file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(compressed, f, indent=2, ensure_ascii=False)
                
            info(f"Successfully processed {input_file}")
            return True
            
        except Exception as e:
            error(f"Failed to process file {input_file}: {e}")
            return False


def integrate_with_parallel_compressor(conversation_file: str) -> List[Dict[str, Any]]:
    """
    Integration function for use with ParallelConversationCompressor
    
    This function can be called from the parallel compressor to apply
    character sheet compression as part of the parallel processing pipeline.
    
    Args:
        conversation_file: Path to conversation history file
        
    Returns:
        Compressed conversation history
    """
    # Load the conversation
    with open(conversation_file, 'r', encoding='utf-8') as f:
        conversation = json.load(f)
    
    # Apply character sheet compression
    compressor = CharacterSheetConversationCompressor()
    return compressor.compress_conversation_history(conversation)


if __name__ == "__main__":
    # Test/CLI usage
    import argparse
    
    parser = argparse.ArgumentParser(description="Compress character sheets in conversation history")
    parser.add_argument("input", help="Input conversation history JSON file")
    parser.add_argument("-o", "--output", help="Output file (default: overwrite input)")
    parser.add_argument("-d", "--characters-dir", default="characters", 
                       help="Directory containing character JSON files")
    
    args = parser.parse_args()
    
    compressor = CharacterSheetConversationCompressor(characters_dir=args.characters_dir)
    success = compressor.process_file(args.input, args.output)
    
    sys.exit(0 if success else 1)