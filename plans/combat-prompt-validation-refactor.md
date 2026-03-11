# Combat Prompt and Validation Refactor Plan

## Executive Summary

This plan applies the same successful refactor pattern used in the recent narrator prompt and validation hardening to the combat stack, with one important scope decision:

- implement structured `updateCharacterInfo.ops` first,
- defer `updateEncounter.ops` to a later second-wave slice,
- modernize combat validation and prompt authority before attempting a deeper combat mechanics rewrite.

The combat system is already functionally strong in gameplay, especially around initiative flow, multi-PC phase control, and vivid narration. The main problem is not that combat lacks rules. The problem is that combat still mixes too much mechanics, validation, and narration in one large prompt/validator loop, while the narrator stack has already moved to a cleaner deterministic-first architecture.

This plan improves combat efficiency, reduces prompt/validator drift, lowers token usage where safe, and sharpens separation between Python-owned reality and LLM-owned tactical/narrative judgment.

The target end state is:

1. Python owns combat reality, legality, and accounting.
2. The combat LLM owns vivid narration, enemy tactical intent, tactical interpretation of player intent, and conversion of approved intent into a constrained action grammar.
3. Validation becomes more targeted, lighter on common turns, and more grounded in compact mechanical truth.
4. Prompt size drops because duplicated state and duplicated rules are removed, not because 5e accounting is weakened.

## Status

- Status: Completed (implemented via archived OpenSpec workstreams through 2026-03-11)
- Priority: High
- Scope: Multi-PC combat prompt, combat validator, combat runtime context assembly, combat validation routing, and structured PC/allied combat mechanics updates
- Risk: Medium to High if attempted as one large patch
- Recommended rollout: incremental, phase-gated

## Explicit Scope Decision

This plan adopts the recommended lower-risk path:

- Phase 1 structured mechanics target: `updateCharacterInfo.ops`
- Deferred target: `updateEncounter.ops`

That means the first structured-mechanics slice focuses on:

- PCs,
- allied NPCs,
- spell slots,
- HP,
- conditions,
- ammo and inventory-affecting combat updates,
- concentration/save pause metadata.

Enemy-side encounter updates remain on the current `updateEncounter.changes` path during the initial refactor so that prompt/validation/runtime cleanup can land without widening the combat-state mutation surface too early.

## Why This Change Is Needed

The narrator stack now has several improvements combat still lacks:

- canonical compressed runtime prompt authority,
- deterministic mechanics prechecks before LLM validation,
- thresholded validation compression,
- conservative low-risk validator skip routing,
- touched-character mechanical truth packs,
- additive structured mechanics ops,
- retry hygiene that keeps correction notes out of persistent conversation history.

Combat still relies on an older architecture where:

- prompt authority can drift between compressed and uncompressed variants,
- full encounter JSON is injected into validation,
- retry feedback is appended into combat conversation history,
- combat validation remains monolithic and expensive,
- mechanics and narration are tightly entangled inside one large output contract,
- `requestRoll` and deterministic concentration helpers exist but are not yet first-class combat contracts,
- combat still leans heavily on prose-only mechanics strings for updates.

The result is working gameplay, but with avoidable token cost, higher latency, and a larger hallucination surface than the narrator stack now has.

## Core Goals

1. Make Python the unambiguous source of truth for combat legality, state, and accounting.
2. Preserve vivid cinematic combat narration and enemy tactical competence.
3. Preserve LLM tactical flexibility for enemy intent without allowing mechanics drift.
4. Reduce prompt and validator duplication in combat.
5. Reduce token usage by sending smaller, more authoritative combat state packets.
6. Move common PC/allied combat mechanics away from prose-only interpretation and toward structured deterministic application.
7. Modernize combat validation using the same deterministic-first patterns now working in narrator flow.
8. Improve retry hygiene and reduce validation pollution in combat conversation history.
9. Maintain 5e correctness for HP, spell slots, conditions, concentration, save pauses, ammo, initiative, round transitions, and exit timing.

## Non-Goals

- Do not rewrite the entire combat system as a separate mechanics engine in one pass.
- Do not remove cinematic narration, tactical flavor, or enemy tactical initiative.
- Do not make monsters tactically stupid in the name of determinism.
- Do not replace combat narration with sterile state summaries.
- Do not change enemy-side mutation contract to structured `updateEncounter.ops` in the first slice.
- Do not break existing single-player compatibility or TT merge-safe boundaries.
- Do not aggressively cut tokens by removing necessary 5e rule/accounting guidance.

## Combat LLM Responsibility Boundary

