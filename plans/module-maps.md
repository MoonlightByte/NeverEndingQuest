# Module Mapping & Spatial Foundation Plan

## 1. Overview & Relationship to Publication

This plan details the implementation of spatial data contracts across both the Homebrew Ingest and Toolkit Builder pipelines to support the v2 grid features (Local Sensory Grid, Combat Threat Radar, Regional Macro Grid).

**Relationship to `module-publication.md`:**
This plan extracts and expands the "Spatial Coordinate Semantic Grounding" section from the publication plan. 
- **This Plan (`module-maps.md`)** owns: `coordinates`, `tactical_grid`, spatial connectivity, map schemas, explicit `directions`, and room `aliases`.
- **`module-publication.md`** retains: NPC scene-authority, semantic travel validation rules, and synthetic play-testing probes (the "is this narrative safe to play?" checks).

## 2. The Spatial Contract

To support the v2 grid features, every module MUST emit the following data at build/ingest time:

### 2.1 Per-Location Requirements (Areas JSON)
1. **`coordinates` (Semantic):** Must reflect actual relative placement based on the prose (e.g., if Room B is North of Room A at X1Y1, Room B must be X1Y0). Naive linear `X0Y0, X1Y0` generation is deprecated.
2. **`tactical_grid`:** An array of exactly 9 short strings representing the 3x3 combat stage (`["NW", "N", "NE", "W", "C", "E", "SW", "S", "SE"]`). Must contain environmental features/terrain only (no actors).
3. **`aliases`:** Array of natural-language names (e.g., `["The Cellar", "Basement", "Beneath the Inn"]`) to ensure deterministic travel resolution without runtime guesswork.

### 2.2 Map & Region Requirements (Map JSON & Registry)
1. **`directions`:** In `map_<AREA>.json`, an explicit mapping of cardinal directions to connected room IDs (e.g., `{"north": "A02", "east": "A03"}`).
2. **Regional Metadata:** Modules must consistently register their `startingLocation`, `levelRange`, `travelNarration`, and primary `areaType` (terrain) to support the macro world map horizon.

---

## 3. Implementation Phases

### Phase 1: Schema & Validator Upgrades
* **Target:** `schemas/loca_schema.json`, `schemas/map_schema.json`, `schemas/locationfile_schema.json`
* **Action:** Add `tactical_grid` (9-element string array), `aliases` (string array), and `directions` (key-value strings) to the schemas.
* **Target:** `core/validation/validate_module_files.py`
* **Action:** Enforce structural presence of these fields. (Implement as warn-first for legacy modules, strict for new builds/ingests).

### Phase 2: Toolkit Builder Parity
* **Target:** `core/generators/location_generator.py`
* **Action:** Update the LLM prompt to require `tactical_grid` generation (environmental features only) and `aliases` extraction during room generation.
* **Target:** `core/generators/map_generator.py`
* **Action:** Update the LLM prompt to generate semantic `coordinates` and explicit `directions` based on the narrative layout, abandoning arbitrary linear placement.

### Phase 3: Homebrew Ingest Upgrades
* **Target:** `core/importers/homebrewery_importer.py`
* **Action:** Replace the naive linear coordinate loop with an LLM-assisted spatial resolution pass (`_resolve_spatial_layout`).
* **Action:** Add an LLM extraction pass to generate the `tactical_grid` and `aliases` for each parsed room block before final NEQ artifact emission.

### Phase 4: Legacy Remediation (Backfill)
* **Target:** `scripts/remediate_module_coordinates.py` (New Script)
* **Action:** Create a developer tool that reads existing `areas/*.json` files, prompts the LLM to analyze the prose descriptions, and safely backfills missing `tactical_grid`, `aliases`, explicit `directions`, and semantic `coordinates`.

---

## 4. Success Criteria
- A newly built Toolkit module has 9-zone tactical grids and aliases in every location.
- A newly ingested Homebrew `.md` module produces non-linear, narrative-accurate X/Y coordinates.
- The `validate_module_files.py` script passes these new modules with 0 spatial warnings.
- The data foundation is 100% ready for the UI/UX features defined in `dm-local-grid.md` and `dm-combat-grid.md` to be built on top.
