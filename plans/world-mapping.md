# World Mapping UX Plan (Graph-First, ASCII-to-Canvas)

Status: Draft for implementation
Priority: High
Date: 2026-02-23
Owner: Tabletop UX + world systems
Target: `plans/world-mapping.md`

---

## 1) Objective

Deliver a map UX that gives players and facilitator a clear spatial picture at three levels:

1. Current environment (local area and immediate surroundings)
2. Traversed locations in current module
3. Known world map across discovered modules

This plan is graph-first and deterministic, with ASCII-first rendering for fast delivery and Canvas polish later.

---

## 2) Why graph-first (recommended)

Graph-first is the best initial strategy for NEQ because it reuses existing canonical data and avoids blocking on full cartography art.

Reasons:
- Existing area files already include room/location connectivity and coordinates.
- Existing location pathfinding already builds node/edge graphs across areas/modules.
- Existing world registry already tracks modules and areas for known-world expansion.
- Graphs are stable for gameplay logic, easy to test, and cheap to render as ASCII.

Decision:
- Start with graph maps (nodes, edges, states).
- Layer visual styling later (tile/glyph + Canvas).
- Keep graph contract as long-term source of truth for map UX.

---

## 3) Scope and map levels

## 3.1 Local Map (Current Environment)

Purpose:
- Show where the party is now and what is immediately reachable.

Inputs:
- Current module + area + location from `party_tracker.json`.
- Area file `map.layout`, `map.rooms`, location connectivity.

Output:
- Local graph with current node highlighted.
- Discovered nodes, immediate exits, unknown nodes (`?`) for fog-of-war.

Light/visibility contract (MVP):
- Approximate "light shines on walls" as visibility radius and adjacency reveal.
- Defer physically accurate wall lightcasting until richer geometry exists.

## 3.2 Module Map (Traversal)

Purpose:
- Show journey through the current module and where players have been.

Inputs:
- Location graph for module.
- Transition history + discovered set.

Output:
- Traversal path overlays (visited order and current branch).
- Optional badges for unresolved hooks, known threats, and blocked routes.

## 3.3 Known World Map (Campaign)

Purpose:
- Show modules/regions known to the party and growth over campaign time.

Inputs:
- `modules/world_registry.json` modules and areas.
- Party discovery records and travel history.
- Future world-narrative signals (pressure overlays).

Output:
- Module-level graph first (hub-and-spoke / region graph).
- States: discovered, rumored, locked, active.
- World-narrative overlays later (threat fronts, faction pressure, instability).

---

## 4) UX placement and interaction

Sidebar placement:
- Add `Maps` tab in right sidebar after `NPCs`.

Maps tab sub-tabs:
1. `Local`
2. `Module`
3. `World`

Behavior:
- Outside combat: default to `Local` graph view.
- In combat: `Local` can switch to tactical combat map profile.
- Preserve current `Character`, `Inventory`, `Spells & Magic`, `NPCs`, `Journal`, `Debug` behavior.

Core controls:
- Zoom in/out
- Center on current
- Toggle labels
- Toggle fog-of-war
- Show path from current to selected node

---

## 5) Shared data contracts

Use one map contract for all renderers and all scopes.

## 5.1 `map_state` (server authoritative)

```json
{
  "scope": "local",
  "active": true,
  "module": "Keep_of_Doom",
  "areaId": "SK001",
  "currentNodeId": "C07",
  "nodes": [
    {
      "id": "C07",
      "name": "Lord's Study",
      "kind": "location",
      "x": 3,
      "y": 3,
      "state": "current",
      "tags": ["discovered"]
    },
    {
      "id": "C05",
      "name": "Great Hall",
      "kind": "location",
      "x": 3,
      "y": 2,
      "state": "discovered",
      "tags": []
    },
    {
      "id": "C06",
      "name": "Unknown",
      "kind": "location",
      "x": 2,
      "y": 3,
      "state": "undiscovered",
      "tags": ["fog"]
    }
  ],
  "edges": [
    {"from": "C07", "to": "C05", "kind": "path", "state": "known"},
    {"from": "C07", "to": "C06", "kind": "path", "state": "unknown"}
  ],
  "overlays": {
    "visitedPath": ["C01", "C03", "C05", "C07"],
    "visibleNodeIds": ["C07", "C05", "C06"]
  },
  "meta": {
    "generatedAt": "2026-02-23T12:00:00",
    "rendererProfile": "ascii"
  }
}
```

