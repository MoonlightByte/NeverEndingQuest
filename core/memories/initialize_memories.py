#!/usr/bin/env python3
"""
Initialize companion memories on startup if they don't exist but journal does
"""

import os
import json
import sys
from pathlib import Path
from utils.enhanced_logger import debug, info, warning
from utils.encoding_utils import safe_json_load

def initialize_memories_if_needed():
    """
    Check if memories need initialization and create them from journal if needed.
    Called on startup to ensure memories exist for existing games.
    """

    # Check if memories already exist
    memory_dir = Path("data/companion_memories")
    memory_files = list(memory_dir.glob("*_memories.json"))

    if memory_files:
        debug("initialize_memories", f"Found {len(memory_files)} existing memory files, skipping initialization")
        return False

    # Check if journal exists
    journal_path = Path("journal.json")
    if not journal_path.exists():
        debug("initialize_memories", "No journal found, skipping memory initialization")
        return False

    # Load journal
    journal_data = safe_json_load(journal_path)
    if not journal_data or not journal_data.get('entries'):
        debug("initialize_memories", "Journal empty or invalid, skipping memory initialization")
        return False

    info("initialize_memories", f"Found journal with {len(journal_data['entries'])} entries, initializing memories...")

    # Load party tracker to get NPCs
    party_tracker_path = Path("party_tracker.json")
    if not party_tracker_path.exists():
        warning("initialize_memories", "No party tracker found, cannot determine NPCs")
        return False

    party_tracker = safe_json_load(party_tracker_path)
    if not party_tracker:
        warning("initialize_memories", "Invalid party tracker")
        return False

    # Extract party NPCs
    party_npcs = []
    for npc in party_tracker.get('partyNPCs', []):
        npc_name = npc.get('name', '') if isinstance(npc, dict) else str(npc)
        if npc_name:
            # Extract just the first name (e.g., "Kira" from "Scout Kira")
            first_name = npc_name.split()[0] if ' ' in npc_name else npc_name
            # Remove titles
            if first_name.lower() in ['scout', 'ranger', 'commander']:
                parts = npc_name.split()
                first_name = parts[1] if len(parts) > 1 else parts[0]
            party_npcs.append(first_name)

    if not party_npcs:
        warning("initialize_memories", "No NPCs found in party tracker")
        return False

    info("initialize_memories", f"Found party NPCs: {', '.join(party_npcs)}")

    # Initialize memory system and process journal
    try:
        from core.memories.companion_memory import CompanionMemoryManager

        # Create memory manager in refresh mode to rebuild from scratch
        memory_manager = CompanionMemoryManager(mode='refresh')

        # Process each journal entry
        entries_processed = 0
        memories_created = {}

        for entry in journal_data['entries']:
            result = memory_manager.process_journal_entry(entry, party_npcs)
            if result:
                entries_processed += 1
                for npc, memory in result.items():
                    if npc not in memories_created:
                        memories_created[npc] = 0
                    memories_created[npc] += 1

        # Save all memories
        memory_manager.save_all_memories()

        info("initialize_memories",
             f"Successfully initialized memories: {entries_processed} entries processed, "
             f"created memories for {', '.join(f'{npc}({count})' for npc, count in memories_created.items())}")

        # Now compress the memories
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, "scripts/memory_management/compress_memories.py"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                info("initialize_memories", "Successfully compressed initial memories")
        except Exception as e:
            debug("initialize_memories", f"Could not compress memories (non-fatal): {e}")

        return True

    except Exception as e:
        warning("initialize_memories", f"Failed to initialize memories: {e}")
        return False

def check_and_initialize_on_startup():
    """
    Main function to call on game startup.
    Ensures memory system is ready for existing games.
    """

    # Create memory directory if it doesn't exist
    memory_dir = Path("data/companion_memories")
    memory_dir.mkdir(parents=True, exist_ok=True)

    # Initialize if needed
    if initialize_memories_if_needed():
        info("initialize_memories", "Memory system initialized from existing journal")
    else:
        debug("initialize_memories", "Memory initialization not needed or not possible")

if __name__ == "__main__":
    # Test the initialization
    check_and_initialize_on_startup()