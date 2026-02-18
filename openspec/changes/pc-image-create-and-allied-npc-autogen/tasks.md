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

## 8. NPC media registration hardening (reuse-first, no extra provider calls)

- [x] 8.1 Add reuse-first media materialization helper in `core/toolkit/portrait_service.py`:
  - Input: NPC identity + optional module context.
  - Reuse existing portrait sources first (`web/static/portraits/<name>.png`, `modules/<module>/portraits/<name>.png`).
  - Output required NPC media variants:
    - `modules/<module>/media/npcs/<name>.jpg`
    - `modules/<module>/media/npcs/<name>_thumb.jpg`
    - `web/static/media/npcs/<name>.jpg` (fallback mirror)
    - `web/static/media/npcs/<name>_thumb.jpg` (fallback mirror)
  - MUST NOT call provider when reusable source exists.

- [x] 8.2 Update `web/extensions/missing_media_autogen.py` generation callback to:
  - Attempt reuse-first materialization before any provider generation.
  - Only call provider if no reusable source exists.
  - Log reuse vs generate path with ASCII-only messages.

- [x] 8.3 Restrict enqueue trigger in `web/web_interface.py` to NPC image misses only:
  - Allow `.jpg`, `.jpeg`, `.png`, `_thumb.jpg`.
  - Skip `_video.mp4` and non-image keys.

- [x] 8.4 Canonicalize dedupe key in `web/extensions/missing_media_autogen.py`:
  - Normalize to NPC identity key (`npcs/<normalized_name>`) across `.jpg/.png/_thumb` variants.

- [x] 8.5 Normalize allied-policy matching with shared filename normalization logic:
  - Ensure `party_tracker.json` names and requested media filenames map to same canonical key.

- [x] 8.6 Add frontend stale-miss recovery in `web/templates/game_interface.html`:
  - Replace permanent missing-image cache with TTL-based entries.
  - Retry previously missing URLs after TTL expiration.

- [x] 8.7 Add targeted regressions in `scripts/test_pc_image_create_mvp.py`:
  - Reuse-first no-provider-call path.
  - Canonical dedupe across `_thumb` and full variants.
  - Allied name normalization consistency.
  - Enqueue image-only filter behavior.

- [x] 8.8 Run verification:
  - `python3 -m py_compile core/toolkit/portrait_service.py web/extensions/missing_media_autogen.py web/web_interface.py` - PASS
  - `python3 core/validation/validate_module_files.py` - PASS (ran with venv)
  - `python3 scripts/test_pc_image_create_mvp.py` - PASS (20 tests OK with venv)

## 9. Portrait Create full-profile modal and enforcement

- [ ] 9.1 Expand portrait prompt composition in `core/toolkit/portrait_service.py` to include:
  - `personality_traits`
  - `ideals`
  - `bonds`
  - `flaws`
  - `backgroundFeature.name`
  - `backgroundFeature.description`
  - MUST sanitize and length-bound free-text fields before adding to prompt.

- [ ] 9.2 Update `POST /api/portrait/create` in `web/web_interface.py` to accept profile payload:
  - `appearance`: `age`, `height`, `weight`, `eyes`, `skin`, `hair`
  - `personality`: `personality_traits`, `ideals`, `bonds`, `flaws`
  - `backgroundFeature`: `name`, `description`

- [ ] 9.3 Add backend fail-closed validation in `web/web_interface.py` for portrait create:
  - MUST require all twelve profile fields above to be non-empty (trimmed).
  - MUST return safe structured error when any required field is empty.
  - MUST preserve upload behavior unchanged.

- [ ] 9.4 Persist submitted modal profile fields to character JSON before generation:
  - Use existing character persistence utilities (`pc_manager` abstraction path) when possible.
  - Preserve backward compatibility for existing character files.

- [ ] 9.5 Implement always-open full-profile modal in `web/templates/game_interface.html` for `Create`:
  - Modal opens every time player clicks Character Sheet portrait `Create`.
  - Modal pre-fills all profile fields from current character data.
  - Modal includes sections:
    - `Appearance`
    - `Personality and Background`

- [ ] 9.6 Enforce modal submit behavior in `web/templates/game_interface.html`:
  - MUST block submit until all required fields are non-empty.
  - MUST submit full profile payload to `/api/portrait/create`.
  - SHOULD label submit action clearly (for example, `Save Profile + Create Portrait`).

- [ ] 9.7 Refresh UX after create success:
  - Refresh portrait image with cache-busted URL.
  - Reload character stats so saved profile fields render immediately.
  - Keep safe error handling for provider/network failures.

- [ ] 9.8 Add regressions in `scripts/test_pc_image_create_mvp.py`:
  - Prompt includes personality/background fields when present.
  - Create API rejects missing required profile fields.
  - Create API persists profile fields before generation.
  - Existing upload/create baseline behavior remains compatible.

- [ ] 9.9 Run verification:
  - `python3 -m py_compile core/toolkit/portrait_service.py web/web_interface.py`
  - `python3 core/validation/validate_module_files.py`
  - `python3 scripts/test_pc_image_create_mvp.py`

## Summary

**Implementation Status**:
- Tasks 1.1 through 7.3: completed and verified.
- Tasks 8.1 through 8.8: completed and verified (reuse-first NPC media registration hardening).
- Tasks 9.1 through 9.9: pending (full-profile modal + enforcement for portrait create).

**Key Deliverables**:
- Appearance fields (age, height, weight, eyes, skin, hair) in schema, audit, creation, and display
- Portrait service (`core/toolkit/portrait_service.py`) with prompt composition and generation
- Create endpoint (`POST /api/portrait/create`) with safe error handling
- Character Sheet Upload/Create dual-action UI with cache-busted refresh
- Missing-media warning throttle (per-key, first-warn, suppress-repeats, re-emit after window)
- Allied-only auto-generation worker with dedupe and cooldown
- Reuse-first NPC media materialization (no provider call when portrait exists)
- Canonical identity-based dedupe across filename variants
- Shared normalization for allied companion matching
- TTL-based frontend missing-image cache (30 second expiry)
- Planned: always-open full-profile modal for portrait create with required profile completion
- Test coverage (20 tests covering all major behaviors)

**Verification**:
- Compile checks: PASS (all 3 files)
- Test execution: PASS (20 tests OK with venv)
- Schema validation: PASS (ran with venv)
- ASCII-only: VERIFIED
- Host hooks: Marked with `# TABLETOP MODE:`
