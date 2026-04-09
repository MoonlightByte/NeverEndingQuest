## 1. Journal-first chapter source foundation

- [x] 1.1 Update `core/memory/session_diary.py` confirmed rebuild helpers to load and normalize `journal.json.entries` directly, preserving entry order as canonical chronology.
- [x] 1.2 Add deterministic journal-entry normalization helpers for date/time/location/location-id parsing and prose cleanup without changing draft Diary behavior.
- [x] 1.3 Verify normalized journal-entry loading with focused tests and `.venv/bin/python -m py_compile core/memory/session_diary.py`.

## 2. Chapter grouping and confirmed rebuild rewrite

- [x] 2.1 Implement deterministic chapter grouping over adjacent normalized journal entries, including exact duplicate collapse and conservative near-duplicate collapse.
- [x] 2.2 Rewrite `rebuild_diary_from_journal(...)` to build one confirmed row per chapter block with stable `journal_chapter:<n>` identities and retained source-range metadata.
- [x] 2.3 Verify chapter ordering, duplicate collapse, and source-range persistence with targeted chapter rebuild tests.

## 3. Chapter summary generation

- [x] 3.1 Add a chapter-summary generator that builds one descriptive player-facing summary from each grouped chapter packet.
- [x] 3.2 Add optional LLM chapter summarization after Python sanitization, with deterministic fallback when disabled, degraded, or rejected by output sanitization.
- [x] 3.3 Verify summary output stays artifact-free and descriptive with focused fallback and sanitization tests.

## 4. UI and runtime boundary preservation

- [x] 4.1 Keep draft Diary generation on the existing checkpoint/live-session path and verify confirmed chapter rebuild logic does not alter draft semantics.
- [x] 4.2 Keep confirmed Diary rendering title-free while preserving world date/time/location display metadata in the Journal modal.
- [x] 4.3 Verify Journal modal Diary rendering and route behavior with targeted UI/source-contract checks.

## 5. Live rebuild and verification

- [x] 5.1 Run compile checks and targeted diary regressions for chapter rebuild, draft stability, and UI rendering with `.venv/bin/python` for dependency-sensitive paths.
- [x] 5.2 Run the confirmed Diary rebuild against `data/memory.db` in preview mode with `.venv/bin/python` and inspect first/middle/last chapter entries for journal-order fidelity.
- [x] 5.3 Apply the confirmed Diary rebuild with `.venv/bin/python`, then manually smoke-test Journal modal readability and chapter usefulness against `journal.json` for review.

SHOULD: Add a dedicated chapter-summary prompt file if the existing checkpoint diary prompt proves too checkpoint-oriented for grouped journal chapter packets.
SHOULD: Preserve source-range metadata in a format that can later support a Story So Far migration to fuller journal-backed chapter packets.
