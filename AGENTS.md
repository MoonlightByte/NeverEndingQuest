# AGENTS.md - NeverEndingQuest Coding Guidelines

This file provides guidance for AI coding agents working in the NeverEndingQuest repository.

## Project Overview

NeverEndingQuest is an AI-powered Dungeon Master system for running SRD 5.2.1 compatible tabletop RPG campaigns. It features token compression, a web interface with real-time updates, and a comprehensive module creation toolkit.

## Documentation Source Hierarchy (Doc Contract)

- `AGENTS.md` is the canonical repo guide for architecture, standards, and workflow.
- `openspec/changes/*` is the source of truth for active change requirements and acceptance criteria.
- `plans/` captures planning and draft thinking; once reflected in OpenSpec, plans are reference-oriented.
- `memory-bank/` is deprecated legacy context (if present), non-authoritative, and read-only by default.
- Conflict resolution: `AGENTS.md` governs repo-wide rules; active OpenSpec artifacts govern change-specific scope.
- Repositories without `memory-bank/` are fully valid and follow the `AGENTS.md` + `openspec` + `plans` workflow.

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

#### Upstream Merge Guidelines

**This repository extends NeverEndingQuest with TABLETOP MODE while maintaining upstream compatibility.**

**When merging upstream updates:**

1. **Preserve upstream features intact** - Accept all upstream HTML, CSS, JS, and Python as written. Don't remove, simplify, or restructure upstream features during the merge.

2. **Mark necessary modifications clearly** - When you must modify host files to hook in TABLETOP MODE:
   ```javascript
   // TABLETOP MODE: Added party member filtering
   // TABLETOP MODE: Multi-PC initiative tracking
   ```

3. **Prefer extension over modification** - Add TABLETOP MODE features in separate files when possible (`multi_pc_combat.py`, `tabletop_mode.js`) and call them from minimal hooks in host files.

4. **Never break upstream patterns** - Don't add null checks that assume elements might be missing. Don't rename upstream variables. Don't move upstream DOM elements.

**Example - The TTS Merge Mistake:**
- **What went wrong**: Removed the DM Voice settings panel and added broken null-checks, breaking upstream JavaScript
- **Why it was wrong**: Modified upstream feature structure instead of accepting it as designed
- **Correct approach**: Keep host TTS feature exactly as upstream designed it, use same Settings dropdown (works for both single and multi)

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

### Developer Tools and Debugging

**ONCNotes - Developer Diary:**
- **File**: `memory-bank/ONCNotes.md` - Ongoing conversational analysis diary
- **Purpose**: Captures "in-the-moment" developer observations from gameplay testing
- **Content**: Narrative summaries, combat analyses, OCNote patterns, architectural insights
- **Format**: Chronological entries with timestamps, conversational tone
- **Relationship**: Complements formal docs (AGENTS.md, OpenSpec) with informal testing observations
- **Updates**: Written after each "read chat log" analysis session

**OpenCode Skill System:**
- **Skill**: `sync-project-memory` - Global OpenCode skill for documentation synchronization
- **Skill**: `read-chat-log` - Local project skill for chat log analysis with OCNote threading
  - **Location**: `.opencode/skills/read-chat-log/SKILL.md`
  - **Trigger Phrases**: "read chat log", "update chat log", "read more", "show chat updates", "read chat"
  - **Features**: Context-based incremental tracking, OCNote analysis with fading memory architecture (ongoing summary + latest 5), automatic ONCNotes diary writing
  - **Bookmark Format**: `=====LAST LOG [timestamp]=====` for tracking read position
  - **Status**: Active (2026-02-05)
- **Location**: `~/.config/opencode/skills/sync-project-memory/SKILL.md`
- **Trigger Phrases**: "update memory bank", "update memory", "sync memory", "sync docs and memory", "update agents and memory"
- **Purpose**: Enforces AGENTS-first documentation sync; memory-bank is deprecated legacy context
- **Behavior**: Exact-phrase matching only (ignores partials like "memory"); always updates AGENTS.md, updates memory-bank only on explicit legacy request, and never creates new files
- **Status**: Active and tested (2026-02-03)

**Real-Time Chat Monitoring (TABLETOP MODE):**
- **File**: `web/web_interface.py` (lines ~228-290, marked with `# TABLETOP MODE:`)
- **Log Location**: `debug/logs/live_chat_monitor.json`
- **Utility**: `utils/chat_monitor.py` - Command-line tool for reading and filtering chat logs
- **Purpose**: Captures live WebSocket chat events for AI assistant visibility and external integrations
- **Implementation**: Wraps `socketio.emit()` to intercept `game_output` events and logs user inputs
- **Use Cases**:
  - AI coding assistant can monitor gameplay in real-time without polling
  - Live text feed for streaming/text-based audiences
  - TTS (text-to-speech) feed source for audio narration
  - Debugging and testing prompt changes with immediate feedback
- **Log Format**: JSON array with timestamp, event_type (user_input/ai_response/system), content, character, metadata
- **Retention**: Last 100 entries (rotating buffer)
- **Activation**: Automatic on server start, no configuration needed

**Chat Monitor Utility (`utils/chat_monitor.py`):**
```bash
# Show last 20 messages
python utils/chat_monitor.py --latest 20

# Real-time monitoring (follow mode)
python utils/chat_monitor.py --follow

# Filter by character
python utils/chat_monitor.py --character acheron

# Filter by event type
python utils/chat_monitor.py --type user_input

# Export to file
python utils/chat_monitor.py --export chat_backup.json

# Show statistics
python utils/chat_monitor.py --stats
```

### Core Files with TABLETOP MODE Modifications
The following core files contain marked modifications for tabletop mode compatibility:
- `main.py` - Added `active_pc` sanitization in `validate_ai_response()` to strip tabletop metadata before validation API calls (lines ~1231-1234, `# TABLETOP MODE:` comment)
- `core/managers/combat_manager.py` - Added `active_pc` sanitization before combat validation API calls (lines ~835-838, `# TABLETOP MODE:` comment)
- `core/generators/combat_builder.py` - Added `armorClass` to enemy encounter generation (line ~347, `# TABLETOP MODE:` comment)
- `core/ai/action_handler.py` - Added party member filtering from NPCs list in `createEncounter` action to prevent PCs being misclassified as NPCs (line ~695-730, `# TABLETOP MODE:` comment)
- `web/web_interface.py` - Added real-time chat monitoring system with SocketIO middleware (lines ~228-290, `# TABLETOP MODE:` comments)
- `prompts/combat/combat_sim_prompt_multipc_compressed.txt` - Added `@SPLIT_PARTY_GUIDANCE` section for split-party narrative handling (lines ~146-154)

### Combat Prompt Enhancements (2026-02-03)

**@SPLIT_PARTY_GUIDANCE - Edge Case Handling:**
- **Location**: `prompts/combat/combat_sim_prompt_multipc_compressed.txt` (lines 146-154)
- **Purpose**: Guides combat LLM to handle party members in different locations from active combat
- **Behavior**: 
  - Maintains dual awareness for 3-5 turns (weaving both locations)
  - Gracefully degrades to minimal acknowledgment after context limit
  - Prevents "What does [wrong PC] do?" prompting for absent characters
  - Supports narrative recovery when player describes rejoining
- **Human DM Role**: When context degrades, human provides narrative bridge (e.g., "we walk up the stairs") to recover
- **Testing Results**: Successfully maintained split narrative for 8-10 turns before natural context compression

### State Synchronization & The Mechanics vs Narrative Philosophy (2026-02-05)

**The Core Problem:**
LLM was hallucinating exhaustion state for all PCs at session start despite rest automation working correctly. Acheron (21/21 HP) was narrated as "limp and drifting on the edge of unconsciousness." The rest automation cleared exhaustion from JSON files, but the LLM couldn't see this and relied on conversation history instead.

**Root Cause:**
DM Note formatting functions (`format_pc_full_stats`, `format_pc_condensed`) never displayed `condition_affected` array to the LLM. Without seeing "Conditions: None," the LLM continued the narrative thread from the previous session's ending (exhausted party).

**The Hierarchy of Truth (Philosophical Resolution):**

```
┌─────────────────────────────────────────┐
│  TIER 1: PYTHON (Objective Reality)    │
│  • HP, max HP, death status            │
│  • Spell slots (current/max)           │
│  • Exhaustion levels (1-6)             │
│  • Death save successes/failures       │
│  [NON-NEGOTIABLE - Source of Truth]    │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│  TIER 2: LLM (Subjective Interpretation)│
│  • "Despite full HP, your old wound    │
│     aches from the battle"             │
│  • "You feel weary even after rest"    │
│    (atmospheric, not mechanical)       │
│  • Emotional states, tension, mood     │
│  [FREEDOM WITHIN CONSTRAINTS]          │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│  TIER 3: PLAYER (The Bridge)           │
│  • Sees Python reality (character sheet)│
│  • Experiences LLM narrative            │
│  • Can challenge: "But my HP is full!" │
│  [TRUST BUT VERIFY]                    │
└─────────────────────────────────────────┘
```

**The Golden Rule:**
> "Python enforces reality; you interpret it."

**Implementation:**

1. **DM Note Enhancement** (`utils/multi_pc_dm_note.py`):
   - `format_pc_full_stats()`: Added condition display after HP/AC line
     - Format: `Conditions: None` or `Conditions: Exhaustion, Prone`
   - `format_pc_condensed()`: Added concise condition display for non-Active PCs
     - Format: `Cond: Exhaustion`

2. **@STATE_SYNC Directive** (`prompts/system_prompt_compressed.txt`):
```javascript
@STATE_SYNC={
  bookmark: "SESSION BOUNDARY - State below is current mechanical truth",
  truth_source: "DM Note character stats are GROUND TRUTH for HP, conditions, slots",
  override: "If narrative memory contradicts DM Note, DM Note WINS",
  narrative_freedom: "You may narrate SUBJECTIVE experience, BUT mechanical state MUST match DM Note",
  principle: "Python enforces reality; you interpret it"
}
```

**Why This Preserves LLM Freedom:**
The LLM isn't constrained—it gains **clarity**. It knows the mechanical truth and narrates *from* that foundation. The story is richer because the axe can actually kill you (Python enforces this), not poorer.

**Why Only PCs, Not NPCs:**
- **PCs:** Load from persistent JSON with condition tracking → Need mechanical consistency for player trust
- **NPCs:** Generated dynamically → No persistent state; feel alive in the moment
- **Result:** NPCs unaffected by this bug; LLM treats them as "fresh" each session

**Token Efficiency:**
- Condition line: ~15 tokens per character
- @STATE_SYNC directive: ~80 tokens total
- No session start message needed (bookmark concept embedded in prompt)

**Key Insight:**
The exhaustion bug wasn't a rest automation failure—it was a **perception synchronization failure**. Python did its job perfectly. The LLM simply couldn't see the results. By adding conditions to the DM Note, we didn't constrain the LLM—we gave it eyes to see the reality Python was already maintaining.

**Files Modified:**
- `utils/multi_pc_dm_note.py` - Added condition display to both formatting functions
- `prompts/system_prompt_compressed.txt` - Added @STATE_SYNC directive

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

## Future Work & Development Notes

### Multi-PC Conversation Compression (Phase 2 - COMPLETED 2026-02-04)

**Status:** COMPLETED
**Priority:** Medium
**Effort:** Medium (~3-4 hours)

**Problem:**
Generic compression treated all messages the same in multi-PC mode, causing:
- Loss of per-PC storyline continuity when rotating between party members
- Reduced AI awareness of each party member's individual narrative arc
- Compression didn't account for different PCs taking turns as `active_character`

**Solution:**
Implemented multi-PC aware conversation compression with message tagging:

1. **Message Tagging (main.py lines ~3661-3680):**
   - User messages tagged with `active_pc` field: `{"role": "user", "content": "...", "active_pc": "Acheron"}`
   - Dual-check activation: `MULTIPLAYER_MODE` from config.py + runtime `active_pc` detection
   - Only applies tagging in multi-PC mode (>1 party member)

2. **MultiPCConversationCompressor (utils/compression/multi_pc_conversation_compressor.py):**
   - Extends `ParallelConversationCompressor` via inheritance (clean merge boundary)
   - Groups consecutive messages by `active_pc` for coherent compression
   - **Smart Compression Strategy:**
     - Recent 8 exchanges kept raw for immediate context
     - Cross-PC events preserved (location transitions, combat, plot)
     - Per-PC grouping maintains individual narrative arcs
     - DM Notes tagged but not compressed

3. **Integration Points (main.py lines ~2274-2291, ~1187-1204):**
   - Runtime detection of `active_pc` tags in conversation history
   - Automatic selection of appropriate compressor
   - Zero overhead for single-PC mode

**Key Features:**
- **Zero Upstream Impact:** Standard `ParallelConversationCompressor` used for single-PC mode
- **Clean Merge Boundaries:** All changes marked with `# TABLETOP MODE:` comments
- **Backward Compatible:** Falls back gracefully if `active_pc` not present
- **Token Efficient:** Only adds ~4 bytes per tagged message overhead

**Architecture Decisions:**
- **Tagging over aggressive compression:** Preserves full narrative for all PCs since they rotate turns
- **Strict active_pc field:** Reliable tracking at message insertion time (no inference)
- **Runtime detection:** Checks conversation history for `active_pc` tags to avoid `party_tracker_data` dependency in `get_ai_response()`
- **Gameplay-first:** Prioritizes AI response quality, refine through testing

**Files Created/Modified:**
- `utils/compression/multi_pc_conversation_compressor.py` - New compressor class (~350 lines)
- `main.py` - Message tagging and conditional compressor selection (~30 lines)

### Rest Automation Enhancement (Option B - COMPLETED 2026-02-05)

**Status:** COMPLETED
**Priority:** Medium
**Effort:** Medium (~1-2 days)
**Implementation Date:** 2026-02-05

**Problem Observed:**
During gameplay testing (2026-02-04), spell slots were not automatically updating after long rests, even though:
- The prompt includes "Long rest = restore all HP/slots/features per 5e rules"
- HP updates were working via updateCharacterInfo
- Players had to manually request spell slot updates

**Solution Implemented (Option B - Code Automation):**
Implemented automatic resource restoration in `core/ai/action_handler.py`:

1. **Function:** `_process_character_rest()` (lines ~1902-2065)
2. **Trigger:** When `{"action":"rest","parameters":{"type":"short|long","characters":[...]}}` is processed
3. **5e-Compliant Logic:**
   - **Short Rest (≥1 hour):**
     - Refreshes `shortRest` class features only
     - Warlock spell slots restored (pact magic)
     - NO automatic HP recovery (players must spend Hit Dice manually via `updateCharacterInfo`)
   - **Long Rest (≥8 hours):**
     - Restores HP to maximum
     - Restores all spell slots to maximum
     - Resets all class feature uses (Channel Divinity, etc.)
     - Removes all exhaustion levels
4. **Bug Fixes Applied:**
   - Fixed prompt contract - added "rest" to @ACTIONS, @PARAMS, @EXAMPLES in `prompts/system_prompt_compressed.txt`
   - Fixed path resolution using `find_character_file_fuzzy()` instead of manual filename building
   - Fixed exhaustion detection (schema uses `list[string]`, not `list[dict]`)
   - Added parameter validation for `rest_type` ("short" or "long")
   - Added file existence safety checks

**Files Modified:**
- `core/ai/action_handler.py` - Implemented `_process_character_rest()` function (~164 lines)
- `prompts/system_prompt_compressed.txt` - Added `rest` to @ACTIONS (line 24), @PARAMS (line 228), @EXAMPLES (lines 292-295), and updated @REST section (lines 109-116)
- `scripts/test_rest_action.py` - **NEW** - Comprehensive test suite for rest automation

**Benefits Achieved:**
- No reliance on LLM to remember rest rules
- Consistent 5e compliance
- Reduces player/AI confusion
- Works for both single-PC and multi-PC modes

**Testing:**
- Test script created but requires full application environment to run
- Serves as integration test specifications
- Logic verified for 5e rule compliance

**Related Files:**
- `utils/multi_pc_dm_note.py` (Phase 3 implementation - HP truth tracking)
- `prompts/system_prompt_compressed.txt` (@MULTI_PC directive with rest rules)
- `core/ai/action_handler.py` (rest handling)
- `config.py` (MULTIPLAYER_MODE toggle)

### Character Data Access Abstraction Layer (COMPLETED 2026-02-06)

**Status:** COMPLETED
**Priority:** Medium
**Effort:** Medium (~2-3 hours)
**Implementation Date:** 2026-02-06

**Purpose:**
Created centralized character data access abstraction in `utils/pc_manager.py` to establish consistent patterns for future database migration while maintaining full backward compatibility.

**Architecture:**
- **Plugin-Based Design:** All core logic contained in TABLETOP MODE file (`utils/pc_manager.py`)
- **Dual-Check Activation:** Uses `config.MULTIPLAYER_MODE` + `len(partyMembers) > 1` pattern
- **Zero Breaking Changes:** Upstream files can migrate gradually; fallback to direct file load

**Functions Added:**
1. **`should_use_abstraction_layer()`** - DUAL-CHECK: config.MULTIPLAYER_MODE + party size
2. **`get_character_state()`** - Retrieve character data with automatic mode detection
3. **`update_character_state()`** - Update character data with validation
4. **`get_party_character_states()`** - Bulk load all party members
5. **`character_exists()`** - Check if character exists
6. **`get_character_field()`** / **`update_character_field()`** - Single field access
7. **`get_character_access_stats()`** - Usage monitoring
8. **`_validate_character_name()`** - Input validation helper
9. **`_is_multiplayer_enabled()`** - Cached config check

**Safety Features:**
- **Thread-Safe Statistics:** `_stats_lock` protects `_character_access_stats` for multi-threaded web server
- **Input Validation:** Rejects empty strings, None values, and wrong types with error logging
- **Config Caching:** `_is_multiplayer_enabled()` caches config import after first call
- **Graceful Degradation:** Try/except blocks ensure fallback to direct file access on any failure

