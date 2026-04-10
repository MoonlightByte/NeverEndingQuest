# World Mapping v2 Plan (Architecture-Aligned, OpenSpec-Ready)

Status: Draft for OpenSpec v2 planning
Priority: High
Date: 2026-02-28
Owner: Tabletop UX + world systems
Target: `plans/version-2/world-mapping.md`

## Titan v2 alignment stub

- Umbrella reference: `plans/version-2/titan-integration.md`
- Retune status: Pending (overlay and filters not yet implemented)
- Last tagged: 2026-02-26
- Retune focus: read-only Titan pressure overlays by scope and debug filters by Titan/status

---

## 0) Objective

Deliver a player-facing map experience (Local, Module, World) that is deterministic, fail-open, and fully aligned with the existing NeverEndingQuest mapping architecture.

This is not a greenfield map system. It is a convergence plan that reuses existing contracts and avoids duplicate map truths.

---

## 1) Existing mapping architecture (current reality)

This section is the authoritative inventory that implementation MUST respect.

### 1.1 Topology and map artifacts

- Area topology currently lives in area files:
  - `modules/<module>/areas/<AREA_ID>.json`
  - Includes location graph data (`locations[].connectivity`, `areaConnectivity`, `areaConnectivityId`)
  - Often includes embedded `map` object (`map.rooms`, `map.layout`)
- Separate map artifacts also exist:
  - `modules/<module>/map_<AREA_ID>.json`
  - Path helper: `utils/module_path_manager.py:get_map_path()`
- Generation paths already write map artifacts:
  - `core/generators/module_builder.py`
  - `core/generators/area_generator.py`

### 1.2 Validation and schema

- Map schema exists and is active:
  - `schemas/map_schema.json`
- Module validator includes dedicated map pass:
  - `core/validation/validate_module_files.py:validate_map_files()`
- `get_area_ids()` intentionally excludes `map_*.json` from area discovery:
  - `utils/module_path_manager.py:get_area_ids()`

### 1.3 Runtime graph foundation

- Canonical traversal graph builder already exists:
  - `utils/location_path_finder.py:LocationGraph`
- It aggregates nodes/edges from area files, cross-area links, and world registry context.
- It already powers movement/path validation and should be reused for map payloads.

### 1.4 AI atlas read models (already in production)

- Module atlas:
  - `core/ai/atlas_builder.py`
  - Built from `areas/*.json`
- Exploration-aware atlas:
  - `core/ai/transition_atlas_builder.py`
- Runtime injection:
  - `core/ai/conversation_utils.py` rebuilds/injects module atlas each cycle.
  - Old per-area `map_*.json` injection is explicitly deprecated in this path.

### 1.5 World catalog

- `modules/world_registry.json` is a world/module/area metadata registry.
- It is useful for world scope labels/state, but not by itself as a complete connectivity graph.

---

## 2) Source-of-truth hierarchy (non-negotiable)

To prevent architecture drift, map implementation MUST follow this hierarchy.

### 2.1 Topology hierarchy

1. Primary runtime topology source: `LocationGraph` (derived from area location connectivity)
2. Secondary topology fallback: embedded `area.map` data in area file
3. Tertiary fallback: `map_<AREA_ID>.json`
4. Fail-open fallback: minimal current-node payload (no crash, degraded map)

### 2.2 World hierarchy

1. `world_registry.json` for module/area catalog metadata and labels
2. Derived graph links from `LocationGraph` and area connectivity for traversal reality

### 2.3 Discovery hierarchy (phased)

- Phase A: `modules/map_discovery/map_discovery.json` (fast MVP)
- Phase B: dual-write JSON + `memory.db`
- Phase C: `memory.db` authoritative (`world_nodes`, `world_edges`, discovery state), JSON optional export cache

### 2.4 Invariants

- UI never mutates topology definitions.
- Discovery state never rewrites canonical area/module topology.
- No parallel graph builders that can diverge from `LocationGraph`.
- AI atlas pipelines remain read models for LLM grounding, not UI authority.

---

## 3) Scope

### 3.1 Local map (MUST)

- Current location node
- Visible adjacent exits
- Discovered vs unknown nodes (fog)
- Deterministic adjacency from canonical graph source chain

### 3.2 Module map (MUST)

- Current module graph view
- Visited traversal overlays
- Path highlighting among discovered nodes

### 3.3 World map (SHOULD)

- Module-level nodes and known areas
- States: discovered, rumored, locked, active
- Optional pressure overlays deferred behind stable core data

---

## 4) Data contracts

### 4.1 Socket contract: `request_map_data`

Request:

```json
{
  "scope": "local|module|world",
  "module": "optional override",
  "areaId": "optional override",
  "includeDebug": false
}
```

Response event: `map_data_response`

