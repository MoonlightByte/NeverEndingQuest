#!/usr/bin/env python3
"""
Enhanced Memory Crystallizer
Detects high-velocity emotional moments and creates core memories with enhanced metadata.
"""

import math
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime

from core.memories.emotional_vectors import EmotionalVector
from core.memories.enhanced_action_parser import ParsedAction

@dataclass
class EnhancedCoreMemory:
    """Enhanced core memory with additional metadata"""
    id: str
    timestamp: str
    location: str
    npc_name: str
    trigger_actions: List[str]
    emotional_vector: Dict[str, float]
    emotional_velocity: float
    mass: float  # Emotional significance
    decay_resistance: float
    journal_excerpt: str
    context: str
    cascade_type: Optional[str] = None  # REVERSAL, CONFIRMATION, COMPLEXITY
    context_tags: List[str] = field(default_factory=list)
    attribution: Dict[str, str] = field(default_factory=dict)  # Action -> attribution
    interaction_number: int = 0
    reinforcement_count: int = 0  # How many times this memory has been reinforced
    relationship_phase: str = "developing"  # strangers, allies, friends, romantic_developing, romantic_established

class EnhancedMemoryCrystallizer:
    """Creates core memories from high-velocity emotional events with enhanced tracking"""

    def __init__(self, crystallization_threshold: float = 0.35):
        self.crystallization_threshold = crystallization_threshold
        self.memory_clusters = {}  # Track thematic clusters
        self.relationship_arc = {}  # Track relationship progression

    def detect_crystallization(
        self,
        actions: List[ParsedAction],
        emotional_delta: EmotionalVector,
        previous_state: EmotionalVector,
        timestamp: str,
        location: str,
        npc_name: str,
        journal_excerpt: str = "",
        interaction_number: int = 0
    ) -> Optional[EnhancedCoreMemory]:
        """Detect if this moment should crystallize into a core memory"""

        # Calculate emotional velocity
        velocity = emotional_delta.magnitude()

        # Check for climactic moments (lower threshold)
        has_climactic = any('climactic' in action.context_tags for action in actions)
        effective_threshold = self.crystallization_threshold * 0.7 if has_climactic else self.crystallization_threshold

        if velocity < effective_threshold:
            return None

        # Detect cascade type
        cascade_type = self._detect_cascade(emotional_delta, previous_state)

        # Calculate memory mass (significance)
        mass = self._calculate_mass(velocity, cascade_type, has_climactic)

        # Calculate decay resistance
        decay_resistance = self._calculate_decay_resistance(
            emotional_delta, cascade_type, has_climactic
        )

        # Create readable action list with proper filtering
        trigger_actions = []
        seen_actions = set()
        attribution_map = {}

        for action in actions:
            readable = action.get_readable_action()
            if readable and len(readable) >= 4 and readable not in seen_actions:
                trigger_actions.append(readable)
                seen_actions.add(readable)
                attribution_map[readable] = action.attribution

        # Collect all context tags
        all_tags = []
        for action in actions:
            all_tags.extend(action.context_tags)
        unique_tags = list(set(all_tags))

        # Determine relationship phase
        relationship_phase = self._determine_relationship_phase(
            emotional_delta, previous_state, unique_tags, npc_name
        )

        # Create context summary
        context = self._create_context_summary(
            actions, location, cascade_type, unique_tags
        )

        # Check for memory reinforcement
        reinforcement_count = self._check_reinforcement(
            trigger_actions, npc_name, location
        )

        memory = EnhancedCoreMemory(
            id=f"{npc_name.lower()}_mem_{interaction_number:03d}",
            timestamp=timestamp,
            location=location,
            npc_name=npc_name,
            trigger_actions=trigger_actions,
            emotional_vector=emotional_delta.to_dict(),
            emotional_velocity=round(velocity, 2),
            mass=round(mass, 2),
            decay_resistance=decay_resistance,
            journal_excerpt=journal_excerpt[:200] if journal_excerpt else "",
            context=context,
            cascade_type=cascade_type,
            context_tags=unique_tags,
            attribution=attribution_map,
            interaction_number=interaction_number,
            reinforcement_count=reinforcement_count,
            relationship_phase=relationship_phase
        )

        # Update memory clusters
        self._update_clusters(memory)

        return memory

    def _detect_cascade(
        self,
        delta: EmotionalVector,
        previous: EmotionalVector
    ) -> Optional[str]:
        """Detect emotional cascade patterns"""

        # Check for reversal
        trust_reversal = (
            previous.emotions.get('trust', 0) > 0.5 and
            delta.emotions.get('trust', 0) < -0.3
        )
        if trust_reversal:
            return "REVERSAL"

        # Check for confirmation
        trust_building = (
            previous.emotions.get('trust', 0) > 0.3 and
            delta.emotions.get('trust', 0) > 0.3
        )
        intimacy_building = (
            previous.emotions.get('intimacy', 0) > 0.3 and
            delta.emotions.get('intimacy', 0) > 0.3
        )
        if trust_building or intimacy_building:
            return "CONFIRMATION"

        # Check for complexity (mixed emotions)
        has_positive = any(v > 0.3 for v in delta.emotions.values())
        has_negative = any(v < -0.2 for v in delta.emotions.values())
        has_fear = delta.emotions.get('fear', 0) > 0.2

        if (has_positive and has_negative) or (has_positive and has_fear):
            return "COMPLEXITY"

        return None

    def _calculate_mass(
        self,
        velocity: float,
        cascade_type: Optional[str],
        has_climactic: bool
    ) -> float:
        """Calculate emotional mass (significance) of the memory"""
        base_mass = velocity

        # Cascade multipliers
        if cascade_type == "REVERSAL":
            base_mass *= 1.5
        elif cascade_type == "COMPLEXITY":
            base_mass *= 1.3
        elif cascade_type == "CONFIRMATION":
            base_mass *= 1.1

        # Climactic bonus
        if has_climactic:
            base_mass *= 1.4

        return base_mass

    def _calculate_decay_resistance(
        self,
        delta: EmotionalVector,
        cascade_type: Optional[str],
        has_climactic: bool
    ) -> float:
        """Calculate how resistant this memory is to decay"""
        resistance = 1.0

        # Traumatic memories decay slower
        if delta.emotions.get('fear', 0) > 0.3:
            resistance = 1.5

        # Love/intimacy memories persist
        if delta.emotions.get('intimacy', 0) > 0.5:
            resistance = 1.3

        # Complex emotions are memorable
        if cascade_type == "COMPLEXITY":
            resistance *= 1.2

        # Climactic moments persist
        if has_climactic:
            resistance *= 1.3

        return min(resistance, 2.0)  # Cap at 2.0

    def _determine_relationship_phase(
        self,
        delta: EmotionalVector,
        previous: EmotionalVector,
        tags: List[str],
        npc_name: str
    ) -> str:
        """Determine current relationship phase"""

        total_trust = previous.emotions.get('trust', 0)
        total_intimacy = previous.emotions.get('intimacy', 0)

        # Check for romantic tags
        has_romantic = any(tag in ['romantic', 'intimate', 'kiss'] for tag in tags)

        # Determine phase
        if total_trust < 0.2 and total_intimacy < 0.2:
            return "strangers"
        elif has_romantic and total_intimacy > 0.7:
            return "romantic_established"
        elif has_romantic and total_intimacy > 0.3:
            return "romantic_developing"
        elif total_trust > 0.5 and total_intimacy > 0.4:
            return "close_friends"
        elif total_trust > 0.3:
            return "friends"
        else:
            return "allies"

    def _create_context_summary(
        self,
        actions: List[ParsedAction],
        location: str,
        cascade_type: Optional[str],
        tags: List[str]
    ) -> str:
        """Create a summary of the memory's context"""

        # Determine primary context
        if 'trauma' in tags or 'captivity' in tags:
            context_type = "Traumatic experience"
        elif 'romantic' in tags and 'climactic' in tags:
            context_type = "Romantic climax"
        elif 'victory' in tags and 'climactic' in tags:
            context_type = "Major victory"
        elif 'romantic' in tags:
            context_type = "Romantic moment"
        elif 'combat' in tags and 'teamwork' in tags:
            context_type = "Combat teamwork"
        elif 'vulnerable' in tags:
            context_type = "Trust-building moment"
        elif 'betrayal' in tags:
            context_type = "Betrayal"
        elif any(action.action_type == 'negative' for action in actions):
            context_type = "Mixed interactions"
        else:
            context_type = "Positive interaction"

        summary = f"{context_type} at {location}"

        if cascade_type:
            summary += f" ({cascade_type})"

        return summary

    def _check_reinforcement(
        self,
        trigger_actions: List[str],
        npc_name: str,
        location: str
    ) -> int:
        """Check if this memory reinforces existing memories"""
        reinforcement_count = 0

        # Check memory clusters for similar patterns
        for cluster_name, cluster_memories in self.memory_clusters.get(npc_name, {}).items():
            for existing_memory in cluster_memories:
                # Check for similar actions
                action_overlap = len(set(trigger_actions) & set(existing_memory.get('actions', [])))
                if action_overlap >= 2:
                    reinforcement_count += 1

                # Check for same location pattern
                if location in existing_memory.get('locations', []):
                    reinforcement_count += 1

        return reinforcement_count

    def _update_clusters(self, memory: EnhancedCoreMemory):
        """Update thematic memory clusters"""
        if memory.npc_name not in self.memory_clusters:
            self.memory_clusters[memory.npc_name] = {}

        # Determine cluster themes
        clusters_to_add = []

        if 'trauma' in memory.context_tags or 'captivity' in memory.context_tags:
            clusters_to_add.append('trauma_memories')
        if 'romantic' in memory.context_tags:
            clusters_to_add.append('romantic_memories')
        if 'combat' in memory.context_tags and 'teamwork' in memory.context_tags:
            clusters_to_add.append('combat_teamwork')
        if 'vulnerable' in memory.context_tags or 'trust_building' in memory.context_tags:
            clusters_to_add.append('vulnerability_bonding')
        if 'victory' in memory.context_tags:
            clusters_to_add.append('shared_victories')

        # Add to appropriate clusters
        for cluster_name in clusters_to_add:
            if cluster_name not in self.memory_clusters[memory.npc_name]:
                self.memory_clusters[memory.npc_name][cluster_name] = []

            cluster_entry = {
                'id': memory.id,
                'actions': memory.trigger_actions,
                'locations': [memory.location],
                'velocity': memory.emotional_velocity
            }
            self.memory_clusters[memory.npc_name][cluster_name].append(cluster_entry)

    def apply_decay_with_reinforcement(
        self,
        emotion_value: float,
        days_passed: int,
        reinforcement_count: int,
        decay_resistance: float
    ) -> float:
        """Apply decay with reinforcement consideration"""
        # Base decay rate
        base_decay_rate = 0.03

        # Reduce decay for reinforced memories
        reinforcement_factor = 1.0 + (reinforcement_count * 0.2)

        # Apply decay resistance
        effective_resistance = decay_resistance * reinforcement_factor

        # Calculate decay
        decay_amount = (base_decay_rate * days_passed) / effective_resistance

        # Apply decay (moves toward 0)
        if emotion_value > 0:
            return max(0, emotion_value - decay_amount)
        else:
            return min(0, emotion_value + decay_amount)

    def get_memory_clusters(self, npc_name: str) -> Dict[str, List]:
        """Get thematic memory clusters for an NPC"""
        return self.memory_clusters.get(npc_name, {})