## Why

The narrator prompt-validator refactor is now proving out well in gameplay, but the combat stack still runs on an older, heavier architecture. Combat currently has duplicated prompt rules, broader-than-needed runtime state packets, monolithic LLM validation, retry-note pollution in combat conversation history, and no combat-native equivalent of the narrator truth-pack and routing improvements.

This change is needed now because combat is already behaving well enough to harden safely: the goal is not to rewrite combat mechanics, but to make the working system cheaper, cleaner, and more deterministic without sacrificing vivid narration, enemy tactical competence, or 5e accounting.

## What Changes

- Make compressed multi-PC combat prompts the canonical live runtime source for combat simulation and combat validation.
- Add combat contract parity tests so prompt, validator, and runtime cannot silently drift on phase rules, routing rules, round advancement, and exit behavior.
- Slim and reorder the compressed multi-PC combat prompt so hard constraints and authoritative state rules come before flavor guidance.
- Reduce combat runtime prompt payload size by trimming duplicated/overlapping state packets while preserving the current legal actor, phase, and initiative contracts.
- Add combat validation routing telemetry and threshold-based validation compression for combat validation calls.
- Add compact touched-combatant mechanical truth packs for combat validation context instead of broad encounter-heavy validation context when only a subset of PCs/allied NPCs are mutated.
- Add combat retry hygiene so validation correction messages and invalid-JSON repair notes remain validation-local instead of being appended into persistent combat conversation history.
- Preserve current combat mutation contracts in this change; structured combat mechanics expansion is explicitly deferred.

MUST constraints:
- Combat must preserve vivid narration and legal enemy tactical behavior.
- Combat must preserve Python authority for initiative, phase control, legality, and accounting.
- Combat must preserve single-player compatibility and current TT merge-safe boundaries.

SHOULD constraints:
- Prompt edits should be semantic-first and avoid noisy full-file churn.
- Context reduction should favor compact authoritative packets over duplicate prose blocks.

Non-goals:
- No `updateEncounter.ops` work in this change.
- No broad combat engine rewrite.
- No intentional weakening of tactical enemy behavior or narration quality.
- No save/check contract expansion beyond what is needed for prompt authority and current validation flow.

## Capabilities

### New Capabilities
- `tt-combat-runtime-prompt-authority`: live combat simulation and validation paths SHALL use the compressed combat prompt variants as canonical runtime sources.
- `tt-combat-context-packet-efficiency`: combat runtime SHALL provide a slimmer authoritative state packet without losing current phase, actor, and accounting fidelity.
- `tt-combat-validation-efficiency-routing`: combat validation SHALL support deterministic telemetry and threshold-based compression decisions.
- `tt-combat-validator-mechanical-truth-pack`: combat validation SHALL use compact touched-combatant mechanical truth packs for mutated PCs/allied NPCs.
- `tt-combat-validation-retry-hygiene`: combat validation correction and repair notes SHALL remain validation-local and SHALL NOT pollute persistent combat conversation history.

### Modified Capabilities
- None.

## Impact

- Affected runtime:
  - `core/managers/combat_manager.py`
  - `core/managers/multi_pc_combat.py`
  - new helper(s) under `utils/` or `core/validation/` for combat routing/truth-pack support
- Affected prompts:
  - `prompts/combat/combat_sim_prompt_multipc_compressed.txt`
  - `prompts/combat/combat_validation_prompt_multipc_compressed.txt`
  - uncompressed mirror files only as needed for prompt parity/docs
- Affected tests:
  - new combat contract parity tests
  - new combat validation routing/telemetry tests
  - new combat truth-pack tests
  - new combat retry hygiene tests
  - existing combat regressions MUST stay green (`scripts/test_multi_pc_combat.py`, `scripts/c5_regression_combat.py`)

- Risk analysis:
  - Risk: prompt slimming could weaken combat discipline.
    - Mitigation: add contract tests first and preserve current legal-actor/phase contracts.
  - Risk: context trimming could remove needed tactical state.
    - Mitigation: trim duplicate packets first; preserve authoritative phase/tracker packets.
  - Risk: combat validator cleanup could alter current gameplay flow.
    - Mitigation: keep behavior conservative and change retry storage before expanding validation scope.

- Fallback strategy (MUST):
  - If regressions appear, revert combat retry-hygiene and prompt-packet slimming before reverting prompt authority/tests, so canonical authority and contract coverage remain in place.

- Merge safety and compatibility:
  - MUST keep host-file edits minimal and marked with `# TABLETOP MODE:` where applicable.
  - MUST preserve single-player combat behavior.
  - SHOULD preserve current TT plugin boundaries and phase-sync contracts.
