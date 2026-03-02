---
name: debug-monitor
description: On-demand TABLETOP MODE debug configuration, log analysis, and cleanup workflow.
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: debugging
  project: NeverEndingQuest
---

# Tabletop Mode Debug Monitor Skill

**Version:** 2.3.0 (Three-Phase Complete Workflow)

## Purpose

On-demand debugging support for TABLETOP MODE features. Reads game logs on request, filters for errors, and displays immediate summary. **Automatically detects and offers to enable debug configuration.**

## Architecture

Simplified polling implementation with smart enable workflow:
- Triggered by user request (no background monitoring)
- **Auto-detects if debug categories are disabled**
- **Offers to enable them automatically**
- Reads game_debug.log directly when invoked
- Filters for CRITICAL/ERROR/TABLETOP MODE entries
- Displays summary immediately with restart instructions
- Zero overhead when not in use

## Trigger Phrases

### Phase 1: Start Debug (Configuration)
- `start debug` - **Initialize debug mode** (START HERE)
  - Checks if debug configuration is enabled
  - Auto-enables if disabled (edits config files)
  - Prompts for server restart
  - Use this FIRST to enable debugging

### Phase 2: Check Debug (Analysis)
- `check debug` or `check debug log` - **Scan for errors**
  - Enhanced error reporter with timestamped listings
  - Groups errors by type and source
  - Extracts file locations and line numbers
  - Provides actionable fix suggestions
- `show me errors` - Display error summary
- `check for critical errors` - Focus on critical issues only

### Phase 3: Stop Debug (Cleanup)
- `stop debug` - **Disable debug mode and clean up**
  - Reverts config files to debug=false
  - Deletes all debug log files
  - Shows "debug off" after restart
  - Use this when done debugging

### Utility Commands
- `enable debug mode` - Enable TABLETOP MODE debugging
- `tabletop debug status` - Show debug configuration status

## Files

### New Files
- `utils/tabletop_debug.py` - Helper functions (error filtering, formatting)
- `scripts/check_debug_logs.py` - Standalone log checker script with --enable flag
- `scripts/debug_error_reporter.py` - **Enhanced error reporter with critical error analysis**

### Modified Files (Plugin-Safe, Kept)
- `debug_config.py` - Categories for filtering: `tabletop_mode`, `tabletop_verbose`
- `config.py` - Flag: `TABLETOP_DEBUG_VERBOSE`
- `core/managers/multi_pc_combat.py` - 16 debug instrumentation points
- `core/managers/combat_manager.py` - 2 debug instrumentation points

## Usage Workflow

### Step 1: Start Debug (Configuration Check)

**When you first start debugging, check configuration:**

```
User: start debug
System: 🔍 Checking debug configuration...
        
        ============================================================
        TABLETOP MODE Debug Configuration Status
        ============================================================
        
        Current Settings:
          debug_config.py:
            - tabletop_mode: True
            - tabletop_verbose: True
        
          config.py:
            - TABLETOP_DEBUG_VERBOSE: True
        
        ✅ Status: DEBUG MODE ENABLED
        
        Debug logging is active. Run 'check debug' to see errors.
```

**If Debug is Disabled → Auto-Enable:**

```
User: start debug
System: 🔍 Checking debug configuration...
        
        ============================================================
        TABLETOP MODE Debug Configuration Status
        ============================================================
        
        TABLETOP MODE debugging is currently DISABLED.
        
        Current settings:
          - debug_config.py -> tabletop_mode: False
          - debug_config.py -> tabletop_verbose: False
          - config.py -> TABLETOP_DEBUG_VERBOSE: False
        
        Would you like me to enable it? (yes/no)

User: yes
System: ✅ Enabling TABLETOP MODE debug...
        
        Changes made:
          ✓ debug_config.py: tabletop_mode = True, tabletop_verbose = True
          ✓ config.py: TABLETOP_DEBUG_VERBOSE = True
        
        ============================================================
        🔄  ACTION REQUIRED: Restart your server
        ============================================================
        
        Please stop and restart your server in your terminal.
        The config changes only take effect on restart.
        
        Once restarted, run 'check debug' to see errors.
```

### Step 2: Check Debug (Error Analysis)

**After enabling debug and restarting, analyze errors:**

```
User: check debug
System: 🔍 Scanning game logs for errors...
        
        ============================================================
        DEBUG STATUS SUMMARY
        ============================================================
        
        🔴 System Status: CRITICAL ISSUES DETECTED
           Critical: 28 | Errors: 18 | Warnings: 572
        
        Latest Critical:
          • [2026-02-06 11:44:13] MultiPCCombatManager: AttributeError
          • [2026-02-06 11:42:22] CombatManager: KeyError
          • [2026-02-06 11:40:11] QuestPlayerFormatter: Validation failed
        
        Run detailed analysis? (yes/no)

User: yes
System: ============================================================
        CRITICAL ERROR REPORT
        ============================================================
        
        🔴 CRITICAL ERRORS (28):
        ----------------------------------------------------------------------
        
        1. [2026-02-06 11:44:13] MultiPCCombatManager
          Location: core/managers/multi_pc_combat.py:867
          Exception: AttributeError
          Message: 'MultiPCCombatManager' object has no attribute 'pc_phase_complete'
        
        2. [2026-02-06 11:42:22] CombatManager
          Exception: KeyError
          Message: 'armorClass'
        
        ...
        
        ============================================================
        SUGGESTED ACTIONS
        ============================================================
        
        • AttributeError detected - Likely a missing attribute or property
          → Check recent code changes for renamed/moved attributes
        
        • Combat-related errors detected
          → Check party_tracker.json and encounter files
```

