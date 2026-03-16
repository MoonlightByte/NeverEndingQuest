## Why

The recent `Night_of_the_Restless_Dead` tunnel loop exposed a separate runtime failure after the module data was corrected: the narrator can still accept a clear travel turn, vividly narrate arrival in a new place, and return `actions: []` or no `transitionLocation`, leaving persisted location state unchanged. On the next beat, the model snaps back to the old current location and the bug appears to re-emerge as "location magic."

This is a hard UX/state-sync bug, not a module-authoring bug. The runtime currently classifies travel intent, but it does not deterministically require location-state commitment when the response actually narrates movement/arrival. That gap allows prose-only travel, contradictory dual-location narration, and stale current-location recap poisoning to survive validation.

## What Changes

- Add a deterministic travel-state sync guard for clear travel-intent turns.
- Reject responses that narrate arrival, emergence, entry, or traversal into a new location without a matching `transitionLocation` action.
- Reject contradictory mixed-location travel narration within a single response when no valid state transition explains it.
- Allow no-transition travel responses only when they explicitly keep the party at the current location (for example: blocker, failed passage, or clarification request) and do not narrate arrival elsewhere.
- Add focused regression coverage for narration-only travel, contradictory dual-location narration, and valid blocker/clarifier responses.

Non-goals:
- No module file changes in this slice.
- No transcript cleanup or save-file repair in this slice.
- No broad narrator prompt rewrite.
- No replacement of the existing transition validator; this patch sits in front of or alongside current travel validation.

## Capabilities

### New Capabilities
- `tt-travel-intent-state-sync-guard`: clear travel-intent turns SHALL either commit location state with `transitionLocation` or remain explicitly grounded at the current location without narrating arrival elsewhere.

### Modified Capabilities
- None.

## Impact

- Primary code:
  - `main.py`
  - possibly `core/ai/action_handler.py` only if narrow reuse improves guard consistency
- Prompt/validator touchpoints only if parity wording is required:
  - `prompts/validation/validation_prompt_compressed.txt`
  - `prompts/validation/validation_prompt.txt`
- Tests:
  - new targeted regression file in `scripts/`
  - possibly small extensions to existing travel/validation tests

Risks and fallback:
- MUST avoid false positives on non-travel clarification turns, map questions, or explicit blocker narration that keeps the party in place.
- MUST stay deterministic and grounded in explicit user travel intent plus explicit arrival/location narration in the assistant response.
- SHOULD prefer a narrow acceptance guard over broader NLP scene interpretation.
- If destination inference from narration is too ambiguous, the guard SHOULD fail open and defer to existing validation rather than invent certainty.

Merge-safety / compatibility:
- Runtime behavior changes only for clearly classified travel-intent turns.
- Single-player and tabletop modes both benefit because the bug exists at the shared narrator/validation layer.
