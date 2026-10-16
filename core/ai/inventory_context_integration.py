#!/usr/bin/env python3
"""
Integration module for the DM's player line
Builds the DM note with the player's own words
"""


def build_enhanced_dm_note(dm_note, user_input_text):
    """The DM note, then the player's own words. The words are never annotated
    with guessed inventory items or a word-matched SRD block (D-KW-5); the DM
    sees every item and spell on the party sheets."""
    return f"{dm_note} Player: {user_input_text}"
