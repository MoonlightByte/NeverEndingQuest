# Module Publication Plan

## Problem

Current ingest and readiness tooling can produce modules that are structurally valid but not safely publishable for live play.

Today the pipeline mostly validates:
- source shape and metadata
- schema compliance
- monster/reference parity
- continuity metadata
- sidecar/registry state

It does not yet guarantee semantic runtime completeness.

That gap is why modules can pass validation while still failing at the table when players use natural language such as:
- "take us to Lintar's place"
- "bring Father Aldric to Brother Lintar"
- "we return to the priest's lodging"

These failures should be caught before publication, not discovered through manual bug testing across dozens of adventures.

## Root Cause

The current pipeline does not enforce a publishability standard for:
- named destination resolution
- hidden/revealable NPC authority
- natural-language room and destination aliases
- runtime-safe semantic travel validation

In practice:
- a location may exist topologically but lack canonical player-facing aliases
- an NPC may exist in hooks or seed data but not in scene-authority records
- prose may mention a destination or refuge that is not mapped to any canonical location ID
- readiness may return pass even though runtime DM play will still guess incorrectly

## Example: Night of the Restless Dead

Observed issue:
- Father Aldric is authored in location hooks and can be surfaced at runtime
- Brother Lintar / Lintar's place is referenced conceptually in play but is not canonically authored as a resolvable destination in the module
- the runtime therefore guesses a valid graph destination instead of the intended authored destination
- validation passes because the move is topologically legal, even though semantically wrong

This is not just a one-off module defect. It exposes a publication-gap in the pipeline.

## Goal

Define a stronger module-publication workflow so a module is only publishable when it is:
- structurally valid
- reference complete
- semantically grounded for runtime play
- safe for natural-language travel and NPC interactions

## Current Status (2026-04-09)

This plan remains **active future work**.

Adjacent work that is now in place:
- narrower structural/readiness and toolkit/ingest parity slices have landed
- spatial contract preparation exists through `tt-spatial-coordinate-grounding`
- some scene-authority and location-exclusivity groundwork now exists in narrower changes

But the full publication workflow described here is still **not** implemented:
- there is no dedicated `publishable` gate distinct from `ready`
- there is no full deterministic destination phrase map built during publication
- there is no complete NPC scene-authority map for all visible and revealable NPCs
- there is no synthetic gameplay probe suite enforcing publication-time semantics
- there is no single semantic publication audit that hard-fails unsafe modules before release

Conclusion:
- completed narrower changes should not be treated as completion of this full plan
- this plan should not be archived yet

## Publication Standard

A module should be considered publishable only if all of the following are true:

1. Schema-valid
- All module files pass validation.

2. Reference-complete
- Monster references resolve.
- Required authored data exists.
- Runtime hydration does not depend on guesswork.

3. Semantic destination-complete
- Every authored named refuge, hall, abode, camp, shrine, chapel, inn, lodge, watchtower, etc. either:
  - maps to exactly one canonical location ID, or
  - fails publication.

4. NPC authority-complete
- Every visible NPC and every hidden/revealable NPC has a canonical scene-authority path.
- If the module allows the NPC to be discovered in a location, runtime must be able to validate and move that NPC deterministically.

5. Natural-language alias-complete
- Common destination and room aliases are deterministic.
- Stripped room titles, authored location nicknames, and key named destinations resolve safely.

6. Probe-safe for live play
- Deterministic test prompts for travel, discovery, and NPC escort behavior resolve to the expected authored targets.

## Required Pipeline Changes

### 1. Add Semantic Enrichment During Ingest

Ingest should build a deterministic semantic layer, not just emit baseline JSON files.

New enrichment outputs should include:
- location alias map
- destination phrase map
- npc scene-authority map
- hidden/revealable NPC bindings
- authored destination mentions resolved to canonical location IDs

Examples:
- "Priest's Lodging" -> `NIG04`
- "Lintar's place" -> intended location ID
- `Father Aldric` -> scene authority at `NIG04`

This enrichment must be deterministic and traceable.

**Status (2026-04-09):**
- Not implemented as a full publication layer.
- Some supporting pieces exist, but there is still no deterministic destination phrase map or full NPC authority enrichment pass during publication.

### 2. Add Publishability Semantic Audit

