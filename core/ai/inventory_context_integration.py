#!/usr/bin/env python3
"""
Integration module for the DM's player line
Builds the DM note with the player's own words and, for a rule the player names, the SRD block
"""

from core.ai.srd_reference import SRDContextMatcher
from utils.enhanced_logger import debug, warning

# Cached SRD matcher instance to avoid re-initialization
_srd_context_matcher = None

def initialize_srd_context_matcher():
    """Initialize the cached deterministic SRD matcher."""
    global _srd_context_matcher
    if _srd_context_matcher is None:
        _srd_context_matcher = SRDContextMatcher()
        debug("SRD context matcher initialized", category="srd_context")
    return _srd_context_matcher


def build_srd_context(user_input_text, character_data=None, structured_names=None):
    """Build a bounded SRD block for an explicit rule mention, if any."""
    try:
        result = initialize_srd_context_matcher().context_for(
            user_input_text,
            actor_sheet=character_data,
            structured_names=structured_names,
        )
        matches = result.get("matches") or []
        if matches:
            debug(
                "Added SRD context for rule IDs: %s"
                % ", ".join(match["ruleId"] for match in matches),
                category="srd_context",
            )
        return result.get("context") or ""
    except Exception as exc:
        warning("SRD context unavailable: %s" % exc, category="srd_context")
        return ""


def build_enhanced_dm_note(dm_note, user_input_text, character_data=None, srd_context=None):
    """The DM note, then the player's own words, then the SRD block for a
    rule named in those words. The words are never annotated with guessed
    inventory items (D-KW-5); the DM sees every item on the party sheets."""
    if srd_context is None:
        srd_context = build_srd_context(user_input_text, character_data)
    player_line = user_input_text
    if srd_context:
        player_line = "%s\n\n%s" % (player_line, srd_context)
    return f"{dm_note} Player: {player_line}"
