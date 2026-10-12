#!/usr/bin/env python3
"""
Initialize companion memories on startup if they don't exist but journal does
"""

import os
import json
from pathlib import Path
from utils.enhanced_logger import debug, info, warning
from utils.encoding_utils import safe_json_load

# check_and_initialize_on_startup's result when journal.json cannot be read (#623).
JOURNAL_UNREADABLE = "journal_unreadable"


def journal_unreadable(journal_path="journal.json"):
    """The parse error when journal.json exists but cannot be read, else None."""
    if not Path(journal_path).exists():
        return None
    try:
        safe_json_load(journal_path)
    except json.JSONDecodeError as e:
        return str(e)
    return None

def initialize_memories_if_needed():
    """
    Report an unreadable journal at startup (#623). The keyword memory build
    that used to follow is retired (#855): companion memory comes from the
    episodic upgrade, which reads the same journal. Existing memory files are
    left as they are and still imported.
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
    try:
        journal_data = safe_json_load(journal_path)
    except json.JSONDecodeError as e:
        # An unreadable chronicle skips the build for this start; play
        # continues, and the chronicle sets the file aside at its next read.
        warning("MEMORY: journal.json could not be read (%s); companion memories are not "
                "built from it this session and play continues" % e, category="startup")
        return JOURNAL_UNREADABLE
    if not journal_data or not journal_data.get('entries'):
        debug("initialize_memories", "Journal empty or invalid, skipping memory initialization")
        return False

    debug("initialize_memories", "Keyword memory build retired; companion memory "
          "comes from the episodic upgrade")
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
    result = initialize_memories_if_needed()
    if result == JOURNAL_UNREADABLE:
        return JOURNAL_UNREADABLE
    if result:
        info("initialize_memories", "Memory system initialized from existing journal")
    else:
        debug("initialize_memories", "Memory initialization not needed or not possible")

if __name__ == "__main__":
    # Test the initialization
    check_and_initialize_on_startup()