The combat LLM should remain responsible for:

- vivid, cinematic combat narration,
- tactical interpretation of approved player combat intent,
- enemy combat intent and tactics,
- deciding when enemies coordinate, focus fire, pressure a weak target, exploit terrain, or challenge a strong target,
- choosing plausible target priorities based on creature intelligence, battlefield pressure, and recent events,
- converting that intent into the allowed action grammar.

The combat LLM should not remain authoritative for:

- acting out of turn,
- advancing phases or rounds illegally,
- changing HP or slot totals beyond legal bounds,
- consuming player prerolls,
- inventing creatures, resources, or illegal abilities,
- overriding Python-side concentration math or save/check pause rules,
- deciding mechanics in contradiction with the authoritative runtime state packet.

In short:

- LLM owns tactics and drama.
- Python owns reality.

## Current Pain Points

### 1. Prompt Authority Drift Still Exists in Combat

`core/managers/combat_manager.py` still uses a toggle-based prompt loader that can switch between compressed and uncompressed combat prompt files. The narrator stack now treats compressed prompts as canonical runtime authority.

Combat should do the same so there is one live combat contract, not two parallel prompt families with potential drift.

### 2. Combat Validation Is Still Heavy and Monolithic

`validate_combat_response()` in `core/managers/combat_manager.py` currently:

- loads the combat validation prompt,
- appends a fixed recent context window,
- injects full `Encounter Data` JSON,
- sends the response for LLM validation,
- retries several times,
- then fails open if retries exhaust.

That is much heavier and less precise than the narrator path in `main.py`, which now has deterministic prechecks, routing telemetry, thresholded compression, and truth packs.

### 3. Retry Hygiene Is Worse Than Narrator Flow

Combat still appends retry/error feedback into combat conversation history as user turns. That is exactly the kind of validation pollution that was cleaned up in the narrator refactor.

### 4. Mechanics and Narration Are Too Entangled

The combat prompt expects one model output to simultaneously handle:

- initiative obedience,
- phase-control correctness,
- save pause logic,
- HP/slot/ammo accounting,
- action routing,
- tactical reasoning,
- cinematic narration.

This works, but at higher cost and with more places for drift than necessary.

### 5. Runtime Context Is Overlapping and Token-Heavy

Combat currently injects several overlapping sources of combat truth:

- head context,
- encounter details,
- monster templates,
- location JSON,
- live tracker,
- creature states,
- AC block,
- phase state,
- party turn summary,
- active PC prompt block,
- required response block.

Many of those sections restate the same state in different forms.

### 6. Structured Mechanics Exist in the Repo but Not Yet in Combat Flow

The repo already has:

- `updateCharacterInfo.ops`,
- deterministic structured op application,
- `requestRoll` validation,
- deterministic concentration DC helpers,
- truth-pack infrastructure,
- validation routing infrastructure.

Combat is not yet benefiting from that full architecture.

## Desired End State

The final combat stack should work like this:

1. Python assembles a compact authoritative combat state packet.
2. The combat prompt tells the LLM what it is allowed to decide and what Python already owns.
3. The LLM decides cinematic narration, enemy tactical intent, tactical interpretation of PC intent, and constrained action serialization.
4. Deterministic Python prechecks reject explicit mechanical contradictions before LLM validation.
5. Combat validation is routed by risk and uses compact touched-entity truth packs instead of broad full-state dumps.
6. Common PC/allied combat mechanics are applied directly from structured ops in Python.
7. Save/check/concentration pauses use a first-class contract instead of ad hoc prose-only conventions.

## Design Principles

### Principle 1: One Canonical Combat Prompt Contract

Combat should have one live runtime authority for sim and validation prompts.

### Principle 2: Deterministic First, Tactical LLM Second

If legality, accounting, or phase control can be enforced by Python, it should be.

### Principle 3: Structured Mechanics, Freeform Tactics and Narration

Mechanics should become more structured. Enemy tactics and narration should remain flexible within the legal state boundary.

### Principle 4: Token Reduction by State Packet Discipline

We should remove duplicated state and redundant examples before removing rules coverage.

### Principle 5: Compact Truth Packs Over Full Dumps

Combat validator context should focus on touched combatants and touched mechanics, not full encounter/world state unless necessary.

### Principle 6: Retry Hygiene Must Match Narrator Stack

Validation-local corrections must stay local, not persistent in conversation history.

### Principle 7: Backward-Compatible Migration

Add structured combat paths first, keep compatibility paths alive, instrument fallback usage, then tighten later.

## Architecture Targets

### Python-Owned Combat Reality

