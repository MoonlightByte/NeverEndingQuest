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

---

## Prompt 1 - Isolate `/init` Gate Handler

Implement tasks `1.1` and `1.2` from `tasks.md`.

Scope:
- `core/managers/combat_manager.py`

Requirements:
- Extract `/init` two-group initiative gate logic into one helper with explicit inputs/outputs.
- Keep behavior equivalent for parse errors, roll validation, winner resolution, persistence, mirror sync, and message output.
- Replace inline gate block with thin helper invocation.

Edit strategy:
- One patch for helper creation.
- One patch for caller replacement.
- Compile after each patch.

Verify before moving on:
- `python3 -m py_compile core/managers/combat_manager.py`

---

## Prompt 2 - Preserve TT Marker and Sync Semantics

Implement tasks `1.3`, `1.4`, `2.1`, and `2.2`.

Scope:
- `core/managers/combat_manager.py`
- `core/managers/combat_state_sync.py`

Requirements:
- Ensure helper path still applies `apply_opening_batch_marker(...)` semantics.
- Ensure startup/resume still applies `normalize_phase1_initiative(...)` then `normalize_multi_pc_roster(...)`.
- Keep writes additive and fail-open.

Verify before moving on:
- `python3 -m py_compile core/managers/combat_manager.py core/managers/combat_state_sync.py`
- `python3 scripts/test_multi_pc_combat.py`

---

## Prompt 3 - Builder Compile Guard Script

Implement tasks `3.1`, `3.2`, and `3.3`.

Scope:
- `scripts/check_builder_patch_syntax.py` (new)

Requirements:
- Compile explicit file arguments; emit per-file pass/fail; return non-zero on any failure.
- Optional convenience mode: no args -> compile changed Python files from git diff.
- Keep script read-only and non-destructive.

Verify before moving on:
- `python3 -m py_compile scripts/check_builder_patch_syntax.py`
- `python3 scripts/check_builder_patch_syntax.py core/managers/combat_manager.py core/managers/combat_state_sync.py`

---

## Prompt 4 - Final Verification and Smoke

Implement tasks `4.1` to `4.4`.

Scope:
- validation only

Required commands:
- `python3 -m py_compile core/managers/combat_manager.py core/managers/combat_state_sync.py core/generators/combat_builder.py scripts/check_builder_patch_syntax.py`
- `python3 scripts/test_multi_pc_combat.py`
- `python3 scripts/check_builder_patch_syntax.py core/managers/combat_manager.py core/managers/combat_state_sync.py core/generators/combat_builder.py`
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
- Do not start upstream-wide refactor here; that belongs to v2 plan.
