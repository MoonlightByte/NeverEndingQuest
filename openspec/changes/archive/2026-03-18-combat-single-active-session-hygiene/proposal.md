## Why

Recent live play exposed a combat-session hygiene regression after the narrator scene-context cleanup work: the runtime ended up with one encounter still marked active in `party_tracker.json` while a second encounter and combat history were created for the same Bandit Trail scene. The result was user input bouncing between stale and fresh combat state, producing repeated `Initiative pending` prompts even after `/init` had already locked the winner.

This change is needed now because the existing `/init` gate behavior was stable before the recent cleanup pass, so the safest fix is to harden single-active-combat ownership rather than widen prompt logic further.

## What Changes

### MUST
- Add a single-active-combat ownership contract so tabletop combat startup cannot create or run a second active encounter while another unresolved encounter already owns input.
- Keep durable combat ownership coherent across `party_tracker.json`, runtime combat-loop startup, and combat conversation history metadata.
- Fail closed with an immediate non-technical `[SYSTEM]` message plus debug logging when duplicate combat startup or stale ownership drift is detected.
- Preserve current successful `/init`, `/att`, `/end`, resume, and single-player combat behavior when only one valid encounter is active.

### SHOULD
- Keep the first implementation narrow and local to `core/ai/action_handler.py`, `core/managers/combat_manager.py`, and minimal control-flow wiring if needed.
- Prefer additive guards and explicit diagnostics over broad combat-flow rewrites.
- Reuse existing safe JSON/state helpers and existing combat logging surfaces before introducing new storage or background cleanup systems.

### Non-Goals
- No prompt-contract rewrite for combat action grammar.
- No redesign of two-group initiative rules or opening-batch marker behavior.
- No archive/spec sync for the unfinished narrator hygiene change.
- No automatic encounter merge or cross-file state repair beyond deterministic active-session ownership enforcement.

## Capabilities

### New Capabilities
- `tt-combat-single-active-session`: ensure exactly one unresolved tabletop combat encounter owns facilitator input, startup, and combat-history identity at a time.

### Modified Capabilities
- `tt-combat-phase-sync`: strengthen runtime guarantees so initiative and phase flow remain bound to the currently owned encounter instead of drifting to a stale or duplicate encounter.

## Impact

- Primary code: `core/ai/action_handler.py`, `core/managers/combat_manager.py`, and minimal caller wiring in `main.py` only if required for player-visible fail-closed feedback.
- Primary tests: `scripts/c5_regression_combat.py` and/or `scripts/test_multi_pc_combat.py` with new duplicate-start/session-ownership coverage.
- Affected state surfaces: `party_tracker.json`, `modules/conversation_history/combat_conversation_history.json`, and encounter files under `modules/encounters/`.
- Merge-safety impact is low because the change is additive tabletop-mode guard logic rather than a broad upstream-flow rewrite.
- Single-player compatibility impact SHALL remain zero; the new ownership contract only applies to multi-PC tabletop combat paths.
