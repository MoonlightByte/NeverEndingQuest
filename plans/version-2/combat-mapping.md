# Combat Mapping UX Plan (PlaySCII-Inspired, NEQ-Native)

Status: Draft for implementation
Priority: High
Date: 2026-02-23
Owner: Tabletop UX + combat systems
Target: `plans/version-2/combat-mapping.md`

---

## 1) Objective

Ship a tactical combat mapping experience for NEQ that is currently missing, with a strong old-school ASCII/tiles aesthetic inspired by PlaySCII art style, while keeping runtime fully NEQ-native (Python + web socket + browser rendering).

Primary goals:
1. Make combat spatially legible (who is where, range, line-of-sight, terrain).
2. Preserve tabletop facilitator flow (fast turn execution, low cognitive overhead).
3. Keep implementation merge-safe and plugin-oriented.
4. Avoid heavy engine lock-in and avoid external runtime dependencies.

---

## 2) Direction and constraints

### 2.1 Product direction (MUST)
- Runtime map system MUST be browser-native inside NEQ.
- PlaySCII is inspiration and optional art authoring tool only (not embedded runtime).
- Combat state remains Python ground truth; visual layer reflects state, never becomes authority.
- Existing initiative and combat flow remain functional during rollout.

### 2.2 UX direction (MUST)
- Visual style should feel deliberate and game-like, not generic dashboard UI.
- Spatial information must be readable at a glance in active combat.
- Tactical overlays (distance, AoE, LOS) should be explicit, deterministic, and lightweight.
- Desktop-first support is acceptable for initial release.

### 2.3 Technical constraints (SHOULD)
- Prefer additive modules and thin host-file hooks (`# TABLETOP MODE:`).
- Keep schema changes backward compatible (optional fields first).
- Fail-open on missing map data: combat still runs with current initiative-only UI.
- Use ASCII-first implementation as an intentional scaffold for canvas rendering, not as throwaway work.
- Align combat map contracts with `plans/version-2/world-mapping.md` shared graph contract so combat is a scoped profile, not a separate map system.

---

## 3) Concrete visual spec

## 3.1 Visual identity

- Theme name: `Tactical Terminal Fantasy`
- Mood: low-res, high-clarity, tabletop command console
- Composition: tile grid foreground + subdued atmospheric backdrop + high-contrast token silhouettes

Design principles:
1. Clarity first, style second.
2. Strong silhouettes over texture noise.
3. Limited palette to preserve readability.
4. Motion used for feedback, not decoration.

## 3.2 Typography and glyph language

- Primary UI font (labels/stats): a crisp mono or pseudo-terminal face already approved in project style.
- Map glyphs: tile/glyph atlas (CP437/PETSCII-inspired forms), not raw text nodes per tile.
- Numeric overlays (distance, coordinates, HP pips) use compact monospace for fast scanning.

Glyph categories:
- Terrain: floor, wall, rubble, water, brush, hazard.
- Tokens: player, allied NPC, enemy, boss.
- Overlay marks: move path, LOS clear/blocked, AoE zone, selected tile.

## 3.3 Palette contract

Use a fixed tactical palette (example baseline):

- `--map-bg-deep`: `#111418`
- `--map-bg-mid`: `#1B2329`
- `--map-grid-line`: `#2A353E`
- `--map-floor`: `#2F3C45`
- `--map-wall`: `#5F6B75`
- `--map-hazard`: `#A0442A`
- `--faction-player`: `#4FA3FF`
- `--faction-ally`: `#6CCB7A`
- `--faction-enemy`: `#E05A5A`
- `--faction-boss`: `#F2B94B`
- `--overlay-measure`: `#8FD3FF`
- `--overlay-los-clear`: `#7EE787`
- `--overlay-los-blocked`: `#FF7B72`
- `--overlay-aoe`: `#C586F8`

Rules:
- Keep token-vs-background contrast >= readable threshold in both bright and dim maps.
- Do not use purple as the dominant base UI color; reserve for AoE overlays only.

## 3.4 Rendering style

Map rendering layers (back to front):
1. Atmosphere layer: soft gradient + subtle noise.
2. Static terrain layer: tile atlas, cached draw.
3. Token layer: entities with silhouette + faction ring.
4. Overlay layer: movement path, LOS, AoE preview, coordinate highlight.
5. UI micro layer: turn marker pulse, selected tile frame, distance labels.

