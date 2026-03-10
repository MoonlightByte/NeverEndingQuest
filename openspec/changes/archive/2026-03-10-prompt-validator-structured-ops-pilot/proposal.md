## Why

The prompt-validator hardening work has now aligned contracts, added deterministic prechecks, moved runtime to compressed prompt authority, and improved validator routing/context. The biggest remaining gap in `plans/prompt-validator-fix.md` is still structured mechanics: common `updateCharacterInfo` writes continue to depend on prose `changes` strings and a second interpretation path.

This change introduces an additive `ops` pilot for `updateCharacterInfo.parameters` so high-risk mechanics can be expressed in structured form and applied directly in Python. Legacy prose remains supported as a fallback during migration.

## What Changes

- Add optional `ops` support to `updateCharacterInfo.parameters` in prompts, validator contracts, and runtime handling.
- Define an initial supported `ops` set for high-value mechanics.
- Apply supported ops deterministically in Python before falling back to prose interpretation.
- Add fallback telemetry so the project can measure how often legacy prose is still used.
- Preserve backward compatibility with existing `changes`-only payloads.

## Covered Scope

This change explicitly covers:
- prompt and validator contract support for `updateCharacterInfo.parameters.ops`
- deterministic application of the initial supported ops set
- legacy `changes` fallback behavior and usage telemetry

Out of scope:
- save/check first-class contract
- new validator skip categories
- full deprecation of prose `changes`
- non-`updateCharacterInfo` structured mechanics

## Initial `ops` Set

- `set_hp`
- `hp_delta`
- `spell_slot_delta`
- `inventory_add`
- `inventory_remove`
- `currency_delta`
- `condition_add`
- `condition_remove`

## Capabilities

### New Capabilities
- `tt-structured-character-ops-contract`: `updateCharacterInfo` MUST support an additive structured `ops` contract without breaking legacy prose updates.
- `tt-deterministic-character-ops-application`: supported `ops` MUST be validated and applied directly in Python when present.

## Impact

- Affected prompts:
  - `prompts/system_prompt_compressed.txt`
  - `prompts/validation/validation_prompt_compressed.txt`
- Affected runtime:
  - `core/ai/action_handler.py`
  - `updates/update_character_info.py`
  - possible new helper under `utils/` or `core/validation/`
- Affected tests:
  - contract tests for `ops`
  - runtime application tests for supported operations
  - fallback telemetry tests

## Acceptance Criteria

- `updateCharacterInfo.parameters` accepts both legacy `changes` and additive `ops`.
- Prompts and validator contract text document the same initial `ops` set.
- Supported `ops` are applied deterministically in Python.
- Unsupported or absent `ops` continue through the legacy prose path without breaking existing gameplay.
- Fallback usage is surfaced in deterministic telemetry or logs.
