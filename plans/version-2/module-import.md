# Module Import and World Expansion Plan

## Status

- Lifecycle state: Planning in progress
- Pre-v2 precursor: `plans/module-uploader.md` defines the interactive reviewed upload path that should complete before this plan expands into full v2 import scope
- Default world mode: Canonical
- Forking mode: Supported in architecture, disabled by default
- Continuity baseline: Initial build implemented (ingest/readiness/sidecar/bulk contracts)
- V2 narrative track reference: `plans/version-2/v2-narrative-track.md`
- Encounter escalation reference: `plans/version-2/encounterEscalationProfile.md`

## Current Baseline

The first continuity normalization build is now in place and should be treated as the default contract for future module ingest work.

The next practical milestone is not bulk import first. It is completing the public interactive uploader so NEQ has one reviewed, artifact-persisted, LLM-assisted import path for player-authored and Homebrewery markdown adventures.

That uploader should be treated as the end of the first pre-v2 phase of module import:

1. it proves the raw prose -> normalized packet -> reviewed build -> validated module loop,
2. it establishes the canonical markdown normalization contract,
3. it establishes the review/quarantine boundary,
4. it establishes artifact persistence and rebuild semantics,
5. it becomes the markdown-side precursor for this broader v2 import plan.

Operational baseline:

1. Ingest emits continuity metadata:
   - `continuity_contract` is produced during ingest and persisted to sidecar results.

2. Strict vs warn-first behavior is standardized:
   - strict mode fails closed when required continuity keys are missing.
   - warn-first mode allows degraded pass with explicit warnings (for example alias ambiguity).

3. Validation pipeline includes continuity gate:
   - per-module continuity audit,
   - readiness gate integration,
   - bulk validator continuity reporting with summary counts.

4. Skill/workflow alignment is in place:
   - developer ingest workflow and module readiness workflow now both include continuity checks.

Required continuity keys for v1 contract:
- `continuity_version`
- `entry_state_variants`
- `cross_module_refs`
- `standalone_fallback`

This is the bridge layer for any-order module play and should be considered mandatory in all new ingest planning.

## Next Milestone

Extend continuity-normalized ingest from current modules to all new imported modules with strict-ready publish defaults.

## Exit Criteria

- Import pipeline emits continuity-complete module payloads by default.
- Strict continuity gate is green for release-target module imports.
- Bulk validation summaries report continuity pass/degraded/fail deterministically.

## Goal

Build a strict, continuous import pipeline that ingests large volumes of community adventure content (DMsGuild free purchases, Homebrewery markdown, and local map packs), converts it into NEQ-compatible modules, validates those modules, and stitches them into one long-lived canonical world campaign.

The canonical world should be large enough to support long party progression without repetition fatigue, while still allowing future optional campaign-level forks ("many worlds") that remix module order and world mapping without duplicating module assets.

This plan begins after the interactive uploader has established the single-source reviewed import lane. V2 import then generalizes and scales that lane into high-volume intake, canonicalization, and world-expansion operations.

## Relationship To The Public Uploader

`plans/module-uploader.md` and this plan are intentionally sequential, not competing.

The relationship is:

1. `plans/module-uploader.md`
   - owns the public reviewed upload flow,
   - owns the single-source markdown import experience,
   - owns mandatory review before registry integration,
   - owns the first source-preserving normalized packet contract.

2. `plans/version-2/module-import.md`
   - builds on the uploader contracts,
   - expands from one-source reviewed import to many-source import operations,
   - introduces bulk inventory scanning and incremental rebuilds,
   - adds canonical world-scale stitching and progression ladders,
   - becomes the higher-volume operational layer for the same family of ingest/build contracts.

Short version:

- uploader = interactive reviewed import
- module-import = scaled canonical import

## Import Modes

This plan should explicitly support two modes.

### Mode A: Interactive Reviewed Import

Purpose:

- player/developer uploads one adventure source and reviews it before apply.

Characteristics:

1. single source at a time,
2. source-preserving local artifacts are allowed,
3. explicit approve/reject gate,
4. toolkit GUI first,
5. registry integration happens only after review and validation.

