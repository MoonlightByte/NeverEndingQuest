# Module Spatial Prep Plan

## 1. Purpose

This plan prepares NeverEndingQuest modules for later v2 mapping work by adding the required spatial data contracts to the current module creation surfaces now.

The immediate goal is gameplay testing readiness:
- Homebrew ingest should emit richer spatial data for new imported modules.
- Toolkit builder should emit the same spatial data for newly built modules.
- Legacy modules should have a safe remediation path.

This is a module-data preparation plan, not a v2 runtime mapping implementation plan.

## 2. Relationship to Other Plans

**Relationship to `plans/version-2/mapping/*`:**
- The v2 mapping plans define future UI, renderer, and runtime payload behavior.
- This plan only prepares module artifacts so that future v2 map work has reliable source data to consume.

**Relationship to `plans/module-publication.md`:**
- `module-publication.md` still owns broader publication/readiness concerns.
- This plan narrows specifically to spatial authoring contracts needed at build/ingest time.

## 2.1 Current Status (2026-04-09)

This plan is **partially implemented**, but not complete enough to archive yet.

Implemented in the repo today:
- shared spatial contract helper exists (`utils/spatial_contract.py`)
- builder outputs now emit `coordinates`, `aliases`, `tactical_grid`, and map-room `directions`
- ingest outputs now emit the same contract shape
- remediation tooling can backfill the current spatial contract fields
- validator distinguishes strict new-output behavior from warn-first legacy behavior

Important gaps still open:
- **Ingest topology is still synthetic.** Current ingest spatial planning still starts from previous/next room ordering instead of true authored adjacency extracted from source semantics. This means ingest now emits the right field shape, but not yet a fully semantically grounded layout.
- **Validator coherence is still shallow.** Current validation checks field presence, map/area parity, and direction-key consistency, but it does not yet fail modules where connected rooms are mathematically too distant or otherwise spatially incoherent.

Practical conclusion:
- The OpenSpec change `tt-spatial-coordinate-grounding` is complete for its narrower contract-alignment scope.
- This broader plan remains active until semantic ingest adjacency and stronger spatial coherence validation are implemented.

## 3. Current Scope

This plan covers four spatial authoring outputs:
1. Semantic `coordinates`
2. Per-location `tactical_grid`
3. Per-location `aliases`
4. Explicit map-room `directions`

It applies to:
- `core/importers/homebrewery_importer.py`
- `core/generators/area_generator.py`
- `core/generators/location_generator.py`
- `core/validation/validate_module_files.py`
- new remediation tooling for legacy modules

## 4. Non-Goals

This plan does **not** implement:
- v2 map UI tabs or renderers
- local/module/world runtime map payload services
- `memory.db` worldview graph work
- combat map overlays
- runtime movement-validator redesign

This plan only ensures the module files produced today are ready for those later phases.

## 5. Spatial Authoring Contract

### 5.1 Location and Area Data

Every newly built or newly ingested location should emit:

1. **`coordinates`**
- Format remains `X#Y#`.
- Coordinates must be semantically grounded in the prose and connectivity.
- Naive linear placement like `X0Y0`, `X1Y0`, `X2Y0` is not acceptable for new outputs unless the prose truly describes a linear sequence.

2. **`tactical_grid`**
- Exactly 9 short strings representing the environment stage.
- Ordering remains the 3x3 stage: `NW, N, NE, W, C, E, SW, S, SE`.
- Contains terrain, furniture, hazards, cover, or empty-space descriptors only.
- Must not contain actors, monsters, or NPC names.

3. **`aliases`**
- Array of natural-language alternate references for the location.
- Should include room-title variants and obvious prose-derived references.
- Supports later deterministic travel matching without runtime guessing.

### 5.2 Map Data

Every newly built or newly ingested `map_<AREA>.json` should emit:

1. **Explicit `directions`**
- Cardinal directions only for this phase: `north`, `south`, `east`, `west`.
- Derived from semantic adjacency, not arbitrary ordering.
- Vertical travel (`up`, `down`) is out of scope for this prep phase.

2. **Layout parity**
- `layout`, map rooms, and area/location coordinates must agree.
- Connected rooms should be spatially near each other unless the narrative clearly implies otherwise.

## 6. Validation Mode

Two validation modes are needed:

1. **New build / new ingest outputs**
- Treated as strict spatial-contract producers.
- Missing required spatial fields should fail the builder/ingest readiness path.

2. **Legacy modules**
- Warn-first until backfilled.
- Existing gameplay must remain functional while remediation is in progress.

## 7. Implementation Surfaces

### Phase 1: Schema and Validator Tightening

