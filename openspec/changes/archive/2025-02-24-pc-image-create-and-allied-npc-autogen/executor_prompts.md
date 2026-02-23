Use this file as the builder execution scaffold for `tasks.md`.

---

## Execution Contract

- MUST execute in order: task groups 1 -> 10.
- MUST keep host file edits minimal and mark required hooks with `# TABLETOP MODE:`.
- MUST keep Python-visible text ASCII only.
- MUST preserve existing upload portrait behavior.
- MUST enforce allied-only auto-generation policy for MVP.
- SHOULD keep logic additive and extension-first.

---

## Prompt 1 - Appearance Fields Foundation

Implement tasks 1.x.

Scope:
- `schemas/char_schema.json`
- `utils/character_creation_audit.py`
- `web/routes/tabletop_party_routes.py`
- `web/templates/partials/character_tabs.html`
- `web/templates/game_interface.html`

Requirements:
- Add optional appearance fields and keep backward compatibility.
- Wire creation and display paths for appearance metadata.

Verify before moving on:
- `python3 -m py_compile utils/character_creation_audit.py web/routes/tabletop_party_routes.py`
- `python3 core/validation/validate_module_files.py`

---

## Prompt 2 - Portrait Service and API

Implement tasks 2.x.

Scope:
- `core/toolkit/portrait_service.py`
- `web/web_interface.py`

Requirements:
- Add portrait prompt/build/save service.
- Add `POST /api/portrait/create` using service.
- Keep upload flow untouched.

Verify before moving on:
- `python3 -m py_compile core/toolkit/portrait_service.py web/web_interface.py`

---

## Prompt 3 - Character Sheet Upload/Create UX

Implement tasks 3.x.

Scope:
- `web/templates/game_interface.html`

Requirements:
- Expose Upload/Create choice.
- Add create request + refresh UX.
- Keep safe errors on create failure.

Verify before moving on:
- Manual smoke: Upload still works.
- Manual smoke: Create updates portrait.

---

## Prompt 4 - Warning Throttle

Implement tasks 4.x.

Scope:
- `web/web_interface.py`
- `model_config.py`

Requirements:
- Add per-key warning throttle with configurable window.
- Preserve first warning signal.

Verify before moving on:
- `python3 -m py_compile web/web_interface.py`
- Manual smoke with repeated miss key.

---

## Prompt 5 - Allied Auto-Heal Worker

Implement tasks 5.x.

Scope:
- `web/extensions/missing_media_autogen.py`
- `web/web_interface.py`
- `model_config.py` (policy flags if not already added)

Requirements:
- Async queue worker with dedupe/cooldown.
- Enqueue only allied companions in MVP.
- Non-allied NPC and monster auto-gen disabled.

Verify before moving on:
- `python3 -m py_compile web/extensions/missing_media_autogen.py web/web_interface.py`
- Manual smoke for allied vs non-allied behavior.

---

## Prompt 6 - Tests and Final Verification

Implement tasks 6.x and 7.x.

Scope:
- `scripts/test_pc_image_create_mvp.py`
- all changed files

Requirements:
- Add focused tests and run compile/schema/smoke checks.
- Confirm NPC -> PC promotion image continuity.

Required final commands:
- `python3 -m py_compile core/toolkit/portrait_service.py web/extensions/missing_media_autogen.py web/web_interface.py web/routes/tabletop_party_routes.py utils/character_creation_audit.py`
- `python3 core/validation/validate_module_files.py`
- tests added in this change

---

## Smoke Checklist

1. Character Sheet Upload path unchanged.
2. Character Sheet Create path generates and refreshes portrait.
3. Allied NPC missing image enqueues one generation task and eventually resolves.
4. Non-allied NPC and monster missing images do not trigger auto-generation in MVP.
5. Repeated same-key misses do not flood warnings.
6. NPC -> PC promotion preserves portrait continuity by fallback chain.

---

## Prompt 7 - Reuse-First NPC Media Registration

Implement tasks 8.1-8.3 only.

Scope:
- `core/toolkit/portrait_service.py`
- `web/extensions/missing_media_autogen.py`
- `web/web_interface.py`