Python should be authoritative for:

- initiative state,
- current phase,
- legal actor set,
- round advancement legality,
- exit timing legality,
- HP legality,
- slot legality,
- ammo legality where deterministically known,
- concentration DC math,
- save/check pause semantics,
- structured PC/allied combat updates.

### LLM-Owned Combat Judgment

The combat LLM should remain responsible for:

- vivid narration,
- tactical enemy behavior,
- deciding between reasonable legal tactical options,
- selecting among legal plausible targets,
- interpreting player combat declarations into the constrained action grammar,
- determining whether a monster presses advantage, protects an ally, retreats, coordinates, or shifts focus.

### Shared Contract Surface

Both runtime and validator should consume the same compact mechanical truth representation for touched PCs/allies and the same phase/turn legality packet.

## Proposed Workstreams

## Workstream A - Combat Contract Alignment and Canonical Prompt Authority

### Objective

Make compressed combat prompts the runtime authority and remove known contract drift.

### Files

- `core/managers/combat_manager.py`
- `prompts/combat/combat_sim_prompt_multipc_compressed.txt`
- `prompts/combat/combat_validation_prompt_multipc_compressed.txt`
- uncompressed combat prompt mirrors for documentation parity

### Changes

1. Make compressed combat prompts canonical runtime sources.
2. Treat uncompressed combat prompt files as mirrors/reference artifacts, not alternate live behavior.
3. Add contract parity tests covering:
   - phase stop rules,
   - batch enemy-phase rules,
   - round increment rules,
   - update routing rules,
   - exit requirements,
   - save pause semantics,
   - parameter key expectations.

### Deliverables

- one canonical live combat prompt family,
- prompt/runtime/validator parity tests for combat contracts.

## Workstream B - Combat Prompt Slimming and Reordering

### Objective

Reduce token load and improve instruction salience without sacrificing 5e accounting.

### Changes

Reorder the compressed combat sim prompt into a cleaner priority stack:

1. output contract,
2. source of truth and Python authority,
3. combat resolution ladder,
4. action grammar and routing,
5. phase/round/turn legality,
6. save/check/concentration pause semantics,
7. tactical guidance,
8. narration style guidance.

### New `@COMBAT_RESOLUTION_LADDER`

Introduce one explicit combat decision ladder:

- If user utterance is a status/query turn -> answer only, no state change.
- If a roll or save is required from a player -> emit/ask via pause contract and stop.
- If enemy/NPC/system actions are resolving deterministically in current phase -> narrate and emit legal structured actions.
- If state changes occur -> route them into constrained update actions.
- If next actor is a PC or boundary reached -> stop.

### Prompt Slimming Targets

1. Remove duplicated routing language.
2. Remove duplicated stop-rule language.
3. Collapse repeated round-increment warnings.
4. Replace multiple overlapping sections with one canonical phase legality block.
5. Reduce bulky examples to a minimal canonical example set.

### Deliverables

- slimmer compressed combat prompt,
- less duplicated logic text,
- better instruction priority ordering.

## Workstream C - Runtime State Packet Reduction

### Objective

Reduce token usage by sending smaller, more authoritative combat state packets.

### Files

- `core/managers/combat_manager.py`
- `core/managers/multi_pc_combat.py`

### Changes

1. Trim head-context payloads for PCs and NPCs to combat-relevant fields.
2. Reduce monster template payloads to encounter-present creatures and combat-relevant fields only.
3. Reduce or omit location JSON in combat unless current turn actually needs environmental/location rule context.
4. Replace large box-style required-response text with compact deterministic phase metadata.
5. Reduce overlap between:
   - live tracker,
   - creature states,
   - phase block,
   - party turn summary,
   - active PC context.

### Design Rule

If the same fact appears in more than one injected combat block, we should justify why both are needed. Otherwise, collapse to one authoritative section.

### Deliverables

- lower average combat prompt size,
- fewer overlapping state representations,
- preserved phase and initiative clarity.

## Workstream D - Combat Validation Routing, Truth Packs, and Telemetry

### Objective

Bring combat validation up to the same architecture level as narrator validation.

### Files

- `core/managers/combat_manager.py`
- new helpers under `utils/` or `core/validation/`

### Phase D1: Deterministic Prechecks Before LLM Validation

Add bounded explicit contradiction checks for combat responses:

- illegal round increment,
- illegal phase actor,
- acting while dead/unconscious,
- explicit HP contradictions,
- explicit slot/ammo underflow for touched PCs/allies,
- illegal stop before required boundary,
- illegal exit when living hostiles remain.

