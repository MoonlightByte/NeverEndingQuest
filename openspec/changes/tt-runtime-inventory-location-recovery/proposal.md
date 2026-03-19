## Why

Live gametest evidence shows two linked runtime failures still persist after the first patch attempt:

- canonical inventory state does not recover when the narrator emits a one-sided party-to-party handoff or later narration-only item handling for the same item;
- canonical location state can remain stale at `NIG01` while recent narration and startup recaps clearly place the party in `NIG04 Priest's Lodging`, so the GUI top bar and rebuilt history continue to expose the wrong scene.

The problem is no longer prompt wording alone. Runtime currently trusts prompt compliance in three places where it should not:

- party-to-party item transfers rely on the model to emit both sides of the handoff;
- narration-only turns can skip validator/recovery too early;
- startup/history refresh trusts stale `party_tracker.json` even when recent transcript evidence clearly places the party elsewhere.

## What Changes

- MUST add deterministic party-to-party inventory transfer reconciliation so explicit handoffs can recover canonical giver/receiver state when the model omits or under-specifies one side.
- MUST add deterministic recovery for later receiver-side item handling turns when ownership is uniquely implied by recent transcript history.
- MUST run deterministic recovery before narration-only validation skip finalizes the turn.
- MUST add narrow startup/history location recovery so recent, uniquely resolved scene evidence can repair stale `party_tracker` location before GUI/history refresh rehydrates the wrong location.
- MUST support safe location alias/title matching for room-style names such as `Room 4: Priest's Lodging` vs `the priest's lodging`.
- SHOULD keep all inference conservative and fail open on ambiguous ownership, ambiguous location identity, or missing item identity.
- SHOULD lock the reliquary handoff + Priest's Lodging transcript with deterministic regressions.

Non-goals:

- No broad fuzzy scene understanding layer.
- No cross-module travel redesign.
- No generic inventory ledger or v2 event-ledger work.
- No prompt-only fix that leaves runtime dependent on model compliance.

## Capabilities

### New Capabilities
- `tt-party-item-transfer-reconcile`: deterministic recovery for explicit party-to-party item ownership changes.
- `tt-startup-scene-location-recovery`: startup/history repair for stale canonical location when recent transcript scene evidence is uniquely resolvable.

### Modified Capabilities
- `tt-narrated-location-arrival-sync`: location reconciliation expands to support conservative room-title aliases used in module prose and recaps.
- `tt-validation-efficiency-routing`: narration-only skip path must occur after deterministic recovery opportunities are exhausted.

## Impact

- Primary code likely affected:
  - `main.py`
  - `utils/travel_state_sync_guard.py`
  - `utils/scene_item_reconcile.py` or a new adjacent deterministic helper
  - startup/history refresh path in `main.py` and/or `utils/startup_wizard.py`
- Primary tests likely affected:
  - new reliquary handoff lock case
  - new receiver self-stow recovery lock case
  - new startup Priest's Lodging recovery lock case
  - existing narrated-arrival and validation-routing suites
- SP/MP impact:
  - MUST remain compatible with both single-player and tabletop modes because inventory truth and location truth are shared runtime state.
- Rollout risk:
  - Main risks are over-committing ownership from vague prose or over-committing location from stale/ambiguous scene text.
  - Fallback is narrow deterministic matching with fail-open behavior.