## 5.2 `ui_state` (client ephemeral)

```json
{
  "scope": "local",
  "zoom": 1.0,
  "pan": {"x": 0, "y": 0},
  "selectedNodeId": "C05",
  "showLabels": true,
  "showFog": true,
  "highlightPathToSelected": true
}
```

## 5.3 Renderer contract

- `renderMap(mapState, uiState)` is the only renderer entry point.
- `AsciiRenderer` and `CanvasRenderer` consume the same contract.
- Tactical/combat map is a specialized profile, not a separate architecture.

---

## 6) Worldview graph semantics in `memory.db` (significant, low-bloat)

Add explicit graph semantics to NEQ SQLite as additive tables, with stable IDs and typed relationships.

Purpose:
- Support coherent local/module/world maps and future worldview logic.
- Provide one queryable graph model for narration context and DM debugging.
- Avoid introducing external memory runtimes.

Table set (proposed, additive):
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
  - Optional per-party fog/discovery state without mutating canonical node definitions.

Non-negotiable constraints:
- `memory.db` remains NEQ source of truth for worldview graph semantics.
- Module files remain topology/content authority.
- Graph tables are additive and backward compatible.
- No external MCP/Node runtime dependency is required.

---

## 7) Discovery and persistence model

Track what players know separately from raw module data.

Recommended file:
- `modules/map_discovery/map_discovery.json`

Transition plan:
- MVP may start with `modules/map_discovery/map_discovery.json` for speed.
- Migrate/dual-write to `memory.db` worldview tables once stable.
- Final target: discovery state and worldview graph in `memory.db` with optional JSON export cache.

Suggested structure:
- `modules`: discovered module IDs and states
- `areas`: discovered area IDs
- `locations`: discovered location IDs
- `visited_order`: chronological list for breadcrumb rendering
- `last_seen`: timestamps for optional recency highlighting

Rules:
- Discover current location on entry.
- Reveal immediate connected nodes on successful transition.
- Never erase discovery unless explicit campaign reset.
- Atomic writes using safe JSON helpers.

---

## 8) Read-only graph viewer for DM/debug (significant, low-bloat)

Add a read-only visualization for discovered world graph and links, exported from `memory.db`.

Purpose:
- Give facilitator and developer a clear worldview diagnostic surface.
- Improve trust/debugging for map and narrative continuity.

Requirements:
- Read-only UI and API surface.
- Data source is `memory.db` export/query only.
- Viewer never mutates graph state.
- If graph data unavailable, fail-open and hide panel gracefully.

Suggested placement:
- Debug/DM panel first (low player clutter).
- Optional later promotion into player-facing `World` map overlays after validation.

Proposed API:
- `GET /api/memory/worldview-graph`
  - Returns nodes, edges, and discovered subsets by current party/campaign context.

---

## 9) Narrator LLM grounding contract

Add bounded map context to DM Note for spatial continuity.

Proposed DM Note block:

```text
--- MAP SNAPSHOT ---
Scope: Local (SK001)
Current: Lord's Study (C07)
Visible exits: Great Hall (C05), Armory (C06)
Discovered nearby: C05, C06, C03
Recent path: C01 -> C03 -> C05 -> C07
Unknown adjacent nodes exist: YES
Rule: Do not narrate movement to nodes not listed as visible exits unless discovered during play.
```

Requirements:
- Keep block short and deterministic.
- Do not inject full map dumps.
- If map state is unavailable, omit block and fail-open.

---

## 10) Integration points (existing files)

Backend:
- `core/memory/memory_db.py`
  - Add worldview graph tables and migrations.
- `core/memory/memory_retrieval.py`
  - Add worldview graph read helpers for map payload + viewer export.
- `web/routes/memory_routes.py`
  - Add read-only worldview graph endpoint.
- `web/web_interface.py`
  - Add socket handler: `request_map_data`
  - Emit `map_data_response` for requested scope.
- `web/extensions/tabletop_socket_handlers.py`
  - Implement map payload builders for local/module/world scopes.
- `utils/location_path_finder.py`
  - Reuse graph data source for module/local graph extraction.
- `core/managers/location_manager.py`
  - Hook discovery updates on successful transitions.
- `utils/multi_pc_dm_note.py`
  - Inject bounded `MAP SNAPSHOT` when available.

Frontend:
- `web/templates/game_interface.html`
  - Add `Maps` tab and map sub-tabs.
  - Add map mount container and controls.
