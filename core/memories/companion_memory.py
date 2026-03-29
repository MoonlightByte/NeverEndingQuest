#!/usr/bin/env python3
"""
Companion Memory Manager - Main orchestrator for the memory system
Manages memory creation, retrieval, and persistence for companion NPCs.
"""

import json
import os
import re
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from collections import defaultdict

from .emotional_vectors import EmotionalVector, BEHAVIORAL_EIGENVECTORS
from .action_parser import ActionParser
from .memory_crystallizer import MemoryCrystallizer, CoreMemory
from .memory_gravity import GravitationalRetrieval
from utils.encoding_utils import safe_json_load, safe_json_dump
from utils.enhanced_logger import debug, info, warning, error

MEMORY_QUALITY_HEALTHY = 'healthy'
MEMORY_QUALITY_SPARSE = 'sparse'
MEMORY_QUALITY_DEGRADED = 'degraded_extract'
MEMORY_QUALITY_MALFORMED = 'malformed'

RELATIONSHIP_TRIGGER_LIMIT = 3
ATTRIBUTION_LOG_LIMIT = 12
GROUP_SHARED_ACTIONS = {
    'agreed to accompany',
    'joined the party',
    'followed into danger',
    'stood watch',
    'kept watch',
    'broke enemy ranks',
    'fought fiercely',
    'worked together',
    'shared determination',
    'stood united',
}
_PC_ALIAS_TITLES = {
    'sir', 'lady', 'lord', 'captain', 'commander', 'ranger', 'scout', 'priest',
    'cleric', 'wizard', 'mage', 'paladin', 'rogue', 'fighter', 'bard',
    'druid', 'monk', 'warlock', 'sorcerer',
}


def _coerce_int(value: Any, default: int = 0) -> int:
    """Coerce a value to int for memory counters."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def has_nonzero_emotional_state(emotional_state: Dict[str, Any]) -> bool:
    """Return True when any tracked emotion is non-zero."""
    if not isinstance(emotional_state, dict):
        return False

    for value in emotional_state.values():
        try:
            if abs(float(value)) > 0.0:
                return True
        except (TypeError, ValueError):
            return False

    return False


def _coerce_float(value: Any, default: float = 0.0) -> float:
    """Coerce a value to float for relationship scores."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_global_state(emotional_state: Dict[str, Any], resentment: float) -> Dict[str, float]:
    """Build bounded global state payload."""
    return {
        'trust': round(_coerce_float(emotional_state.get('trust', 0.0)), 3),
        'power': round(_coerce_float(emotional_state.get('power', 0.0)), 3),
        'intimacy': round(_coerce_float(emotional_state.get('intimacy', 0.0)), 3),
        'fear': round(_coerce_float(emotional_state.get('fear', 0.0)), 3),
        'respect': round(_coerce_float(emotional_state.get('respect', 0.0)), 3),
        'resentment': round(max(0.0, min(1.0, _coerce_float(resentment, 0.0))), 3),
    }


def _canonicalize_pc_name(character_name: str) -> str:
    """Normalize PC names using the shared character identity convention."""
    name = str(character_name or '').strip().lower()
    name = name.replace(' ', '_').replace("'", '_')
    name = re.sub(r'[^a-z0-9_]', '_', name)
    name = re.sub(r'_+', '_', name)
    return name.strip('_')


def _build_party_member_aliases(character_name: str) -> List[str]:
    """Build bounded alias list for summary attribution."""
    aliases = []
    name = str(character_name or '').strip()
    if not name:
        return aliases

    aliases.append(name)
    normalized = name.replace('_', ' ').strip()
    if normalized and normalized.lower() != name.lower():
        aliases.append(normalized)

    tokens = [token for token in re.split(r"[\s_]+", normalized) if token]
    if tokens:
        if tokens[0].lower() in _PC_ALIAS_TITLES and len(tokens) > 1:
            aliases.append(tokens[1])
        else:
            aliases.append(tokens[0])
        if len(tokens) > 1:
            aliases.append(tokens[-1])

    deduped = []
    seen = set()
    for alias in aliases:
        alias_text = str(alias or '').strip()
        alias_key = alias_text.lower()
        if not alias_text or alias_key in seen:
            continue
        deduped.append(alias_text)
        seen.add(alias_key)
    return deduped


def _build_party_member_identity(character_name: str) -> Optional[Dict[str, Any]]:
    """Build canonical identity record for a party member."""
    display_name = str(character_name or '').strip()
    if not display_name:
        return None

    character_id = ''
    try:
        from utils.pc_manager import get_character_state

        character_data = get_character_state(display_name, fields=['character_id', 'name']) or {}
        character_id = str(character_data.get('character_id', '')).strip()
        if character_data.get('name'):
            display_name = str(character_data.get('name')).strip() or display_name
    except Exception:
        character_id = ''

    edge_key = character_id or _canonicalize_pc_name(display_name)
    if not edge_key:
        return None

    return {
        'key': edge_key,
        'display_name': display_name,
        'character_id': character_id,
        'normalized_name': _canonicalize_pc_name(display_name),
        'aliases': _build_party_member_aliases(display_name),
    }