### Phase D2: Touched Combatant Truth Packs

Build compact truth packs for touched PCs/allied NPCs with:

- HP/max HP,
- conditions,
- spell slots,
- death saves when relevant,
- class feature usage when relevant,
- inventory/ammo only when the turn references them,
- concentration status when relevant.

### Phase D3: Validation Routing and Telemetry

Add combat-specific routing telemetry:

- skip reason,
- compression reason,
- payload size,
- validator mode,
- deterministic guard reason.

Combat skip routing should be conservative. Likely eligible turns:

- narration-only combat query branch,
- deterministic initiative/status answer branch with no state change.

High-risk turns should still validate:

- damage application,
- slot/ammo changes,
- concentration/save pauses,
- end-of-round transitions,
- enemy batch resolution,
- combat exit.

### Phase D4: Thresholded Compression

Use threshold-based validation compression, not unconditional compression.

### Deliverables

- smaller validation payloads,
- fewer unnecessary validator calls,
- cleaner logs and observability,
- lower latency on low-risk combat turns.

## Workstream E - Retry Hygiene and Fail Policy Modernization

### Objective

Remove combat retry pollution and replace blanket fail-open behavior with risk-aware handling.

### Changes

1. Keep combat validation retry corrections validation-local instead of appending them as user turns.
2. Keep invalid-JSON retry notes validation-local as well.
3. Replace blanket "assume valid" behavior for exhausted high-risk combat validation with a deterministic failure path.
4. Preserve compatibility/fail-soft behavior only for explicitly low-risk combat branches.

### Deliverables

- cleaner combat conversation history,
- reduced prompt noise on later rounds,
- safer handling of high-risk validator exhaustion.

## Workstream F - Structured PC/Allied Combat Mechanics Pilot

### Objective

Use the already-built `updateCharacterInfo.ops` system for combat-generated PC/allied mechanics.

### Files

- `prompts/combat/combat_sim_prompt_multipc_compressed.txt`
- `prompts/combat/combat_validation_prompt_multipc_compressed.txt`
- `core/ai/action_handler.py`
- `updates/update_character_info.py`

### Initial Supported Combat Ops Usage

Combat prompt examples and validator should encourage/accept `ops` for:

- `hp_delta`
- `set_hp`
- `spell_slot_delta`
- `condition_add`
- `condition_remove`
- `inventory_remove` for ammo and item spend
- `inventory_add` where appropriate

### Migration Rule

During this phase:

- `changes` remains valid,
- `changes + ops` is preferred for combat PC/allied updates,
- `ops` becomes the authoritative mechanic payload where present,
- prose remains the compatibility mirror.

### Explicit Deferral

Enemy-side `updateEncounter.ops` is not part of this first structured slice.

### Deliverables

- reduced prose-only combat mechanics interpretation for PCs/allies,
- deterministic application of common combat updates,
- measurable fallback logging when combat still uses prose-only updates.

## Workstream G - First-Class Combat Save and Concentration Contract

### Objective

Move combat pauses for player-facing saves/checks onto the existing `requestRoll` contract.

### Files

- `prompts/combat/combat_sim_prompt_multipc_compressed.txt`
- `prompts/combat/combat_validation_prompt_multipc_compressed.txt`
- `core/managers/combat_manager.py`
- `core/ai/action_handler.py`

### Changes

1. Use `requestRoll` as the preferred contract for:
   - saving throws,
   - ability checks in combat,
   - skill checks in combat,
   - concentration saves.
2. Require stop-after-request semantics.
3. Use deterministic concentration DC math: `max(10, floor(damage / 2))`.
4. Preserve prose-only compatibility during migration if needed, but make structured request the preferred path.

### Deliverables

- clearer combat pause semantics,
- explicit concentration contract,
- reduced ambiguity in validator reasoning.

## Workstream H - Expanded Combat Deterministic Guards

### Objective

Tighten combat legality only after telemetry confirms low false-positive rates.

### Candidate Guard Extensions

- unconscious vs HP contradictions,
- explicit ammo underflow for ranged attacks,
- explicit spell-slot underflow for combat casting,
- illegal action by forbidden phase actor,
- illegal stop mid enemy batch,
- illegal exit while hostiles remain,
- illegal round increment before all PCs acted.

### Deliverables

- stronger combat-state integrity,
- lower mechanics hallucination surface,
- preserved tactical/narrative freedom where explicit contradiction is absent.

## Workstream I - Deferred Second-Wave Encounter Ops

### Objective

Document the intentionally deferred follow-up slice.

### Deferred Scope

