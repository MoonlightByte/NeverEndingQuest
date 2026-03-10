## Why

The prompt-validator hardening work is now in a better state: compressed prompts are live runtime authority, deterministic mechanics prechecks run before the validator, validation compression is threshold-based, and low-risk turns can skip the LLM validator. The next safest change is not more behavior expansion - it is observability plus cleaner validator context.

Right now we still lack two things:

1. clear telemetry showing whether skip/compression routing is actually saving time and tokens in practice,
2. a compact, mechanically truthful validator context for touched characters.

The current validation flow still assembles inventory-heavy context in `main.py`, and it does not yet expose simple counters and reasons for routing decisions. Without that visibility, threshold tuning and further validation optimization are guesswork.

## What Changes

- Add validation-routing telemetry for:
  - validator skip decisions,
  - compression decisions,
  - payload size before compression,
  - skip/compression reason codes.
- Add a compact touched-character mechanical truth pack builder for validation.
- Feed the validator a compact truth pack for touched characters instead of the current uneven inventory-first context.
- Keep behavior conservative: this change improves measurement and context quality, but does not expand skip eligibility or alter prompt contracts.

## Covered Scope

This change explicitly covers:
- validation-routing observability
- touched-character mechanical truth-pack assembly
- validation context integration for touched characters

Out of scope:
- new low-risk skip categories
- new deterministic mechanics guards
- structured `updateCharacterInfo.ops`
- save/check contract redesign
- DM Note architecture cleanup outside the validation truth pack itself

## Capabilities

### New Capabilities
- `tt-validation-routing-telemetry`: validation flow MUST emit deterministic telemetry for compression and skip decisions.
- `tt-validator-mechanical-truth-pack`: validator context MUST use a compact, touched-character mechanical truth pack when characters are mutated in the candidate response.

## Impact

- Affected runtime:
  - `main.py`
  - new validation helper under `utils/` or `core/validation/`
- Affected tests:
  - new regression coverage for telemetry and truth-pack assembly
- Risk profile:
  - low, because routing behavior remains conservative and context becomes more explicit rather than less

## Acceptance Criteria

- Validation flow records skip/compression reason codes in a deterministic and testable way.
- Validation flow records pre-compression payload size in a deterministic and testable way.
- Touched-character validation context contains compact mechanical truth fields: HP/max HP, conditions, spell slots, death saves, class feature usage, and inventory only when relevant.
- Current inventory-heavy ad hoc context assembly for touched characters is reduced or replaced by the truth-pack helper.
- Targeted tests verify telemetry wiring and truth-pack content contracts.
