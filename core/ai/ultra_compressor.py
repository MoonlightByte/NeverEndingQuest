#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
Ultra-Compression Engine for Narrative Text

Transforms verbose narrative text into an ultra-compact indexed format
with 90%+ compression ratios. Uses multi-pass analysis with NLP techniques
to extract entities and convert narratives to symbolic notation.

TARGET FORMAT:
@C={1:Name,2:Name,...}     # Characters
@L={1:Location,...}         # Locations  
@S={1:Spell,...}           # Spells
@I={item:details,...}       # Items
@R={r1:relationship,...}    # Relationships

EVT[                        # Events in symbolic notation
1) Action@Location. Details.
2) Character→Location. Action.
...]
"""

import re
import json
from typing import Dict, List, Tuple, Set, Any
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from enum import Enum

# Try to import spaCy for NLP, fallback to regex if not available
try:
    import spacy
    nlp = spacy.load("en_core_web_sm")
    NLP_AVAILABLE = True
except:
    NLP_AVAILABLE = False
    print("Warning: spaCy not available. Using regex-based extraction.")

class EntityType(Enum):
    """Types of entities we extract"""
    CHARACTER = "@C"
    LOCATION = "@L"
    SPELL = "@S"
    ITEM = "@I"
    RELATIONSHIP = "@R"

@dataclass
class Entity:
    """Represents an extracted entity"""
    name: str
    type: EntityType
    index: int = 0
    aliases: Set[str] = field(default_factory=set)
    attributes: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Event:
    """Represents a narrative event"""
    actors: List[int] = field(default_factory=list)
    action: str = ""
    location: int = None
    objects: List[int] = field(default_factory=list)
    modifiers: List[str] = field(default_factory=list)
    raw_text: str = ""

class UltraCompressor:
    """Advanced narrative compression engine"""
    
    # Common action verbs mapped to symbols
    ACTION_SYMBOLS = {
        "move": "→", "go": "→", "travel": "→", "walk": "→", "run": "→",
        "return": "←", "back": "←", "retreat": "←",
        "attack": "⚔", "fight": "⚔", "battle": "⚔", "strike": "⚔",
        "defend": "🛡", "protect": "🛡", "guard": "🛡",
        "cast": "✨", "spell": "✨", "magic": "✨",
        "talk": "💬", "speak": "💬", "say": "💬", "tell": "💬",
        "give": "→", "take": "←", "receive": "←",
        "increase": "↑", "grow": "↑", "rise": "↑", "improve": "↑",
        "decrease": "↓", "fall": "↓", "reduce": "↓", "diminish": "↓",
        "die": "💀", "death": "💀", "kill": "💀", "slay": "💀",
        "heal": "❤", "cure": "❤", "restore": "❤",
        "and": "&", "with": "&",
        "at": "@", "in": "@", "inside": "@",
        "equals": "=", "is": "=", "becomes": "=",
        "multiply": "×", "times": "×",
        "relationship": "↔", "between": "↔", "together": "↔"
    }
    
    # ASCII fallback symbols (for Windows compatibility)
    ACTION_SYMBOLS_ASCII = {
        "move": "->", "go": "->", "travel": "->", "walk": "->", "run": "->",
        "return": "<-", "back": "<-", "retreat": "<-",
        "attack": "ATK", "fight": "ATK", "battle": "ATK", "strike": "ATK",
        "defend": "DEF", "protect": "DEF", "guard": "DEF",
        "cast": "CAST", "spell": "CAST", "magic": "CAST",
        "talk": "TALK", "speak": "TALK", "say": "TALK", "tell": "TALK",
        "give": "->", "take": "<-", "receive": "<-",
        "increase": "UP", "grow": "UP", "rise": "UP", "improve": "UP",
        "decrease": "DN", "fall": "DN", "reduce": "DN", "diminish": "DN",
        "die": "DIE", "death": "DIE", "kill": "KILL", "slay": "KILL",
        "heal": "HEAL", "cure": "HEAL", "restore": "HEAL",
        "and": "&", "with": "&",
        "at": "@", "in": "@", "inside": "@",
        "equals": "=", "is": "=", "becomes": "=",
        "multiply": "x", "times": "x",
        "relationship": "<->", "between": "<->", "together": "<->"
    }
    
    def __init__(self, use_ascii=True):
        """Initialize the compressor
        
        Args:
            use_ascii: Use ASCII symbols for Windows compatibility
        """
        self.entities: Dict[EntityType, List[Entity]] = defaultdict(list)
        self.entity_index: Dict[str, Entity] = {}
        self.events: List[Event] = []
        self.use_ascii = use_ascii
        self.symbols = self.ACTION_SYMBOLS_ASCII if use_ascii else self.ACTION_SYMBOLS
        
    def compress(self, text: str) -> str:
        """Main compression pipeline
        
        Args:
            text: The narrative text to compress
            
        Returns:
            Ultra-compressed indexed format
        """
        # Pipeline stages
        self._extract_entities(text)
        self._extract_events(text)
        self._build_relationships()
        self._compress_events()
        
        # Generate output
        return self._generate_output()
    
    def _extract_entities(self, text: str):
        """Extract all entities from the text"""
        
        if NLP_AVAILABLE:
            self._extract_entities_nlp(text)
        else:
            self._extract_entities_regex(text)
            
        # Assign indices
        self._assign_indices()
    
    def _extract_entities_nlp(self, text: str):
        """Extract entities using spaCy NLP"""
        doc = nlp(text)
        
        # Extract named entities
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                self._add_entity(ent.text, EntityType.CHARACTER)
            elif ent.label_ in ["LOC", "GPE", "FAC"]:
                self._add_entity(ent.text, EntityType.LOCATION)
                
        # Extract items (nouns with certain patterns)
        for token in doc:
            if token.pos_ == "NOUN":
                # Check for item patterns
                if any(pat in token.text.lower() for pat in ["sword", "armor", "potion", "scroll", "gem", "gold", "shield", "bow", "staff", "ring"]):
                    self._add_entity(token.text, EntityType.ITEM)
                # Check for spell patterns
                elif any(pat in token.text.lower() for pat in ["spell", "magic", "enchantment", "curse", "blessing"]):
                    self._add_entity(token.text, EntityType.SPELL)
    
    def _extract_entities_regex(self, text: str):
        """Extract entities using regex patterns"""
        
        # Character patterns (capitalized words, names)
        char_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b'
        for match in re.finditer(char_pattern, text):
            name = match.group(1)
            # Filter out common words
            if name.lower() not in ['the', 'a', 'an', 'this', 'that', 'here', 'there']:
                self._add_entity(name, EntityType.CHARACTER)
        
        # Location patterns (places with certain keywords)
        loc_keywords = ['town', 'city', 'village', 'castle', 'tower', 'forest', 'mountain', 'river', 'inn', 'tavern', 'temple', 'dungeon', 'cave', 'road', 'path', 'bridge', 'gate', 'wall', 'room', 'hall', 'chamber']
        for keyword in loc_keywords:
            pattern = rf'(\w+\s+)?{keyword}|{keyword}(\s+\w+)?'
            for match in re.finditer(pattern, text, re.IGNORECASE):
                self._add_entity(match.group(0).strip(), EntityType.LOCATION)
        
        # Item patterns
        item_keywords = ['sword', 'armor', 'shield', 'bow', 'staff', 'ring', 'potion', 'scroll', 'gem', 'gold', 'cloak', 'boots', 'helm', 'gauntlet', 'amulet', 'dagger', 'axe', 'mace', 'spear']
        for keyword in item_keywords:
            pattern = rf'(\w+\s+)?{keyword}|{keyword}(\s+\w+)?'
            for match in re.finditer(pattern, text, re.IGNORECASE):
                self._add_entity(match.group(0).strip(), EntityType.ITEM)
        
        # Spell patterns
        spell_keywords = ['spell', 'magic', 'enchantment', 'curse', 'blessing', 'ward', 'barrier', 'summon', 'teleport', 'heal', 'fireball', 'lightning']
        for keyword in spell_keywords:
            pattern = rf'(\w+\s+)?{keyword}|{keyword}(\s+\w+)?'
            for match in re.finditer(pattern, text, re.IGNORECASE):
                self._add_entity(match.group(0).strip(), EntityType.SPELL)
    
    def _add_entity(self, name: str, entity_type: EntityType):
        """Add an entity to our collection"""
        # Normalize name
        normalized = self._normalize_name(name)
        
        # Check if already exists
        if normalized in self.entity_index:
            # Add as alias if different
            if name != self.entity_index[normalized].name:
                self.entity_index[normalized].aliases.add(name)
            return
        
        # Create new entity
        entity = Entity(name=normalized, type=entity_type)
        entity.aliases.add(name)
        
        self.entities[entity_type].append(entity)
        self.entity_index[normalized] = entity
    
    def _normalize_name(self, name: str) -> str:
        """Normalize entity names for matching"""
        # Remove articles and common words
        words_to_remove = ['the', 'a', 'an', 'of', 'to', 'in', 'at', 'on']
        words = name.lower().split()
        words = [w for w in words if w not in words_to_remove]
        
        # Rejoin and capitalize
        if words:
            return ''.join(w.capitalize() for w in words)
        return name.capitalize()
    
    def _assign_indices(self):
        """Assign numerical indices to entities"""
        for entity_type in EntityType:
            entities = self.entities[entity_type]
            for i, entity in enumerate(entities, 1):
                entity.index = i
    
    def _extract_events(self, text: str):
        """Extract events from the narrative"""
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        
        for sentence in sentences:
            if not sentence.strip():
                continue
                
            event = Event(raw_text=sentence.strip())
            
            # Find actors (characters mentioned)
            for entity in self.entities[EntityType.CHARACTER]:
                for alias in entity.aliases:
                    if alias.lower() in sentence.lower():
                        event.actors.append(entity.index)
            
            # Find location
            for entity in self.entities[EntityType.LOCATION]:
                for alias in entity.aliases:
                    if alias.lower() in sentence.lower():
                        event.location = entity.index
                        break
            
            # Find items
            for entity in self.entities[EntityType.ITEM]:
                for alias in entity.aliases:
                    if alias.lower() in sentence.lower():
                        event.objects.append(entity.index)
            
            # Extract action
            event.action = self._extract_action(sentence)
            
            # Only add events with content
            if event.actors or event.action or event.location:
                self.events.append(event)
    
    def _extract_action(self, sentence: str) -> str:
        """Extract and symbolize the main action"""
        sentence_lower = sentence.lower()
        
        # Find action verbs and convert to symbols
        actions = []
        for word, symbol in self.symbols.items():
            if word in sentence_lower:
                actions.append(symbol)
        
        # Return most relevant action or abbreviated form
        if actions:
            return actions[0]
        
        # Fallback: extract verb
        words = sentence.split()
        verbs = []
        for word in words:
            # Simple heuristic for verbs (ends with common verb endings)
            if any(word.lower().endswith(ending) for ending in ['ed', 'ing', 's', 'es']):
                verbs.append(word[:3].lower())  # Abbreviate
        
        return verbs[0] if verbs else "act"
    
    def _build_relationships(self):
        """Analyze and build relationships between entities"""
        relationships = []
        
        # Analyze co-occurrence in events
        char_pairs = defaultdict(int)
        for event in self.events:
            if len(event.actors) >= 2:
                for i in range(len(event.actors)):
                    for j in range(i+1, len(event.actors)):
                        pair = tuple(sorted([event.actors[i], event.actors[j]]))
                        char_pairs[pair] += 1
        
        # Create relationships for frequently co-occurring characters
        for pair, count in char_pairs.items():
            if count >= 2:  # Threshold for relationship
                rel = f"r{len(relationships)+1}:({pair[0]}<->{pair[1]} together)"
                relationships.append(rel)
        
        # Store relationships
        if relationships:
            rel_entity = Entity(name="relationships", type=EntityType.RELATIONSHIP)
            rel_entity.attributes["relations"] = relationships
            self.entities[EntityType.RELATIONSHIP].append(rel_entity)
    
    def _compress_events(self):
        """Apply compression patterns to events"""
        # Group consecutive events at same location
        compressed = []
        current_location = None
        location_events = []
        
        for event in self.events:
            if event.location == current_location:
                location_events.append(event)
            else:
                if location_events:
                    compressed.append(self._merge_location_events(location_events, current_location))
                current_location = event.location
                location_events = [event]
        
        # Don't forget last group
        if location_events:
            compressed.append(self._merge_location_events(location_events, current_location))
        
        self.events = compressed
    
    def _merge_location_events(self, events: List[Event], location: int) -> Event:
        """Merge multiple events at the same location"""
        if len(events) == 1:
            return events[0]
        
        merged = Event()
        merged.location = location
        
        # Collect all unique actors
        all_actors = set()
        actions = []
        objects = set()
        
        for event in events:
            all_actors.update(event.actors)
            if event.action:
                actions.append(event.action)
            objects.update(event.objects)
        
        merged.actors = sorted(list(all_actors))
        merged.objects = sorted(list(objects))
        
        # Combine actions
        if actions:
            # Use semicolon to separate multiple actions
            merged.action = ';'.join(actions[:3])  # Limit to 3 actions
        
        return merged
    
    def _generate_output(self) -> str:
        """Generate the final compressed output"""
        output = []
        
        # Generate entity tables
        if self.entities[EntityType.CHARACTER]:
            chars = ','.join(f"{e.index}:{self._abbreviate(e.name)}" 
                           for e in self.entities[EntityType.CHARACTER])
            output.append(f"@C={{{chars}}}")
        
        if self.entities[EntityType.LOCATION]:
            locs = ','.join(f"{e.index}:{self._abbreviate(e.name)}" 
                          for e in self.entities[EntityType.LOCATION])
            output.append(f"@L={{{locs}}}")
        
        if self.entities[EntityType.SPELL]:
            spells = ','.join(f"{e.index}:{self._abbreviate(e.name)}" 
                            for e in self.entities[EntityType.SPELL])
            output.append(f"@S={{{spells}}}")
        
        if self.entities[EntityType.ITEM]:
            items = ','.join(f"{self._abbreviate(e.name)}" 
                           for e in self.entities[EntityType.ITEM])
            output.append(f"@I={{{items}}}")
        
        if self.entities[EntityType.RELATIONSHIP]:
            for e in self.entities[EntityType.RELATIONSHIP]:
                if "relations" in e.attributes:
                    rels = ';'.join(e.attributes["relations"])
                    output.append(f"@R={{{rels}}}")
        
        # Generate event list
        output.append("\nEVT[")
        
        for i, event in enumerate(self.events, 1):
            event_str = f"{i}) "
            
            # Add actors
            if event.actors:
                if len(event.actors) == 1:
                    event_str += f"{event.actors[0]}"
                else:
                    event_str += f"({','.join(map(str, event.actors))})"
            
            # Add action
            if event.action:
                event_str += event.action
            
            # Add location
            if event.location:
                event_str += f"@{event.location}"
            
            # Add objects
            if event.objects:
                event_str += f" [{','.join(map(str, event.objects))}]"
            
            # Limit line length
            if len(event_str) > 80:
                event_str = event_str[:77] + "..."
            
            output.append(event_str)
        
        output.append("]")
        
        return '\n'.join(output)
    
    def _abbreviate(self, text: str) -> str:
        """Abbreviate text for compression"""
        # Remove spaces and common words
        words = text.split()
        
        # For multi-word names, use camelCase
        if len(words) > 1:
            return ''.join(w.capitalize() for w in words)
        
        # For single words, return as-is but capitalized
        return text.capitalize()
    
    def get_compression_stats(self, original_text: str) -> Dict[str, Any]:
        """Calculate compression statistics"""
        compressed = self.compress(original_text)
        
        original_size = len(original_text)
        compressed_size = len(compressed)
        
        return {
            "original_size": original_size,
            "compressed_size": compressed_size,
            "compression_ratio": (1 - compressed_size/original_size) * 100,
            "entities_found": sum(len(entities) for entities in self.entities.values()),
            "events_extracted": len(self.events),
            "characters": len(self.entities[EntityType.CHARACTER]),
            "locations": len(self.entities[EntityType.LOCATION]),
            "items": len(self.entities[EntityType.ITEM]),
            "spells": len(self.entities[EntityType.SPELL])
        }


def compress_narrative(text: str, use_ascii: bool = True) -> Tuple[str, Dict[str, Any]]:
    """Convenience function to compress narrative text
    
    Args:
        text: The narrative text to compress
        use_ascii: Use ASCII symbols for Windows compatibility
        
    Returns:
        Tuple of (compressed_text, statistics)
    """
    compressor = UltraCompressor(use_ascii=use_ascii)
    compressed = compressor.compress(text)
    stats = compressor.get_compression_stats(text)
    
    return compressed, stats


def batch_compress_conversations(conversations: List[Dict], use_ascii: bool = True) -> str:
    """Compress multiple conversation entries into a single narrative
    
    Args:
        conversations: List of conversation dictionaries with 'role' and 'content'
        use_ascii: Use ASCII symbols for Windows compatibility
        
    Returns:
        Ultra-compressed format
    """
    # Extract narrative content
    narrative_parts = []
    for msg in conversations:
        if msg.get('role') in ['user', 'assistant']:
            content = msg.get('content', '')
            # Skip system messages and metadata
            if not content.startswith('===') and not content.startswith('SYSTEM:'):
                narrative_parts.append(content)
    
    # Join into single narrative
    full_narrative = ' '.join(narrative_parts)
    
    # Compress
    compressed, stats = compress_narrative(full_narrative, use_ascii)
    
    print(f"Compression achieved: {stats['compression_ratio']:.1f}%")
    print(f"Original: {stats['original_size']} chars -> Compressed: {stats['compressed_size']} chars")
    
    return compressed


# Example usage and testing
if __name__ == "__main__":
    # Test with the sample text
    sample_text = """
    Beneath the somber skies that perpetually shrouded Marrow's Rest, the Black Lantern Hearth 
    flickered like a solitary beacon against the encroaching gloom. Here, the adventurers--Eirik, 
    known among close friends as Trouble Magnet for his uncanny knack for calamity, the lithe scout 
    Kira whose spirit flickered like the black flame of the lighthouse itself, the ever-watchful 
    Elen with her hawk's gaze, and the steady, unyielding Thane--began and returned repeatedly.
    
    They moved to Shroudwatch Garrison where they met Brother Lintar. The party traded for gear
    including armor, boots, two swords, a bow and a cloak. Kira received an agile leather set,
    Elen got precise archer equipment, and Thane received steady defender items. Thane defended
    Kira against Grimjaw's past threats. A pact was made between the village and the party.
    
    They returned to the Black Lantern Hearth. Cira served stew and ale. Bonds grew stronger.
    Kira breathed in relief, Elen smiled warmly, and Thane grinned. Later, Eirik and Kira made
    vows, kissed, and shared intimacy in a private chamber. Kira's laughter pushed back the shadows.
    Eirik assured her of safety.
    """
    
    print("Original Text Length:", len(sample_text))
    print("-" * 50)
    
    compressed, stats = compress_narrative(sample_text)
    
    print("\nCompressed Output:")
    print("-" * 50)
    print(compressed)
    print("-" * 50)
    
    print("\nCompression Statistics:")
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.1f}")
        else:
            print(f"  {key}: {value}")