# AGENTS.md - NeverEndingQuest Coding Guidelines

This file provides guidance for AI coding agents working in the NeverEndingQuest repository.

## Project Overview

NeverEndingQuest is an AI-powered Dungeon Master system for running SRD 5.2.1 compatible tabletop RPG campaigns. It features token compression, a web interface with real-time updates, and a comprehensive module creation toolkit.

### Tabletop Multiplayer Context

**This repository is a merge-safe tabletop multiplayer plugin/modification** of the upstream [MoonlightByte/NeverEndingQuest](https://github.com/MoonlightByte/NeverEndingQuest) project.

**Core Purpose:**
- Designed for **local, in-person tabletop RPG sessions** (e.g., public library events, game stores)
- A facilitator/staff member manages **multiple player characters (PCs)** on a single laptop
- Provides a **tabbed UI** for switching between character sheets
- Replaces LLM-prompted PC management with **hard-wired Python functions** to prevent PCs being misidentified as NPCs
- Maintains **full backward compatibility** with single-player mode

**Plugin Architecture:**
- **Minimal core file modifications** - Changes to `web_interface.py` and `game_interface.html` are clearly marked
- **Encapsulated functionality** - New features in separate files (e.g., `tabletop_mode.js`, `multi_pc_combat.py`)
- **Merge-safe design** - Easy to integrate upstream updates while preserving tabletop features
- **State-driven activation** - Tabletop Mode activates when `partyMembers` in `party_tracker.json` has more than one entry

## Build/Lint/Test Commands

### Running the Application
```bash
# Main web interface (recommended)
python run_web.py          # Opens http://localhost:8357

# Module toolkit directly
python launch_toolkit.py    # Opens module creation interface

# Terminal mode (limited features)
python main.py             # Classic text interface
```

### Validation and Testing
```bash
# Validate module schemas (run after JSON changes)
python core/validation/validate_module_files.py   # Aim for 100% pass rate

# Test compression system
python test_compression.py

# Check token usage
python analyze_telemetry.py
```

### Dependency Installation
```bash
pip install -r requirements.txt
```

### Setup Configuration
```bash
cp config_template.py config.py  # Add your OpenAI API key to config.py
```

## Code Style Guidelines

### File Headers
Every Python file must include the SPDX license header:

```python
# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest [Component] - [Brief Description]
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""
```

Major modules should also include the architecture documentation block (see existing files for examples).

### Import Order
```python
# 1. Standard library imports
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# 2. Third-party imports
from openai import OpenAI
from flask import Flask

# 3. Internal module imports (grouped by layer)
# Core AI/Generators
from core.ai.action_handler import process_action
from core.generators.module_builder import ModuleBuilder

# Managers
from core.managers.combat_manager import CombatManager
from core.managers.storage_manager import StorageManager

# Utilities
from utils.file_operations import safe_write_json, safe_read_json
from utils.enhanced_logger import debug, info, warning, error
from utils.encoding_utils import safe_json_load, safe_json_dump

# Configuration (always near end)
from config import OPENAI_API_KEY, DM_MAIN_MODEL
from model_config import USE_COMPRESSED_COMBAT
from debug_config import DEBUG_CATEGORIES
```

### Naming Conventions
- **Functions**: `snake_case`, verb-noun pattern (e.g., `process_action()`, `get_location_data()`)
- **Classes**: `PascalCase` with descriptive suffixes (e.g., `CombatManager`, `ModuleGenerator`)
- **Constants**: `UPPER_CASE_WITH_UNDERSCORES` (e.g., `DM_MAIN_MODEL`, `MAX_RETRIES`)
- **Private methods**: Leading underscore (e.g., `_sanitize_unicode()`, `_load_data()`)
- **Type variables**: Use `T`, `K`, `V` for generics if needed

### Type Hints
Always use type hints for public functions:

```python
def get_party_tracker() -> Dict[str, Any]:
def process_action(action: str, data: Dict[str, Any]) -> Dict[str, Any]:
def find_path(from_loc: str, to_loc: str) -> Tuple[bool, List[str], str]:
def get_npc(name: str) -> Optional[Dict[str, Any]]:
```

Use `Optional[T]` for nullable returns, `Any` for flexible parameters.

### Error Handling
```python
# Use try/except with specific exceptions
from utils.enhanced_logger import debug, info, warning, error

try:
    data = safe_read_json(filepath)
    lock_acquired = True
except FileNotFoundError:
    warning(f"File not found: {filepath}", category="file_operations")
    return None
except json.JSONDecodeError as e:
    error(f"Invalid JSON in {filepath}: {e}", category="file_operations")
    return None
except Exception as e:
    error(f"Unexpected error: {e}", exception=e, category="file_operations")
    raise
finally:
    if lock_acquired:
        release_lock(filepath)
```

### Logging
Use the enhanced logger with categories:

```python
from utils.enhanced_logger import debug, info, warning, error

debug(f"Processing action: {action}", category="ai_processing")
info(f"Character updated: {name}", category="character_updates")
warning(f"Schema validation failed for {file}", category="validation")
error(f"Failed to load module: {e}", exception=e, category="module_loading")
```

### CRITICAL: Unicode Characters - NEVER USE
Windows console (cp1252) crashes with Unicode. Use ASCII only:
- Use `[OK]` or `[PASS]` instead of checkmarks
- Use `[ERROR]` or `[FAIL]` instead of X marks
- Use `->` or `=>` instead of arrows
- No emojis, use text descriptions

### Atomic File Operations
Always use atomic operations for JSON files:

```python
from utils.file_operations import safe_write_json, safe_read_json
from utils.encoding_utils import safe_json_load, safe_json_dump

# Writing
data = {"key": "value"}
safe_write_json("path/to/file.json", data)

# Reading
data = safe_read_json("path/to/file.json")
```

### Architecture Patterns

#### 1. Orchestrator-Worker Pattern (Module Generation)
- `module_builder.py` = ORCHESTRATOR (manages workflow)
- `module_generator.py` = WORKER (implementation, area connections)
- **Always fix bugs in module_generator.py, NOT module_builder.py**

#### 2. Manager Pattern
Major subsystems use dedicated managers:
- `CampaignManager`: Hub-and-spoke campaign orchestration
- `CombatManager`: Turn-based combat with AI validation
- `StorageManager`: Atomic file operations with rollback
- `LocationManager`: Location-based features and storage
- `MultiPCCombatManager`: Multi-PC turn tracking and initiative management

#### 3. Multi-PC Combat Pattern (Tabletop Mode)
- **Head-Body-Tail Prompt Architecture**:
  - **Head**: Immutable JSON block with ALL PCs' stats, status, and initiative (authoritative state)
  - **Body**: Compressible narrative history (compressed as it grows)
  - **Tail**: Fresh narrative (last 1-3 interactions in raw text)
- **Deterministic Initiative**: Bypass AI tracker (which only recognizes one "player"), use `format_initiative_tracker()` to generate turn order from `turn_queue` state
- **Phase Automation**: PC phase → Enemy phase batch processing with explicit `/end` command trigger
- **Active PC Context**: `[PC_NAME]` markers in prompts to identify which PC's turn it is
- **Enemy Armor Class Persistence**:
  - Encounter generation MUST include `armorClass` in enemy entries (`core/generators/combat_builder.py`)
  - Turn queue initialization should backfill missing AC from monster templates (`core/managers/multi_pc_combat.py`)
  - Example fix: `"armorClass": monster_data.get("armorClass", 10)` with `# TABLETOP MODE:` comment
  - See: Multi-PC Combat Enemy Armor Class Fix (2026-02-02)
- **Party Member NPC Filtering**:
  - When AI generates `createEncounter` action, it includes all allies in `npcs` array following prompt examples
  - TABLETOP MODE must filter `partyMembers` from `npcs` list before encounter generation to prevent PC misclassification
  - Implementation in `action_handler.py`: Compare `npcs` against `party_tracker_data["partyMembers"]` and remove matches
  - This ensures PCs get `type: "player"` not `type: "npc"` in encounter files
  - Prevents combat sync from loading PC files as NPC templates (causes NPC_LOAD logs and LLM confusion)
  - See: Multi-PC Combat PC/NPC Type Classification Fix (2026-02-02)

#### 4. Plugin Architecture Pattern
- **Minimal Core Modifications**: Changes to upstream files marked with `# TABLETOP MODE:` comments
- **Encapsulated Extensions**: New functionality in separate modules (`utils/pc_manager.py`, `web/static/js/tabletop_mode.js`)
- **State Detection**: Tabletop features activate based on `party_tracker.json` state, not configuration flags
- **Merge Safety**: Clear boundaries allow easy integration of upstream updates

### SRD 5.2.1 Compliance
When implementing game mechanics:
- Use "5th edition" or "5e" instead of "D&D"
- Add attribution: `"_srd_attribution": "Portions derived from SRD 5.2.1, CC BY 4.0"`
- Reference only generic fantasy settings
- Follow official SRD rules for mechanics

## Key File Locations

### Critical Paths
- `modules/conversation_history/` - Active conversation files
- `modules/campaign_summaries/` - AI-generated module summaries
- `core/validation/` - Schema validation scripts
- `core/managers/` - Manager classes
- `core/generators/` - Content generation
- `utils/` - Utility functions
- `data/` - Game data (bestiary, spells, etc.)
- `schemas/` - JSON schemas for validation

### Configuration Files
- `config.py` - API keys and module settings (not in git)
- `model_config.py` - AI model routing (safe to commit)
- `debug_config.py` - Debug category toggles

### Tabletop Mode Specific Files
- `utils/pc_manager.py` - Party management and PC state logic
- `core/managers/multi_pc_combat.py` - Multi-PC combat state and turn tracking (includes armorClass backfill logic for existing encounters)
- `party_tracker.json` - Single source of truth for party state (`partyMembers`, `active_character`)
- `web/static/js/tabletop_mode.js` - Client-side multiplayer UI logic
- `web/static/css/tabletop_mode.css` - Tabletop-specific styles
- `prompts/combat/combat_sim_prompt_multipc.txt` - Multi-PC combat prompt (narrative format)
- `prompts/combat/combat_sim_prompt_multipc_compressed.txt` - Multi-PC combat prompt (@-directive format)

### Core Files with TABLETOP MODE Modifications
The following core files contain marked modifications for tabletop mode compatibility:
- `core/generators/combat_builder.py` - Added `armorClass` to enemy encounter generation (line ~347, `# TABLETOP MODE:` comment)
- `core/ai/action_handler.py` - Added party member filtering from NPCs list in `createEncounter` action to prevent PCs being misclassified as NPCs (line ~695-730, `# TABLETOP MODE:` comment)

## Quality Gates

Before finishing work:
- [ ] No Unicode characters in Python code
- [ ] Schema validation passes (run validate_module_files.py)
- [ ] Atomic operations used for state changes
- [ ] JPEG compression for new images (quality 95)
- [ ] Root cause addressed (not workaround)
- [ ] Import patterns match standards
- [ ] Media files in correct locations

## Quick Reference

```python
# Standard function template
def function_name(param: str, optional: bool = True) -> Dict[str, Any]:
    """Brief description of what this function does.
    
    Args:
        param: Description of parameter
        optional: Description of optional parameter
        
    Returns:
        Dictionary containing result data
    """
    try:
        # Implementation
        result = process_data(param)
        info(f"Success: {result}", category="appropriate_category")
        return {"status": "success", "data": result}
    except Exception as e:
        error(f"Failed: {e}", exception=e, category="appropriate_category")
        return {"status": "error", "message": str(e)}
```

```python
# Class template
class ManagerName:
    """Brief description of manager purpose."""
    
    CONSTANT_VALUE = "value"
    
    def __init__(self):
        self.data = {}
        
    def public_method(self, param: str) -> bool:
        """Description of method."""
        return True
        
    def _private_helper(self) -> None:
        """Private helper method."""
        pass
```