Effects budget (initial):
- Optional scanline opacity <= 0.08
- Optional vignette opacity <= 0.10
- Token pulse animation only for active actor (1.2s cycle)
- No continuous heavy particle systems in MVP

## 3.5 Combat map panel layout

Desktop panel structure:
- Left: tactical map canvas (dominant area)
- Right/top rail: existing initiative strip and combat round indicator
- Bottom micro-bar: mode chips (`Move`, `Measure`, `LOS`, `AoE`, `Clear`)

Fallback behavior:
- If map data missing, hide map panel and keep current initiative-only behavior.
- If canvas errors, fail-open to ASCII map text block in combat output area.

## 3.6 Token and indicator spec

Token visuals:
- Circular or rounded-square base icon with faction ring.
- Tiny facing indicator optional (deferred).
- HP state indicated by ring segment color or thin underbar.

Selection/turn states:
- Active turn token: animated outer ring pulse.
- Hover token: subtle glow + quick tooltip.
- Targeted token: red bracket corners.
- Dead/defeated token: desaturated + crossed overlay.

## 3.7 Interaction spec

Modes:
1. `Select` (default): inspect tile/token details.
2. `Measure`: click start/end, show distance tiles/feet.
3. `LOS`: click source/target, show clear vs blocked line.
4. `AoE`: pick shape/range, preview affected tiles.

Interaction behavior:
- Left click: select
- Shift+click: additive selection (future)
- Right click: context action (future)
- ESC: clear overlay state

Determinism requirements:
- Distance calculations and LOS checks run from shared Python rules.
- Frontend preview may run optimistic math but must reconcile with backend truth.

---

## 4) Implementation outline (initial plan)

This outline follows the previously recommended rollout path.

## 4.1 Phase 1 - Foundation and immediate value (MUST)

Scope:
- Add optional spatial fields to encounter creature contract.
- Add backend map payload endpoint/socket response.
- Add lightweight ASCII tactical map rendering and coordinate display.

Data contract additions (optional first):
- Creature-level:
  - `position: {"x": int, "y": int}`
  - `movementSpeed: int` (default from speed)
  - `movementRemaining: int` (per turn)
- Encounter-level:
  - `gridBounds: {"minX": int, "maxX": int, "minY": int, "maxY": int}`
  - `terrain: [{"x": int, "y": int, "type": str}]`
  - `obstacles: [{"x": int, "y": int, "kind": str}]`

Frontend output in Phase 1:
- Coordinate readout in initiative tooltip/cards.
- Text-mode tactical map block for immediate usability.

ASCII scaffold contract:
- Phase 1 defines the canonical `map_state` payload and tactical interaction state machine.
- Phase 1 tactical helpers (distance, movement, later LOS/AoE) are renderer-agnostic.
- Canvas implementation in later phases reuses Phase 1 contracts and logic, swapping only draw/render layers.
- ASCII renderer remains as a fail-open fallback path even after canvas ships.

Success criteria:
- Facilitator can see where each combatant is.
- No regression to existing combat turn flow.

## 4.2 Phase 2 - Deterministic tactical helpers (MUST)

Scope:
- Add backend helpers:
  - `measure_distance(start, end, metric='5e')`
  - `validate_movement(actor, from, to, budget, obstacles, terrain)`
- Add path preview overlays and movement budget display.

Rules:
- 5e-compatible movement accounting.
- Clear error messages on blocked/out-of-range moves.
- Atomic persistence of movement state to encounter file.

Success criteria:
- Move intent can be validated before action resolution.
- Remaining movement visibly updates per actor turn.

## 4.3 Phase 3 - LOS and AoE overlays (SHOULD)

Scope:
- Add backend LOS check and AoE tile calculators.
- Frontend toggles for LOS and AoE preview.

Shapes:
- Circle (radius), line, cone, rectangle.

Success criteria:
- Facilitator can preview tactical effects without manual counting.
- Overlay calculations are deterministic and performant.

## 4.4 Phase 4 - Visual polish panel (SHOULD)

Scope:
- Replace/augment text map with styled Canvas/Pixi panel.
- Keep ASCII/glyph aesthetic, add subtle effects from visual spec.
- Add static map-template import workflow (PlaySCII-authored exports as optional backdrop).

Success criteria:
- Distinct retro-tactical look and feel.
- Stable rendering at tabletop session cadence.

---

## 5) Architecture and file-level planning

## 5.1 Backend additions

Candidate modules:
- `core/combat/spatial_rules.py` (new)
  - distance, LOS, AoE, movement validation