MUST:
- Reuse existing portrait files first; no provider call when reusable source exists.
- Materialize NPC media outputs into `/media/npcs` serving paths.
- Restrict enqueue to NPC image misses only.
- Keep host hooks minimal and mark required host edits with `# TABLETOP MODE:`.

SHOULD:
- Keep helper functions small and testable.
- Reuse existing normalization utilities.

Verify before moving on:
- `python3 -m py_compile core/toolkit/portrait_service.py web/extensions/missing_media_autogen.py web/web_interface.py`

---

## Prompt 8 - Canonical Dedupe, Policy Normalization, Frontend Cache TTL

Implement tasks 8.4-8.6 only.

Scope:
- `web/extensions/missing_media_autogen.py`
- `web/templates/game_interface.html`

MUST:
- Canonicalize dedupe key by NPC identity across image variants.
- Normalize allied matching consistently with filename normalization.
- Add TTL-based retry for missing-image cache.

SHOULD:
- Keep JS changes localized to image cache utility path.
- Preserve existing fallback order.

Verify before moving on:
- Manual smoke: generated/reused image appears without full page reload after TTL window.
- Manual smoke: repeated variant requests suppress duplicate generation.

---

## Prompt 9 - Regression Coverage and Final Validation

Implement tasks 8.7-8.8 only.

Scope:
- `scripts/test_pc_image_create_mvp.py`
- any touched files from Prompts 7-8

MUST:
- Add tests for reuse-first no-provider-call behavior.
- Add tests for dedupe across variant filenames.
- Add tests for image-only enqueue filtering and allied normalization.

Required final commands:
- `python3 -m py_compile core/toolkit/portrait_service.py web/extensions/missing_media_autogen.py web/web_interface.py`
- `python3 core/validation/validate_module_files.py`
- `python3 scripts/test_pc_image_create_mvp.py`

---

## Prompt 10 - Full Profile Modal + Portrait Create Enforcement

Implement tasks 9.1-9.9 only.

Scope:
- `core/toolkit/portrait_service.py`
- `web/web_interface.py`
- `web/templates/game_interface.html`
- `scripts/test_pc_image_create_mvp.py`

MUST:
- Character Sheet `Create` SHALL always open a full-profile modal.
- Modal SHALL include and prefill all required fields:
  - Appearance: `age`, `height`, `weight`, `eyes`, `skin`, `hair`
  - Personality/Background: `personality_traits`, `ideals`, `bonds`, `flaws`, `backgroundFeature.name`, `backgroundFeature.description`
- Create submit SHALL be blocked until all required fields are non-empty (trimmed).
- `/api/portrait/create` SHALL fail closed for incomplete profile payloads.
- Submitted profile values SHALL persist to character JSON before generation.
- Portrait prompt composition SHALL include personality/background context and sanitize/length-bound free-text fields.
- Upload portrait flow SHALL remain unchanged.

SHOULD:
- Use a clear submit label (for example `Save Profile + Create Portrait`).
- Keep modal code localized and reuse existing modal styles/patterns.
- Reuse `pc_manager` abstraction for character state updates.

Verify before moving on:
- `python3 -m py_compile core/toolkit/portrait_service.py web/web_interface.py`
- `python3 core/validation/validate_module_files.py`
- `python3 scripts/test_pc_image_create_mvp.py`
- Manual smoke:
  1. Click Create -> full-profile modal opens every time.
  2. Blank required field -> submit blocked.
  3. Submit valid fields -> portrait updates and stats reload shows saved edits.
  4. Upload path unchanged.

---

## Prompt 11 - Portrait Cache Coherence Across GUI Surfaces

Implement tasks 10.1-10.8 only.

Scope:
- `web/extensions/tabletop_socket_handlers.py`
- `web/web_interface.py`
- `web/templates/game_interface.html`
- `scripts/test_pc_image_create_mvp.py`

MUST:
- Backend SHALL emit deterministic portrait/image metadata for all GUI refresh payloads:
  - `player_data_response` (`dataType=stats`) -> `_portrait_slug`, `_portrait_version`
  - `initiative_data_response.combatants[]` -> `image_slug`, `image_version` for player/npc entries
  - `party_data_response.members[]` and `party_data_response.location_npcs[]` -> `image_slug`, `image_version`
