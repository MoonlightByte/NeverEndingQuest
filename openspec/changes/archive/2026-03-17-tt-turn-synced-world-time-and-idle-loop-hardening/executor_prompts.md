# Executor Prompts: tt-turn-synced-world-time-and-idle-loop-hardening

## Execution Contract

MUST:
- Keep edits scoped to this change.
- Preserve explicit `updateTime` behavior outside the narrow inferred-arrival parity path.
- Keep host-file edits additive and marked with `# TABLETOP MODE:` comments.
- Use ASCII-only Python-visible log/output strings.
- Apply one anchored patch at a time in `main.py` and `web/web_interface.py`, then re-run `py_compile` before the next patch.
- Run targeted verification after each step before continuing.

SHOULD:
- Prefer one helper module for wall-clock math and timestamp persistence.
- Keep clamp values deterministic and centralized.
- Use source-contract tests for the idle-blocking path if direct runtime queue simulation is awkward.

## Prompt 1 - Contract Locks and Tests (Tasks 1.1-1.2)

Implement the spec deltas and regression locks before runtime edits.

Scope:
- `openspec/changes/tt-turn-synced-world-time-and-idle-loop-hardening/specs/**`
- targeted tests under `scripts/`

Required:
- Add new spec deltas for:
  - `tt-web-input-idle-blocking`
  - `tt-turn-input-wall-clock-sync`
- Modify the local `tt-transition-time-sync` delta to require inferred narrated-arrival time parity.
- Add/extend tests for:
  - idle web input does not synthesize blank turns
  - first accepted turn seeds timestamp with no time advance
  - elapsed whole-minute advancement on later turns
  - clamp behavior for large gaps
  - malformed timestamp resets safely
  - narrated-arrival inferred actions include deterministic time sync

Verify before continuing:
- `python3 -m py_compile <changed_test_files>`

## Prompt 2 - Web Idle Input Hardening (Tasks 2.1-2.2)

Remove synthetic blank-turn behavior from the web input path without breaking queue-based input delivery.

Scope:
- `web/web_interface.py`

Required:
- Update `WebInput.readline()` so it blocks until real queued input is available.
- Preserve status signaling and existing stream-recovery expectations.
- Do not return synthetic `"\n"` values merely because no input is available yet.

Constraints:
- Do not redesign broader socket or queue architecture.
- Keep the change narrow and compatible with the current web loop.

Verify before continuing:
- `python3 -m py_compile web/web_interface.py`
- run the touched idle-input tests

## Prompt 3 - Turn-Synced Wall-Clock Helper + Main Loop Integration (Tasks 3.1-3.3)

Implement bounded turn-sync world time using persisted wall-clock markers.

Scope:
- `utils/turn_time_sync.py` (new helper)
- `main.py`

Required:
- Add helper functions for timestamp parse, elapsed-minute computation, clamp, and safe application.
- Persist additive timestamp metadata in `party_tracker.json` using existing safe JSON helpers.
- First accepted non-empty player turn seeds timestamp only.
- Later accepted non-empty turns advance world time by elapsed whole minutes, clamped to the configured bound.
- Malformed or missing timestamp metadata must reset safely and not block play.
- Integrate helper in `main.py` once per accepted non-empty turn before standard turn processing.

Constraints:
- Do not alter explicit `updateTime` action handling.
- Do not add continuous background ticking.
- Keep logs concise and ASCII-only.

Edit Strategy:
- Apply one anchored patch at a time, then re-run py_compile before next patch.

Verify before continuing:
- `python3 -m py_compile utils/turn_time_sync.py`
- `python3 -m py_compile main.py utils/turn_time_sync.py`
- run the touched turn-sync tests

## Prompt 4 - Narrated-Arrival Time Parity (Tasks 4.1-4.2)

Keep inferred arrival commits synchronized across both location and time.

Scope:
- `utils/travel_state_sync_guard.py`
- `main.py`
- touched travel/scene sync tests

Required:
- When narrated-arrival reconcile-first commits a safe location update without explicit `updateTime`, infer deterministic time advancement in the same effective commit cycle.
- Preserve explicit `updateTime` precedence.
- Avoid duplicate time injection when explicit time already exists.
- Update call-site inputs and regression expectations accordingly.

Constraints:
- Reuse existing deterministic same-area/cross-area fallback semantics where possible.
- Keep reconcile-first ambiguity-safe and additive.

Verify before continuing:
- `python3 -m py_compile utils/travel_state_sync_guard.py main.py`
- run the touched travel/scene sync tests

## Prompt 5 - Final Verification (Tasks 5.1-5.4)

Run the focused verification gate for this change.

Required commands:
- `python3 -m py_compile web/web_interface.py main.py utils/turn_time_sync.py utils/travel_state_sync_guard.py <changed_test_files>`
- targeted regression scripts for:
  - idle input blocking
  - turn-sync wall-clock behavior
  - transition-time fallback
  - scene-location sync
- `openspec validate tt-turn-synced-world-time-and-idle-loop-hardening`

Report:
- files changed
- tests run
- compile/test/openspec results
- PASS/FAIL per gate
- any follow-up tuning recommendation (for example clamp value) kept separate from MUST results
