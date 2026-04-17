---
name: dev-homebrew-ingest
description: Developer workflow to normalize, preflight, transform, validate, and ingest Homebrew modules with media extraction and portrait prewarm. Also covers existing-module registry remediation and finishing/publication.
license: MIT
compatibility: opencode
metadata:
  audience: developers
  workflow: content-ingest
  project: NeverEndingQuest
---

# Dev Homebrew Ingest Skill

**Purpose:** Developer workflow for preparing, ingesting, finishing, and publishing Homebrew modules into NEQ. Covers both new-source ingest and existing-module remediation.

**Target Audience:** Developers (you + other devs who want to add modules programmatically)
**NOT for end-users** - End-users should use Toolkit GUI for module creation and upload.

---

## Two Modes

This skill supports two distinct entry points:

| Mode | Entry | When to Use |
|------|-------|-------------|
| **Mode A: Source Ingest** | Markdown file on disk or uploaded via GUI | New module from Homebrewery/homebrew markdown source |
| **Mode B: Existing-Module Remediation** | Module folder already exists under `modules/` | Module exists on disk but is missing from registry, needs finishing, or needs publication audit |

Both modes converge at the **Finishing + Publication** stage.

---

## Trigger Phrases

**Mode A (Source Ingest):**
- "prep homebrew ingest `<path>`"
- "ingest module dev `<path>`"
- "convert homebrew to neq `<path>`"
- "process homebrew `<path>`"

**Mode B (Existing-Module Remediation):**
- "finish module `<slug>`"
- "register existing module `<slug>`"
- "remediate module `<slug>`"
- "bring `<slug>` up to spec"

---

## Mode A: Source Ingest Workflow

```
Homebrew Source (*.md)
         |
         v
  [A1] PREFLIGHT CHECKS
         - Title hygiene (strip prefixes)
         - Metadata completeness
         - Structure classification (room-based vs act/location)
         |
         v
  [A2] LLM NORMALIZATION (when source is human-readable only)
         - Convert prose into deterministic room-based markdown
         - Preserve source intent; do not invent mechanics
         |
         v
  [A3] STRUCTURAL TRANSFORM (if needed)
         - ACT/LOCATION format -> ## Room N: format
         - Add explicit exits, generate connectivity
         |
         v
  [A4] DRY-RUN VALIDATION
         - scripts/homebrew_ingest_dev.py --dry-run --strict
         |
         v
  [A5] REGISTRY GUARD
         - Check for duplicate/conflicting slugs
         |
         v
  [A6] STRICT INGEST
         - Deterministic import via homebrewery_importer
         |
         v
  [A7] CONTINUITY NORMALIZATION
         - Backfill continuity v1 contract keys
         - Enrich cross_module_refs from narrative hints
         |
         v
  [A8] SEMANTIC AUTHORITY ENRICHMENT
         - Location alias map, NPC scene-authority map
         |
         v
      *** CONVERGE -> FINISHING + PUBLICATION (below) ***
```

### Mode A GUI Parity

The GUI upload path (`web/routes/toolkit_homebrew_routes.py`) executes:
1. Upload + normalization review gate
2. Packet build (`web/extensions/toolkit_homebrew_packet_builder.py`)
3. Readiness gate (`web/extensions/toolkit_homebrew_readiness_gate.py`)
4. Finisher (`web/extensions/toolkit_module_finisher.py`)
5. Publication outcome: `completed` or `not_publishable`

The dev CLI (`scripts/homebrew_ingest_dev.py`) runs the same shared pipeline entrypoint (`run_ingest_pipeline`) but enters through preflight/transform/import rather than GUI upload/packet build.

Both paths converge at the finisher stage. The dev CLI runs media/prewarm stages that the GUI currently skips.

---

## Mode B: Existing-Module Remediation Workflow

```
Existing Module Folder (modules/<slug>/)
         |
         v
  [B1] ARTIFACT VALIDATION
         - Confirm: module_context.json exists
         - Confirm: module_plot.json exists
         - Confirm: areas/*.json exist (at least 1 non-BU area file)
         - If any missing: HALT, report what is needed
         |
         v
  [B2] REGISTRY DRIFT CHECK
         - scripts/homebrew_registry_guard.py --slug <slug> --verify-present --json
         - If already present: skip to finishing
         - If missing: continue to collision check
         |
         v
  [B3] COLLISION CHECK
         - Extract area IDs from modules/<slug>/areas/*.json (non-BU files)
         - Check each against world_registry.json areas
         - If collisions: HALT, report conflicting IDs
         |
         v
  [B4] TARGETED REGISTRY RESTORE
         - Read area metadata from actual area JSON files (authoritative source)
         - Read module metadata from module_plot.json + module_context.json
         - Build world_registry.modules[<slug>] entry
         - Build world_registry.areas[<id>] entries for each area
         - Write to world_registry.json
         - DO NOT use ModuleStitcher.integrate_module() for this step
         |
         v
  [B5] REGISTRY VERIFICATION
         - scripts/homebrew_registry_guard.py --slug <slug> --verify-present --json
         - Must return present: true
         |
         v
      *** CONVERGE -> FINISHING + PUBLICATION (below) ***
```

