## Why

Combat currently allows validated enemy-phase responses whose narration contradicts authoritative hit/miss math, which breaks trust in Python-grounded combat state. In the live `NIG05-E2` failure, Blarg's `4+5=9` vs Skeleton AC `13` was a miss but narration described a bone-splintering hit, while a confirmed skeleton hit on Athelon was narrated like a harmless miss.

## What Changes

- Add a bounded deterministic combat guard that MUST reject explicit narration contradictions when attack math and target AC make hit or miss outcomes unambiguous.
- Tighten combat validation so enemy-only routing boundaries MUST reject `updateEncounter` payloads that target PC or allied NPC state.
- Add focused validator prompt parity for explicit hit->miss and miss->hit contradiction classes.
- Add targeted regression coverage for DM-group opening enemy phase, including the exact `Cultist -> Blarg -> Skeleton` opening batch failure.
- Preserve fail-open behavior for ambiguous flavor text, incomplete math, or non-authoritative narration.

Non-goals:
- broad combat prompt rewrites
- encounter generation redesign
- combat style or prose tuning beyond contradiction prevention
- new dice systems or combat-flow redesign

Rollout risk and fallback:
- MUST keep the new guards additive and bounded to explicit contradictions only.
- MUST prefer deterministic rejection only when attack math, bonus, and target AC are available in the response context.
- SHOULD fail open to existing validation flow when narration is too vague to prove contradiction safely.
- If a new guard produces false positives, it SHOULD be narrowed before any prompt widening.

Merge-safety and compatibility:
- MUST preserve upstream-compatible combat flow outside TABLETOP MODE hooks.
- MUST preserve current single-player and non-combat behavior.
- MUST not alter encounter math resolution itself; only validation and routing acceptance rules change.

## Capabilities

### New Capabilities
- `tt-combat-hit-miss-narration-consistency`: combat validation rejects explicit narration that contradicts authoritative hit/miss outcomes when the contradiction is state-backed and unambiguous.

### Modified Capabilities
- `tt-combat-structured-encounter-ops-routing`: strengthen the routing boundary so `updateEncounter` payloads MUST remain enemy-only and MUST reject PC or allied NPC targets in prose mirrors or supported ops.

## Impact

- Affected code: `core/managers/combat_manager.py`, a new narrow deterministic combat validation helper under `utils/`, and possibly existing bounded combat integrity helper integration points.
- Affected prompts: `prompts/combat/combat_validation_prompt_multipc_compressed.txt` and `prompts/combat/combat_validation_prompt_multipc.txt`.
- Affected tests: `scripts/c5_regression_combat.py` and new/extended targeted combat validation regressions.
- Systems impacted: multi-PC combat validation, enemy-phase narration integrity, and enemy-routing acceptance for `updateEncounter` changes and ops.
- Provider/quota behavior: no new LLM dependency is introduced; the change SHOULD shift obvious contradiction rejection earlier and reduce wasted combat validation retries.
