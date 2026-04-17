"""
Companion Memory Core System
A deterministic memory system for companion NPCs based on emotional physics.
"""

from .emotional_vectors import EmotionalVector, EmotionalDimensions
from .action_parser import ActionParser
from .memory_crystallizer import MemoryCrystallizer
from .memory_gravity import MemoryGravity
from .companion_memory import CompanionMemoryManager

__all__ = [
    'EmotionalVector',
    'EmotionalDimensions',
    'ActionParser',
    'MemoryCrystallizer',
    'MemoryGravity',
    'CompanionMemoryManager'
]