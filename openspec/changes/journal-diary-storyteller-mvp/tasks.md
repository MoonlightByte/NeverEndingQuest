## 1. Memory DB and prompt scaffolding

- [x] 1.1 Add additive diary/cache migrations in `core/memory/memory_db.py` for `session_diary_entries`, `session_diary_state`, and `story_so_far_cache`.
- [x] 1.2 Export new diary/story helpers from `core/memory/__init__.py` and add any prompt scaffolding needed under `prompts/tabletop/` for compact diary-entry generation.
- [x] 1.3 Verify migration and prompt scaffolding with `python3 -m py_compile core/memory/memory_db.py core/memory/__init__.py` and a migration smoke check against a temp DB.

## 2. Diary service implementation

- [x] 2.1 Create `core/memory/session_diary.py` with world-sort-key helpers, bounded source assembly, and diary row serialization utilities.
- [x] 2.2 Implement `refresh_draft_if_stale(...)` so Start Game can create/update exactly one active draft row without duplicates.
- [x] 2.3 Implement `confirm_diary_for_save(...)` and `list_diary_entries(...)` with idempotent `save_id` behavior and deterministic fallback summary generation.
- [x] 2.4 Verify diary service behavior with `python3 -m py_compile core/memory/session_diary.py` plus focused tests covering single active draft, confirmed idempotency, and fallback generation.

## 3. Runtime integration hooks

- [x] 3.1 Update `updates/save_game_manager.py` to call `confirm_diary_for_save(...)` behind a fail-open `# TABLETOP MODE:` hook that preserves save success on diary failure.
- [x] 3.2 Update `web/web_interface.py` `handle_start_game()` to call `refresh_draft_if_stale(...)` behind a fail-open `# TABLETOP MODE:` hook that preserves normal game start behavior.
- [x] 3.3 Verify runtime hook safety with `python3 -m py_compile updates/save_game_manager.py web/web_interface.py` and targeted tests that force diary errors while asserting Save and Start Game still succeed.

## 4. Story compiler and download routes

- [x] 4.1 Create `core/memory/story_so_far_compiler.py` to load confirmed diary entries only, assemble storyteller prompt input, and generate long-form story text with deterministic fallback.
- [x] 4.2 Implement confirmed-fingerprint cache reuse and PDF rendering support in `core/memory/story_so_far_compiler.py`.
- [x] 4.3 Extend `web/routes/memory_routes.py` with `GET /api/journal/diary` and `GET /api/journal/story-so-far/pdf` using safe error responses.
- [x] 4.4 Verify compiler/routes with `python3 -m py_compile core/memory/story_so_far_compiler.py web/routes/memory_routes.py` and tests proving confirmed-only source selection, cache reuse, and safe failure behavior.

## 5. Journal UI integration

- [x] 5.1 Update `web/templates/game_interface.html` to add Quests/Diary tab controls while preserving current quest rendering behavior.
- [x] 5.2 Add Diary tab rendering for the draft card, confirmed timeline, and `Download the story so far...` action.
- [x] 5.3 Add frontend request/download handling and resilient button re-enable behavior for story download failures.
- [x] 5.4 Verify Journal UI behavior with `node --check` if extracted JS is touched, plus manual smoke confirming Quests remain intact and Diary renders draft/confirmed states correctly.

## 6. Test coverage and final verification

- [x] 6.1 Add `scripts/test_session_diary_mvp.py` covering migrations, draft refresh idempotency, confirmed `save_id` idempotency, and fail-open hook behavior.
- [x] 6.2 Add `scripts/test_story_so_far_pdf_mvp.py` covering confirmed-only story compilation, draft exclusion, cache reuse, and safe error paths.
- [x] 6.3 Run compile verification for all touched Python files and execute the new focused test suites.
- [x] 6.4 Perform manual smoke validation: Start Game creates/refreshes a draft, Save produces a confirmed entry, Quests tab still works, and story download excludes draft content.

SHOULD:
- Keep diary-entry generation prompt payloads compact and bounded to avoid slowing Start Game and Save paths.
- Keep explicit Exit checkpoint work lightweight and fail-open so shutdown remains reliable.
- Prefer additive UI logic and helper extraction over replacing existing Journal rendering code.
- Keep story compiler prompt assembly provider-agnostic by reusing the existing AI client/model selection helpers.

## 7. Exit auto-confirm follow-up plan

- [x] 7.1 Add additive checkpoint identity support in `core/memory/memory_db.py` and `core/memory/session_diary.py` so confirmed entries can distinguish `save` vs `exit` origins without duplicating the same exit checkpoint window.
- [x] 7.2 Implement `confirm_diary_for_exit(...)` in `core/memory/session_diary.py` so explicit Exit creates one idempotent confirmed checkpoint when new eligible source history exists after the last confirmed checkpoint, and clears/supersedes the active draft after promotion.
- [x] 7.3 Update `web/web_interface.py` `handle_user_exit()` to call `confirm_diary_for_exit(...)` behind a fail-open `# TABLETOP MODE:` hook that preserves shutdown success even when diary confirmation degrades.
- [x] 7.4 Add focused regression coverage proving explicit Exit creates one confirmed diary entry, repeated Exit retries do not duplicate canon rows, no-progress Exit creates nothing, and diary failure does not block shutdown.
- [ ] 7.5 Perform manual smoke validation: play without clicking Save, press explicit GUI Exit, restart with Start Game, confirm the Diary timeline now contains a confirmed entry and Story So Far can build from it without requiring a manual save.