```json
{
  "status": "ok|degraded|error",
  "scope": "local|module|world",
  "map_state": {
    "module": "The_Thornwood_Watch",
    "areaId": "TW001",
    "currentNodeId": "TW04",
    "nodes": [
      {
        "id": "TW04",
        "name": "Hermit's Refuge",
        "kind": "location|area|module",
        "x": 2,
        "y": 1,
        "state": "current|discovered|undiscovered|rumored|locked",
        "tags": ["fog"],
        "source": "location_graph|area_map|map_file|registry"
      }
    ],
    "edges": [
      {
        "from": "TW04",
        "to": "TW06",
        "kind": "path|area_transition|module_transition",
        "state": "known|unknown|blocked",
        "source": "location_graph|area_map|map_file|registry"
      }
    ],
    "overlays": {
      "visitedPath": ["TW01", "TW02", "TW04"],
      "visibleNodeIds": ["TW04", "TW06", "TW03"]
    },
    "meta": {
      "generatedAt": "ISO-8601",
      "rendererProfile": "ascii",
      "degraded": false,
      "fallbackLevel": "none|secondary|tertiary|minimal"
    }
  },
  "error": null
}
```

### 4.2 UI state contract (`world_map_state.js`)

Client-local, non-authoritative state:

- `scope`
- `zoom`
- `pan`
- `selectedNodeId`
- `showLabels`
- `showFog`
- `highlightPathToSelected`

### 4.3 Discovery contract

Initial JSON form (`map_discovery.json`):

- discovered modules/areas/locations
- visited order
- last seen timestamps
- optional visibility snapshots

Later `memory.db` equivalent MUST preserve the same semantics.

---

## 5) Rendering architecture

- Single renderer entrypoint:
  - `renderMap(mapState, uiState)`
- Two renderers under one contract:
  - `AsciiRenderer` (MVP required)
  - `CanvasRenderer` (later polish)
- Tactical combat mapping is a renderer profile, not a separate architecture.
- If map payload is unavailable:
  - fail-open placeholder view
  - never break chat/combat flow

---

## 6) Integration points (concrete, merge-safe)

### 6.1 Backend

- `web/web_interface.py`
  - Thin socket wrapper for `request_map_data` (host hook only)
- `web/extensions/tabletop_socket_handlers.py`
  - Map payload builder implementation for local/module/world scopes
- `utils/location_path_finder.py`
  - Reused as canonical graph extraction source
- `core/managers/location_manager.py`
  - Discovery updates on successful transitions
- `core/memory/memory_db.py` + retrieval layer
  - Worldview tables and read helpers (phase-gated)
- `web/routes/memory_routes.py`
  - Read-only world graph endpoint for debug surface
- `utils/multi_pc_dm_note.py`
  - Inject compact deterministic MAP SNAPSHOT when available

### 6.2 Frontend

- `web/templates/game_interface.html`
  - Add `Maps` tab after `NPCs`
  - Add `Local/Module/World` sub-tabs and controls
- `web/static/js/world_map_renderer.js` (new)
- `web/static/js/world_map_state.js` (new)
- `web/static/css/world_map.css` (new)

### 6.3 Merge-safety rules

- Prefer extension modules over core rewrites.
- Core hooks must be marked with `# TABLETOP MODE:` comments.
- Preserve upstream structure and naming; add integration seams only.

---

## 7) AI grounding alignment (no drift)

Map UI and AI map context must remain coherent:

- Keep existing atlas pipelines:
  - `atlas_builder` and `transition_atlas_builder` remain active
- Add bounded DM Note map snapshot sourced from the same map payload service:
  - current node
  - visible exits
  - nearby discovered nodes
  - recent path
- Do not inject full map dumps into prompt context.
- If map state is missing, omit map snapshot and fail-open.

---

## 8) Worldview graph semantics in `memory.db`

Add explicit graph semantics to NEQ SQLite as additive tables, with stable IDs and typed relationships.

Purpose:

- Support coherent local/module/world maps and future worldview logic
- Provide one queryable graph model for narration context and DM debugging
- Avoid introducing external memory runtimes

Proposed additive tables:

- `world_nodes`
  - `node_id` (stable canonical ID, PK)
  - `node_type` (`module`, `area`, `location`, `faction`, `landmark`, `threat`, `party`)
  - `display_name`
  - `source_key` (link to canonical source where applicable)
  - `status` (`discovered`, `rumored`, `locked`, `active`, `archived`)
  - `metadata_json`
  - `created_at`, `updated_at`
- `world_edges`
  - `edge_id` (stable ID, PK)
  - `from_node_id`, `to_node_id`
  - `edge_type` (`connects_to`, `contains`, `located_in`, `threatens`, `allied_with`, `visited_after`)
  - `weight` (optional confidence/strength)
  - `metadata_json`
  - `created_at`, `updated_at`
- `world_discovery`
  - `party_id`, `node_id`, `discovered_at`, `discovery_source`

Non-negotiable constraints:

- `memory.db` is source of truth for worldview graph semantics once migrated.
- Module files remain topology/content authority.
- Graph tables are additive and backward compatible.
- No external runtime dependencies are required.

---

## 9) Read-only graph viewer for DM/debug

Add a read-only visualization for discovered world graph and links, exported from `memory.db`.

Requirements:

- Read-only UI and API surface
- Data source is `memory.db` export/query only
- Viewer never mutates graph state
- If graph data is unavailable, fail-open and hide panel gracefully

Suggested placement:

