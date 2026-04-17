#!/usr/bin/env python3
"""
Enhanced Action Parser for Companion Memory Core
Fixes parsing artifacts and adds climactic moment detection.
"""

import re
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field

@dataclass
class ParsedAction:
    """Represents a parsed action with emotional impact"""
    pattern: str
    emotional_impact: Dict[str, float]
    context: str
    npc_name: str
    action_type: str  # 'positive' or 'negative'
    attribution: str = "player"  # 'player', 'external', 'mutual'
    context_tags: List[str] = field(default_factory=list)

    def get_readable_action(self) -> str:
        """Convert pattern to readable action description"""
        # Remove regex syntax for clean output
        clean_pattern = self.pattern

        # Remove regex special chars
        clean_pattern = clean_pattern.replace(r'\s+', ' ')
        clean_pattern = clean_pattern.replace(r'\b', '')
        clean_pattern = clean_pattern.replace(r'(?:', '')
        clean_pattern = clean_pattern.replace(r')?', '')
        clean_pattern = clean_pattern.replace(r'(?i)', '')
        clean_pattern = clean_pattern.replace('|', ' or ')

        # Specific readable mappings
        readable_map = {
            r'cast(?:ing)?\s+cure\s+wounds': 'cast healing magic',
            r'cast(?:ing)?\s+sacred\s+flame': 'used divine power',
            r'offered?\s+reassurance': 'offered reassurance',
            r'tended?\s+(?:to\s+)?wounds?': 'tended wounds',
            r'passionate\s+kiss': 'shared passionate kiss',
            r'shared?\s+(?:a\s+)?kiss': 'shared kiss',
            r'(?:embrace|embraced)': 'shared embrace',
            r'intimate\s+moment': 'shared intimate moment',
            r'first\s+kiss': 'shared first kiss',
            r'(?:took|taking)\s+(?:the\s+)?lead': 'took the lead',
            r'keen\s+eyes?\s+(?:scanning|surveying|watching)': 'kept keen watch',
            r'stood?\s+guard': 'stood guard',
            r'protected?\s+(?:from|against)': 'provided protection',
            r'fought\s+(?:alongside|together)': 'fought together',
            r'bond\s+(?:deepened|strengthened)': 'deepened bond',
            r'shared?\s+(?:tales?|stories|experiences?)': 'shared experiences',
            r'camaraderie': 'shared camaraderie',
            r'(?:unity|unified|united)': 'unified united',
            r'renewed?\s+hope': 'renewed hope',
            r'shared?\s+(?:purpose|resolve|determination)': 'shared determination',
            r'laughed?\s+together': 'laughed together',
            r'(?:betrayed|betrayal)': 'experienced betrayal',
            r'deceived?\s+(?:ally|friend)': 'was deceived',
            r'(?:abandoned|left\s+behind)': 'faced abandonment',
            r'showed?\s+cruelty': 'showed cruelty',
            r'(?:enslaved|captive|prisoner)': 'held captive',
            r'forced?\s+(?:to\s+)?dance': 'forced to perform',
            r'victory\s+over\s+(?:the\s+)?(?:final|main)\s+(?:boss|enemy|villain)': 'achieved final victory',
            r'defeated?\s+malarok': 'defeated Malarok',
            r'kiss(?:ed)?\s+(?:amid|after|during)\s+(?:battle|victory|danger)': 'kiss after battle',
            r'coordinated?\s+(?:attack|assault|strike)': 'coordinated attack',
            r'perfect\s+(?:teamwork|coordination|synergy)': 'perfect teamwork',
            r'saved?\s+(?:my\s+)?life': 'saved life',
            r'risked?\s+(?:everything|life|all)': 'risked everything',
            r'last\s+stand': 'made last stand',
            r'heroic\s+(?:moment|act|deed)': 'heroic moment',
            r'confessed?\s+(?:love|feelings)': 'confessed feelings',
            r'(?:declared|declaration)\s+(?:of\s+)?love': 'declared love',
            r'vulnerable\s+moment': 'shared vulnerability',
            r'admitted?\s+(?:weakness|vulnerability|fear)': 'admitted vulnerability',
            r'(?:revealed|revealing)\s+(?:past|trauma|secret)': 'revealed past trauma',
            r'moment\s+of\s+(?:triumph|victory)': 'moment of triumph',
            r'(?:celebrated|celebration)': 'celebrated victory',
            r'(?:wedding|married|marriage)': 'married',
            r'(?:proposal|proposed)': 'marriage proposal',
            r'(?:vow|vowed|promised)': 'made vows',
            r'resolve\s+determination': 'showed determination',
            r'stories\s+experiences': 'shared stories',
            r'provided\s+comfort': 'provided comfort',
            r'banter\s+exchange': 'playful banter'
        }

        # Return mapped version if exists
        for pattern, readable in readable_map.items():
            if pattern in self.pattern:
                return readable

        # Clean up raw pattern as fallback
        result = clean_pattern.strip()

        # Remove word boundary markers and clean up
        result = re.sub(r'[\\()?\[\]{}+*]', '', result)
        result = re.sub(r'\s+', ' ', result)

        # Ensure minimum length (fix "s hope" issue)
        if len(result) < 4:
            return None

        return result.strip()

