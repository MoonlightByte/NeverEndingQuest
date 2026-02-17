## 1. Appearance field scaffolding

- [x] 1.1 Add optional appearance fields to `schemas/char_schema.json` (`age`, `height`, `weight`, `eyes`, `skin`, `hair`) with backward-compatible constraints.
- [x] 1.2 Update defaults/normalization in `utils/character_creation_audit.py` for optional appearance fields.
- [x] 1.3 Update manual creation payload in `web/routes/tabletop_party_routes.py` and quick-create UI in `web/templates/partials/character_tabs.html` to accept appearance fields.
- [x] 1.4 Add appearance display wiring in Character Sheet UI (`web/templates/game_interface.html`).

## 2. Portrait service and create endpoint

- [x] 2.1 Add `core/toolkit/portrait_service.py` for prompt composition, normalization, generation call, and canonical file outputs.
- [x] 2.2 Add `POST /api/portrait/create` in `web/web_interface.py` (or route module) using portrait service.
- [x] 2.3 Ensure existing upload endpoint/path remains unchanged and interoperable with create output.

## 3. Character Sheet Upload/Create UX

- [x] 3.1 Update Character Sheet portrait control in `web/templates/game_interface.html` to expose `Upload / Create` action choice.
- [x] 3.2 Implement client-side create call + success refresh (cache-busted image URL).
- [x] 3.3 Ensure create failure displays safe UI error without breaking sheet interactions.

## 4. Missing-media warning throttle

- [x] 4.1 Add per-key missing-media warning throttle in `web/web_interface.py` media serving path.
- [x] 4.2 Add throttle settings in `model_config.py` and wire defaults.
- [x] 4.3 Keep first miss warning signal while suppressing repeated spam inside throttle window.

## 5. Allied-only auto-generation queue

- [x] 5.1 Add `web/extensions/missing_media_autogen.py` with async worker, key dedupe, and cooldown.
- [x] 5.2 Wire enqueue hook from `/media/npcs/<filename>` miss path in `web/web_interface.py` with `# TABLETOP MODE:` marker.
- [x] 5.3 Enforce policy gating: auto-gen enabled for allied companions only; non-allied NPCs and monsters disabled in MVP.

## 6. Validation and regression

- [x] 6.1 Add `scripts/test_pc_image_create_mvp.py` covering create API happy path/error path, allied auto-gen gating, and warning throttle behavior.
- [x] 6.2 Run compile checks:
  - `python3 -m py_compile core/toolkit/portrait_service.py web/extensions/missing_media_autogen.py web/web_interface.py web/routes/tabletop_party_routes.py utils/character_creation_audit.py`
- [x] 6.3 Run schema validation and smoke checks:
  - `python3 core/validation/validate_module_files.py`
  - manual smoke for Upload/Create, allied auto-heal, NPC->PC promotion continuity

## 7. Builder handoff

- [x] 7.1 Keep host hooks minimal and marked `# TABLETOP MODE:`.
- [x] 7.2 Ensure all new Python-visible text remains ASCII only.
- [x] 7.3 Document implementation notes and verification evidence in change discussion or follow-up logs.

## Summary

**Implementation Complete**: All tasks 1.1 through 7.3 have been completed and verified.

**Key Deliverables**:
- Appearance fields (age, height, weight, eyes, skin, hair) in schema, audit, creation, and display
- Portrait service (`core/toolkit/portrait_service.py`) with prompt composition and generation
- Create endpoint (`POST /api/portrait/create`) with safe error handling
- Character Sheet Upload/Create dual-action UI with cache-busted refresh
- Missing-media warning throttle (per-key, first-warn, suppress-repeats, re-emit after window)
- Allied-only auto-generation worker with dedupe and cooldown
- MVP test coverage (11 tests covering all major behaviors)

**Verification**:
- Compile checks: PASS
- Test execution: PASS (11 tests OK)
- ASCII-only: VERIFIED
- Host hooks: Marked with `# TABLETOP MODE:`