- `core/combat/map_state.py` (new)
  - normalization, defaults, serialization helpers

Likely touched files:
- `schemas/encounter_schema.json` (optional spatial fields)
- `core/ai/action_handler.py` (encounter initialization defaults)
- `updates/update_encounter.py` (safe support for spatial change updates)
- `web/extensions/tabletop_socket_handlers.py` (map payload emitter)
- `web/web_interface.py` (thin socket hook only)

## 5.2 Frontend additions

Candidate files:
- `web/static/js/combat_map_renderer.js` (new)
- `web/static/js/combat_map_overlays.js` (new)
- `web/static/css/combat_map.css` (new)

Likely touched host files:
- `web/templates/game_interface.html` (mount point + mode controls + listeners)

Integration approach:
- Keep existing initiative tracker active.
- Map panel subscribes to same combat payload cycle.
- Fail-open if map payload absent.

## 5.3 Renderer boundary contract (ASCII -> Canvas)

Lock this contract in Phase 1 so later canvas work is additive.

`map_state` example payload:

```json
{
  "active": true,
  "encounterId": "TW03-E2",
  "round": 2,
  "grid": {
    "minX": 0,
    "maxX": 13,
    "minY": 0,
    "maxY": 9,
    "tileSize": 5
  },
  "combatants": [
    {
      "id": "pc_acheron",
      "name": "Acheron",
      "type": "player",
      "initiative": 16,
      "currentHp": 21,
      "maxHp": 21,
      "movementSpeed": 30,
      "movementRemaining": 10,
      "position": {"x": 2, "y": 7},
      "status": "alive"
    },
    {
      "id": "enemy_skeleton_1",
      "name": "Skeleton_1",
      "type": "enemy",
      "initiative": 12,
      "currentHp": 7,
      "maxHp": 13,
      "movementSpeed": 30,
      "movementRemaining": 30,
      "position": {"x": 11, "y": 6},
      "status": "alive"
    }
  ],
  "terrain": [
    {"x": 0, "y": 0, "type": "wall"},
    {"x": 3, "y": 5, "type": "difficult"},
    {"x": 3, "y": 2, "type": "hazard"}
  ],
  "obstacles": [
    {"x": 10, "y": 5, "kind": "wall"}
  ],
  "currentTurn": {
    "combatantId": "pc_acheron",
    "phase": "pc"
  }
}
```

`ui_state` example payload (frontend only, not persisted):

```json
{
  "mode": "measure",
  "selectedCombatantId": "pc_acheron",
  "measureStart": {"x": 5, "y": 3},
  "measureEnd": {"x": 11, "y": 3},
  "losStart": null,
  "losEnd": null,
  "aoePreview": null
}
```

Renderer contract:
- `renderMap(mapState, uiState)` is the only renderer entry point.
- `AsciiRenderer` and `CanvasRenderer` both consume the same `mapState` and `uiState`.
- Tactical math and validation stay in backend/shared helpers; renderer only draws.

Cross-plan alignment:
- Combat map uses the same renderer boundary defined in `plans/version-2/world-mapping.md`.
- Combat should be represented as `scope: "combat"` within shared map payload semantics.
- Shared map UI host (`Maps` tab) should be able to display local/module/world/combat scopes without parallel rendering stacks.
- Worldview graph semantics (`memory.db` node/edge tables) are shared infrastructure for non-combat map scopes; combat state remains encounter-authoritative.
- Read-only worldview graph viewer is diagnostic only and does not become a combat state write path.

## 5.4 Required changes in existing NEQ combat managers

This section defines what must be added to current combat code so mapping works with minimal disruption.

`core/managers/multi_pc_combat.py` (primary integration point):
- Extend `Combatant.metadata` and `PCCombatState.metadata` usage to carry spatial state reliably:
  - `position: {"x": int, "y": int}`
  - `movementSpeed: int`
  - `movementRemaining: int`
- During `initialize_turn_queue(encounter_data)`:
  - Read optional creature `position` and movement fields from encounter data.
  - Preserve backward compatibility by assigning safe defaults when fields are missing.
- Add facade helpers for map-aware state access:
  - `get_map_state(encounter_data) -> Dict[str, Any]`
  - `get_combatant_position(name) -> Optional[Dict[str, int]]`
  - `set_combatant_position(name, x, y) -> bool`
  - `reset_movement_for_actor(name) -> None`
