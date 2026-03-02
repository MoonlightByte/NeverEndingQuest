---
name: dev-homebrew-ingest
description: Developer workflow to preflight, transform, validate, and ingest Homebrew modules.
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: content-ingest
  project: NeverEndingQuest
---

# Dev Homebrew Ingest Skill

**Purpose:** Developer-only workflow for preparing and ingesting Homebrew modules into NEQ.

**Target Audience:** Developers (you + other devs who want to add modules programmatically)
**NOT for end-users** - End-users should use Toolkit GUI for module creation.

---

## Trigger Phrases

- "prep homebrew ingest <path>"
- "ingest module dev <path>"
- "convert homebrew to neq <path>"
- "process homebrew <path>"

---

## Workflow Overview

```
Homebrew Source (Docs/modules/hombrew/*.md)
           |
           v
    [1] PREFLIGHT CHECKS
           - Title hygiene (strip "CLONE - ADVENTURE:" prefixes)
           - Metadata completeness (title, description, author)
           - Structure classification (room-based vs act/location)
           |
           v
    [2] STRUCTURAL TRANSFORM (if needed)
           - ACT/LOCATION format → ## Room N: format
           - Add explicit exits
           - Generate deterministic connectivity
           |
           v
    [3] DRY-RUN VALIDATION
           - scripts/import_homebrewery_module.py --dry-run --deterministic
           |
           v
    [4] STRICT INGEST
           - Copy to modules/ingest/
           - OR run: scripts/import_homebrewery_module.py --strict --deterministic
           |
           v
    [5] REGISTRY VERIFICATION
           - Check sidecar .result.json
           - Confirm slug in world_registry.json
           - Confirm module appears in /api/toolkit/modules
           |
           v
    [6] REPORT
           - PASS/FAIL status
           - Registry slug
           - Quarantine reason (if failed)
           - Cleanup guidance
```

---

## Tool Dependencies

**Existing (already built):**
- `core/importers/homebrewery_importer.py` - deterministic ingest path
- `scripts/import_homebrewery_module.py` - CLI runner
- `core/generators/module_stitcher.py` - registry integration

**To Build (5 helper scripts):**
1. `scripts/homebrew_preflight.py` - readiness assessment
2. `scripts/homebrew_transform_to_deterministic.py` - structural conversion
3. `scripts/homebrew_ingest_dev.py` - orchestrator
4. `scripts/homebrew_sidecar_audit.py` - result validation
5. `scripts/homebrew_registry_guard.py` - duplicate prevention

---

## Step-by-Step Execution Guide

### Step 1: Read Source File

```python
source_path = Path("<provided_path>")
content = source_path.read_text(encoding='utf-8')
```

### Step 2: Preflight Checks

Run `scripts/homebrew_preflight.py <source_path>` and parse JSON output:

Expected output:
```json
{
  "ready": false,
  "issues": [
    {
      "type": "title_hygiene",
      "severity": "fixable",
      "current": "CLONE - ADVENTURE: The Secrets of Mangrove Keep",
      "recommended": "The Secrets of Mangrove Keep"
    },
    {
      "type": "structure",
      "severity": "fixable",
      "detected": "act_location_format",
      "required": "room_blocks"
    }
  ],
  "structure_class": "act_location",
  "can_auto_transform": true
}
```

### Step 3: Transform (if needed)

If `can_auto_transform: true`, run:

```bash
python scripts/homebrew_transform_to_deterministic.py \
  --source <source_path> \
  --output /tmp/prepared_<slug>.md
```

Transform rules:
- Strip title prefixes: `"CLONE - ADVENTURE:"`, `"CLONE:"`, etc.
- Ensure metadata block with: title, author, description, party_size_min, party_size_max
- Convert ACT/LOCATION bullets to `## Room N: <name>` sections
- Infer exits from location descriptions ("north of X", "south gate", etc.)
- Add empty encounters list if not present
- Maintain NEQ sequential IDs (not literal room numbers)

### Step 4: Dry-Run Validation

```bash
python scripts/import_homebrewery_module.py \
  --source /tmp/prepared_<slug>.md \
  --strict \
  --deterministic \
  --dry-run \
  --json
```

Must return:
```json
{
  "status": "dry_run",
  "module_slug": "The_Secrets_of_Mangrove_Keep",
  "validation": {
    "passed": true,
    "errors": [],
    "success_rate": "100%"
  }
}
```

If `passed: false`, stop and report issues. Do not proceed to ingest.

### Step 5: Registry Guard Check

```bash
python scripts/homebrew_registry_guard.py \
  --slug "The_Secrets_of_Mangrove_Keep" \
  --check-duplicate
```

Must return:
```json
{
  "safe_to_proceed": true,
  "conflicts": []
}
```

If conflicts exist, stop and suggest rename/alternate slug.

### Step 6: Strict Ingest