- Debug/DM panel first (low player clutter)
- Optional later promotion into player-facing World overlays after validation

Proposed API:

- `GET /api/memory/worldview-graph`

---

## 10) OpenSpec v2 scaffold targets

Create one parent change with capability specs:

1. `world-map-data-contracts`
2. `world-map-local-module-world-ui`
3. `world-map-discovery-persistence`
4. `world-map-llm-snapshot-grounding`
5. `world-map-readonly-debug-viewer`

Each spec MUST include:

- deterministic inputs/outputs
- fail-open behavior
- non-regression requirements for existing gameplay
- clear source-of-truth references to existing architecture

---

## 11) Phased delivery plan

### 11.1 Phase 0 - Architecture lock + contracts (MUST)

Deliver:

- Source-of-truth hierarchy finalized
- Socket contract frozen (`request_map_data` / `map_data_response`)
- Fallback precedence codified and tested

Success:

- No duplicate map truth paths introduced

### 11.2 Phase 1 - Local map MVP (MUST)

Deliver:

- `Maps` tab with `Local` sub-tab
- Local graph ASCII rendering
- Current node and visible exits
- Discovery persistence and fog states

Success:

- Players can orient in current environment without relying on descriptions only

### 11.3 Phase 2 - Module traversal map (MUST)

Deliver:

- `Module` sub-tab with visited path
- Current position in module graph
- Path highlight to selected discovered nodes

Success:

- Players can reconstruct route through module and plan returns

### 11.4 Phase 3 - Known world graph (SHOULD)

Deliver:

- `World` sub-tab from world registry + discovery state
- Module nodes with discovered/rumored/locked/active states

Success:

- Campaign progression feels spatially coherent across modules

### 11.5 Phase 3B - `memory.db` worldview graph semantics (SHOULD)

Deliver:

- Add `world_nodes`, `world_edges`, and discovery semantics in SQLite
- Provide query/export layer for map payloads and viewer

Success:

- NEQ has explicit stable node/edge worldview semantics in `memory.db`

### 11.6 Phase 4 - LLM map snapshot + debug viewer (SHOULD)

Deliver:

- DM Note map snapshot injection
- Read-only worldview graph viewer powered by `memory.db`

Success:

- Narrator continuity improves and facilitator debugging is easier

### 11.7 Phase 5 - Canvas polish (SHOULD)

Deliver:

- Canvas renderer with glyph/tile style and subtle effects
- ASCII renderer retained as fallback

Success:

- Distinctive map UX with robust degraded behavior

---

## 12) Test and verification strategy

### 12.1 New regression suites

- `scripts/test_world_map_payloads.py`
- `scripts/test_world_map_discovery.py`
- `scripts/test_world_map_ui_contracts.py` (source-contract tests)

### 12.2 Required validation gates

- `.venv/bin/python core/validation/validate_module_files.py`
- Verify map schema pass rate remains stable or improves
- Verify no regression in movement, combat, and narration flows

### 12.3 Architecture-specific checks

- Fallback precedence validated end-to-end:
  - `LocationGraph -> area.map -> map_<AREA_ID>.json -> minimal payload`
- No contradiction between UI map payload and atlas-based LLM context for current location/exits
- Read-only viewer has zero mutation handlers

---

## 13) Risks and mitigations

Risk: duplicate graph logic drifts from traversal logic.

- Mitigation: map payloads must be built on `LocationGraph`; no parallel graph builder.

Risk: conflicting discovery truth across JSON and SQLite.

- Mitigation: explicit phased authority, dual-write transition window, and migration tests.

Risk: token/context bloat from map data in prompts.

- Mitigation: strict bounded MAP SNAPSHOT only.

Risk: old modules with sparse map fields.

- Mitigation: fallback precedence and degraded rendering contract.

Risk: upstream merge conflicts in host UI shell.

- Mitigation: extension-first implementation and minimal host hooks marked `# TABLETOP MODE:`.

---

## 14) Acceptance criteria

1. `Maps` tab exists and works in sidebar after `NPCs`.
2. Local map highlights current location and visible exits correctly.
3. Module map shows discovered traversal path deterministically.
4. World map shows known modules/areas from registry + discovery state.
5. DM Note map snapshot appears when map state is available.
6. Existing gameplay remains functional if map services fail.
7. Fallback precedence behaves exactly as specified.
8. `memory.db` worldview graph semantics are additive and stable.
9. Read-only worldview graph viewer works without write capability.
10. Atlas context and map payload remain coherent for current location/exits.

---

## 15) Immediate next steps (for OpenSpec creation)

1. Create OpenSpec parent change for world mapping v2.
2. Split into the five capability specs listed in Section 10.
3. Encode the source-of-truth hierarchy as explicit MUST requirements.
4. Add Phase 0 contract tests before implementing UI rendering.
5. Implement Phase 1 (`Local`, ASCII) first; defer Canvas and overlays.
6. Add MAP SNAPSHOT only after payload contract is stable.
7. Introduce `memory.db` worldview tables after Local/Module payloads are validated.
8. Add read-only debug graph endpoint and viewer after DB semantics land.
