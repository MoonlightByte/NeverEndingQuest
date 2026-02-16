## 1. Save Manager Global Catalog

- [ ] 1.1 Add global save discovery helper in `updates/save_game_manager.py` that scans `modules/*/saved_games/save_*` and normalizes metadata with `source_module`.
- [ ] 1.2 Add deterministic global sort by `save_timestamp` descending and preserve local module listing methods for compatibility.
- [ ] 1.3 Add additive metadata fields (`memory_package_present`, `source_module`) for each global list entry.

## 2. Cross-Module Restore Routing

- [ ] 2.1 Add restore target validator in `updates/save_game_manager.py` that accepts module + save folder and rejects invalid/non-canonical paths.
- [ ] 2.2 Add a cross-module restore entrypoint that delegates to the existing restore pipeline (backup, preflight, import, copy) to preserve safety invariants.
- [ ] 2.3 Keep legacy restore call path operational when only `saveFolder` is provided.

## 3. Web Action and UI Integration

- [ ] 3.1 Update `web/web_interface.py` `listSaves` action to return global catalog entries.
- [ ] 3.2 Update `web/web_interface.py` `restoreGame` action to accept and pass module-aware restore parameters.
- [ ] 3.3 Update `web/templates/game_interface.html` load dialog rendering to display source module and memory parity indicator and to send module-aware restore payload.

## 4. Validation and Regression Checks

- [ ] 4.1 Run `python3 -m py_compile updates/save_game_manager.py web/web_interface.py` and address syntax/runtime import issues.
- [ ] 4.2 Run manual smoke: save in module A, save in module B, restore A from GUI without manual terminal routing.
- [ ] 4.3 Run negative smoke: invalid module/folder restore payload fails cleanly with no state mutation.
