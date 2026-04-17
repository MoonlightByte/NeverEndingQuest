#!/usr/bin/env python3
"""
Inventory Context Matcher v2 - Improved fuzzy matching with reduced false positives
Indexes player's inventory and intelligently matches against player text
"""

import re
from typing import List, Dict, Tuple, Set
from difflib import SequenceMatcher

class InventoryContextMatcherV2:
    def __init__(self, similarity_threshold: float = 0.65, max_matches: int = 5):
        self.similarity_threshold = similarity_threshold
        self.max_matches = max_matches
        
        # Common words to ignore in matching - more selective list
        self.stop_words = {
            'i', 'me', 'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at',
            'to', 'for', 'of', 'by', 'from', 'as', 'is', 'was', 'are', 'were',
            'been', 'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'can', 'cant', 'lets', 'let',
            'well', 'done', 'yes', 'no', 'ok', 'okay', 'sure', 'yeah', 'nope',
            'this', 'that', 'these', 'those', 'there', 'here', 'where', 'when',
            'who', 'what', 'which', 'why', 'how', 'all', 'any', 'some', 'very',
            'too', 'also', 'just', 'only', 'still', 'now', 'then', 'out', 'up',
            'down', 'into', 'over', 'under', 'again', 'after', 'before', 'team'
        }
        
        # Combat-related keywords for context prioritization
        self.combat_keywords = {
            'attack', 'strike', 'hit', 'swing', 'fire', 'shoot', 'block', 'defend',
            'damage', 'hurt', 'wound', 'fight', 'combat', 'battle', 'guard'
        }
        
        # Item type priorities for different contexts
        self.context_priorities = {
            'combat': ['weapon', 'armor', 'shield', 'consumable'],
            'general': ['equipment', 'consumable', 'misc', 'tool']
        }

    def clean_word(self, word: str) -> str:
        """Clean and normalize a word for matching"""
        # Remove non-alphanumeric characters and lowercase
        return re.sub(r'[^a-z0-9]', '', word.lower())

    def fuzzy_match(self, word1: str, word2: str) -> float:
        """Calculate similarity between two words"""
        return SequenceMatcher(None, word1.lower(), word2.lower()).ratio()

    def calculate_word_importance(self, word: str) -> float:
        """Calculate importance of a word based on various factors"""
        clean = self.clean_word(word)
        
        # Skip stop words entirely
        if clean in self.stop_words:
            return 0.0
        
        # Short words are less important (but not ignored if not stop words)
        if len(clean) <= 2:
            return 0.3
        elif len(clean) <= 3:
            return 0.5
        
        # Longer, specific words are more important
        base_importance = min(1.0, 0.6 + (len(clean) - 4) * 0.1)
        
        # Combat words get a boost in combat context
        if clean in self.combat_keywords:
            base_importance *= 1.2
            
        return min(1.0, base_importance)

    def match_words(self, text_word: str, item_word: str) -> Tuple[float, str]:
        """
        Match two words and return score and match type
        Returns: (score, match_type)
        """
        text_clean = self.clean_word(text_word)
        item_clean = self.clean_word(item_word)
        
        # Exact match
        if text_clean == item_clean:
            return (1.0, 'exact')
        
        # Check for plurals (simple stemming)
        if text_clean.endswith('s') and text_clean[:-1] == item_clean:
            return (0.95, 'plural')
        if item_clean.endswith('s') and item_clean[:-1] == text_clean:
            return (0.95, 'plural')
        
        # Fuzzy match
        fuzzy_score = self.fuzzy_match(text_clean, item_clean)
        if fuzzy_score >= self.similarity_threshold:
            return (fuzzy_score, 'fuzzy')
        
        # Substring match for compound words (e.g., "sword" in "longsword")
        if len(text_clean) >= 4 and len(item_clean) > len(text_clean):
            if text_clean in item_clean:
                # Position-based scoring: earlier matches score higher
                position = item_clean.find(text_clean)
                position_penalty = position / len(item_clean) * 0.2
                return (0.8 - position_penalty, 'substring')
        
        return (0.0, 'none')

    def calculate_item_score(self, text: str, item: Dict, context: str) -> float:
        """Calculate overall matching score for an item"""
        text_words = re.findall(r'\b\w+\b', text.lower())
        item_name = item.get('name', '').lower()
        item_words = re.findall(r'\b\w+\b', item_name)
        
        # Keep action words like "use", "check", "take" but filter true stop words
        significant_text_words = [
            (word, self.calculate_word_importance(word))
            for word in text_words
            if self.calculate_word_importance(word) > 0.2  # Allow low-importance words
        ]
        
        if not significant_text_words:
            return 0.0
        
        # Track best matches for each text word
        word_scores = []
        match_details = []
        
        for text_word, text_importance in significant_text_words:
            best_score = 0.0
            best_match_type = 'none'
            
            for item_word in item_words:
                score, match_type = self.match_words(text_word, item_word)
                if score > best_score:
                    best_score = score
                    best_match_type = match_type
            
            # Weight the score by word importance
            weighted_score = best_score * text_importance
            if weighted_score > 0:
                word_scores.append(weighted_score)
                match_details.append((text_word, best_match_type, weighted_score))
        
        if not word_scores:
            return 0.0
        
        # Calculate final score
        # Use best match if at least one good match exists
        if word_scores:
            # Use max score if we have at least one strong match
            base_score = max(word_scores) if max(word_scores) > 0.7 else sum(word_scores) / len(word_scores)
            match_count_bonus = min(0.2, len(word_scores) * 0.05)
        else:
            base_score = 0.0
            match_count_bonus = 0.0
        
        # Context-based boost
        context_boost = 0.0
        item_type = item.get('type', '').lower()
        if context == 'combat' and item_type in ['weapon', 'armor', 'shield']:
            context_boost = 0.1
        elif context == 'general' and item_type in ['equipment', 'consumable', 'tool']:
            context_boost = 0.05
        
        total_score = base_score + match_count_bonus + context_boost
        
        # Store match details for debugging (optional)
        item['_match_details'] = match_details
        item['_match_score'] = total_score
        
        return min(1.0, total_score)

    def find_matches_in_text(self, text: str, inventory: List[Dict], context: str = 'general') -> List[Dict]:
        """Find inventory items mentioned in text using improved matching"""
        matched_items = []
        
        for item in inventory:
            score = self.calculate_item_score(text, item, context)
            
            # Only include items with significant matches
            if score >= self.similarity_threshold:
                matched_items.append((item.copy(), score))
        
        # Sort by score and limit to max_matches
        matched_items.sort(key=lambda x: x[1], reverse=True)
        
        # Return only the top matches
        return [item for item, score in matched_items[:self.max_matches]]

    def format_item_description(self, item: Dict, context: str = 'general') -> str:
        """Format single item description based on context - no truncation"""
        name = item.get('name', 'Unknown')
        parts = []
        
        # Add rarity if special
        rarity = item.get('rarity', 'common')
        if rarity not in ['common', '']:
            parts.append(rarity)
        
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
            # Still include effect/description for context
            if item.get('effect'):
                parts.append(item['effect'])
            elif item.get('description'):
                # Include full description for AI context
                parts.append(item['description'])
        else:
            # General context - show effects/description
            if item.get('effect'):
                parts.append(item['effect'])
            elif item.get('description'):
                # Include full description for AI context
                parts.append(item['description'])
        
        if parts:
            return f"[{name}: {'; '.join(parts)}]"
        return f"[{name}]"

    def process_player_text(self, text: str, inventory: List[Dict], context: str = 'general') -> str:
        """Main function: find matches and inject descriptions"""
        matched_items = self.find_matches_in_text(text, inventory, context)
        
        if matched_items:
            descriptions = []
            for item in matched_items:
                # Clean up debug fields before formatting
                item.pop('_match_details', None)
                item.pop('_match_score', None)
                
                # Format: "ItemName - Description with stats"
                name = item.get('name', 'Unknown')
                parts = []
                
                # Include weapon combat stats if available
                if item.get('attackBonus') is not None or item.get('damageDice'):
                    combat_parts = []
                    if item.get('attackBonus') is not None:
                        combat_parts.append(f"+{item['attackBonus']} to hit")
                    if item.get('damageDice'):
                        damage_str = item['damageDice']
                        if item.get('damageBonus'):
                            damage_str += f"+{item['damageBonus']}"
                        if item.get('damageType'):
                            damage_str += f" {item['damageType']}"
                        combat_parts.append(damage_str)
                    if combat_parts:
                        parts.append(', '.join(combat_parts))
                
                # Include armor stats if available
                if item.get('ac_base'):
                    ac_str = f"AC {item['ac_base']}"
                    if item.get('dex_limit') is not None:
                        ac_str += f" + Dex (max {item['dex_limit']})"
                    parts.append(ac_str)
                if item.get('ac_bonus') and item.get('ac_bonus') != 0:
                    parts.append(f"AC +{item['ac_bonus']}")
                
                # Include effect or description
                if item.get('effect'):
                    parts.append(item['effect'])
                elif item.get('description'):
                    parts.append(item['description'])
                
                # Add equipped status if relevant
                if item.get('equipped') is not None:
                    if item.get('equipped'):
                        parts.append('[EQUIPPED]')
                    else:
                        parts.append('[NOT EQUIPPED]')
                
                if parts:
                    descriptions.append(f"{name} - {'; '.join(parts)}")
                else:
                    descriptions.append(name)
            
            # Use the [Inventory Context: ...] format
            return f"{text}\n[Inventory Context: {'; '.join(descriptions)}]"
        
        return text