- additive `updateEncounter.ops`,
- deterministic enemy state application,
- further reduction of enemy-side prose update strings.

### Why Deferred

Because the highest-value first move is to:

- modernize prompt authority,
- shrink combat payloads,
- fix combat validation architecture,
- use existing structured character ops for PCs/allies first.

This gives most of the safety and efficiency benefit with lower change risk.

### Completion Role

If kept narrow, this is the capstone slice that completes the combat prompt/validation refactor as scoped in this plan.

The goal is not a new encounter engine. The goal is to bring enemy-side combat mutation routing into the same structured, Python-owned legality model already established for:

- combat prompt authority,
- combat validation routing and truth packs,
- PC/allied `updateCharacterInfo.ops`,
- combat `requestRoll` save/concentration pauses,
- bounded deterministic legality guards.

When this slice lands successfully, monsters stop being the last major prose-heavy combat mutation path.

### Recommended Narrow Scope

Workstream I should stay focused on enemy-side combat mutation routing only.

Recommended in scope:

- `updateEncounter` payloads that include additive `changes + ops`,
- deterministic application of supported enemy encounter ops,
- prompt and validator preference for structured enemy-side mutations,
- preservation of prose fallback while migration remains in progress,
- preservation of PC/allied routing on `updateCharacterInfo`.

### Recommended First Enemy Ops Surface

The safest first enemy op family is:

- `hp_delta`
- `set_hp`
- `condition_add`
- `condition_remove`
- `set_status`

These cover the highest-value enemy-state mutations already expressed repeatedly in combat prose:

- damage and healing,
- bloodied to defeated transitions,
- explicit dead/defeated/unconscious states,
- condition application and removal.

### Still Deferred Inside Workstream I

Even in Workstream I, keep these deferred unless a later follow-up explicitly broadens scope:

- creature spawn/despawn semantics,
- initiative queue rebuilds or reorder operations,
- encounter topology changes,
- broad battlefield-state ops,
- full enemy mechanics engine behavior,
- removal of prose fallback.

### Intended Architectural Outcome

This slice should complete the combat refactor by making the architecture symmetrical:

- PCs and allied NPCs prefer structured `updateCharacterInfo.ops`,
- enemies prefer structured `updateEncounter.ops`,
- Python owns legality and accounting for both domains,
- the LLM remains free to supply tactics, target selection, pressure, pacing, and vivid narration within those Python-owned bounds.

The expected result is:

- lower enemy-side hallucination surface,
- better prompt/validator/runtime contract symmetry,
- cleaner combat state mutation semantics,
- moderate additional token savings through reduced prose-heavy enemy mutation guidance,
- preserved tactical creativity instead of sterile combat narration.

### Primary Risks and Guardrails

#### Risk 1 - Scope expands into an encounter engine rewrite

Guardrail:

- keep the first slice limited to enemy HP, status, and conditions.

#### Risk 2 - Enemy ops drift into PC/allied routing semantics

Guardrail:

- preserve the boundary that enemy-side mutations stay on `updateEncounter` while PC/allied mutations stay on `updateCharacterInfo`.

#### Risk 3 - Prompt examples teach unsupported encounter ops

Guardrail:

- lock examples to the approved first-wave enemy op family only.

#### Risk 4 - Prose fallback is removed before runtime confidence exists

Guardrail:

- keep `changes` compatibility-valid throughout Workstream I.

### Recommended Tests Before Runtime Widening

Add a focused combat suite such as:

- `scripts/test_combat_encounter_ops_contract.py`

That suite should lock:

- enemy-side mixed `changes + ops` preference,
- preservation of prose-only fallback,
- routing separation between `updateEncounter` for enemies and `updateCharacterInfo` for PCs/allies,
- supported first-wave enemy ops (`hp_delta`, `set_hp`, `condition_add`, `condition_remove`, `set_status`),
- fail-open behavior for partial, unsupported, or ambiguous enemy ops payloads.

Keep green:

- `scripts/test_multi_pc_combat.py`
- `scripts/c5_regression_combat.py`
- existing PC/allied structured-ops contract suites.

### Practical Build Order For Workstream I

1. Lock contract tests for enemy-side structured encounter ops.
2. Update combat prompt and combat validator wording/examples to prefer enemy `changes + ops`.
3. Inspect `core/ai/action_handler.py` and `updates/update_encounter.py` for the narrowest runtime wiring needed.
4. Implement only the approved first-wave enemy ops.
5. Verify existing combat regressions and spec validation before any further widening.

## Rollout Plan

### Phase 0 - Safety Prep and Measurement

