## Why

`openspec/changes/archive/2026-03-11-combat-runtime-authority-and-efficiency/` completed the first safe combat hardening wave: canonical compressed prompt authority, slimmer runtime packets, validation telemetry/compression, touched-combatant truth packs, and retry-local correction hygiene. That change deliberately deferred structured combat mechanics expansion.

The next safest slice is to deepen combat use of the already-implemented `updateCharacterInfo.ops` path for PC and allied NPC updates. Combat still teaches mostly prose-era HP, spell-slot, ammo, and condition updates even though runtime already supports deterministic additive ops application. This change closes that gap without widening into enemy-side `updateEncounter.ops` or save/check contract work.

## What Changes

- Update combat prompt and combat validator contract text to prefer mixed `changes + ops` payloads for PC and allied NPC `updateCharacterInfo` actions.
- Keep `changes` compatibility-valid during migration, but treat `ops` as the authoritative mechanics payload when present.
- Keep enemy-side combat mutations on the existing `updateEncounter` contract in this slice.
- Add focused combat contract tests that lock mixed payload preference, preserve prose fallback, and prevent accidental enemy-side contract widening.
- Preserve deterministic fallback telemetry/logging so combat migration progress remains measurable.

## Covered Scope

This change explicitly covers:
- multi-PC combat prompt/validator guidance for `updateCharacterInfo.ops`
- combat examples for HP, spell slots, ammo/item spend, and conditions
- combat-facing tests for structured-only, mixed, and prose-fallback acceptance
- narrow runtime alignment only if combat reveals a missing routing or payload gap

Out of scope:
- `updateEncounter.ops`
- combat `requestRoll` migration
- concentration/save contract alignment
- full deprecation of prose `changes`
- full combat mechanics rewrite

## Capabilities

### New Capabilities
- `tt-combat-structured-character-ops-routing`: combat prompt and validator contracts MUST prefer additive structured `updateCharacterInfo.ops` for PC/allied mutations while preserving prose compatibility during migration.

### Modified Capabilities
- `tt-structured-character-ops-contract`
- `tt-deterministic-character-ops-application`

## Risks and Fallback

- MUST preserve single-player compatibility and current multi-PC phase behavior.
- MUST keep enemy-side mutation routing on `updateEncounter` in this change.
- MUST preserve prose fallback when supported `ops` are absent or combat examples have not yet migrated.
- SHOULD prefer mixed `changes + ops` payload examples over `ops`-only examples so current narrative mirrors remain legible.
- SHOULD keep host-file edits minimal and marked with `# TABLETOP MODE:` comments where required.

Fallback strategy:
- If combat regressions appear, revert combat prompt/validator ops preference edits before touching the underlying runtime structured-ops engine.
- If a combat-specific op shape proves incompatible, preserve the prose fallback path and narrow the prompt examples rather than widening runtime scope.

## Impact

- Affected prompts:
  - `prompts/combat/combat_sim_prompt_multipc_compressed.txt`
  - `prompts/combat/combat_validation_prompt_multipc_compressed.txt`
  - combat prompt mirror files only as needed for parity/docs
- Expected runtime touchpoints:
  - `core/ai/action_handler.py`
  - `updates/update_character_info.py`
- Expected tests:
  - new `scripts/test_combat_structured_ops_contract.py`
  - existing `scripts/test_update_character_ops_contract.py`
  - existing combat regressions (`scripts/test_multi_pc_combat.py`, `scripts/c5_regression_combat.py`)

## Acceptance Criteria

- Combat prompts and validator explicitly prefer mixed `changes + ops` payloads for PC/allied updates.
- Combat examples cover HP, spell slot, ammo/item spend, and condition updates through supported ops.
- Enemy-side combat mutations remain on `updateEncounter` in this slice.
- Prose-only fallback remains compatibility-valid and measurable.
- The change validates cleanly and the targeted combat regression suites remain green.
