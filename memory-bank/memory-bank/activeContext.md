# NeverEndingQuest Memory Bank

## Project Overview

NeverEndingQuest is an AI-powered Dungeon Master system for running SRD 5.2.1 compatible tabletop RPG campaigns. This repository is a merge-safe tabletop multiplayer plugin/modification of the upstream MoonlightByte/NeverEndingQuest project.

## Current Session Context

### Recently Completed Work

**Issue: Multi-PC Combat Enemy Armor Class Fix**

**Problem**: In Multi-PC combat mode, enemy Armor Class (AC) was defaulting to 10 regardless of monster template values (e.g., Mimic has AC 12 but was treated as AC 10).

**Root Cause**: 
- `core/generators/combat_builder.py` was not including `armorClass` when building enemy encounter entries
- `core/managers/multi_pc_combat.py` had fallback logic that only triggered when AC was `None` or `0`, but `combat_builder.py` was defaulting to `10`

**Solution Implemented**:

1. **Primary Fix** (`core/generators/combat_builder.py` line ~347):
   - Added `armorClass` field to enemy monster dictionary
   - Marked with `# TABLETOP MODE:` comment for merge safety
   - Code: `"armorClass": monster_data.get("armorClass", 10)`

2. **Backfill Logic** (`core/managers/multi_pc_combat.py` lines ~326-352):
   - Added imports: `ModulePathManager`, `safe_json_load`
   - Enhanced `initialize_turn_queue()` to look up missing AC from monster templates
   - Falls back to 10 only when template lookup fails
   - Handles both encounter data and party tracker module resolution

**Impact**:
- New encounters will include correct AC values
- Existing encounters (19 found without AC) will be backfilled at runtime
- `/att` command will now resolve hits/misses against correct AC

**Files Modified**:
- `core/generators/combat_builder.py` - Added armorClass to monster generation
- `core/managers/multi_pc_combat.py` - Added backfill logic for missing AC

**Verification**:
- Mimic monster template confirmed: AC 12
- 19 existing encounters identified missing armorClass
- Both files pass syntax validation

## Key Architecture Patterns

### Plugin Architecture (Merge-Safe)
- **Minimal Core Modifications**: Changes marked with `# TABLETOP MODE:` comments
- **Encapsulated Extensions**: New functionality in separate modules
- **State Detection**: Features activate based on `party_tracker.json` state

### Multi-PC Combat Pattern
- **Head-Body-Tail Prompt Architecture**: Immutable JSON block with all PCs, compressible narrative, fresh interactions
- **Deterministic Initiative**: Bypass AI tracker, use turn queue state
- **Phase Automation**: PC phase → Enemy phase with explicit `/end` trigger

## Key File Locations

- `core/generators/combat_builder.py` - Encounter generation
- `core/managers/multi_pc_combat.py` - Multi-PC combat state
- `core/managers/combat_manager.py` - Combat orchestration
- `party_tracker.json` - Single source of truth for party state
- `modules/encounters/*.json` - Encounter files
- `modules/*/monsters/*.json` - Monster templates

## Quality Standards

- No Unicode characters in Python code
- Schema validation required for JSON changes
- Atomic file operations for state changes
- Root cause fixes (not workarounds)
- Import patterns follow AGENTS.md standards
