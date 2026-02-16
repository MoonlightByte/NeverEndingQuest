## 1. Migration and state model

- [ ] 1.1 Add additive migration for `session_diary_entries`, `session_diary_state`, and `story_so_far_cache` in `core/memory/memory_db.py`.
- [ ] 1.2 Add required indexes for status/world ordering, save idempotency, draft uniqueness, and confirmed fingerprint cache lookup.
- [ ] 1.3 Verify migration idempotency by initializing DB twice and confirming no schema/data loss errors.

## 2. Diary service implementation

- [ ] 2.1 Create `core/memory/session_diary.py` with world-time normalization helpers and sort key generation.
- [ ] 2.2 Implement `refresh_draft_if_stale(...)` with stale check, single-draft behavior, and checkpoint updates.
- [ ] 2.3 Implement `confirm_diary_for_save(...)` with `save_id` idempotency and confirmed checkpoint updates.
- [ ] 2.4 Implement deterministic fallback summary path for diary generation failures.

## 3. Save and Start Game integration

- [ ] 3.1 Update `updates/save_game_manager.py` to call `confirm_diary_for_save(...)` inside `create_save_game(...)` with guarded error isolation.
- [ ] 3.2 Add diary status metadata to save success path without changing save success semantics.
- [ ] 3.3 Update `web/web_interface.py` `handle_start_game()` to call `refresh_draft_if_stale(...)` after thread start in non-blocking failure-safe flow.

## 4. Story PDF compiler

- [ ] 4.1 Create `core/memory/story_so_far_compiler.py` for confirmed-only story source assembly.
- [ ] 4.2 Implement confirmed fingerprint cache lookup and regeneration logic.
- [ ] 4.3 Implement PDF render function and safe fallback/error behavior without mutating diary records.

## 5. API routes

- [ ] 5.1 Extend `web/routes/memory_routes.py` with `GET /api/journal/diary` returning draft + confirmed timeline payload.
- [ ] 5.2 Extend `web/routes/memory_routes.py` with `GET /api/journal/story-so-far/pdf` returning attachment download.
- [ ] 5.3 Ensure route registration remains correct in `web/web_interface.py` with merge-safe minimal hooks.

## 6. Journal UI integration

- [ ] 6.1 Update `web/templates/game_interface.html` to add Quests/Diary tab controls while preserving existing Quests rendering path.
- [ ] 6.2 Implement Diary panel rendering for optional draft card and confirmed timeline list in world-time order.
- [ ] 6.3 Add `Download the story so far...` button handler to fetch PDF endpoint and trigger browser download with loading/disabled state.

## 7. Validation and regression

- [ ] 7.1 Run compile checks: `python3 -m py_compile core/memory/memory_db.py core/memory/session_diary.py core/memory/story_so_far_compiler.py updates/save_game_manager.py web/routes/memory_routes.py web/web_interface.py`.
- [ ] 7.2 Add/extend tests (for example `scripts/test_session_diary_mvp.py`, `scripts/test_story_so_far_pdf_mvp.py`) covering draft refresh, save idempotency, and confirmed-only PDF source.
- [ ] 7.3 Run manual smoke: Start Game draft refresh, Save confirmation, exit-without-save restart behavior, Diary tab rendering, PDF download behavior.

## 8. Documentation and builder handoff

- [ ] 8.1 Update `plans/journal.md` links/references if implementation-specific details differ from approved MVP contract.
- [ ] 8.2 Add implementer notes in `openspec/changes/journal-diary-mvp-phase1/executor_prompts.md` with phase order and verification commands for Kimi execution.
