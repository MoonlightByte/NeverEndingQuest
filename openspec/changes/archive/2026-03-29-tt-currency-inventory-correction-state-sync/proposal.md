## Why

The narrator can currently answer a bookkeeping correction turn with `actions: []`, skip LLM validation as `narration_only`, and then claim that currency or inventory state has already been fixed. This breaks the repo's core contract that Python-backed character state is the mechanical truth and creates visible GUI chat drift where the DM says a coin moved into the pouch even though no `updateCharacterInfo` action ran.

## What Changes

- Add a narrow runtime guard that MUST fail closed when a response claims an explicit currency or inventory bookkeeping correction without matching state mutation actions.
- Extend validation skip routing so explicit bookkeeping-correction turns MUST NOT qualify for `narration_only` fast-path acceptance.
- Add a focused prompt and validator contract so ruling-only clarification remains valid, but narrated bookkeeping corrections MUST emit `updateCharacterInfo` in the same response.
- Add regression coverage for coin-pouch, payment, refund, and correction turns so this drift does not return.
- Non-goal: this change SHOULD not introduce broad automatic currency reconciliation from prose alone; ambiguous cases should still fail closed or remain ruling-only.

## Capabilities

### New Capabilities
- `tt-currency-correction-state-sync`: Ensure explicit currency and inventory bookkeeping corrections cannot be narrated as committed state unless matching character-update actions are present.

### Modified Capabilities
- `tt-validation-efficiency-routing`: Tighten low-risk skip eligibility so bookkeeping-correction turns do not finalize through `narration_only` routing before deterministic guards run.

## Impact

- Affected runtime: `main.py`, `utils/validation_routing.py`, `utils/deterministic_mechanics_precheck.py`
- Affected prompt surfaces: `prompts/system_prompt_compressed.txt`, `prompts/validation/validation_prompt_compressed.txt`, and uncompressed mirrors if needed for parity
- Affected tests: validation skip routing, deterministic mechanics precheck, and new targeted correction regressions
- Risk: low-to-medium; this is a fail-closed tightening that may reject turns previously accepted through narration-only drift
- Fallback strategy: ambiguous or purely advisory rulings SHOULD remain narration-only; only explicit committed bookkeeping corrections become invalid without actions
- Merge safety: host-file edits remain narrow and TABLETOP MODE marked; no schema changes or save-format changes required
- SP/MP compatibility: behavior MUST remain compatible in both single-player and tabletop mode because the guard applies to shared narrator validation paths