def test_improved_matching():
    """Test improved fuzzy matching with reduced false positives"""
    
    inventory = [
        {"name": "Longsword +1", "type": "weapon", "damage": "1d8+1", "attack_bonus": 1, "rarity": "uncommon"},
        {"name": "Shortsword", "type": "weapon", "damage": "1d6"},
        {"name": "Shield", "type": "armor", "ac_bonus": 2},
        {"name": "Heavy Crossbow", "type": "weapon", "damage": "1d10", "range": "100/400"},
        {"name": "Potion of Healing", "type": "consumable", "effect": "Restores 2d4+2 HP"},
        {"name": "Holy Symbol", "type": "equipment", "description": "A blessed symbol providing divine focus"},
        {"name": "Rope", "type": "equipment", "description": "50 feet of hempen rope"},
        {"name": "Lantern", "type": "equipment", "description": "Casts bright light in 30-foot radius"},
        {"name": "Iron Key", "type": "misc", "description": "A heavy iron key with unknown purpose"},
        {"name": "Map", "type": "equipment", "description": "A detailed map of the local region"},
    ]
    
    matcher = InventoryContextMatcherV2(similarity_threshold=0.7, max_matches=5)
    
    test_cases = [
        # Should have minimal/no matches
        ("Well done!", 'general'),
        ("Yes, lets check the room", 'general'),
        
        # Should match specific items
        ("I swing my sword", 'combat'),
        ("I fire the crossbow", 'combat'),
        ("Use the rope to climb", 'general'),
        ("Light the lantern", 'general'),
        ("Check the map", 'general'),
        ("Drink a healing potion", 'general'),
        
        # Typos should still work
        ("I use my sheild", 'combat'),
        ("Fire the crosbow", 'combat'),
        ("Drink the heliang potion", 'general'),
        
        # Multiple items
        ("I use my sword and shield", 'combat'),
    ]
    
    print("IMPROVED INVENTORY MATCHING TEST (v2)")
    print("=" * 60)
    print(f"Max matches: {matcher.max_matches}")
    print(f"Similarity threshold: {matcher.similarity_threshold}")
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
    test_improved_matching()