**Targets:**
- `schemas/loca_schema.json`
- `schemas/locationfile_schema.json`
- `schemas/map_schema.json`
- `core/validation/validate_module_files.py`

**Work:**
- Add `tactical_grid` and `aliases` where missing.
- Tighten `directions` expectations for new outputs.
- Add spatial coherence checks that compare connectivity to emitted coordinates.
- Keep legacy handling warn-first while making new generation paths strict.

**Status (2026-04-09):**
- Completed: schema alignment, strict-vs-legacy validator split, direction presence checks, map/area parity checks.
- Remaining: true spatial coherence validation for adjacency distance and broken local-grid geometry.

### Phase 2: Toolkit Builder Parity

**Targets:**
- `core/generators/area_generator.py`
- `core/generators/location_generator.py`

**Work:**
- Ensure builder-generated rooms use semantic coordinates rather than arbitrary placement.
- Emit explicit `directions` from those coordinates.
- Require `tactical_grid` and `aliases` in location generation output.
- Keep the contract aligned with ingest so both pipelines produce the same artifact shape.

**Status (2026-04-09):**
- Completed for current scope. Builder now emits the shared spatial contract shape through the shared helper and location post-processing.

### Phase 3: Homebrew Ingest Parity

**Target:**
- `core/importers/homebrewery_importer.py`

**Work:**
- Replace the current naive linear coordinate emission with a semantic spatial resolution pass.
- Emit `tactical_grid` and `aliases` during artifact generation.
- Emit `directions` in `map_<AREA>.json` from the resolved spatial layout.

**Status (2026-04-09):**
- Partially completed. Ingest now emits the richer spatial contract and uses the shared spatial helper.
- Remaining: replace the current sequential previous/next ingest connectivity scaffold with true authored adjacency extraction so semantic spatial resolution is grounded in source structure instead of source order alone.

### Phase 4: Legacy Remediation Tooling

**Target:**
- `scripts/remediate_module_coordinates.py`

**Work:**
- Expand the remediation concept so it can backfill:
  - `coordinates`
  - `tactical_grid`
  - `aliases`
  - `directions`
  - layout parity where needed
- Support `--dry-run` and `--apply`.
- Preserve authored connectivity and other unrelated content.

**Status (2026-04-09):**
- Completed for current scope. Remediation preserves authored connectivity while backfilling the new spatial contract fields.

### Phase 5: Gameplay-Testing Verification

**Work:**
- Verify newly ingested modules can be used for gameplay testing without spatial-contract warnings.
- Verify newly built toolkit modules emit the same spatial structure as ingested modules.
- Confirm runtime gameplay still works when a legacy module has not yet been remediated.

**Status (2026-04-09):**
- Completed for the narrower OpenSpec slice.
- Not yet sufficient to close this broader plan because the remaining ingest-topology and validator-coherence gaps still need repo-level implementation.

## 8. Path Ahead

To finish this plan and make it archive-ready, the next work should be:

1. **Authored adjacency extraction for ingest**
- Replace previous/next room scaffolding with deterministic extraction of exits, cross-links, stairs, wings, and room references from the imported source text.
- Feed that adjacency graph into `resolve_semantic_spatial_plan(...)` so ingest coordinates are grounded in authored room relationships.

2. **Spatial coherence validator upgrade**
- Add an explicit geometric coherence check in `validate_module_files.py`.
- Fail strict new-output modules when connected rooms are implausibly distant, disconnected from their declared directions, or otherwise violate local-grid expectations.
- Keep legacy behavior warn-first until remediated.

3. **Targeted ingest regressions**
- Add importer tests proving non-linear source structures produce non-linear connectivity and coordinates.
- Add validator tests proving incoherent strict outputs fail while legacy modules remain warnings-only.

4. **Then archive this plan**
- Once those two missing implementation slices are complete, this plan should be considered fulfilled and can be archived.

## 9. Success Criteria

This plan is complete when:

1. New Homebrew ingests emit semantic `coordinates`, `tactical_grid`, `aliases`, and explicit cardinal `directions`.
2. New Toolkit-built modules emit the same fields with the same contract shape.
3. Validator behavior is strict for new outputs and warn-first for legacy modules.
4. Legacy remediation tooling can safely backfill missing spatial data without disturbing authored connectivity.
5. Modules produced during current gameplay-testing rounds are spatially ready for later v2 mapping work, without requiring the v2 runtime/UI to exist yet.

## 10. Archive Gate

This plan should **not** be archived yet.

Archive only when:
- ingest adjacency is no longer synthesized from source order alone
- strict spatial coherence validation exists beyond field-presence checks
- targeted regressions cover both behaviors
