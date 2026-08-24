# The Map Tab

Both players (React at `/play`, legacy at `/`) have a **Map** tab in the
right-side panel: a hand-drawn, fog-of-war map of the party's current area,
rendered client-side by the vendored `mapper` library.

## Data flow

- Socket event `request_map_data` → `map_data_response`
  (`web/web_interface.py::handle_map_data_request`).
- The payload is built by `web/map_projection.py::project_map_payload` — the
  **spoiler security boundary**. Client-side fog is cosmetic; anything sent
  is readable in devtools, so unvisited rooms are redacted server-side: no
  `name`, no `type`, and no edges between two hidden rooms. Rooms count as
  revealed when `explorationState.status` is `visited`
  (`utils/path_encounter_analyzer.derive_location_exploration_state`, with
  legacy-module fallbacks) plus the party's current room (the engine marks
  rooms visited on departure). Keep any change to the payload inside that
  module, covered by `tests/test_map_data_projection.py`.
- Clients refresh on tab activation, on the standard 5s active-tab poll, and
  after each turn; the React side rides the hydration coordinator's
  revision/staleness machinery (`src/stores/world.ts::setMapData`).

## Vendored renderer

`web/frontend/src/vendor/mapper/` (React, imported as `mapper-lib`) and
`web/static/js/mapper/` (legacy) are **generated copies** of the standalone
`mapper` repo, stamped by `VENDORED.md` (source SHA + per-file hashes).
Never edit them here — change the mapper repo and run its
`tools/sync-into-game.js --dest <this repo>`. Shared client behavior that is
NEQ-specific (auto-fit, pan/zoom, current-room marker, reveal diffing) lives
in `web/frontend/src/components/sheet/useMapPanZoom.ts` and its vanilla-JS
port `web/static/js/mapper-glue.js`; keep the two in sync when changing
either.

The map's typeface (IM Fell English, OFL) is self-hosted
(`web/frontend/src/theme/fonts/`, `web/static/fonts/`) because hosted-mode
CSP has no route to Google Fonts; both clients call `createMap` with
`fontCss: false`.

## Known follow-ups

- Hosted hardening: generic error envelopes still use `str(e)` in the
  repo-wide idiom; consider scrubbing for hosted (`web_interface.py`).
- Cross-area exits (`areaConnectivity`) are deliberately not drawn (v1
  single-map model).
- Doors/locks (`accessType` in location files) are not yet surfaced on the
  map.