### Why Not ModuleStitcher for Pre-Existing Modules

`ModuleStitcher.integrate_module()` (`core/generators/module_stitcher.py:517-580`):
- Creates backup directories on every run
- Can rename area IDs during conflict resolution
- Can rewrite module files during BU file updates
- Designed for first-time integration of freshly built modules

For modules that already exist on disk and simply fell out of the registry (drift), targeted registry restoration is safer. It adds only registry entries without touching module files.

The finisher's `_run_registry_stage()` (`web/extensions/toolkit_module_finisher.py:115-157`) currently falls back to `integrate_module()` when a module is not in the registry. For Mode B remediation, the targeted restore in step B4 should run first so the finisher finds the module already present and skips integration.

---

## Finishing + Publication (Both Modes Converge Here)

```
  [F1] CONTINUITY NORMALIZATION (if not already done)
         - web/extensions/toolkit_module_finisher.py -> _run_continuity_stage()
         |
         v
  [F2] SEMANTIC AUTHORITY ENRICHMENT (if not already done)
         - web/extensions/toolkit_module_finisher.py -> _run_semantic_authority_stage()
         |
         v
  [F3] REGISTRY VERIFICATION
         - web/extensions/toolkit_module_finisher.py -> _run_registry_stage()
         - If already present from Mode B step B4: passes immediately
         |
         v
  [F4] MONSTER MATERIALIZATION
         - scripts/homebrew_materialize_monsters.py --module <slug> --json
         - Resolves seed monster references to bestiary stat files
         - Degraded if unresolved (non-blocking for registry)
         |
         v
  [F5] PUBLISHABILITY AUDIT
         - scripts/audit_module_publishability.py
         - Reports: ready_status (structural) + publishable_status (semantic)
         |
         v
  [F6] REPORT
         - Writes toolkit_build_report.json to module directory
         - Overall status: success / degraded / failed
         - ready_status: pass / fail
         - publishable_status: pass / fail
```

### Finishing Outcomes

| ready_status | publishable_status | Result | Module Builder Visible? |
|-------------|-------------------|--------|------------------------|
| pass | pass | `completed` | Yes |
| pass | fail | `not_publishable` | Yes |
| fail | fail | `failed` | Yes (if registry restored) |

**Key insight:** Module Builder visibility requires only registry presence. Publishability is a separate quality gate. A module can appear in Module Builder (for portrait generation, inspection, etc.) even if it is `not_publishable`.

---

## Media Stages (Non-Blocking)

These stages run after core ingest/registry in Mode A. They are optional for Mode B.

```
  [M1] MEDIA EXTRACTION
         - Parse source markdown for image URLs
         - Download/copy to modules/<slug>/media/
         - Classify: title_image, map_image, handout
         - Fail-open: degraded on fetch failures
         |
         v
  [M2] MEDIA HANDLE MANIFEST
         - Generate media_handles.json
         - Deterministic handle IDs
         |
         v
  [M3] PORTRAIT PREWARM
         - Discover NPCs and monsters from module
         - Generate portraits with skip-if-exists
         - Fail-open on provider errors
```

**Missing images never block registration or builder visibility.**
- Registry verification happens before media stages
- Media stages are explicitly fail-open (degraded status)
- Finisher/publishability stack does not inspect portrait/media assets
- Module Builder reads only `world_registry.json` for its module list

---

## Tool Dependencies

**All scripts below already exist in the repo:**