class EnhancedActionParser:
    """Enhanced parser with better pattern matching and attribution"""

    def __init__(self):
        self.positive_patterns = self._compile_positive_patterns()
        self.negative_patterns = self._compile_negative_patterns()
        self.climactic_patterns = self._compile_climactic_patterns()
        # NPCs should be provided dynamically from party tracker
        self.companion_npcs = []

    def _compile_positive_patterns(self) -> Dict[str, Dict]:
        """Compile positive action patterns with metadata"""
        patterns = {}

        # Healing/Support (with word boundaries)
        patterns[r'\bcast(?:ing)?\s+cure\s+wounds\b'] = {
            'impact': {'trust': 0.4, 'intimacy': 0.2},
            'tags': ['healing', 'support']
        }
        patterns[r'\bcast(?:ing)?\s+(?:a\s+)?healing\s+spell\b'] = {
            'impact': {'trust': 0.3, 'intimacy': 0.1},
            'tags': ['healing', 'support']
        }
        patterns[r'\boffered?\s+reassurance\b'] = {
            'impact': {'trust': 0.2, 'intimacy': 0.1},
            'tags': ['emotional_support']
        }
        patterns[r'\btended?\s+(?:to\s+)?wounds?\b'] = {
            'impact': {'trust': 0.3, 'intimacy': 0.2},
            'tags': ['healing', 'care']
        }
        patterns[r'\bprovided\s+comfort\b'] = {
            'impact': {'intimacy': 0.3, 'trust': 0.1},
            'tags': ['emotional_support']
        }

        # Romance (enhanced)
        patterns[r'\bpassionate\s+kiss\b'] = {
            'impact': {'intimacy': 0.7, 'trust': 0.3, 'respect': 0.1},
            'tags': ['romantic', 'intimate']
        }
        patterns[r'\bshared?\s+(?:a\s+)?kiss\b'] = {
            'impact': {'intimacy': 0.5, 'trust': 0.2},
            'tags': ['romantic']
        }
        patterns[r'\b(?:embrace|embraced)\b'] = {
            'impact': {'intimacy': 0.4, 'trust': 0.1},
            'tags': ['romantic', 'comfort']
        }
        patterns[r'\bintimate\s+moment\b'] = {
            'impact': {'intimacy': 0.6, 'trust': 0.3},
            'tags': ['romantic', 'intimate']
        }
        patterns[r'\bfirst\s+kiss\b'] = {
            'impact': {'intimacy': 0.8, 'trust': 0.4},
            'tags': ['romantic', 'milestone']
        }
        patterns[r'\bconfessed?\s+(?:love|feelings)\b'] = {
            'impact': {'intimacy': 0.9, 'trust': 0.5, 'respect': 0.2},
            'tags': ['romantic', 'milestone', 'vulnerable']
        }

        # Combat Excellence
        patterns[r'\bcoordinated?\s+(?:attack|assault|strike)\b'] = {
            'impact': {'trust': 0.4, 'respect': 0.3, 'power': 0.2},
            'tags': ['combat', 'teamwork']
        }
        patterns[r'\bperfect\s+(?:teamwork|coordination|synergy)\b'] = {
            'impact': {'trust': 0.5, 'respect': 0.4, 'power': 0.2},
            'tags': ['combat', 'teamwork', 'excellence']
        }
        patterns[r'\bsaved?\s+(?:my\s+)?life\b'] = {
            'impact': {'trust': 0.7, 'respect': 0.5, 'intimacy': 0.3},
            'tags': ['heroic', 'life_debt']
        }
        patterns[r'\brisked?\s+(?:everything|life|all)\b'] = {
            'impact': {'trust': 0.6, 'respect': 0.6, 'intimacy': 0.2},
            'tags': ['heroic', 'sacrifice']
        }
        patterns[r'\blast\s+stand\b'] = {
            'impact': {'respect': 0.5, 'trust': 0.4, 'power': 0.2},
            'tags': ['heroic', 'combat', 'desperate']
        }

        # Trust Building
        patterns[r'\badmitted?\s+(?:weakness|vulnerability|fear)\b'] = {
            'impact': {'intimacy': 0.5, 'trust': 0.4},
            'tags': ['vulnerable', 'trust_building']
        }
        patterns[r'\b(?:revealed|revealing)\s+(?:past|trauma|secret)\b'] = {
            'impact': {'intimacy': 0.6, 'trust': 0.5},
            'tags': ['vulnerable', 'backstory', 'trust_building']
        }
        patterns[r'\bshared?\s+(?:tales?|stories|experiences?)\b'] = {
            'impact': {'intimacy': 0.3, 'trust': 0.2},
            'tags': ['bonding', 'backstory']
        }
        patterns[r'\bdeepened\s+bond\b'] = {
            'impact': {'intimacy': 0.4, 'trust': 0.3},
            'tags': ['bonding', 'relationship_growth']
        }

        # Victory Moments
        patterns[r'\bvictory\s+over\s+(?:the\s+)?(?:final|main)\s+(?:boss|enemy|villain)\b'] = {
            'impact': {'trust': 0.5, 'respect': 0.5, 'power': 0.3},
            'tags': ['victory', 'climactic', 'milestone']
        }
        patterns[r'\bdefeated?\s+malarok\b'] = {
            'impact': {'trust': 0.6, 'respect': 0.6, 'power': 0.4},
            'tags': ['victory', 'boss_defeat', 'climactic']
        }
        patterns[r'\bmoment\s+of\s+(?:triumph|victory)\b'] = {
            'impact': {'respect': 0.4, 'trust': 0.3, 'power': 0.2},
            'tags': ['victory', 'celebration']
        }

        # Social bonds (cleaned up)
        patterns[r'\b(?:camaraderie|fellowship)\b'] = {
            'impact': {'trust': 0.2, 'intimacy': 0.2},
            'tags': ['bonding', 'friendship']
        }
        patterns[r'\b(?:unity|unified|united)\b'] = {
            'impact': {'trust': 0.2, 'respect': 0.1},
            'tags': ['teamwork', 'bonding']
        }
        patterns[r'\brenewed?\s+hope\b'] = {
            'impact': {'trust': 0.2, 'respect': 0.1},
            'tags': ['morale', 'inspiration']
        }
        patterns[r'\blaughed?\s+together\b'] = {
            'impact': {'intimacy': 0.2, 'trust': 0.1},
            'tags': ['bonding', 'humor', 'relaxation']
        }
        patterns[r'\bbanter\s+exchange\b'] = {
            'impact': {'intimacy': 0.2, 'trust': 0.1},
            'tags': ['humor', 'friendship']
        }

        # Clean up compound patterns
        patterns[r'\bresolve\s+determination\b'] = {
            'impact': {'respect': 0.2, 'trust': 0.2},
            'tags': ['determination', 'morale']
        }
        patterns[r'\bstories\s+experiences\b'] = {
            'impact': {'intimacy': 0.3, 'trust': 0.2},
            'tags': ['bonding', 'backstory']
        }

        return patterns

    def _compile_negative_patterns(self) -> Dict[str, Dict]:
        """Compile negative action patterns with attribution"""
        patterns = {}

        # Betrayal (usually external)
        patterns[r'\b(?:betrayed|betrayal)\b'] = {
            'impact': {'trust': -0.7, 'respect': -0.3, 'fear': 0.2},
            'tags': ['betrayal', 'trust_broken'],
            'attribution': 'contextual'  # Need to check who betrayed whom
        }

        # Deception (check attribution)
        patterns[r'\bdeceived?\s+(?:ally|friend)\b'] = {
            'impact': {'trust': -0.5, 'respect': -0.2},
            'tags': ['deception'],
            'attribution': 'contextual'
        }

        # Abandonment
        patterns[r'\b(?:abandoned|left\s+behind)\b'] = {
            'impact': {'trust': -0.4, 'fear': 0.3},
            'tags': ['abandonment'],
            'attribution': 'contextual'
        }

        # Cruelty (usually external - enemies)
        patterns[r'\bshowed?\s+cruelty\b'] = {
            'impact': {'respect': -0.4, 'fear': 0.4, 'trust': -0.2},
            'tags': ['cruelty', 'trauma'],
            'attribution': 'external'  # Usually enemies
        }

        # Captivity (always external)
        patterns[r'\b(?:enslaved|captive|prisoner)\b'] = {
            'impact': {'fear': 0.6, 'trust': -0.3, 'power': -0.4},
            'tags': ['trauma', 'captivity'],
            'attribution': 'external'
        }

        patterns[r'\bforced?\s+(?:to\s+)?(?:dance|perform)\b'] = {
            'impact': {'fear': 0.5, 'respect': -0.5, 'intimacy': 0.3},
            'tags': ['trauma', 'humiliation', 'captivity'],
            'attribution': 'external'
        }

        # Combat failures
        patterns[r'\b(?:fled|retreated|ran\s+away)\b'] = {
            'impact': {'respect': -0.2, 'power': -0.2},
            'tags': ['retreat', 'tactical'],
            'attribution': 'mutual'
        }

        patterns[r'\b(?:failed|failure)\b'] = {
            'impact': {'respect': -0.1, 'trust': -0.1},
            'tags': ['failure'],
            'attribution': 'mutual'
        }

        return patterns

    def _compile_climactic_patterns(self) -> Dict[str, Dict]:
        """Special patterns for climactic/pivotal moments"""
        patterns = {}

        # Major victories
        patterns[r'\bvictory\s+after\s+final\s+battle\b'] = {
            'impact': {'trust': 0.7, 'respect': 0.6, 'power': 0.4, 'intimacy': 0.3},
            'tags': ['climactic', 'victory', 'finale']
        }

        patterns[r'\bkiss(?:ed)?\s+(?:amid|after|during)\s+(?:battle|victory|danger)\b'] = {
            'impact': {'intimacy': 0.8, 'trust': 0.4, 'respect': 0.2},
            'tags': ['climactic', 'romantic', 'dramatic']
        }

        patterns[r'\btriumphed?\s+(?:against|over)\s+(?:great|terrible|impossible)\s+odds\b'] = {
            'impact': {'respect': 0.7, 'trust': 0.5, 'power': 0.3},
            'tags': ['climactic', 'victory', 'heroic']
        }

        patterns[r'\bembrace(?:d)?\s+(?:in|after|during)\s+(?:triumph|relief|joy|victory)\b'] = {
            'impact': {'intimacy': 0.6, 'trust': 0.3},
            'tags': ['climactic', 'romantic', 'celebration']
        }

        patterns[r'\b(?:dawn|sunrise|sunset)\s+(?:kiss|embrace|moment)\b'] = {
            'impact': {'intimacy': 0.7, 'trust': 0.3},
            'tags': ['climactic', 'romantic', 'cinematic']
        }

        return patterns

    def parse_entry(self, text: str, npc_name: str) -> List[ParsedAction]:
        """Extract actions with improved parsing"""
        actions = []

        # Check if NPC is mentioned
        if not self._is_npc_mentioned(text, npc_name):
            return actions

        # Check climactic patterns first (highest priority)
        actions.extend(self._find_enhanced_patterns(
            text, npc_name, self.climactic_patterns, 'climactic'
        ))

        # Check positive patterns
        actions.extend(self._find_enhanced_patterns(
            text, npc_name, self.positive_patterns, 'positive'
        ))

        # Check negative patterns with attribution
        actions.extend(self._find_enhanced_patterns(
            text, npc_name, self.negative_patterns, 'negative'
        ))

        # Filter out artifacts (actions with readable form < 4 chars)
        valid_actions = []
        for action in actions:
            readable = action.get_readable_action()
            if readable and len(readable) >= 4:
                valid_actions.append(action)

        return valid_actions

    def _is_npc_mentioned(self, text: str, npc_name: str) -> bool:
        """Check if NPC is mentioned with word boundaries"""
        return bool(re.search(rf'\b{npc_name}\b', text, re.IGNORECASE))

    def _find_enhanced_patterns(self, text: str, npc_name: str,
                                patterns: Dict, action_type: str) -> List[ParsedAction]:
        """Find patterns with enhanced context and attribution"""
        found_actions = []
        seen_patterns = set()  # Prevent duplicates

        # Find all mentions of the NPC
        npc_mentions = list(re.finditer(rf'\b{npc_name}\b', text, re.IGNORECASE))

        for pattern_regex, pattern_data in patterns.items():
            # Skip if already found this pattern
            if pattern_regex in seen_patterns:
                continue

            # Check if pattern exists in text
            matches = list(re.finditer(pattern_regex, text, re.IGNORECASE))
            if not matches:
                continue

            # Check proximity to NPC mentions
            for match in matches:
                for mention in npc_mentions:
                    # Check if within reasonable proximity (200 chars)
                    distance = abs(match.start() - mention.start())
                    if distance <= 200:
                        # Extract context
                        context_start = max(0, match.start() - 100)
                        context_end = min(len(text), match.end() + 100)
                        context = text[context_start:context_end].strip()

                        # Determine attribution for negative actions
                        attribution = pattern_data.get('attribution', 'player')
                        if attribution == 'contextual':
                            attribution = self._determine_attribution(context, npc_name)

                        action = ParsedAction(
                            pattern=pattern_regex,
                            emotional_impact=pattern_data['impact'],
                            context=context,
                            npc_name=npc_name,
                            action_type=action_type,
                            attribution=attribution,
                            context_tags=pattern_data.get('tags', [])
                        )

                        found_actions.append(action)
                        seen_patterns.add(pattern_regex)
                        break  # Only count each pattern once

                if pattern_regex in seen_patterns:
                    break

        return found_actions

    def _determine_attribution(self, context: str, npc_name: str) -> str:
        """Determine who is responsible for negative action"""
        context_lower = context.lower()
        npc_lower = npc_name.lower()

        # Check for enemy names
        enemy_indicators = ['grimjaw', 'bandit', 'goblin', 'cultist', 'malarok',
                           'enemy', 'foe', 'attacker', 'captor', 'slaver']
        for enemy in enemy_indicators:
            if enemy in context_lower:
                return 'external'

        # Check for player indicators (generic, not hardcoded to specific name)
        # The player's actual name should be passed in if needed
        player_indicators = ['you ', 'your ', 'the party', 'we ', 'our ']
        for indicator in player_indicators:
            if indicator in context_lower:
                # Likely player action toward NPC
                return 'player'

        # If neither enemy nor clear player action, it's mutual
        # Note: Specific player name can be added to player_indicators if known

        # Default to mutual if unclear
        return 'mutual'

    def extract_all_npcs(self, text: str) -> Dict[str, List[ParsedAction]]:
        """Extract actions for all NPCs with enhanced parsing"""
        results = {}

        for npc_name in self.companion_npcs:
            actions = self.parse_entry(text, npc_name)
            if actions:
                results[npc_name] = actions

        return results