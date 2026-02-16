Use this file as the builder execution scaffold for `tasks.md`.

---

## Execution Contract

- MUST execute in order: task groups 1 -> 7.
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