- Add synchronization helpers:
  - Keep `_turns.turn_queue` and encounter creature spatial fields in sync after movement updates.
  - Ensure round and phase transitions do not wipe spatial metadata.
- Movement lifecycle rules:
  - On turn start, actor `movementRemaining` resets to `movementSpeed`.
  - On valid movement, decrement `movementRemaining` using shared distance/cost rules.
  - Never allow negative remaining movement.
- Scope boundary:
  - MultiPCCombatManager owns `combat` scope map state only.
  - Local/module/world exploration map scopes are handled by world mapping services (`plans/version-2/world-mapping.md`).

`core/managers/combat_manager.py` (orchestration point):
- Request and pass map-aware encounter state into multi-PC manager each combat tick.
- On combat command routing, allow map helper commands (measure/los/aoe preview hooks).
- Preserve existing initiative and enemy batch behavior unchanged.

`core/ai/action_handler.py` (encounter creation/update point):
- Add optional spatial defaults when creating encounters:
  - `gridBounds`, `terrain`, `obstacles`
  - per-creature optional `position`, `movementSpeed`, `movementRemaining`
- Continue fail-open behavior when map fields are absent.

`updates/update_encounter.py` (persistence/update point):
- Allow safe updates to creature `position` and movement fields.
- Keep current sync behavior for HP/status/conditions intact.
- Validate updated encounter against expanded schema.

`web/extensions/tabletop_socket_handlers.py` (payload emitter):
- Emit `map_state_response` (or extend existing initiative payload with `map_state`).
- Include combatants with positions, terrain, obstacles, bounds, and current turn metadata.

`web/templates/game_interface.html` + new renderer files:
- Add a map mount container and renderer mode controls.
- Phase 1 uses `AsciiRenderer`; later phases add `CanvasRenderer` against same contract.
- Keep initiative UI visible and authoritative during transition.

Testing updates required:
- Unit tests for movement budget and position sync in `scripts/test_multi_pc_combat.py`.
- Contract tests for socket `map_state` payload shape.
- Regression checks that no-map encounters still run with current initiative-only behavior.

---

## 6) Asset pipeline for PlaySCII-inspired look

Recommended pipeline:
1. Create tile/glyph concepts in PlaySCII (or similar ASCII art tooling).
2. Export sprite sheets/PNGs.
3. Import into NEQ static assets under versioned paths.
4. Use NEQ-controlled atlas mapping table (`tile_id -> sprite frame`).

Rules:
- Store source art and exported atlases with clear naming/versioning.
- Keep runtime decoupled from authoring tool format.
- Preserve fallback rendering if atlas missing.

---

## 7) Acceptance criteria

MVP acceptance (Phases 1-2):
1. Combatants have optional persisted map positions.
2. UI shows spatial info during active combat.
3. Distance and movement checks are deterministic and test-covered.
4. Existing non-map combat flow remains fully functional.
5. All additions are backward compatible with old encounter files.

Extended acceptance (Phases 3-4):
1. LOS and AoE previews match backend calculations.
2. Map panel is visually distinct and readable at tabletop distances.
3. Art style aligns with retro ASCII tactical direction.

---

## 8) Risks and mitigations

Risk: schema drift and fragile updates in live encounters.
- Mitigation: optional fields, strict validation, migration-safe defaults.

Risk: frontend complexity/regression in `game_interface.html`.
- Mitigation: isolate rendering logic in new JS/CSS files, thin hooks only.

Risk: tactical calculations diverge between client and server.
- Mitigation: server is authoritative; client previews reconcile against server responses.

Risk: performance degradation on large encounters.
- Mitigation: tile culling, layered caching, bounded overlay redraw.

---

## 9) Delivery recommendation

Recommended immediate build target:
- Implement Phase 1 + Phase 2 as the first milestone.

Reason:
- Delivers concrete tabletop utility quickly.
- Establishes stable data contracts needed for later visual polish.
- Avoids premature investment in heavy rendering before mechanics are reliable.
- Provides a reusable scaffold so canvas work is additive, not a restart.
- Keeps tactical combat mapping consistent with broader world mapping rollout.

---

## 10) Next execution steps

1. Implement encounter schema optional spatial fields.
2. Add backend map payload + ASCII map fallback output.
3. Add distance/movement helpers with focused tests.
4. Add map panel mount and mode controls in shared `Maps` tab UI host.
5. Lock renderer boundary (`map_state` + `ui_state` + `renderMap` contract).
6. Iterate visual polish toward PlaySCII-inspired style once tactical correctness is stable.