Option A - CLI direct (cleanest):
```bash
python scripts/import_homebrewery_module.py \
  --source /tmp/prepared_<slug>.md \
  --strict \
  --deterministic
```

Option B - Copy to watch folder (triggers watcher):
```bash
cp /tmp/prepared_<slug>.md modules/ingest/
```

Wait for watcher to process (if watcher enabled and not running, use Option A).

### Step 7: Sidecar Verification

```bash
python scripts/homebrew_sidecar_audit.py \
  --slug "The_Secrets_of_Mangrove_Keep" \
  --require-success
```

Must return:
```json
{
  "valid": true,
  "sidecar_found": true,
  "status": "success",
  "registration": {
    "registration_attempted": true,
    "registration_success": true,
    "registry_module_present": true
  }
}
```

If quarantined, report `quarantine_reason` and stop.

### Step 8: Registry Verification

```bash
python scripts/homebrew_registry_guard.py \
  --slug "The_Secrets_of_Mangrove_Keep" \
  --verify-present
```

Must return:
```json
{
  "present": true,
  "module_key": "The_Secrets_of_Mangrove_Keep",
  "areas_count": 8,
  "has_encounters": true
}
```

### Step 9: Final Report

Output format:
```
[PASS] Homebrew Ingest Complete

Source: Docs/modules/hombrew/The Secrets of Mangrove Keep.md
Prepared: /tmp/prepared_The_Secrets_of_Mangrove_Keep.md
Module Slug: The_Secrets_of_Mangrove_Keep
Registry: modules/world_registry.json

Status: SUCCESS
Registration: Verified (registration_attempted=true, registry_module_present=true)
Areas: 8
Encounters: 3

Toolkit API: Ready (verify with: curl http://localhost:8357/api/toolkit/modules)
```

If failed:
```
[FAIL] Homebrew Ingest Blocked

Source: Docs/modules/hombrew/Bad Module.md
Issue: <quarantine_reason or validation errors>
Status: QUARANTINED

Next steps:
1. Fix issues in source
2. Re-run: prep homebrew ingest <path>
3. Cleanup: rm modules/ingest/<bad_file> (if copied)
```

---

## Stop Conditions

HALT and report immediately if:

1. **Canonical module missing after transform** - never overwrite Birble, Thornwood, Pumpkin
2. **Dry-run validation fails** - do not proceed to strict ingest
3. **Registry guard finds conflicts** - prevent duplicate/clone slugs
4. **Sidecar shows quarantine** - registration did not occur
5. **Registry verification fails** - module not present after claimed success
6. **File I/O error** - cannot read source or write prepared file

---

## Cleanup Guidance (on failure)

If ingest partially succeeds but registry verification fails:

```bash
# 1. Check sidecar for reason
cat modules/ingest/archive/*_<slug>.md.result.json

# 2. Remove bad module folder (if created)
rm -rf "modules/<slug>"

# 3. Remove from registry (if partially added)
python scripts/homebrew_registry_guard.py --remove <slug>

# 4. Re-run after fixing source
```

---

## Example Session

**User:** "prep homebrew ingest Docs/modules/hombrew/The Secrets of Mangrove Keep.md"

**Me:**
1. Read source file (260 lines)
2. Preflight: `structure_class: "act_location"`, `can_auto_transform: true`
3. Transform: created `/tmp/prepared_The_Secrets_of_Mangrove_Keep.md`
   - Title: "The Secrets of Mangrove Keep" (cleaned)
   - Added metadata block
   - Converted ACT/LOCATION → 8 room blocks
   - Inferred 12 exits
4. Dry-run: PASSED (validation 100%)
5. Registry guard: PASSED (no conflicts)
6. Strict ingest: SUCCESS
7. Sidecar audit: PASSED (registry_module_present: true)
8. Registry verification: CONFIRMED (8 areas, 3 encounters)

**Output:**
```
[PASS] Homebrew Ingest Complete

Source: Docs/modules/hombrew/The Secrets of Mangrove Keep.md
Prepared: /tmp/prepared_The_Secrets_of_Mangrove_Keep.md
Module Slug: The_Secrets_of_Mangrove_Keep
Registry: modules/world_registry.json

Status: SUCCESS
Registration: Verified
Areas: 8
Encounters: 3

Toolkit API: Ready
```

---

## Development Notes

This skill REUSES existing infrastructure:
- `core/importers/homebrewery_importer.py` (deterministic path)
- `scripts/import_homebrewery_module.py` (CLI)
- `core/generators/module_stitcher.py` (registry)
- `web/extensions/module_ingest_watch.py` (optional watcher)

NEW scripts to build (see OpenSpec: `dev-homebrew-tools`):
1. `scripts/homebrew_preflight.py`
2. `scripts/homebrew_transform_to_deterministic.py`
3. `scripts/homebrew_ingest_dev.py`
4. `scripts/homebrew_sidecar_audit.py`
5. `scripts/homebrew_registry_guard.py`

Version: 1.0
Last Updated: 2026-03-02
