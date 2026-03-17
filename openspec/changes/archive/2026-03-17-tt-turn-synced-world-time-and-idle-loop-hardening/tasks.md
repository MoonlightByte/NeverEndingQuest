## 1. Contract and Regression Locks

- [X] 1.1 Add spec deltas for new capabilities (`tt-web-input-idle-blocking`, `tt-turn-input-wall-clock-sync`) and the modified capability (`tt-transition-time-sync`).
- [X] 1.2 Add focused source/behavior tests covering idle web input blocking, first-turn timestamp seeding, elapsed-minute advancement, clamp behavior, malformed timestamp reset, and narrated-arrival inferred time sync; verify with `python3 -m py_compile <changed_test_files>`.

## 2. Web Idle Input Hardening

- [X] 2.1 Update `web/web_interface.py` so `WebInput.readline()` blocks for real queued input and no longer returns synthetic blank turns during idle waits; verify with `python3 -m py_compile web/web_interface.py`.
- [X] 2.2 Preserve existing status/stream recovery behavior without reintroducing empty-input churn; verify with the touched web/runtime tests.

## 3. Turn-Synced World Time Runtime

- [X] 3.1 Add a narrow helper module (for example `utils/turn_time_sync.py`) that parses persisted timestamps, computes elapsed whole minutes, clamps advancement, and fail-open resets malformed metadata; verify with `python3 -m py_compile utils/turn_time_sync.py`.
- [X] 3.2 Update `main.py` to apply the helper once per accepted non-empty player turn before normal turn processing, while preserving explicit `updateTime` semantics; verify with `python3 -m py_compile main.py utils/turn_time_sync.py`.
- [X] 3.3 Persist additive timestamp metadata in `party_tracker.json` via existing safe JSON helpers and ensure the first accepted turn seeds the marker without advancing world time; verify through the targeted runtime tests.

## 4. Travel / Arrival Time Parity

- [X] 4.1 Update `utils/travel_state_sync_guard.py` so safe narrated-arrival inferred commits include deterministic time advancement in the same effective commit cycle when explicit `updateTime` is absent; verify with `python3 -m py_compile utils/travel_state_sync_guard.py`.
- [X] 4.2 Update the `main.py` call site and regression expectations so inferred narrated-arrival actions preserve explicit `updateTime` precedence and avoid duplicate time injection; verify by running the touched travel/scene sync tests.

## 5. Verification

- [X] 5.1 Run targeted compile checks for all touched Python files and targeted regression scripts covering idle blocking, turn-sync wall clock behavior, travel time fallback, and scene-location sync.
- [X] 5.2 Run `openspec validate tt-turn-synced-world-time-and-idle-loop-hardening`.
- [X] 5.3 SHOULD perform one manual gameplay smoke pass: start web game, wait idle for several minutes, submit one turn, confirm no idle churn and bounded world-time advancement.
- [X] 5.4 SHOULD perform one narrated-arrival smoke pass proving inferred arrival updates both location and time without duplicate advancement.

## SHOULD Notes

- SHOULD keep the per-turn clamp in one constant so post-review tuning does not require hunting through multiple files.
- SHOULD log one concise ASCII `STATE_SYNC` line when wall-clock time is applied or when malformed metadata is reset.