| Script | Purpose |
|--------|---------|
| `scripts/homebrew_preflight.py` | Readiness assessment |
| `scripts/homebrew_transform_to_deterministic.py` | Structural conversion |
| `scripts/homebrew_ingest_dev.py` | Orchestrator with media stages |
| `scripts/homebrew_sidecar_audit.py` | Result validation |
| `scripts/homebrew_registry_guard.py` | Duplicate prevention, presence verification, safe removal |
| `scripts/homebrew_media_extract.py` | Media asset extraction |
| `scripts/homebrew_media_handles.py` | Handle manifest generation |
| `scripts/homebrew_prewarm_portraits.py` | NPC/monster portrait prewarm |
| `scripts/homebrew_materialize_monsters.py` | Monster stat file materialization |
| `scripts/audit_module_publishability.py` | Publishability audit |
| `scripts/audit_module_readiness.py` | Structural readiness audit |
| `scripts/module_semantic_authority_audit.py` | Semantic authority audit |
| `scripts/module_semantic_probe_harness.py` | Semantic probe harness |
| `scripts/module_continuity_audit.py` | Continuity contract audit |
| `scripts/continuity_cross_ref_enrichment.py` | Cross-module ref enrichment |
| `scripts/remediate_module_continuity.py` | Legacy continuity backfill |
| `scripts/validate_modules_bulk.py` | Bulk validation with publishability |

**Key runtime modules:**

| Module | Purpose |
|--------|---------|
| `core/importers/homebrewery_importer.py` | Deterministic ingest path |
| `core/generators/module_stitcher.py` | Registry integration (use cautiously) |
| `web/extensions/toolkit_module_finisher.py` | Post-build finishing orchestrator |
| `web/extensions/toolkit_homebrew_packet_builder.py` | GUI packet build |
| `web/extensions/toolkit_homebrew_readiness_gate.py` | GUI readiness gate |
| `utils/module_semantic_authority.py` | Semantic authority enrichment |
| `web/extensions/module_ingest_watch.py` | Optional filesystem watcher |

---

## Step-by-Step: Mode A (Source Ingest)

### Step A1: Preflight

```bash
.venv/bin/python scripts/homebrew_preflight.py <source_path> --json
```

### Step A2: LLM Normalization (if preflight returns `can_auto_transform: false`)

Normalization contract:
- MUST add required metadata: `title`, `author`, `description`
- MUST produce deterministic `## Room N: <name>` sections
- MUST include parseable `**Exits:**` bullets
- MUST preserve source names, locations, and encounter intent
- MUST NOT invent new mechanics, factions, or plot branches

### Step A3: Transform (if needed)

```bash
.venv/bin/python scripts/homebrew_transform_to_deterministic.py \
  --source <source_path> --output /tmp/prepared_<slug>.md
```

### Step A4: Dry-Run

```bash
.venv/bin/python scripts/homebrew_ingest_dev.py \
  --source /tmp/prepared_<slug>.md --strict --dry-run --json
```

### Step A5: Registry Guard

```bash
.venv/bin/python scripts/homebrew_registry_guard.py \
  --slug "<slug>" --check-duplicate --json
```

### Step A6: Strict Ingest

```bash
.venv/bin/python scripts/homebrew_ingest_dev.py \
  --source /tmp/prepared_<slug>.md --strict --json
```

Options:
- `--no-media-extract` - Skip media extraction and handle generation
- `--no-prewarm` - Skip portrait prewarm
- `--media-timeout <seconds>` - Timeout for media stage subprocesses (default: 30)
- `--allow-provider` - Enable AI portrait generation (costs money)

### Step A7-A8: Continuity + Semantic Authority

Handled automatically by the ingest pipeline. Verify in pipeline output:
- `continuity_contract.status` should be `success` or `warning`
- `semantic_authority.status` should be `success` or `degraded`

### Step A-Final: Run Finisher

```bash
.venv/bin/python -c "
from web.extensions.toolkit_module_finisher import run_toolkit_module_postbuild_finishing
import json
report = run_toolkit_module_postbuild_finishing('<slug>', strict=True)
print(json.dumps(report, indent=2))
"
```

---

## Step-by-Step: Mode B (Existing-Module Remediation)

### Step B1: Artifact Validation

```bash
# Check minimum required files exist
ls modules/<slug>/module_context.json
ls modules/<slug>/module_plot.json
ls modules/<slug>/areas/*.json
```

If `module_context.json` or `module_plot.json` is missing, the module is incomplete and cannot be remediated without further content work.

### Step B2: Registry Drift Check

```bash
.venv/bin/python scripts/homebrew_registry_guard.py \
  --slug "<slug>" --verify-present --json
```

If `present: true`, skip to Step B-Finish.

### Step B3: Collision Check

```python
# Check area IDs from module against existing registry
import json
from pathlib import Path

slug = "<slug>"
areas_dir = Path(f"modules/{slug}/areas")
area_ids = [f.stem for f in areas_dir.glob("*.json") if not f.name.endswith("_BU.json")]

with open("modules/world_registry.json") as f:
    reg = json.load(f)

for aid in area_ids:
    if aid in reg.get("areas", {}):
        existing_module = reg["areas"][aid].get("module")
        if existing_module != slug:
            print(f"COLLISION: {aid} already belongs to {existing_module}")
```

