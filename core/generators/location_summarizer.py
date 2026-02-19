#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
AI-Powered Location Transition Summarizer

This module generates intelligent summaries of location transition groups using AI,
preserving critical game information while compressing narrative content.
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

# Import local modules
from utils.token_estimator import TokenEstimator
from openai import OpenAI
import config
from utils.enhanced_logger import debug, info, warning, error, set_script_name
from utils.capture.multi_model_capture import capture_and_fanout, register_callsite
register_callsite("T027", "core/generators/location_summarizer.py", 530)

# Set script name for logging
set_script_name("location_summarizer")


@dataclass
class GameEvent:
    """Represents a critical game event that must be preserved"""
    event_type: str  # combat, npc_interaction, inventory, character_state, discovery, plot
    location: str
    description: str
    details: Dict[str, Any]
    importance: str  # critical, important, minor


class LocationSummarizer:
    """Generate intelligent summaries of location transition groups"""
    
    def __init__(self, ai_model: str = None):
        """Initialize summarizer with AI model configuration"""
        self.ai_model = ai_model or config.DM_SUMMARIZATION_MODEL
        self.token_estimator = TokenEstimator()
        self.summarization_history = []
        
        # Initialize OpenAI client
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
        
        # No artificial compression parameters - purely agentic AI generation
        
    def summarize_transition_group(self, start_location: str, end_location: str, 
                                 messages: List[Dict], intermediate_locations: List[str] = None) -> Dict:
        """
        Generate AI-powered summary preserving key information
        
        Args:
            start_location: Starting location name
            end_location: Ending location name
            messages: List of conversation messages to summarize
            intermediate_locations: Optional list of locations visited between start/end
            
        Returns:
            Dictionary with compressed message group and metadata
        """
        if not messages:
            return self._create_empty_summary(start_location, end_location)
        
        # Extract key events from messages
        events = self.extract_key_events(messages)
        
        # Preserve critical data
        preserved_data = self.preserve_critical_data(events)
        
        # Generate location summary
        summary = self.generate_location_summary(
            start_location, end_location, intermediate_locations or [], preserved_data, messages
        )
        
        # Calculate compression metrics
        original_tokens = sum(self.token_estimator.estimate_tokens_from_text(
            msg.get('content', '')) for msg in messages)
        summary_tokens = self.token_estimator.estimate_tokens_from_text(summary)
        
        compression_result = {
            'summary': summary,
            'original_message_count': len(messages),
            'original_tokens': original_tokens,
            'summary_tokens': summary_tokens,
            'compression_ratio': (original_tokens - summary_tokens) / original_tokens if original_tokens > 0 else 0,
            'events_preserved': len(events),
            'locations_covered': [start_location] + (intermediate_locations or []) + [end_location],
            'timestamp': datetime.now().isoformat(),
            'metadata': {
                'start_location': start_location,
                'end_location': end_location,
                'intermediate_locations': intermediate_locations or [],
                'critical_events': [e for e in events if e.importance == 'critical'],
                'summary_quality': self._assess_summary_quality(original_tokens, summary_tokens, events)
            }
        }
        
        # Store in history for future reference
        self.summarization_history.append(compression_result)
        
        return compression_result
    
    def extract_key_events(self, messages: List[Dict]) -> List[GameEvent]:
        """
        Parse messages for critical game events
        
        Returns list of GameEvent objects representing important occurrences
        """
        events = []
        
        for i, message in enumerate(messages):
            content = message.get('content', '')
            role = message.get('role', '')
            
            # Skip system messages
            if role == 'system':
                continue
                
            # Detect combat encounters
            combat_events = self._extract_combat_events(content, i)
            events.extend(combat_events)
            
            # Detect NPC interactions
            npc_events = self._extract_npc_interactions(content, i)
            events.extend(npc_events)
            
            # Detect inventory changes
            inventory_events = self._extract_inventory_changes(content, i)
            events.extend(inventory_events)
            
            # Detect character state changes
            character_events = self._extract_character_changes(content, i)
            events.extend(character_events)
            
            # Detect environmental discoveries
            discovery_events = self._extract_discoveries(content, i)
            events.extend(discovery_events)
            
            # Detect plot progression
            plot_events = self._extract_plot_progression(content, i)
            events.extend(plot_events)
        
        return events
    
    def _extract_combat_events(self, content: str, message_index: int) -> List[GameEvent]:
        """Extract combat-related events"""
        events = []
        
        # Look for combat indicators
        combat_patterns = [
            r'(attack|damage|hit points?|initiative|combat|battle|fight)',
            r'(\d+\s*damage|takes?\s*\d+|deals?\s*\d+)',
            r'(roll|rolled|d20|saving throw|check)',
            r'(defeated|killed|destroyed|dies?|death)'
        ]
        
        combat_score = 0
        for pattern in combat_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                combat_score += 1
        
        if combat_score >= 2:  # Multiple combat indicators
            importance = 'critical' if 'death' in content.lower() or 'defeated' in content.lower() else 'important'
            events.append(GameEvent(
                event_type='combat',
                location='',  # Will be filled by caller
                description=self._extract_combat_summary(content),
                details={'message_index': message_index, 'combat_score': combat_score},
                importance=importance
            ))
        
        return events
    
    def _extract_npc_interactions(self, content: str, message_index: int) -> List[GameEvent]:
        """Extract NPC interaction events"""
        events = []
        
        # Look for dialogue and NPC mentions
        npc_patterns = [
            r'"([^"]+)"',  # Quoted dialogue
            r'says?|tells?|asks?|responds?|replies?',
            r'(npc|character|person|guard|merchant|villager)',
            r'(quest|task|mission|information|rumor)'
        ]
        
        dialogue_count = len(re.findall(r'"[^"]+"', content))
        npc_score = dialogue_count
        
        for pattern in npc_patterns[1:]:  # Skip dialogue pattern
            if re.search(pattern, content, re.IGNORECASE):
                npc_score += 1
        
        if npc_score >= 2 or dialogue_count > 0:
            importance = 'critical' if 'quest' in content.lower() else 'important'
            events.append(GameEvent(
                event_type='npc_interaction',
                location='',
                description=self._extract_npc_summary(content),
                details={'message_index': message_index, 'dialogue_count': dialogue_count},
                importance=importance
            ))
        
        return events
    
    def _extract_inventory_changes(self, content: str, message_index: int) -> List[GameEvent]:
        """Extract inventory change events"""
        events = []
        
        inventory_patterns = [
            r'(find|found|discover|take|pick up|receive|give|drop|lose|use)',
            r'(gold|silver|copper|coin|treasure|item|weapon|armor|potion)',
            r'(inventory|equipment|gear|belongings)'
        ]
        
        inventory_score = 0
        for pattern in inventory_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                inventory_score += 1
        
        if inventory_score >= 2:
            events.append(GameEvent(
                event_type='inventory',
                location='',
                description=self._extract_inventory_summary(content),
                details={'message_index': message_index, 'inventory_score': inventory_score},
                importance='important'
            ))
        
        return events
    
    def _extract_character_changes(self, content: str, message_index: int) -> List[GameEvent]:
        """Extract character state change events"""
        events = []
        
        character_patterns = [
            r'(level up|experience|xp|gained)',
            r'(hit points?|hp|health|healing|damage)',
            r'(spell slots?|magic|cast|spells?)',
            r'(condition|effect|curse|blessing)',
            r'(rest|sleep|recover)'
        ]
        
        character_score = 0
        for pattern in character_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                character_score += 1
        
        if character_score >= 1:
            importance = 'critical' if 'level up' in content.lower() else 'important'
            events.append(GameEvent(
                event_type='character_state',
                location='',
                description=self._extract_character_summary(content),
                details={'message_index': message_index, 'character_score': character_score},
                importance=importance
            ))
        
        return events
    
    def _extract_discoveries(self, content: str, message_index: int) -> List[GameEvent]:
        """Extract environmental discovery events"""
        events = []
        
        discovery_patterns = [
            r'(secret|hidden|trap|door|passage|room)',
            r'(discover|find|notice|spot|see|reveal)',
            r'(search|investigate|examine|explore)',
            r'(treasure|chest|artifact|clue|evidence)'
        ]
        
        discovery_score = 0
        for pattern in discovery_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                discovery_score += 1
        
        if discovery_score >= 2:
            importance = 'critical' if 'secret' in content.lower() or 'treasure' in content.lower() else 'important'
            events.append(GameEvent(
                event_type='discovery',
                location='',
                description=self._extract_discovery_summary(content),
                details={'message_index': message_index, 'discovery_score': discovery_score},
                importance=importance
            ))
        
        return events
    
    def _extract_plot_progression(self, content: str, message_index: int) -> List[GameEvent]:
        """Extract plot progression events"""
        events = []
        
        plot_patterns = [
            r'(quest|mission|objective|goal)',
            r'(complete|finish|accomplish|succeed)',
            r'(plot|story|narrative|lore)',
            r'(important|significant|major|crucial)'
        ]
        
        plot_score = 0
        for pattern in plot_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                plot_score += 1
        
        if plot_score >= 2:
            events.append(GameEvent(
                event_type='plot',
                location='',
                description=self._extract_plot_summary(content),
                details={'message_index': message_index, 'plot_score': plot_score},
                importance='critical'
            ))
        
        return events
    
    def preserve_critical_data(self, events: List[GameEvent]) -> Dict[str, Any]:
        """
        Ensure no loss of critical game data
        
        Returns structured data for AI consumption
        """
        preserved = {
            'critical_events': [],
            'combat_summary': {},
            'character_progression': {},
            'npc_relationships': {},
            'inventory_changes': {},
            'location_discoveries': {},
            'plot_developments': {}
        }
        
        for event in events:
            if event.importance == 'critical':
                preserved['critical_events'].append({
                    'type': event.event_type,
                    'description': event.description,
                    'details': event.details
                })
            
            # Categorize events
            if event.event_type == 'combat':
                preserved['combat_summary'][event.details['message_index']] = event.description
            elif event.event_type == 'character_state':
                preserved['character_progression'][event.details['message_index']] = event.description
            elif event.event_type == 'npc_interaction':
                preserved['npc_relationships'][event.details['message_index']] = event.description
            elif event.event_type == 'inventory':
                preserved['inventory_changes'][event.details['message_index']] = event.description
            elif event.event_type == 'discovery':
                preserved['location_discoveries'][event.details['message_index']] = event.description
            elif event.event_type == 'plot':
                preserved['plot_developments'][event.details['message_index']] = event.description
        
        return preserved
    
    def generate_location_summary(self, start_loc: str, end_loc: str, 
                                intermediate_locs: List[str], preserved_data: Dict[str, Any],
                                original_messages: List[Dict] = None) -> str:
        """
        Generate AI-powered chronicle summary using the narrative design prompt
        
        This uses the agentic approach with the prompt from claude.txt to create
        rich, detailed narrative summaries that preserve actual story content.
        """
        # Prepare the AI prompt based on claude.txt format
        system_prompt = """You are a narrative design assistant trained to convert sequential TTRPG-style location logs into richly detailed, emotionally resonant summary chronicles. You write with a tone that blends atmospheric storytelling, declarative clarity, and key-detail preservation. You must retain character actions, important items, magical effects, social or emotional beats, combat outcomes, boss confrontations, and environmental changes, while compressing multiple locations into a seamless chronicle that reads like a chapter from a dark fantasy journal or campaign codex."""
        
        user_prompt = f"""Given the following sequential location transitions and logs, generate a single, highly detailed chronicle summary that:

1. **Compresses all location segments** into one fluid narrative without headers or bullet points.
2. **Maintains chronological continuity**, including who did what, where, and why.
3. **Includes all key discoveries**, magical items, ritual effects, emotional reactions, decisions, and changes in setting or mood.
4. **Uses elevated, immersive fantasy prose** -- not modern or casual.
5. **Depict combat sequences, monster encounters, and boss battles with intensity**. Describe the foes, their abilities, how the party fought, who was wounded or heroic, and the aftermath. Convey the stakes.
6. **Preserve any player character sacrifices, wounds, or major successes**. If a battle was hard-fought, show the exhaustion and toll.
7. **Concludes with a reflective or forward-facing insight**, setting up what may come next.
8. **Avoids generic or vague phrasing** -- always prefer specificity (e.g., "Norn plunged the dagger into the specter's core" instead of "a character won a fight").
9. **Assumes no events should be omitted**, even if there was no combat. Silence, ambiance, and tension are part of the story.
10. **Narrate the complete journey through each location**: You MUST explicitly mention moving through or arriving at each location listed below. Weave each location name naturally into the narrative as the party travels through them. Use transitions like "descended from [Location A] into", "emerged at [Location B] to find", "the path through [Location C] revealed", etc.

REQUIRED JOURNEY PROGRESSION (all locations must appear in your narrative):
Starting at: {start_loc}
Traveling through (in order): {' -> '.join(intermediate_locs)}
Ending at: {end_loc}

You MUST narrate the party's movement through EACH of these {len(intermediate_locs) + 2} locations in sequence.

PRESERVED STORY ELEMENTS:
{self._format_preserved_data_for_ai(preserved_data)}

CRITICAL: Your narrative must include all location names from the journey above. Each location should appear naturally within the story as the party progresses through them.

Produce a narrative in the style of a campaign journal or game codex entry. Do not use headings, bullet points, or dialogue labels. Do not refer to the logs or metadata -- only write the compressed, immersive story that shows the party's journey through every listed location."""
        
        # Generate actual AI-powered chronicle summary
        return self._generate_ai_chronicle(start_loc, end_loc, intermediate_locs, preserved_data, original_messages)
    
    def _format_preserved_data_for_ai(self, preserved_data: Dict[str, Any]) -> str:
        """Format preserved data for AI consumption"""
        formatted_sections = []
        
        # Critical events
        if preserved_data.get('critical_events'):
            events = []
            for event in preserved_data['critical_events']:  # All events
                if hasattr(event, 'description'):
                    events.append(event.description)
                else:
                    events.append(event.get('description', ''))
            formatted_sections.append(f"CRITICAL EVENTS: {'; '.join(events)}")
        
        # Combat encounters
        if preserved_data.get('combat_summary'):
            combat_list = list(preserved_data['combat_summary'].values())
            formatted_sections.append(f"COMBAT: {'; '.join(combat_list)}")  # All combat
        
        # NPC interactions
        if preserved_data.get('npc_relationships'):
            npc_list = list(preserved_data['npc_relationships'].values())
            formatted_sections.append(f"NPC INTERACTIONS: {'; '.join(npc_list)}")  # All NPCs
        
        # Discoveries
        if preserved_data.get('location_discoveries'):
            discovery_list = list(preserved_data['location_discoveries'].values())
            formatted_sections.append(f"DISCOVERIES: {'; '.join(discovery_list)}")  # All discoveries
        
        # Plot developments
        if preserved_data.get('plot_developments'):
            plot_list = list(preserved_data['plot_developments'].values())
            formatted_sections.append(f"PLOT: {'; '.join(plot_list)}")
        
        return '\n'.join(formatted_sections) if formatted_sections else "No specific events recorded."
    
    def _format_messages_for_compression(self, messages: List[Dict]) -> str:
        """Format the actual conversation messages for AI compression"""
        formatted_text = ""
        
        for i, message in enumerate(messages):
            role = message.get('role', '')
            content = message.get('content', '')
            
            # Include all message content for the AI to process
            if role and content:
                formatted_text += f"[{role.upper()}]: {content}\n\n"
        
        return formatted_text.strip()
    
    def _generate_ai_chronicle(self, start_loc: str, end_loc: str, 
                              intermediate_locs: List[str], preserved_data: Dict[str, Any], 
                              original_messages: List[Dict] = None) -> str:
        """
        Generate AI-powered chronicle summary using exact prompts from claude.txt
        Includes retry logic for API failures
        """
        max_retries = 3
        retry_delay = 2  # seconds
        
        for attempt in range(max_retries):
            try:
                # Use exact prompts from claude.txt (updated version)
                system_prompt = """You are a narrative design assistant trained to convert sequential TTRPG-style location logs into richly detailed, emotionally resonant chronicle summaries. You write with a tone that blends elevated fantasy prose, atmospheric worldbuilding, and declarative clarity. Your goal is to compress multiple location entries into a seamless narrative arc that captures exploration, discovery, character actions, intense combat, magical rituals, social tension, emotional consequences, ambient detail, AND the intimate human moments that make characters real.

**Your Sacred Duty**: Beyond tracking locations and events, you must capture the heartbeat of relationships—the lingering glances, whispered confessions, playful banter, desperate kisses, and tender moments that define who these characters truly are. The dungeon corridors and forest paths are merely stages where love blooms, friendships deepen, and desires ignite.

**Character Intimacy is Paramount**: As you chronicle the journey through locations, you must weave in:
- Every nickname, pet name, or term of endearment used
- Physical chemistry and attraction between characters
- Moments of vulnerability, comfort, and connection
- Romantic tension, jealousy, yearning, and passion
- Inside jokes, teasing, and playful dynamics
- Personal quirks, habits, fears, and desires
- How characters touch, look at, and respond to each other
- The heat of passion and the tenderness of quiet moments"""
                
                # Format the actual conversation text to compress
                conversation_text = self._format_messages_for_compression(original_messages or [])
                
                user_prompt = f"""Given the following sequential location transitions and logs, generate a single, highly detailed chronicle summary that:

1. **Compresses all location segments** into one fluid narrative without using headings, bullet points, or dialogue labels.
2. **Maintains chronological continuity**, including who did what, where, and why.
3. **Includes all key discoveries**, magical items, environmental cues, rituals, emotional reactions, and major decisions.
4. **Uses immersive, elevated fantasy prose** -- never casual or modern.
5. **Depicts combat sequences, monster encounters, and boss battles with vivid, cinematic intensity**. Describe enemy forms, tactics, powers, damage taken, and how the party triumphed (or failed).
6. **Preserves character impact**: who took wounds, who made sacrifices, who cast crucial spells or delivered final blows. Show exhaustion, fear, or resolve when relevant.
7. **Concludes with a reflective or forward-looking insight**, thematically linking what has occurred to what lies ahead.
8. **Avoids generic phrasing** -- use specific names, textures, items, and visual language (e.g., "Norn's blade parted the specter's ribbed shadows" instead of "a character hit a ghost").
9. **Never omits quiet moments**: include tension-building silence, fog, haunted ambiance, or signs of dread -- even when no combat occurs.
10. **Narrate the complete journey through each location**: You MUST explicitly mention moving through or arriving at each location from the journey progression. Weave location names naturally into the narrative as the party travels through them.
11. **Captures the intimate human story**: As characters move through locations, chronicle their relationships. Did lovers steal a kiss in the shadowed alcove? Did companions share knowing glances across the battlefield? Use their nicknames and pet names—"Trouble Magnet" not just "the cleric." Show the tender touch that healed more than wounds, the playful banter that lightened dark moments, the jealous glare when affections wandered. These moments are as vital as any treasure found.
12. **Weaves in character details**: Include personal quirks and habits—how someone always checks their weapon thrice, needs three cups of tea to be civil, sleeps curled around their pack, or unconsciously reaches for their companion's hand in darkness. Show their fears (claustrophobia in dungeons?), desires (that longing look at soft beds), and intimate preferences.
13. **Chronicles both heat and tenderness**: When passion ignites—the desperate embrace after near-death, hands tangling in hair, armor clattering to stone—capture it fully. When comfort is offered—the cloak shared against cold, the wordless vigil by a sickbed, the gentle cleaning of wounds—honor it. The way bodies betray emotions: nervous tics, bitten lips, tell-tale blushes. Both fire and gentleness forge unbreakable bonds.

REQUIRED JOURNEY PROGRESSION (all locations must appear in your narrative):
Starting at: {start_loc}
Traveling through (in order): {' -> '.join(intermediate_locs)}
Ending at: {end_loc}

You MUST narrate the party's movement through EACH of these {len(intermediate_locs) + 2} locations in sequence.

Here is the input:

{conversation_text}

**The Golden Rule: Names Are Memory, Details Are Soul**
Before you begin, scan the entire conversation for:
- Every nickname, pet name, or term of endearment used
- Personal preferences (favorite drinks, foods, colors)
- Behavioral quirks and habits
- Fears, phobias, desires, and dreams
- How characters physically interact with each other
- Inside jokes and running gags

Then weave ALL of these throughout your chronicle. When you write "Eirik moved forward," you have failed if somewhere he was called "Trouble Magnet." When describing a rest, you have failed if you don't mention someone's tea ritual or how they always sleep with one eye open.

CRITICAL: Your narrative must include all location names from the journey progression above. Each location should appear naturally within the story as the party progresses through them. More importantly, show how each location affected the relationships—did the dark dungeon bring them closer? Did the open road allow playful teasing? Did danger spark passion?

Your output should read like a published game codex, narrative recap, or campaign journal entry written by a bard who was intimate with the party's secrets. Never reference this prompt or the data format -- just write the immersive chronicle that shows both the party's journey through every listed location AND the evolution of their bonds."""

                # Make API call to OpenAI - purely agentic, no artificial limits
                response = capture_and_fanout("T027", self.client.chat.completions.create, messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ], model=self.ai_model, temperature=0.6)
                    # No max_tokens limit - let AI decide optimal length
                
                # Extract the generated chronicle
                chronicle = response.choices[0].message.content.strip()
                
                # Add a note about AI generation
                return f"{chronicle}\n\n[AI-Generated Chronicle Summary]"
                
            except Exception as e:
                if attempt < max_retries - 1:
                    warning(f"AI_RETRY: Chronicle generation attempt {attempt + 1} failed, retrying...", category="summarization")
                    import time
                    time.sleep(retry_delay)
                    continue
                else:
                    error(f"AI_FAILURE: Failed to generate AI chronicle after {max_retries} attempts: {e}", exception=e, category="summarization")
                    raise RuntimeError(f"AI chronicle generation failed after {max_retries} attempts: {e}")
    
    
    def _create_empty_summary(self, start_location: str, end_location: str) -> Dict:
        """Create summary for empty message set"""
        return {
            'summary': f"Brief transition from {start_location} to {end_location}.",
            'original_message_count': 0,
            'original_tokens': 0,
            'summary_tokens': self.token_estimator.estimate_tokens_from_text(
                f"Brief transition from {start_location} to {end_location}."
            ),
            'compression_ratio': 0.0,
            'events_preserved': 0,
            'locations_covered': [start_location, end_location],
            'timestamp': datetime.now().isoformat(),
            'metadata': {
                'start_location': start_location,
                'end_location': end_location,
                'intermediate_locations': [],
                'critical_events': [],
                'summary_quality': 'minimal'
            }
        }
    
    def _assess_summary_quality(self, original_tokens: int, summary_tokens: int, events: List[GameEvent]) -> str:
        """Simple quality assessment - no artificial thresholds"""
        if original_tokens == 0:
            return 'minimal'
        return 'agentic'  # Let AI determine quality, not coded rules
    
    # Helper methods for extracting specific event summaries
    def _extract_combat_summary(self, content: str) -> str:
        """Extract concise combat summary"""
        # Look for damage numbers, outcomes, participants
        damage_match = re.search(r'(\d+)\s*damage', content, re.IGNORECASE)
        damage_info = f"{damage_match.group(1)} damage dealt" if damage_match else "combat encounter"
        
        if 'defeated' in content.lower() or 'killed' in content.lower():
            return f"Combat victory - {damage_info}"
        else:
            return f"Combat engagement - {damage_info}"
    
    def _extract_npc_summary(self, content: str) -> str:
        """Extract concise NPC interaction summary"""
        # Look for NPC names and key dialogue
        dialogue_matches = re.findall(r'"([^"]+)"', content)
        if dialogue_matches:
            return f"Dialogue with NPC: {dialogue_matches[0]}"
        else:
            return "NPC interaction occurred"
    
    def _extract_inventory_summary(self, content: str) -> str:
        """Extract concise inventory change summary"""
        if 'find' in content.lower() or 'found' in content.lower():
            return "Items found and collected"
        elif 'give' in content.lower() or 'trade' in content.lower():
            return "Items exchanged or traded"
        else:
            return "Inventory changes made"
    
    def _extract_character_summary(self, content: str) -> str:
        """Extract concise character change summary"""
        if 'level up' in content.lower():
            return "Character leveled up"
        elif 'damage' in content.lower():
            return "Character took damage"
        elif 'healing' in content.lower() or 'heal' in content.lower():
            return "Character healed"
        else:
            return "Character state changed"
    
    def _extract_discovery_summary(self, content: str) -> str:
        """Extract concise discovery summary"""
        if 'secret' in content.lower():
            return "Secret discovered"
        elif 'trap' in content.lower():
            return "Trap found"
        elif 'treasure' in content.lower():
            return "Treasure discovered"
        else:
            return "Environmental discovery made"
    
    def _extract_plot_summary(self, content: str) -> str:
        """Extract concise plot progression summary"""
        if 'complete' in content.lower() or 'finish' in content.lower():
            return "Quest objective completed"
        elif 'quest' in content.lower():
            return "Quest progression made"
        else:
            return "Plot development occurred"
    
    def get_summarization_history(self) -> List[Dict]:
        """Get history of all summarizations performed"""
        return self.summarization_history.copy()
    
    def save_summarization_report(self, output_file: str = None) -> str:
        """Save summarization history and statistics to file"""
        if not output_file:
            output_file = "summarization_report.json"
        
        report = {
            'summarization_timestamp': datetime.now().isoformat(),
            'total_summarizations': len(self.summarization_history),
            'total_original_tokens': sum(s['original_tokens'] for s in self.summarization_history),
            'total_summary_tokens': sum(s['summary_tokens'] for s in self.summarization_history),
            'average_compression_ratio': sum(s['compression_ratio'] for s in self.summarization_history) / len(self.summarization_history) if self.summarization_history else 0,
            'summarization_history': self.summarization_history
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return output_file