def build_companion_memory_participants(party_tracker_data: Dict[str, Any]) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Build canonical companion NPC and party-member identity inputs."""
    party_npcs: List[str] = []
    party_member_identities: List[Dict[str, Any]] = []
    seen_npcs = set()
    seen_members = set()

    try:
        from utils.npc_name_canonicalizer import get_canonical_name
    except Exception:
        get_canonical_name = None

    for npc in party_tracker_data.get('partyNPCs', []):
        npc_name = npc.get('name', '') if isinstance(npc, dict) else str(npc)
        npc_name = str(npc_name or '').strip()
        if not npc_name:
            continue
        canonical_name = get_canonical_name(npc_name) if get_canonical_name else npc_name
        if canonical_name and canonical_name not in seen_npcs:
            party_npcs.append(canonical_name)
            seen_npcs.add(canonical_name)

    for member in party_tracker_data.get('partyMembers', []):
        identity = _build_party_member_identity(str(member))
        if not identity:
            continue
        if identity['key'] in seen_members:
            continue
        party_member_identities.append(identity)
        seen_members.add(identity['key'])

    return party_npcs, party_member_identities


def _edge_has_signal(edge_data: Any) -> bool:
    """Return True when a relationship edge contains usable continuity signal."""
    if not isinstance(edge_data, dict):
        return False

    for field in ('trust', 'respect', 'intimacy', 'fear', 'resentment'):
        if abs(_coerce_float(edge_data.get(field, 0.0))) > 0.0:
            return True

    recent_triggers = edge_data.get('recent_triggers', [])
    return isinstance(recent_triggers, list) and len(recent_triggers) > 0


def _has_usable_relationship_edges(edges: Any) -> bool:
    """Return True when any stored relationship edge contains signal."""
    if not isinstance(edges, dict):
        return False
    return any(_edge_has_signal(edge_data) for edge_data in edges.values())


def build_recent_meaningful_event(location: str, actions: List[Any], timestamp: str) -> Dict[str, str]:
    """Build a compact recent-event record for sparse/degraded fallback."""
    trigger_actions = []
    for action in actions:
        readable = action.get_readable_action()
        if readable and readable not in trigger_actions:
            trigger_actions.append(readable)

    summary = ', '.join(trigger_actions[:3]) if trigger_actions else 'meaningful interaction'
    if len(summary) > 90:
        summary = summary[:87] + '...'

    return {
        'timestamp': timestamp,
        'location': location,
        'summary': summary,
    }


def classify_npc_memory_data(data: Dict[str, Any]) -> str:
    """Classify raw NPC memory payload quality."""
    if not isinstance(data, dict):
        return MEMORY_QUALITY_MALFORMED

    npc_name = data.get('npc_name')
    core_memories = data.get('core_memories', [])
    emotional_state = data.get('current_emotional_state', {})
    behavioral_model = data.get('behavioral_model', {})
    total_interactions = data.get('total_interactions', 0)
    mention_count = data.get('mention_count', total_interactions)
    meaningful_count = data.get('meaningful_interaction_count', total_interactions)
    recent_events = data.get('recent_meaningful_events', [])
    relationship_edges = data.get('relationship_edges', {})

    if not isinstance(npc_name, str) or not npc_name.strip():
        return MEMORY_QUALITY_MALFORMED
    if not isinstance(core_memories, list):
        return MEMORY_QUALITY_MALFORMED
    if not isinstance(emotional_state, dict):
        return MEMORY_QUALITY_MALFORMED
    if not isinstance(behavioral_model, dict):
        return MEMORY_QUALITY_MALFORMED
    if not isinstance(recent_events, list):
        return MEMORY_QUALITY_MALFORMED
    if not isinstance(relationship_edges, dict):
        return MEMORY_QUALITY_MALFORMED

    try:
        meaningful_count = int(meaningful_count)
        mention_count = int(mention_count)
        int(total_interactions)
    except (TypeError, ValueError):
        return MEMORY_QUALITY_MALFORMED

    if core_memories or has_nonzero_emotional_state(emotional_state) or _has_usable_relationship_edges(relationship_edges):
        return MEMORY_QUALITY_HEALTHY
    if meaningful_count > 0 or len(recent_events) > 0:
        return MEMORY_QUALITY_DEGRADED
    if mention_count > 0:
        return MEMORY_QUALITY_SPARSE

    return MEMORY_QUALITY_SPARSE

class CompanionMemoryManager:
    """Manages the complete memory system for companion NPCs"""
    
    def __init__(self, mode='append', data_dir: Optional[str] = None):
        """Initialize the memory management system

        Args:
            mode: 'append' to add to existing memories, 'refresh' to rebuild from scratch
            data_dir: Optional override for companion memory storage path
        """
        self.mode = mode
        self.data_dir = Path(data_dir) if data_dir else Path('data/companion_memories')
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Core components
        self.action_parser = ActionParser()
        self.crystallizer = MemoryCrystallizer(crystallization_threshold=0.35)
        self.retrieval_system = GravitationalRetrieval()

        # Memory storage
        self.npc_memories: Dict[str, List[CoreMemory]] = defaultdict(list)
        self.npc_emotional_states: Dict[str, EmotionalVector] = defaultdict(EmotionalVector)
        self.npc_behavioral_models: Dict[str, Dict[str, float]] = defaultdict(self._init_behavioral_model)
        self.npc_global_resentment: Dict[str, float] = defaultdict(float)
        self.npc_relationship_edges: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        self.relationship_attribution_logs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.mention_counts: Dict[str, int] = defaultdict(int)
        self.interaction_counts: Dict[str, int] = defaultdict(int)
        self.recent_meaningful_events: Dict[str, List[Dict[str, str]]] = defaultdict(list)

        # Time tracking
        self.day_counter = 0
        self.last_date = None
        self.processed_entries = set()  # Track processed entries to avoid duplicates

        # Configuration
        self.config_file = self.data_dir / 'memory_config.json'

        if mode == 'refresh':
            # Clear everything for fresh start
            self.clear_all_data()
            self.crystallizer.memory_counter = 0
        else:
            self.load_configuration()
            # Load existing memories
            self.load_all_memories()

        debug("CompanionMemoryManager", f"Initialized Companion Memory System (mode: {mode})")
    
    def _init_behavioral_model(self) -> Dict[str, float]:
        """Initialize behavioral eigenvector model"""
        return {
            'protector_vs_exploiter': 0.0,
            'consistent_vs_chaotic': 0.0, 
            'generous_vs_greedy': 0.0,
            'truthful_vs_deceptive': 0.0,
            'violent_vs_peaceful': 0.0
        }
    
    def calculate_relative_day(self, journal_entry: Dict[str, Any]) -> int:
        """Calculate relative day number from journal entry"""
        current_date = journal_entry.get('date', '')

        # Update day counter if date changed
        if current_date != self.last_date:
            if self.last_date is not None:  # Not the first entry
                self.day_counter += 1
            self.last_date = current_date

        return self.day_counter

    def create_entry_hash(self, entry: Dict[str, Any]) -> str:
        """Create unique hash for entry to prevent duplicates"""
        return f"{entry.get('date', '')}_{entry.get('time', '')}_{entry.get('location', '')}"

    def is_duplicate_memory(self, new_memory: CoreMemory, existing_memories: List[CoreMemory]) -> bool:
        """Check if memory is a duplicate"""
        for existing in existing_memories:
            # Check if same timestamp and location with similar velocity
            if (existing.timestamp == new_memory.timestamp and
                existing.location == new_memory.location and
                abs(existing.emotional_velocity - new_memory.emotional_velocity) < 0.01):
                return True
        return False

    def process_journal_entry(self,
                            journal_entry: Dict[str, Any],
                            party_npcs: Optional[List[str]] = None,
                            party_members: Optional[List[Any]] = None) -> Dict[str, CoreMemory]:
        """Process a journal entry for memory extraction"""

        # Check for duplicate processing
        entry_hash = self.create_entry_hash(journal_entry)
        if entry_hash in self.processed_entries:
            debug("CompanionMemory", f"Skipping duplicate entry: {entry_hash}")
            return {}
        self.processed_entries.add(entry_hash)

        # Calculate relative day
        relative_day = self.calculate_relative_day(journal_entry)

        # Extract key information
        location = journal_entry.get('location', 'Unknown')

        # Use relative day in timestamp for better time tracking
        timestamp = f"Day {relative_day:03d} {journal_entry.get('time', '00:00:00')}"
        original_timestamp = f"{journal_entry.get('date', '')} {journal_entry.get('time', '')}"

        summary = journal_entry.get('summary', '')

        if not summary:
            return {}

        # Get list of NPCs to track (must be provided from party tracker)
        if not party_npcs:
            debug("CompanionMemory", "No party NPCs provided, skipping memory processing")
            return {}

        party_member_identities = self._prepare_party_member_identities(party_members)

        memories_created = {}
        state_changed = False

        # Process each NPC
        for npc_name in party_npcs:
            # Skip if NPC not mentioned
            if npc_name.lower() not in summary.lower():
                continue

            # Ensure state exists for mentioned NPCs and track story presence
            self.npc_memories[npc_name]
            self.npc_emotional_states[npc_name]
            self.npc_behavioral_models[npc_name]
            self.mention_counts[npc_name] += 1
            state_changed = True

            # Parse actions from journal
            actions = self.action_parser.parse_entry(summary, npc_name)

            if not actions:
                continue

            # Track meaningful interactions separately from story presence
            self.interaction_counts[npc_name] += 1

            recent_event = build_recent_meaningful_event(location, actions, original_timestamp)
            self.recent_meaningful_events[npc_name].append(recent_event)
            self.recent_meaningful_events[npc_name] = self.recent_meaningful_events[npc_name][-3:]
            state_changed = True

            attributed_edges = self._attribute_actions_to_party_members(summary, npc_name, party_member_identities)
            attributed_action_names = set()
            edge_keys = []
            for edge_key, edge_info in attributed_edges.items():
                edge_keys.append(edge_key)
                edge_actions = edge_info.get('actions', [])
                for action in edge_actions:
                    attributed_action_names.add(action.get_readable_action())
                if edge_actions:
                    self._update_relationship_edge_state(
                        npc_name,
                        edge_info,
                        edge_actions,
                        location,
                        original_timestamp,
                    )

            group_actions = self._select_group_actions(actions, attributed_action_names)
            if group_actions:
                self._update_group_relationship_state(
                    npc_name,
                    group_actions,
                    location,
                    original_timestamp,
                )

            attribution_mode = 'group_only'
            if attributed_edges and group_actions:
                attribution_mode = 'mixed'
            elif attributed_edges:
                attribution_mode = 'edge_only'

            self._record_attribution_event(
                npc_name,
                attribution_mode,
                location,
                original_timestamp,
                edge_keys,
                group_actions,
                attributed_action_names,
            )

            # Extract relevant excerpt
            excerpt = self._extract_excerpt(summary, npc_name)

            # Check for memory crystallization
            memory = self.crystallizer.check_crystallization(
                actions=actions,
                npc_name=npc_name,
                location=location,
                timestamp=original_timestamp,  # Keep original for display
                journal_excerpt=excerpt,
                current_emotional_state=self.npc_emotional_states[npc_name],
                existing_memories=self.npc_memories[npc_name]
            )

            if memory:
                # Add relative day for internal use
                memory.relative_day = relative_day

                # Check for duplicates before adding
                if not self.is_duplicate_memory(memory, self.npc_memories[npc_name]):
                    # Apply emotional decay based on time since last interaction
                    if self.npc_memories[npc_name]:
                        last_memory = self.npc_memories[npc_name][-1]
                        if hasattr(last_memory, 'relative_day'):
                            days_passed = relative_day - last_memory.relative_day
                            if days_passed > 0:
                                self.apply_emotional_decay(self.npc_emotional_states[npc_name], days_passed)

                    # Update behavioral model
                    self._update_behavioral_model(npc_name, actions)

                    # Store memory
                    self.npc_memories[npc_name].append(memory)

                    # Prune if needed (keep top 5)
                    self.npc_memories[npc_name] = self.crystallizer.prune_memories(
                        self.npc_memories[npc_name], max_count=5
                    )

                    memories_created[npc_name] = memory

                    info("CompanionMemory",
                         f"Day {relative_day}: Crystallized memory for {npc_name}: {memory.trigger_actions[:3]} (velocity: {memory.emotional_velocity})")
                else:
                    debug("CompanionMemory", f"Skipping duplicate memory for {npc_name}")

        # Save any changed companion state when appending incrementally
        if state_changed and self.mode != 'refresh':
            self.save_all_memories()

        return memories_created

    def apply_emotional_decay(self, emotion_vector: EmotionalVector, days_passed: int) -> None:
        """Apply decay to emotional state over time"""
        if days_passed <= 0:
            return

        # 3% decay per day (0.97 multiplier)
        decay_rate = 0.97 ** days_passed

        for emotion in emotion_vector.emotions:
            emotion_vector.emotions[emotion] *= decay_rate

        debug("CompanionMemory", f"Applied {days_passed} days of decay (rate: {decay_rate:.3f})")
    
    def _extract_excerpt(self, text: str, npc_name: str, context_chars: int = 100) -> str:
        """Extract relevant excerpt mentioning NPC"""
        match = re.search(rf'\b{npc_name}\b', text, re.IGNORECASE)
        if match:
            start = max(0, match.start() - context_chars)
            end = min(len(text), match.end() + context_chars)
            excerpt = text[start:end].strip()
            
            # Add ellipsis if truncated
            if start > 0:
                excerpt = '...' + excerpt
            if end < len(text):
                excerpt = excerpt + '...'
            
            return excerpt
        return text[:200] + '...' if len(text) > 200 else text

    def _prepare_party_member_identities(self, party_members: Optional[List[Any]]) -> List[Dict[str, Any]]:
        """Normalize party-member identity input for relationship attribution."""
        identities = []
        seen = set()

        for member in party_members or []:
            if isinstance(member, dict):
                identity = dict(member)
                display_name = str(identity.get('display_name') or identity.get('name') or '').strip()
                if not display_name:
                    continue
                identity.setdefault('display_name', display_name)
                identity.setdefault('normalized_name', _canonicalize_pc_name(display_name))
                identity.setdefault('character_id', str(identity.get('character_id', '')).strip())
                identity.setdefault('key', identity.get('character_id') or identity['normalized_name'])
                identity.setdefault('aliases', _build_party_member_aliases(display_name))
            else:
                identity = _build_party_member_identity(str(member))

            if not identity:
                continue

            key = str(identity.get('key', '')).strip()
            if not key or key in seen:
                continue
            identities.append(identity)
            seen.add(key)

        return identities

    def _extract_attribution_window(self, text: str, alias: str, radius: int = 90) -> Optional[str]:
        """Extract a local attribution window around a party-member alias."""
        if not alias:
            return None

        match = re.search(rf'\b{re.escape(alias)}\b', text, re.IGNORECASE)
        if not match:
            return None

        start = max(0, match.start() - radius)
        end = min(len(text), match.end() + radius)
        return text[start:end].strip()

    def _summarize_action_names(self, actions: List[Any]) -> List[str]:
        """Return bounded unique readable action names."""
        summaries = []
        seen = set()
        for action in actions:
            readable = str(action.get_readable_action() or '').strip()
            if not readable or readable in seen:
                continue
            summaries.append(readable)
            seen.add(readable)
        return summaries

    def _attribute_actions_to_party_members(self,
                                            summary: str,
                                            npc_name: str,
                                            party_member_identities: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Attribute companion-memory actions to specific PCs when evidence is strong."""
        attributed: Dict[str, Dict[str, Any]] = {}
        if not party_member_identities:
            return attributed

        sentence_candidates = re.split(r'(?<=[.!?])\s+', summary)
        candidate_fragments = [fragment.strip() for fragment in sentence_candidates if fragment.strip()]
        candidate_fragments.append(summary)

        for identity in party_member_identities:
            best_actions = []
            best_score = 0
            best_window = ''

            for alias in identity.get('aliases', []):
                for fragment in candidate_fragments:
                    if not re.search(rf'\b{re.escape(alias)}\b', fragment, re.IGNORECASE):
                        continue
                    if not re.search(rf'\b{re.escape(npc_name)}\b', fragment, re.IGNORECASE):
                        continue

                    window = self._extract_attribution_window(fragment, alias) or fragment
                    window_actions = self.action_parser.parse_entry(window, npc_name)
                    if not window_actions:
                        continue

                    specific_actions = []
                    for action in window_actions:
                        if action.get_readable_action() in GROUP_SHARED_ACTIONS:
                            continue
                        specific_actions.append(action)
                    if not specific_actions:
                        continue

                    score = len(specific_actions)
                    if re.search(rf'\b{re.escape(alias)}\b', window, re.IGNORECASE):
                        score += 1

                    if score > best_score:
                        best_actions = specific_actions
                        best_score = score
                        best_window = window

            if best_actions:
                attributed[identity['key']] = {
                    'key': identity['key'],
                    'display_name': identity['display_name'],
                    'character_id': identity.get('character_id', ''),
                    'actions': best_actions,
                    'window': best_window,
                }

        return attributed

    def _select_group_actions(self,
                              all_actions: List[Any],
                              attributed_action_names: set) -> List[Any]:
        """Keep group continuity actions plus unassigned actions."""
        group_actions = []
        seen = set()
        for action in all_actions:
            readable = action.get_readable_action()
            if not readable:
                continue
            if readable in seen:
                continue
            if readable in GROUP_SHARED_ACTIONS or readable not in attributed_action_names:
                group_actions.append(action)
                seen.add(readable)
        return group_actions

    def _calculate_resentment_delta(self, actions: List[Any]) -> float:
        """Approximate resentment drift from parsed actions."""
        resentment_delta = 0.0
        for action in actions:
            trust_delta = _coerce_float(action.emotional_impact.get('trust', 0.0))
            respect_delta = _coerce_float(action.emotional_impact.get('respect', 0.0))
            fear_delta = _coerce_float(action.emotional_impact.get('fear', 0.0))

            if action.action_type == 'negative':
                resentment_delta += abs(min(trust_delta, 0.0))
                resentment_delta += abs(min(respect_delta, 0.0)) * 0.75
                resentment_delta += max(fear_delta, 0.0) * 0.4
            elif action.action_type == 'positive':
                resentment_delta -= max(trust_delta, 0.0) * 0.25
                resentment_delta -= max(respect_delta, 0.0) * 0.2

        return resentment_delta

    def _update_group_relationship_state(self,
                                         npc_name: str,
                                         actions: List[Any],
                                         location: str,
                                         timestamp: str) -> None:
        """Update group continuity state for ambiguous or party-wide beats."""
        if not actions:
            return

        for action in actions:
            for emotion, value in action.emotional_impact.items():
                self.npc_emotional_states[npc_name].add(emotion, value)

        resentment = self.npc_global_resentment.get(npc_name, 0.0)
        resentment += self._calculate_resentment_delta(actions)
        self.npc_global_resentment[npc_name] = max(0.0, min(1.0, resentment))

    def _get_relationship_edge_state(self,
                                     npc_name: str,
                                     edge_key: str,
                                     display_name: str,
                                     character_id: str) -> Dict[str, Any]:
        """Get or initialize per-PC relationship edge state."""
        existing = self.npc_relationship_edges[npc_name].get(edge_key)
        if isinstance(existing, dict):
            existing.setdefault('display_name', display_name)
            existing.setdefault('character_id', character_id)
            existing.setdefault('recent_triggers', [])
            return existing

        edge_state = {
            'display_name': display_name,
            'character_id': character_id,
            'trust': 0.0,
            'respect': 0.0,
            'intimacy': 0.0,
            'fear': 0.0,
            'resentment': 0.0,
            'recent_triggers': [],
            'last_significant_interaction': '',
        }
        self.npc_relationship_edges[npc_name][edge_key] = edge_state
        return edge_state

    def _update_relationship_edge_state(self,
                                        npc_name: str,
                                        edge_info: Dict[str, Any],
                                        actions: List[Any],
                                        location: str,
                                        timestamp: str) -> None:
        """Apply specific-PC relationship edge updates."""
        edge_state = self._get_relationship_edge_state(
            npc_name,
            edge_info['key'],
            edge_info.get('display_name', edge_info['key']),
            edge_info.get('character_id', ''),
        )

        for action in actions:
            edge_state['trust'] = max(-1.0, min(1.0, _coerce_float(edge_state.get('trust', 0.0)) + _coerce_float(action.emotional_impact.get('trust', 0.0))))
            edge_state['respect'] = max(-1.0, min(1.0, _coerce_float(edge_state.get('respect', 0.0)) + _coerce_float(action.emotional_impact.get('respect', 0.0))))
            edge_state['intimacy'] = max(0.0, min(1.0, _coerce_float(edge_state.get('intimacy', 0.0)) + _coerce_float(action.emotional_impact.get('intimacy', 0.0))))
            edge_state['fear'] = max(0.0, min(1.0, _coerce_float(edge_state.get('fear', 0.0)) + _coerce_float(action.emotional_impact.get('fear', 0.0))))

        resentment = _coerce_float(edge_state.get('resentment', 0.0))
        resentment += self._calculate_resentment_delta(actions)
        edge_state['resentment'] = round(max(0.0, min(1.0, resentment)), 3)
        edge_state['last_significant_interaction'] = timestamp

        triggers = edge_state.get('recent_triggers', [])
        if not isinstance(triggers, list):
            triggers = []
        for action_name in self._summarize_action_names(actions):
            trigger_text = f"{action_name}@{location[:40]}"
            if trigger_text in triggers:
                continue
            triggers.append(trigger_text)
        edge_state['recent_triggers'] = triggers[-RELATIONSHIP_TRIGGER_LIMIT:]

    def _record_attribution_event(self,
                                  npc_name: str,
                                  mode: str,
                                  location: str,
                                  timestamp: str,
                                  edge_keys: List[str],
                                  group_actions: List[Any],
                                  attributed_action_names: set) -> None:
        """Record bounded attribution diagnostics for rebuild and tests."""
        log_entry = {
            'timestamp': timestamp,
            'location': location,
            'mode': mode,
            'edge_keys': sorted(edge_keys),
            'group_actions': self._summarize_action_names(group_actions),
            'edge_actions': sorted(attributed_action_names),
        }
        self.relationship_attribution_logs[npc_name].append(log_entry)
        self.relationship_attribution_logs[npc_name] = self.relationship_attribution_logs[npc_name][-ATTRIBUTION_LOG_LIMIT:]
        debug(
            "CompanionMemory",
            f"REL_EDGE npc={npc_name} mode={mode} edges={','.join(sorted(edge_keys)) or 'none'}",
        )

    def _update_behavioral_model(self, npc_name: str, actions: List[Any]) -> None:
        """Update behavioral eigenvector model based on actions"""
        model = self.npc_behavioral_models[npc_name]
        
        for action in actions:
            # Analyze action for behavioral patterns
            action_text = action.get_readable_action().lower()
            
            # Protector vs Exploiter
            if any(word in action_text for word in ['protect', 'defend', 'heal', 'rescue']):
                model['protector_vs_exploiter'] += 0.1
            elif any(word in action_text for word in ['abandon', 'betray', 'exploit']):
                model['protector_vs_exploiter'] -= 0.2
            
            # Consistent vs Chaotic
            if any(word in action_text for word in ['trust', 'promise', 'reliable']):
                model['consistent_vs_chaotic'] += 0.1
            elif any(word in action_text for word in ['betray', 'unpredictable']):
                model['consistent_vs_chaotic'] -= 0.2
            
            # Generous vs Greedy
            if any(word in action_text for word in ['share', 'give', 'generous']):
                model['generous_vs_greedy'] += 0.1
            elif any(word in action_text for word in ['steal', 'hoard', 'greedy']):
                model['generous_vs_greedy'] -= 0.2
            
            # Truthful vs Deceptive
            # Note: Check for positive patterns first, then negative
            if any(word in action_text for word in ['honest', 'truth', 'confide', 'admitted', 'shared secret']):
                model['truthful_vs_deceptive'] += 0.1
            elif any(word in action_text for word in ['lied', 'betrayed trust']):
                # Don't trigger on "deceived ally" which means enemy deceived the ally
                model['truthful_vs_deceptive'] -= 0.2
            elif 'deceived ally' in action_text:
                # This means someone else deceived the NPC - no change
                pass

            # Violent vs Peaceful
            if any(word in action_text for word in ['peaceful', 'calm', 'gentle', 'comfort', 'reassurance']):
                model['violent_vs_peaceful'] += 0.1
            elif any(word in action_text for word in ['violent', 'aggressive', 'cruel', 'brutal']):
                model['violent_vs_peaceful'] -= 0.2
            elif any(word in action_text for word in ['combat', 'attack', 'fight']):
                # Combat actions are neutral, not violent
                pass
        
        # Clamp values
        for key in model:
            model[key] = max(-1.0, min(1.0, model[key]))
    
    def get_relevant_memories(self,
                             npc_name: str,
                             current_situation: Dict[str, Any],
                             max_memories: int = 3) -> List[CoreMemory]:
        """Retrieve most relevant memories for current situation"""
        
        if npc_name not in self.npc_memories:
            return []
        
        memories = self.npc_memories[npc_name]
        if not memories:
            return []
        
        # Use gravitational retrieval
        relevant = self.retrieval_system.retrieve_memories(
            memories, current_situation, max_memories
        )
        
        # Return just the memories (not the pull values)
        return [memory for memory, pull in relevant]
    
    def get_npc_profile(self, npc_name: str) -> Dict[str, Any]:
        """Get complete emotional and behavioral profile for an NPC"""
        
        profile = {
            'name': npc_name,
            'total_interactions': self.interaction_counts.get(npc_name, 0),
            'mention_count': self.mention_counts.get(npc_name, self.interaction_counts.get(npc_name, 0)),
            'meaningful_interaction_count': self.interaction_counts.get(npc_name, 0),
            'core_memories': len(self.npc_memories.get(npc_name, [])),
            'emotional_state': self.npc_emotional_states[npc_name].to_dict() if npc_name in self.npc_emotional_states else {},
            'npc_global_state': _build_global_state(
                self.npc_emotional_states[npc_name].to_dict() if npc_name in self.npc_emotional_states else {},
                self.npc_global_resentment.get(npc_name, 0.0),
            ),
            'relationship_edges': self.npc_relationship_edges.get(npc_name, {}),
            'relationship_attribution_log': self.relationship_attribution_logs.get(npc_name, []),
            'behavioral_model': self.npc_behavioral_models.get(npc_name, {}),
            'relationship_status': self._determine_relationship(npc_name),
            'strongest_memory': None,
            'recent_meaningful_events': self.recent_meaningful_events.get(npc_name, []),
        }
        profile['memory_quality'] = classify_npc_memory_data({
            'npc_name': npc_name,
            'core_memories': [m.to_dict() for m in self.npc_memories.get(npc_name, [])],
            'current_emotional_state': profile['emotional_state'],
            'behavioral_model': profile['behavioral_model'],
            'total_interactions': profile['total_interactions'],
            'mention_count': profile['mention_count'],
            'meaningful_interaction_count': profile['meaningful_interaction_count'],
            'recent_meaningful_events': profile['recent_meaningful_events'],
            'relationship_edges': profile['relationship_edges'],
        })
        
        # Add strongest memory if exists
        if npc_name in self.npc_memories and self.npc_memories[npc_name]:
            strongest = max(self.npc_memories[npc_name], 
                          key=lambda m: m.emotional_velocity)
            profile['strongest_memory'] = strongest.to_dict()
        
        return profile
    
    def _determine_relationship(self, npc_name: str) -> List[str]:
        """Determine relationship status based on emotional state"""
        
        if npc_name not in self.npc_emotional_states:
            return ['Acquaintance']
        
        state = self.npc_emotional_states[npc_name]
        relationships = []
        
        if state.emotions['trust'] > 0.5:
            relationships.append('Trusted Ally')
        elif state.emotions['trust'] > 0.3:
            relationships.append('Friend')
        elif state.emotions['trust'] < -0.3:
            relationships.append('Distrusted')
        
        if state.emotions['respect'] > 0.4:
            relationships.append('Respected')
        elif state.emotions['respect'] < -0.3:
            relationships.append('Disrespected')
        
        if state.emotions['intimacy'] > 0.5:
            relationships.append('Close Bond')
        elif state.emotions['intimacy'] > 0.3:
            relationships.append('Growing Closeness')
        
        if state.emotions['fear'] > 0.4:
            relationships.append('Feared')
        
        if state.emotions['power'] > 0.4:
            relationships.append('Leader')
        elif state.emotions['power'] < -0.4:
            relationships.append('Follower')
        
        return relationships if relationships else ['Neutral']
    
    def save_all_memories(self) -> None:
        """Save all memories to disk"""
        
        npc_names = set(self.npc_memories.keys())
        npc_names.update(self.npc_emotional_states.keys())
        npc_names.update(self.npc_behavioral_models.keys())
        npc_names.update(self.npc_global_resentment.keys())
        npc_names.update(self.npc_relationship_edges.keys())
        npc_names.update(self.relationship_attribution_logs.keys())
        npc_names.update(self.interaction_counts.keys())
        npc_names.update(self.mention_counts.keys())
        npc_names.update(self.recent_meaningful_events.keys())

        for npc_name in sorted(npc_names):
            self.save_npc_memories(npc_name)
        
        # Save configuration
        self.save_configuration()
    
    def save_npc_memories(self, npc_name: str) -> None:
        """Save memories for a specific NPC"""
        
        core_memories = [m.to_dict() for m in self.npc_memories.get(npc_name, [])]
        emotional_state = self.npc_emotional_states[npc_name].to_dict() if npc_name in self.npc_emotional_states else {}
        behavioral_model = self.npc_behavioral_models.get(npc_name, {})
        total_interactions = self.interaction_counts.get(npc_name, 0)
        mention_count = self.mention_counts.get(npc_name, total_interactions)
        recent_events = self.recent_meaningful_events.get(npc_name, [])
        relationship_edges = self.npc_relationship_edges.get(npc_name, {})
        attribution_log = self.relationship_attribution_logs.get(npc_name, [])

        filename = self.data_dir / f"{npc_name.lower().replace(' ', '_')}_memories.json"

        data = {
            'npc_name': npc_name,
            'core_memories': core_memories,
            'current_emotional_state': emotional_state,
            'npc_global_state': _build_global_state(emotional_state, self.npc_global_resentment.get(npc_name, 0.0)),
            'relationship_edges': relationship_edges,
            'relationship_attribution_log': attribution_log,
            'behavioral_model': behavioral_model,
            'total_interactions': total_interactions,
            'meaningful_interaction_count': total_interactions,
            'mention_count': mention_count,
            'crystallized_memory_count': len(core_memories),
            'recent_meaningful_events': recent_events,
        }
        data['memory_quality'] = classify_npc_memory_data(data)
        
        safe_json_dump(data, filename)
        debug("CompanionMemory", f"Saved memories for {npc_name}")
    
    def load_all_memories(self) -> None:
        """Load all memories from disk"""
        
        for filepath in self.data_dir.glob('*_memories.json'):
            if filepath.name != 'memory_config.json':
                self.load_npc_memories(filepath)
    
    def load_npc_memories(self, filepath: Path) -> None:
        """Load memories for a specific NPC"""
        
        data = safe_json_load(filepath)
        if not data:
            return
        
        npc_name = data.get('npc_name')
        if not npc_name:
            return
        
        # Load memories
        self.npc_memories[npc_name] = [
            CoreMemory.from_dict(m) for m in data.get('core_memories', [])
        ]
        
        # Load emotional state
        if 'current_emotional_state' in data:
            self.npc_emotional_states[npc_name].from_dict(data['current_emotional_state'])

        npc_global_state = data.get('npc_global_state', {})
        if isinstance(npc_global_state, dict):
            self.npc_global_resentment[npc_name] = max(0.0, min(1.0, _coerce_float(npc_global_state.get('resentment', 0.0))))

        # Load behavioral model
        if 'behavioral_model' in data:
            self.npc_behavioral_models[npc_name] = data['behavioral_model']

        relationship_edges = data.get('relationship_edges', {})
        if isinstance(relationship_edges, dict):
            self.npc_relationship_edges[npc_name] = relationship_edges

        # Load interaction counts
        total_interactions = _coerce_int(data.get('meaningful_interaction_count', data.get('total_interactions', 0)))
        mention_count = _coerce_int(data.get('mention_count', total_interactions), total_interactions)
        self.interaction_counts[npc_name] = total_interactions
        self.mention_counts[npc_name] = mention_count

        recent_events = data.get('recent_meaningful_events', [])
        if isinstance(recent_events, list):
            self.recent_meaningful_events[npc_name] = recent_events[-3:]

        attribution_log = data.get('relationship_attribution_log', [])
        if isinstance(attribution_log, list):
            self.relationship_attribution_logs[npc_name] = attribution_log[-ATTRIBUTION_LOG_LIMIT:]

        debug("CompanionMemory", f"Loaded {len(self.npc_memories[npc_name])} memories for {npc_name}")
    
    def save_configuration(self) -> None:
        """Save system configuration"""
        
        config = {
            'crystallization_threshold': self.crystallizer.crystallization_threshold,
            'max_memories_per_npc': 5,
            'retrieval_pull_threshold': self.retrieval_system.pull_threshold,
            'total_memories_created': self.crystallizer.memory_counter,
            'npc_interaction_counts': dict(self.interaction_counts),
            'npc_mention_counts': dict(self.mention_counts)
        }
        
        safe_json_dump(config, self.config_file)
    
    def load_configuration(self) -> None:
        """Load system configuration"""
        
        if not self.config_file.exists():
            return
        
        config = safe_json_load(self.config_file)
        if not config:
            return
        
        # Apply configuration
        if 'crystallization_threshold' in config:
            self.crystallizer.crystallization_threshold = config['crystallization_threshold']
        
        if 'retrieval_pull_threshold' in config:
            self.retrieval_system.pull_threshold = config['retrieval_pull_threshold']
        
        if 'total_memories_created' in config:
            self.crystallizer.memory_counter = config['total_memories_created']
        
        if 'npc_interaction_counts' in config:
            self.interaction_counts.update(config['npc_interaction_counts'])

        if 'npc_mention_counts' in config:
            self.mention_counts.update(config['npc_mention_counts'])
    
    def clear_npc_memories(self, npc_name: str) -> None:
        """Clear all memories for a specific NPC"""
        
        if npc_name in self.npc_memories:
            del self.npc_memories[npc_name]
        
        if npc_name in self.npc_emotional_states:
            del self.npc_emotional_states[npc_name]
        
        if npc_name in self.npc_behavioral_models:
            del self.npc_behavioral_models[npc_name]

        if npc_name in self.npc_global_resentment:
            del self.npc_global_resentment[npc_name]

        if npc_name in self.npc_relationship_edges:
            del self.npc_relationship_edges[npc_name]

        if npc_name in self.relationship_attribution_logs:
            del self.relationship_attribution_logs[npc_name]
        
        if npc_name in self.interaction_counts:
            del self.interaction_counts[npc_name]

        if npc_name in self.mention_counts:
            del self.mention_counts[npc_name]

        if npc_name in self.recent_meaningful_events:
            del self.recent_meaningful_events[npc_name]
        
        # Delete file
        filename = self.data_dir / f"{npc_name.lower().replace(' ', '_')}_memories.json"
        if filename.exists():
            filename.unlink()
        
        info("CompanionMemory", f"Cleared all memories for {npc_name}")

    def clear_all_data(self) -> None:
        """Clear all memory data for fresh rebuild"""
        # Clear in-memory data
        self.npc_memories.clear()
        self.npc_emotional_states.clear()
        self.npc_behavioral_models.clear()
        self.npc_global_resentment.clear()
        self.npc_relationship_edges.clear()
        self.relationship_attribution_logs.clear()
        self.mention_counts.clear()
        self.interaction_counts.clear()
        self.recent_meaningful_events.clear()
        self.processed_entries.clear()

        # Reset counters
        self.day_counter = 0
        self.last_date = None

        # Clear files
        for filepath in self.data_dir.glob('*.json'):
            filepath.unlink()

        info("CompanionMemory", "Cleared all memory data for fresh rebuild")