Primary owner:

- `plans/module-uploader.md`

### Mode B: Bulk Canonical Import

Purpose:

- scan and process many sources into the canonical module pool.

Characteristics:

1. inventory-driven,
2. incremental and scheduled operation,
3. batch quarantine behavior,
4. may reuse the same normalization and build contracts,
5. optimized for throughput and canonical world expansion.

Primary owner:

- this plan (`plans/version-2/module-import.md`)

## Product Direction

1. Canonical first:
   - Every import contributes to one shared worldline by default.
   - New campaigns start in this canonical world unless the user explicitly selects a fork profile in a future release.

2. Strict quality gate:
   - Only schema-valid, integrity-valid modules are auto-published into world stitching.
   - Degraded imports are quarantined for review and never silently stitched.

3. Throughput at scale:
   - Bulk ingest is expected and desired.
   - The system is built for continuous intake from fan resources over time.

4. World consistency over source fidelity:
   - Imported adventures are adapted into a cohesive NEQ world.
   - We do not require strict textual fidelity to source PDFs/markdown.

## Why This Fits NeverEndingQuest

- "NeverEnding" content means sustained expansion, not fixed module packs.
- The repo already contains core building blocks for ingestion, world narrative memory, module validation, and module stitching.
- The main missing piece is a robust orchestrator that turns raw source files into validated modules continuously.

## Scope

In scope:

- Extension of the uploader's normalization/build contracts into bulk import operation
- Bulk source discovery from local staging folders and Homebrewery markdown files
- Automated extraction, normalization, conversion, validation, and stitching
- Level-band campaign ladder generation (for party progression)
- Canonical worldline updates as new modules are imported
- Strict autopublish policy

Out of scope (for initial implementation):

- Full OCR recovery for image-only scans with perfect accuracy
- Human-authored editorial rewrite UI
- Runtime multi-tenant world switching in the player UI

## Source Inputs

Supported source types:

- PDF adventures (`.pdf`)
- Markdown adventures (`.md`, especially Homebrewery exports)
- Asset packs (`.zip`) containing maps/handouts

Staging approach:

- Local intake root remains the source of truth for raw files.
- Raw source files are considered import inputs, not runtime gameplay artifacts.

## Source Rights And Provenance Classification

This plan should explicitly distinguish source classes because later integration with world-narrative depends on it.

Recommended classes:

1. `user_authored`
   - player-created or project-owned raw adventure content,
   - source-preserving normalized packets and module artifacts are acceptable in local workflow,
   - can proceed through reviewed module publication flow.

2. `licensed_or_project_owned`
   - approved internal content or content with rights permitting module conversion,
   - may follow the same module import lane with policy-appropriate review.

3. `third_party_copyright_restricted`
   - locally processed source material whose raw identifying content must not enter committable derived outputs,
   - may still inform future source-anonymous narrative abstractions,
   - must not be treated as ordinary source-preserving module import by default.

Architectural rule:

- This module-import plan primarily targets `user_authored` and approved `licensed_or_project_owned` module sources.
- Future bridges into `plans/version-2/world-narrative.md` must respect its stronger source-anonymous firewall for `third_party_copyright_restricted` material.

## Canonical Pipeline Architecture

### Stage 1: Intake and Inventory

Create a bulk scanner that:

- Walks configured roots (for example `Docs/modules/` and Homebrewery drop folders)
- Classifies each file by type
- Computes file hashes for dedupe
- Creates/updates `import_inventory.json` (or DB table) with provenance and status

Output:

- Deterministic inventory rows keyed by content hash

### Stage 2: Extract

Use per-format extractors:

- PDF extractor: text chunk extraction with page spans
- MD extractor: heading-aware parsing for sections, encounters, hooks, and level hints, building on the normalized packet contract proven by `plans/module-uploader.md`
- ZIP extractor: map/media expansion into normalized media staging

Output:

- Structured extraction payloads and manifests per source

### Stage 3: Normalize to Intermediate Adventure Schema