If collisions exist: HALT and decide whether this is a true duplicate or corruption.

### Step B4: Targeted Registry Restore

Build registry entries from actual module files. DO NOT call `ModuleStitcher.integrate_module()`.

Source values from:
- `module_plot.json` -> `mainObjective` (plotObjective), `plotPoints` (themes)
- Area files -> `areaName`, `areaType`, `dangerLevel`, `recommendedLevel`, `climate`, `terrain`, location count
- `module_context.json` -> `levelRange` if present, otherwise infer from area `recommendedLevel` min/max

Write to `world_registry.json`:
- `modules[<slug>]` with moduleName, addedDate, themes, plotObjective, levelRange, areaCount, startingLocation
- `areas[<area_id>]` for each non-BU area file with module=slug

### Step B5: Registry Verification

```bash
.venv/bin/python scripts/homebrew_registry_guard.py \
  --slug "<slug>" --verify-present --json
```

### Step B-Finish: Run Finisher

```bash
.venv/bin/python -c "
from web.extensions.toolkit_module_finisher import run_toolkit_module_postbuild_finishing
import json
report = run_toolkit_module_postbuild_finishing('<slug>', strict=True)
print(json.dumps(report, indent=2))
"
```

The finisher runs these stages in order:
1. Continuity normalization
2. Semantic authority enrichment
3. Registry verification (will pass since B4 already restored)
4. Monster materialization
5. Publishability audit

Report is written to `modules/<slug>/toolkit_build_report.json`.

---

## Stop Conditions

HALT and report immediately if:

1. **Canonical module missing after transform** - never overwrite existing registered modules
2. **Dry-run validation fails** (Mode A) - do not proceed to strict ingest
3. **Registry guard finds conflicts** - prevent duplicate/clone slugs
4. **Sidecar shows quarantine** (Mode A) - registration did not occur
5. **Continuity contract fails in strict mode** - missing required continuity keys
6. **Registry verification fails** - module not present after claimed success
7. **Area ID collision detected** (Mode B) - do not blindly overwrite
8. **Minimum artifacts missing** (Mode B) - module_context.json, module_plot.json, areas/
9. **File I/O error** - cannot read source or write files

**Continue with WARNING if:**
- Media extraction fails (degraded, not failed)
- Portrait generation fails (degraded, not failed)
- Media handles generation fails (degraded, not failed)
- Semantic authority enrichment degrades (non-blocking)
- Monster materialization has unresolved seeds (non-blocking for registry)
- Publishability audit fails (module is still visible in builder)

---

## Cleanup Guidance (on failure)

If ingest partially succeeds but registry verification fails:

```bash
# 1. Check sidecar for reason
cat modules/ingest/archive/*_<slug>.md.result.json

# 2. Remove bad module folder (if created by ingest)
rm -rf "modules/<slug>"

# 3. Remove from registry (if partially added)
.venv/bin/python scripts/homebrew_registry_guard.py --slug <slug> --remove --json

# 4. Re-run after fixing source
```

---

## Contract Alignment Notes

- Use `media_extraction` (not `media_extract`) in payloads and audits
- Legacy `media_extract` key is accepted with deprecation warning
- Media stages are fail-open (degraded status) while core ingest is fail-closed
- Use `.venv/bin/python` for all commands that touch runtime dependencies

Continuity contract requirements (`any-order-module-continuity-normalization`):
- `scripts/homebrew_ingest_dev.py` MUST emit `continuity_contract` in pipeline output and sidecar `result`
- `scripts/homebrew_ingest_dev.py` SHOULD backfill missing continuity v1 required keys before strict audit
- `scripts/homebrew_ingest_dev.py` SHOULD enrich `continuity.cross_module_refs` from module narrative hints before strict audit
- Strict profile MUST fail closed when required continuity keys are missing
- Alias ambiguity SHOULD remain warn-first unless strict alias policy is explicitly enabled
- `scripts/homebrew_sidecar_audit.py` MUST validate continuity payload shape when present

---

## Interpreter Rule

Use `.venv/bin/python` as the default interpreter for all ingest, finishing, validation, and remediation commands. This ensures runtime dependencies (`openai`, `flask`, `jsonschema`, provider clients) are available. Use bare `python` or `python3` only for clearly interpreter-agnostic operations.

Version: 3.0
Last Updated: 2026-04-13
