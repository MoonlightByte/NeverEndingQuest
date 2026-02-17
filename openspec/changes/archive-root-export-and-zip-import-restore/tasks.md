## 1. Root Archive Export Directory

- [x] 1.1 Add root export directory constant and helper path resolver in `updates/save_game_manager.py`.
- [x] 1.2 Update full-save zip generation path to write artifacts into `archive_exports/`.
- [x] 1.3 Update deterministic zip naming to include module + timestamp + save folder.

## 2. Full Save Payload and Listing Integration

- [x] 2.1 Ensure full-save success payload returns root export `zip_path` and archive metadata unchanged in shape.
- [x] 2.2 Keep essential save success payload unchanged (content-only legacy shape).
- [x] 2.3 Add archive zip catalog listing helper in `updates/save_game_manager.py` for `archive_exports/*.zip`.

## 3. Zip Preflight Validation and Secure Extraction

- [x] 3.1 Add zip preflight validator: required metadata, source module resolution, and envelope checks.
- [x] 3.2 Add traversal protection checks (`..`, absolute paths, invalid root entries).
- [x] 3.3 Add secure extract-to-temp staging helper and cleanup behavior.

## 4. Zip Restore Pipeline

- [x] 4.1 Add zip staging helper to place extracted save folder into canonical module save path.
- [x] 4.2 Add zip restore entrypoint in `updates/save_game_manager.py` that delegates to existing folder restore after staging.
- [x] 4.3 Preserve existing folder restore methods unchanged and backward compatible.

## 5. Web Integration (No New Top-Level Buttons)

- [x] 5.1 Add web action to list archive zips from root export folder.
- [x] 5.2 Add web action to restore from selected zip archive.
- [x] 5.3 Ensure error/success emits follow existing restore semantics and fail-closed behavior.

## 6. Load Dialog Wiring

- [x] 6.1 Extend existing load dialog model to include archive zip entries.
- [x] 6.2 Add minimal operator-visible archive row rendering (name, size, modified).
- [x] 6.3 Route archive row restore action to zip restore path while preserving folder restore controls.

## 7. Validation and Regression

- [x] 7.1 Compile gate: `python3 -m py_compile updates/save_game_manager.py web/web_interface.py utils/reset_campaign.py`.
- [x] 7.2 Positive smoke: full save creates zip in `archive_exports/`; reset; restore from zip succeeds.
- [x] 7.3 Negative smoke: malformed zip, missing metadata, traversal zip -> explicit restore failure.
- [x] 7.4 Regression smoke: essential save unchanged, folder restore unchanged.
