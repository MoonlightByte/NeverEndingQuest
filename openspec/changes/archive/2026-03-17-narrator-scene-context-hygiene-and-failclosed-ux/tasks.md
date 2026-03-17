## 1. Narrator Payload Hygiene

- [x] 1.1 Add narrator-only outbound payload helper(s) in `main.py` to sanitize the live DM message list without mutating canonical conversation history.
- [x] 1.2 Exclude historical assistant location summaries/chronicles and the full module atlas from the live narrator payload while preserving current location, recent raw turns, and mechanical truth surfaces.
- [x] 1.3 Add narrator-safe plot compaction so active/upcoming plot pressure remains visible while verbose completed-beat prose is removed from the live narrator payload.

## 2. Fail-Closed UX And Observability

- [x] 2.1 Update retry-exhaustion handling in `main.py` so the active UI receives an immediate, non-technical `[SYSTEM]` message while runtime control flow stays fail-closed.
- [x] 2.2 Add dedicated rejected-turn JSONL logging under `debug/quality_control/` with fail-open file-write handling and basic scene context.

## 3. Regression Coverage And Verification

- [x] 3.1 Extend `scripts/test_narrator_prompt_validation_refactor.py` (or add a focused companion test) with source-contract and behavior tests for narrator payload hygiene, player-facing retry exhaustion output, and rejected-turn logging wiring.
- [x] 3.2 Verify the change with `python3 -m py_compile main.py`, targeted narrator/validation tests, and exported-payload inspection confirming historical chronicles and atlas data are absent from the live narrator payload while current-scene context remains.

SHOULD: keep the first implementation local to `main.py` and avoid broad compression/history rewrites until this conservative slice is verified in live transcript replay.
