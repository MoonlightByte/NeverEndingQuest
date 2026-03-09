## Kimi Builder Execution Prompts - tt-combat-manager-hardening-only

Use this file as the plan-to-builder handoff for TT-only hardening in the current test build.

---

## Execution Contract

- MUST stay TT-only for this change; do not expand into broad upstream decomposition.
- MUST keep host edits merge-safe and mark integration points with `# TABLETOP MODE:`.
- MUST preserve single-player behavior and existing multi-PC rules semantics.
- MUST apply one anchored patch at a time, then run compile checks before next patch.
- MUST avoid broad regex/script rewrites in indentation-sensitive blocks.
- SHOULD prefer helper extraction over large inline rewrites.

## Kimi K2.5 Reliability Addendum

- MUST keep each patch to one logical block.
- MUST run `python3 -m py_compile <touched_file>` immediately after each patch.
- MUST preserve exact existing `/init` gate output strings containing `[skipTTS][prefill:/init ]`.
- MUST preserve existing marker lifecycle contracts and debug log strings already asserted by `scripts/c5_regression_combat.py`.
- MUST stop and fix immediately if compile or contract tests fail.

---

## Prompt 1 - Create Compile Guard First

Implement tasks `1.1`, `1.2`, and `1.3` from `tasks.md`.

Scope:
- `scripts/check_builder_patch_syntax.py` (new)

Requirements:
- Compile explicit Python file arguments and emit deterministic per-file results.
- Use ASCII tags only, for example `[PASS]` and `[FAIL]`.
- Exit non-zero on any compile/read failure.
- Keep script read-only and non-destructive.
- Include header docstring usage examples for explicit-file mode.

Edit strategy:
- One patch only.
- Compile script immediately after patch.

Verify before moving on:
- `python3 -m py_compile scripts/check_builder_patch_syntax.py`
- `python3 scripts/check_builder_patch_syntax.py core/managers/combat_manager.py core/managers/combat_state_sync.py core/managers/multi_pc_combat.py`

---

## Prompt 2 - Extract `/init` Gate Helper Only

Implement task `2.1` from `tasks.md`.

Scope:
- `core/managers/combat_manager.py`

Requirements:
- Add one dedicated helper for TT `/init` gate handling with explicit inputs/outputs.
- Keep helper behavior-equivalent to current inline branch semantics.
- Do not replace caller inline branch in this prompt.
- Do not alter marker lifecycle touchpoints outside helper creation.

Edit strategy:
- One anchored helper-addition patch.
- No broad movement of existing blocks.

Verify before moving on:
- `python3 -m py_compile core/managers/combat_manager.py`

---

## Prompt 3 - Thin Caller Replacement for `/init` Gate

Implement tasks `2.2`, `2.3`, and `2.4` from `tasks.md`.

Scope:
- `core/managers/combat_manager.py`

Requirements:
- Replace inline `/init` gate branch in `run_combat_simulation()` with thin helper invocation.
- Preserve exact gate strings for invalid input and pending guidance (`[skipTTS][prefill:/init ] ...`).
- Preserve winner writes (`initiativeMode`, `initiativeRolls`, `initiativeWinner`, `roundStartsWith`, `awaitingPcGroupRoll`).
- Preserve compatibility mirror write to `party_tracker.json`.
- Preserve dmGroup forced enemy fall-through behavior.
- Keep TT guard behind existing multi-PC checks.

Edit strategy:
- One patch for caller replacement only.
- No unrelated refactor in adjacent command-processing branches.

Verify before moving on:
- `python3 -m py_compile core/managers/combat_manager.py`
- `python3 scripts/check_builder_patch_syntax.py core/managers/combat_manager.py`

---

## Prompt 4 - Ownership/Lifecycle Hardening + Convenience Mode

Implement tasks `3.1`, `3.2`, `3.3`, `3.4`, and `4.1` from `tasks.md`.

Scope:
- `core/managers/combat_manager.py`
- `core/managers/combat_state_sync.py` (only if needed for marker/roster compatibility)
- `scripts/check_builder_patch_syntax.py`

Requirements:
- Keep `normalize_phase1_initiative(...)` in `core/managers/combat_manager.py` (no relocation).
- Preserve startup/resume normalization + mirror update behavior.
- Preserve marker lifecycle at all existing touchpoints:
  - `/init` winner resolution,
  - round-start reapplication,
  - post-opening-batch clear.
- Retain `# TABLETOP MODE:` comments on integration points.
- Add optional convenience mode to syntax guard for changed `.py` files from git diff when no args are provided.

Verify before moving on:
- `python3 -m py_compile core/managers/combat_manager.py core/managers/combat_state_sync.py scripts/check_builder_patch_syntax.py`
- `python3 scripts/test_multi_pc_combat.py`
- `python3 scripts/c5_regression_combat.py`

---

## Prompt 5 - Final Verification and Smoke

Implement tasks `5.1` to `5.6`.

Scope:
- validation only

Required commands:
- `python3 -m py_compile core/managers/combat_manager.py core/managers/combat_state_sync.py core/generators/combat_builder.py scripts/check_builder_patch_syntax.py`
- `python3 scripts/check_builder_patch_syntax.py core/managers/combat_manager.py core/managers/combat_state_sync.py core/generators/combat_builder.py`
- `python3 scripts/test_multi_pc_combat.py`
- `python3 scripts/c5_regression_combat.py`
- `openspec validate tt-combat-manager-hardening-only`

Manual smoke checklist:
1. dmGroup opener path (`/init` loser/tie for PCs) does not phase-loop.
2. pcGroup opener path keeps player-first flow.
3. No false roster loss for multi-PC participants.
4. Single-player combat path remains unchanged.

---

## Stop Conditions

- Stop immediately if compile fails after a patch and fix before proceeding.
- Stop and report if behavior drift is detected in `/init` gate semantics.
- Stop and report if `scripts/c5_regression_combat.py` contract checks fail after extraction.
- Do not start upstream-wide refactor here; that belongs to v2 plan.