### Manual Enable (Alternative)
```
User: enable debug mode
System: ✅ TABLETOP MODE debug enabled!
        
        🔄 ACTION REQUIRED: Restart your server
        
        Please stop and restart your server in your terminal.
        The config changes only take effect on restart.
```

### After Server Restart
```
User: check debug
System: === TABLETOP MODE Debug Summary ===
        Source: modules/logs/game_debug.log (last 100 lines)
        
        TABLETOP MODE Activity: 12 entries
        Latest: 2026-02-06 14:31:12
        
        [Shows detailed log output]
```

### Step 3: Stop Debug (Cleanup)

**When done debugging, clean up and disable:**

```
User: stop debug
System: 🧹 Stopping debug mode and cleaning up...
        
        ============================================================
        TABLETOP MODE Debug - Cleanup
        ============================================================
        
        Reverting configuration files:
          ✓ debug_config.py: tabletop_mode = False, tabletop_verbose = False
          ✓ config.py: TABLETOP_DEBUG_VERBOSE = False
        
        Cleaning up log files:
          ✓ Deleted modules/logs/game_debug.log
          ✓ Deleted modules/logs/game_errors.log
          ✓ Deleted 5 rotated log files
        
        ============================================================
        🔄  ACTION REQUIRED: Restart your server
        ============================================================
        
        Please stop and restart your server in your terminal.
        
        After restart, debug mode will be OFF.
        Logs cleaned and ready for next session.
```

**After Server Restart:**
```
User: check debug status
System: ============================================================
        TABLETOP MODE Debug Configuration Status
        ============================================================
        
        Current Settings:
          debug_config.py:
            - tabletop_mode: False
            - tabletop_verbose: False
        
          config.py:
            - TABLETOP_DEBUG_VERBOSE: False
        
        ⚠️  Status: DEBUG MODE DISABLED (debug off)
        
        To enable debugging, run: start debug
```

## Automated Workflows

### Enable Workflow (`start debug`)

When the skill detects debug is disabled:

1. **Check Status** - Reads debug_config.py and config.py
2. **Prompt User** - "Would you like me to enable it? (yes/no)"
3. **If Yes:**
   - Edit debug_config.py: Set `tabletop_mode = True`
   - Edit config.py: Set `TABLETOP_DEBUG_VERBOSE = True`
4. **Show Restart Message** - Clear instructions to restart server
5. **Done** - User restarts, then runs check again

### Disable Workflow (`stop debug`)

When you want to clean up and disable debugging:

1. **Revert Configs** - Sets all debug flags to False
   - Edit debug_config.py: Set `tabletop_mode = False`
   - Edit config.py: Set `TABLETOP_DEBUG_VERBOSE = False`
2. **Clean Up Logs** - Deletes all debug log files
   - game_debug.log and rotated versions
   - game_errors.log and rotated versions
3. **Show Restart Message** - Clear instructions to restart server
4. **Done** - After restart, debug is OFF and logs are clean

### Example Output

```
=== TABLETOP MODE Debug Summary ===
Source: modules/logs/game_debug.log (last 100 lines)

CRITICAL (1):
[2026-02-06 14:31:12] MultiPCCombatManager.handle_combat_command
  File: core/managers/multi_pc_combat.py:867
  Type: AttributeError
  Message: 'NoneType' object has no attribute 'ac'

ERRORS (2):
[2026-02-06 14:28:45] CombatManager._persist_combat_changes
  Message: Failed to write encounter file

WARNINGS (3):
[2026-02-06 14:25:30] Missing armorClass for enemy 'goblin'

TABLETOP MODE Activity: 12 entries
Latest: 2026-02-06 14:31:12

=== Configuration ===
tabletop_mode: True
Log file size: 1757 KB
```

## Enhanced Error Reporting Features

The `start debug` command uses an advanced error reporter (`scripts/debug_error_reporter.py`) that provides:

### 1. Automatic Error Classification
- **CRITICAL**: Exceptions (AttributeError, KeyError, etc.), crashes, failures
- **ERROR**: Failed operations, validation failures
- **WARNING**: Missing data, unexpected states

### 2. Timestamped Chronological Listing
Errors sorted by time with source component identification:
```
[2026-02-06 11:44:13] MultiPCCombatManager: AttributeError
[2026-02-06 11:42:22] CombatManager: KeyError
```

### 3. Smart Error Grouping
Groups similar errors by exception type or source:
```
AttributeError: 5 occurrence(s)
  Latest: [11:44:13] MultiPCCombatManager: 'NoneType' object has no attribute 'ac'

KeyError: 3 occurrence(s)
  Latest: [11:42:22] CombatManager: 'armorClass'
```

