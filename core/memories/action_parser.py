#!/usr/bin/env python3
"""
Action Parser for Companion Memory Core
Extracts emotionally significant actions from journal entries.
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# Action patterns that trigger emotional changes
# Based on actual journal content analysis
ACTION_PATTERNS = {
    # Healing/helping actions
    r'cast(?:ing)?\s+cure\s+wounds': {'trust': 0.4, 'intimacy': 0.2},
    r'cast(?:ing)?\s+(?:a\s+)?healing\s+spell': {'trust': 0.3, 'intimacy': 0.1},
    r'offered?\s+reassurance': {'trust': 0.2, 'intimacy': 0.1},
    r'offered?\s+(?:cautious\s+)?support': {'trust': 0.2, 'respect': 0.1},
    r'offered?\s+counsel': {'trust': 0.2, 'respect': 0.2},
    r'expressed?\s+(?:concern|worry)': {'intimacy': 0.2, 'trust': 0.1},
    r'tended?\s+(?:to\s+)?wounds?': {'trust': 0.3, 'intimacy': 0.2},
    r'comforted': {'intimacy': 0.3, 'trust': 0.1},
    
    # Combat cooperation
    r'cast(?:ing)?\s+sacred\s+flame': {'trust': 0.2, 'respect': 0.2, 'power': 0.1},
    r'(?:took|taking)\s+(?:the\s+)?lead': {'power': 0.2, 'respect': 0.1},
    r'(?:took|assumed)\s+point': {'power': 0.2, 'respect': 0.1},
    r'keen\s+eyes?\s+(?:scanning|surveying|watching)': {'trust': 0.1, 'respect': 0.1},
    r'kept?\s+watch': {'trust': 0.2, 'respect': 0.1},
    r'stood?\s+guard': {'trust': 0.2, 'respect': 0.1},
    r'protected?\s+(?:from|against)': {'trust': 0.5, 'respect': 0.3},
    r'defended': {'trust': 0.3, 'respect': 0.2},
    r'stood\s+(?:between|against)': {'trust': 0.4, 'respect': 0.3},
    r'fought\s+(?:alongside|together)': {'trust': 0.3, 'respect': 0.2},
    
    # Positive social bonds
    r'bond\s+(?:deepened|strengthened)': {'intimacy': 0.2, 'trust': 0.2},
    r'shared?\s+(?:tales?|stories|experiences?)': {'intimacy': 0.3, 'trust': 0.1},
    r'(?:built|earned|won)\s+trust': {'trust': 0.3, 'respect': 0.1},
    r'camaraderie': {'trust': 0.2, 'intimacy': 0.2},
    r'(?:unity|unified|united)': {'trust': 0.2, 'respect': 0.1},
    r'shared?\s+(?:purpose|resolve|determination)': {'trust': 0.2, 'respect': 0.2},
    r'renewed?\s+hope': {'trust': 0.2, 'respect': 0.1},
    r'shared?\s+(?:a\s+)?moments?': {'intimacy': 0.2, 'trust': 0.1},
    r'laughed?\s+together': {'intimacy': 0.2, 'trust': 0.1},
    
    # Resource sharing
    r'(?:gave|offered|provided)\s+(?:supplies|equipment|tools?)': {'trust': 0.2, 'respect': 0.1},
    r'refused?\s+(?:any\s+)?payment': {'respect': 0.3, 'trust': 0.2},
    r'(?:generous|generosity)': {'respect': 0.2, 'trust': 0.2},
    r'(?:shared|split)\s+(?:treasure|loot|rewards?)': {'trust': 0.2, 'respect': 0.2},
    r'(?:gave|offered)\s+(?:their\s+)?rations?': {'trust': 0.3, 'respect': 0.2},
    
    # Leadership/decision actions
    r'(?:gave|issued)\s+orders?': {'power': 0.2},
    r'followed?\s+(?:advice|suggestion|lead)': {'power': -0.1, 'respect': 0.2},
    r'(?:took|assumed)\s+(?:command|leadership)': {'power': 0.3, 'respect': 0.2},
    r'deferred?\s+to': {'power': -0.2, 'respect': 0.3},
    r'valued?\s+(?:opinion|counsel)': {'respect': 0.3, 'trust': 0.1},
    
    # Trust building
    r'kept?\s+(?:a\s+)?promise': {'trust': 0.3, 'respect': 0.2},
    r'(?:proved|proven)\s+(?:reliable|trustworthy)': {'trust': 0.4, 'respect': 0.2},
    r'(?:confided|confessed)': {'intimacy': 0.3, 'trust': 0.2},
    r'shared?\s+(?:a\s+)?secrets?': {'intimacy': 0.4, 'trust': 0.2},
    
    # Danger/sacrifice
    r'(?:risked|sacrificed)\s+(?:for|to\s+protect)': {'trust': 0.5, 'respect': 0.4, 'intimacy': 0.2},
    r'took\s+(?:the\s+)?(?:blow|hit|damage)\s+(?:for|instead)': {'trust': 0.6, 'respect': 0.4, 'intimacy': 0.3},
    r'(?:saved|rescued)\s+(?:from|when)': {'trust': 0.6, 'respect': 0.5, 'intimacy': 0.3},
    
    # Working together
    r'together,?\s+(?:we|they)\s+(?:examined|investigated|searched)': {'trust': 0.2, 'intimacy': 0.1},
    r'(?:we|they)\s+(?:worked|acted)\s+together': {'trust': 0.2, 'respect': 0.1},
    r'prepared?\s+to\s+(?:report|return)\s+(?:back\s+)?together': {'trust': 0.1, 'respect': 0.1},
    r'(?:collaborated|cooperated)': {'trust': 0.2, 'respect': 0.2},

    # Recruitment / alliance formation
    r'\b(?:agreed|agreeing)\b.*\b(?:accompany|aid|help|join)\b': {'trust': 0.2, 'respect': 0.2},
    r'\b(?:consented|consenting)\b.*\b(?:accompany|aid|help|join)\b': {'trust': 0.2, 'respect': 0.2},
    r'(?:accompan(?:y|ied|ying)|join(?:ed|ing))\s+(?:the\s+)?party': {'trust': 0.2, 'respect': 0.1},
    r'follow(?:ed|ing)\s+(?:the\s+party|them)\s+(?:into|down|through)': {'trust': 0.2, 'respect': 0.1},

    # Guard / escort / watch duties
    r'stand(?:ing)?\s+watch': {'trust': 0.2, 'respect': 0.1},
    r'guard(?:ing|ed)?\s+(?:the\s+)?(?:rear|door|doors|entry|entrance|main\s+doors)': {'trust': 0.2, 'respect': 0.1},
    r'bring(?:ing)?\s+up\s+(?:the\s+)?rear': {'trust': 0.2, 'respect': 0.1},

    # Narrative combat teamwork / contribution
    r'scattered?\s+(?:the\s+)?enemy\s+ranks': {'trust': 0.2, 'respect': 0.3, 'power': 0.2},
    r'strikes?\s+(?:relentless|unyielding)': {'respect': 0.2, 'power': 0.2},
    r'pressed\s+forward,?\s+united\s+in\s+purpose': {'trust': 0.2, 'respect': 0.2},

    # ===== ENHANCED PATTERNS ADDED =====

    # Romantic/Intimate actions
    r'passionate\s+kiss': {'intimacy': 0.7, 'trust': 0.3, 'respect': 0.1},
    r'(?:gentle|tender|soft)\s+kiss': {'intimacy': 0.5, 'trust': 0.2},
    r'embraced?\s+(?:tenderly|gently|warmly)': {'intimacy': 0.4, 'trust': 0.2},
    r'held?\s+(?:hands|close)': {'intimacy': 0.3, 'trust': 0.2},
    r'(?:brief\s+)?intimate\s+dance': {'intimacy': 0.5, 'trust': 0.3},
    r'whispered?\s+(?:softly|gently)': {'intimacy': 0.3, 'trust': 0.1},
    r'gazed?\s+(?:into\s+eyes|longingly)': {'intimacy': 0.3, 'trust': 0.1},
    r'romantic\s+(?:gesture|moment)': {'intimacy': 0.4, 'trust': 0.2},
    r'(?:showed|expressed)\s+(?:deep\s+)?affection': {'intimacy': 0.4, 'trust': 0.2},

    # Combat excellence
    r'(?:landed|struck)\s+(?:a\s+)?(?:critical|devastating)\s+(?:hit|blow)': {'respect': 0.4, 'power': 0.3},
    r'(?:heroically|bravely)\s+(?:charged|attacked)': {'respect': 0.3, 'power': 0.2, 'trust': 0.2},
    r'(?:expertly|skillfully)\s+(?:dodged|parried|blocked)': {'respect': 0.3, 'power': 0.1},
    r'(?:flanked|outmaneuvered)\s+(?:the\s+)?(?:enemy|opponent)': {'respect': 0.2, 'trust': 0.2},
    r'(?:coordinated|synchronized)\s+(?:attack|strike)': {'trust': 0.3, 'respect': 0.2},
    r'(?:covered|watched)\s+(?:my|their|our)\s+(?:back|flank)': {'trust': 0.4, 'respect': 0.2},
    r'(?:drew|attracted)\s+(?:enemy\s+)?fire': {'trust': 0.3, 'respect': 0.3},
    r'last\s+stand': {'respect': 0.5, 'trust': 0.4, 'power': 0.2},

    # Humor and levity
    r'(?:shared|exchanged)\s+(?:a\s+)?(?:joke|jest|laugh)': {'intimacy': 0.2, 'trust': 0.1},
    r'(?:made|cracked)\s+(?:a\s+)?(?:joke|jest)': {'intimacy': 0.1, 'trust': 0.1},
    r'(?:laughed|chuckled)\s+(?:together|heartily)': {'intimacy': 0.2, 'trust': 0.1},
    r'(?:lightened|lifted)\s+(?:the\s+)?mood': {'intimacy': 0.1, 'trust': 0.1},
    r'(?:playful|teasing)\s+(?:banter|exchange)': {'intimacy': 0.2, 'trust': 0.1},
    r'(?:amusing|humorous)\s+(?:comment|observation)': {'intimacy': 0.1},

    # Deep loyalty
    r'(?:swore|pledged)\s+(?:an\s+)?oath': {'trust': 0.5, 'respect': 0.4},
    r'(?:proved|demonstrated)\s+(?:unwavering\s+)?loyalty': {'trust': 0.5, 'respect': 0.3},
    r'(?:refused|rejected)\s+(?:to\s+)?(?:abandon|leave)': {'trust': 0.4, 'respect': 0.3},
    r'(?:stood|remained)\s+(?:by|with)\s+(?:through|despite)': {'trust': 0.4, 'respect': 0.2},
    r'(?:kept|honored)\s+(?:their\s+)?word': {'trust': 0.4, 'respect': 0.3},
    r'(?:never|not)\s+(?:gave\s+up|surrendered)': {'respect': 0.3, 'trust': 0.2},

    # Strategic brilliance
    r'(?:devised|formulated)\s+(?:a\s+)?(?:clever|brilliant)\s+(?:plan|strategy)': {'respect': 0.4, 'power': 0.2},
    r'(?:outsmarted|outwitted)': {'respect': 0.3, 'power': 0.2},
    r'(?:spotted|detected)\s+(?:a\s+)?(?:trap|ambush)': {'trust': 0.3, 'respect': 0.2},
    r'(?:found|discovered)\s+(?:a\s+)?(?:hidden|secret)': {'respect': 0.2, 'trust': 0.1},
    r'(?:solved|deciphered)\s+(?:the\s+)?(?:puzzle|riddle)': {'respect': 0.3, 'power': 0.1},
    r'tactical\s+(?:advantage|insight)': {'respect': 0.3, 'power': 0.2},

    # Emotional support
    r'(?:comforted|consoled)\s+(?:in|during)\s+(?:grief|sorrow|pain)': {'intimacy': 0.4, 'trust': 0.3},
    r'(?:offered|provided)\s+(?:a\s+)?shoulder\s+to\s+cry': {'intimacy': 0.4, 'trust': 0.2},
    r'(?:listened|heard)\s+(?:patiently|carefully)': {'intimacy': 0.2, 'trust': 0.2, 'respect': 0.1},
    r'(?:understood|empathized)': {'intimacy': 0.3, 'trust': 0.2},
    r'(?:encouraged|inspired)\s+(?:when|during)': {'trust': 0.2, 'respect': 0.2},
    r'(?:believed|had\s+faith)\s+(?:in|when)': {'trust': 0.3, 'respect': 0.2},

    # Vulnerability and honesty
    r'(?:revealed|shared)\s+(?:a\s+)?(?:painful|dark)\s+(?:past|secret)': {'intimacy': 0.5, 'trust': 0.4},
    r'(?:admitted|confessed)\s+(?:weakness|fear|mistake)': {'intimacy': 0.3, 'trust': 0.3},
    r'(?:opened\s+up|bared)\s+(?:soul|heart)': {'intimacy': 0.5, 'trust': 0.3},
    r'(?:cried|wept)\s+(?:openly|together)': {'intimacy': 0.4, 'trust': 0.2},
    r'(?:showed|revealed)\s+vulnerability': {'intimacy': 0.4, 'trust': 0.3},

    # Teaching and mentoring
    r'(?:taught|instructed)\s+(?:patiently|carefully)': {'respect': 0.3, 'trust': 0.2},
    r'(?:guided|mentored)': {'respect': 0.3, 'trust': 0.2, 'power': -0.1},
    r'(?:shared|passed\s+on)\s+(?:knowledge|wisdom)': {'respect': 0.3, 'trust': 0.2},
    r'(?:learned|trained)\s+(?:from|under)': {'respect': 0.3, 'power': -0.2},

    # Celebration and joy
    r'(?:celebrated|rejoiced)\s+(?:together|victory)': {'intimacy': 0.2, 'trust': 0.2},
    r'(?:toasted|cheered)\s+(?:to|for)': {'intimacy': 0.2, 'trust': 0.1},
    r'(?:sang|danced)\s+(?:together|around)': {'intimacy': 0.3, 'trust': 0.1},
    r'(?:shared|enjoyed)\s+(?:a\s+)?meal\s+together': {'intimacy': 0.2, 'trust': 0.2},

    # Competition and rivalry
    r'(?:friendly|good-natured)\s+(?:competition|rivalry)': {'respect': 0.2, 'intimacy': 0.1},
    r'(?:challenged|competed)\s+(?:fairly|honorably)': {'respect': 0.2},
    r'(?:acknowledged|recognized)\s+(?:skill|superiority)': {'respect': 0.3, 'power': -0.1},
    r'(?:bested|defeated)\s+(?:in|at)\s+(?:fair|honorable)': {'respect': 0.2, 'power': 0.2},
}

# Negative patterns tracked separately
NEGATIVE_PATTERNS = {
    r'(?:fled|abandoned)\s+(?:the\s+)?(?:scene|area|location|battle)': {'trust': -0.5, 'respect': -0.3, 'fear': 0.2},
    r'(?:betrayed|deceived)\s+(?:by|us)': {'trust': -0.6, 'respect': -0.4},
    r'(?:was\s+)?threatened\s+by': {'fear': 0.4, 'trust': -0.3},
    r'(?:ignored|dismissed)\s+(?:our|their)\s+(?:concern|advice|plea)': {'respect': -0.2, 'trust': -0.1},
    r'(?:lied|deceived|misled)': {'trust': -0.4, 'respect': -0.3},
    r'broke\s+(?:a\s+)?promise': {'trust': -0.4, 'respect': -0.3},
    r'(?:stole|pilfered|took)\s+(?:from|without)': {'trust': -0.3, 'respect': -0.2},
    r'(?:mocked|ridiculed|belittled)': {'respect': -0.3, 'intimacy': -0.2},
    r'(?:argued|quarreled|fought)\s+(?:with|against)': {'trust': -0.1, 'intimacy': -0.1},
    r'(?:rejected|spurned|rebuffed)': {'intimacy': -0.3, 'respect': -0.1},
    r'(?:cruel|callous|heartless)': {'fear': 0.4, 'trust': -0.6, 'respect': -0.4},
    r'(?:intimidated|frightened|scared)': {'fear': 0.5, 'trust': -0.3},

    # Exposure / leverage / coercion
    r'hidden\s+(?:bundle\s+of\s+)?letters': {'trust': -0.2, 'fear': 0.2},
    r'secret\s+correspondence': {'trust': -0.3, 'fear': 0.2},
    r'covert\s+allegiance': {'trust': -0.4, 'respect': -0.2, 'fear': 0.1},
    r'blackmail(?:ed|ing)': {'trust': -0.3, 'fear': 0.4},
    r'confronted?': {'fear': 0.2, 'respect': 0.1},
    r'demand(?:ed|ing)\s+(?:his|her|their)\s+(?:aid|help|cooperation)': {'trust': -0.1, 'fear': 0.3},
    r'pressured?\s+(?:him|her|them)?\s*(?:into|to)\s+(?:aid|help|cooperate|accompany|join)': {'trust': -0.1, 'fear': 0.3},
}

@dataclass
class ParsedAction:
    """Represents a parsed action from journal text"""
    pattern: str
    emotional_impact: Dict[str, float]
    context: str
    npc_name: str
    action_type: str  # 'positive' or 'negative'
    
    def get_readable_action(self) -> str:
        """Convert pattern to readable action description"""
        # Extract key words from pattern for readable output

        # Healing and support
        if 'cure' in self.pattern or 'heal' in self.pattern:
            return 'cast healing magic'
        elif 'sacred' in self.pattern:
            return 'used divine power'
        elif 'support' in self.pattern:
            return 'offered support'
        elif 'reassurance' in self.pattern:
            return 'offered reassurance'
        elif 'comforted' in self.pattern or 'consoled' in self.pattern:
            return 'provided comfort'

        # Romantic/Intimate
        elif 'passionate' in self.pattern and 'kiss' in self.pattern:
            return 'shared passionate kiss'
        elif 'kiss' in self.pattern:
            return 'shared kiss'
        elif 'embrace' in self.pattern:
            return 'embraced warmly'
        elif 'dance' in self.pattern:
            return 'danced together'
        elif 'whisper' in self.pattern:
            return 'whispered softly'
        elif 'affection' in self.pattern:
            return 'showed affection'
        elif 'romantic' in self.pattern:
            return 'romantic moment'

        # Combat
        elif 'critical' in self.pattern or 'devastating' in self.pattern:
            return 'critical strike'
        elif 'heroically' in self.pattern or 'bravely' in self.pattern:
            return 'heroic charge'
        elif 'dodged' in self.pattern or 'parried' in self.pattern:
            return 'expert defense'
        elif 'flanked' in self.pattern or 'outmaneuvered' in self.pattern:
            return 'tactical maneuver'
        elif 'coordinated' in self.pattern or 'synchronized' in self.pattern:
            return 'coordinated attack'
        elif 'last' in self.pattern and 'stand' in self.pattern:
            return 'last stand'

        # Social bonds
        elif 'bond' in self.pattern:
            return 'deepened bond'
        elif 'trust' in self.pattern:
            return 'built trust'
        elif 'agree' in self.pattern or 'consent' in self.pattern:
            return 'agreed to accompany'
        elif 'accompany' in self.pattern or 'join' in self.pattern:
            return 'joined the party'
        elif 'follow' in self.pattern:
            return 'followed into danger'
        elif 'together' in self.pattern:
            return 'worked together'
        elif 'camaraderie' in self.pattern:
            return 'shared camaraderie'
        elif 'purpose' in self.pattern or 'resolve' in self.pattern or 'determination' in self.pattern:
            return 'shared determination'
        elif 'unity' in self.pattern or 'unified' in self.pattern or 'united' in self.pattern:
            return 'stood united'
        elif 'laugh' in self.pattern or 'joke' in self.pattern:
            return 'shared laughter'
        elif 'celebrated' in self.pattern or 'rejoiced' in self.pattern:
            return 'celebrated together'
        elif 'meal' in self.pattern:
            return 'shared meal'

        # Loyalty
        elif 'oath' in self.pattern or 'pledged' in self.pattern:
            return 'pledged oath'
        elif 'loyalty' in self.pattern:
            return 'proved loyalty'
        elif 'refused' in self.pattern and 'abandon' in self.pattern:
            return 'refused to abandon'
        elif 'stood' in self.pattern and 'by' in self.pattern:
            return 'stood by ally'

        # Strategic
        elif 'plan' in self.pattern or 'strategy' in self.pattern:
            return 'devised strategy'
        elif 'outsmarted' in self.pattern or 'outwitted' in self.pattern:
            return 'outsmarted enemy'
        elif 'trap' in self.pattern or 'ambush' in self.pattern:
            return 'detected danger'
        elif 'puzzle' in self.pattern or 'riddle' in self.pattern:
            return 'solved puzzle'

        # Vulnerability
        elif 'revealed' in self.pattern and 'secret' in self.pattern:
            return 'shared secret'
        elif 'admitted' in self.pattern or 'confessed' in self.pattern:
            return 'admitted vulnerability'
        elif 'cried' in self.pattern or 'wept' in self.pattern:
            return 'shared tears'
        elif 'vulnerability' in self.pattern:
            return 'showed vulnerability'

        # Protection
        elif 'watch' in self.pattern or 'keen' in self.pattern:
            return 'kept watch'
        elif 'guard' in self.pattern or 'rear' in self.pattern:
            return 'stood watch'
        elif 'protected' in self.pattern:
            return 'provided protection'
        elif 'risked' in self.pattern or 'sacrificed' in self.pattern:
            return 'made sacrifice'
        elif 'saved' in self.pattern or 'rescued' in self.pattern:
            return 'performed rescue'
        elif 'enemy' in self.pattern and 'ranks' in self.pattern:
            return 'broke enemy ranks'
        elif 'relentless' in self.pattern or 'unyielding' in self.pattern:
            return 'fought fiercely'

        # Teaching
        elif 'taught' in self.pattern or 'instructed' in self.pattern:
            return 'taught skills'
        elif 'mentored' in self.pattern or 'guided' in self.pattern:
            return 'mentored ally'
        elif 'wisdom' in self.pattern or 'knowledge' in self.pattern:
            return 'shared wisdom'

        # Competition
        elif 'competition' in self.pattern or 'rivalry' in self.pattern:
            return 'friendly rivalry'
        elif 'challenged' in self.pattern or 'competed' in self.pattern:
            return 'friendly challenge'

        # Negative actions
        elif 'fled' in self.pattern or 'abandoned' in self.pattern:
            return 'abandoned in danger'
        elif 'betrayed' in self.pattern:
            return 'betrayed trust'
        elif 'blackmail' in self.pattern:
            return 'was blackmailed'
        elif 'letters' in self.pattern or 'correspondence' in self.pattern:
            return 'secret exposed'
        elif 'allegiance' in self.pattern:
            return 'allegiance exposed'
        elif 'confront' in self.pattern or 'demand' in self.pattern or 'pressure' in self.pattern:
            return 'faced coercion'
        elif 'threatened' in self.pattern:
            return 'made threats'
        elif 'cruel' in self.pattern or 'callous' in self.pattern:
            return 'showed cruelty'
        elif 'lied' in self.pattern or 'deceived' in self.pattern:
            return 'deceived ally'

        # Resource sharing
        elif 'generous' in self.pattern:
            return 'showed generosity'

        else:
            # Fallback - extract main word from pattern
            words = re.findall(r'\w+', self.pattern)
            if words:
                return ' '.join(words[-2:]) if len(words) > 1 else words[-1]
            return 'interacted'

class ActionParser:
    """Parses journal entries to extract emotionally significant actions"""
    
    def __init__(self):
        self.positive_patterns = ACTION_PATTERNS
        self.negative_patterns = NEGATIVE_PATTERNS
        # NPCs should be provided dynamically from party tracker
        self.companion_npcs = []
    
    def parse_entry(self, text: str, npc_name: str) -> List[ParsedAction]:
        """Extract actions related to a specific NPC from journal text"""
        actions = []
        
        # Check if NPC is mentioned
        if not self._is_npc_mentioned(text, npc_name):
            return actions
        
        # Look for positive patterns
        actions.extend(self._find_patterns(
            text, npc_name, self.positive_patterns, 'positive'
        ))
        
        # Look for negative patterns
        actions.extend(self._find_patterns(
            text, npc_name, self.negative_patterns, 'negative'
        ))
        
        return actions
    
    def _is_npc_mentioned(self, text: str, npc_name: str) -> bool:
        """Check if NPC is mentioned in text"""
        return bool(re.search(rf'\b{npc_name}\b', text, re.IGNORECASE))
    
    def _find_patterns(self, text: str, npc_name: str, 
                      patterns: Dict, action_type: str) -> List[ParsedAction]:
        """Find action patterns near NPC mentions"""
        found_actions = []
        
        # Find all mentions of the NPC
        npc_mentions = list(re.finditer(rf'\b{npc_name}\b', text, re.IGNORECASE))
        
        for pattern, emotion_impact in patterns.items():
            # Check if pattern exists anywhere in text first
            if not re.search(pattern, text.lower()):
                continue
                
            # Check proximity to NPC mentions (within 150 chars)
            for mention in npc_mentions:
                start = max(0, mention.start() - 150)
                end = min(len(text), mention.end() + 150)
                context = text[start:end]
                
                if re.search(pattern, context.lower()):
                    # Extract cleaner context
                    context_start = max(0, mention.start() - 50)
                    context_end = min(len(text), mention.end() + 50) 
                    clean_context = text[context_start:context_end].strip()
                    
                    action = ParsedAction(
                        pattern=pattern,
                        emotional_impact=emotion_impact,
                        context=clean_context,
                        npc_name=npc_name,
                        action_type=action_type
                    )
                    found_actions.append(action)
                    break  # Only count each pattern once per entry
        
        return found_actions
    
    def extract_all_npcs(self, text: str, npc_names: List[str] = None) -> Dict[str, List[ParsedAction]]:
        """Extract actions for all companion NPCs from text

        Args:
            text: The text to parse
            npc_names: List of NPC names to check (uses self.companion_npcs if not provided)
        """
        results = {}

        npcs_to_check = npc_names if npc_names else self.companion_npcs

        for npc_name in npcs_to_check:
            actions = self.parse_entry(text, npc_name)
            if actions:
                results[npc_name] = actions

        return results
    
    def get_emotional_summary(self, actions: List[ParsedAction]) -> Dict[str, float]:
        """Summarize emotional impact of multiple actions"""
        summary = {'trust': 0.0, 'power': 0.0, 'intimacy': 0.0, 
                  'fear': 0.0, 'respect': 0.0}
        
        for action in actions:
            for emotion, value in action.emotional_impact.items():
                summary[emotion] += value
        
        return summary
