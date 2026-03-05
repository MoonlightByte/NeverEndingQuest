# Module Gameplay Audit Skill

## Purpose

Validates monster reference parity for NeverEndingQuest modules before gameplay sessions. Ensures that all referenced monsters have JSON definitions and media assets, preventing tabletop mode fail-closed errors that cause narration/combat desync.

## Trigger Phrases

- "audit module gameplay"
- "validate module gameplay"
- "monster parity audit"

## Usage

```bash
# Basic audit
python scripts/audit_module_gameplay.py --module <module_name>

# With baseline comparison
python scripts/audit_module_gameplay.py --module <module_name> --baseline <baseline_module>

# JSON output for automation
python scripts/audit_module_gameplay.py --module <module_name> --json
```

## Output Contract

The audit produces four sections:

### 1. blocking_errors
Critical issues that will break tabletop gameplay:
- Missing monster JSON files
- Invalid JSON syntax
- Missing base media assets

### 2. warnings
Non-critical issues that may affect quality:
- Missing thumbnail images
- Missing video files
- Missing optional schema fields

### 3. coverage_stats
Quantitative metrics:
- referenced_monsters: Total unique monster references
- json_valid: Count of valid monster JSON files
- json_coverage_pct: Percentage of references with valid JSON
- media_base_coverage_pct: Percentage with base media assets

### 4. fix_list
Actionable items to resolve blockers.

## Exit Codes

- **0**: No blocking errors (safe to play)
- **1**: Blocking errors found (gameplay will fail)

## Runtime Contract

Monster filename resolution uses the same normalization as the game runtime:

1. Lowercase
2. Replace spaces/apostrophes with underscores
3. Replace any non-[a-z0-9_] with underscores
4. Collapse consecutive underscores
5. Trim leading/trailing underscores

## Tabletop Mode Warning

⚠️ **CRITICAL**: In tabletop multiplayer mode, missing monster JSON files cause `combat_builder.load_or_create_monster()` to return `None`, resulting in monsters appearing in narration but failing to materialize as valid combatants. This produces the "monsters appearing in narration but not combat" symptom.

Always run this audit before tabletop sessions.

## Examples

### Example 1: Failed audit

```
$ python scripts/audit_module_gameplay.py --module The_Pumpkin_Kings_Curse

❌ BLOCKING ERRORS (3):
  • Missing monster JSON: animated_scarecrow
  • Missing monster JSON: blight_tendril
  • Missing base media for: shadow

⚠️  TABLETOP MODE RISK:
   Missing monster JSON files will cause combat_builder to fail-closed,
   resulting in narration/combat desync for affected monsters.

🔧 FIX LIST (3 items):
  • Create: modules/The_Pumpkin_Kings_Curse/monsters/animated_scarecrow.json
  • Create: modules/The_Pumpkin_Kings_Curse/monsters/blight_tendril.json
  • Add media: modules/The_Pumpkin_Kings_Curse/media/monsters/shadow.jpg
```

### Example 2: Successful audit

```
$ python scripts/audit_module_gameplay.py --module The_Pumpkin_Kings_Curse

✅ No blocking errors found!

JSON Coverage: 22/22 (100.0%)
Media Coverage: 22/22 (100.0%)
```

### Example 3: Baseline comparison

```
$ python scripts/audit_module_gameplay.py --module The_Pumpkin_Kings_Curse --baseline The_Thornwood_Watch

Baseline (The_Thornwood_Watch) Comparison:
  JSON coverage: 88.9% -> 100.0%
  Media coverage: 100.0% -> 100.0%
```

## Enhanced Reference Extraction

The audit script performs multi-layer reference detection:

### 1. Structural References (Always Checked)
- `locations[].monsters[]` arrays
- `locations[].randomEncounters[].monsters[]` 
- `randomEncounters[].monsters[]` (top-level)
- `createEncounter` action payloads
- Nested monster descriptors in dict/list structures

### 2. Heuristic Text Scanning (Optional)
When `--strict-instructions` is enabled:
- `dmInstructions` and `dmNotes` fields
- `plotHooks` and `storyHooks`
- `dcChecks` descriptions
- Encounter narrative text

Heuristic patterns detect monster names in:
- Combat/encounter contexts ("fight the X", "spawn X")
- Quoted names ("'Animated Scarecrow'")
- Capitalized phrases in combat contexts

**Source Attribution**: Every detected reference includes:
- Source file (area JSON)
- Path within structure (e.g., `locations[2].randomEncounters[1].monsters[0]`)
- Confidence level (`structural` or `heuristic`)

### Strict Mode

```bash
# Heuristic unresolved refs become blockers
python scripts/audit_module_gameplay.py --module <name> --strict-instructions
```

Use strict mode for final pre-release validation. Use default mode for development (heuristic findings are warnings only).

## Implementation Notes

- Schema validation uses `schemas/mon_schema.json` if available
- Falls back to basic required field checks if schema unavailable
- Media checks look for: `.jpg`, `.jpeg`, `.png`, `.webp` extensions
- Video checks look for: `_video.mp4` suffix
- Backup files (`*_BU.json`) are excluded from reference extraction
- Normalization matches runtime `normalize_character_name()` exactly

## Dependencies

- Python 3.7+
- Standard library only (json, glob, os, re, sys, argparse, pathlib, typing)
- Optional: Pillow for placeholder image generation (not required for audit)