- add baseline token/latency measurement for combat sim and validation payloads,
- snapshot current prompt contracts in tests,
- capture replay fixtures for known-good combat flows.

### Phase 1 - Canonical Prompt Authority and Contract Parity

- make compressed combat prompts canonical,
- add parity tests,
- no behavior-changing mechanics migration yet.

### Phase 2 - Prompt Slimming and State Packet Reduction

- dedupe prompt rules,
- trim context injection,
- reduce overlap in combat runtime packets.

### Phase 3 - Combat Validation Modernization

- deterministic prechecks,
- truth packs,
- routing telemetry,
- thresholded compression,
- retry hygiene.

### Phase 4 - Structured PC/Allied Combat Mechanics

- use `updateCharacterInfo.ops` in combat paths,
- apply deterministic PC/allied updates directly,
- keep prose fallback.

### Phase 5 - Save/Concentration Contract

- move combat save/check pauses onto `requestRoll`,
- lock concentration handling to deterministic DCs.

### Phase 6 - Expanded Guard Set

- add more bounded deterministic legality checks,
- tighten only after telemetry confirms safe behavior.

### Phase 7 - Deferred Second-Wave Encounter Ops

- revisit `updateEncounter.ops` after the first-wave architecture is stable.

## Recommended First Build Slice

The safest first implementation slice is:

1. canonical compressed combat prompt authority,
2. combat contract parity tests,
3. combat prompt slimming and context reduction,
4. combat validation telemetry + thresholded compression,
5. combat retry hygiene,
6. touched-combatant truth packs for combat validation.

This should produce immediate efficiency and cleanliness gains without forcing the structured mechanics slice in the same patch.

## Testing Strategy

### Contract Tests

- compressed combat prompt is live runtime source,
- combat validator uses same canonical source,
- routing rules match runtime expectations,
- save pause semantics match runtime helpers,
- round increment rules match runtime guardrails,
- exit behavior matches runtime rules.

### Payload Hygiene Tests

- no duplicated contradictory rules in combat prompt,
- no unnecessary repeated mechanic/state sections,
- payload size bounded relative to current baseline,
- compact state packet remains sufficient for required behavior.

### Deterministic Guard Tests

- illegal round increment blocked,
- phase-actor violations blocked,
- explicit HP contradictions blocked,
- slot/ammo underflow blocked when parseable,
- illegal exit blocked when hostiles remain.

### Validation Routing Tests

- low-risk combat query branch can skip heavy validation,
- high-risk mutating combat turns still validate,
- thresholded compression routes correctly,
- routing telemetry reason codes emitted correctly.

### Truth Pack Tests

- touched PC/allied combatant truth packs include required mechanical data,
- inventory/ammo included only when relevant,
- irrelevant bulk state omitted.

### Structured Ops Tests

- combat-generated `updateCharacterInfo` mixed payloads accepted,
- deterministic combat ops applied correctly,
- prose fallback markers emitted when needed,
- unsupported ops with prose fallback remain compatible.

### Save/Concentration Tests

- `requestRoll` contract accepted in combat context,
- pause semantics enforced,
- concentration DC matches deterministic formula,
- contingent outcome not narrated in same response.

### Regression Suites To Keep Green

- `scripts/test_multi_pc_combat.py`
- `scripts/c5_regression_combat.py`
- `scripts/test_save_concentration_contract.py`
- new combat prompt/validation contract suites

## Performance Measurement Plan

Measure before/after on these combat scenarios:

1. PC melee attack requiring roll pause
2. PC spell turn with slot spend
3. enemy batch damaging multiple PCs
4. concentration hit requiring save request
5. dmGroup opening batch at round start
6. status/initiative query branch
7. combat exit on last hostile defeat

Metrics:

- total model calls per turn,
- combat sim payload chars,
- combat validation payload chars,
- validator compression usage,
- validator skip frequency,
- structured-op usage frequency,
- prose fallback frequency,
- wall-clock latency.

## Risks and Mitigations

### Risk 1: Prompt slimming weakens combat discipline

Mitigation:

- add contract tests first,
- slim duplicated rules before changing semantics,
- keep phase/round legality explicit.

### Risk 2: Over-tight deterministic guards reject good combat narration

Mitigation:

- only reject explicit contradictions,
- fail open on ambiguous prose,
- roll out guards incrementally.

### Risk 3: Structured combat ops introduce update regressions

Mitigation:

- use additive mixed payloads first,
- keep prose fallback alive,
- instrument fallback reasons.

### Risk 4: Token reduction removes needed tactical context

Mitigation:

- remove duplicated state first,
- keep compact authoritative tactical state packet,
- validate against replay fixtures.

### Risk 5: Enemy tactics become constrained or bland

Mitigation:

- explicitly preserve LLM tactical freedom for legal enemy intent,
- constrain legality/accounting, not tactical creativity,
- keep tactical target selection in LLM scope.

### Risk 6: Combat validator fail policy becomes too brittle

Mitigation:

- use risk-tiered handling,
- keep low-risk fail-soft where safe,
- make high-risk mutating turns fail closed only after deterministic guard and contract parity are in place.

## Success Criteria

This plan is successful when all of the following are true:

1. Combat compressed prompts are the canonical live runtime source.
2. Known combat contract drift between prompt, validator, and runtime is removed.
3. Combat prompt size drops measurably through deduplication and state-packet reduction.
4. Combat validation payload size drops measurably through truth packs and thresholded compression.
5. Combat retry corrections no longer pollute persistent conversation history.
6. Common PC/allied combat mechanics can be applied through deterministic structured ops.
7. Combat save/concentration pauses use a first-class contract.
8. Enemy tactical competence and vivid narration remain intact in gameplay testing.
9. 5e accuracy and accounting are preserved or improved.

## Recommended OpenSpec Breakdown

When implementation begins, split into narrow changes similar to the narrator refactor:

1. `combat-prompt-validator-contract-alignment`
2. `combat-runtime-authority-and-efficiency`
3. `combat-validation-routing-and-truth-pack`
4. `combat-structured-pc-allied-ops-pilot`
5. `combat-save-concentration-contract`
6. `combat-expanded-deterministic-guards`
7. `combat-encounter-ops-second-wave` (deferred)

## Recommended Implementation Order

If executed as a practical build sequence, use this order:

1. canonical compressed prompt authority for combat,
2. combat contract parity tests,
3. combat prompt dedupe and context slimming,
4. combat validation routing + telemetry + truth packs,
5. combat retry hygiene and fail-policy cleanup,
6. structured `updateCharacterInfo.ops` for combat PC/allied updates,
7. combat `requestRoll` + concentration contract,
8. expanded deterministic combat guards,
9. deferred `updateEncounter.ops` follow-up.

## Final Summary

The narrator refactor showed the right pattern:

- one canonical prompt contract,
- deterministic-first validation,
- compact truth packs,
- thresholded compression,
- retry hygiene,
- additive structured mechanics.

Combat should follow the same pattern, but with an explicit preservation clause:

- keep combat tactically alive,
- keep monsters capable of coordination and target prioritization,
- keep narration vivid,
- make Python own the legality and accounting beneath that layer.

That is the balance this plan is designed to achieve.

## Post-Archive Builder Handoff (2026-03-11)

Reference archive:

- `openspec/changes/archive/2026-03-11-combat-runtime-authority-and-efficiency/`

That archived change completed the first-wave combat hardening slice:

- canonical compressed combat prompt authority,
- combat contract parity coverage,
- combat prompt slimming and runtime packet reduction,
- combat validation telemetry and thresholded compression,
- touched-combatant truth packs,
- retry-local correction hygiene.

It also explicitly deferred two follow-on slices that are now the safest next implementation path:

1. `combat-structured-pc-allied-ops-pilot`
2. `combat-save-concentration-contract`

### Recommended Follow-On Order

The next practical build order after the archived runtime-authority change is:

1. deepen combat adoption of `updateCharacterInfo.ops` for PCs and allied NPCs,
2. then align combat save/check/concentration pauses to the first-class `requestRoll` contract.

This order is recommended because:

- the runtime structured-ops path already exists and is working in `updates/update_character_info.py`,
- combat currently still teaches mostly prose-era HP, slot, ammo, and condition updates,
- `requestRoll` and concentration helpers already exist as scaffolding, but combat prompts still use older prose-only guidance,
- save/concentration alignment becomes cleaner once combat PC/allied mechanics already prefer structured updates.

### Follow-On Change 1 - `combat-structured-pc-allied-ops-pilot`

#### Objective

Adopt the existing additive `updateCharacterInfo.ops` contract inside combat prompt, validator, and combat-facing tests for PC and allied NPC mutations, while preserving prose fallback and deferring enemy-side `updateEncounter.ops`.

#### Scope

In scope:

- combat prompt/validator contract updates for mixed `changes + ops` payloads,
- combat preference for structured mechanics on PC/allied updates,
- deterministic combat-facing tests for HP, spell slot, ammo, inventory, and condition updates,
- fallback telemetry preservation when combat still uses prose-only updates.

