## Kimi Builder Execution Prompts - journal-diary-mvp-phase1

Use this file as a practical execution guide while implementing tasks from `tasks.md`.

---

## Execution Contract

- MUST implement in task-group order (1 -> 8).
- MUST keep host edits merge-safe and mark host hooks with `# TABLETOP MODE:`.
- MUST keep Python-visible text ASCII-only.
- MUST preserve existing Quests behavior and existing save success semantics.
- MUST enforce confirmed-only source for story PDF export.
- SHOULD keep changes additive and avoid broad rewrites.

---

## Prompt 1 - Migration and Diary Service Foundation

Implement tasks 1.x and 2.x from `tasks.md`.

Scope:
- `core/memory/memory_db.py`
- `core/memory/session_diary.py` (new)
- `core/memory/__init__.py`

Requirements:
- Add additive migration for diary tables/indexes.
- Build draft/confirmed checkpoint logic with idempotency.
- Add fallback summary behavior when LLM fails.

Verify before moving on:
- `python3 -m py_compile core/memory/memory_db.py core/memory/session_diary.py core/memory/__init__.py`

---

## Prompt 2 - Save and Start Integrations

Implement tasks 3.x.

Scope:
- `updates/save_game_manager.py`
- `web/web_interface.py`

Requirements:
- Save confirms diary by `save_id` with non-fatal failure isolation.
- Start Game refreshes draft if stale; do not block `game_started` emission.

Verify before moving on:
- `python3 -m py_compile updates/save_game_manager.py web/web_interface.py`

---

## Prompt 3 - Confirmed-only Story PDF Compiler

Implement tasks 4.x.

Scope:
- `core/memory/story_so_far_compiler.py` (new)
- `core/memory/__init__.py`

Requirements:
- Build story source from confirmed entries only.
- Add minimal fingerprint-based cache reuse.
- Add fallback/error-safe generation path.

Verify before moving on:
- `python3 -m py_compile core/memory/story_so_far_compiler.py core/memory/__init__.py`

---

## Prompt 4 - API and UI Wiring

Implement tasks 5.x and 6.x.

Scope:
- `web/routes/memory_routes.py`
- `web/web_interface.py` (registration/hook only if needed)
- `web/templates/game_interface.html`

Requirements:
- Add `/api/journal/diary` and `/api/journal/story-so-far/pdf`.
- Add Diary tab while preserving Quests tab behavior.
- Add download button and browser file-download flow.

Verify before moving on:
- `python3 -m py_compile web/routes/memory_routes.py web/web_interface.py`

Manual checks:
- Journal opens and Quests still works.
- Diary renders draft + confirmed data.
- Download button initiates PDF download.

---

## Prompt 5 - Regression and Final Verification

Implement tasks 7.x and 8.x.

Scope:
- test scripts under `scripts/`
- docs/prompt notes updates

Requirements:
- Add tests for:
  - start refresh draft behavior
  - save confirmation idempotency
  - confirmed-only PDF data source
  - failure isolation on save/start
- Run full compile and targeted smoke checks.

Required final commands:
- `python3 -m py_compile core/memory/memory_db.py core/memory/session_diary.py core/memory/story_so_far_compiler.py updates/save_game_manager.py web/routes/memory_routes.py web/web_interface.py`
- test commands added in this change

---

## Smoke Checklist

1. Start game with stale history -> draft appears.
2. Save game -> confirmed entry appears for save_id.
3. Save again without new content -> no duplicate confirmed entry for same save_id logic path.
4. Exit without save after new activity -> next Start Game refreshes draft.
5. Story PDF download excludes draft and includes confirmed timeline only.
6. Save/start still work when diary LLM call fails (fallback or safe error path).
