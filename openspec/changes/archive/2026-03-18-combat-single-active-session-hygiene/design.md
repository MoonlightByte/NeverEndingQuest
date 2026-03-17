## Overview

This change hardens tabletop combat so exactly one unresolved encounter owns combat input at a time. The root problem is not `/init` parsing; it is ownership drift between three state surfaces:

1. durable owner: `party_tracker.json -> worldConditions.activeCombatEncounter`
2. runtime owner: the currently running combat loop in `core/managers/combat_manager.py`
3. history owner: `modules/conversation_history/combat_conversation_history.json`

When these surfaces point at different encounters, gate commands such as `/init` and `/att` can be evaluated against the wrong session, which produces the observed loop.

## MUST Contract

- The durable encounter owner SHALL be `party_tracker.json -> worldConditions.activeCombatEncounter`.
- A new tabletop `createEncounter` request SHALL NOT create or start a second unresolved encounter while a different active encounter owner already exists.
- Combat loop startup SHALL reject concurrent ownership and SHALL release ownership on every normal and exceptional exit path.
- Player-facing failure output SHALL be non-technical and immediate, while diagnostics remain detailed in logs.
- Existing successful single-encounter paths (`/init`, `/att`, `/end`, resume, post-combat cleanup) SHALL remain behaviorally unchanged.

## SHOULD Guidance

- Prefer a narrow guardrail instead of a large combat refactor.
- Keep ownership checks close to the two entry points that matter most:
  - encounter creation in `core/ai/action_handler.py`
  - combat loop startup in `core/managers/combat_manager.py`
- Treat history metadata as a compatibility mirror, not the primary source of truth.

## Architecture

### 1. Durable Ownership Gate

Before a new tabletop encounter is created, action handling should read the current durable owner.

- If no active encounter is set, normal create/start flow proceeds.
- If an active encounter is already set and unresolved, the new create path fails closed.
- The failure response should tell the facilitator that combat is already active and they should continue the current encounter, without exposing internal file names.

This stops duplicate encounter files such as `TW02-E2` and `TW02-E3` from being created for the same live scene when the prior combat session still owns input.

### 2. Runtime Session Claim

`run_combat_simulation(...)` should claim a process-local session slot when it starts and release it in a `finally` block.

Behavior:
- First caller claims ownership and runs normally.
- Second caller while the slot is active is rejected deterministically.
- Rejected startup logs encounter ids and ownership state for diagnosis.

This prevents overlapping combat loops from consuming the same queued web input even if a higher layer misfires.

### 3. History Owner Coherence

Combat history metadata should be validated against the durable owner when a combat session is resumed or started.

- If history owner matches durable owner, continue normally.
- If history owner mismatches durable owner, runtime should prefer the durable owner and emit a diagnostic log.
- This change SHOULD avoid automatic repair of unrelated history content; it only needs enough coherence checking to stop routing commands to the wrong encounter.

### 4. Fail-Closed UX

Duplicate-start or ownership-drift detection must surface two outputs:

- User-visible: concise `[SYSTEM]` guidance such as "Combat is already active. Continue the current encounter." 
- Diagnostic: structured debug log with active encounter id, attempted encounter id, and reason.

The system must fail closed for the attempted duplicate startup; it must not narrate a second combat opening.

## File Strategy

### `core/ai/action_handler.py`
- Add a tabletop-only duplicate-start guard before creating a new encounter.
- Return structured status that callers already understand (`status:error` or equivalent explicit failure).
- Preserve existing success path unchanged.

### `core/managers/combat_manager.py`
- Add a process-local single-session claim/release helper.
- Guard `run_combat_simulation(...)` startup.
- On mismatch between runtime startup request and durable owner, log and fail closed instead of spinning a second loop.

### `main.py`
- Only touch if needed to route the new explicit duplicate-combat failure into the existing user-facing fail-closed output path.
- Avoid large narrator/control-flow edits in this change.

## Verification Strategy

### Positive
- Normal multi-PC combat creation still reaches `/init` exactly once.
- After valid `/init`, `/att` remains inside the same owned encounter.
- Resume of an existing owned encounter still works.

### Negative
- Attempting to create a second encounter while one is active is rejected.
- Attempting to start a second combat loop while one is already running is rejected.
- Ownership mismatch between durable owner and history owner logs diagnostics and does not create a new initiative loop.

## Rollback

The implementation is additive and local. If it causes false positives, rollback is a narrow revert of the duplicate-start guard and runtime session-claim helper without touching prompt contracts or existing encounter schemas.
