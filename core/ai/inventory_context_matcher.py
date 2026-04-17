#!/usr/bin/env python3
"""
Inventory Context Matcher - Simple fuzzy matching
Indexes player's inventory and fuzzy matches against player text
"""

import re
from typing import List, Dict, Set, Tuple
from difflib import SequenceMatcher

class InventoryContextMatcher:
    def __init__(self, similarity_threshold: float = 0.6):
        self.similarity_threshold = similarity_threshold
        self.inventory = []

    def fuzzy_match(self, word1: str, word2: str) -> float:
        """Calculate similarity between two words"""
        return SequenceMatcher(None, word1.lower(), word2.lower()).ratio()

    def find_matches_in_text(self, text: str, inventory: List[Dict], context: str = 'general') -> List[Dict]:
        """Find inventory items mentioned in text using fuzzy matching"""
        text_lower = text.lower()
        text_words = re.findall(r'\b\w+\b', text_lower)

        matched_items = []

        for item in inventory:
            item_name = item.get('name', '').lower()
            item_words = re.findall(r'\b\w+\b', item_name)

            # Check if any word in text fuzzy matches any word in item name
            best_score = 0
            for text_word in text_words:
                for item_word in item_words:
                    score = self.fuzzy_match(text_word, item_word)
                    best_score = max(best_score, score)

                    # For compound words like "longsword", check substrings
                    if len(item_word) > 5:
                        # Check if text word matches end of item word (e.g., "sword" in "longsword")
                        if len(text_word) > 3:
                            for i in range(len(item_word) - len(text_word) + 1):
                                substring = item_word[i:i+len(text_word)]
                                sub_score = self.fuzzy_match(text_word, substring)
                                if sub_score > 0.75:
                                    best_score = max(best_score, sub_score)

            # If good enough match, include the item
            if best_score >= self.similarity_threshold:
                matched_items.append((item, best_score))

        # Sort by score and return items
        matched_items.sort(key=lambda x: x[1], reverse=True)
        return [item for item, score in matched_items]

    def format_item_description(self, item: Dict, context: str = 'general') -> str:
        """Format single item description based on context"""
        name = item.get('name', 'Unknown')
        parts = []

        # Add rarity if special
        if item.get('rarity', 'common') not in ['common', '']:
            parts.append(item['rarity'])

        # Combat context - show combat stats
        if context == 'combat':
            if item.get('damage'):
                parts.append(f"dmg:{item['damage']}")
            if item.get('attack_bonus'):
                parts.append(f"+{item['attack_bonus']}")
            if item.get('range'):
                parts.append(f"rng:{item['range']}")
            if item.get('ac_bonus'):
                parts.append(f"AC+{item['ac_bonus']}")
        else:
            # General context - show effects/description
            if item.get('effect'):
                parts.append(item['effect'][:50])
            elif item.get('description'):
                parts.append(item['description'][:50])

        if parts:
            return f"[{name}: {'; '.join(parts)}]"
        return f"[{name}]"

    def process_player_text(self, text: str, inventory: List[Dict], context: str = 'general') -> str:
        """Main function: find fuzzy matches and inject descriptions"""
        matched_items = self.find_matches_in_text(text, inventory, context)

        if matched_items:
            descriptions = []
            for item in matched_items:
                descriptions.append(self.format_item_description(item, context))

            return f"{text}\n{' '.join(descriptions)}"

        return text


def test_fuzzy_matching():
    """Test fuzzy matching with typos and variations"""

    inventory = [
        {"name": "Longsword +1", "type": "weapon", "damage": "1d8+1", "attack_bonus": 1, "rarity": "uncommon"},
        {"name": "Shortsword", "type": "weapon", "damage": "1d6"},
        {"name": "Greatsword", "type": "weapon", "damage": "2d6", "properties": ["two-handed"]},
        {"name": "Heavy Crossbow", "type": "weapon/ranged", "damage": "1d10", "range": "100/400"},
        {"name": "Shield", "type": "armor", "ac_bonus": 2},
        {"name": "Potion of Healing", "type": "consumable", "effect": "Restores 2d4+2 HP"},
        {"name": "Commander's Horn", "type": "wondrous", "description": "Summons allied forces", "rarity": "rare"},
        {"name": "Torch", "type": "gear", "description": "Provides light for 1 hour"},
        {"name": "Ancient Map", "type": "item", "description": "Shows the hidden temple location"},
    ]

    matcher = InventoryContextMatcher(similarity_threshold=0.65)  # Allow more typos

    test_cases = [
        # Normal cases
        ("I draw my sword", 'combat'),
        ("I swing my longsword", 'combat'),

        # Typos
        ("I swing my swrod", 'combat'),  # typo: swrod -> sword
        ("Let me use the sheild", 'combat'),  # typo: sheild -> shield
        ("I drink the heliang potion", 'general'),  # typo: heliang -> healing

        # Partial matches
        ("I fire the crossbow", 'combat'),
        ("I blow the horn", 'general'),
        ("Let me check the map", 'general'),
        ("I light the torch", 'general'),

        # Multiple matches
        ("I'll use my sword and shield", 'combat'),
    ]

    print("FUZZY INVENTORY MATCHING TEST")
    print("=" * 60)

    for text, context in test_cases:
        result = matcher.process_player_text(text, inventory, context)
        print(f"\nPlayer: {text}")
        if result != text:
            injected = result.replace(text + "\n", "")
            print(f"Matched: {injected}")
        else:
            print("Matched: (none)")


if __name__ == "__main__":
    test_fuzzy_matching()