A new audit phase should fail publication when:
- a named destination is mentioned in authored content but cannot resolve uniquely
- a hidden/revealable NPC can appear in scene but lacks canonical authority mapping
- a likely player phrase could resolve to the wrong valid location
- runtime would need to guess instead of apply deterministic module truth

**Status (2026-04-09):**
- Not implemented.
- Current validation remains a combination of structural checks and narrower semantic slices, not the full publishability audit described here.

### 3. Add Probe-Based Validation

Publication auditing should run synthetic gameplay probes against authored module semantics.

Examples:
- "take us to Lintar's place"
- "return to the priest's lodging"
- "bring Father Aldric to Brother Lintar"
- "show us the hidden priest"

Expected result:
- each probe resolves to one canonical authored target
- ambiguity or drift blocks publication

**Status (2026-04-09):**
- Not implemented.
- No publication-time synthetic gameplay probe harness currently enforces these cases.

### 4. Upgrade Readiness -> Publishability

Current readiness pass is not enough.

We need two levels:
- `ready`: structurally valid
- `publishable`: structurally valid + semantically safe for runtime play

A module should not be released to testers or players unless it passes `publishable`.

**Status (2026-04-09):**
- Not implemented.
- The repo still lacks a formal `publishable` result distinct from current readiness/validation passes.

## Policy Recommendation

Unresolved semantic references should hard-fail publication.

Recommended policy:
- if a destination like "Brother Lintar's place" is not canonically resolvable, publication fails
- do not silently guess
- do not rely on runtime heuristics to save missing authored structure

Rationale:
- matches the requirement that validated modules should be publishable
- scales better than manual bug testing across 50+ adventures
- forces missing semantics to be fixed once in the pipeline rather than repeatedly in runtime patches

## Proposed OpenSpec Change

Suggested change name:
- `module-publishability-semantic-readiness`

Suggested scope:
- deterministic destination alias extraction
- hidden/revealable NPC authority enrichment
- semantic publishability audit
- readiness gate upgrade from pass to publishable
- synthetic probe coverage for live-play travel/NPC semantics

## Expected Outcome

After this work:
- modules that pass publication validation should be safe to ship
- destination and NPC authority bugs should be caught during ingest/readiness
- runtime should stop carrying the burden of repairing missing authored semantics
- manual bug testing should become confirmation, not discovery

## Findings From Current Spatial Review

1. **Spatial contract shape now exists**
- builder and ingest now emit `coordinates`, `aliases`, `tactical_grid`, and `directions`
- remediation and validator support exist for that narrower spatial slice

2. **But publication-grade semantics still do not**
- ingest topology is still partly synthetic rather than fully authored-semantic
- validator coherence still does not enforce the stronger spatial publishability audit described below
- broader destination/NPC publication semantics remain outside completed slices

3. **This plan therefore stays open**
- `tt-spatial-coordinate-grounding` can be archived independently
- this larger publication plan cannot

## Spatial Coordinate Semantic Grounding (DM Local Grid Support)

### Problem
To fully enable the 3x3 phenomenological "DM Local Grid", modules must possess semantically accurate `X#Y#` coordinates where connected rooms are physically adjacent in coordinate space, and their relative placement (North, South, East, West) matches the narrative descriptions. Currently:
- **New Ingests:** `homebrewery_importer.py` creates naive, linear maps (`X0Y0`, `X1Y0`...) ignoring text descriptions.
- **Legacy Modules:** Coordinates are manually authored (often conflicting with text) or missing entirely.

### 1. Ingest Pipeline Upgrade (New Modules)
Add a "Spatial Resolution Pass" to the `core/importers/homebrewery_importer.py` pipeline.
- **LLM Spatial Inference:** After room extraction, invoke an LLM cartographer (`_resolve_spatial_layout()`).
- **Prompt Logic:** "Analyze these rooms for directional cues (north, stairs down, east wing) and logical adjacency. Output a JSON map assigning a relative X,Y coordinate to each room, starting at X10Y10 for the entrance. Ensure North is Y-1, South is Y+1, East is X+1, and West is X-1."
- **Pipeline Integration:** Replace the linear logic in `_emit_map_file()`. Emit these semantically grounded coordinates in both `areas/<AREA>.json` and `map_<AREA>.json`.

