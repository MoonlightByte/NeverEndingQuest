## Context

`core/managers/combat_manager.py` combines upstream combat flow and TABLETOP MODE extensions in one large function (`run_combat_simulation`). The most fragile parts are TT initiative gate handling (`/init`) and phase/round sync branches that are deeply nested and frequently edited.

Interim combat updates already landed after this change was drafted:
- startup normalization through `normalize_phase1_initiative(...)` in `combat_manager.py`,
- fast-lane startup when `awaitingPcGroupRoll=True`,
- opening marker lifecycle spanning `/init`, round-start, and post-opening-batch clear.

This design revision hardens helper isolation against that newer baseline.

For the current test build, we need TT-only hardening: improve edit safety and testability without broad upstream refactor risk.

## Goals / Non-Goals

**Goals:**
- Extract TT initiative gate logic into a dedicated helper with clear contract.
- Preserve current TT state-sync ownership boundaries (no relocation in this change).
- Add a deterministic builder syntax check utility that fails fast on malformed Python edits.
- Preserve current gameplay behavior (no rules change).

**Non-Goals:**
- Full upstream combat manager decomposition in this change.
- Prompt architecture redesign.
- Encounter schema redesign.
- UI or socket payload refactors not required by TT gate extraction.

## Decisions

1) TT-only extraction boundary (MUST)
- Keep extraction scoped to TT-specific branches in `run_combat_simulation`.
- Do not move unrelated upstream blocks in this change.
- Rationale: reduces regression surface for current test build.
- Alternative considered: full function decomposition now. Rejected for risk and schedule.

2) `/init` gate helper contract (MUST)
- Introduce a helper (for example `_handle_group_initiative_gate(...)`) that:
  - validates `/init <1-20>`,
  - resolves winner and phase,
  - updates encounter initiative fields,
  - applies `openingEnemyBatchPending` marker via `apply_opening_batch_marker(...)`,
  - persists encounter + mirror payload,
  - preserves deterministic gate messaging (`[skipTTS][prefill:/init ]`) and dmGroup forced enemy fall-through behavior,
  - returns structured result to caller.
- Rationale: deterministic behavior and isolated testing.
- Alternative considered: leave inline and add comments. Rejected as insufficient for reliability.

3) Compile-guard utility (MUST)
- Add `scripts/check_builder_patch_syntax.py` that compiles passed Python files and exits non-zero on failure.
- SHOULD support convenience mode for changed files from git diff.
- Rationale: catches indentation/syntax regressions immediately in builder loop.

4) Baseline ownership and marker lifecycle invariants (MUST)
- Keep `normalize_phase1_initiative(...)` defined/invoked in `combat_manager.py` for this change.
- Keep `combat_state_sync.py` ownership limited to marker/roster helpers (`apply_opening_batch_marker`, `normalize_multi_pc_roster`).
- Preserve opening marker lifecycle across all current touchpoints:
  - `/init` winner resolution,
  - round-start reapplication,
  - post-opening-batch clear to transition back to PC phase.

5) Compatibility invariants (MUST)
- Single-player behavior remains unchanged.
- TT refactor remains additive and fail-open for legacy encounter data.
- Existing logging categories remain stable where practical.

## Risks / Trade-offs

- [Risk] helper extraction changes control flow ordering -> Mitigation: preserve branch order and side effects; verify with existing combat tests and smoke flow.
- [Risk] hidden reliance on local variables in inline block -> Mitigation: explicit helper parameters and return payloads.
- [Risk] accidental upstream behavior drift -> Mitigation: TT-only scope guard and no unrelated code moves.
- [Trade-off] partial refactor leaves monolith present -> acceptable for test build; full decomposition deferred to v2 plan.

## Migration Plan

1. Extract `/init` gate logic into helper with behavior-equivalent outputs.
2. Replace inline `/init` branch with thin helper invocation.
3. Preserve current ownership split: keep phase1 normalization in `combat_manager.py`; keep marker/roster helpers in `combat_state_sync.py`.
4. Add `scripts/check_builder_patch_syntax.py`.
5. Validate with compile + `scripts/test_multi_pc_combat.py` + `scripts/c5_regression_combat.py` + dmGroup/pcGroup smoke checks.

Rollback strategy:
- Revert helper invocation and restore previous inline block if any behavioral regression appears.
- Revert compile-guard script independently (no runtime dependency).

## Open Questions

- Should compile-guard script run only explicit file args in test build, or include git-diff auto-detection now?
- Do we include one targeted regression test specifically for `/init` helper return contract in this change, or defer to broader v2 test expansion?