- `web/templates/game_interface.html` (Debug/DM section)
  - Add read-only worldview graph viewer mount (initially debug-only).
- `web/static/js/world_map_renderer.js` (new)
  - Shared render entry; ASCII first.
- `web/static/js/world_map_state.js` (new)
  - UI state machine for map scope/zoom/select.
- `web/static/css/world_map.css` (new)
  - Graph-first styling; PlaySCII-inspired palette continuity.

---

## 11) Delivery phases

## 11.1 Phase 1 - Local graph MVP (MUST)

Deliver:
- `Maps` tab with `Local` sub-tab.
- Local graph ASCII rendering from area map/connectivity.
- Current node and visible exits.
- Discovery persistence and fog states.

Success:
- Players can orient in current environment without reading raw descriptions only.

## 11.2 Phase 2 - Module traversal map (MUST)

Deliver:
- `Module` sub-tab with visited path.
- Current position in module graph.
- Path highlight to selected discovered nodes.

Success:
- Players can reconstruct route through module and plan return routes.

## 11.3 Phase 3 - Known world graph (SHOULD)

Deliver:
- `World` sub-tab from world registry + discovery state.
- Module nodes with discovered/rumored/locked states.

Success:
- Campaign progression feels spatially coherent across modules.

## 11.3b Phase 3B - `memory.db` worldview graph semantics (SHOULD)

Deliver:
- Add `world_nodes`, `world_edges`, and discovery semantics in SQLite.
- Provide query/export layer for map payloads and viewer.

Success:
- NEQ has explicit stable node/edge worldview semantics in `memory.db`.
- No duplicate source-of-truth behavior is introduced.

## 11.4 Phase 4 - LLM map snapshot + world overlays (SHOULD)

Deliver:
- DM Note map snapshot injection.
- Optional world-narrative overlays (pressure markers) on world map.

Success:
- Narrator continuity improves and world state feels alive.

## 11.4b Phase 4B - Read-only graph viewer (SHOULD)

Deliver:
- Debug/DM graph viewer powered by `memory.db` export endpoint.
- Filter by scope (`local`, `module`, `world`) and discovery state.

Success:
- Facilitator can inspect world links and discovery state without editing data.

## 11.5 Phase 5 - Canvas polish (SHOULD)

Deliver:
- Canvas renderer with glyph/tile style and subtle effects.
- Keep ASCII renderer as fallback.

Success:
- Distinctive retro tactical/world map UX with robust fallback.

---

## 12) Risks and mitigations

Risk: conflicting map truths between area files and discovery state.
- Mitigation: module files define topology; discovery file defines visibility only.

Risk: token/context bloat from map data in prompts.
- Mitigation: bounded map snapshot block only.

Risk: sidebar complexity and crowding.
- Mitigation: progressive disclosure via sub-tabs and minimal default overlays.

Risk: old modules with inconsistent map fields.
- Mitigation: fallback to connectivity graph from location data when `map.layout` missing.

Risk: worldview duplication across JSON + SQLite.
- Mitigation: treat JSON discovery as temporary bootstrap; migrate toward SQLite as final source.

Risk: read-only viewer accidentally becomes write surface.
- Mitigation: endpoint and UI stay strictly read-only; no mutation handlers in viewer module.

---

## 13) Acceptance criteria

1. `Maps` tab exists and works in sidebar after `NPCs`.
2. Local map correctly highlights current location and visible exits.
3. Module map shows discovered traversal path.
4. World map shows known modules from registry + discovery state.
5. DM Note map snapshot appears when map state is available.
6. Existing gameplay remains functional if map services fail or are missing.
7. `memory.db` contains explicit worldview node/edge semantics with stable IDs.
8. Read-only worldview graph viewer works from `memory.db` export without write capability.

---

## 14) Immediate next build steps

1. Implement `request_map_data` + `map_data_response` socket contract.
2. Build local graph payload from current area file and location connectivity.
3. Add `Maps` tab with `Local/Module/World` sub-tabs (ASCII renderer first).
4. Add `map_discovery.json` persistence and transition-time updates.
5. Add compact `MAP SNAPSHOT` block to DM Note builder.
6. Expand to module and world scopes once local graph is stable.
7. Add `memory.db` worldview graph tables and read helpers.
8. Add read-only `/api/memory/worldview-graph` endpoint and debug viewer mount.
