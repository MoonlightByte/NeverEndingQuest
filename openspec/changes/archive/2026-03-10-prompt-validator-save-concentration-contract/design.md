## Context

NeverEndingQuest currently asks players for many saves and checks through prose narration only. That keeps narration flexible, but it leaves the validator with no explicit action contract for an important pause point, and it keeps concentration handling partly encoded as prompt text instead of as a deterministic rule that runtime code can share.

This change prepares a narrow, builder-friendly path to fix that gap. It does not attempt to solve all dice handling. It introduces only enough structure to make save/check requests explicit and to lock the 5e concentration DC rule before any broader runtime tightening.

## Goals / Non-Goals

**Goals:**
- Add a lightweight first-class contract for player-facing save/check requests.
- Define a deterministic concentration DC helper contract.
- Preserve current prose-only behavior as a compatibility path during migration.
- Keep the rollout narrow, test-first, and merge-safe.

**Non-Goals:**
- No full dice engine.
- No automatic roll resolution or state mutation from the request alone.
- No combat round-flow rewrite.
- No deprecation of prose-only save/check narration in this change.

## Decisions

### Decision 1: Use `requestRoll` as the additive action contract

**Decision:** The new structured contract SHALL use `requestRoll` as the default action name.

**Rationale:** `plans/prompt-validator-fix.md` already identifies `requestRoll` as the preferred lightweight shape for player-facing saves/checks. Reusing that name keeps the change aligned with the planning baseline.

**Guidance:** If implementation inspection uncovers an already-canonical action name with equivalent semantics, builders SHOULD report it before changing the contract.

### Decision 2: Keep the payload minimal and explicit

**Decision:** `requestRoll.parameters` SHALL lock this minimum payload shape:
- `characterName` (required)
- `rollType` (required; one of `saving_throw`, `ability_check`, `skill_check`)
- `dc` (required integer)
- `reason` (required short string)
- `ability` (required for `saving_throw` and `ability_check`)
- `skill` (required for `skill_check`)
- `advantage` (optional; `normal`, `advantage`, or `disadvantage`)

**Rationale:** This is enough for prompt clarity, validation, and future runtime helpers without pulling result resolution into this change.

### Decision 3: `requestRoll` remains a pause contract, not a resolution contract

**Decision:** When `requestRoll` is emitted, the narrator/validator contract SHALL treat it as a pause point. The same response SHALL NOT narrate contingent player-roll success or failure after issuing the request.

**Rationale:** This matches the current gameplay pattern and avoids accidental partial dice-engine behavior.

### Decision 4: Concentration DC uses one deterministic formula

**Decision:** Concentration save DC SHALL be computed as `max(10, floor(damage / 2))`.

**Rationale:** This is the 5e rule and gives runtime and validator paths one shared, testable source of truth.

**Guidance:** Builders SHOULD implement the helper in a small reusable function so prompt tests, runtime logic, and future combat paths can share it.

### Decision 5: Prose compatibility remains during migration

**Decision:** Prose-only save/check narration SHALL remain valid during this change unless and until a later change explicitly deprecates it.

**Rationale:** The codebase still contains many prose-era examples and combat behaviors. Narrow migration reduces risk.

## Risks and Mitigations

- **Risk:** Builders accidentally widen scope into full roll resolution.
  - **Mitigation:** Tasks and builder prompts explicitly forbid dice-engine work.
- **Risk:** Prompt and runtime drift reappears if only prompts are updated.
  - **Mitigation:** Phase 1 locks source contracts with focused tests before runtime edits.
- **Risk:** Concentration logic diverges between combat and non-combat contexts.
  - **Mitigation:** The change requires one deterministic DC helper contract and explicit runtime touchpoints.
- **Risk:** Existing prose behavior breaks in tabletop combat.
  - **Mitigation:** Compatibility tests remain mandatory and prose-only requests stay allowed.

## Runtime Boundaries

- `main.py` and `core/managers/combat_manager.py` are expected consumers of the contract.
- `core/ai/action_handler.py` is the expected parser boundary for a new structured action.
- A helper under `utils/` or `core/validation/` SHOULD hold payload validation and concentration DC logic.
- Existing combat prompts MAY need only minimal clarifying edits; broad combat prompt rewrites are out of scope.

## Migration Plan

### Phase 1 - Contract and tests
- Add focused tests for `requestRoll` source references, payload shape, and concentration DC rule.
- Do not change runtime behavior yet.

### Phase 2 - Prompt and validator contract update
- Update compressed narrator and validator prompts to recognize `requestRoll` and the concentration rule.
- Keep prose-only save/check requests documented as compatibility behavior.

### Phase 3 - Runtime scaffolding
- Add a small request payload validator/helper.
- Add deterministic concentration DC helper wiring.
- Add minimal runtime references without broad flow changes.

### Phase 4 - Compatibility and negative-path verification
- Add explicit tests for structured requests, prose compatibility, and invalid payload rejection.
- Confirm pause semantics remain intact.

### Phase 5 - Final verification
- Run targeted tests, syntax checks, and `openspec validate`.
- Declare the change apply-ready for implementation review.

## Deferred Follow-Ups

- Structured roll-result ingestion.
- First-class trap/save metadata beyond the initial contract.
- Broader combat prompt alignment once the lightweight contract is proven.
- Any future deprecation of prose-only roll requests.
