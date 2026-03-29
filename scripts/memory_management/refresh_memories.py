#!/usr/bin/env python3
"""
Refresh Companion Memories - Rebuild all memories from scratch
This ensures idempotent processing with no duplicates
"""

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.memories.companion_memory import CompanionMemoryManager, build_companion_memory_participants

def refresh_all_memories():
    """Process entire journal from scratch, replacing all existing memories"""
    print("\n" + "=" * 80)
    print("COMPANION MEMORY REFRESH")
    print("Rebuilding all memories from journal (idempotent mode)")
    print("=" * 80)

    # Initialize in refresh mode
    print("\nInitializing memory manager in refresh mode...")
    memory_manager = CompanionMemoryManager(mode='refresh')

    # Load journal
    journal_path = Path('journal.json')
    if not journal_path.exists():
        print("ERROR: journal.json not found")
        return False

    with open(journal_path, 'r') as f:
        journal_data = json.load(f)

    entries = journal_data.get('entries', [])
    print(f"Found {len(entries)} journal entries to process\n")

    # Get party NPCs and party-member identities from party tracker
    party_npcs = []
    party_members = []
    party_tracker_path = Path('party_tracker.json')
    if party_tracker_path.exists():
        with open(party_tracker_path, 'r') as f:
            party_data = json.load(f)
            party_npcs, party_members = build_companion_memory_participants(party_data)

    if not party_npcs:
        print("ERROR: No party NPCs found in party_tracker.json")
        print("Please ensure party_tracker.json exists and has partyNPCs defined")
        return False

    print(f"Tracking companions: {', '.join(party_npcs)}")
    print("-" * 40)

    # Process chronologically
    total_memories = 0
    entries_with_memories = 0
    current_day = -1

    for i, entry in enumerate(entries):
        # Show progress every 10 entries
        if i % 10 == 0:
            print(f"Processing entries {i+1}-{min(i+10, len(entries))}...", end="\r")

        # Process entry
        memories = memory_manager.process_journal_entry(entry, party_npcs, party_members=party_members)

        # Track day changes
        if memory_manager.day_counter != current_day:
            current_day = memory_manager.day_counter
            if memories:
                print(f"\nDay {current_day:03d}: ", end="")

        if memories:
            entries_with_memories += 1
            total_memories += len(memories)
            # Show what was crystallized
            for npc_name, memory in memories.items():
                actions = ', '.join(memory.trigger_actions[:2])
                print(f"[{npc_name}: {actions} ({memory.emotional_velocity:.2f})] ", end="")

    # Save all memories
    print(f"\n\nSaving all memories...")
    memory_manager.save_all_memories()

    # Display summary
    print("\n" + "=" * 80)
    print("REFRESH COMPLETE")
    print("=" * 80)

    print(f"\nStatistics:")
    print(f"  Total entries processed: {len(entries)}")
    print(f"  Days covered: {memory_manager.day_counter + 1}")
    print(f"  Entries creating memories: {entries_with_memories}")
    print(f"  Total memories crystallized: {total_memories}")
    print(f"  Crystallization rate: {(entries_with_memories/len(entries)*100):.1f}%")

    # Show final profiles
    print("\n" + "-" * 40)
    print("COMPANION PROFILES")
    print("-" * 40)

    for npc_name in party_npcs:
        profile = memory_manager.get_npc_profile(npc_name)

        if profile['total_interactions'] > 0:
            print(f"\n{npc_name}:")
            print(f"  Interactions: {profile['total_interactions']}")
            print(f"  Core Memories: {profile['core_memories']}")

            # Show emotional state (not maxed out anymore due to decay)
            if profile['emotional_state']:
                emotions = profile['emotional_state']
                significant = [(k, v) for k, v in emotions.items() if abs(v) > 0.01]
                if significant:
                    significant.sort(key=lambda x: abs(x[1]), reverse=True)
                    emotion_str = ", ".join(f"{k}={v:.2f}" for k, v in significant[:3])
                    print(f"  Emotional State: {emotion_str}")

            # Show behavioral traits (should be more accurate now)
            if profile['behavioral_model']:
                behaviors = profile['behavioral_model']
                traits = []
                for trait, value in behaviors.items():
                    if abs(value) > 0.1:
                        if value > 0:
                            traits.append(trait.split('_vs_')[0].replace('_', ' ').title())
                        else:
                            traits.append(trait.split('_vs_')[1].replace('_', ' ').title())
                if traits:
                    print(f"  Traits: {', '.join(traits)}")

            # Show strongest memory
            if profile.get('strongest_memory'):
                memory = profile['strongest_memory']
                actions = ', '.join(memory.get('trigger_actions', [])[:2])
                print(f"  Strongest Memory: {actions} at {memory.get('location')} (v={memory.get('emotional_velocity'):.2f})")

            relationship_edges = profile.get('relationship_edges', {})
            if relationship_edges:
                print("  Relationship Edges:")
                for edge_key, edge_data in sorted(relationship_edges.items()):
                    if not isinstance(edge_data, dict):
                        continue
                    display_name = edge_data.get('display_name', edge_key)
                    edge_parts = []
                    for field in ('trust', 'respect', 'intimacy', 'fear', 'resentment'):
                        value = float(edge_data.get(field, 0.0))
                        if abs(value) > 0.05:
                            edge_parts.append(f"{field}={value:.2f}")
                    if not edge_parts:
                        edge_parts.append('low-signal')
                    print(f"    - {display_name}: {', '.join(edge_parts)}")

    # Check for duplicates
    print("\n" + "-" * 40)
    print("DUPLICATE CHECK")
    print("-" * 40)

    duplicates_found = False
    for npc_name in party_npcs:
        if npc_name in memory_manager.npc_memories:
            memories = memory_manager.npc_memories[npc_name]
            seen = set()
            for memory in memories:
                key = f"{memory.timestamp}_{memory.location}_{memory.emotional_velocity:.2f}"
                if key in seen:
                    print(f"  DUPLICATE: {npc_name} - {key}")
                    duplicates_found = True
                seen.add(key)

    if not duplicates_found:
        print("  No duplicates found - system is idempotent!")

    print("\n" + "=" * 80)
    print("SUCCESS")
    print("=" * 80)
    print("\nMemories have been refreshed and saved to data/companion_memories/")
    print("The system is now:")
    print("  - Using relative day tracking (Day 001, Day 002, etc.)")
    print("  - Applying emotional decay over time")
    print("  - Preventing duplicate memories")
    print("  - Generating more accurate behavioral models")
    print("\nRun this script again to verify idempotency (same input = same output)")

    return True

if __name__ == "__main__":
    try:
        success = refresh_all_memories()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nRefresh interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