Out of scope:

- enemy-side `updateEncounter.ops`,
- full deprecation of prose `changes`,
- save/check runtime flow redesign.

#### Combat-Specific Ops Priority

Combat should prefer `changes + ops` for:

- `hp_delta`
- `set_hp`
- `spell_slot_delta`
- `condition_add`
- `condition_remove`
- `inventory_remove` for ammo and consumable spend
- `inventory_add` where combat resolution legitimately grants or returns an item

#### File Targets

- `prompts/combat/combat_sim_prompt_multipc_compressed.txt`
- `prompts/combat/combat_validation_prompt_multipc_compressed.txt`
- combat prompt mirror files as needed for parity/docs
- `core/ai/action_handler.py` only for narrow combat-routing adjustments if required
- `updates/update_character_info.py` only if combat reveals a missing supported op shape

#### Required Contract Direction

During this slice:

- `changes` remains compatibility-valid,
- `changes + ops` becomes the preferred combat PC/allied payload,
- `ops` is the authoritative mechanic payload where present,
- prose remains the mirror/fallback path,
- enemy-side `updateEncounter` remains unchanged.

#### Concrete Prompt Gaps To Close

Current combat prompts still rely heavily on prose-era guidance such as:

- slot spend written only in `changes`,
- ammo spend written only in `changes`,
- healing deferral described only through prose fields,
- `updateCharacterInfo` examples that do not show mixed `changes + ops` payloads.

This slice should update combat examples so the model sees structured mechanics as the preferred combat expression for PC/allied updates without breaking current fallback behavior.

#### Recommended Tests

Keep green:

- `scripts/test_multi_pc_combat.py`
- `scripts/c5_regression_combat.py`
- `scripts/test_update_character_ops_contract.py`

Add focused combat coverage:

- `scripts/test_combat_structured_ops_contract.py`

That suite should cover:

- combat prompt/validator parity for `changes + ops`,
- enemy-side `updateEncounter` still prose-only in this slice,
- mixed payload acceptance for damaged PCs/allied NPCs,
- ammo and slot-spend examples preferring ops,
- unsupported ops falling back only when prose `changes` is also present.

### Follow-On Change 2 - `combat-save-concentration-contract`

#### Objective

Move combat-facing save/check pauses onto the existing `requestRoll` contract and lock concentration requests to deterministic 5e DC handling.

#### Why This Comes Second

- the request scaffolding already exists in `core/managers/combat_manager.py` and `core/ai/action_handler.py`,
- combat prompts currently still use prose-era guidance such as "concentration check required",
- save/check pauses become easier to reason about once combat already prefers structured PC/allied state updates.

#### Required Contract Direction

Combat should prefer `requestRoll` for:

- saving throws,
- ability checks in combat,
- skill checks in combat,
- concentration saves.

This slice should enforce:

- stop-after-request semantics,
- no contingent success/failure narration in the same response,
- concentration DC formula `max(10, floor(damage / 2))`,
- prose-only compatibility retained during migration.

#### File Targets

- `prompts/combat/combat_sim_prompt_multipc_compressed.txt`
- `prompts/combat/combat_validation_prompt_multipc_compressed.txt`
- combat prompt mirror files as needed for parity/docs
- `core/managers/combat_manager.py` for narrow helper usage if needed
- `core/ai/action_handler.py` only for narrow metadata handling if required

#### Recommended Tests

Keep green:

- `scripts/test_multi_pc_combat.py`
- `scripts/c5_regression_combat.py`
- `scripts/test_save_concentration_contract.py`

Add focused combat coverage:

- `scripts/test_combat_save_concentration_contract.py`

That suite should cover:

- combat prompt/validator parity for `requestRoll`,
- stop-after-request enforcement,
- concentration hits producing deterministic DC expectations,
- no same-response contingent outcome narration,
- prose-only compatibility remaining valid during migration.

### Recommended Builder Sequence

Use the next builder passes in this order:

1. scaffold and execute `combat-structured-pc-allied-ops-pilot`,
2. verify combat regressions stay green,
3. then scaffold and execute `combat-save-concentration-contract`,
4. only after both are stable, revisit deferred combat deterministic guards or `updateEncounter.ops`.

### Guardrails For Both Follow-On Slices

- Do not widen to `updateEncounter.ops` yet.
- Do not deprecate prose fallback yet.
- Do not expand into full roll resolution.
- Keep changes narrow, merge-safe, and additive.
- Preserve vivid narration and enemy tactical competence while moving legality/accounting further into Python-owned structure.
