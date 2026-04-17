#!/usr/bin/env python3
"""
NPC Name Normalizer - Word-based exact matching
Matches INPUT name TO party tracker names using exact word containment

Strategy:
- "Alice" matches "Scout Alice" (word "Alice" found)
- "Alice" REJECTS if both "Scout Alice" and "Scout Alice Junior" exist (multiple matches)
- "Ranger Alice" matches "Scout Alice" (word "Alice" found, ignore title difference)
- "Alicia" does NOT match "Scout Alice" (no exact word match)

Related: GitHub Issue #108
"""

def normalize_npc_name_for_action(input_name, party_tracker_data, debug_print=False):
    """
    Normalize NPC name from AI action to party tracker canonical name.

    Args:
        input_name: Name from updateCharacterInfo action
        party_tracker_data: Party tracker JSON
        debug_print: Print debug info

    Returns:
        (canonical_name, match_type) or (None, "no_match")
        match_type: "exact", "word_match", "no_match"
    """

    if not input_name or not isinstance(input_name, str):
        if debug_print:
            print(f"[NPC_NORM] REJECT: Invalid input")
        return None, "no_match"

    input_clean = input_name.strip()
    input_lower = input_clean.lower()

    if debug_print:
        print(f"[NPC_NORM] Input: '{input_name}'")

    # Extract party member and NPC names
    party_members = party_tracker_data.get('partyMembers', [])
    party_npcs = party_tracker_data.get('partyNPCs', [])

    valid_names = []
    valid_names.extend(party_members)
    valid_names.extend([npc.get('name', '') for npc in party_npcs if npc.get('name')])

    if debug_print:
        print(f"[NPC_NORM] Valid names: {valid_names}")

    if not valid_names:
        if debug_print:
            print(f"[NPC_NORM] REJECT: No party members or NPCs")
        return None, "no_match"

    # STEP 1: Exact match (case-insensitive)
    for valid_name in valid_names:
        # Direct match
        if valid_name.lower() == input_lower:
            if debug_print:
                print(f"[NPC_NORM] EXACT MATCH: '{valid_name}'")
            return valid_name, "exact"

        # Player character: handle underscore format
        # "testplayer_main" matches "TestPlayer Main" or "testplayer main"
        if '_' in valid_name:
            valid_spaced = valid_name.replace('_', ' ')
            if valid_spaced.lower() == input_lower:
                if debug_print:
                    print(f"[NPC_NORM] EXACT MATCH (underscore): '{valid_name}'")
                return valid_name, "exact"

    # STEP 2: Word-based matching with title handling
    input_words_list = input_lower.replace('_', ' ').split()

    if debug_print:
        print(f"[NPC_NORM] Input words: {input_words_list}")

    # Try matching with different word combinations
    # For "Ranger Alice": try ["ranger", "alice"] and ["alice"] (drop first word)
    word_combinations_to_try = [
        set(input_words_list),  # All words: ["ranger", "kira"]
    ]

    # If multi-word, also try without first word (drops title)
    if len(input_words_list) > 1:
        word_combinations_to_try.append(set(input_words_list[1:]))  # Drop first: ["kira"]

    # If multi-word, also try without last word
    if len(input_words_list) > 1:
        word_combinations_to_try.append(set(input_words_list[:-1]))  # Drop last

    # If single word, also try it as-is
    if len(input_words_list) == 1:
        word_combinations_to_try.append(set(input_words_list))

    # Try each combination
    for word_set in word_combinations_to_try:
        if not word_set:
            continue

        matches = []

        for valid_name in valid_names:
            valid_lower = valid_name.lower()
            valid_words = set(valid_lower.replace('_', ' ').split())

            if debug_print:
                print(f"[NPC_NORM]   '{valid_name}' words {valid_words} vs input words {word_set}")

            # Check if ALL words in word_set are in valid_words
            if word_set.issubset(valid_words):
                matches.append(valid_name)
                if debug_print:
                    print(f"[NPC_NORM]     → MATCH: All words found")

        # If we found matches with this combination, evaluate them
        if matches:
            if debug_print:
                print(f"[NPC_NORM] Found {len(matches)} matches with word set {word_set}: {matches}")
            break  # Use this combination

    if not matches:
        matches = []  # Ensure it's defined

    # Evaluate matches
    if len(matches) == 0:
        if debug_print:
            print(f"[NPC_NORM] REJECT: No word-based matches found")
        return None, "no_match"

    elif len(matches) == 1:
        if debug_print:
            print(f"[NPC_NORM] WORD MATCH: '{matches[0]}' (unambiguous)")
        return matches[0], "word_match"

    else:
        # Multiple matches - ambiguous
        if debug_print:
            print(f"[NPC_NORM] REJECT: Ambiguous - {len(matches)} matches: {matches}")
        return None, "no_match"

# Test this implementation
if __name__ == "__main__":
    # Quick sanity test
    test_tracker = {
        "partyMembers": ["testplayer_main"],
        "partyNPCs": [
            {"name": "Scout Alice"},
            {"name": "Scout Bob"},
            {"name": "Ranger Charlie"}
        ]
    }

    tests = [
        ("Scout Alice", "Scout Alice", "exact"),
        ("Alice", "Scout Alice", "word_match"),
        ("Ranger Alice", "Scout Alice", "word_match"),
        ("Scout", None, "no_match"),  # Ambiguous
        ("Alicia", None, "no_match"),  # Typo
        ("TestPlayer", "testplayer_main", "word_match"),
    ]

    print("Quick Sanity Test:")
    for input_name, expected, expected_type in tests:
        result, match_type = normalize_npc_name_for_action(input_name, test_tracker, debug_print=False)
        status = "✓" if result == expected and match_type == expected_type else "✗"
        print(f"{status} '{input_name}' → '{result}' ({match_type})")
