## 1. Save/Restore Memory Parity Wiring

- [x] 1.1 Add memory package export hook to `SaveGameManager.create_save_game()` in `updates/save_game_manager.py` using portability helpers.
- [x] 1.2 Persist memory package status and manifest summary fields into `save_metadata.json` during save creation.
- [x] 1.3 Add memory package import hook to `SaveGameManager.restore_save_game()` and gate restore success on import success for non-legacy saves.
- [x] 1.4 Implement deterministic legacy-save fallback path when memory package is absent and record fallback mode in restore metadata.

## 2. Worldline Lineage Metadata

- [x] 2.1 Define and persist lineage fields (`save_id`, `worldline_id`, parent/fork fields) in save metadata generation.
- [x] 2.2 Implement fork-on-first-save-after-restore behavior with persisted restore context that survives process restart.
- [x] 2.3 Update save listing/read paths to expose lineage and memory package status fields without breaking existing consumers.

## 3. Validation and Safety

- [x] 3.1 Add automated tests for save parity (package exists), restore parity (import rewinds), and corrupt-package failure behavior.
- [x] 3.2 Add automated tests for worldline invariants: sequential saves stay on same worldline, restore then save forks a new worldline.
- [x] 3.3 Add automated tests for legacy-save fallback semantics and metadata annotations.

## 4. Verification and Documentation

- [x] 4.1 Run targeted validation (`python3 -m py_compile` for touched modules and memory tests) and capture results in change notes.
- [x] 4.2 Update operator documentation (`plans/memory.md` and/or related docs) with Many Worlds save/restore behavior and lineage fields.

## 5. Hardening Addendum (Post-Review)

- [x] 5.1 Add restore preflight validation for memory package integrity/compatibility before backup, directory cleanup, or gameplay file copy.
- [x] 5.2 Exclude `memory_db_package/` from generic restore copy loop and keep package handling exclusively in managed import path.
- [x] 5.3 Eliminate duplicate validation work in restore path by validating once and reusing validated import path.
- [x] 5.4 Enforce explicit save outcome when memory parity export fails (when parity is enabled and DB exists).
- [x] 5.5 Make legacy fallback strict: propagate clean-init failure as restore failure instead of silent fallback success.
- [x] 5.6 Isolate memory parity tests from real runtime DB path and add regression tests for preflight atomicity and package-directory exclusion.

## 6. Follow-up Hardening (Test Isolation)

- [x] 6.1 Add `_patch_db_path()` context manager helper for proper test DB path isolation.
- [x] 6.2 Update `TestLegacySaveFallback` to use patched DB path during `_import_memory_package()` calls.
- [x] 6.3 Verify tests operate on temp directories only and do not mutate `data/memory.db`.
