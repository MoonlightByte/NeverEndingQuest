## Why

The prompt-validator work now has contract alignment, deterministic prechecks for explicit HP/slot/inventory contradictions, structured character ops, and a first-class save/concentration contract. The next roadmap item in `plans/prompt-validator-fix.md` is the expanded deterministic guard set so more common mechanics contradictions can fail deterministically before they become validator retries or runtime drift.

This change extends the bounded deterministic-precheck approach to a few more high-value 5e cases: cantrip/no-slot legality, slot-underflow from explicit spend language, unconscious-vs-HP contradictions, ammo legality beyond simple explicit removals, and rest-duration legality at validator-precheck time.

## What Changes

- Expand deterministic precheck coverage for explicit spell-slot legality contradictions.
- Add deterministic unconscious-vs-HP integrity checks for explicit mechanical claims.
- Add deterministic ammo legality checks for explicit ammunition use/spend language when inventory state is known.
- Add deterministic rest-duration precheck coverage for explicit short-rest and long-rest declarations.
- Add focused regression tests that lock the new guard domains before broad prompt/runtime tightening.
- Preserve fail-open behavior for ambiguous or unparseable prose.

## Covered Scope

This change explicitly covers:
- deterministic validator-precheck extensions for explicit parseable mechanics contradictions
- additive helper boundaries under `utils/` or `core/validation/`
- targeted tests and source-contract verification for the expanded guard set

Out of scope:
- rewriting combat architecture
- broad validator routing redesign
- replacing prose mechanics with structured actions in this phase
- changing save/concentration contracts beyond the already completed change
- broad prompt bulk expansion

## Capabilities

### New Capabilities
- `tt-spell-slot-legality-guard`: deterministic precheck MUST reject explicit cantrip-slot contradictions and explicit slot-underflow contradictions before LLM validation.
- `tt-unconscious-hp-integrity-guard`: deterministic precheck MUST reject explicit mechanical states that claim a character is unconscious while also explicitly placing them above 0 HP.
- `tt-ammo-legality-guard`: deterministic precheck MUST reject explicit ammunition spend/use contradictions when canonical inventory state shows insufficient tracked ammunition.
- `tt-rest-duration-precheck`: deterministic precheck MUST reject explicit rest actions that violate short-rest or long-rest minimum duration rules when the duration is parseable.

### Modified Capabilities
- `tt-deterministic-mechanics-precheck`: extend the existing deterministic precheck capability to cover the new explicit contradiction classes while preserving fail-open behavior for ambiguous text.

## Risks and Fallback

- MUST preserve fail-open behavior when text is ambiguous, unparseable, or canonical state lookup is unavailable.
- MUST keep checks bounded to explicit parseable mechanics claims.
- MUST avoid broad natural-language interpretation or combat-flow rewrites.
- SHOULD centralize new helpers in one deterministic precheck utility unless a tiny focused helper improves clarity.
- SHOULD prefer explicit negative tests for false-positive resistance before tightening prompt behavior later.

## Merge-Safety and SP/MP Compatibility

- MUST preserve single-player and tabletop compatibility.
- MUST use minimal host-file hooks and mark required host edits with `# TABLETOP MODE:` comments.
- SHOULD keep the new checks additive to the existing precheck pipeline rather than restructuring validation flow.

## Impact

- Expected runtime touchpoints:
  - `utils/deterministic_mechanics_precheck.py`
  - `scripts/test_deterministic_mechanics_precheck.py`
  - `main.py`
  - possibly `prompts/system_prompt_compressed.txt`
  - possibly `prompts/validation/validation_prompt_compressed.txt`
- New focused contract tests:
  - `scripts/test_expanded_deterministic_guards_contract.py`

## Acceptance Criteria

- New guard domains are specified in OpenSpec and builder prompts.
- Contract tests lock the new deterministic guard expectations before implementation.
- Runtime implementation phases remain bounded to explicit parseable contradictions only.
- Existing fail-open principles remain explicit in the change artifacts.
