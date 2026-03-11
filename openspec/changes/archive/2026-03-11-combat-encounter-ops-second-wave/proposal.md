## Why

`openspec/changes/archive/2026-03-11-combat-runtime-authority-and-efficiency/`, `openspec/changes/archive/2026-03-11-combat-structured-pc-allied-ops-pilot/`, `openspec/changes/archive/2026-03-11-combat-save-concentration-contract/`, and `openspec/changes/archive/2026-03-11-combat-expanded-deterministic-guards/` completed the first-wave combat refactor: canonical combat authority, lighter validation packets, structured PC/allied mechanics, first-class save/check pause contracts, and bounded deterministic contradiction guards.

The remaining asymmetry is enemy-side mutation routing. Combat still prefers prose-heavy `updateEncounter.changes` for enemy HP, status, and conditions even though the architecture now expects Python-owned legality and accounting beneath LLM tactics and narration. This deferred second-wave slice closes that gap without turning combat into a broad encounter-engine rewrite.

## What Changes

- Update combat prompt and validator contract text to prefer mixed `updateEncounter` payloads that include both `changes` and supported `ops` for enemy-side combat mutations.
- Define a narrow first-wave enemy op family for combat: `hp_delta`, `set_hp`, `condition_add`, `condition_remove`, and `set_status`.
- Preserve prose compatibility during migration, but treat supported enemy `ops` as the authoritative mechanics payload when present.
- Preserve the routing boundary that enemies mutate through `updateEncounter` while PCs/allies continue to mutate through `updateCharacterInfo`.
- Add focused combat contract tests that lock mixed-payload preference, first-wave enemy op scope, and fail-open fallback behavior for unsupported or ambiguous enemy ops payloads.
- Keep runtime edits narrow and evidence-driven, touching `core/ai/action_handler.py` and `updates/update_encounter.py` only if tests reveal a real routing gap.

## Covered Scope

This change explicitly covers:
- multi-PC combat prompt/validator guidance for enemy-side `updateEncounter.ops`
- deterministic application for a narrow first-wave enemy op family
- combat-facing tests for mixed, prose-only, and ambiguous enemy payloads
- preservation of PC/allied `updateCharacterInfo` routing and current save/check behavior

Out of scope:
- creature spawn/despawn semantics
- initiative reorder or queue rebuild ops
- battlefield topology or positioning ops
- full deprecation of prose `changes`
- roll resolution engine changes
- broad combat manager rewrite

## Capabilities

### New Capabilities
- `tt-combat-structured-encounter-ops-routing`: combat prompt and validator contracts MUST prefer additive structured `updateEncounter.ops` for enemy-side mutations while preserving prose compatibility during migration.

### Modified Capabilities
- `tt-combat-structured-character-ops-routing`
- `tt-combat-validation-efficiency-routing`

## Risks and Fallback

- MUST preserve the routing boundary that enemy-side combat mutations stay on `updateEncounter` while PC/allied mutations stay on `updateCharacterInfo`.
- MUST keep the first-wave enemy op family limited to `hp_delta`, `set_hp`, `condition_add`, `condition_remove`, and `set_status`.
- MUST preserve prose fallback for unsupported, partial, or ambiguous enemy ops payloads.
- SHOULD prefer mixed `changes + ops` payload examples over `ops`-only examples so narration mirrors remain readable during migration.
- SHOULD keep host-file edits minimal and marked with `# TABLETOP MODE:` comments where required.

Fallback strategy:
- If combat regressions appear, revert prompt/validator encounter-ops preference edits before widening runtime behavior.
- If an enemy op shape proves brittle, preserve prose fallback and narrow the approved op family rather than broadening runtime scope.

## Impact

- Affected prompts:
  - `prompts/combat/combat_sim_prompt_multipc_compressed.txt`
  - `prompts/combat/combat_validation_prompt_multipc_compressed.txt`
  - combat prompt mirror files only as needed for parity/docs
- Expected runtime touchpoints:
  - `core/ai/action_handler.py`
  - `updates/update_encounter.py`
- Expected tests:
  - new `scripts/test_combat_encounter_ops_contract.py`
  - existing `scripts/test_combat_structured_ops_contract.py`
  - existing combat regressions (`scripts/test_multi_pc_combat.py`, `scripts/c5_regression_combat.py`)

## Acceptance Criteria

- Combat prompts and validator explicitly prefer mixed `changes + ops` payloads for enemy-side encounter mutations.
- Combat examples and tests cover the approved first-wave enemy op family only.
- Enemy-side `updateEncounter` routing remains separate from PC/allied `updateCharacterInfo` routing.
- Prose-only fallback remains compatibility-valid and ambiguous enemy ops continue to fail open to safe fallback behavior.
- The change validates cleanly and the targeted combat regression suites remain green.