- Frontend SHALL use one canonical normalization helper for portrait slugs aligned with backend normalization semantics.
- Frontend SHALL version portrait and thumbnail URLs using emitted version metadata.
- Successful upload/create SHALL invalidate both local image caches (`existingImageCache`, `missingImageCache`) for the affected slug.
- Successful upload/create SHALL immediately refresh Character Sheet, initiative, and party data without waiting for polling.
- Host-file edits MUST stay minimal and be marked with `# TABLETOP MODE:` where required.

SHOULD:
- Keep version-lookup logic centralized in one backend helper and reuse across payload builders.
- Keep frontend cache invalidation targeted per slug (avoid global cache clears).
- Preserve existing fallback order and polling loop behavior as compatibility fallback.

Verify before moving on:
- `python3 -m py_compile web/extensions/tabletop_socket_handlers.py web/web_interface.py`
- `python3 core/validation/validate_module_files.py`
- `python3 scripts/test_pc_image_create_mvp.py`
- Manual smoke:
  1. Upload PC portrait -> Character Sheet, initiative, and party strip refresh and remain stable.
  2. Create PC portrait -> no update-then-revert behavior across polling cycles.
  3. Missing allied NPC thumbnail resolves after worker write without hard reload.
  4. Apostrophe/hyphen name cases resolve to same portrait identity in all surfaces.

---

## Prompt 12 - Promotion Readiness Alignment (PC <-> NPC viability first)

Implement tasks 11.1-11.6 only.

Scope:
- `utils/character_creation_audit.py`
- `web/routes/tabletop_party_routes.py`
- `scripts/test_pc_image_create_mvp.py` (or promotion-focused regression file)

MUST:
- Add a deterministic profile-readiness helper for portrait-driving fields:
  - Appearance: `age`, `height`, `weight`, `eyes`, `skin`, `hair`
  - Personality/background: `personality_traits`, `ideals`, `bonds`, `flaws`, `backgroundFeature.name`, `backgroundFeature.description`
- Keep schema validation contract unchanged (do not make optional appearance fields globally required).
- Promotion preview/apply SHALL surface profile-readiness warnings but SHALL NOT fail promotion due to missing optional profile fields.
- Promotion apply SHALL seed missing appearance keys as empty strings for promoted records.
- Preserve existing promotion invariants:
  - same character file identity
  - `character_id` continuity
  - lifecycle role history append
  - `active_character` unchanged

SHOULD:
- Keep role-switch logic centralized in existing `pc_manager` helpers.
- Keep route responses additive and backward compatible.

Verify before moving on:
- `python3 -m py_compile utils/character_creation_audit.py web/routes/tabletop_party_routes.py`
- `python3 scripts/test_pc_image_create_mvp.py`
- Manual smoke: Manage Party -> Add Existing -> Promote for an NPC with missing appearance fields.

---

## Prompt 13 - NPC Prompt Enrichment After Readiness Alignment

Implement tasks 12.1-12.6 only.

Scope:
- `web/extensions/missing_media_autogen.py`
- `core/toolkit/portrait_service.py`
- `web/web_interface.py` (only if minimal hook changes are required)
- `scripts/test_pc_image_create_mvp.py`

MUST:
- Allied NPC auto-generation SHALL hydrate character context from canonical character state before provider generation.
- If canonical character state is unavailable, fallback SHALL use party role/name hints.
- Generation callback SHALL pass hydrated context to `generate_and_save_portrait(...)`.
- Prompt composition SHALL include bounded role/class-consistent anchors when available.
- Reuse-first flow, allied-only gating, dedupe/cooldown, and non-blocking miss path MUST remain intact.

SHOULD:
- Keep context hydration helper testable and isolated from request path logic.
- Keep prompt additions concise and deterministic.

Verify before moving on:
- `python3 -m py_compile core/toolkit/portrait_service.py web/extensions/missing_media_autogen.py web/web_interface.py`
- `python3 scripts/test_pc_image_create_mvp.py`
- Manual smoke: allied NPC miss generation uses role/class-consistent portrait cues.