Convert extracted payloads into one canonical intermediate format (per source):

- `source_id`, `title_slug`, `estimated_level_range`
- `acts` and `quest_arcs`
- `locations`
- `npcs`
- `encounter_seeds`
- `loot_and_rewards`
- `travel_hooks`

This schema is not runtime gameplay data. It is conversion-grade data for module generation.

For markdown sources, the first practical implementation of this stage should be the uploader's normalized packet contract. V2 import should refine and generalize that contract rather than inventing a separate markdown normalization model.

### Stage 4: World Consistency Rewrite (Canonical Worldline)

Apply consistency policies from `plans/version-2/world-narrative.md`:

- Normalize recurring factions and place names
- Merge equivalent NPC identities
- Resolve timeline conflicts into canonical chronology
- Enforce mechanical truth boundaries where needed
- Prefer adaptation for coherence over literal source fidelity

Output:

- Canonicalized intermediate adventure package ready for NEQ module emission

Boundary note:

- This module-import rewrite stage is about canonical module cohesion and world placement.
- It is not the same as the source-anonymous narrative atom pipeline in `plans/version-2/world-narrative.md`.
- The world-narrative plan remains the later interpreted-state lane for narrative web, anonymized literary inspiration, and Titan-facing pressure systems.

### Stage 5: Emit NEQ Modules

Generate module folder artifacts compatible with NEQ expectations:

- areas
- encounters
- characters/NPCs
- monsters
- module plot data
- media references

Module naming convention should avoid collisions and remain deterministic.

### Stage 6: Strict Validation Gate

Run:

```bash
.venv/bin/python core/validation/validate_module_files.py
```

Publish policy:

- PASS: module enters canonical stitch queue
- FAIL: module enters quarantine queue with machine-readable error report
- No silent bypass on validator errors

### Stage 7: Stitch and Level Ladder Update

Integrate passing modules into world registry via module stitcher behavior:

- Register module metadata and area metadata
- Preserve isolated module structure
- Add narrative transition hooks
- Recompute campaign progression ladders based on level range bands

Output:

- Updated canonical world registry and progression index

## Canonical World Campaign Design

The canonical world should remain broad and non-repetitive as the source corpus grows.

Design rules:

1. Maintain content diversity per level band:
   - Mix dungeon, city intrigue, wilderness, mystery, political, and horror motifs.

2. Ensure progression overlap:
   - Adjacent level bands should overlap (`1-4`, `3-6`, `5-8`, `7-10`, etc.) so campaign routing remains flexible.

3. Track novelty pressure:
   - Avoid repeating very similar motifs in adjacent suggested modules.

4. Preserve multiple branch options:
   - Each level band should present multiple viable next-module candidates.

5. Keep travel narrative coherent:
   - Stitch transitions should read as world travel, not teleporting disconnected one-shots.

## Campaign Initialization Behavior

Default behavior (required):

- New campaign initializes in the canonical world.
- It reuses the shared validated module pool.
- Module availability and ordering derive from the canonical registry and progression ladder.

Result:

- Every new campaign benefits from ongoing imports and world improvements.

## Future: Many Worlds Forking (Potential)

Forking should be supported as an optional extension, not default behavior.

### Concept

"Many worlds" means alternate campaign mappings over the same validated module asset pool.

- Canonical world:
  - Single shared progression and continuity map
- Forked world profile:
  - Alternative progression graph, faction alignments, and transition logic
- Shared module files:
  - No duplication of core module artifacts required

### Why This Matters

- Different tables can experience distinct campaign arcs
- Experimental mappings can be tested without destabilizing canonical continuity
- Supports replayability with minimal asset duplication

### Minimal Fork Architecture

Add campaign profile overlays:

- `campaign_profiles/<profile_id>/world_registry_overlay.json`
- `campaign_profiles/<profile_id>/progression_rules.json`
- Optional `campaign_profiles/<profile_id>/world_model_delta.json`

At campaign init:

- Default to canonical profile
- Optional explicit profile selection enables forked mapping