**Status (2026-04-09):**
- Partially implemented.
- New ingest outputs now emit the spatial contract fields, but ingest still derives base topology from source ordering in places rather than from full authored semantic adjacency extraction.

### 2. Backfill Tooling (Legacy Modules)
Create targeted developer remediation tooling for existing modules.
- **New Script:** `scripts/remediate_module_coordinates.py`
- **Read & Extract:** Read an area file, extract the `locations` array, preserving exact `connectivity` and `description` text.
- **LLM Reconciliation:** Prompt the LLM: "Here is an existing map with fixed connections. Read the descriptions and assign an X,Y coordinate to each room starting at X10Y10. Ensure connected rooms are placed as close to adjacent as possible in the grid, strictly respecting any directional words (North, South) mentioned in the text."
- **Safe Write:** Safely update the `coordinates` key for every location in the `areas/` JSON and rebuild the layout array in the `map_/` JSON. Support `--dry-run` and `--apply` flags.

**Status (2026-04-09):**
- Implemented for the current spatial contract slice.

### 3. Alignment with Publication Standards
This solves semantic grounding issues for spatial movement:
- **Semantic Reality:** Ensures coordinates match the prose. When a player says "We head North through the door", the Python travel validator (using the 3x3 local grid) naturally aligns with the authored reality of the module.
- **Publishability Audit:** Add a "Spatial Coherence" check to the readiness validator (`validate_module_files.py`). A module fails publication if connected rooms are mathematically distant (e.g., connected but >2 coordinate steps away) without a narrative justification (like a teleport trap). This ensures broken local grids never reach the runtime.

**Status (2026-04-09):**
- Partially implemented.
- Current validator checks field presence, map/area parity, and direction consistency, but it does **not** yet enforce the stronger distance-based spatial coherence audit described here.

### 4. The Stage (Environment Grid)
A 3x3 tactical grid representing the physical room or clearing. It contains *no people*, only terrain, hazards, and features.

* **Generation:** Created at module ingest or backfill (Option A). The LLM cartographer extracts a `tactical_grid` array from the location's prose description and saves it to the module's `areas/` JSON.
* **Schema Definition:** The `tactical_grid` should be an array of 9 strings mapping to `["NW", "N", "NE", "W", "C", "E", "SW", "S", "SE"]`. Each string contains a terse descriptor of the terrain, furniture, or hazards in that zone (e.g., `"Bar/Kegs"`, `"Open Space"`, `"Fireplace"`, `"Stairs Up"`).
* **Prompt Logic:** "Analyze the physical description of this room. Create a 3x3 tactical grid dividing the room into 9 zones. For each zone, provide a 1-3 word description of the most prominent environmental feature, hazard, or terrain. Do not include characters or monsters. If a zone is empty, label it 'Open Space'."
* **Publishability Audit:** Extend the readiness validator to check that every location possesses a valid 9-element `tactical_grid` array containing string descriptors, ensuring the runtime combat system always has an environment stage to load.

**Status (2026-04-09):**
- Implemented for the current spatial contract validation slice.

## Path Ahead

To move this plan toward completion, the next work should be:

1. **Finish spatial publishability foundations**
- complete authored-semantic ingest adjacency extraction
- add strict geometric spatial coherence validation for new outputs
- keep legacy modules warn-first until remediated

2. **Add deterministic semantic enrichment for publication**
- destination phrase map
- canonical location alias map
- NPC scene-authority map
- hidden/revealable NPC bindings

3. **Introduce a dedicated publication audit layer**
- hard-fail unresolved destination phrases
- hard-fail NPCs that can appear in scene without deterministic authority mapping
- hard-fail likely player phrases that can drift to the wrong valid destination

4. **Add probe-based publication tests**
- travel probes
- escort probes
- hidden/revealable NPC probes
- authored destination resolution probes

5. **Split readiness from publishable**
- preserve current structural readiness checks
- add a stricter `publishable` level for tester/player release decisions

## Archive Gate

This plan should **not** be archived yet.

Archive only when:
- the repository has a real `publishable` gate
- semantic enrichment and publication audit are implemented
- synthetic probe validation exists
- spatial publication checks are upgraded from field-shape enforcement to true coherence enforcement
