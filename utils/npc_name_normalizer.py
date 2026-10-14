#!/usr/bin/env python3
"""
NPC Name Normalizer - exact names only
Matches INPUT name TO party tracker names exactly (case ignored, "_" read as a
space). A near name is refused, never matched to another character: "Kira",
"Ranger Kira" and "Scout Elen" do not become "Scout Kira" (#855, family 2).
The caller refuses the action and lists the exact names.

Related: GitHub Issues #108, #855
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
        match_type: "exact", "no_match"
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

    # STEP 2: The underscore form on either side ("scout_kira" is "Scout Kira")
    input_spaced = ' '.join(input_lower.replace('_', ' ').split())
    for valid_name in valid_names:
        if ' '.join(valid_name.lower().replace('_', ' ').split()) == input_spaced:
            if debug_print:
                print(f"[NPC_NORM] EXACT MATCH (underscore): '{valid_name}'")
            return valid_name, "exact"

    # No partial or word match (#855, family 2): a name that is not exactly a
    # party name is refused, and the caller lists the exact names.
    if debug_print:
        print(f"[NPC_NORM] REJECT: '{input_clean}' is not an exact party name")
    return None, "no_match"


def exact_character_reference(input_name, party_tracker_data, extra_names=()):
    """The exact character a name refers to, or None (#855, family 2).

    A party name or one of extra_names (case ignored, "_" read as a space),
    else the name itself when a character sheet exists under exactly that
    name. Never a partial or word match.
    """
    tracker = {
        'partyMembers': list(party_tracker_data.get('partyMembers', []) or [])
        + [name for name in extra_names if isinstance(name, str) and name],
        'partyNPCs': list(party_tracker_data.get('partyNPCs', []) or []),
    }
    canonical, _ = normalize_npc_name_for_action(input_name, tracker)
    if canonical is not None:
        return canonical
    if not isinstance(input_name, str) or not input_name.strip():
        return None
    import os
    from updates.update_character_info import detect_character_role, get_character_path

    name = input_name.strip()
    if os.path.exists(get_character_path(name, detect_character_role(name))):
        return name
    return None

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
        ("scout alice", "Scout Alice", "exact"),
        ("testplayer main", "testplayer_main", "exact"),
        ("scout_alice", "Scout Alice", "exact"),
        ("Alice", None, "no_match"),  # Near name: refused
        ("Ranger Alice", None, "no_match"),  # Another title: refused
        ("Scout", None, "no_match"),
        ("Alicia", None, "no_match"),  # Typo
        ("TestPlayer", None, "no_match"),
    ]

    print("Quick Sanity Test:")
    for input_name, expected, expected_type in tests:
        result, match_type = normalize_npc_name_for_action(input_name, test_tracker, debug_print=False)
        status = "✓" if result == expected and match_type == expected_type else "✗"
        print(f"{status} '{input_name}' → '{result}' ({match_type})")
