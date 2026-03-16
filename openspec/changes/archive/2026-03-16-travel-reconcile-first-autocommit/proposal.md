## Why

The current gametest build still treats legal narrated travel as invalid unless the LLM emits the exact explicit action plumbing. That reject-first model is causing visible immersive-play failures: the narrator describes movement that feels natural, Python or the validator rejects it, retries accumulate, and the player gets pulled out of the scene.

The minimum gametest goal is not to revert to upstream looseness. It is to keep narrator breathing room while adding stronger runtime reconciliation than upstream had. Travel is the first and most visible domain where this rebalance should happen: runtime should auto-commit legal narrated travel within Python topology/mechanical truth, preserve an in-transit/progress state when arrival is not exact, and block only impossible or ambiguous movement.

## What Changes

- Add reconcile-first travel auto-commit for clear travel-intent turns.
- Allow runtime to infer legal travel state from narration plus current authoritative packet truth when explicit `transitionLocation` is missing.
- Persist in-transit/progress state when narration clearly indicates movement toward a known destination without exact arrival.
- Preserve explicit `transitionLocation` as a preferred and fully supported path.
- Keep fail-closed behavior for impossible topology, same-location no-op transitions, and unresolved ambiguity that would commit false canon.
- Narrow travel-domain validation so legal/resolvable travel no longer enters brittle retry loops.
- Add transcript-driven regression coverage for explicit arrival, in-transit progress, ambiguity, and impossible travel.

Non-goals:
- No broad NPC scene-presence reconciliation in this slice.
- No Titans/EGO runtime integration in this slice.
- No event ledger in this slice.
- No planner/narrator split in this slice.
- No broad prompt rewrite outside parity wording if runtime tests require it.

## Capabilities

### New Capabilities
- `tt-travel-reconcile-first-autocommit`: runtime SHALL reconcile and auto-commit legal narrated travel using current authoritative world truth rather than rejecting turns solely for missing explicit travel actions.

### Modified Capabilities
- `tt-transition-time-sync`: travel-time synchronization requirements SHALL apply to effective committed travel state, including inferred travel commits and in-transit progress.
- `tt-narrator-validation-contract`: travel-intent validation SHALL prefer reconciliation over rejection when narrated movement is legal and safely resolvable.

## Impact

- Primary code:
  - `main.py`
  - `utils/travel_state_sync_guard.py`
  - `core/managers/location_manager.py`
  - `core/ai/action_handler.py`
- Likely shared truth dependency:
  - `utils/authoritative_state_packet.py` from `narrative-sovereignty-state-packet-foundation`
- Tests:
  - new travel reconciliation regression file in `scripts/`
  - targeted extensions to existing travel/validation tests
- Possible prompt parity touchpoints only if runtime tests show mismatch:
  - `prompts/system_prompt_compressed.txt`
  - `prompts/validation/validation_prompt_compressed.txt`

Risks and fallback:
- MUST preserve hard topology and same-location safety.
- MUST avoid false travel commits when destination remains ambiguous.
- SHOULD preserve explicit `transitionLocation` behavior as the clearest action path.
- If reconcile-first logic proves too broad, fallback is to keep explicit arrival auto-commit and defer richer in-transit handling while preserving tests.

Merge-safety / compatibility:
- Single-player and tabletop modes MUST continue to function.
- This change strengthens runtime reconciliation without replacing the current action schema.
- This change is intentionally more resilient than upstream prompt-strict/runtime-loose travel handling, but it is not a protocol break.