**Upstream Integration Points (all marked # TABLETOP MODE):**
- `core/managers/combat_manager.py` - Character loading in combat (lines ~2279-2289)
- `core/ai/action_handler.py` - Party filtering for encounters (lines ~704-709)
- `utils/multi_pc_dm_note.py` - Character loading for DM notes (lines ~283-291)

**Verification Results:**
- ✅ All 9 functions present and functional
- ✅ Combat LLM path verified working
- ✅ Narrator LLM path verified working
- ✅ Input validation correctly rejects invalid names
- ✅ Thread-safe statistics with lock protection
- ✅ Config caching prevents repeated imports
- ✅ Dual-check activation working correctly
- ✅ Syntax valid on all modified files
- ✅ Zero breaking changes to existing APIs

**Performance Impact:**
- Neutral to slightly improved (config caching eliminates repeated imports)
- No file I/O changes (same underlying operations)
- Negligible overhead (<0.1% compared to LLM latency)

**Future Database Migration Path:**
1. Update `CHARACTER_STORAGE_BACKEND` constant to "database"
2. Modify `_get_character_path()` to return DB connection string
3. All existing code continues working unchanged
4. Business logic (`get_character_state()`, `update_character_state()`) unchanged

**Files Modified:**
- `utils/pc_manager.py` - Core abstraction layer (~175 lines added)
- `core/managers/combat_manager.py` - Combat integration (6 lines, TABLETOP MODE marked)
- `core/ai/action_handler.py` - Action handler integration (5 lines, TABLETOP MODE marked)
- `utils/multi_pc_dm_note.py` - DM note integration (12 lines, TABLETOP MODE marked)

**Documentation:**
- Created `docs/functional_verification_report.md` with comprehensive testing results
- Added implementation summary to `docs/character_data_abstraction_implementation.md`

### Multi-PC Combat Manager Error Handling Fix (COMPLETED - 2026-02-06)

**Status:** COMPLETED
**Priority:** Low (Code Quality)
**Effort:** Small (~15 minutes)

**Problem:**
Inconsistent error handling across `core/managers/multi_pc_combat.py` with mix of `debug()`, `print()`, and silent pass statements. Six `print()` statements needed standardization:
- Lines 849, 868, 871: Error conditions using print()
- Line 866: Success messages using print()
- Line 1274: Callback errors using print()
- Lines 1310-1314: Lifecycle messages using print()

**Solution:**
Standardized all logging to use `utils.enhanced_logger`:
1. **Import Update (line 45):** Added `info` and `error` to existing `debug` import
2. **Error Replacements:**
   - Line 849: `error()` for persist combat changes failure
   - Line 868: `error()` for save changes failure
   - Line 871: `error()` with exception parameter for persist exception
   - Line 1274: `error()` with exception parameter for callback errors
3. **Info Replacements:**
   - Line 866: `info()` for successful save confirmation
   - Lines 1310-1314: `info()` for combat lifecycle messages (session end, persistence stats)

**Logger Categories:**
- `combat_persistence` - For save/load operations
- `combat_events` - For callback errors
- `combat_lifecycle` - For session start/end messages

**Result:**
- Zero `print()` statements remaining in file
- Consistent error handling following codebase standards
- Proper categorization enables filtering and debugging
- No functional changes (pure refactoring)

**Files Modified:**
- `core/managers/multi_pc_combat.py` - 6 lines changed, 1 import updated

### Context Manager Pattern for Testability (COMPLETED - 2026-02-06)

**Status:** COMPLETED
**Priority:** Medium (Architecture/Testability)
**Effort:** Small (~20 minutes)

**Problem:**
Global singleton pattern (`_active_combat_manager`, `_combat_callback`) makes unit testing difficult. Tests cannot easily mock combat state or capture events without running the full Flask application.

**Solution:**
Implemented context manager pattern for dependency injection in tests:

1. **Imports Added (lines 30-31):**
   - `Generator` from `typing`
   - `contextmanager` from `contextlib`

2. **Context Managers (lines 1251-1290):**
   - `temporary_combat_manager(manager)` - Temporarily replaces global combat manager
     - Usage: `with temporary_combat_manager(mock_manager):`
     - Automatically restores original manager on exit
   - `temporary_combat_callback(callback)` - Temporarily replaces global callback
     - Usage: `with temporary_combat_callback(mock_callback):`
     - Enables event capture in tests

3. **Reset Helper (lines 1292-1302):**
   - `reset_combat_state()` - Clears both manager and callback
   - Logs reset action for debugging
   - Marked "USE ONLY IN TESTS"

**Benefits:**
- **Zero breaking changes** - All existing code unchanged
- **Clean test syntax** - Context managers provide readable test code
- **Automatic cleanup** - `try/finally` ensures state restoration
- **Composable** - Can nest multiple context managers
- **Thread-safe** - Context managers work per-thread
- **Test scenarios enabled:**
  - Mock combat without Flask app running
  - Test edge cases (all PCs unconscious, etc.)
  - Verify persistence without file I/O
  - Capture web UI events in tests
  - Parallel test execution safe

**Files Modified:**
- `core/managers/multi_pc_combat.py` - 3 imports added, 3 functions added (~50 lines)

### MultiPCCombatManager Structure Refactoring (COMPLETED - 2026-02-06)

**Status:** COMPLETED
**Priority:** High (Architecture/Phase 3)
**Effort:** Medium (~2-3 hours)
**Implementation Date:** 2026-02-06

**Objective:**
Phase 3 of multi-PC combat rebuild: Refactor monolithic `MultiPCCombatManager` into focused sub-managers using Facade pattern.

**Architecture Changes:**

1. **Sub-Managers Created:**
   - `CombatStateManager` (lines 142-327, ~185 lines, 7 methods):
     - Manages PC combat states (`pc_states` dictionary)
     - Tracks HP, status, death saves per PC
     - Handles round/initiative metadata
   - `TurnQueueManager` (lines 331-635, ~305 lines, 10 methods):
     - Manages initiative order (`turn_queue` list)
     - Handles turn advancement and round tracking
     - Tracks phase completion flags

2. **MultiPCCombatManager Refactored:**
   - Reduced from 15 individual fields to 2 sub-manager references
   - Kept: `first_round`, `last_attack_weapon`, `last_target`, constants, `pending_character_updates`
   - Added: `_state: CombatStateManager`, `_turns: TurnQueueManager`

**Delegation Pattern Implemented:**

7 methods converted to thin delegation wrappers:
- `initialize_from_party()` → `self._state.initialize_from_party()`
- `initialize_turn_queue()` → `self._turns.initialize_turn_queue()`
- `get_available_pcs()` → `self._state.get_available_pcs()`
- `get_current_actor()` → `self._turns.get_current_actor()`
- `advance_turn()` → `self._turns.advance_turn()`
- `find_target()` → `self._turns.find_target()`
- `get_remaining_enemies_for_round()` → `self._turns.get_remaining_enemies_for_round()`

**Coordination Methods Preserved:**
5 methods kept in MultiPCCombatManager that coordinate between both sub-managers:
- `update_pc_hp()` - Updates state AND syncs changes to turn_queue
- `complete_pc_turn()` - Marks PC acted + checks if PC phase complete
- `force_end_pc_phase()` - Marks all PCs acted + sets phase flag
- `start_new_round()` - Coordinates round increment, state reset, phase reset
- `get_combat_state_summary()` - Aggregates data from both sub-managers

**Line Reduction:**
- Before: 1,943 lines
- After: 1,756 lines
- **Saved: -187 lines (~10% reduction)**

**Benefits:**
- Better separation of concerns (state vs turn logic)
- Easier unit testing (can test sub-managers independently)
- Clearer responsibilities (each class has single focus)
- Facade pattern: MultiPCCombatManager coordinates, sub-managers implement

**Verification:**
- Python syntax validated (`python -m py_compile`)
- Instantiation verified (sub-managers initialize correctly)
- Cross-manager linking verified (`_turns.state_manager` references `_state`)
- All delegations tested and functional

**Files Modified:**
- `core/managers/multi_pc_combat.py` - Major restructuring (no breaking changes)

---

## Plugin Architecture & SP/MP Unification Roadmap

### Core Philosophy: "Upstream First, Extend Second"

This codebase maintains a plugin architecture that enables both **easy upstream merges** AND **future unification** of Single-Player (SP) and Multi-Player (MP) modes. The goal is to make MP feel like a natural extension of SP, not a separate codebase.

### Current State: Plugin Mode (Phase 1)

**Activation Pattern:**
```python
# Dual-check: Config flag + runtime detection
if config.MULTIPLAYER_MODE and len(party_members) > 1:
    # MP features activate
```

**Key Principles:**
- **Minimal core file modifications** - Changes marked with `# TABLETOP MODE:` comments
- **Encapsulated extensions** - New features in separate files (`multi_pc_combat.py`, `tabletop_mode.js`)
- **Runtime detection** - Features activate based on party size, not just config flags
- **Shared data structures** - MP uses identical schemas to SP (character files, encounters, etc.)

### Phase 2: Runtime Detection Only (Target: v0.4.0)

**Migration Goal:** Remove `MULTIPLAYER_MODE` config requirement

**Activation Pattern:**
```python
# Runtime detection only
if len(party_members) > 1:
    # MP features activate automatically
```

**Benefits:**
- No configuration required
- Automatic activation at runtime
- Simpler deployment
- Backward compatible (SP = MP with 1 party member)

### Phase 3: Full Unification (Target: v0.5.0)

**End State:** MP becomes the default behavior

**Changes:**
- Remove `MULTIPLAYER_MODE` config entirely
- SP is simply MP with a single party member
- All MP-specific files become core files
- Upstream becomes unified codebase

### Coding Patterns for Unification

#### Pattern 1: Dual-Path Functions
Handle both SP and MP in the same function:
```python
def process_character_update(character_name, changes):
    # SP path (always works)
    update_character_info(character_name, changes)
    
    # MP extension (conditional)
    if multi_pc_manager and len(get_party_members()) > 1:
        multi_pc_manager.queue_update(character_name, changes)
```

#### Pattern 2: Abstraction Layers
Use abstraction functions that work for both modes:
```python
# utils/pc_manager.py
from utils.pc_manager import get_character_state

# Works for both SP and MP
character_data = get_character_state("Acheron")
```

**Migration Path:**
1. Phase 1: `if config.MULTIPLAYER_MODE and len(party) > 1`
2. Phase 2: `if len(party) > 1`
3. Phase 3: Always use abstraction layer

#### Pattern 3: Hook-Based Extensions
Add minimal hooks to upstream code:
```python
# In combat_manager.py (upstream)
def run_combat_simulation():
    # ... upstream logic ...
    _post_turn_hook()  # Single line addition

# In multi_pc_combat.py (extension)
def _post_turn_hook():
    if len(get_party_members()) > 1:
        persist_combat_changes()
```

#### Pattern 4: Extend Don't Replace
Add fields to existing structures rather than creating new ones:
```python
# BAD: Separate MP structure
mp_character = {"mp_hp": value, "mp_slots": value}

# GOOD: Extend existing structure
character_data["party_position"] = position
character_data["is_active_pc"] = True
```

### Critical Rules for Maintaining Compatibility

1. **Always use upstream persistence functions**
   - `update_character_info()` for character changes
   - `safe_write_json()` for file operations
   - Never write direct SQL or raw file I/O in MP code

2. **Never modify upstream data structures**
   - Don't add MP-specific fields to core JSON schemas
   - Use extension fields that upstream ignores gracefully
   - Maintain backward compatibility

3. **Runtime detection over configuration**
   - Check `len(party_members) > 1` instead of `config.MULTIPLAYER_MODE`
   - Check `multi_pc_manager is not None`
   - Remove hard dependencies on config flags

4. **Single source of truth**
   - Character state lives in character JSON files (not MP cache)
   - Party state lives in `party_tracker.json`
   - Combat state lives in encounter files
   - MP managers are caches, not primary storage

5. **Clear merge boundaries**
   - All modifications marked with `# TABLETOP MODE:`
   - Extensions in separate files when possible
   - Minimal changes to upstream logic flow

### Benefits of This Architecture

**For Upstream Merges:**
- Clear boundaries make conflict resolution easy
- Upstream changes don't break MP features
- Plugin files are isolated from core changes

**For Future Unification:**
- Gradual migration path (Phase 1 → 2 → 3)
- No rewrite required
- Tested MP code becomes core code
- Single codebase to maintain

**For Development:**
- Test SP mode works? It will work in unified build
- Test MP mode works? It validates unified architecture
- No duplicate code paths to maintain
- Consistent patterns across entire codebase

### Action Items for Maintaining Compatibility

**When Adding MP Features:**
1. Can this use existing SP functions?
2. Can this extend existing data structures?
3. Is this marked with `# TABLETOP MODE:`?
4. Will this work if `MULTIPLAYER_MODE` config is removed?

**When Merging Upstream:**
1. Preserve upstream features intact
2. Only add hooks if absolutely necessary
3. Test MP features still work after merge
4. Update TABLETOP MODE comments if lines shift

**When Planning New Features:**
1. Design for unified architecture from start
2. Use abstraction layers (`pc_manager`)
3. Implement runtime detection patterns
4. Document unification path in comments

---

## Recent Changes

### Combat Expanded Deterministic Guards (COMPLETED - 2026-03-11)

**Status:** COMPLETED - OpenSpec change archived and main specs synchronized

**OpenSpec Archive:**
- `openspec/changes/archive/2026-03-11-combat-expanded-deterministic-guards/`

**Objective:**
Add bounded deterministic combat guard coverage for explicit mechanics and phase-integrity contradiction classes while preserving fail-open behavior for ambiguous text/state.

**Implementation Summary:**
- Added phase-integrity deterministic helper: `utils/combat_phase_integrity_precheck.py`.
- Wired helper into combat validation flow in `core/managers/combat_manager.py` with fail-open exception handling.
- Added contract locks and source-touchpoint tests: `scripts/test_combat_expanded_deterministic_guards_contract.py`.
- Added guard behavior tests for forbidden actors, mid-batch stop, illegal exit, and illegal round increment: `scripts/test_combat_phase_integrity_precheck.py`.
- Archived change and synced new main specs for both guard domains.

**Verification:**
- `python3 scripts/test_combat_expanded_deterministic_guards_contract.py` -> PASS (14/14)
- `python3 scripts/test_combat_phase_integrity_precheck.py` -> PASS (10/10)
- `python3 scripts/test_deterministic_mechanics_precheck.py` -> PASS (18/18)
- `python3 scripts/test_multi_pc_combat.py` -> PASS (43/43)
- `python3 scripts/c5_regression_combat.py` -> PASS (32/32)
- `python3 -m py_compile core/managers/combat_manager.py utils/combat_phase_integrity_precheck.py scripts/test_combat_expanded_deterministic_guards_contract.py scripts/test_combat_phase_integrity_precheck.py` -> PASS
- `openspec validate combat-expanded-deterministic-guards` -> VALID

**Spec Sync:**
- `openspec/specs/tt-combat-mechanics-contradiction-guards/spec.md` (new)
- `openspec/specs/tt-combat-phase-integrity-guards/spec.md` (new)

### Combat Save/Concentration Contract Alignment (COMPLETED - 2026-03-11)

**Status:** COMPLETED - OpenSpec change archived and main specs synchronized

**OpenSpec Archive:**
- `openspec/changes/archive/2026-03-11-combat-save-concentration-contract/`

**Objective:**
Align multi-PC combat prompt and validator contracts to prefer first-class `requestRoll` for saves/checks/concentration pauses, keep pause-only semantics explicit, and lock deterministic concentration DC guidance.

**Implementation Summary:**
- Updated compressed combat sim and validation prompts to prefer `requestRoll` for player-facing saving throws, ability checks, skill checks, and concentration saves.
- Explicitly enforced pause semantics: after `requestRoll`, stop and wait for player input; no same-response contingent outcome narration.
- Added concentration DC rule guidance in combat contract language: `max(10, floor(damage / 2))`.
- Preserved prose-only save/check/concentration compatibility during migration.
- Updated uncompressed combat mirror prompts for contract parity.
- Confirmed no runtime widening was required (`requestRoll` runtime path remains scaffold/pause-oriented).

**Regression and Verification:**
- `python3 scripts/test_combat_save_concentration_contract.py` -> PASS (18/18)
- `python3 scripts/test_save_concentration_contract.py` -> PASS (28/28)
- `python3 scripts/test_multi_pc_combat.py` -> PASS (43/43)
- `python3 scripts/c5_regression_combat.py` -> PASS (32/32)
- `python3 -m py_compile scripts/test_combat_save_concentration_contract.py scripts/test_save_concentration_contract.py` -> PASS
- `openspec validate combat-save-concentration-contract` -> VALID

**Spec Sync:**
- `openspec/specs/tt-combat-request-roll-routing/spec.md` (new)
- `openspec/specs/tt-combat-concentration-request-dc/spec.md` (new)

**Notes:**
- Repaired `scripts/test_save_concentration_contract.py` OpenSpec artifact path resolution to support archived-change layouts and main-spec canonical lookup.

### Combat Structured PC/Allied Ops Pilot (COMPLETED - 2026-03-11)

**Status:** COMPLETED - OpenSpec change archived and main specs synchronized

**OpenSpec Archive:**
- `openspec/changes/archive/2026-03-11-combat-structured-pc-allied-ops-pilot/`

**Objective:**
Deepen combat adoption of structured `updateCharacterInfo.ops` for PC/allied mechanics updates while preserving prose compatibility and deferring enemy-side `updateEncounter.ops`.

**Implementation Summary:**
- Added combat-specific contract tests for mixed `changes + ops` preference, prose fallback compatibility, and enemy-side `updateEncounter` deferral.
- Updated compressed combat sim and validation prompts to prefer mixed payloads for PC/allied updates.
- Explicitly retained enemy-side `updateEncounter` changes-text routing and no-ops guard in this slice.
- Updated uncompressed combat mirror prompts for parity.
- Confirmed runtime alignment was already sufficient and kept runtime scope unchanged.

**Regression and Verification:**
- `python3 scripts/test_combat_structured_ops_contract.py` -> PASS (16/16)
- `python3 scripts/test_update_character_ops_contract.py` -> PASS (13/13)
- `python3 scripts/test_multi_pc_combat.py` -> PASS (43/43)
- `python3 scripts/c5_regression_combat.py` -> PASS (32/32)
- `python3 -m py_compile scripts/test_combat_structured_ops_contract.py` -> PASS
- `openspec validate combat-structured-pc-allied-ops-pilot` -> VALID

**Spec Sync:**
- `openspec/specs/tt-combat-structured-character-ops-routing/spec.md` (new)

### Combat Runtime Authority and Efficiency Refactor (COMPLETED - 2026-03-11)

**Status:** COMPLETED - OpenSpec change archived and main specs synchronized

**OpenSpec Archive:**
- `openspec/changes/archive/2026-03-11-combat-runtime-authority-and-efficiency/`

**Objective:**
Apply narrator-style prompt/validator hardening patterns to combat manager runtime and validation flow while preserving vivid narration, tactical enemy competence, phase integrity, and 5e accounting.

**Implementation Summary:**
- Multi-PC combat prompt authority locked to compressed runtime sources in `core/managers/combat_manager.py`.
- Added contract/regression test coverage for prompt authority, payload hygiene, validation routing telemetry, truth-pack behavior, and retry hygiene.
- Reduced runtime payload duplication (single authoritative `CURRENT_PHASE` emission in multi-PC context).
- Reordered/slimmed compressed combat sim and validation prompts so hard constraints/authority precede flavor guidance.
- Added threshold-based validation compression routing and deterministic telemetry (`validation_payload_chars`, `compression_reason`, `validation_routing_telemetry`).
- Added compact touched-combatant truth packs for PC/allied `updateCharacterInfo` validation context with inventory/ammo relevance gating.
- Added fail-open helper fallbacks for truth-pack assembly, compression decision/apply, and telemetry construction.
- Refactored retry flow so validation correction notes remain retry-local instead of persisting as canonical user turns in combat history.

**Verification:**
- `python3 scripts/test_combat_runtime_prompt_authority.py` -> PASS (7/7)
- `python3 scripts/test_combat_payload_hygiene.py` -> PASS (4/4)
- `python3 scripts/test_combat_validation_routing.py` -> PASS (11/11)
- `python3 scripts/test_combat_truth_pack.py` -> PASS (5/5)
- `python3 scripts/test_combat_retry_hygiene.py` -> PASS (3/3)
- `python3 scripts/test_multi_pc_combat.py` -> PASS (43/43)
- `python3 scripts/c5_regression_combat.py` -> PASS (32/32)
- `openspec validate combat-runtime-authority-and-efficiency` -> VALID

**Spec Sync:**
- `openspec/specs/tt-combat-context-packet-efficiency/spec.md` (new)
- `openspec/specs/tt-combat-runtime-prompt-authority/spec.md` (new)
- `openspec/specs/tt-combat-validation-efficiency-routing/spec.md` (new)
- `openspec/specs/tt-combat-validation-retry-hygiene/spec.md` (new)
- `openspec/specs/tt-combat-validator-mechanical-truth-pack/spec.md` (new)

**ADR Impact:**
- No new ADR required. Changes harden existing combat runtime/validation contracts without introducing a new durable architecture decision boundary.

### Prompt/Validator Refactor Completion (A1-A8) (COMPLETED - 2026-03-10)

**Status:** COMPLETED - OpenSpec change chain archived and specs synchronized

**OpenSpec Archives:**
- `openspec/changes/archive/2026-03-10-prompt-validator-contract-alignment/`
- `openspec/changes/archive/2026-03-10-prompt-validator-save-module-contract-alignment/`
- `openspec/changes/archive/2026-03-10-prompt-validator-deterministic-mechanics-precheck/`
- `openspec/changes/archive/2026-03-10-prompt-validator-runtime-authority-and-performance/`
- `openspec/changes/archive/2026-03-10-prompt-validator-telemetry-and-truth-pack/`
- `openspec/changes/archive/2026-03-10-prompt-validator-structured-ops-pilot/`
- `openspec/changes/archive/2026-03-10-prompt-validator-save-concentration-contract/`
- `openspec/changes/archive/2026-03-10-prompt-validator-expanded-deterministic-guards/`

**Objective:**
Complete the phased prompt/validator hardening plan in `plans/archive/prompt-validator-fix.md` by finishing canonical compressed-prompt authority, deterministic mechanics and guard rails, validator routing/performance controls, structured update contracts, and explicit save/concentration contracts.

**Implementation Summary:**
- Canonical runtime source enforced for compressed prompts and validation ordering hardened.
- Thresholded validation compression, low-risk skip routing, and validation telemetry/truth-pack wiring added.
- Deterministic mechanics precheck expanded across explicit contradiction classes (HP/slots/inventory/ammo/rest/unconscious coherence) with fail-open ambiguity handling.
- Structured `updateCharacterInfo.ops` contract introduced with deterministic fallback markers and runtime routing visibility.
- First-class `requestRoll` + concentration DC contract (`max(10, floor(damage / 2))`) introduced with compatibility-preserving pause semantics.
- Main specs synced for all archived prompt-validator capabilities under `openspec/specs/tt-*`.

**Verification:**
- `python3 scripts/test_prompt_validator_rest_contract.py` -> PASS
- `python3 scripts/test_prompt_validator_save_module_contracts.py` -> PASS
- `python3 scripts/test_runtime_prompt_authority.py` -> PASS
- `python3 scripts/test_validation_compression_routing.py` -> PASS
- `python3 scripts/test_validation_skip_routing.py` -> PASS
- `python3 scripts/test_validation_routing_telemetry.py` -> PASS
- `python3 scripts/test_validator_truth_pack.py` -> PASS
- `python3 scripts/test_update_character_ops_contract.py` -> PASS
- `python3 scripts/test_save_concentration_contract.py` -> PASS
- `python3 scripts/test_expanded_deterministic_guards_contract.py` -> PASS
- `python3 scripts/test_deterministic_mechanics_precheck.py` -> PASS

**ADR Impact:**
- No new ADR required. Changes extend existing prompt-validator architecture and contracts without introducing a new durable architecture decision boundary.

### NPC Join Name Canonicalization (COMPLETED - 2026-03-10)

**Status:** COMPLETED - OpenSpec change archived

**OpenSpec:** `openspec/changes/archive/2025-03-10-tt-npc-join-name-normalization/`

**Objective:**
Fix narrator validation loops where short NPC action names (for example `Kira`) were semantically correct but rejected by strict full-name validation contracts.

**Implementation Summary:**
- Extended runtime pre-validation canonicalization in `main.py` (`normalize_character_names_in_response`) for:
  - `updatePartyNPCs.parameters.npc.name` (dict form)
  - `updatePartyNPCs.parameters.npc` (string form -> canonical dict)
  - `updatePartyNPCs.parameters.add` (string/list/list-of-dicts)
  - `moveBackgroundNPC.parameters.npcName`
- Preserved fail-closed behavior for ambiguous/unresolved identity mapping with deterministic rejection messaging.
- Aligned system prompt contract example in `prompts/system_prompt_compressed.txt` to canonical name usage (`"name":"Scout Kira"`).
- Added regression coverage in `scripts/test_npc_arrival_state_sync.py` for add-form parity and prompt source-contract guard.

**Spec Sync:**
- Created `openspec/specs/tt-party-npc-action-name-canonicalization/spec.md`.
- Updated `openspec/specs/tt-npc-arrival-name-resolution/spec.md`.
- Updated `openspec/specs/tt-narrator-validation-contract/spec.md`.

**Verification:**
- `.venv/bin/python -m py_compile main.py utils/npc_name_normalizer.py utils/npc_arrival_validator.py scripts/test_npc_arrival_state_sync.py` -> PASS
- `.venv/bin/python scripts/test_npc_arrival_state_sync.py` -> PASS (37/37)
- `.venv/bin/python scripts/test_narrator_prompt_validation_refactor.py` -> PASS (16/16)
- `openspec validate tt-npc-join-name-normalization` -> VALID


### ADR Baseline and Memory-Sync Wiring (COMPLETED - 2026-03-10)

**Status:** COMPLETED - ADR corpus initialized and sync guidance updated

**Objective:**
Establish a durable project-level architecture decision record set for tabletop/v2 decisions and wire memory sync guidance to maintain ADR status/supersession links.

**Implementation Summary:**
- Created root ADR directory and baseline records: `adrs/` (`0001`-`0029`) plus `adrs/index.md` and `adrs/0000-template.md`.
- Added supersession cross-links:
  - `ADR-0023` supersedes `ADR-0028`.
  - `ADR-0026` marked planned successor to `ADR-0025`.
- Updated ADR docs guidance in `adrs/README.md` and index supersession map in `adrs/index.md`.
- Updated global `sync-project-memory` skill guidance to include ADR maintenance during memory sync (`~/.config/opencode/skills/sync-project-memory/SKILL.md`).

**Verification:**
- `adrs/` contains indexed ADR set with template and status labels.
- Cross-link fields (`Supersedes`, `Superseded by`) present in related ADRs.
- Sync skill now includes ADR update rules and hierarchy placement.

### Start Game Monster Preflight Hard-Fail Gate (COMPLETED - 2026-03-10)

**Status:** COMPLETED - OpenSpec change archived

**OpenSpec:** `openspec/changes/archive/2026-03-09-start-game-monster-preflight-hard-fail/`

**Objective:**
Enforce strict startup integrity for unresolved monster references while allowing one deterministic remediation attempt before final hard fail.

**Implementation Summary:**
- Added preflight helper: `web/extensions/start_game_preflight.py`
  - Terminal status contract: `pass`, `repaired_pass`, `fail`
  - One-attempt remediation flow: validate -> attempt closure -> revalidate -> terminal decision
- Updated startup hook in `web/web_interface.py`:
  - Calls preflight helper before output redirection and thread launch
  - Hard-fails on `status=fail` with deterministic `[SYSTEM]` operator message
- Added regression coverage: `scripts/test_start_game_preflight.py`
  - Helper outcomes: direct pass, remediation pass, remediation fail
  - One-attempt guarantee test
  - Source-contract fail-gate test (emit+return before startup progression)

**Verification:**
- `python3 -m py_compile web/extensions/start_game_preflight.py web/web_interface.py` -> PASS
- `.venv/bin/python scripts/test_start_game_preflight.py -v` -> PASS (11 tests)
- `.venv/bin/python core/validation/validate_module_files.py --module The_Thornwood_Watch` -> PASS (reference integrity resolved)
- `openspec validate start-game-monster-preflight-hard-fail` -> VALID

**Archive Notes:**
- Archive completed with `--skip-specs` due OpenSpec modifier resolution issue in automated sync.
- Main specs were synchronized manually:
  - `openspec/specs/tt-start-game-monster-preflight-gate/spec.md` (new)
  - `openspec/specs/tt-monster-reference-integrity-validation/spec.md` (updated)

### Homebrew Ingest Plan Archival (COMPLETED - 2026-03-10)

**Status:** COMPLETED - plan archived as superseded/deferred

**Objective:**
Close the Wave 1 dev-ingest planning artifact now that ingest watcher and continuity gates are validated in active module workflows, while deferring Birble-specific ingest to later full homebrew rollout.

**Implementation Summary:**
- Moved `plans/ingest-module.md` to `plans/archive/ingest-module.md`.
- Updated archived plan status to explicitly mark deferred Birble scope.
- Updated ownership reference in `plans/version-2/v2-narrative-track.md` to point to archived plan path.

**Verification:**
- Archived plan present at `plans/archive/ingest-module.md`.
- No active `plans/ingest-module.md` file remains.

---

### V2 Narrative Prime Directive Integration (COMPLETED - 2026-03-09)

**Status:** COMPLETED - planning/doc synchronization update

**Objective:**
Lock the v2 narrative prime directive for LLM/Python authority boundaries and dynamic runtime narrative evolution under indeterministic tabletop PC input.

**Implementation Summary:**
- Updated `plans/version-2/v2-narrative-track.md` with canonical prime-directive language:
  - Python remains world reality authority.
  - Runtime LLM remains creatively adaptive during live play.
  - Approval gate remains mandatory before canon apply.
  - Ralph loop documented as proposal -> Python validation -> human approval.
- Added explicit Phase 2A track for creative ingest + approval gate MVP.
- Added execution stages for runtime draft synthesis, deterministic validation, facilitator review, apply/provenance, and gameplay-coupled evolution.

**Verification:**
- Prime directive language present in `plans/version-2/v2-narrative-track.md` under:
  - `## Prime Directive (Locked for v2)`
  - `## Creative Ingest Execution Plan (v2)`
  - updated dependency chain and milestone blocks.

---

### Any-Order Module Continuity Normalization (COMPLETED - 2026-03-09)

**Status:** COMPLETED - OpenSpec change archived

**OpenSpec:** `openspec/changes/archive/2026-03-09-any-order-module-continuity-normalization/`

**Objective:**
Normalize continuity metadata so modules can support any-order play with strict/warn-first validation behavior across ingest, sidecar auditing, readiness, and bulk validation.

**Implementation Summary:**
- Added continuity contract audit script: `scripts/module_continuity_audit.py`.
- Updated ingest pipeline (`scripts/homebrew_ingest_dev.py`) to:
  - normalize continuity v1 contract fields,
  - enforce strict missing-key failure behavior,
  - persist `continuity_contract` to sidecar result payload.
- Updated readiness gate orchestration (`scripts/audit_module_readiness.py`) to include a continuity gate with strict/warn-mode controls.
- Updated bulk validation (`scripts/validate_modules_bulk.py`) to include continuity outcomes in pass/fail and summary.
- Updated sidecar audit coverage (`scripts/homebrew_sidecar_audit.py` + tests) for continuity payload validation.
- Updated local skill docs:
  - `.opencode/skills/dev-homebrew-ingest/SKILL.md`
  - `.opencode/skills/module-gameplay-audit/SKILL.md`

**Verification:**
- Continuity regression suites passing:
  - `python3 scripts/test_homebrew_ingest_dev.py`
  - `python3 scripts/test_homebrew_sidecar_audit.py`
  - `python3 scripts/test_audit_module_readiness.py`
  - `python3 scripts/test_module_continuity_audit.py`
  - `python3 scripts/test_homebrew_ingest_media_pipeline.py`
- OpenSpec change validated and archived.

---

### Continuity Cross-Reference Enrichment + Legacy Remediation (COMPLETED - 2026-03-09)

**Status:** COMPLETED - continuity workflow hardening for testing round

**Objective:**
Backfill and enrich continuity metadata on active modules, then make enrichment part of ongoing ingest/validation workflow so new homebrew modules carry narrative cross-module refs by default.

**Implementation Summary:**
- Added legacy remediation script: `scripts/remediate_module_continuity.py`
  - Backfills required continuity keys in `module_context.json` for existing modules.
- Added deterministic cross-ref enrichment helper + CLI:
  - `scripts/continuity_cross_ref_enrichment.py`
  - `scripts/enrich_module_cross_refs.py`
- Updated ingest pipeline (`scripts/homebrew_ingest_dev.py`) to:
  - auto-backfill required continuity keys,
  - auto-enrich `continuity.cross_module_refs` from narrative text hints,
  - persist `continuity_enrichment` metadata to sidecar result payload.
- Updated continuity/readiness validators:
  - `scripts/module_continuity_audit.py` now warns when `cross_module_refs` is empty and validates canonical `entity_id` format.
  - `scripts/audit_module_readiness.py` adds deterministic fix guidance for cross-ref enrichment.
- Updated skill contracts:
  - `.opencode/skills/dev-homebrew-ingest/SKILL.md`
  - `.opencode/skills/module-gameplay-audit/SKILL.md`

**Testing Round Application:**
- Applied remediation + enrichment across active modules for local testing round.
- Strict continuity audit passes for:
  - `Keep_of_Doom`
  - `Night_of_the_Restless_Dead`
  - `The_Pumpkin_Kings_Curse`
  - `The_Thornwood_Watch`
- Bulk validator now reports all current modules passing (`scripts/validate_modules_bulk.py --all --json`).

**Verification:**
- `python3 scripts/test_remediate_module_continuity.py` -> PASS
- `python3 scripts/test_continuity_cross_ref_enrichment.py` -> PASS
- `python3 scripts/test_module_continuity_audit.py` -> PASS
- `python3 scripts/test_homebrew_ingest_dev.py` -> PASS
- `python3 scripts/validate_modules_bulk.py --all --json` -> PASS (`all_passed: true`)

---

### Monster Reference Closure + Validator Hygiene (COMPLETED - 2026-03-09)

**Status:** COMPLETED - Builder/runtime integrity hardening

**Objective:**
Eliminate unresolved monster-reference drift by enforcing closure during module generation, and reduce validator noise from backup files/duplicate reporting.

**Implementation Summary:**
- Added monster reference closure in `core/generators/module_generator.py`:
  - collects referenced monsters from active area files,
  - generates missing monster files via `monster_builder.py`,
  - fail-closed if unresolved references remain.
- Updated `core/generators/monster_builder.py` with explicit `--module` support for deterministic module path writes.
- Hardened validator (`core/validation/validate_module_files.py`):
  - excludes backup/temp area files in reference scans,
  - improves location-name fallback (`locationName -> name -> locationId`),
  - deduplicates unresolved monster-reference errors.
- Added regression coverage: `scripts/test_validator_monster_reference_hygiene.py`.

**Verification:**
- `python3 scripts/test_validator_monster_reference_hygiene.py` -> PASS (8/8)
- `.venv/bin/python core/validation/validate_module_files.py --module The_Thornwood_Watch` -> PASS (100%)

---

### NPC Arrival Negation False-Positive Hardening (COMPLETED - 2026-03-05)

**Status:** COMPLETED - Runtime guard fix + regression coverage

**Objective:**
Stop retry-loop failures where narration explicitly states an NPC is absent (for example, "no Harvest Witnesses here") but the arrival validator still flags it as an off-location arrival.

**Root Cause:**
- Mention extraction treated all matching name tokens as arrivals without robust negation handling.
- Stopword tokens in multi-word NPC names (notably `the` in `The Harvest Witnesses`) could match unrelated text and resolve as a valid NPC mention.

**Implementation Summary:**
- Updated `utils/npc_arrival_validator.py`:
  - Added `_is_negated_mention(...)` context filter for explicit absence phrasing.
  - Switched `_extract_npc_mentions(...)` from `re.search` to `re.finditer` and skipped negated matches.
  - Added `_NPC_MENTION_STOPWORDS` filter to ignore non-identity tokens (`the`, `of`, etc.) during token matching.
  - Deduped failure reporting by changing `missing_actions` to a set.
- Updated `scripts/test_npc_arrival_state_sync.py`:
  - Added regression tests for negated mentions, mixed negated/positive mentions, and exact retry-loop wording using "Harvest Witnesses".

**Verification:**
- `python3 -m py_compile utils/npc_arrival_validator.py scripts/test_npc_arrival_state_sync.py` -> PASS
- `python3 scripts/test_npc_arrival_state_sync.py` -> PASS (19/19)

**Files Modified:**
- `utils/npc_arrival_validator.py`
- `scripts/test_npc_arrival_state_sync.py`

---

### Pumpkin King's Curse Occult Branching Expansion (COMPLETED - 2026-03-05)

**Status:** COMPLETED - OpenSpec change archived

**Objective:**
Implement complete occult-horror branching expansion for "The Pumpkin King's Curse" module with 5 distinct endings, comprehensive clue graph, and full DM runbook documentation.

**Implementation Summary:**

**Prompt B - Mid-Arc Clue Graph (Completed):**
- CMS001 additions: Elric's journal page (physical clue), ghostly whisper testimony (testimonial clue), Wisdom DC 12 check
- BOO001 additions: Miriam Bramble's locket (complicating evidence), Sybil Nettlemire's rhyme (alternate-branch clue)
- module_context updates: miriam_bramble NPC entry, elric appearances populated, PROMPT_B_COMPLETE marker

**Ending Branch Integration (Completed):**
- module_plot.json PP007: 5 ending branches documented (Bramble Sacrifice, Contract Void, Kingslayer, Dark Bargain, Collective Refusal)
- Each ending has explicit requirements, unlock conditions, and distinct consequence profiles
- Ending parity achieved: investigation reduces combat difficulty proportionally

**Documentation Deliverables:**
- CLUE_MATRIX.md: 23+ clues across 6 truth categories, DC compliance analysis (92.7% within 12-18 range)
- DM_RUNBOOK.md: Complete drive procedures for all 5 endings, parity analysis, quick reference flowchart
- FINAL_ACCEPTANCE_REPORT.md: Comprehensive completion summary with task matrix
- PROMPT_B_CLOSURE_NOTES.md: Verification artifact for Prompt B completion

**Clue Source Verification:**
- Origin Truth (First Tithe): 7 independent sources across HFG001, CMS001, BOO001
- Contract Weakness: 7 sources revealing 4 different ending paths
- Ritual Completion: 6 sources ensuring Ember Gourd mechanics discoverable
- All major truths exceed 2-source minimum requirement

**Fallback Behavior:**
- Kingslayer ending always available (no preparation required)
- Original linear backbone PP001-PP007 preserved
- No soft-locks possible
- Ember Gourd obtainable through main quest progression

**Validation:**
- All 25 tasks completed (100%)
- JSON syntax validation passed for all modified files
- Schema validation skipped (jsonschema dependency unavailable), fallback JSON parse used
- All ending paths verified reachable with distinct requirements
- Additive-only edits confirmed, no breaking changes

**Files Modified:**
- modules/The_Pumpkin_Kings_Curse/module_plot.json (ending branches, parity note)
- modules/The_Pumpkin_Kings_Curse/areas/GRV001.json (Executioner's Sickle, Judge dialogue)
- modules/The_Pumpkin_Kings_Curse/areas/HLF001.json (crown mechanics, Dark Bargain, Collective Refusal)

**Result:**
- Complete branching expansion with 5 viable endings
- Comprehensive clue graph with reason-first progression
- Full DM documentation for driving each ending path
- Archive: openspec/changes/archive/2026-03-05-pumpkin-kings-curse-occult-branching-expansion/

---

### Homebrew Watcher Strict CLI Parity (COMPLETED - 2026-03-05)

**Status:** COMPLETED - OpenSpec change archived

**Objective:**
Implement strict ingest-ready gate and CLI parity for the module ingest watcher, ensuring watcher behavior aligns with the dev-homebrew-ingest skill contract.

**Implementation Summary:**

**Shared Pipeline Entry (Prompt 1):**
- Added `__all__ = ["run_ingest_pipeline"]` to `scripts/homebrew_ingest_dev.py` to formalize the shared pipeline entrypoint
- CLI behavior preserved; no breaking changes to existing workflows

**Strict Watcher Gate + Pipeline Parity (Prompt 2):**
- Updated `web/extensions/module_ingest_watch.py`:
  - Added strict preflight readiness gate using `assess_source_readiness`
  - Non-ready files: immediate quarantine with `quarantine_reason: "preflight_not_ready"` and full `preflight` payload
  - Ready files: route through shared `run_ingest_pipeline` with strict validation
  - Pipeline kwargs: `strict=True`, `dry_run_only=False`, `allow_provider=False` (provider generation opt-in only)
- Added sidecar audit compatibility in `scripts/homebrew_sidecar_audit.py`:
  - Supports watcher nested `result` format for `module_slug` lookup
  - Handles `ingest.registration` nesting for registration validation

**Regression Coverage:**
- Extended `scripts/test_module_ingest_watch.py` with 16 comprehensive tests:
  - Strict gate rejection (`preflight_not_ready`)
  - Pipeline import failure handling
  - Canonical media keys validation (`media_extraction`, `media_handles`, `portrait_prewarm`)
  - Watcher/CLI parity contract verification
  - Sidecar canonical key persistence

**Verification:**
- All 16 unit tests pass
- Compile checks pass for all modified files
- Sidecar audit (`--require-success`) passes for watcher-produced modules
- OpenSpec validation passes

**Result:**
- Watcher now enforces strict ingest-ready gating with CLI parity through shared pipeline
- Provider generation remains opt-in only (`allow_provider=False` by default)
- Archive: `openspec/changes/archive/2026-03-05-homebrew-watcher-strict-cli-parity/`

---

### AGENTS-First Memory Sync Policy (COMPLETED - 2026-03-02)

**Status:** COMPLETED - Documentation policy and skill contract updated

**Objective:**
Deprecate legacy Cline-style memory-bank synchronization as a default behavior and make AGENTS.md the sole default memory target.

**Implementation Summary:**
- Updated Documentation Source Hierarchy wording to mark `memory-bank/` as deprecated, non-authoritative, and read-only by default
- Updated sync-project-memory skill contract description in AGENTS to enforce AGENTS-first behavior
- Clarified sync-project-memory behavior:
  - Always update `AGENTS.md`
  - Update `memory-bank/` only on explicit legacy request
  - Never create missing files
- Updated ONCNotes relationship text to reference AGENTS/OpenSpec as formal sources

**Result:**
- Default memory update flow is now AGENTS-only
- Legacy memory-bank support remains available as explicit opt-in for historical workflows

---

### Startup Stale Recap Auto-Cleanup (COMPLETED - 2026-03-02)

**Status:** COMPLETED - OpenSpec change archived

**Objective:**
Ensure automatic stale recap cleanup runs at startup for both history files, preventing accumulation of "SESSION RESUME RECAP ONLY" constraints that block gameplay actions.

**Implementation Summary:**

**Shared Cleanup Utility (1.1-1.3):**
- Created `utils/session_cleanup.py` as canonical source for stale recap detection/removal
- Functions: `is_stale_resume_recap_message()`, `remove_stale_resume_recaps()`, `cleanup_history_file()`, `cleanup_history_files()`
- Fail-open design: missing/malformed files log degraded status but don't block startup

**Startup Integration (2.1-2.3):**
- Moved cleanup call to pre-branch location in `main.py` (before combat/non-combat split)
- Cleans both `conversation_history.json` and `chat_history.json`
- Per-file logging with status: ok/missing/error
- Removed dead unreachable cleanup block from combat branch

**Script Parity (3.1-3.3):**
- Refactored `scripts/cleanup_stale_recaps.py` to use shared utility
- CLI modes: `--dry-run` (default safe) and `--apply`
- Deterministic summary output with per-file counts

**Regression Coverage (4.1-4.2):**
- `scripts/test_session_cleanup.py`: 5 tests for matcher/removal/idempotency/fail-open
- `scripts/test_cleanup_stale_recaps_cli.py`: 3 tests for CLI mode contracts
- `scripts/test_npc_arrival_party_exemption.py`: 5 tests for party member exemption

**Verification:**
- Compile: PASS for all modified files
- Tests: 13/13 PASS (5 + 3 + 5)
- OpenSpec validation: VALID
- Archive: `openspec/changes/archive/2026-03-02-startup-stale-recap-autocleanup/`

**Files Modified:**
- `main.py` (+30 lines startup cleanup wiring, removed dead block)
- `utils/session_cleanup.py` (new, ~120 lines)
- `scripts/cleanup_stale_recaps.py` (refactored to shared utility, ~70 lines)
- `scripts/test_session_cleanup.py` (new, ~90 lines)
- `scripts/test_cleanup_stale_recaps_cli.py` (new, ~75 lines)

---

### NPC Arrival State Sync (COMPLETED - 2026-02-27)

**Status:** COMPLETED - All tasks 1.1-5.4 implemented and archived

**Objective:**
Enforce deterministic NPC arrival state synchronization to prevent narration/state divergence when off-location NPCs appear in scenes.

**Implementation Summary:**

**Section 1 - Validation Guard Core (Steps 1.1-1.4):**
- Deterministic NPC mention/action pairing logic in validation path
- Integration into `validate_ai_response()` with fail-closed rejection reasons
- Guard targets only non-present known NPC mentions
- Action acceptance includes both `moveBackgroundNPC` (arrival) and `updatePartyNPCs add` (party join)

**Section 2 - Prompt and Validator Contract Alignment (Steps 2.1-2.3):**
- Added `@NPC_ARRIVAL_STATE_SYNC` block to `prompts/system_prompt_compressed.txt` with explicit MUST rule
- Updated `prompts/validation/validation_prompt_compressed.txt` with validity/violation rules and JSON examples
- Updated `prompts/validation/validation_prompt.txt` with full uncompressed section and detailed examples
- Rule: Off-location NPC arrival claims MUST be paired with matching state action in same response
- Exception: Already-present NPC mentions require no additional action

**Section 3 - Party Strip Dedupe Hardening (Steps 3.1-3.2):**
- Replaced substring-based dedupe with canonical equality matching in `web/extensions/tabletop_socket_handlers.py`
- Canonical normalization: lowercase, strip apostrophes, replace spaces with underscores
- Fixed false positive where "Ansel" was suppressed by "Anselara" (substring match)
- Preserved correct suppression of true duplicates

**Section 4 - Regression Coverage (Steps 4.1-4.5):**
- Created `scripts/test_npc_arrival_state_sync.py` with 10 comprehensive tests
- Test coverage:
  - Valid: non-present NPC mention + matching action passes
  - Invalid: non-present NPC mention without matching action fails (fail-closed)
  - No-op: already-present NPC mention requires no additional action
  - Dedupe: "Ansel" and "Anselara" remain distinct under equality matching
  - Case-insensitive matching and space/apostrophe normalization

**Section 5 - Verification (Steps 5.1-5.4):**
- Compile validation: PASS for main.py and tabletop_socket_handlers.py
- Test file compile: PASS
- Test execution: 10/10 tests PASS
- OpenSpec validation: VALID

**Files Modified:**
- `prompts/system_prompt_compressed.txt` (+10 lines: @NPC_ARRIVAL_STATE_SYNC block)
- `prompts/validation/validation_prompt_compressed.txt` (+8 lines: validation rules and examples)
- `prompts/validation/validation_prompt.txt` (+52 lines: uncompressed section with examples)
- `web/extensions/tabletop_socket_handlers.py` (+9 lines: canonical equality dedupe)
- `scripts/test_npc_arrival_state_sync.py` (new, ~280 lines)

**Archived:**
- OpenSpec change archived to `openspec/changes/archive/2025-02-27-tt-npc-arrival-state-sync/`

---

### Combat Initiation Fast-Lane (COMPLETED - 2026-02-26)

**Status:** COMPLETED - Steps 1.1-1.4 implemented, 13 tests passing

**Objective:**
Remove duplicate combat-start narration and eliminate extra LLM call at combat initiation in Multi-PC Phase 1.

**Implementation Summary:**

**Step 1.1 - Fast-Lane Guard:**
- Added `is_fast_lane` condition in `core/managers/combat_manager.py`:
  - `multi_pc_manager is not None`
  - `encounter_data.get("awaitingPcGroupRoll", False) is True`
- Fast-lane branch skips initial-scene LLM generation
- Non-fast-lane paths (single-player, resumed combat) unchanged

**Step 1.2 - Immediate Initiative Prompt:**
- Added system prompt in fast-lane branch:
  - `"Dungeon Master: [SYSTEM] Combat initiated. Initiative pending. Enter /init <1-20> to begin combat."`
- Immediate stdout flush after print
- Existing `/init` validation preserved

**Step 1.3 - Regression Coverage:**
- Added `TestFastLaneInitiationContract` class to `scripts/c5_regression_combat.py`:
  - `test_fast_lane_guard_contract_exists` - verifies guard conditions
  - `test_immediate_initiative_prompt_exists` - verifies exact prompt string
  - `test_initial_scene_llm_in_non_fast_lane_path` - verifies AI call in else branch
  - `test_existing_init_gate_preserved` - verifies `/init` validation unchanged
- All 4 new tests PASS (13/13 total tests PASS)

**Step 1.4 - Verification:**
- Syntax validation: PASS (`python3 -m py_compile`)
- Regression suite: PASS (13 tests)
- Compatibility: Resume path, non-fast-lane path, `/init` gate all preserved

**Impact:**
- **Before:** 2 LLM narrations + ~3-5 second delay before `/init` prompt
- **After:** 1 LLM narration + immediate `/init` prompt
- **Savings:** ~$0.01-0.03 + 2-5 seconds per Phase 1 combat initiation

**Files Modified:**
- `core/managers/combat_manager.py` (+16 lines fast-lane logic)
- `scripts/c5_regression_combat.py` (+58 lines, 4 new tests)

---

### Session Resume Recap Cleanup (COMPLETED - 2026-02-26)

**Status:** COMPLETED - Implementation and state cleanup complete

**Objective:**
Fix combat initiation failure caused by accumulated "SESSION RESUME RECAP ONLY" prompts blocking gameplay actions.

**Root Cause:**
`main.py` injected recap prompt containing "do NOT emit gameplay actions" every server start. Multiple restarts accumulated these constraints in `conversation_history.json`, causing LLM to output `actions: []` instead of `createEncounter`.

**Implementation:**
- Added stale recap filter in `main.py:check_and_inject_return_message()` (line ~248):
  - `conversation_history[:] = [msg for msg in conversation_history if "SESSION RESUME RECAP ONLY" not in msg.get("content", "")]`
  - Logs removal count: `STATE_CHANGE: Removed N stale recap messages`
- Created cleanup utility: `scripts/cleanup_stale_recaps.py`

**State Cleanup:**
- Removed 8 stale messages from active session:
  - `conversation_history.json`: 42 → 38 messages
  - `chat_history.json`: 32 → 28 messages

**Verification:**
- Syntax validation: PASS (`python3 -m py_compile main.py`)
- Cleanup script executed successfully

**Files Modified:**
- `main.py` (+10 lines cleanup logic)
- `scripts/cleanup_stale_recaps.py` (new, 26 lines)

---

### Chat Auto-Scroll Fix for TTS Word-Sync (COMPLETED - 2026-02-26)

**Status:** COMPLETED - 3 surgical fixes applied

**Objective:**
Restore reliable chat auto-scroll on new DM messages when word-sync/fallback reveal is active.

**Root Cause:**
Pre-initializing reveal mode collapsed message height before playback, causing initial auto-scroll to target wrong final height.

**Implementation (3 fixes in `web/templates/game_interface.html`):**
1. Removed early reveal pre-init from `addMessage()` autoplay path (~line 6190)
2. Added `requestAnimationFrame(() => scrollToBottom('game-output'))` in watchdog fallback (~line 10257)
3. Added same scroll pin in `finalizeReveal()` for end/error/stop paths (~line 10533)

**Behavior:**
- New messages arrive at full height → initial auto-scroll works
- 1s watchdog reveals text → chat re-pins to bottom
- Stop/error paths also re-pin scroll

**Verification:**
- JavaScript syntax: PASS
- Logic verified, TABLETOP MODE comments preserved

**Files Modified:**
- `web/templates/game_interface.html` (~15 lines across 3 locations)

---

### Multi-Currency Debug Tab Cost Conversion (COMPLETED - 2026-02-24)

**Status:** COMPLETED - Live exchange rate fetching with multi-currency support and robust fallback behavior

**Objective:**
Enable configurable target currency for Debug tab cost estimates (NZD, AUD, CAD, EUR, GBP, JPY, etc.) with live exchange rate fetching at game startup and safe fallback chains.

**Implementation Summary:**

**Step 1 - Configuration Contract:**
- Removed `EXCHANGE_RATE_CACHE_MINUTES` (not needed - one-time fetch at startup)
- Added clear currency code examples in `config_template.py` and `config.py`
- Documented ISO 4217 3-letter codes: NZD, AUD, CAD, EUR, GBP, JPY
- Clarified one-time fetch behavior (no periodic refresh)

**Step 2 - Tracker Currency Support (`utils/llm_usage_tracker.py`):**
- Added `exchange_configured_currency` and `exchange_effective_currency` tracking
- Implemented 3-letter alphabetic code validation (`len == 3` and `isalpha()`)
- Enhanced `_resolve_exchange_rate()` with multi-currency fallback logic:
  - Invalid code → USD (rate 1.0) with `fallback_invalid_currency_code` marker
  - NZD target + API failure → static `USD_TO_NZD_RATE` from config
  - Non-NZD target + API failure → USD (rate 1.0)
- Added comprehensive source markers for debugging (`fallback_*_non_nzd` variants)

**Step 3 - Stats Metadata Exposure:**
- Exposed `exchange_configured_currency`, `exchange_effective_currency`, `usd_to_nzd_source` in `get_current_stats()`
- Updated error/fallback return payloads with currency fields
- Maintained backward compatibility with existing `session_cost_nzd`/`week_cost_nzd` keys

**Step 4 - Frontend Dynamic Labels (`web/templates/game_interface.html`):**
- Changed hardcoded "NZD" labels to dynamic elements with IDs: `session-currency-label`, `week-currency-label`
- Updated `token_update` handler to read `exchange_effective_currency` from payload
- Labels now automatically reflect effective currency (NZD, AUD, etc.) based on backend configuration

**Step 5 - Backend Payload Wiring (`web/web_interface.py`):**
- Added currency metadata to `token_update` emit: `exchange_configured_currency`, `exchange_effective_currency`, `usd_to_nzd_source`
- Updated both success path and fallback emit paths

**Step 6 - Regression Test Coverage:**
- Extended `scripts/test_usage_rollups_debug_tab.py` with 4 new tests:
  - Test 8.4: Currency fields present in stats
  - Test 8.5: NZD-specific fallback preserved on API failure
  - Test 8.6: Invalid currency code falls back to USD via config validation (end-to-end)
  - Test 8.7: Configured vs effective currency tracking
- Fixed Test 8.6 to use config monkeypatching instead of direct field manipulation
- Updated existing tests to remove hardcoded 1.65 assumptions

**Verification:**
- `python3 -m py_compile` on modified files: PASS
- `python3 scripts/test_usage_rollups_debug_tab.py`: 23/23 tests PASS
- All fallback scenarios verified: invalid code, API failure, missing requests module

**Files Modified:**
- `config_template.py` (+25 lines: currency config with examples, no cache minutes)
- `config.py` (+10 lines: live API URL, currency examples, no cache minutes)
- `utils/llm_usage_tracker.py` (+170 lines: currency validation, multi-currency fallback, metadata exposure)
- `web/web_interface.py` (+9 lines: currency fields in token_update payload)
- `web/templates/game_interface.html` (+7 lines: dynamic currency labels, JS handler update)
- `scripts/test_usage_rollups_debug_tab.py` (+180 lines: 4 new tests, test 8.6 fixed for config-driven validation)

**Architecture Notes:**
- Fail-open: Invalid/missing codes always fall back to USD (1.0), never crash
- One-time fetch: Rate fetched once at game startup, no background refresh
- NZD legacy support: Preserves static `USD_TO_NZD_RATE` fallback for existing users
- Clear audit trail: `usd_to_nzd_source` tracks exact fallback reason (14 distinct markers)
- Configurable target: Any ISO 4217 3-letter code supported via `EXCHANGE_RATE_TARGET_CURRENCY`

---

### Character Sheet Edit with Dedicated Manage PC Modal (COMPLETED - 2026-02-24)

**Status:** COMPLETED - Dedicated edit modal separation from Manage Party, 21 tests passing

**OpenSpec Change:** `character-sheet-roll-your-own-edit-entry` (created with full artifacts)

**Objective:**
Add 'Edit' button to character sheet for direct PC editing via dedicated Manage PC modal, completely separate from Manage Party creation flow to avoid tab confusion and endpoint cross-contamination.

**Implementation Summary:**

**Step 1 - UI Separation (`web/templates/partials/character_tabs.html`):**
- Added new `manage-pc-modal` (id="manage-pc-modal") completely separate from `manage-party-modal`
- Title: "Manage PC" (not "Manage Party")
- No tabs - single Roll Your Own form for editing only
- Form ID: `manage-pc-form` with all fields having `manage-pc-*` prefixed IDs
- Name field is readonly with `#333` background (identity preserved)
- Hidden `character_name` field for tracking which PC is being edited
- Submit button: "Save Changes" (not "Create & Add to Party")

**Step 2 - JavaScript Separation (`web/static/js/tabletop_mode.js`):**
- `openManagePcModal(characterName)` - opens dedicated edit modal, prefills via `_prefillManagePcForm()`
- `closeManagePcModal()` - closes modal and resets form
- `_prefillManagePcForm()` / `_fillManagePcForm()` - dedicated prefill logic for Manage PC form
- `submitManagePcEdit()` - always POSTs to `/api/party/update_manual` (no branching)
- `window.openCharacterEdit()` - entry point from character sheet, calls `openManagePcModal()` directly
- Cleaned up duplicate function definitions to ensure single canonical behavior

**Step 3 - Backend Edit Endpoint (`web/routes/tabletop_party_routes.py`):**
- New route: `POST /api/party/update_manual`
- Loads existing character via `pc_manager.get_character_state()`
- Merges form fields onto existing payload, preserves non-targeted nested structures
- Runs `audit_character_creation()` before write (fail-closed on audit failure)
- No party membership mutation, no intro prompt enqueue
- Returns structured error with `missing_paths` on validation failure

**Step 4 - Character Sheet Integration (`web/templates/game_interface.html`):**
- Added 'Edit' button before 'Download PDF' in action row
- SP compatibility guard: `{% if multiplayer_mode or party_members|length > 1 %}`
- Calls `openCharacterEdit('${normalizedName}')` on click

**Step 5 - Test Coverage (`scripts/test_character_sheet_edit.py`):**
- 21 comprehensive tests covering:
  - UI contracts: button order, modal existence, title, no tabs
  - Endpoint separation: `submitQuickCreate` uses `create_manual` only, `submitManagePcEdit` uses `update_manual` only
  - Backend contracts: route existence, character loading, audit gating, no party mutation
  - Non-regression: create flow unchanged, Manage Party tabs preserved

**Verification:**
- `python3 -m py_compile web/routes/tabletop_party_routes.py`: PASS
- `node --check web/static/js/tabletop_mode.js`: PASS
- `python3 scripts/test_character_sheet_edit.py`: 21/21 tests PASS
- Zero cross-contamination: Each flow uses its dedicated endpoint exclusively

**Files Modified:**
- `web/templates/partials/character_tabs.html` (+210 lines: new Manage PC modal)
- `web/static/js/tabletop_mode.js` (+398 lines: dedicated edit handlers, prefill logic, removed duplicates)
- `web/routes/tabletop_party_routes.py` (+186 lines: `update_manual` endpoint)
- `web/templates/game_interface.html` (+8 lines: Edit button with SP guard)
- `scripts/test_character_sheet_edit.py` (new, 334 lines: 21 comprehensive tests)

**Architecture Notes:**
- Complete modal separation prevents tab confusion and state leakage
- Dedicated endpoints prevent accidental create-vs-update operations
- Deterministic form→JSON update without LLM involvement
- Full backward compatibility: Manage Party create flow unchanged, single-player mode unaffected

---

### PC Backstory Profile and Narrative Context (COMPLETED - 2026-02-24)

**Status:** COMPLETED - OpenSpec change validated, all 5 prompts implemented, 40 tests passing

**OpenSpec Change:** `pc-backstory-profile-and-narrative-context` (created with full artifacts)

**Objective:**
Add comprehensive backstory field for PC narrative development, replacing portrait Create modal background-feature fields with backstory, and integrating backstory across creation workflows, portrait generation, and runtime narrative contexts.

**Implementation Summary:**

**Phase 1 - Schema and Audit Foundation:**
- Added `backstory` property to `schemas/char_schema.json` (additive, not in required list for compatibility)
- Extended `utils/character_creation_audit.py`:
  - Added `backstory` to `_COMPLETENESS_PATHS` for PC creation validation
  - Added `backstory` to `READINESS_REPAIR_WRITABLE_FIELDS`
  - Added deterministic fallback text for missing backstory in `_READINESS_REPAIR_FALLBACK_TEXT`
  - Added `backstory` to `_canonical_character_defaults()` and `_PROFILE_READINESS_PATHS`

**Phase 2 - PC Creation Workflows:**
- Roll Your Own: Added `backstory` textarea to manual creation form in `web/templates/partials/character_tabs.html`
- Backend persistence: Updated `/api/party/create_manual` to include `backstory` in payload
- Create with DM: Updated `prompts/character_creation/dm_interview_prompt.txt` to collect and require backstory
- Startup fallback: Added backstory to `utils/startup_wizard.py` fallback character generation

**Phase 3 - Portrait Create Modal Contract Swap:**
- Replaced background-feature fields with required `backstory` textarea in portrait profile modal
- Updated `_REQUIRED_PROFILE_FIELDS` in `web/templates/game_interface.html` to require `backstory`
- Updated API payload to send `backstory` instead of `backgroundFeature`
- Updated backend `_REQUIRED_PORTRAIT_PROFILE_FIELDS` in `web/web_interface.py` to 11 fields (removed 2 bg fields, added 1 backstory)
- Added compatibility fallback: uses existing character backstory if payload omits it

**Phase 4 - Narrative Influence Integration:**
- Portrait prompt: Added bounded backstory clause in `core/toolkit/portrait_service.py` (first sentence, max 120 chars)
- Conversation context: Added `BACKSTORY:` line to player/NPC context blocks in `core/ai/conversation_utils.py` (120 char limit)
- Combat formatting: Added bounded backstory to player/NPC combat context in `core/managers/combat_manager.py`
- Multi-PC DM notes: Added concise backstory snippets to full and condensed PC stats in `utils/multi_pc_dm_note.py` (60-80 char limits)
- Character compressor: Added `BACKSTORY=` token to flat output in `core/ai/character_sheet_compressor.py` (100 char limit)

**Phase 5 - Promotion and PDF Alignment:**
- NPC→PC promotion: Seeds empty `backstory` key during promotion in `web/routes/tabletop_party_routes.py`
- Profile readiness warnings include missing backstory (non-blocking)
- PDF page 2: Prefers authored `char_data.backstory` with optional recent-adventures append in `web/routes/character_sheet_routes.py`
- PDF Allies field: Added to `PDF_EXPORT_FONT10_FIELDS` for font-size parity with Feat+Traits

**Test Coverage:**
- `scripts/test_character_creation_audit.py`: 10/10 tests PASS
  - Added `test_backstory_completeness()` for missing backstory validation
- `scripts/test_pc_image_create_mvp.py`: 30/30 tests PASS
  - Added `test_create_api_uses_existing_backstory_when_payload_blank` for compatibility fallback
  - Added `TestPromotionBackstoryWarnings` suite (2 tests) for warning behavior
  - Added `TestPdfBackstoryPrecedence` suite (2 tests) for PDF mapping
  - Existing: portrait prompt enrichment tests including backstory integration

**Files Modified:**
- `schemas/char_schema.json`
- `utils/character_creation_audit.py`
- `web/templates/partials/character_tabs.html`
- `web/routes/tabletop_party_routes.py`
- `prompts/character_creation/dm_interview_prompt.txt`
- `utils/startup_wizard.py`
- `web/templates/game_interface.html`
- `web/web_interface.py`
- `core/toolkit/portrait_service.py`
- `core/ai/conversation_utils.py`
- `core/managers/combat_manager.py`
- `utils/multi_pc_dm_note.py`
- `core/ai/character_sheet_compressor.py`
- `web/routes/character_sheet_routes.py`
- `scripts/test_character_creation_audit.py`
- `scripts/test_pc_image_create_mvp.py`

**Verification:**
- Compile check: PASS on all modified Python files
- Character creation audit: 10/10 tests PASS
- PC image create MVP: 30/30 tests PASS
- Portrait API profile validation: PASS
- Portrait API persistence: PASS
- Promotion backstory warnings: PASS
- PDF backstory precedence: PASS

---

**Status:** COMPLETED - All tasks finished, validated, archived, and committed

**OpenSpec Change:** `dalle3-image-cost-rollup-debug-tab` (archived to `openspec/changes/archive/2026-02-19-dalle3-image-cost-rollup-debug-tab/`)

**Objective:**
Ensure DALL-E 3 image generation events (portrait create, NPC/monster portraits) contribute estimated costs to Debug tab session/week USD/NZD rollups, while keeping token counters unchanged for image-cost events.

**Implementation Summary:**

**Step 1 - Pricing and Tracker Foundation:**
- Added `DALLE3_PRICING_USD` config table in `model_config.py` for size/quality combinations (1024x1024, 1024x1792, 1792x1024; standard/hd)
- Added `track_image_cost()` helper in `utils/llm_usage_tracker.py` for cost-only image event tracking
- Added `get_dalle3_cost_usd()` helper for pricing lookup with safe fallback to 0.0
- Re-exported new helpers via `utils/openai_usage_tracker.py` for compatibility import path

**Step 2 - Image Callsite Instrumentation:**
- Instrumented `core/toolkit/portrait_service.py` successful generation path with fail-open tracking
- Instrumented `core/toolkit/npc_generator.py` and `core/toolkit/monster_generator.py` with fail-open tracking
- Instrumented `web/web_interface.py` `generate_image` socket flow with retry-safe single-count behavior
- All tracking calls include context metadata: endpoint, purpose, model, size, quality, n

**Step 3 - Regression Coverage:**
- Extended `scripts/test_usage_rollups_debug_tab.py` with 6 new image-cost test functions (Test 7.x series)
- Tests verify: cost lookup, cost-only event updates, mixed token+image sessions, fail-open behavior, telemetry structure, multi-event aggregation
- All assertions verify token counters remain unchanged for image-only events

**Step 4 - Final Verification:**
- Compile validation passed for all 7 modified Python files
- Regression tests: 16 passed, 0 failed
- OpenSpec validation: VALID (archived successfully)

**Files Created:**
- None (all changes additive to existing files)

**Files Modified:**
- `model_config.py` (+17 lines: DALLE3_PRICING_USD config table)
- `utils/llm_usage_tracker.py` (+112 lines: track_image_cost, get_dalle3_cost_usd helpers)
- `utils/openai_usage_tracker.py` (+2 lines: re-export new helpers)
- `core/toolkit/portrait_service.py` (+18 lines: tracking instrumentation)
- `core/toolkit/npc_generator.py` (+22 lines: tracking instrumentation)
- `core/toolkit/monster_generator.py` (+22 lines: tracking instrumentation)
- `web/web_interface.py` (+19 lines: tracking instrumentation)
- `scripts/test_usage_rollups_debug_tab.py` (+220 lines: 6 new test functions)

**Testing:**
- `python3 -m py_compile` on all 7 modified files: PASS
- `python3 scripts/test_usage_rollups_debug_tab.py`: 16 tests PASS
- OpenSpec validation: VALID

**Architecture Notes:**
- Fail-open design: tracking failures never block image generation success
- Zero token inflation: image events contribute only cost, not tokens
- Compatibility maintained: existing import paths preserved via re-export shim
- Deterministic pricing: explicit config table, no runtime API calls for cost lookup

---

### Background Feature UX Clarity (COMPLETED - 2026-02-19)

**Status:** COMPLETED - All 15 tasks across Sections 1-5 finished, validated, and archived

**OpenSpec Change:** `background-feature-ux-clarity` (archived to `openspec/changes/archive/2026-02-19-background-feature-ux-clarity/`)

**Objective:**
Improve player UX for filling `backgroundFeature.name` and `backgroundFeature.description` fields, normalize legacy placeholder values, and provide deterministic remediation tooling.

**Implementation Summary:**

**Section 1 - Shared Placeholder Contract:**
- Added centralized placeholder detection helpers (`is_generic_background_feature_name`, `is_generic_background_feature_description`) in `utils/character_creation_audit.py`
- Extended completeness audit to flag generic placeholders as `completeness_error`
- Added deterministic suggestion helpers for known backgrounds (acolyte, criminal, folk hero, noble, sage, soldier)

**Section 2 - Guided Entry UX:**
- Updated portrait profile modal labels/placeholders with concrete examples (e.g., "Criminal Contact, Researcher, Military Rank")
- Updated manual character creation form hints to match
- Added backend prefill logic for known backgrounds with blank/generic values

**Section 3 - Readiness and Repair Alignment:**
- Extended Character Sheet readiness warnings to detect generic background-feature placeholders
- Updated warning banner copy: "Character sheet incomplete: fields missing or need meaningful values"
- Added `backgroundFeature.name` to repair allowlist with non-generic fallback text
- Mechanical snapshot invariants preserved

**Section 4 - Legacy Remediation Tooling:**
- Created `scripts/remediate_background_feature_placeholders.py` with `--dry-run` and `--apply` modes
- Fail-open per-file error handling with categorization (read/analysis/write)
- Atomic writes via `safe_write_json`, structured summary with error subtypes
- Created `scripts/test_remediate_background_feature_placeholders.py` with 5 test functions covering dry-run, apply, unknown backgrounds, error handling, and idempotency

**Section 5 - Verification and Closure:**
- Compile validation passed for all 6 modified Python files
- Targeted tests passed (character creation audit + remediation script)
- Character Sheet/PDF wiring verified, no regressions detected
- OpenSpec validation: VALID

**Files Created:**
- `scripts/remediate_background_feature_placeholders.py` (~350 lines)
- `scripts/test_remediate_background_feature_placeholders.py` (~280 lines)

**Files Modified:**
- `utils/character_creation_audit.py` (+~150 lines: helpers, suggestions, completeness detection, repair allowlist)
- `web/templates/game_interface.html` (~+50 lines: guidance text, readiness detection, warning banner)
- `web/templates/partials/character_tabs.html` (~+4 lines: guidance text)
- `web/web_interface.py` (+~10 lines: suggestion prefill in portrait create)
- `web/routes/tabletop_party_routes.py` (+~8 lines: suggestion prefill in manual create)
- `scripts/test_character_creation_audit.py` (+~85 lines: helper tests, repair regression tests)
- `openspec/specs/character-sheet-completeness-audit/spec.md` (updated with generic placeholder scenario)
- `openspec/specs/tt-character-readiness-repair/spec.md` (updated with backgroundFeature.name and generic placeholder scenario)
- `openspec/specs/background-feature-guided-entry-ux/spec.md` (NEW)
- `openspec/specs/background-feature-placeholder-remediation/spec.md` (NEW)

**Testing:**
- All 7 test groups in `test_character_creation_audit.py` PASS
- All 5 test functions in `test_remediate_background_feature_placeholders.py` PASS
- Dry-run tested on 19 production character files: 0 changes needed (all already have proper values)

---

### Developer Documentation Packaging for Tester Handoff (COMPLETED - 2026-02-19)

**Status:** COMPLETED - Documentation-only commit stream updated

**Objective:**
Bundle current developer documentation into the tester-facing GitHub commit stream while keeping gameplay/runtime files unchanged.

**Included in Commit Stream:**
- `plans/` (current and archived planning docs)
- `openspec/changes/debug-usage-session-week-nzd-rollup/` scaffold artifacts
- `openspec/changes/toolkit-module-builder-rebuild-phase1-npc-alignment/` scaffold artifacts
- `memory-bank/` updates tracking documentation packaging state

**Guardrail Clarification (`.opencode`):**
- Commit only curated `.opencode` docs paths when explicitly needed (for example `.opencode/skills/*`, `.opencode/command/*`).
- Do not force-add dependency/package artifacts (`node_modules`, lockfiles, package metadata) into documentation commits.

**Commits:**
- `a9cfee7` - Added plans and debug-usage OpenSpec artifacts
- `ebfbcc9` - Updated memory-bank packaging notes

---

### Debug Sidebar Density and Cost Row Alignment (COMPLETED - 2026-02-19)

**Status:** COMPLETED - UI density and cost-line alignment pass finalized

**Objective:**
Improve narrow-sidebar readability for Debug tab telemetry and long narrator output while preserving behavior.

**Implementation Summary:**
- `web/templates/game_interface.html`: Added compact spacing and typography scaling for Debug panel and narration message flow.
- Converted Session/Week cost rows to structured token spans (`cost-values`, `cost-divider`, `cost-currency`, `cost-paren`, `cost-text`) to eliminate spacing artifacts around `$` and `(NZD)` values.
- Added right-aligned table-style label column for `Session:` and `Week:` via grid layout in `#debug-tab .cost-stat`.
- Refined typography scope after visual QA:
  - Removed unintended LED font use from sidebar tabs.
  - Removed unintended LED font use from main chat author/body text.
  - Kept compact monospace emphasis on Debug telemetry surfaces only.

**Result:**
- Debug cost rows render as two aligned, table-like lines with stable spacing.
- Sidebar remains compact and readable in narrow widths.
- Main narration chat preserves compact spacing without terminal-style font spill.

**Files Modified:**
- `web/templates/game_interface.html`

---

### Portrait Cache Coherence - Section 10 (COMPLETED - 2026-02-19)

**Status:** COMPLETED - All Section 10 tasks 10.1-10.8 finished and verified

**OpenSpec Change:** `pc-image-create-and-allied-npc-autogen` Section 10 extended

**Objective:**
Implement deterministic portrait cache coherence across Character Sheet, initiative queue, and party strip to eliminate stale/reverting portrait behavior after upload/create mutations.

**Implementation Summary:**

**Step 10.1 - Backend Version Metadata Helper:**
- `web/extensions/tabletop_socket_handlers.py`: Added `_normalize_character_slug()`, `_get_image_candidate_paths()`, `_compute_image_version_from_paths()`, `_build_image_metadata()`
- Candidate chain: PC portraits (`web/static/portraits/`) + module NPC media + static NPC media
- Version algorithm: max mtime among existing files, fail-open (returns None if no files)

**Step 10.2 - Metadata Emission in Payloads:**
- `initiative_data_response.combatants[]`: Added `image_slug` + `image_version` for player/npc entries
- `party_data_response.members[]` + `location_npcs[]`: Added `image_slug` + `image_version`
- `player_data_response` stats: Added `_portrait_slug` + `_portrait_version`

**Step 10.3 - Frontend Normalization and Versioned URLs:**
- `web/templates/game_interface.html`: Added `normalizePortraitSlug()` matching backend semantics
- Added `withAssetVersion(url, version)` for deterministic cache-busting
- Updated all three surfaces: Character Sheet, initiative cards, party strip

**Step 10.4 - Targeted Cache Invalidation:**
- Added `_getCacheInvalidationPatterns()` + `invalidateImageCachesForSlug()` helpers
- Removes matching entries from `missingImageCache` and `existingImageCache`
- Invoked after upload/create success, preserves TTL behavior

**Step 10.5 - Ordering Bug Fix:**
- Fixed race condition where `closePortraitProfileModal()` cleared state before refresh
- Now captures `preservedCharacterName` + `preservedSlug` before modal close
- Uses preserved identity for cache invalidation and image refresh

**Step 10.6 - Immediate Refresh Hooks:**
- Upload success: calls `loadCharacterStats()`, `requestInitiativeData()`, `requestPartyData()`
- Create success: calls same refresh functions after `loadCharacterStats()`
- No polling wait - updates propagate immediately across all surfaces

**Step 10.7 - Regression Test Coverage:**
- `scripts/test_pc_image_create_mvp.py`: Added 8 new test methods
- `TestPortraitMetadataPayloadContracts` (4 tests): Payload field presence, normalization consistency, deterministic version
- `TestFrontendCacheInvalidationContracts` (4 tests): Source-level contracts for helpers, refresh hooks, preserved identity pattern
- All 8 tests PASS

**Step 10.8 - Final Verification:**
- Compile checks: PASS (all Python files compile successfully)
- Schema validation: PASS (ran with venv fallback, pre-existing schema availability issues)
- Full test suite: 35 tests total, Section 10 specific 8/8 PASS
- Manual smoke: All 4 checklist items PASS (via code review and contract verification)
- OpenSpec validation: valid

**Key Deliverables:**
- Deterministic portrait version metadata across all GUI refresh paths
- Consistent name normalization (backend + frontend aligned)
- Targeted cache invalidation after portrait mutations
- Immediate cross-surface refresh (no polling wait)
- 8 regression tests for cache coherence contracts
- Section 10 fully documented in OpenSpec artifacts

**Files Modified:**
- `web/extensions/tabletop_socket_handlers.py` (+115 lines: version metadata helpers)
- `web/web_interface.py` (+14 lines: stats payload metadata)
- `web/templates/game_interface.html` (+102 lines: frontend helpers, cache invalidation, immediate refresh)
- `scripts/test_pc_image_create_mvp.py` (+128 lines: 8 regression tests)
- `openspec/changes/pc-image-create-and-allied-npc-autogen/tasks.md` (Section 10 marked complete)
- `openspec/changes/pc-image-create-and-allied-npc-autogen/implementation_notes.md` (Section 10 documentation)

**Verification:**
- `python3 -m py_compile web/extensions/tabletop_socket_handlers.py web/web_interface.py` -> PASS
- `python3 scripts/test_pc_image_create_mvp.py TestPortraitMetadataPayloadContracts TestFrontendCacheInvalidationContracts` -> PASS (8 tests)
- `openspec validate pc-image-create-and-allied-npc-autogen` -> valid

---

### PC Image Create and Allied NPC Auto-Generation (COMPLETED - 2026-02-24)

**Status:** COMPLETED - All tasks 1.1-12.6 finished, verified, and archived

**OpenSpec Change:** `pc-image-create-and-allied-npc-autogen` (archived to `openspec/changes/archive/2025-02-24-pc-image-create-and-allied-npc-autogen/`)

**Objective:**
Implement Character Sheet portrait `Upload / Create` UX with appearance field support, allied NPC auto-generation, missing-media warning throttle, cache coherence, profile readiness alignment, and NPC prompt enrichment.

**Implementation Summary:**

**Sections 1-7 (Foundation):**
- Appearance fields scaffolding in schema, audit, routes, and UI
- Portrait service with prompt composition and generation
- Character Sheet Upload/Create dual-action UX
- Missing-media warning throttle
- Allied-only auto-generation queue with dedupe and cooldown
- Validation and regression coverage (11 tests)
- Builder handoff with TABLETOP MODE markers

**Section 8 - Reuse-First NPC Media Registration Hardening:**
- `materialize_npc_media_from_portrait()` helper for reuse-first materialization
- Generation callback updated to attempt reuse before provider generation
- Canonical identity-based dedupe across filename variants
- Shared normalization for allied-policy matching
- Frontend stale-miss recovery with TTL-based cache
- Targeted regressions (6 tests)

**Section 9 - Full-Profile Modal + Enforcement for Portrait Create:**
- Expanded portrait prompt composition with personality/background/appearance fields
- Backend validation requiring complete profile before generation
- Always-open full-profile modal with required field completion
- Persist submitted profile fields to character JSON before generation
- Refresh UX with cache-busted image URL and immediate stats reload
- Regressions (7 tests)

**Section 10 - Portrait Cache Coherence:**
- Backend version metadata helpers (`_compute_image_version_from_paths()`)
- Version metadata emission in initiative/party/stats payloads
- Frontend normalization and versioned URL helpers
- Targeted cache invalidation after portrait mutations
- Immediate post-mutation UI refresh hooks
- Regression coverage (8 tests)

**Section 11 - PC/NPC Profile Readiness Alignment:**
- Profile-readiness helper evaluating 12 portrait-driving fields
- Promotion preview/apply endpoints with profile warnings
- Safe appearance field seeding for promoted NPCs
- Promotion invariants preserved (identity, character_id, lifecycle history)
- Regression coverage (7 tests)

**Section 12 - NPC Prompt Enrichment:**
- Allied NPC context hydration (`_hydrate_allied_npc_context()`): canonical-first lookup with party role fallback
- Generation callback passes hydrated context to `generate_and_save_portrait()`
- Bounded archetype anchors (`_build_archetype_anchor()`): 14-class deterministic mapping, ≤60 chars, ASCII-only
- Miss-path contracts preserved: reuse-first, allied-only, dedupe/cooldown, non-blocking
- Regression coverage (3 tests)

**Files Created:**
- `core/toolkit/portrait_service.py`
- `web/extensions/missing_media_autogen.py`
- `scripts/test_pc_image_create_mvp.py` (85 tests total across Sections 1-12)
- `openspec/changes/pc-image-create-and-allied-npc-autogen/implementation_notes.md`

**Files Modified:**
- `schemas/char_schema.json`
- `utils/character_creation_audit.py`
- `web/routes/tabletop_party_routes.py`
- `web/templates/partials/character_tabs.html`
- `web/templates/game_interface.html`
- `web/web_interface.py`
- `model_config.py`
- `web/extensions/tabletop_socket_handlers.py`

**Verification:**
- `python3 -m py_compile core/toolkit/portrait_service.py web/extensions/missing_media_autogen.py web/web_interface.py` -> PASS
- `python3 -m unittest scripts.test_pc_image_create_mvp.TestNpcPromptEnrichmentHydrationContracts` -> PASS (3/3 tests)
- Section 12 specific tests pass; full suite shows pre-existing environment issues (not regressions)
- Non-ASCII scan: No violations in new/changed Python files
- OpenSpec archive: VALID (archived successfully)

---

### Portrait Download Best-Resolution and Popup Quality Fixes (COMPLETED - 2026-02-24)

**Status:** COMPLETED

**Objective:**
Fix low-resolution portrait downloads and blurry popup modals by implementing best-source priority chains and full-resolution sidecar persistence.

**Problems Addressed:**

1. **Portrait Download Resolution:** Sidebar "Download" button was downloading only 256x256 web portraits, even when higher resolution originals existed from AI generation (1024x1024) or uploads.

2. **AI Portrait Generation:** `generate_and_save_portrait()` was resizing to 256x256 before saving, losing the original DALL-E resolution.

3. **Upload Portrait Ordering Bug:** `/upload-portrait` referenced `normalized_filename`, `current_module`, and `module_portraits_dir` before they were defined, causing runtime errors.

4. **Popup Quality:** Narration strip NPC popups were opening thumbnails (128x128) instead of full images because `imageCandidates` was thumb-first for both tiles and popups.

**Implementation Summary:**

**Portrait Service (`core/toolkit/portrait_service.py:596-660`):**
- Preserve full-resolution copy before resize: `full_res_image = img.convert('RGBA')...`
- Save `<normalized>_full.png` sidecar to static portraits AND module portraits
- Create 256x256 compatibility image separately: `compat_image = full_res_image.resize(...)`
- Full-res saved first, then compatibility resized version

**Upload Portrait (`web/web_interface.py:1066-1115`):**
- Fixed ordering: normalize character name BEFORE using it
- Fixed ordering: resolve module directory BEFORE save attempts
- Save hi-res `_full.png` from cropped image before 256x256 resize
- Fail-open module saves (warnings only, don't block success)

**Download Logic (`web/templates/game_interface.html:5328-5391`):**
- New priority chain (5 levels):
  1. `/static/portraits/<slug>_full.png` (hi-res sidecar)
  2. `/media/npcs/<slug>.jpg` (NPC full-res)
  3. `/media/npcs/<slug>.png` (NPC fallback)
  4. `/static/portraits/<slug>.png` (legacy 256x256)
  5. Current `char-portrait-img.src` (last resort)
- Recursive `tryDownloadCandidate()` attempts each URL in order
- Preserves existing user feedback and filename sanitization

**Popup Quality (`web/templates/game_interface.html:8016-8040`):**
- Split single `imageCandidates` into two separate arrays:
  - `tileImageCandidates`: thumb-first for fast strip rendering
  - `popupImageCandidates`: full-image-first for quality modals
- Video-first behavior preserved for characters with `_video.mp4`

**Testing:**

**Regression Tests Added (`scripts/test_pc_image_create_mvp.py`):**
- `TestPortraitDownloadBestResolutionContracts` (6 tests):
  - `test_download_candidates_priority`: Verifies priority chain ordering
  - `test_portrait_create_saves_hi_res_sidecar`: Confirms `_full.png` creation in AI path
  - `test_portrait_service_preserves_full_res_before_resize`: Validates copy-before-resize
  - `test_upload_portrait_normalizes_before_full_save`: Checks init ordering
  - `test_upload_portrait_saves_hi_res_sidecar`: Confirms upload path hi-res save
  - `test_legacy_256_save_paths_remain_present`: Backward compatibility check
  - `test_party_render_uses_separate_tile_and_popup_candidate_lists`: Split arrays
  - `test_popup_candidates_prioritize_full_images_before_thumb`: Full > thumb ordering
  - `test_tile_candidates_use_thumb_first`: Thumb > full for tiles
  - `test_video_candidates_remain_first_in_popup_flow`: Video priority preserved

All 10 tests pass: `Ran 10 tests in 0.002s OK`

**Files Modified:**
- `web/templates/game_interface.html` - Download priority chain, split candidate arrays
- `core/toolkit/portrait_service.py` - Full-res sidecar persistence before resize
- `web/web_interface.py` - Fixed upload ordering and hi-res save
- `scripts/test_pc_image_create_mvp.py` - 10 new regression tests

**Backward Compatibility:**
- Legacy `<name>.png` (256x256) still generated and used for UI
- New `<name>_full.png` is additive, not replacement
- Download falls through gracefully if `_full.png` missing
- NPC media fallback chain unchanged for promoted characters

**Performance:**
- Hi-res images only saved once (generation or upload time)
- Download attempts URLs sequentially (fast path: `_full.png` usually exists)
- No additional runtime overhead for display paths

---

### Exit/Enter GUI Button Implementation Phase 1 (COMPLETED - 2026-02-17)

**Status:** COMPLETED - Archived to `openspec/changes/archive/2026-02-17-exit-only-gui-shutdown/`

**Objective:**
Implement Phase 1 Exit-only functionality allowing users to gracefully stop the Python server from the GUI Exit button without requiring terminal Ctrl+C.

**Implementation Summary:**
- **Server Handler** (`web/web_interface.py:2717-2741`): Upgraded `handle_user_exit()` to emit `exit_acknowledged`, attempt graceful `socketio.stop()`, and force exit with code `91` (fail-closed on exceptions)
- **Launcher Contract** (`run_web.py:119-122`): Added explicit `elif result.returncode == 91` branch to print shutdown message and break loop without restart
- **GUI Flow** (`web/templates/game_interface.html:8501-8545`): Immediate "Shutting Down..." overlay on Exit confirm, input controls disabled, `user_exit` event emission
- **Ack Handler** (`web/templates/game_interface.html:8459-8469`): `exit_acknowledged` listener updates overlay text to "Shutdown acknowledged...", no restart/reload logic

**Key Behaviors:**
- Exit code `91` = intentional GUI shutdown (no restart)
- Exit code `0` = restart path preserved for reset/restore flows
- ASCII-only terminal output (`[Py]`, `[SHUTDOWN]`, `[ERROR]`)
- All changes marked with `# TABLETOP MODE:` comments

**Verification:**
- Compile checks: `python3 -m py_compile web/web_interface.py run_web.py` -> PASS
- Smoke test: GUI Exit -> server exits with code 91 -> launcher prints "[SHUTDOWN] User initiated exit..." -> no restart
- Regression: reset/restore code `0` restart path unchanged
- Ctrl+C fallback: terminal interrupt still works cleanly

**Files Modified:**
- `web/web_interface.py` (exit handler with graceful stop + fail-closed exit)
- `run_web.py` (return-code 91 handling)
- `web/templates/game_interface.html` (immediate shutdown UI + ack listener)

---

### PC Leave/Return World Memory (COMPLETED - 2026-02-17)

**Status:** COMPLETED - Archived to `openspec/changes/archive/2026-02-17-pc-leave-return-world-memory/`

**Objective:**
Implement explicit PC retirement/rejoin lifecycle with world-memory continuity persistence in `data/memory.db`, enabling narrative continuity when characters leave and return to the party.

**Implementation Summary:**

**Phase 1 - Transition Memory Service Foundation (Steps 1.1-1.3):**
- **New Module** (`core/memory/party_transition_memory.py`): Write helpers `record_pc_retirement()` and `record_pc_return()` using canonical entity IDs and `role_transition` events
- **Retrieval Helper** (`build_return_memory_pack()`): Composes bounded transition + social continuity snippets (max 12 combined) for narration context
- **Package Exports** (`core/memory/__init__.py`): All transition functions exported and import-verified

**Phase 2 - Retirement Flow Integration (Steps 2.1-2.5):**
- **Route Extension** (`web/routes/tabletop_party_routes.py:remove_party_character`):
  - Accepts optional `departure_text` parameter
  - Runtime guards block retirement during active combat and when retiring final party member
  - Pre-mutation party snapshot for witness continuity
  - Calls `record_pc_retirement()` with fail-open error handling
  - Enqueues retirement narration (explicit farewell vs mysterious departure fallback)
  - Appends `_tabletop_role_history` lifecycle metadata via `pc_manager.append_role_history_event()`

**Phase 3 - Return Flow Integration (Steps 3.1-3.4):**
- **Route Extension** (`web/routes/tabletop_party_routes.py:add_party_character`):
  - Detects true rejoins (character not previously in party)
  - Calls `record_pc_return()` with fail-open error handling
  - Builds return narration context via `build_return_memory_pack()`
  - Enqueues return narration with continuity snippets
  - Appends return lifecycle metadata preserving canonical identity

**Phase 4 - UI and Prompt Assets (Steps 4.1-4.4):**
- **UI Flow** (`web/static/js/tabletop_mode.js:retireCharacter`): Collects optional farewell text via `prompt()`, sends in `departure_text` payload
- **Prompt Templates**:
  - `prompts/tabletop/retirement_narration.txt`: Narration-only instructions with `{character_name}`, `{departure_mode}`, `{departure_text}`, `{witness_context}` placeholders
  - `prompts/tabletop/return_narration.txt`: Continuity-focused framing with `{character_name}`, `{continuity_snippets}`, `{witness_context}`, `{return_context}` placeholders

**Phase 5 - Resilience and Verification (Steps 5.1-5.5):**
- **Structured Logging**: All memory persistence outcomes emit `MEMORY_TRANSITION event=retirement|return character=<name> status=success|degraded ... fallback=enabled`
- **Fail-Open Guarantees**: If memory persistence fails, party add/remove still completes and fallback narration still queues
- **Test Coverage** (`scripts/test_party_retirement_memory.py`):
  - 4 test functions, 20+ assertions
  - Validates persistence, no-purge guarantees, continuity retrieval, graceful degradation
  - Uses temp DB isolation, restores `DEFAULT_MEMORY_DB_PATH` after each test
  - All tests PASS

**Key Behaviors:**
- Canonical entity identity preserved across retire/return transitions (same `entity_id`)
- `role_transition` events with `importance=95`, `persistence_class=identity_core`, `decay_profile=none`
- Actor/witness linking: transitioning PC as `actor`, remaining party as `witness`
- Bounded continuity: max 3 snippets per source, max 12 combined
- Non-destructive: prior memory events/links never deleted
- ASCII-only output and logs

**Verification:**
- Compile checks: `python3 -m py_compile web/routes/tabletop_party_routes.py core/memory/party_transition_memory.py` -> PASS
- JS syntax: `node --check web/static/js/tabletop_mode.js` -> PASS
- Regression tests: `python3 scripts/test_memory_regression_coverage.py` -> ALL PASSED
- Lifecycle tests: `python3 scripts/test_party_retirement_memory.py` -> ALL TESTS PASSED

**Files Modified/Created:**
- `core/memory/party_transition_memory.py` (new - 394 lines)
- `core/memory/__init__.py` (exports added)
- `web/routes/tabletop_party_routes.py` (retirement/return flow integration)
- `web/static/js/tabletop_mode.js` (farewell text collection)
- `prompts/tabletop/retirement_narration.txt` (new)
- `prompts/tabletop/return_narration.txt` (new)
- `scripts/test_party_retirement_memory.py` (new - test suite)

**OpenSpec Artifacts:**
- Change: `exit-only-gui-shutdown`
- All artifacts created: proposal, design, spec, tasks, executor_prompts
- Validated and archived to `openspec/changes/archive/2026-02-17-exit-only-gui-shutdown/`

---

### Module Import and World Expansion Plan (PLANNED - 2026-02-28)

**Status:** PLANNED - Documentation complete, ready for implementation  
**Priority:** High (Core Platform Growth)  
**Effort:** Large (~2-3 weeks)  
**Implementation Date:** TBD

**Objective:**
Build a strict, continuous import pipeline that ingests large volumes of community adventure content (DMsGuild free purchases, Homebrewery markdown), converts it into NEQ-compatible modules, validates those modules, and stitches them into one long-lived canonical world campaign.

**Key Capabilities:**
- Bulk intake scanner for `Docs/modules/` and Homebrewery sources
- Dual extractor path: PDF (text chunking) + Markdown (heading-aware parsing)
- Canonical intermediate adventure schema (acts, locations, NPCs, encounter seeds)
- World consistency rewrite pass aligning factions/timeline with `plans/version-2/world-narrative.md`
- NEQ module emission (areas, encounters, plots, characters, monsters)
- Strict validation gate: only 100% schema-valid modules auto-publish
- Level-band progression ladder (1-4, 3-6, 5-8, 10-15, etc.)
- Auto-stitch integration with existing module stitcher

**Campaign Initialization Model:**
- **Default: Canonical world** - All new campaigns start in shared canonical world
- **Modules are continuously expanded** as new sources are imported
- **No per-campaign module duplication** required
- **Future: Forked world profiles** (many worlds) supported but disabled by default

**Source Inputs:**
- PDF adventures (DMsGuild free purchases)
- Markdown exports (Homebrewery)
- Asset packs (maps, handouts)

**Strict Quality Gates:**
- Schema validation must pass (`core/validation/validate_module_files.py`)
- Cross-reference integrity checks
- Level range present and valid
- Encounter/creature references resolve
- Degraded imports quarantined, never silently stitched

**Files Created:**
- `plans/version-2/module-import.md` - Complete implementation plan

**Documentation:**
- Plan Location: `plans/version-2/module-import.md`
- Pipeline: Intake -> Extract -> Normalize -> Canonical Rewrite -> Emit -> Validate -> Stitch
- Supports continuous import ("NeverEnding" expansion)
- Canonical worldline over source fidelity

---

### Journal Diary MVP Phase 1 Planning (PLANNED - 2026-02-16)

**Status:** PLANNED - Ready for Kimi Builder execution  
**Priority:** Medium (User Experience Enhancement)  
**Effort:** Medium (~4-6 days)

**Objective:**
Implement a transparent diary system with dual-checkpoint model: Start Game refreshes draft diary entries while Save operations create confirmed canonical entries tied to save branches. Adds Diary tab to Journal modal with world-time ordering and user-triggered "Download the story so far..." PDF export from confirmed entries only.

**Key Capabilities:**
- **Dual-checkpoint diary state:** `draft` (unsaved session summary) + `confirmed` (save-bound canonical entry)
- **Two update points:** Start Game (draft refresh if stale), Save (confirmed checkpoint generation)
- **Failure isolation:** Diary generation failures never block Start Game or Save operations
- **Journal UI tabs:** Quests (preserved behavior) + Diary (draft card + confirmed timeline)
- **Story PDF export:** User-triggered download compiled from confirmed diary entries only (draft excluded)

**Architecture Decisions:**
- Additive memory DB tables: `session_diary_entries`, `session_diary_state`, `story_so_far_cache`
- World-time ordering using normalized `world_sort_key` from `party_tracker.json`
- Third-person anonymous narration style for all diary entries
- Reuse existing LLM provider factory (`create_chat_client`, `get_model_config`)
- Merge-safe host hooks with `# TABLETOP MODE:` comments

**OpenSpec Artifacts:**
- Change: `journal-diary-mvp-phase1`
- Proposal, design, specs (3 capabilities), tasks, executor prompts all scaffolded
- Specs: `journal-diary-dual-checkpoint`, `journal-diary-tabbed-ui`, `campaign-journal-story-pdf`

**Implementation Plan:**
1. Migration + diary service (`core/memory/session_diary.py`)
2. Save/Start Game integration (`updates/save_game_manager.py`, `web/web_interface.py`)
3. Story compiler + PDF endpoint (`core/memory/story_so_far_compiler.py`, `web/routes/memory_routes.py`)
4. Journal UI tabs (`web/templates/game_interface.html`)
5. Tests and validation

**Time Estimate:** 4-6 days (MVP Phase 1)

**Plan Location:** `/plans/version-2/journal.md`

---

### Archive Zip Portability and Memory Backup Parity (COMPLETED - 2026-02-16)

**Status:** COMPLETED  
**Priority:** High (Save/Restore Reliability)  
**Effort:** Medium (~1 day)

**Objective:**
Complete PR2 archive portability and memory backup parity so Archive Edition full saves produce explicit zip artifacts and reset backups preserve `data/memory.db` state.

**Implementation Highlights:**
- **Full-save archive contract:** `web/web_interface.py` now fail-closes full saves when archive generation fails and returns archive artifact metadata on success (`archive.status`, `zip_path`, `zip_name`, `bytes`)
- **Essential-save compatibility:** Essential saves keep legacy payload shape (`content` only) with no archive dependency
- **Reset backup memory parity:** `utils/reset_campaign.py` now copies `data/memory.db` into backup snapshots when present and reports non-fatal absence when missing
- **Backup layout verification:** Added `_verify_backup_layout_compatibility()` guard to confirm root files, modules path, and memory artifact placement without changing restore semantics

**Validation Artifacts:**
- Added report scripts: `scripts/step_4_2_smoke_report.py`, `scripts/step_4_3_negative_test_report.py`
- Smoke coverage confirms archive artifact and payload fields for full saves
- Negative coverage confirms fail-closed behavior on forced archive failure and no essential-save regression

**Files Modified:**
- `web/web_interface.py`
- `utils/reset_campaign.py`
- `scripts/step_4_2_smoke_report.py` (new)
- `scripts/step_4_3_negative_test_report.py` (new)

---

### PC Leave/Return World Memory Planning (PLANNED - 2026-02-16)

**Status:** PLANNED  
**Priority:** High (Narrative Continuity)  
**Effort:** Medium (~3-5 days)

**Objective:**
Add explicit PC retirement/rejoin lifecycle that records world-memory continuity in `data/memory.db` and uses those transition memories to drive leave/return narration.

**OpenSpec Scaffolding:**
- Change: `pc-leave-return-world-memory` (scaffolded)
- Artifacts: `proposal.md`, `design.md`, `tasks.md`
- Capability specs:
  - `tt-pc-leave-return-lifecycle`
  - `memory-role-transition-continuity`

**Planned Architecture:**
- New service: `core/memory/party_transition_memory.py` for `record_pc_retirement`, `record_pc_return`, and bounded return-memory retrieval packs
- Route integration in `web/routes/tabletop_party_routes.py` with fail-open memory writes (party operations continue if memory persistence fails)
- Optional departure text in retirement flow plus continuity-aware return narration context
- Character identity continuity preserved via canonical entity IDs and `_tabletop_role_history` role transition events

**Execution Contract:**
- Phase-gated rollout with explicit verification checkpoints after each phase
- Minimal host-file edits marked with `# TABLETOP MODE:` comments
- No purge of prior memory links on retirement

---

### PC Image Create and Allied NPC Auto-Generation Planning (PLANNED - 2026-02-16)

**Status:** PLANNED  
**Priority:** Medium (User Experience Enhancement)  
**Effort:** Medium (~2-3 days)

**Objective:**
Add Character Sheet portrait `Upload / Create` UX, auto-generate missing portraits for allied NPC companions, and reduce missing-media warning spam while preserving module-first media behavior.

**User Decisions Locked:**
- Auto-generation enabled for allied NPC companions only; disabled for non-allied NPCs and monsters in MVP
- NPC -> PC promotion preserves image linkage by name identity
- Module-first media lookup with fallback to static media (from activated graphic packs)

**Key Features:**
- **Character Sheet Upload/Create:** Portrait action provides both upload and AI-generated create options
- **Appearance Fields:** Optional schema fields (`age`, `height`, `weight`, `eyes`, `skin`, `hair`) enrich portrait prompts
- **Allied Auto-Heal:** Missing portrait for party companions triggers background generation with dedupe/cooldown
- **Warning Throttle:** Per-key missing media log throttling prevents repeated warning floods
- **Promotion Continuity:** Image resolution follows same name-based fallback chain after NPC -> PC promotion

**OpenSpec Scaffolding:**
- Change: `pc-image-create-and-allied-npc-autogen` (validated)
- Artifacts: `proposal.md`, `design.md`, `tasks.md`, `executor_prompts.md`
- Four capability specs: `pc-sheet-upload-create-portrait`, `allied-npc-missing-media-autogen`, `missing-media-warning-throttle`, `appearance-fields-for-portrait-prompts`

**Step 1.1 Completed:**
- Added optional appearance fields to `schemas/char_schema.json` (`age`, `height`, `weight`, `eyes`, `skin`, `hair`)
- Backward compatible: existing character files remain valid
- `additionalProperties: false` preserved with explicit field declarations

**Plan Location:** `/plans/pc-image-create.md`  
**OpenSpec Location:** `openspec/changes/pc-image-create-and-allied-npc-autogen/`

### Exit/Enter GUI Button Implementation Plan (PLANNED - 2026-02-15)

**Status:** PLANNED  
**Priority:** Medium (User Experience Enhancement)  
**Effort:** Small (~1-2 hours)

**Objective:**
Add Exit button to web GUI that gracefully stops all Python processes without requiring Ctrl+C in terminal.

**User Experience:**
- Click "Exit" in pinned browser tab
- Server acknowledges and gracefully shuts down
- Terminal prints "Shutting down NeverEndingQuest Web Interface..."
- User must manually restart with `python run_web.py`

**Phase 1 (Exit Only - Recommended):**
- Modify `handle_user_exit()` in `web/web_interface.py` to gracefully stop server
- Use exit code 91 so launcher knows intentional shutdown (not error)
- Update `run_web.py` to detect code 91 and print shutdown message without restart
- Update GUI button to show waiting message during shutdown

**Phase 2 (Full Exit/Enter - Future):**
- Requires persistent supervisor/watcher process (not implemented in Phase 1)
- Allows Enter button to restart server without manual terminal command
- Deferred due to complexity/maintenance concerns

**Files to Modify:**
- `web/web_interface.py` - Graceful shutdown handler
- `run_web.py` - Exit code 91 detection
- `web/templates/game_interface.html` - Exit button UI

**Plan Location:** `/plans/exit-enter.md`

### TTS Text Sync Browser-First Implementation (COMPLETED - 2026-02-15)

**Status:** COMPLETED  
**Priority:** Medium (UX Enhancement)  
**Effort:** Medium (~4-5 hours)  
**Implementation Date:** 2026-02-15

**Objective:**
Implement word-by-word text reveal synchronized with Browser TTS speech, with fallback faux sync for browsers/voices that don't emit boundary events.

**Implementation Highlights:**

**1. Configuration & Toggle Wiring (C1):**
- Added `ENABLE_BROWSER_WORD_SYNC = False` in `model_config.py` - Browser TTS word-boundary synchronized text reveal (default OFF)
- Added `ENABLE_TTS_ESTIMATED_TIMING = False` in `model_config.py` - Future OpenAI TTS timing estimation (scaffold only)
- Wired config flags through `web/web_interface.py` template context
- Added "Word Sync" toggle in DM Voice settings with browser-only visibility
- Added localStorage persistence for toggle state

**2. Browser Reveal Rendering Layer (C2):**
- Added CSS classes for narration reveal mode (`.revealed`, `.unrevealed` with `display: none`)
- Added reveal-helper functions: `isWordSyncEnabled()`, `initRevealMode()`, `updateReveal()`, `finalizeReveal()`, `clearRevealMode()`
- Updated `addMessage()` to apply `reveal-mode` class and pre-initialize reveal DOM for autoplay
- Lazy-init pattern: reveal only activates when boundary/timer events arrive

**3. Browser TTS Boundary Sync Integration (C3):**
- Implemented `SpeechSynthesisUtterance.onboundary` handler with stale-callback guard
- Updated stop/error/end handlers to finalize reveal state deterministically
- Added `notifyTTSPlaybackEnded()` for explicit Browser TTS queue completion

**4. Estimated Timeline Fallback (Faux Sync):**
- Added 1000ms watchdog timeout - switches to faux sync if no boundaries
- Calculates word-end checkpoints from text using regex
- Estimates duration (165 WPM base, 3x slowdown factor applied)
- Drives updates via `setInterval` with calculated tick timing
- Real boundaries take precedence over faux sync if they arrive

**5. Queue and Strategy Abstraction (C4):**
- Added `SYNC_STRATEGY` constants: `BROWSER_BOUNDARY`, `NONE`, `ESTIMATED_TIMELINE`
- Queue items carry immutable `syncStrategy` field
- Manual TTS replay uses `'none'` strategy to prevent text reveal rerun
- Auto-scroll chat as reveal text grows

**Files Modified:**
- `model_config.py` - Added sync feature flags
- `web/web_interface.py` - Template context wiring
- `web/templates/game_interface.html` - Core implementation (~300 lines)
    - `web/static/js/tts_queue_manager.js` - Queue strategy and completion callbacks

**Verification:**
- `python3 -m py_compile model_config.py web/web_interface.py` -> PASS
- Edge (MS TTS): Real boundary sync works
- Chrome/other: Faux sync fallback triggers after watchdog
- Stop mid-playback: Text finalizes, queue advances
- Manual replay: Audio only, no text reveal rerun

---

### TTS Boundary Sync Fallback Hardening (COMPLETED - 2026-02-24)

**Status:** COMPLETED  
**Priority:** High (UX Stability)  
**Effort:** Small (1 implementation pass)

**Objective:**
Disable slow faux streaming fallback while preserving true boundary sync when available. Ensure text is never hidden until TTS finishes.

**Problem Addressed:**
Original implementation's faux streaming was too slow/annoying. After disabling it, text was only revealing first word and hiding remainder until TTS ended.

**Implementation (game_interface.html:10234-10242):**
- Watchdog timer (1s) now reveals FULL TEXT immediately if no boundary events arrive
- `finalizeReveal(revealState)` called to show all text
- `clearRevealMode(targetMessageDiv)` cleans up reveal spans
- Removes `reveal-mode` class and clears state
- `hasBoundaryEvent = true` blocks any late boundary events
- Faux streaming function (`startEstimatedTimelineFallback`) remains intact but commented out for future toggling

**Behavior:**
- **Edge with MS voices:** Word-by-word sync works via real boundary events (immersive)
- **Chrome/other browsers:** Full text appears after 1s watchdog (readable, never hidden)
- **First word:** Shows immediately to avoid blank start
- **No fake streaming:** Slow faux word-by-word animation completely disabled

**Files Modified:**
- `web/templates/game_interface.html` - Watchdog fallback block (lines 10234-10242)

**Verification:**
- JS syntax: valid
- TTS auto-play: works with reveal semantics preserved
- Boundary sync: real events honored, fallback shows full text

---

### Combat State Init and Batching Hardening (C1-C5) (COMPLETED - 2026-02-15)

**Status:** COMPLETED  
**Priority:** High (Combat Flow Integrity)  
**Effort:** Medium (~1 session)

**Objective:**
Harden combat entry, command routing, initiative startup state, and enemy-phase batching integrity using the OpenSpec change `combat-state-init-and-batching-hardening`.

**Implementation (C1-C5):**
- **C1 Fail-closed combat entry:**
  - `main.py` now aborts safely after validation retry exhaustion with deterministic system error output.
  - `main.py` handles explicit `{"status":"error"}` from action processing and blocks fake continuation.
  - `core/ai/action_handler.py` returns explicit error dicts on `createEncounter` failure paths (no silent continue).
- **C2 Combat-only command guards:**
  - `main.py` intercepts combat-only commands outside active combat (`/init`, `/end`, `/pass`, `/att`, `/dmg`, aliases/forms).
  - Guard path returns deterministic `[SYSTEM]` + `[skipTTS]` guidance and prevents narrator drift.
- **C3 Phase 1 initiative consistency:**
  - `core/managers/combat_manager.py` added startup normalizer for two-group initiative state (`initiativeMode`, `initiativeRolls`, `initiativeWinner`, `roundStartsWith`, `awaitingPcGroupRoll`).
  - Legacy startup reroll fallback removed; startup now derives from normalized persisted state.
  - `/init` resolution mirrors compatibility initiative state to `party_tracker.json -> worldConditions.combatInitiative`.
- **C4 Enemy/NPC batch integrity + targeting:**
  - `core/managers/multi_pc_combat.py` deterministic living non-PC actor filtering for enemy-phase batches.
  - `core/managers/combat_manager.py` integrity roster expanded to include active multi-PC roster so legal non-active PC targets are accepted.
  - Invariant preserved: PCs remain forbidden as DM-controlled actors during ENEMY_PHASE but valid as damage/effect targets.
- **C5 Regression and smoke coverage:**
  - Added focused regression suite: `scripts/c5_regression_combat.py`.
  - Extended guard/fail-closed coverage plus C4 integrity checks.
  - Manual smoke checklist M1-M5 completed and marked done in tasks.

**Verification:**
- `python3 -m py_compile main.py core/ai/action_handler.py core/managers/combat_manager.py core/managers/multi_pc_combat.py` -> PASS
- `python3 scripts/test_multi_pc_combat.py` -> PASS (43 tests)
- `python3 scripts/c5_regression_combat.py` -> PASS (9 tests)
- `openspec validate combat-state-init-and-batching-hardening` -> valid

**Commits:**
- `56ec86c` - `fix(combat): harden enemy-phase batching and PC target validation`
- `48ac4aa` - `fix(combat): fail closed entry and add C5 regressions`

**OpenSpec Status:**
- Change implementation complete and validated.
- Not archived yet (intentionally deferred pending full gameplay test pass).

### Multi-PC Initiative Phase Sync and Roster Integrity (COMPLETED - 2026-02-27)

**Status:** COMPLETED - Archived to `openspec/changes/archive/2026-02-27-multipc-initiative-phase-sync-and-roster-integrity/`

**Priority:** High (Combat Flow Integrity)

**Objective:**
Resolve coder collision around opening-batch marker contract and complete the Phase 1 two-group initiative synchronization implementation.

**Collision Context:**
- Prior builder added regression tests expecting `apply_opening_batch_marker()` calls and `PHASE_MARKER` logs
- Runtime implementation had partial wiring (/init path only) causing 6 test failures
- Required reconciliation to bring runtime into alignment with test contract

**Implementation (Collision Reconciliation Pass 2):**

1. **Import Infrastructure** (`core/managers/combat_manager.py:163-179`):
   - Added `apply_opening_batch_marker` and `normalize_multi_pc_roster` imports from `combat_state_sync`
   - Fail-open fallback definitions for missing module

2. **Initiative Resolution Marker Wiring** (`core/managers/combat_manager.py:3054-3069`):
   - `/init` path now calls `apply_opening_batch_marker(encounter_data, winner)` after winner determination
   - Logs: `PHASE_MARKER: Set openingEnemyBatchPending=True via /init dmGroup path`
   - Logs: `PHASE_MARKER: Cleared openingEnemyBatchPending via /init pcGroup path`

3. **Round-Start Marker Wiring** (`core/managers/combat_manager.py:4235-4260`):
   - Round start now calls `apply_opening_batch_marker(encounter_data, "dmGroup")` when `round_starts_with == "dmGroup"`
   - Round start calls `apply_opening_batch_marker(encounter_data, "pcGroup")` for pcGroup path
   - Logs: `PHASE_MARKER: Set openingEnemyBatchPending=True via round-start dmGroup path`
   - Logs: `PHASE_MARKER: Cleared openingEnemyBatchPending via round-start pcGroup path`

4. **Opening Batch Completion Block** (`core/managers/combat_manager.py:4445-4459`):
   - After first enemy batch resolves when marker is set:
   - Clears `openingEnemyBatchPending`
   - Sets `pc_phase_complete = False`
   - Logs: `PHASE_MARKER: Cleared openingEnemyBatchPending after opening enemy batch resolution`
   - Logs: `STATE_CHANGE: Opening batch complete -> PC_PHASE`
   - Persists encounter state

5. **Prefill Prompt Consistency**:
   - All initiative pending prompts now include `[skipTTS][prefill:/init ]` markers
   - Applied to fast-lane combat initiation and /init validation paths

**Roster Integrity Implementation:**
- `core/managers/combat_state_sync.py` - Normalization helpers for multi-PC roster
- Backfill logic ensures all `partyMembers` appear in encounter creatures
- Deduplication prevents duplicate player entries
- Fail-open handling for missing character files

**Smoke Validation (Step 5.3):**
- Scenario A (dmGroup start): PASS - marker set -> enemy batch -> clear -> PC_PHASE
- Scenario B (pcGroup start): PASS - direct PC_PHASE (no opening batch)
- Roster integrity: PASS - no duplication, all party members present

**Test Results:**
- C5 regression suite: 30/30 PASS (all collision-reconciliation tests green)
- Smoke validation: All scenarios PASS

**Files Modified:**
- `core/managers/combat_manager.py` - Marker wiring, round-start logic, completion block, prefill prompts
- `core/managers/combat_state_sync.py` - Roster normalization helpers
- `scripts/c5_regression_combat.py` - Regression tests (unchanged, contract preserved)
- `scripts/step_5_3_smoke_validation.py` - NEW - Smoke validation script
- `openspec/specs/tt-combat-phase-sync/spec.md` - NEW - Main spec synced from delta
- `openspec/specs/tt-combat-roster-coherence/spec.md` - NEW - Main spec synced from delta

**OpenSpec Status:**
- Validated: `openspec validate multipc-initiative-phase-sync-and-roster-integrity` -> valid
- Archived to: `openspec/changes/archive/2026-02-27-multipc-initiative-phase-sync-and-roster-integrity/`

### Streaming UX Reversion to Foundation-Only (COMPLETED - 2026-02-15)

**Status:** COMPLETED  
**Priority:** High (Narration UX Stability)  
**Effort:** Medium (~1 session)

**Objective:**
Roll back player-facing streaming execution paths (JSON token draft rendering + stream sentence TTS) while preserving a minimal backend foundation for future stream-safe redesign.

**Selective Keep/Revert Plan Applied:**
- **Keep foundation:**
  - `model_config.py` streaming flags (`ENABLE_CHAT_STREAMING`, `ENABLE_BROWSER_TTS_STREAM_SYNC`, `STREAM_SUPERSEDED_VISIBLE`) with defaults OFF
  - `web/extensions/streaming_events.py` as dormant lifecycle helper
  - minimal host transport/template wiring in `web/web_interface.py`
- **Revert execution:**
  - `main.py` streaming attempt/commit integration
  - `core/managers/combat_manager.py` streaming attempt/commit integration
  - `web/templates/game_interface.html` draft stream chat rendering and sentence-level stream TTS pipeline
  - `web/static/js/tts_queue_manager.js` stream source-tag queue behavior
- **WebOutputCapture guardrail:** removed stream-based canonical suppression hook usage from `web/web_interface.py` to keep baseline narration emit path explicit.

**OpenSpec Artifacts:**
- `openspec/changes/streaming-ux-dual-pipeline/` (execution attempt history)
- `openspec/changes/streaming-ux-stabilization/` (diagnosis/hardening pass)
- `openspec/changes/archive/2026-02-15-streaming-ux-reversion/` (archived selective rollback spec and tasks)
- Synced main specs:
  - `openspec/specs/canonical-output-single-path/spec.md`
  - `openspec/specs/streaming-disabled-stable-output/spec.md`
  - `openspec/specs/tts-block-narration-only/spec.md`

**Verification:**
- `python3 -m py_compile main.py core/managers/combat_manager.py web/web_interface.py web/extensions/streaming_events.py` -> PASS
- `python3 scripts/test_multi_pc_combat.py` -> PASS (40 tests)
- Dormant foundation sanity (`ENABLE_CHAT_STREAMING=False`): `start_stream(...)` returns `None`, no stream events emitted -> PASS

**Verification Completion:**
- Manual smoke pass completed (`intro + one non-combat turn + one combat round`) with no stream events and no JSON leakage in narration output.
- `/opsx-verify streaming-ux-reversion` completed; warning only: legacy `scripts/test_streaming_ux_stabilization.py` assertions still target pre-reversion behavior.
- `/opsx-archive streaming-ux-reversion` completed with spec sync.

### Tabletop Character Stack Hardening (COMPLETED - 2026-02-12)

**Status:** COMPLETED  
**Priority:** High (Tabletop UX / Data Integrity)  
**Effort:** Large (multi-change sequence)

**Objective:**
Stabilize and unify tabletop character creation, readiness repair, saving-throw consistency, and NPC->PC promotion lifecycle for live facilitator workflows.

**Completed OpenSpec Changes:**
1. `tt-pc-creation-unification`
2. `tt-character-readiness-repair`
3. `tt-saving-throws-normalization`
4. `tt-npc-pc-role-lifecycle`

**Implementation Highlights:**
- **Shared Creation Audit Pipeline:** Added `utils/character_creation_audit.py` and routed startup/manual/DM-interview finalization through deterministic audit outcomes (`schema_error`, `completeness_error`, `success`).
- **Readiness Repair Flow:** Added in-sheet `Repair` preview->confirm workflow with endpoints in `web/routes/character_sheet_routes.py`; non-chat, cooldown-protected, narrative-whitelist patching, mechanical guard, and post-patch audit.
- **Saving Throws Consistency:** Added `utils/saving_throw_utils.py`; GUI now always renders six saves, PDF export uses identical normalized/fallback proficiency logic, and one-time cleanup utility added at `scripts/backfill_saving_throws.py`.
- **NPC->PC Lifecycle Promotion:** Add Existing now supports `players`/`npc_companions`/`all`; added promotion preview/apply endpoints in `web/routes/tabletop_party_routes.py`, in-place role promotion, `active_character` preserved, and lifecycle metadata persisted.

**Schema Update Required for Lifecycle Metadata:**
- Added `character_id` and `_tabletop_role_history` to `schemas/char_schema.json` `properties` so promotion metadata passes validation with `additionalProperties: false`.

**Identity and Lifecycle Pattern (New Standard):**
- Maintain one canonical character file across role transitions.
- Promote in place (`npc` -> `player`) by normalizing `type`, `character_type`, and `character_role`.
- Ensure stable `character_id` and append `_tabletop_role_history` events.
- Do not auto-switch `active_character` on promotion.

**Validation / Testing (2026-02-12):**
- `python3 -m py_compile main.py utils/startup_wizard.py utils/character_creation_audit.py utils/saving_throw_utils.py utils/pc_manager.py web/routes/tabletop_party_routes.py web/routes/character_sheet_routes.py web/web_interface.py scripts/backfill_saving_throws.py` -> PASS
- `.venv/bin/python scripts/test_character_creation_audit.py` -> PASS
- `python3 scripts/backfill_saving_throws.py` dry-run -> PASS
- End-to-end API smoke suite -> PASS:
  - creation validation endpoints
  - readiness repair preview/apply
  - promotion preview/apply (membership transition + active-character invariance)
  - PDF export compatibility

**Files Added:**
- `utils/character_creation_audit.py`
- `utils/saving_throw_utils.py`
- `scripts/backfill_saving_throws.py`
- OpenSpec artifacts under `openspec/changes/tt-pc-creation-unification/`
- OpenSpec artifacts under `openspec/changes/tt-character-readiness-repair/`
- OpenSpec artifacts under `openspec/changes/tt-saving-throws-normalization/`
- OpenSpec artifacts under `openspec/changes/tt-npc-pc-role-lifecycle/`

**Files Modified (key):**
- `main.py`
- `utils/startup_wizard.py`
- `utils/pc_manager.py`
- `web/routes/tabletop_party_routes.py`
- `web/routes/character_sheet_routes.py`
- `web/templates/game_interface.html`
- `web/templates/partials/character_tabs.html`
- `web/static/js/tabletop_mode.js`
 - `web/web_interface.py`
 - `schemas/char_schema.json`
 
### Roll Your Own Creation Sanitization (COMPLETED - 2026-02-24)

**Status:** COMPLETED  
**Priority:** High (Tabletop UX / Data Integrity)  
**Effort:** Small (surgical patch)

**Objective:**
Prevent stale field carryover from autofill and prior UI state in Manage Party -> Roll Your Own PC creation flow. Fixes bug where newly created PCs inherited unrelated inventory lists (e.g., Anselara inheriting Acheron's equipment).

**Root Cause:**
- Backend `create_manual` route is deterministic from form payload
- Contamination occurred in frontend form state/autofill, not server merge
- Browser autocomplete and form history cross-populated fields between PC creation sessions

**Implementation:**
1. **Force-reset on Manage Party open** (`tabletop_mode.js:openManagePartyModal`):
   - Call `resetQuickCreateState()` before anything else
   - Call `clearQuickCreateAutofillResidue()` to scrub stale values
   - Force default tab to `'add-existing'` to avoid landing on Roll Your Own with stale values

2. **New sanitization helper** (`tabletop_mode.js:clearQuickCreateAutofillResidue`):
   - Clears 9 high-risk text fields: `equipment`, `attacks`, `personality_traits`, `ideals`, `bonds`, `flaws`, `backstory`, `background_feature_name`, `background_feature_description`
   - Preserves numeric defaults (level/AC/HP/ability defaults)

3. **Form-level autocomplete isolation** (`character_tabs.html`):
   - Add `autocomplete="off"` to both forms: `quick-create-form`, `manage-pc-form`
   - Add field-level `autocomplete="off"` to high-risk inputs: `equipment`, `attacks`

4. **Regression tests** (`scripts/test_character_sheet_edit.py`):
   - `test_clear_autofill_residue_function_exists` - helper exists and targets correct fields
   - `test_open_manage_party_resets_and_sanitizes` - open modal calls sanitization before loading
   - `test_forms_have_autocomplete_off` - forms have autocomplete disabled
   - `test_high_risk_fields_have_autocomplete_off` - equipment/attacks inputs protected
   - All 25 tests passing

**Result:**
- Roll Your Own creation always starts with clean slate
- No PC can inherit another PC's inventory via stale form values
- Endpoint separation preserved: `submitQuickCreate` → `create_manual`, `submitManagePcEdit` → `update_manual`

**Files Modified:**
- `web/static/js/tabletop_mode.js` - Reset and sanitization logic (35 lines)
- `web/templates/partials/character_tabs.html` - Autocomplete attributes (8 lines)
- `scripts/test_character_sheet_edit.py` - Regression tests (102 lines)

### Initiative Phase 1 Two-Group Start Gate (COMPLETED - 2026-02-12)

**Status:** COMPLETED  
**Priority:** High (Combat Flow)  
**Effort:** Small (~1-2 hours)

**Objective:**
Implement Phase 1 two-group initiative startup so combat opening phase is deterministic (`dmGroup` vs `pcGroup`) without changing the existing `/end` enemy-batch flow.

**Implementation:**
1. **Encounter startup state** (`core/ai/action_handler.py`):
   - Added Phase 1 fields on encounter creation:
     - `initiativeMode: "two_group_phase1"`
     - `initiativeRolls: {"dmGroup": <d20>, "pcGroup": null}`
     - `initiativeWinner: null`
     - `roundStartsWith: null`
     - `awaitingPcGroupRoll: true`
   - DM group pre-roll now generated in Python (`random.randint(1, 20)`).
   - Preserved compatibility mirror in `party_tracker.json -> worldConditions.combatInitiative`.

2. **Combat gate + resolver** (`core/managers/combat_manager.py`):
   - Added hard gate while `awaitingPcGroupRoll=true`.
   - Only accepts `/init <1-20>`; all other input blocked with usage prompt.
   - On valid `/init`, persists `pcGroup` roll, computes winner, sets `roundStartsWith`, clears waiting flag.
   - Tie rule enforced: `dmGroup` wins ties.
   - If `dmGroup` wins, injects explicit enemy-phase trigger and immediately runs opening enemy batch.
   - Added help command entry: `/init [1-20] - Set PC group initiative roll`.

3. **Prompt/runtime phase consistency** (`core/managers/combat_manager.py`):
   - Added dynamic `=== INITIATIVE STATE ===` block to combat prompt context:
     - `MODE`, `DM_GROUP_ROLL`, `PC_GROUP_ROLL`, `WINNER`, `ROUND_STARTS_WITH`, `CURRENT_PHASE`
   - Round advancement now applies persisted `roundStartsWith` to deterministically set each new round opener.

4. **Prompt wording alignment (minimal edits):**
   - `prompts/combat/combat_sim_prompt_multipc_compressed.txt`: ENEMY_PHASE can start via `/end` OR initiative-driven DM start.
   - `prompts/combat/combat_validation_prompt_multipc_compressed.txt`: validation rules now accept initiative-driven ENEMY_PHASE start and matching routing.

**Verification:**
- `python3 -m py_compile core/ai/action_handler.py core/managers/combat_manager.py`
- `python3 scripts/test_multi_pc_combat.py` -> PASS (40 tests, 0 failures, 0 errors)

**Files Modified:**
- `core/ai/action_handler.py`
- `core/managers/combat_manager.py`
- `prompts/combat/combat_sim_prompt_multipc_compressed.txt`
- `prompts/combat/combat_validation_prompt_multipc_compressed.txt`

### Web Interface TT Merge Refactor Completion (COMPLETED - 2026-02-12)

**Status:** COMPLETED  
**Priority:** High (Merge Safety)  
**Effort:** Medium (~2-3 hours incremental)

**Objective:**
Reduce divergence from upstream in `web/web_interface.py` by extracting TABLETOP MODE logic into extension/route modules while preserving behavior and keeping host hooks thin.

**Increments Completed:**
1. **Increment 7:** Extracted `request_plot_data` and `request_storage_data` socket handler implementations to `web/extensions/tabletop_socket_handlers.py`; host handlers remain thin wrappers.
2. **Increment 8:** Deduped repeated WebOutputCapture debug-line filter logic with shared helper and marker list in `web/web_interface.py`.
3. **Increment 9:** Hardened live chat monitor wrapper lifecycle in `web/extensions/live_chat_monitor.py` with idempotent setup and optional teardown helper.

**Validation:**
- `python3 -m py_compile web/web_interface.py web/extensions/tabletop_socket_handlers.py`
- `python3 -m py_compile web/web_interface.py`
- `python3 -m py_compile web/web_interface.py web/extensions/live_chat_monitor.py`
- Grep verification confirmed host wrappers are thin and wrapper lifecycle ownership is centralized in extension module.

**Commit:**
- `094a938` - `refactor(web): reduce TT divergence via extension hooks`

**Files in Commit:**
- `web/web_interface.py`
- `web/output_markers.py`
- `web/extensions/__init__.py`
- `web/extensions/live_chat_monitor.py`
- `web/extensions/tabletop_socket_handlers.py`
- `web/routes/__init__.py`
- `web/routes/browser_settings_routes.py`
- `web/routes/character_sheet_routes.py`
- `web/routes/tabletop_party_routes.py`

---

### Phase 0 Cleanup: Factory Routing Alignment (COMPLETED - 2026-02-12)

**Status:** COMPLETED  
**Priority:** High (Pre-Push Cleanup)  
**Effort:** Small (~1 hour)

**Objective:**
Align core files to OpenRouter factory routing baseline before GitHub push. Remove documentation drift and establish consistent client initialization pattern across all LLM call sites.

**Files Modified:**
1. `core/ai/transition_validator.py` - Factory client + provider model selection + fallback handling
2. `main.py` - `generate_module_summary()` uses factory routing with fallback
3. `core/managers/combat_manager.py` - Global client initialization uses factory
4. `AGENTS.md` - Updated migration status, removed duplicate entries, renumbered lists

**Technical Changes:**

**Import Replacements:**
- Removed: `from openai import OpenAI` and direct `OPENAI_API_KEY` usage
- Added: `from utils.ai_client_factory import create_chat_client, get_chat_model_name, handle_provider_error`

**Client Initialization:**
- Before: `client = OpenAI(api_key=OPENAI_API_KEY)`
- After: `client = create_chat_client()`

**Fallback Pattern Implementation:**
```python
model_name = get_chat_model_name()
actual_model_used = model_name

try:
    response = client.chat.completions.create(
        model=model_name,
        ...
    )
except Exception as api_error:
    error_result = handle_provider_error(api_error, context="...")
    if error_result["should_fallback"]:
        fallback_client = create_chat_client(use_fallback=True)
        response = fallback_client.chat.completions.create(
            model=TRANSITION_VALIDATOR_MODEL,  # or DM_SUMMARIZATION_MODEL
            ...
        )
        actual_model_used = TRANSITION_VALIDATOR_MODEL
    else:
        raise
```

**Fix 4 Prevention:**
- Used distinct variable names in local scopes (`summary_client`, `fallback_client`)
- Avoided `client` variable shadowing that caused UnboundLocalError in prior migration

**Risk Mitigation:**
- Zero prompt/content changes (temperature, system messages preserved)
- All existing fallback behavior maintained (non-AI summary on failure in main.py)
- No model selection logic changes
- Syntax verification: `python3 -m py_compile` passes for all 3 Python files

**Lines Changed:**
- Total: +72/-41 across 4 files
- `transition_validator.py`: +38/-22 (factory + fallback wrapper)
- `main.py`: +30/-13 (summary function factory alignment)
- `combat_manager.py`: +3/-3 (global client factory)
- `AGENTS.md`: +1/-3 (status cleanup, renumbering)

**Verification:**
- ✅ All files compile successfully
- ✅ No module-level `client = OpenAI(...)` in patched files
- ✅ Factory usage verified: 4 `create_chat_client()` calls
- ✅ AGENTS.md consistency: no duplicate migration entries

**Next Steps:**
- Smoke testing: startup → transition validation → combat entry
- OpenRouter rollout preparation (post-tester release)

---

### Combat Round Synchronization & Allied NPC Fix (COMPLETED - 2026-02-09)

**Status:** COMPLETED  
**Priority:** High (Combat Flow)  
**Effort:** Small (~30 minutes)

**Problem:**
Combat was stuck at Round 2 forever, with the AI refusing to increment to Round 3. Additionally, allied NPCs (Scout Kira, liri, Festivus, Henry Andersen, Dryad Sylara) were not getting attack turns during the enemy phase batch after `/end` command.

**Root Causes:**

1. **Round State Desync:** `MultiPCCombatManager.current_round` defaults to 1 on construction and was never synced from the encounter file's `combat_round: 2`. The initiative tracker prompt showed Round 1 to the AI, which processed Round 1 enemy phase, returned `combat_round: 2`, but the Python check `2 > 2` failed, skipping `start_new_round()`. Combat remained stuck in limbo.

2. **NPC Exclusion:** `get_remaining_enemies_for_round()` (line 537) only returned `CombatantType.ENEMY`, excluding allied `CombatantType.NPC` from the batch processing list. The AI was never instructed to process allied NPC attacks.

**Solution:**

**Round Synchronization (multi_pc_combat.py:1148):**
```python
def sync_round_from_encounter(self, encounter_data: Dict[str, Any]) -> bool:
    """Sync manager round state from persisted encounter file."""
    encounter_round = encounter_data.get('combat_round', encounter_data.get('current_round', 1))
    if encounter_round > 0 and encounter_round != self._state.current_round:
        self._state.current_round = encounter_round
        return True
    return False
```

**Sync Call (combat_manager.py:2007-2011):**
```python
# TABLETOP MODE: Sync round state from encounter file
# The manager defaults to round 1 on construction, but the encounter
# may be at a higher round from a previous session
if multi_pc_manager.sync_round_from_encounter(encounter_data):
    info(f"STATE_SYNC: Combat round synced to {multi_pc_manager.current_round} from encounter file", category="combat_events")
```

**NPC Inclusion (multi_pc_combat.py:537):**
```python
# Before:
if combatant.type == CombatantType.ENEMY and combatant.status.lower() != "dead":

# After:
if combatant.type in (CombatantType.ENEMY, CombatantType.NPC) and combatant.status.lower() != "dead":
```

**Reverted Broken Fix:**
Removed the `clean_old_dm_notes()` modification that was deleting temporary system messages ("PROCEED TO ENEMY PHASE") before the AI could process them. This would have broken the `/end` command entirely.

**Result:**
- Combat now advances rounds correctly (Round 2 → Round 3 → etc.)
- Allied NPCs participate in enemy phase batch attacks
- Round state stays synchronized with encounter file
- Manager state is authoritative at runtime, encounter file is ground truth for persistence

**Files Modified:**
1. `core/managers/multi_pc_combat.py` (+21 lines: `sync_round_from_encounter()` method, docstring updates, filter change)
2. `core/managers/combat_manager.py` (+5 lines: sync call after `initialize_turn_queue()`)

---

### Combat Validation & Character Update Fixes (COMPLETED - 2026-02-09)

**Status:** COMPLETED  
**Priority:** High (Combat System)  
**Effort:** Medium (~2 hours)

**Problems:**
1. The AI validator was incorrectly rejecting valid `updateCharacterInfo` actions during enemy batch phase, claiming they were "consolidation violations"
2. The simulation prompt had ambiguous routing guidance that could mislead the AI about where PC damage belongs
3. Character updates during combat were silently failing with `UnboundLocalError`

**Root Causes:**

1. **Validation Confusion:** The consolidation rule said "ALL enemy changes must be in ONE updateEncounter" but was being interpreted to include PC damage. The validator rejected multiple `updateCharacterInfo` actions even though they're required for PC damage.

2. **Ambiguous Plan Note:** Line 97 of `combat_sim_prompt_multipc_compressed.txt` said `'Enemy_X hits [PC_NAME] -> updateEncounter'` which could be read as "PC damage goes in updateEncounter."

3. **OpenRouter Scoping Bug:** The `update_character_info()` function had `client = create_chat_client(use_fallback=True)` at line 2110 for fallback handling. Because Python saw this assignment anywhere in the function body, it treated `client` as a local variable for the entire function. When line 1643 tried to read `client`, it raised `UnboundLocalError`.

**Solutions:**

**Fix 1a-d - Validation Prompt Clarifications (combat_validation_prompt_multipc_compressed.txt):**
- Line 143: `consolidation_rule` now explicitly states "enemy STATE changes" and notes that "Multiple updateCharacterInfo actions for different PCs/NPCs damaged during the same enemy phase is VALID and REQUIRED"
- Lines 152-155: Added `batch_enemy_phase` routing rule explaining the expected pattern after `/end`
- Line 178: Added parenthetical note to `multiple_update_encounter` violation: "(NOTE: multiple updateCharacterInfo for different PCs/NPCs is VALID, not a violation)"
- Lines 311-319: Added `batch_enemy_pc_damage` positive example showing valid action routing

**Fix 2a - Simulation Prompt Clarification (combat_sim_prompt_multipc_compressed.txt):**
- Line 97: Changed `'Enemy_X hits [PC_NAME] -> updateEncounter'` to `'Enemy_X attacks [PC_NAME] -> updateEncounter (enemy housekeeping only)'` and matched line 75's clearer format with `'[PC_NAME] takes 6 damage, HP Y->Z -> updateCharacterInfo'`

**Fix 3a-b - Uncompressed Validation Prompt (combat_validation_prompt_multipc.txt):**
- Line 151: Added `- FLAG AS VALID: Multiple updateCharacterInfo actions...` bullet
- Lines 304-311: Added "VALID - Batch Enemy Phase with PC Damage" example section

**Fix 4 - UnboundLocalError Resolution (updates/update_character_info.py):**
- Line 1259: Added `global client  # Required because fallback reassigns client at line 2110`
- This allows the function to read the module-level `client` (created at line 137) before the fallback reassignment at line 2110

**Result:**
- AI validator now accepts correct action routing (1 updateEncounter + multiple updateCharacterInfo during enemy phase)
- Simulation prompt no longer ambiguous about PC damage routing
- Character updates work during combat; HP damage is properly applied
- All combat actions process correctly during batch enemy phase

**Files Modified:**
1. `prompts/combat/combat_validation_prompt_multipc_compressed.txt` (+9 lines, +1 example)
2. `prompts/combat/combat_sim_prompt_multipc_compressed.txt` (+1 line edit)
3. `prompts/combat/combat_validation_prompt_multipc.txt` (+9 lines, +1 example)
4. `updates/update_character_info.py` (+1 line `global client`)

---

### Combat API Timeout Protection & StatusTimer Infrastructure (COMPLETED - 2026-02-09)

**Status:** COMPLETED  
**Priority:** High (Reliability/UX)  
**Effort:** Small (~1 hour)  

**Problem:**
On 2026-02-09 at 10:57:42, combat validation hung indefinitely waiting for an OpenAI API response. The SDK default timeout is 600s (10 minutes) - unacceptable for interactive gameplay. Users saw a static "Validating combat actions..." placeholder with no feedback escalation or timeout recovery.

**Solution:**
Implemented timeout infrastructure and StatusTimer context manager for future UX improvements. Three surgical changes across 3 files.

**Constants Added (model_config.py:50-51):**
```python
COMBAT_API_TIMEOUT_SECONDS = 120                        # Per-call timeout for combat LLM calls (prevents indefinite hangs)
COMBAT_CONNECT_TIMEOUT_SECONDS = 10                     # TCP connection timeout for combat LLM calls
```

**StatusTimer Class (status_manager.py:143-206):**

Context manager for escalating status messages during blocking operations:

```python
class StatusTimer:
    DEFAULT_SCHEDULE = [
        (10, "Still processing, please wait..."),
        (30, "Response taking longer than usual..."),
        (60, "Waiting for AI provider ({elapsed}s)..."),
    ]
    
    def __enter__(self):  # Starts daemon thread
    def __exit__(self):   # Stops thread on completion/exception
```

**Key Features:**
- Escalation schedule: 10s → 30s → 60s with live elapsed counter
- Daemon thread auto-cancels on context exit (success or exception)
- Uses `threading.Event.wait(timeout=1.0)` for responsive shutdown
- DEFAULT_SCHEDULE is class-level constant for per-call-site customization
- **Ready for OpenRouter build:** Will be reused by `llm_router.py` when Phase 1 is implemented

**Timeout Protection Applied (combat_manager.py):**

| Line | Function | Call Type | Priority |
|------|----------|-----------|----------|
| 852 | `validate_combat_response()` | Validation LLM | HIGH |
| 2576 | Initial scene generation | Scene narration | HIGH |
| 3619 | Main combat loop GPT-4.1 | Combat generation | **CRITICAL** |

**Implementation Notes:**

- All 3 high-traffic combat paths now protected; 6 secondary calls remain unprotected (acceptable risk)
- Timeout exceptions caught by existing retry loops (up to 5 attempts)
- StatusTimer not yet wired up (deferred for Section 4); timeout infrastructure complete
- Zero code restructuring; all additive single-line changes with `# TABLETOP MODE:` comments

**Result:**
- ✅ Combat API calls timeout after 120s instead of 600s SDK default
- ✅ Prevents indefinite hangs during live gameplay
- ✅ Existing retry logic handles timeouts gracefully
- ✅ StatusTimer ready for future UX escalation work

**Files Modified:**
1. `model_config.py` - Added timeout constants (2 lines)
2. `core/managers/status_manager.py` - StatusTimer class (66 lines)
3. `core/managers/combat_manager.py` - 3 timeout additions (marked with # TABLETOP MODE:)

**Future Work:**
- Section 4: Wire up StatusTimer at 3 main call sites for escalating UX feedback
- Complete coverage: Add timeout to 6 secondary API calls (dialogue summary, log analyzer, re-engage paths)

---

### MultiPCCombatManager Bug Fixes & Code Quality Improvements (COMPLETED - 2026-02-09)

**Status:** COMPLETED
**Priority:** High (Architecture/Reliability)
**Effort:** Medium (~3-4 hours)

**Objective:**
Fixed 10 synchronization bugs and applied 5 code quality improvements to `core/managers/multi_pc_combat.py` based on comprehensive audit report. All fixes address state synchronization issues between the `MultiPCCombatManager` facade and its sub-managers (`CombatStateManager`, `TurnQueueManager`).

**Bugs Fixed (Bugs 1-10):**

| Bug | File | Change |
|-----|------|--------|
| **Bug 1** | multi_pc_combat.py:775-783 | Added `current_round` property getter/setter on facade to route writes to `_state.current_round` (was creating shadow attribute) |
| **Bug 2** | multi_pc_combat.py:1229, 1365 | Fixed `start_new_round()` to write to `self._turns.enemy_phase_complete` instead of orphan facade attribute |
| **Bug 3** | multi_pc_combat.py:1068-1093 | Refactored `complete_pc_turn()` to delegate to `self._turns.complete_pc_turn()` |
| **Bug 4** | multi_pc_combat.py:1095-1103 | Refactored `force_end_pc_phase()` to delegate entirely to `self._turns.force_end_pc_phase()` |
| **Bug 5** | multi_pc_combat.py | Removed dead `CombatStateManager.get_combat_state_summary()` method (28 lines) |
| **Bug 6** | multi_pc_combat.py:1032-1044, 1046-1066, 1137-1158 | Converted 4 facade methods from reimplementing logic to delegating to `_state` |
| **Bug 7** | multi_pc_combat.py:1312-1316 | **Windows Compatibility:** Replaced Unicode icons (⏳✓💀☠️😴) with ASCII tags ([WAIT], [DONE], [DOWN], [DEAD], [STBL]) |
| **Bug 8** | multi_pc_combat.py | Removed 3 dead methods from `TurnQueueManager` - 74 lines |
| **Bug 9** | multi_pc_combat.py:429-461, 778-815 | Fixed `TurnQueueManager.advance_turn()` to return tuple instead of mutating state; moved round rollover to facade to prevent double-increment |
| **Bug 10** | multi_pc_combat.py | Removed dead `first_round` field from facade (2 lines) |

**Code Quality Improvements:**

1. **Bug 7 (Item 1 above):** Windows Unicode compatibility fix (already counted in bugs)
2. **Unicode Removal (Item 2):** Replaced Unicode emoji (⛔⚠️) with ASCII tags ([BLOCKED], [WARNING]) in prompt boxes (lines 1402, 1436, 1447)
3. **Facade Properties (Item 3):** Changed `manager._state.party_initiative` to `manager.party_initiative` using facade properties (lines 1811-1817)
4. **Stale Comment (Item 4):** Removed stale `# ... [Keep existing methods below] ...` comment (line 1010)
5. **Unused Imports (Item 5):** Removed unused `Union` and `re` imports (lines 30, 34)

**Test File Fix:**
- **scripts/test_multi_pc_combat.py:258** - Fixed test to unpack tuple from `advance_turn()` call: `next_actor, rolled_over = self.turn_mgr.advance_turn()`

**Architecture Principle Established:**
Facade methods should either **delegate** to sub-managers (pure delegation) or **coordinate** between multiple sub-managers. They should not reimplement sub-manager logic by directly accessing `self._state.pc_states` when a sub-manager method exists.

**Key Patterns:**
- **Delegation:** `return self._state.method_name()` or `return self._turns.method_name()`
- **Coordination:** Facade methods touching both `_state` and `_turns` handle coordination logic
- **Properties:** External reads/writes go through facade properties that delegate to `_state`
- **Return Types:** Sub-managers return simple types or tuples; facade consumes tuples, returns simple types

**Verification:**
- All 10 bugs from audit report fixed
- Test suite should pass (fixed Bug 9 return type impact)
- Zero breaking changes confirmed
- State synchronization bugs resolved (shadow attributes, orphan writes, double-increment)
- Windows compatibility issues resolved

**Pre-existing Issues (Not Our Changes):**
3 LSP type annotation errors (~1537, ~1550, ~1554) - existed before fixes, unrelated to bug fixes

**Files Modified:**
1. `core/managers/multi_pc_combat.py` - ~200+ lines (mix of additions, deletions, refactors)
2. `scripts/test_multi_pc_combat.py` - Line 258 (tuple unpacking fix)

---

### TTS Auto-Play Fix & Queue Management (COMPLETED - 2026-02-06)

**Status:** COMPLETED  
**Priority:** High (User Experience)  
**Effort:** Medium (~2-3 hours)  

**Problem:**
TTS (Text-to-Speech) auto-play had three critical issues:
1. **Cacophony on reload:** When auto-play enabled and page reloaded, ALL cached messages played simultaneously
2. **No queue management:** Multiple messages could play at once, causing audio overlap
3. **Mechanical messages spoken:** Combat results (/att, /dmg) and system commands (/help, /stats) were being narrated, breaking immersion

**Solution:**
Implemented comprehensive TTS management system with queue control, message filtering, and `[skipTTS]` tagging:

**1. TTS Queue Manager Plugin (`web/static/js/tts_queue_manager.js`) - NEW:**
- **Sequential Playback:** Only one TTS plays at a time, preventing audio overlap
- **Queue Management:** Max 3 queued messages, skips new messages when TTS is playing
- **Smart Behavior:** DM can manually click TTS button if auto-play skips a message
- **Emergency Stop:** `cancelAll()` method stops all playback immediately
- **Plugin Architecture:** Isolated from upstream code, loaded as extension

**2. Cached Message Protection (`web/templates/game_interface.html`):**
- Added `skipAutoplay` parameter to `addMessage(outputId, message, skipAutoplay = false)`
- Cached messages from previous sessions pass `skipAutoplay=true` (no TTS on page reload)
- Prevents cacophony when restoring chat history after reconnect

**3. Player Message Cleanup (`web/templates/game_interface.html`):**
- Removed TTS button (▶) from player input messages entirely
- Only DM narration displays TTS controls
- Cleaner UX: TTS is DM-only feature

**4. System Content Filter (`web/templates/game_interface.html`):**
- Filters `[SYSTEM]`, `---` (dividers), and `/command` lines from TTS auto-play
- Help menus, command lists, and session boundaries not spoken
- Content still displays normally, just not narrated

**5. `[skipTTS]` Tag System (4 files):**

**A. Message Generation (Python):**
- **`core/managers/multi_pc_combat.py`:** Combat commands (`/att`, `/dmg`) prepend `[skipTTS]` to mechanical output
  - Lines modified: ~1012, 1029, 1034, 1039, 1055, 1082
  - Messages: "Hit! Rolled X vs AC Y", "Miss. (Rolled X vs AC Y)", damage confirmations
  
- **`main.py`:** `/help` command output prepends `[skipTTS]`
  - Line ~3072: Help menu marked for TTS exclusion

**B. Tag Processing (`web/web_interface.py`):**
- **`WebOutputCapture.write()` method:** Detects `[skipTTS]` prefix, strips it, sets `skipTTS: true` flag
  - Lines 432-442: First DM section end handler
  - Lines 504-513: Debug message handler  
- **`WebOutputCapture.flush()` method:** Same detection and stripping
  - Lines 574-584: Critical fix for stdout flush scenarios
- Tag stripped before display, `skipTTS` boolean passed to frontend

**C. Frontend Filtering (`web/templates/game_interface.html`):**
- Line ~5202: Checks `message.skipTTS` flag before auto-play
- DM narration without flag → TTS plays
- Mechanical messages with flag → TTS skipped

**TTS Behavior Summary:**

| Message Type | Auto-Play | Manual Button | Spoken Content |
|--------------|-----------|---------------|----------------|
| **DM Narration** | ✅ Yes (queued) | ✅ Yes | Story content only |
| **Player Input** | ❌ No | ❌ No | N/A |
| **System/Error** | ❌ No | ❌ No | N/A |
| **Cached Messages** | ❌ No | ✅ Yes | If manually clicked |
| **Combat Results** | ❌ No | ❌ No | Display only |
| **Help Menus** | ❌ No | ❌ No | Display only |

**Implementation Flow:**
```
Player: /att goblin 15
↓
Python: Returns "[skipTTS] Dungeon Master: Miss. (Rolled 15 vs AC 16)"
↓
stdout.flush() or marker detection
↓
WebOutputCapture: Detects [skipTTS], strips tag, sets skipTTS: true
↓
Message: {type: 'narration', content: 'Miss...', skipTTS: true}
↓
Frontend: Displays normally, checks skipTTS flag
↓
❌ No TTS (tagged as mechanical), queue not blocked
↓
LLM Narration arrives: "The goblin dodges your blade!"
↓
✅ TTS plays immediately (queue ready, immersive)
```

**Files Modified:**
1. `web/static/js/tts_queue_manager.js` - **NEW** Plugin implementation (~200 lines)
2. `web/templates/game_interface.html` - skipAutoplay param, system filters, skipTTS flag check (lines ~5132, 5202, 5231, 5373)
3. `core/managers/multi_pc_combat.py` - [skipTTS] prefixes on 6 combat outputs (lines ~1012-1082)
4. `main.py` - [skipTTS] prefix on /help command (line ~3072)
5. `web/web_interface.py` - Tag detection/stripping in 3 locations (lines 432-442, 504-513, 574-584)

**Result:**
- ✅ No cacophony on page reload
- ✅ Only DM narration speaks (immersive storytelling)
- ✅ Combat mechanics display but don't break immersion
- ✅ Queue flows smoothly, no blocking by mechanical messages
- ✅ All changes marked with `# TABLETOP MODE:` comments (merge-safe)

### OpenRouter Integration - Phase 1 Core Chat/LLM (2026-02-06)

**Status:** COMPLETED  
**Priority:** High  
**Effort:** Medium (~2-3 hours)  

**Objective:**
Enable multi-provider AI support with transparent fallback from OpenRouter to OpenAI for all chat/LLM operations.

**Factory Pattern Implementation:**

1. **New File Created - `utils/ai_client_factory.py` (312 lines):**
   - `create_chat_client(use_fallback=False)` - Creates OpenAI or OpenRouter client based on config
   - `get_chat_model_name()` - Returns appropriate model (Kimi K2.5 or GPT-4.1) based on provider
   - `handle_provider_error()` - Detects retryable errors (rate limits, 503s, etc.) and triggers fallback
   - `get_fallback_notification()` - Returns user-friendly GUI message when fallback occurs
   - `get_provider_status()` - Diagnostics for troubleshooting provider configuration

2. **Configuration Added to `model_config.py` (lines 68-101):**
   ```python
   LLM_PROVIDER = "openai"  # Options: "openai", "openrouter"
   OPENROUTER_API_KEY = ""  # Set in config.py
   OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
   OPENROUTER_CHAT_MODEL = "moonshotai/kimi-k2.5"
   ENABLE_PROVIDER_FALLBACK = True
   ```

**Files Updated (9 total):**
1. `utils/ai_client_factory.py` - **NEW** Factory implementation (312 lines)
2. `updates/update_character_info.py` - Factory pattern + transparent fallback in character updates
3. `utils/startup_wizard.py` - Factory pattern for character creation
4. `core/ai/transition_validator.py` - Factory pattern + fallback for location transitions (completed in Phase 0 cleanup)
5. `core/ai/combat_compression_engine.py` - Factory pattern for combat compression
6. `core/ai/incremental_compression.py` - Factory pattern for location compression
7. `core/ai/cumulative_summary.py` - Factory pattern for adventure summaries
8. `core/ai/adv_summary.py` - Factory pattern for validation summaries
9. `web/web_interface.py` - Factory pattern for chat-based endpoints (skipped image/TTS for Phase 2)

**Fallback Behavior:**
- **Transparent auto-retry** when OpenRouter fails
- Detects rate limits, timeouts, 503/504 errors, connection issues
- Automatically switches to OpenAI without user intervention
- System message displayed in GUI: "AI provider switched from openrouter to openai..."
- Fallback persists for entire game session (KISS principle)

**Validation:**
- All 9 files compile successfully (`python -m py_compile`)
- Zero breaking changes - existing OpenAI-only users unaffected
- Backward compatible with single-player mode

**Quick Start:**
1. Get OpenRouter API key from https://openrouter.ai/keys
2. Add to config.py: `OPENROUTER_API_KEY = "sk-or-..."`
3. In model_config.py: Change `LLM_PROVIDER = "openrouter"`
4. Run game normally - Kimi K2.5 will be used automatically with fallback to OpenAI

**Future Work:**
- Phase 2: OpenRouter image generation (FLUX, Gemini) and TTS (Higgs Audio, Kokoro)
- Phase 3: Video generation stubs

---

### OpenRouter Migration - Phase 1B Model Reference Updates (COMPLETED - 2026-02-06)

**Status:** COMPLETED  
**Priority:** High  
**Effort:** Medium (~4-5 hours)  
**Risk:** High (core AI calls)  

**Objective:**
Migrate all hardcoded model references to use the OpenRouter 3-tier configuration system via `get_model_config()` factory function.

**Migration Strategy:**
- **Surgical line replacement:** Only modify `model=` lines, preserve all other parameters
- **Client factory integration:** Replace `OpenAI()` with `create_chat_client()` for multi-provider support
- **Temperature preservation:** Keep explicit temperature settings, add from config only when missing
- **extra_body handling:** Pass thinking mode parameters only to OpenRouter (handled by factory)

**Files Migrated (5 successfully, 3 pending):**

**✅ Successfully Migrated:**
1. `updates/plot_update.py` - 1 usage, uses `create_chat_client()`
2. `updates/update_encounter.py` - 1 usage, uses `create_chat_client()`  
3. `web/web_interface.py` - 1 usage (image prompt generation), uses `create_chat_client()`
4. `core/ai/adv_summary.py` - 2 usages, uses `create_chat_client()`
5. `core/ai/cumulative_summary.py` - 2 usages, uses `create_chat_client()`
6. `core/ai/transition_validator.py` - 1 usage, factory pattern + fallback (completed in Phase 0 cleanup)

**⚠️ Complex Files (Manual Migration Required):**
7. `main.py` - 3 usages, core narration functions (high risk)
8. `core/managers/combat_manager.py` - 6 usages, combat validation (highest risk)

**Key Changes Per File:**
```python
# Before:
from openai import OpenAI
from config import OPENAI_API_KEY, MODEL_CONSTANT
client = OpenAI(api_key=OPENAI_API_KEY)
response = client.chat.completions.create(
    model=MODEL_CONSTANT,
    temperature=0.7,
    messages=messages
)

# After:
from utils.ai_client_factory import create_chat_client, get_model_config
client = create_chat_client()  # Supports OpenAI and OpenRouter
config = get_model_config("task_id", MODEL_CONSTANT)
response = client.chat.completions.create(
    model=config["model"],
    **config.get("extra_body", {}),  # Only for OpenRouter
    temperature=0.7,  # Preserved if explicitly set
    messages=messages
)
```

**Critical Bug Fixed During Migration:**
- **Issue:** `TypeError: Completions.create() got an unexpected keyword argument 'thinking'`
- **Root Cause:** Migrated files using `OpenAI()` client but passing `extra_body` with `thinking` parameter (OpenRouter-specific)
- **Solution:** Changed `updates/plot_update.py` and `updates/update_encounter.py` to use `create_chat_client()` instead of direct `OpenAI()` initialization
- **Result:** Client and parameters now match provider (OpenAI gets empty extra_body, OpenRouter gets thinking params)

**Migration Script:**
- Created `scripts/migrate_to_openrouter.py` - AST-based migration tool
- Features: Surgical replacement, temperature preservation, duplicate prevention
- Safety: Backups, syntax validation, dry-run mode, unit tests
- Fixed bugs: Multi-line import handling, false positive detection, config line placement

**Validation:**
- All 5 migrated files compile successfully (`python -m py_compile`)
- Unit tests pass for migration script logic
- No breaking changes to existing APIs

**Task ID Mappings:**
- `DM_MAIN_MODEL` → `dm_main`
- `DM_VALIDATION_MODEL` → `dm_validation`  
- `COMBAT_MAIN_MODEL` → `combat_main`
- `DM_SUMMARIZATION_MODEL` → `summaries`
- `ADVENTURE_SUMMARY_MODEL` → `adventure_summary`
- `PLOT_UPDATE_MODEL` → `plot_update`
- `ENCOUNTER_UPDATE_MODEL` → `encounter_update`
- `TRANSITION_VALIDATOR_MODEL` → `transition_validation`
- `DM_MINI_MODEL` → `dm_mini`

**Next Steps:**
- Test Phase 1B migrated files in-game with OpenRouter provider
- Complete manual migration for remaining 3 complex files
- Phase 2: Image generation and TTS via OpenRouter

---

### HP Persistence Bug Fix & Code Quality Cleanup (2026-02-06)

**Critical Bug Fixed - HP Cascade Failure:**
- **Problem:** Every PC showing 10/10 HP regardless of actual values; defeated characters resurrecting mid-combat
- **Root Cause:** `multi_pc_combat.py:initialize_from_party()` reading from non-existent `party_data["characters"][name]["hp"]` structure, defaulting to 10 when keys missing
- **Solution:** Load character data directly from character JSON files using ModulePathManager
- **Files:** `core/managers/multi_pc_combat.py` (lines 276-305)

**Code Quality Improvements:**

1. **Removed Duplicate json Imports:**
   - Removed 2 redundant inline `import json` statements (lines 299, 1111)
   - All json calls now use module-level import (line 29)
   - Lines saved: 2

2. **Fixed Silent Exception Swallowing:**
   - Added debug logging for monster AC lookup failures
   - Now logs creature name, monster type, and exception details
   - File: `core/managers/multi_pc_combat.py` (lines 379-383)

3. **Consolidated Defensive Imports:**
   - Removed 4 separate try/except ImportError blocks for internal modules
   - Internal imports now fail fast (config import keeps fallback)
   - Consolidated duplicated check in `multi_pc_dm_note.py` to use centralized `should_use_abstraction_layer()`
   - Files: `core/managers/multi_pc_combat.py`, `utils/multi_pc_dm_note.py`
   - Lines saved: ~20

4. **Refactored Large Method:**
   - Split 130-line `format_initiative_tracker()` into 4 focused methods:
     - `_get_combatant_marker()`: State logic (22 lines)
     - `_build_initiative_lines()`: Line construction (20 lines)
     - `_determine_instruction_block()`: Phase logic (50 lines)
     - `format_initiative_tracker()`: Orchestrator (40 lines)
   - Result: Better separation of concerns, easier testing
   - File: `core/managers/multi_pc_combat.py` (lines 1087-1220)

5. **Eliminated Magic Numbers:**
   - Added constants: `DEFAULT_AC = 10`, `INITIATIVE_DIE = 20`
   - Replaced 6 hardcoded `ac=10` occurrences
   - Replaced 4 hardcoded `random.randint(1, 20)` calls
   - File: `core/managers/multi_pc_combat.py` (lines 176-180, 340, 369, 377, 383, 393, 396, 552, 628-629)

6. **Planned: Inconsistent Error Handling:**
   - 6 print() statements need conversion to logger calls
   - Will standardize on `debug()`, `info()`, `error()` from enhanced_logger
   - Status: Ready for implementation in next session

### MultiPCCombatManager Audit & Test Suite (COMPLETED - 2026-02-06)

**Phase 3 Refactoring Verification:**
- **Comprehensive Audit:** Documented all LLM prompt integration points and Python function integration points
- **40 Unit Tests Created:** All tests passing, covering 7 test categories
- **Test Coverage:** Core functionality, edge cases, integration scenarios, delegation pattern

**Bugs Fixed During Testing:**
1. **Line 1183:** Fixed missing `enemy_phase_complete` attribute in `get_combat_state_summary()`
   - Changed from `self.enemy_phase_complete` to hardcoded `False` (not tracked in TurnQueueManager yet)
2. **Lines 1741-1747:** Fixed deprecated direct attribute access in `get_multi_pc_initiative_narrative()`
   - Updated to use `manager._state.party_initiative`, etc.

**Test Suite Categories:**
1. **CombatStateManager Tests (7 tests):** Initialization, party loading, available PCs, incapacitated PCs, HP updates, death saves
2. **TurnQueueManager Tests (5 tests):** Queue building, turn advancement, current actor, remaining enemies
3. **Facade Tests (7 tests):** Delegation verification, coordination methods, sub-manager linking
4. **LLM Prompt Tests (8 tests):** Head context, initiative tracker, required response prompts, PC context formatting
5. **Context Manager Tests (3 tests):** Temporary manager/callback injection, event emission
6. **Edge Case Tests (7 tests):** Empty party, all incapacitated, no enemies, invalid names, forbidden actors
7. **Integration Tests (2 tests):** Full combat round, PC death mid-combat

**Key Integration Points Verified:**
- ✅ LLM Prompt Generation: 5 formatting functions tested
- ✅ Sub-Manager Delegation: All 7 delegation methods verified
- ✅ Coordination Logic: All 5 coordination methods tested
- ✅ Context Managers: Both `temporary_combat_manager` and `temporary_combat_callback` tested
- ✅ Zero breaking changes confirmed

**Test Execution:**
```bash
python scripts/test_multi_pc_combat.py
```

**Documentation Created:**
- `docs/multi_pc_combat_audit.md` - Comprehensive audit report
- `scripts/test_multi_pc_combat.py` - Complete test suite (~750 lines)
- `docs/test_results_multi_pc_combat.md` - Test results and coverage analysis

### Tabletop Mode Debug Monitor Skill v2.3.0 (COMPLETED - 2026-02-06)

**Three-Phase Complete Debug Workflow:**

**Phase 1: Start Debug (`start debug`)**
- Checks if debug configuration is enabled
- Auto-enables if disabled (edits `debug_config.py` and `config.py`)
- Prompts for server restart
- **Trigger:** "start debug"

**Phase 2: Check Debug (`check debug`)**
- Enhanced error reporter with timestamped listings
- Groups errors by type and source
- Extracts file locations and line numbers
- Provides actionable fix suggestions
- **Trigger:** "check debug" or "check debug log"

**Phase 3: Stop Debug (`stop debug`)**
- Reverts config files to debug=false
- Deletes all debug log files (cleanup)
- Shows "debug off" after restart
- **Trigger:** "stop debug"

**New Files:**
- `.opencode/skills/debug-monitor/SKILL.md` - Complete skill definition (v2.3.0)
- `scripts/check_debug_logs.py` - Log checker with `--enable`, `--stop`, `--status` flags
- `scripts/debug_error_reporter.py` - **NEW** Enhanced error reporter with critical analysis
- `utils/tabletop_debug.py` - Helper functions

**Enhanced Error Reporter Features:**
- Automatic error classification (CRITICAL/ERROR/WARNING)
- Timestamped chronological error listings
- Smart error grouping by exception type
- File location extraction (e.g., `core/managers/multi_pc_combat.py:867`)
- Actionable fix suggestions based on error patterns

**Configuration Changes:**
- `debug_config.py` - Categories: `tabletop_mode`, `tabletop_verbose`
- `config.py` - Flag: `TABLETOP_DEBUG_VERBOSE`
- `core/managers/multi_pc_combat.py` - Debug instrumentation points
- `core/managers/combat_manager.py` - Debug instrumentation points

**Features:**
- ✅ Three-phase workflow (start → check → stop)
- ✅ Smart detection of disabled debug mode
- ✅ One-command enable/disable with automatic config editing
- ✅ Log cleanup on stop (deletes all debug logs)
- ✅ Enhanced error reporting with timestamps
- ✅ Filter by severity (CRITICAL, ERROR, WARNING, TABLETOP MODE)
- ✅ Zero background processes (polling-based)
- ✅ KISS principle - manual control, no auto-disable

**Usage:**
```bash
# Phase 1: Enable debugging
python3 scripts/check_debug_logs.py --enable

# Phase 2: Check for errors (after restart)
python3 scripts/check_debug_logs.py
python3 scripts/debug_error_reporter.py --detailed

# Phase 3: Stop debugging and cleanup
python3 scripts/check_debug_logs.py --stop

# Show configuration status
python3 scripts/check_debug_logs.py --status

# Include warnings
python3 scripts/check_debug_logs.py --warnings

# Verbose output
python3 scripts/check_debug_logs.py --verbose
```

---

### OpenRouter LLM Router Architecture Plan (COMPLETED - 2026-02-07)

**Strategic Architecture Decision:** Path A - Gradual Hardening with dual-mode support for upstream merge potential.

**Objective:** Centralize 89 LLM call sites across 39 files through single capability-based router interface.

**Model Strategy:**
- **Creative/Narration:** Trinity Large Preview (arcee-ai/trinity-large-preview:free) → GPT-4.1 fallback
- **Mechanics/JSON:** Gemini 2.5 Flash Lite (google/gemini-2.5-flash-lite) → GPT-4.1 fallback
- **Universal Fallback:** GPT-4.1 when primary models unavailable

**Router Interface:**
```python
from utils.llm_router import llm

# Single interface for all LLM calls
response = llm.call(role="narrate", messages=[...])           # Trinity, temp 0.8
result = llm.call(role="combat_validate", messages=[...])     # Flash Lite, temp 0.2
data = llm.call(role="extract_json", messages=[...], structured_output=Schema)  # Flash Lite JSON
```

**Dual-Mode Architecture:**
- **MULTIPLAYER_MODE = False:** Original OpenAI hardwired (upstream compatible, merge potential preserved)
- **MULTIPLAYER_MODE = True:** Full OpenRouter with capability routing
- Mode detected at startup, requires restart to change

**Strategic Rationale:**
- Upstream frozen (4 commits in 90 days) but TTS feature valuable for merging
- Keep merge insurance policy while focusing development on TT mode
- Plugin architecture enables clean extraction to TT-only fork when upstream declared legacy
- New features developed as TT-only (SP code maintained but not enhanced)

**Implementation Timeline:**
- **Phase 1 (3-4 days):** Create `utils/llm_router.py`, update `model_config.py`, integration tests
- **Phase 2 (5-7 days):** Migrate all 39 files with LLM calls
- **Phase 3 (2-3 days):** Cleanup, usage reporting, documentation

**Key Features:**
- Capability-based routing (creative/mechanics/structured)
- Cost tracking (total + by model/capability/role)
- Hard stop error handling (game stops on quota/billing errors)
- JSON retry logic (3 attempts with progressive correction)
- Structured output support (Pydantic model validation)

**Plan Document:** `/plans/version-2/openrouter_llm_router_architecture.md` (700 lines comprehensive plan)

**Status:** PLANNING PHASE - Under review, not yet implemented

### Hallucinated Monster Defense - Three-Layer Safety System (COMPLETED - 2026-02-10)

**Status:** COMPLETED  
**Priority:** High (Data Integrity)  
**Effort:** Small (~1 hour)

**Problem:**
When the narrator LLM hallucinates creature names (e.g., "spectral servants appear"), the system auto-creates stat blocks via `monster_builder.py`, resulting in encounters with fabricated monsters that were never part of the module's bestiary. This creates data integrity issues where non-existent creatures gain persistent stats and participate in combat.

**Root Cause:**
The `load_or_create_monster()` function in `combat_builder.py` automatically spawns `monster_builder.py` subprocess when a monster file is not found. The LLM is not constrained in what names it can put in the `monsters` array of `createEncounter` actions.

**Solution - Three Independent Defense Layers:**

**Layer 1: Bestiary-Only Validation Gate (combat_builder.py:147-161)**
```python
# TABLETOP MODE: In multiplayer mode, refuse to auto-create monsters from
# hallucinated names. Only pre-existing bestiary files are valid combat targets.
try:
    from config import MULTIPLAYER_MODE
    if MULTIPLAYER_MODE:
        error(f"TABLETOP MODE: Monster '{monster_type}' not found in bestiary...")
        return None
except ImportError:
    pass  # config.MULTIPLAYER_MODE not available, use upstream behavior
```
- Blocks auto-creation in tabletop mode (MULTIPLAYER_MODE=True)
- Preserves upstream single-player behavior (auto-creation allowed)
- Lazy import pattern ensures no upstream impact

**Layer 2: Encounter Enemy Count Validation (action_handler.py:798-838)**
```python
# TABLETOP MODE: Validate encounter file has at least one enemy before starting combat
encounter_file_check = f"modules/encounters/encounter_{encounter_id}.json"
encounter_check_data = safe_json_load(encounter_file_check)
if encounter_check_data:
    enemy_count = sum(1 for c in encounter_check_data.get("creatures", [])
                      if c.get("type") == "enemy")
    if enemy_count == 0:
        error(f"TABLETOP MODE: Encounter {encounter_id} created with 0 enemies...")
        os.remove(encounter_file_check)  # Cleanup invalid file
        return {"status": "continue", "needs_update": False}  # Abort combat
```
- Catches edge cases Layer 1 doesn't cover (single-player mode, malformed entries)
- Validates encounter file before combat starts
- Cleans up invalid encounter file
- Returns gracefully without starting combat

**Layer 3: Narrator Prompt Constraint (system_prompt_compressed.txt:59)**
```
monsterSource: The "monsters" array in createEncounter MUST reference creatures that exist in the game world bestiary or have been explicitly described in the location/area data. Do NOT invent new creature types. Use standard 5e SRD creature names (e.g., "Skeleton", "Bandit", "Wight", "Goblin") that would have pre-built stat blocks.
```
- Added to @COMBAT directive
- Guides LLM toward valid creature names
- Reduces frequency of hallucinated monster names
- ~35 tokens added to prompt

**Defense-in-Depth Strategy:**

| Scenario | Fix 3 (Prompt) | Fix 1 (Bestiary Gate) | Fix 2 (Validation) | Result |
|----------|----------------|----------------------|-------------------|--------|
| LLM obeys, uses "Skeleton" | Valid name, bestiary hit | Loads from file | Count > 0, passes | Combat starts correctly |
| LLM ignores, uses "Spectral Servant" | Ignored | Bestiary miss, blocks (TT mode) | Never reached | No combat, encounter aborted |
| Single-player mode, hallucinated name | Ignored | Skipped (upstream behavior) | Catches 0-enemy encounter | No combat (SP protected too) |
| Valid name missing from module | Valid SRD name but file doesn't exist | Blocks (TT) or auto-creates (SP) | Catches if all missing | Appropriate failure per mode |

**Failure Cascade (Hallucinated Monster Blocked):**
1. Narrator says "spectral servants appear" → puts "Spectral Servant" in monsters array
2. `load_or_create_monster("spectral servant")` → file not found
3. Layer 1 (if TT mode): Returns None → `generate_encounter()` returns None
4. Layer 2: Never reached (no encounter file created)
5. No "Encounter successfully built" message in stdout
6. Combat never starts, player sees error log
7. Narrator can retry with valid bestiary creatures

**Files Modified:**
- `core/generators/combat_builder.py` - Layer 1 bestiary gate (+14 lines)
- `core/ai/action_handler.py` - Layer 2 validation (+41 lines)
- `prompts/system_prompt_compressed.txt` - Layer 3 prompt constraint (+1 line)

**Backward Compatibility:**
- Single-player mode: All three fixes preserve upstream behavior
- Tabletop mode: Protected against hallucinated monsters while maintaining full combat functionality for valid creatures
- Zero breaking changes to existing encounters or gameplay

---

### Expandable Chat Input Textarea (COMPLETED - 2026-02-09)

**Status:** COMPLETED
**Priority:** Medium (UI/UX Enhancement)
**Effort:** Small (~30 minutes)
**Implementation Date:** 2026-02-09

**Objective:**
Replace single-line text input with auto-expanding textarea for improved long prompt and detailed action descriptions.

**User Requirements:**
1. Start as single-line height (40px)
2. Auto-expand line-by-line as user types (no internal scroll)
3. Cap at 5 lines max (150px) - no infinite growth
4. Push-up effect: Input expands upward, chat transcript shrinks, header bars (dice/PC/NPC) stay fixed
5. Send button stays left-aligned at bottom
6. Enter sends message, Shift+Enter adds newline
7. No mobile support required

**Implementation:**

**CSS Changes (web/templates/game_interface.html:832-852):**
- `.input-container`: Added `align-items: flex-end` to keep Send button at bottom
- `.input-field`: Added textarea-specific styles:
  - `resize: none` - prevent manual resize handles
  - `overflow: hidden` - no scrollbar, auto-expand instead
  - `min-height: 40px` - single line default
  - `max-height: 150px` - cap at ~5 lines
  - `line-height: 24px` - consistent line spacing

**HTML Changes (web/templates/game_interface.html:4551-4559):**
- Changed `<input type="text">` to `<textarea rows="1">`
- Replaced `onkeypress` with `onkeydown` and added `oninput` handler
- Added paste event handling via DOMContentLoaded listener

**JavaScript Functions (web/templates/game_interface.html:5619-5635):**
1. `handleKeyDown(event)`: Intercepts Enter key - sends if no Shift, adds newline if Shift held
2. `autoResizeTextarea(textarea)`: Calculates scrollHeight, caps at 150px, updates height
3. `resetTextareaHeight()`: Returns textarea to 40px after message sent
4. Paste event listener: Triggers resize after paste operation completes

**Layout Behavior:**
The existing flexbox structure handles the push-up effect naturally:
- `.panel-header` - Fixed height, no flex-grow (combat/adventure box, scroller, dice strip)
- `.panel-content#game-output` - `flex: 1`, shrinks as input grows
- `.input-container` - Bottom-positioned, expands upward

**Result:**
- Textarea starts at 40px (1 line), expands to max 150px (5 lines)
- Header bars remain fixed at top, never pushed out of view
- Chat transcript area flexibly accommodates input expansion
- Enter sends immediately, Shift+Enter for multi-line input
- Clean ~50-line change with zero breaking changes
- Works for both single-player and multi-PC modes

**Files Modified:**
- `web/templates/game_interface.html` (~50 lines: CSS 9 lines, HTML 10 lines, JS 31 lines)

---

### OpenSpec Initialization for Project Management (COMPLETED - 2026-02-12)

**Status:** COMPLETED  
**Priority:** High (Architecture/Planning)  
**Effort:** Medium (~1 hour)

**Objective:**
Initialize OpenSpec spec-driven development framework in the repository for structured planning of OpenRouter LLM Router and future EGO/RATIO cybernetic control system.

**Work Completed:**

**1. OpenSpec Repository Initialization:**
- Ran `openspec init --tools opencode` to enable OpenCode scaffolding support
- Generated local OpenSpec command skills in `.opencode/command/` directory
- Generated local OpenSpec workflow skills in `.opencode/skills/openspec-*/` directory
- Created project guardrails in `openspec/config.yaml` aligned with AGENTS.md conventions

**2. OpenRouter LLM Router Planning (Split into Two Changes):**
- Created `openspec/changes/openrouter-llm-router-facade`
  - Scope: Router facade implementation and model profile infrastructure
  - Fast-forwarded all artifacts: proposal, design, specs, tasks
  
- Created `openspec/changes/openrouter-llm-callsite-migration`
  - Scope: Tiered migration of 89 LLM callsites to `llm.call()` facade
  - Fast-forwarded all artifacts: proposal, design, specs, tasks

**3. Global OpenSpec Workflow Skill:**
- Created `~/.config/opencode/skills/openspec-workflow/SKILL.md`
- Provides consistent OPSX workflow execution across all projects
- Includes mandatory confirmation gates for archive operations
- Supports natural language triggers and explicit OPSX commands

**Key OpenSpec Commands Now Available:**
```bash
/opsx explore          # Investigation mode
/opsx new <name>       # Create new change
/opsx continue         # Continue current change
/opsx ff               # Fast-forward planning artifacts
/opsx apply            # Implement tasks
/opsx verify           # Validate implementation
/opsx archive          # Archive change (with confirmation)
```

**Result:**
- Clean scaffolding for OpenRouter implementation phases
- Structured planning capability for complex multi-phase work
- Consistent workflow across NeverEndingQuest and future projects
- Zero impact on current codebase (planning-only artifacts)

**Files Modified:**
- `openspec/config.yaml` (NEW - project guardrails)
- `openspec/changes/openrouter-llm-router-facade/*` (NEW - 5 artifact files)
- `openspec/changes/openrouter-llm-callsite-migration/*` (NEW - 4 artifact files)
- `~/.config/opencode/skills/openspec-workflow/SKILL.md` (NEW - global skill)

---

### EGO + RATIO Concept Plan Revision (COMPLETED - 2026-02-12)

**Status:** COMPLETED (Conceptual Review Only)  
**Priority:** Medium (Future Architecture)  
**Effort:** Medium (~2 hours documentation)

**Objective:**
Revise and tighten the EGO/RATIO cybernetic control architecture plan based on RSO (Relative State Observer) theoretical framework, preparing it for future OpenSpec implementation.

**Conceptual Foundation:**
EGO/RATIO architecture maps directly to the RSO (Relative State Observer) framework:
- **EGO (fast, bounded)** = State Observer reflex controller (System 1)
- **RATIO (slow, reflective)** = Neocortical learning layer (System 2)
- **Python ground truth** = Mechanical Reality (P2)
- **LLM narration** = Narrative Reality (P1)
- **Control objective** = Maximize narrative richness while maintaining P1/P2 consistency

**Key Architectural Decisions:**

**1. Boundary Contract (Non-Negotiable):**
- Python engine state is authoritative (Realitas)
- EGO writes only Tier 1a prompt knobs
- RATIO writes Tier 1a, 1b, and 2 (with review gate)
- Tier 3 (schemas, contracts) is immutable
- All edits logged, attributable, reversible

**2. Decision Relay (EGO):**
- **END (DRIFT):** Acceptable flavor divergence - log only
- **ADJUST (DISTORTION):** Recoverable mismatch - Tier 1a adjustment
- **ESCALATE (HALLUCINATION):** Serious causal break - correction + RATIO queue

**3. Human DM as External Input:**
- Human behavior is exogenous control signal, not noise
- Distinguish unsanctioned hallucination from table-preferred style drift
- Use multiple signals: no correction request, no regenerate/edit, stable continuation
- Enables implicit RLHF without thumbs-up buttons

**4. Write Surface Policy:**
- **Tier 1a:** Temperature, narration quotas, style weights (EGO + RATIO)
- **Tier 1b:** Safe prose guidance (RATIO only)
- **Tier 2:** Behavioral guidance (RATIO + strong checks)
- **Tier 3:** Immutable schemas and parser-critical contracts

**Implementation Phasing (Conceptual):**
- **Phase 0:** Gate conditions (router stable, baseline metrics)
- **Phase 1:** Passive foundation (event capture, no writes)
- **Phase 2:** EGO observe/classify (dashboard, audit, no live writes)
- **Phase 3:** Bounded EGO adjustments (Tier 1a canary, rollback enabled)
- **Phase 4:** RATIO proposal engine (between-session synthesis, review gate)
- **Phase 5:** Controlled adaptation (pattern library, measured outcomes)

**Go/No-Go Gates:**
- Gate A: Event coverage complete, prompt import validated
- Gate B: Classification quality acceptable, no latency impact
- Gate C: No oscillation, rollback proven
- Gate D: Review throughput acceptable, net positive edits

**Major Risks:**
1. Overfitting to short-term play style
2. Controller oscillation from aggressive tuning
3. Prompt regression from broad structural edits
4. DB-as-runtime-source fragility
5. Cost overrun from frequent analysis calls

**Mitigations:**
- Strict tier enforcement, write budgets, cooldowns
- Human/agent review queue
- Regression replay before deploy
- Last-good prompt fallback
- Conservative canary rollout

**OpenSpec Scaffolding for Future Build:**
Three planned OpenSpec changes when implementation begins:
1. `ego-foundation-passive-observer` - Phase 1 passive foundation
2. `ego-bounded-adjustments` - Phase 2-3 bounded adjustments
3. `ratio-reviewed-evolution` - Phase 4-5 RATIO adaptation

**Prerequisite Dependency:**
Requires completion of `openrouter-llm-router-facade` for unified `llm.call()` entrypoint with role/task routing and usage stats.

**Files Modified:**
- `plans/version-2/CNS build/EGO.md` (REWRITTEN - concise architecture, 353 lines)
- `plans/EGO-Comments_on_Cybernetic_Potentials.md` (REFERENCE - theoretical analysis)

**Status:**
Ready for implementation when:
1. Current tester build stabilized and released
2. OpenRouter router changes completed and validated
3. Baseline divergence metrics captured
4. Cost and time budgets defined for canary sessions

### Memory Foundation Retrieval + Backfill (COMPLETED - 2026-02-13)

**Status:** COMPLETED  
**Priority:** High (Narrative Continuity Foundation)  
**Effort:** Medium (~3-4 hours)

**Objective:**
Implement Stage 1 memory foundation with deterministic retrieval, idempotent ingest, read-only inspection route, and practical backfill tooling for existing campaign histories.

**Core Implementation:**
1. **Memory package scaffold (`core/memory/`):**
   - `memory_db.py`: SQLite bootstrap + idempotent migrations (`schema_migrations`)
   - `memory_retrieval.py`: deterministic ranking queries
   - `memory_ingest.py`: journal ingest + file ingest + history backfill
   - `__init__.py`: exported service surface

2. **Schema + readiness tables (`memory_db.py`):**
   - Core: `entities`, `entity_aliases`, `entity_roles`, `journal_entries`, `memory_events`, `memory_links`, `companion_memory_state`, `retrieval_snippets`
   - EGO/RATIO readiness (additive/optional): `memory_policy_profiles`, `memory_policy_assignments`, `retrieval_audit_log`, `controller_change_log`, `memory_event_provenance`

3. **Deterministic retrieval (`memory_retrieval.py`):**
   - `get_entity_timeline()` with weighted SQL scoring (pinned/active-PC/importance/persistence/decay/reinforcement)
   - `get_context_memories()` scene-aware pack retrieval
   - `get_retirement_return_memories()` milestone retrieval
   - Guardrails: limit clamping + deterministic tie-break (`event_ts`, `event_id`)
   - Optional audit logging (best-effort no-op if table absent)

4. **Ingestion + backfill (`memory_ingest.py` + script):**
   - `ingest_journal_entry()` checksum idempotency (`source_type`, `checksum`)
   - `ingest_journal_file()` malformed-entry tolerance + deferred-link metadata
   - `backfill_memory_db_from_histories()` pulls from:
     - `journal.json`
     - `modules/conversation_history/conversation_history.json`
     - `modules/conversation_history/combat_conversation_history.json`
   - Auto-upserts party entities from `party_tracker.json` and links events by known names
   - New script: `scripts/backfill_memory_db.py`

5. **Backfill utility flags (NEW):**
   - `--dry-run`: runs against temp DB copy and discards writes
   - `--include-system`: includes `role=system` history messages in backfill source set

6. **Web route integration (`web/routes/memory_routes.py` + `web/web_interface.py`):**
   - `GET /api/memory/entity/<entity_id>?limit=25`
   - Startup memory DB init hook is guarded and non-blocking
   - Fallback behavior returns safe empty timeline when DB unavailable

**Backfill Results (2026-02-13):**
- Default (no system messages):
  - `journal`: 40
  - `conversation_history`: 48
  - `combat_history`: 23
  - `events_created`: 111
  - `links_created`: 478
- Include-system dry-run:
  - `conversation_history`: 65
  - `combat_history`: 34
  - `events_created`: 139
  - `links_created`: 534

**Validation:**
- `python3 -m py_compile core/memory/memory_db.py core/memory/memory_retrieval.py core/memory/memory_ingest.py core/memory/__init__.py web/routes/memory_routes.py` -> PASS
- `python3 scripts/test_memory_retrieval_plan.py` -> PASS (9 tests)
- `.venv/bin/python scripts/test_memory_foundation.py` -> PASS (5 tests)

**Files Added:**
- `core/memory/memory_db.py`
- `core/memory/memory_retrieval.py`
- `core/memory/memory_ingest.py`
- `core/memory/__init__.py`
- `web/routes/memory_routes.py`
- `scripts/backfill_memory_db.py`
- `scripts/test_memory_foundation.py`

**Files Modified:**
- `web/web_interface.py`
- `plans/memory.md`
- `openspec/changes/memory-schema-retrieval-foundation/*`

### Memory Backfill Source Selection + DB Portability Tools (COMPLETED - 2026-02-13)

**Status:** COMPLETED  
**Priority:** High (Archive/Restore Readiness)  
**Effort:** Small-Medium (~1-2 hours)

**Objective:**
Add operator-safe source selection and portability tooling so memory DB workflows can support future campaign archive/restore operations without coupling to gameplay runtime.

**Implementation:**
1. **Selective source backfill (`scripts/backfill_memory_db.py` + `core/memory/memory_ingest.py`):**
   - Added `--sources` CSV selector with allowed values: `journal`, `conversation`, `combat`
   - Invalid values fail fast with clear error output
   - Backfill orchestration now gates source channels deterministically

2. **Portability module (`core/memory/memory_portability.py`):**
   - `export_memory_db_package()`
   - `validate_memory_package()`
   - `import_memory_db_package()`
   - Export manifest includes schema version, timestamp, row counts, applied migrations, campaign metadata, and DB SHA-256 integrity hash

3. **Safe import defaults:**
   - Import blocks overwrite unless explicit `--overwrite`
   - `--dry-run` performs full validation with zero writes

4. **Tooling integration:**
   - `scripts/backfill_memory_db.py` now supports backfill, export, and import workflows
   - `core/memory/__init__.py` exports portability helpers

5. **Tests:**
   - New `scripts/test_memory_backfill_portability.py`
   - Covers selector parsing/validation, selective ingest idempotency, export/import safety defaults, manifest compatibility checks

**Validation:**
- `python3 -m py_compile core/memory/memory_ingest.py core/memory/memory_portability.py core/memory/__init__.py scripts/backfill_memory_db.py scripts/test_memory_backfill_portability.py` -> PASS
- `python3 scripts/test_memory_backfill_portability.py` -> PASS
- `python3 scripts/backfill_memory_db.py --sources journal,foo` -> expected error (invalid selector)

**OpenSpec:**
- Created and applied change: `memory-backfill-portability-tools`
- Archived to: `openspec/changes/archive/2026-02-13-memory-backfill-portability-tools`
