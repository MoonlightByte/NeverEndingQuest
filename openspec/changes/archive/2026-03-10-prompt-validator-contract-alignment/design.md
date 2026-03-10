## Context

This change is the first implementation slice of the larger prompt/validator hardening program described in `plans/prompt-validator-fix.md`. The immediate problem is contract drift, not missing rules text. The narrator system prompt, validation prompt, and runtime action handler currently disagree on a few action contracts, with `rest` being the clearest production example.

The current stack has three important properties that this design MUST preserve:

- Python state remains ground truth for mechanics.
- Validation retries remain fail-closed and transient.
- Single-player and tabletop mode share the same action contract surface.

This phase intentionally avoids the broader structured-mechanics refactor. It is a contract-alignment and regression-coverage pass only.

For clarity, this change is Phase 1A of the larger plan: `rest` parity plus parity scaffolding. The next parity slice can address save/restore/list/delete-save and `createNewModule` after this narrower cut lands cleanly.

## Goals / Non-Goals

**Goals:**
- Align action-name and parameter-shape expectations across system prompt, validation prompt, and runtime for the first parity slice.
- Make `rest` a fully consistent first-class action across prompt, validator, and runtime.
- Add automated parity checks so future prompt edits cannot silently drift away from runtime behavior.
- Reduce false validation failures caused by stale prompt contracts.
- Preserve existing retry-local correction behavior and deterministic fail-closed guards.
- Keep the covered action set explicit so the builder cannot silently expand the change past the intended Phase 1A boundary.

**Non-Goals:**
- Do not introduce a new universal action-schema generator in this phase.
- Do not redesign `updateCharacterInfo` into structured ops yet.
- Do not broaden the scope into combat mechanics, saving-throw architecture, or validator-mode routing.
- Do not remove legacy compatibility paths unless they are already dead and covered by tests.
- Do not include save/restore/list/delete-save or `createNewModule` contract cleanup in this change; treat those as Phase 1B follow-up work.

## Decisions

### Decision 1: Treat this as a narrow phase-1 alignment change, not the full refactor

**Decision:** This OpenSpec change SHALL cover only prompt/runtime contract alignment and parity regressions.

**Rationale:** The broader prompt-validator fix plan is at least a five-phase program. Starting with a narrow alignment slice reduces risk, makes review easier, and gives the builder a safe first target.

**Alternatives considered:**
- Build the full structured-mechanics refactor immediately: rejected as too large and too risky.
- Change prompts only without tests: rejected because drift would recur.

### Decision 2: Keep runtime as the operational contract source for this phase

**Decision:** Runtime behavior in `core/ai/action_handler.py` SHALL be treated as the operational baseline for the covered actions, and prompt/validator contracts SHALL be brought into alignment with it unless an obvious runtime bug is discovered.

**Rationale:** Runtime is what actually executes game state. For phase 1, the safest move is to align prompts to reality rather than redesign runtime and prompt simultaneously.

**Alternatives considered:**
- Make prompt text the source of truth and change runtime to match: rejected for this phase because it can create hidden gameplay regressions.
- Introduce a new shared action-schema file now: deferred to a later phase because it adds architecture churn beyond this slice.

### Decision 3: `rest` remains a dedicated action with Python-owned recovery semantics

**Decision:** `rest` SHALL remain the dedicated action for short and long rests, and validation text SHALL explicitly reflect Python-owned recovery behavior.

**Rationale:** Runtime already has a rest handler. The main issue is stale validator wording that still expects direct `updateCharacterInfo` rest recovery.

**Alternatives considered:**
- Revert to direct narrator-authored `updateCharacterInfo` rest flows: rejected because it re-expands mechanics-by-prose.
- Add new rest sub-actions now: deferred as unnecessary for contract sync.

### Decision 4: Add parity tests instead of inventing a heavy schema layer

**Decision:** Phase 1 SHALL enforce parity with regression tests that assert:
- supported actions appear in the relevant prompts,
- prompt parameter examples match runtime expectations for the covered actions,
- stale contradictory wording is absent for covered actions.

**Rationale:** Tests are the lightest merge-safe way to stop regression now.

**Alternatives considered:**
- Manual review only: rejected because drift already happened.
- Introduce a generated prompt build system: deferred to later phases.

### Decision 5: The covered action set for this change is explicit and narrow

**Decision:** The phase-1 parity slice in this OpenSpec change SHALL cover `rest` only.

**Rationale:** `rest` is the clearest production mismatch and gives the project a safe first landing zone for parity testing. Expanding to save/restore or `createNewModule` in the same change would blur review boundaries and increase regression risk.

**Alternatives considered:**
- Cover `rest`, save/restore, and `createNewModule` together: deferred to the next change slice to keep this phase reviewable.
- Leave the covered-action set implicit: rejected because it invites scope creep and weakens acceptance criteria.

### Decision 6: Parity must cover both prompt variants that runtime can load

**Decision:** Regression coverage for this slice SHALL check both compressed and uncompressed prompt copies.

**Rationale:** Runtime currently uses `prompts/system_prompt.txt`, while validation may load compressed or uncompressed variants depending on configuration. Checking only one prompt file would allow real production drift to slip through.

**Alternatives considered:**
- Test compressed prompts only: rejected because it misses active runtime behavior.
- Test uncompressed prompts only: rejected because compressed validation prompt drift already caused production issues.

### Decision 7: Preserve compatibility shims where practical

**Decision:** If save/restore or other auxiliary contracts differ between prompt and runtime, phase 1 SHOULD prefer one of:
- prompt correction to runtime,
- runtime compatibility shim plus prompt correction,
- additive tests documenting the intended contract.

**Rationale:** Some stale prompt assumptions may still exist in tests or side paths. A soft landing is safer than abrupt cleanup.

## Risks / Trade-offs

- **[Risk] Prompt alignment may expose stale tests or hidden assumptions** -> Mitigation: add/adjust focused regression tests in the same change and keep compatibility shims if needed.
- **[Risk] Runtime may itself contain outdated parameter expectations for non-core actions** -> Mitigation: restrict the first parity slice to `rest` and record newly discovered auxiliary drift for the follow-up slice.
- **[Risk] Prompt edits could accidentally affect narrative behavior beyond contract text** -> Mitigation: keep edits surgical and avoid broad reordering in this phase.
- **[Risk] Builders may over-expand scope into full validator refactor** -> Mitigation: tasks and builder prompt MUST forbid structured-mechanics or pipeline redesign in this change.
- **[Trade-off] Tests enforce parity but do not eliminate all future architecture duplication** -> Accepted for this phase because they provide immediate protection with minimal churn.

## Migration Plan

1. Align compressed prompt and compressed validator contracts for `rest` first.
2. Align uncompressed prompt and validator copies to the same contract.
3. Audit runtime handling for `rest`, keeping behavior as the baseline unless an obvious runtime bug is found.
4. Add regression tests that fail on drift across both prompt variants.
5. Record deferred auxiliary drift discovered during audit for the next parity slice.
6. Run targeted verification and stop.

Rollback strategy:
- Prompt edits are file-local and can be reverted cleanly.
- Runtime compatibility shims SHOULD be additive so rollback is low risk.
- New tests can remain even if prompt wording must be adjusted again.

## Deferred Follow-Ups

- Phase 1B SHOULD address save/restore/list/delete-save parameter-shape drift after `rest` parity lands.
- A later contract slice SHOULD address `createNewModule` prompt/runtime expectations explicitly rather than folding that work into this change.
- For later phases, the project can still decide between a generated action-schema source file and parity-test-first enforcement, but that decision is outside Phase 1A.