### Safety Rules for Forking

- Fork overlays cannot mutate canonical module source artifacts
- Fork overlays must pass schema and consistency checks
- Canonical remains authoritative fallback

## Operational Modes

1. Scheduled continuous build:
   - Daily or hourly intake run over staging roots

2. Manual bulk run:
   - One command for large corpus import/rebuild

3. Incremental run:
   - Process only new/changed hashes since last successful run

## Data Contracts

Required metadata per import source:

- `source_hash`
- `source_type`
- `ingest_timestamp`
- `extract_status`
- `normalize_status`
- `module_emit_status`
- `validation_status`
- `stitch_status`
- `quarantine_reason` (if any)

Required metadata per emitted module:

- `module_slug`
- `origin_source_ids`
- `level_range_min`
- `level_range_max`
- `theme_tags`
- `canonicalization_version`
- `validation_report_ref`

## Validation and Quality Gates

Hard gates:

- Module schema validation must pass
- Cross-reference integrity checks must pass
- Level range must be present and valid
- Encounter and creature references must resolve
- No malformed area/location graph structures

Soft scoring (for ranking only, not publication):

- Narrative coherence score
- Novelty score versus nearby level-band modules
- Transition quality score for stitch edges

## Failure Handling

Fail-closed for publication:

- If validation fails, module is quarantined.
- If stitching fails, module remains unstitched and flagged.

Fail-open for intake progress:

- One bad source file must not stop the entire batch.
- Batch continues and reports per-source failures.

## Suggested Commands (Target UX)

```bash
# Full continuous import pass
python scripts/import_modules_bulk.py --strict --canonical

# Incremental pass only
python scripts/import_modules_bulk.py --strict --canonical --incremental

# Recompute progression ladder after manual edits
python scripts/rebuild_progression_index.py --canonical
```

## Metrics to Track

Pipeline metrics:

- Sources scanned
- Sources extracted
- Modules emitted
- Validation pass rate
- Quarantine rate
- Stitch success rate

World metrics:

- Modules per level band
- Distinct theme coverage per level band
- Average branching factor of progression graph
- Repeat-motif adjacency rate

## Implementation Phases

Phase 0: Interactive uploader completion (pre-v2 dependency)

- Complete `plans/module-uploader.md`
- Lock normalized packet, review, artifact, and rebuild contracts
- Use real Homebrewery corpus as regression fixtures

Phase 1: Bulk intake foundation

- Build inventory scanner
- Add markdown extractor path using uploader-proven normalization contracts where possible
- Add ZIP media unpack normalization

Phase 2: Intermediate schema + emitter

- Define canonical adventure intermediate schema
- Build converters from extract payloads and uploader-normalized packets
- Emit NEQ module drafts

Phase 3: Strict validation + quarantine

- Enforce strict publication gate
- Persist per-module validation reports

Phase 4: Canonical stitch + progression ladder

- Auto-stitch validated modules
- Build and publish level-band progression graph

Phase 5: Continuous operations

- Scheduled incremental imports
- Metrics dashboard/reporting

Phase 6: Many-worlds fork overlays (optional)

- Add profile overlay schema
- Campaign init profile selection (canonical default)
- Overlay validation and rollback

## Non-Negotiable Defaults

- Canonical world is default for all new campaigns.
- Strict validation is required for autopublish.
- Module pool is shared and continuously expanded.
- Forking is optional and additive, not a replacement for canonical.

## Expected Outcome

With strict continuous import active, NEQ evolves into a living campaign platform where:

- New fan adventures can be absorbed regularly.
- Parties can progress through a deep, varied, linked module ecosystem.
- The canonical world remains coherent and scalable.
- Future many-world forks remain possible without fragmenting core assets.

This expected outcome assumes a continuity chain:

1. uploader completes the interactive reviewed import lane,
2. v2 module-import scales that lane into bulk canonical operations,
3. world-narrative later adds source-anonymous narrative web and world-pressure interpretation,
4. Titan integration later consumes those interpreted narrative structures without owning the module import path itself.
