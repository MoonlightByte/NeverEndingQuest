## Why

A live gametest bug still allows narration and NPC scene presence to advance into Hermit Maelo's refuge while the canonical party location remains stuck at the prior node. The GUI top bar is only exposing the real problem: runtime never commits party location when arrival is clearly narrated into a known location but `transitionLocation` is omitted.

## What Changes

- MUST add a narrow reconcile-first path for explicit narrated arrival into one known in-module location.
- MUST infer and apply party location commit when narration clearly places the party at that location and no explicit location action already exists.
- MUST extend authoritative packet topology so runtime can safely resolve known locations across the active module, not only the current area.
- MUST keep fail-open behavior for ambiguous, progress-only, or non-unique scene narration.
- SHOULD add transcript-driven regression coverage using the Hermit's Refuge arrival bug as the lock case.
- SHOULD keep the implementation localized to narrator validation/runtime reconciliation and avoid prompt-stack expansion unless runtime parity demands it.

Non-goals:
- No event ledger or Titans work.
- No broad fuzzy scene resolver.
- No cross-module travel redesign.
- No replacement of explicit `transitionLocation` flow when it is already present.

## Capabilities

### New Capabilities
- `tt-narrated-location-arrival-sync`: deterministic reconcile-first commit for explicit narrated arrival into one known location.

### Modified Capabilities
- `tt-authoritative-state-packet-foundation`: reachable topology context expands to include the module-level location catalog required for safe cross-area arrival reconciliation.

## Impact

- Primary code likely affected:
  - `main.py`
  - `utils/travel_state_sync_guard.py`
  - `utils/authoritative_state_packet.py`
- Primary tests likely affected:
  - new transcript lock for Hermit's Refuge arrival
  - existing travel and packet regression suites
- SP/MP impact:
  - MUST remain compatible with single-player and tabletop modes because location truth is shared runtime state.
- Rollout risk:
  - Main risk is over-committing location from vague scene prose.
  - Fallback is to keep the heuristic narrow and fail open when narration is not uniquely resolvable.