### 4. Actionable Fix Suggestions
Based on error patterns, suggests specific actions:
- AttributeError detected → Check for renamed/moved attributes
- KeyError detected → Check data loading and JSON parsing
- Combat-related errors → Check party_tracker.json and encounter files

### 5. File Location Extraction
Automatically extracts file paths and line numbers:
```
Location: core/managers/multi_pc_combat.py:867
```

## Severity Levels

### CRITICAL (Always Shown)
- Errors causing crashes or exceptions
- MultiPCCombatManager failures
- Combat state corruption
- File I/O errors in combat persistence

### ERROR (Always Shown)
- Failed operations
- Validation failures
- Data inconsistencies

### WARNING (Shown with `--warnings` flag)
- Unexpected state transitions
- Missing data in combat calculations
- Turn queue anomalies

### INFO/VERBOSE (Shown with `--verbose` flag)
- Method entry/exit tracing
- State transitions
- Combat command flow

## Script Usage

### Enhanced Error Reporter (Recommended)
```bash
# Quick status check (default)
python scripts/debug_error_reporter.py

# Detailed critical error report with fix suggestions
python scripts/debug_error_reporter.py --detailed

# Show only critical errors (hides warnings)
python scripts/debug_error_reporter.py --critical-only

# Show errors from last hour only
python scripts/debug_error_reporter.py --last-hour

# Show current session errors (last 4 hours)
python scripts/debug_error_reporter.py --session

# Scan more lines (default: 500)
python scripts/debug_error_reporter.py --detailed --lines 1000
```

### Basic Log Checker
```bash
# Check for critical errors and errors (auto-enables if needed)
python scripts/check_debug_logs.py

# Enable debug mode explicitly
python scripts/check_debug_logs.py --enable

# Include warnings
python scripts/check_debug_logs.py --warnings

# Full verbose output
python scripts/check_debug_logs.py --verbose

# Custom line count
python scripts/check_debug_logs.py --lines 200

# Stop debug mode and clean up logs
python scripts/check_debug_logs.py --stop
```

### Manual Log Reading
```bash
# Direct log access
tail -50 modules/logs/game_debug.log | grep -E "(CRITICAL|ERROR|tabletop_mode)"
```

## Configuration

### debug_config.py Categories
```python
# TABLETOP MODE: Multi-PC debugging
"tabletop_mode": True,      # TT-specific combat and UI debugging
"tabletop_verbose": True,   # Full method call tracing
```

### config.py Flag
```python
# TABLETOP MODE: Debug configuration
TABLETOP_DEBUG_VERBOSE = True  # Enable full TT debug tracing
```

## Merge Safety

All modifications to upstream files:
- Marked with `# TABLETOP MODE:` comments
- Append-only (don't modify existing categories/flags)
- Minimal line count (instrumentation only)
- No logic changes, only debug logging

## Rollback

To disable:

1. Disable categories in debug_config.py:
   ```python
   "tabletop_mode": False,
   "tabletop_verbose": False,
   ```

2. Set flag in config.py:
   ```python
   TABLETOP_DEBUG_VERBOSE = False
   ```

3. Remove instrumentation (optional):
   - Comment out or delete `# TABLETOP MODE:` debug blocks

4. Delete skill directory (optional):
   ```bash
   rm -rf .opencode/skills/debug-monitor/
   rm -f scripts/check_debug_logs.py
   ```

## Version History

### 2.3.0 (2026-02-06)
- **Complete three-phase debug workflow**:
  - Phase 1: `start debug` → Enable debugging, configure, restart
  - Phase 2: `check debug` → Analyze errors with enhanced reporter
  - Phase 3: `stop debug` → Disable debugging and clean up
- **Added `stop debug` command**:
  - Reverts config files to debug=false
  - Deletes all debug log files
  - Shows "debug off" status after restart
- **KISS principle** - No auto-disable, manual control only

### 2.2.0 (2026-02-06)
- **Added enhanced error reporter** (`scripts/debug_error_reporter.py`)
- Clarified command separation:
  - `start debug` → Configuration check and enable workflow
  - `check debug` → Enhanced error analysis with timestamped listings
- Timestamped chronological error listings
- Smart error grouping by type and source
- Actionable fix suggestions based on error patterns
- File location extraction with line numbers
- Critical error prioritization

### 2.1.0 (2026-02-06)
- Added automated enable workflow
- Added restart notification message
- Added --enable flag to check_debug_logs.py
- Smart detection of disabled debug mode

### 2.0.0 (2026-02-06)
- Rebuilt as polling-based (no background processes)
- Simplified architecture
- Removed session management complexity
- Added standalone check_debug_logs.py script

### 1.0.0 (2026-02-06)
- Initial subagent-based implementation
- Real-time monitoring with background process
- Auto-stop functionality
- ONCNotes.md integration

## See Also

- AGENTS.md - Coding guidelines
- debug_config.py - Debug category configuration
- utils/tabletop_debug.py - Helper functions
- scripts/check_debug_logs.py - Basic log checker script
- **scripts/debug_error_reporter.py** - Enhanced error reporter with critical analysis
