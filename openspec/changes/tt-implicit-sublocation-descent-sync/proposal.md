## Why

A live runtime gap still allows the narrator to move the party from an authored parent room into an authored lower sublocation without committing canonical location state when the prose is directional rather than destination-named. In Night of the Restless Dead, the party can descend through the altar crevice, fight in the catacombs, and still restart upstairs because persisted location truth never left `NIG02`.

This needs fixing now because it creates restart drift, encounter anchoring drift, and extra player repair work in live play even when the narration itself is already correct. The existing DM adjudication fallback is excellent UX, but it should remain a fallback for recovery rather than the primary path that repairs missing runtime state sync.

## What Changes

- MUST add a deterministic reconcile-first runtime path for implicit same-module sublocation descent when scene evidence clearly establishes movement into one uniquely resolvable authored adjacent lower location and no explicit location action already exists.
- MUST ensure inferred location commit applies before same-turn encounter creation so combat state, encounter IDs, and restart truth anchor to the correct sublocation.
- MUST preserve fail-open behavior for ambiguous, multi-target, or progress-only prose so runtime does not guess a false canonical room.
- MUST preserve direct DM adjudication and drift-question behavior; the system SHALL continue to support players asking the DM to explain or repair a mismatch.
- SHOULD support additive authored transition-hint metadata for lock cases like `NIG02 -> NIG03` so modules can expose deterministic scene cues without widening generic heuristics.
- SHOULD add transcript-driven regression coverage for the cathedral descent bug, same-turn descent-plus-combat anchoring, and ambiguity fail-open behavior.

Non-goals:
- MUST NOT replace or weaken explicit `transitionLocation` handling.
- MUST NOT introduce a broad fuzzy scene guesser for arbitrary location prose.
- MUST NOT redesign cross-module travel or generic startup recovery in this change.
- MUST NOT remove the current DM-facing repair UX for state drift questions.

## Capabilities

### New Capabilities
- `tt-implicit-sublocation-descent-sync`: deterministic runtime reconciliation for unnamed but clearly established descent or entry into one authored adjacent sublocation.

### Modified Capabilities
- `tt-travel-reconcile-first-autocommit`: extend clear-travel reconciliation to cover narrow same-module sublocation descent when one adjacent target is uniquely provable.
- `tt-authoritative-same-module-transition`: require same-turn inferred sublocation commits to remain bounded by authored topology and explicit action precedence.

## Impact

- Primary code likely affected:
  - `main.py`
  - `utils/travel_state_sync_guard.py`
  - possibly the action ordering path that processes inferred location updates before `createEncounter`
  - transcript and runtime regression suites around scene/location/combat sync
- Primary module lock case:
  - `modules/Night_of_the_Restless_Dead/areas/NIG001.json`
- Merge safety:
  - Host-file edits SHOULD stay limited to existing TABLETOP MODE reconciliation hooks and remain marked with `# TABLETOP MODE:` comments.
- SP/MP compatibility:
  - The fix MUST remain safe in both single-player and tabletop modes because canonical location truth is shared runtime state.
- Rollout risk:
  - Main risk is over-committing location from vivid but non-unique scene prose.
  - Mitigation: inference MUST require one uniquely resolvable adjacent authored target and SHALL fail open otherwise.
- Fallback strategy:
  - If one canonical target cannot be proven, runtime SHALL keep current behavior and allow the existing DM adjudication recovery path to resolve the mismatch explicitly.
