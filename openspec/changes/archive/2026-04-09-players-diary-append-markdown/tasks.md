## 1. Runtime artifact foundation

- [X] 1.1 Add canonical gameplay/runtime storage paths for the confirmed players diary markdown artifact and its separate bookmark file under `data/`.
- [X] 1.2 Add safe load/write helpers for the confirmed players diary markdown artifact and bookmark state using atomic file operations where appropriate.
- [X] 1.3 Verify runtime path and helper behavior with `.venv/bin/python -m py_compile` and focused tests.

## 2. Append-based confirmed diary generation

- [X] 2.1 Implement append-mode confirmed diary generation that reads `journal.json`, computes the unprocessed journal delta from the bookmark, and reads only a bounded tail of the existing diary for style continuity.
- [X] 2.2 Add an append prompt contract explicitly targeting the UX quality demonstrated by the reference example in `Local_Docs/diary.md` while keeping `Local_Docs` out of gameplay/runtime storage.
- [X] 2.3 Ensure append generation appends only new markdown chronicle content, never rewrites prior diary content, and does not advance the bookmark on failure.
- [X] 2.4 Add focused tests for no-op when no new journal entries exist, successful append behavior, bounded context behavior, and bookmark safety on failure.

## 3. Full rebuild repair mode

- [X] 3.1 Implement a full rebuild mode that regenerates the complete confirmed players diary markdown artifact from all of `journal.json`.
- [X] 3.2 Ensure rebuild mode atomically replaces the diary artifact and resets the bookmark to the latest journal entry index only on success.
- [X] 3.3 Add focused tests for rebuild correctness, artifact replacement safety, and bookmark reset behavior.

## 4. GUI integration

- [X] 4.1 Add a dedicated route to return the confirmed players diary markdown artifact for the Journal GUI.
- [X] 4.2 Update the Journal GUI to render the confirmed players diary markdown artifact directly, keeping any draft/live-session diary surface separate.
- [X] 4.3 Verify the GUI route/rendering contract with focused UI/source tests.

## 5. Verification and operator workflow

- [X] 5.1 Document and use `.venv/bin/python` for all dependency-sensitive append/rebuild/verification commands in this change.
- [X] 5.2 Run targeted append/rebuild/GUI tests with `.venv/bin/python`.
- [X] 5.3 Perform a manual smoke pass that confirms the in-game confirmed Diary feels materially closer to the reference example in `Local_Docs/diary.md` than to the prior DB-backed diary summaries.

SHOULD: Keep the implementation deliberately simple and artifact-first; do not reintroduce a DB-heavy confirmed diary model for this UX surface.
SHOULD: Reserve full rebuild as a repair/reset tool rather than the normal update path.
