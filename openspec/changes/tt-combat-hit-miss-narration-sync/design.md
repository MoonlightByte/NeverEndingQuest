## Context

Multi-PC combat already has bounded deterministic guards for phase integrity and explicit mechanics contradictions, but hit-versus-miss narration consistency is still enforced only probabilistically through the combat validator prompt. The live `NIG05-E2` opening enemy-phase failure showed that this is not strong enough: a response with explicit miss math and explicit hit narration still passed validation.

A second defect surfaced in the same response: `updateEncounter` accepted a player target in enemy ops (`Athelon`), then fail-opened into fallback encounter update behavior before the correct `updateCharacterInfo` path applied the damage. That means both the validator and runtime currently permit explicit routing-boundary drift.

Constraints:
- Python combat math and persisted encounter/character state remain the ground truth.
- The fix MUST stay additive and merge-safe.
- The fix MUST preserve current single-player and non-combat behavior.
- The fix MUST fail open on ambiguous prose, but fail closed on explicit math-backed contradictions.

## Goals / Non-Goals

**Goals:**
- Add a deterministic precheck that MUST reject explicit narration contradictions when attack outcome and target AC are authoritative.
- Add a deterministic routing precheck that MUST reject `updateEncounter` prose or ops targeting PC/allied state.
- Keep the new logic bounded to explicit contradiction classes only.
- Add regressions for the exact DM-group opening enemy-phase failure shape.

**Non-Goals:**
- Rewriting combat prompting strategy or enemy tactics.
- Changing encounter math resolution, preroll consumption, or damage formulas.
- Reworking fallback encounter update architecture beyond explicit routing rejection.
- Policing vague atmosphere or non-mechanical prose.

## Decisions

### Decision: Add a new narrow deterministic narration-consistency helper
- MUST implement hit/miss narration checks in a dedicated helper under `utils/` rather than burying more string logic in `combat_manager.py`.
- MUST inspect explicit attack math from `plan`, `narration`, and action mirror text only when all three components are available: attacker outcome, numeric total or components, and target AC.
- SHOULD classify contradiction language using bounded phrase families:
  - miss-but-hit language: `bites deep`, `bone splinters`, `cuts into`, `strikes true`, `draws blood`, `slams into`
  - hit-but-miss language: `shatters against the wall`, `goes wide`, `misses entirely`, `harmlessly past`, `glances off empty stone`
- Alternative considered: rely on prompt parity only. Rejected because the live failure already passed the probabilistic validator.

### Decision: Reject explicit routing-boundary violations before fallback update paths
- MUST add a deterministic guard that inspects `updateEncounter.parameters.changes` and supported `ops` for PC/allied NPC names and state mutations.
- MUST reject `updateEncounter` if it explicitly targets a player or allied NPC for HP, status, condition, or ammo/inventory mutation.
- SHOULD allow enemy-only housekeeping text in `updateEncounter` while PC/allied damage remains on `updateCharacterInfo`.
- Alternative considered: let `update_encounter.py` fail open and rely on later `updateCharacterInfo`. Rejected because it permits invalid payloads to validate and execute partially.

### Decision: Wire new guards before probabilistic combat validation
- MUST execute deterministic narration and routing guards before the LLM validator call in `validate_combat_response(...)`.
- MUST preserve existing fail-open behavior when contradiction cannot be established confidently.
- SHOULD reuse the current validation failure feedback pattern so retries stay consistent with existing combat retry hygiene.
- Alternative considered: place guards after LLM validation. Rejected because wasted retries and false validator passes are part of the bug.

### Decision: Keep prompt changes narrow and parity-focused
- MUST update compressed and uncompressed combat validation prompts with explicit contradiction examples for miss->hit and hit->miss narration.
- SHOULD avoid changing combat simulation prompt unless implementation reveals missing contract clarity there too.
- Alternative considered: broader prompt rewrite to make narration less cinematic. Rejected because the problem is contradiction, not intensity.

## Risks / Trade-offs

- [False positives from aggressive phrase matching] -> Mitigation: only reject when attack outcome is explicit and contradiction phrases are strong, not generic atmosphere.
- [Validator/runtime disagreement] -> Mitigation: deterministic guards run before probabilistic validation, making validator acceptance secondary for these explicit cases.
- [Merge drift from broad helper edits] -> Mitigation: isolate new logic in a dedicated helper and keep host-file wiring minimal.
- [Routing guard blocks valid enemy housekeeping text] -> Mitigation: only reject when `updateEncounter` explicitly applies PC/allied state mutation semantics, not mere mentions.

## Migration Plan

1. Add OpenSpec delta specs and lock regression expectations.
2. Implement deterministic helper for narration consistency.
3. Implement deterministic routing-boundary precheck for `updateEncounter` payloads.
4. Wire both checks into `core/managers/combat_manager.py` before probabilistic validator calls.
5. Apply narrow prompt parity updates.
6. Run targeted regression, compile, and OpenSpec validation.

Rollback strategy:
- If the new deterministic helper false-positives, disable the helper wiring and keep prompt parity/test scaffolding while narrowing the matcher.
- If the routing guard proves too broad, reduce it to supported ops first and re-expand only after tests.

## Open Questions

- Should contradiction phrase matching live entirely in code, or should a small shared phrase list also be reflected in prompt examples for maintenance parity?
- Should the new helper inspect only `plan` plus `narration`, or also `updateEncounter.parameters.changes` for extra contradiction evidence?
- Is a dedicated regression file clearer than extending `scripts/c5_regression_combat.py`, or is keeping all opening enemy-phase regressions together preferable?
