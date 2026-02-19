# Web Interface TT Merge Refactor Plan

Date: 2026-02-12
Status: Completed (increments 1-9 implemented)

## Goal

Reduce divergence from upstream in `web/web_interface.py` and `web/templates/game_interface.html` while preserving TABLETOP MODE behavior and keeping clear merge-safe hooks.

## Completed Increments

### Increment 1 - Frontend ownership cleanup

- Removed duplicate TT global function ownership from `web/templates/game_interface.html` and kept ownership in `web/static/js/tabletop_mode.js`.
- Reused existing socket in TT JS instead of always creating a second connection.

Key files:
- `web/templates/game_interface.html`
- `web/static/js/tabletop_mode.js`

### Increment 2 - Party/creation route extraction

- Extracted `/api/party*` and TT character creation endpoints from host file to dedicated module.
- Added thin registration hook in host file.

Key files:
- `web/routes/tabletop_party_routes.py`
- `web/routes/__init__.py`
- `web/web_interface.py`

### Increment 3 - Browser settings route extraction

- Extracted `/api/settings/browser` GET/POST endpoints.
- Host file now uses registration hook.

Key files:
- `web/routes/browser_settings_routes.py`
- `web/web_interface.py`

### Increment 4 - Character sheet PDF extraction

- Moved heavy PDF export implementation out of host file.
- Kept host route as thin wrapper for compatibility.

Key files:
- `web/routes/character_sheet_routes.py`
- `web/web_interface.py`

### Increment 5 - Live monitor + marker parsing extraction

- Extracted live chat monitor setup/wrapper to extension module.
- Consolidated `[skipTTS]` + `[prefill:...]` parsing into shared utility and reused in all WebOutputCapture paths.

Key files:
- `web/extensions/live_chat_monitor.py`
- `web/output_markers.py`
- `web/web_interface.py`

### Increment 6 - Party/initiative socket handler extraction

- Extracted `request_party_data` and `request_initiative_data` logic to extension module.
- Kept host socket handlers as thin wrappers.

Key files:
- `web/extensions/tabletop_socket_handlers.py`
- `web/web_interface.py`

### Increment 7 - Additional socket extraction

- Extracted `request_plot_data` and `request_storage_data` logic from host file to extension module.
- Kept host socket handlers as thin wrappers.

Key files:
- `web/extensions/tabletop_socket_handlers.py`
- `web/web_interface.py`

### Increment 8 - WebOutputCapture filter dedupe

- Consolidated repeated debug-line filtering marker list into one shared helper in host file.
- Replaced duplicate `any(marker in clean_line ...)` blocks with helper calls.

Key files:
- `web/web_interface.py`

### Increment 9 - Emit wrapper hardening

- Hardened live chat monitor wrapper lifecycle in extension module.
- Added idempotent setup behavior to prevent double-wrapping `socketio.emit`.
- Added optional teardown helper and documented hook contract in extension docstring.

Key files:
- `web/extensions/live_chat_monitor.py`
- `web/web_interface.py`

## Remaining Increments

None. Increments 1-9 are complete.

## Validation Checklist (run after each increment)

1. `python3 -m py_compile` on changed files.
2. Grep checks to ensure host wrappers remain thin and extracted functions are in extension/route modules.
3. Verify no duplicate frontend TT function ownership in template and TT JS.
4. Manual smoke checks in UI:
   - party tabs and active PC switching
   - party modal add/remove/create
   - initiative panel updates
   - chat monitor logging
   - TTS skip/prefill behavior

## Rollback Strategy

- Keep each increment in isolated commit scope.
- If regression occurs, revert only the affected increment module/hook pair.
- Do not revert unrelated TT behavior or upstream structures.

### Rollback Map (Increment-Specific)

- Increment 7 rollback:
  - Revert extraction in `web/extensions/tabletop_socket_handlers.py` for `handle_plot_data_request_impl` and `handle_storage_data_request_impl`.
  - Restore previous inline handler bodies in `web/web_interface.py` for `request_plot_data` and `request_storage_data`.
  - Validate: `python3 -m py_compile web/web_interface.py web/extensions/tabletop_socket_handlers.py`.

- Increment 8 rollback:
  - Revert helper `should_filter_to_debug_output()` and `WEB_OUTPUT_DEBUG_FILTER_MARKERS` in `web/web_interface.py`.
  - Restore the two prior inline marker lists in `WebOutputCapture.write()`.
  - Validate: `python3 -m py_compile web/web_interface.py`.

- Increment 9 rollback:
  - Revert idempotent lifecycle constants and teardown helper in `web/extensions/live_chat_monitor.py`.
  - Keep host hook unchanged (`setup_live_chat_monitor(socketio)` call in `web/web_interface.py`).
  - Validate: `python3 -m py_compile web/web_interface.py web/extensions/live_chat_monitor.py`.

### Safe Order

- Roll back in reverse order if multiple regressions are suspected: 9 -> 8 -> 7.
- Re-test after each rollback step (socket events, chat monitor logging, TTS skip/prefill behavior).

## Session Resume Prompt

Use this in a fresh session:

"Continue implementation from `plans/web_interface_tt_merge_refactor.md`. Execute Increment 7 only, keep host handlers as thin wrappers, run py_compile and grep validation, then report changed files and risk notes."
