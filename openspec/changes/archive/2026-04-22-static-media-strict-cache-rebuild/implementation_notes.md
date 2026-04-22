## Implementation Notes

### What landed

1. **Strict-cache audit/rebuild core** (`core/toolkit/pack_manager.py`)
   - Added active-pack resolution that supports both `active_pack` and `active_packs` payloads.
   - Added dry-run audit output for `web/static/media/{npcs,monsters}`:
     - live files
     - active-pack source files
     - orphaned files
     - collisions
   - Added backup snapshot path (`graphic_packs/live_backup_*`) before destructive rebuild.
   - Added clear-and-repopulate rebuild path for static NPC/monster folders from active packs only.

2. **Toolkit API surface** (`web/web_interface.py`)
   - Added `GET /api/toolkit/static-cache/audit`.
   - Added `POST /api/toolkit/static-cache/rebuild` with `dry_run`, `create_backup`, and optional `active_packs` override.
   - Updated pack activation path to use strict-cache rebuild flow rather than additive static copy logic.

3. **Operator docs and CLI**
   - Added concise operator guidance: `docs/operations/static-media-strict-cache.md`.
   - Added maintenance CLI: `scripts/static_media_strict_cache.py`.

4. **Regression coverage**
   - Added strict-cache tests: `scripts/test_static_media_strict_cache.py`.
   - Added publishability guardrail regression:
     - `scripts/test_audit_module_publishability.py::test_shared_static_fallback_does_not_override_module_local_media_debt`

### Verification run

- `.venv/bin/python -m py_compile core/toolkit/pack_manager.py web/web_interface.py scripts/static_media_strict_cache.py scripts/test_static_media_strict_cache.py scripts/test_audit_module_publishability.py` -> PASS
- `.venv/bin/python scripts/test_static_media_strict_cache.py` -> PASS (3 tests)
- `.venv/bin/python scripts/test_audit_module_publishability.py` -> PASS (10 tests)
- `.venv/bin/python scripts/static_media_strict_cache.py --json` -> PASS (dry-run report produced with orphan/collision classification)

### Notes on scope

- Runtime lookup order remains unchanged (module-first, then fallback).
- Sibling static folders (e.g., `videos`, `environment`, `class_portraits`) remain out of scope and untouched.
- Publishability remains module-local; shared static fallback is not treated as debt resolution.
