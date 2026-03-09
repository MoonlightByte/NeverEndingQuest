## 1. Builder Compile Guard Script (First)

- [x] 1.1 Create `scripts/check_builder_patch_syntax.py` to compile explicit Python file arguments and return non-zero on failure.
- [x] 1.2 Keep compile guard deterministic and read-only with ASCII pass/fail output per file.
- [x] 1.3 Add header docstring usage examples for explicit-file mode.

## 2. TT `/init` Gate Isolation

- [x] 2.1 Add dedicated helper for TT `/init` initiative gate handling in `core/managers/combat_manager.py` with explicit input/output contract.
- [x] 2.2 Replace inline `/init` gate branch in `run_combat_simulation()` with thin helper invocation and structured result handling.
- [x] 2.3 Ensure helper path preserves existing writes for initiative fields and mirror payload, including `openingEnemyBatchPending` handling via `apply_opening_batch_marker(...)`.
- [x] 2.4 Keep single-player flow unchanged and guard TT path behind existing multi-PC activation checks.

## 3. TT State Ownership and Marker Lifecycle Hardening

- [x] 3.1 Preserve ownership boundary: keep `normalize_phase1_initiative(...)` in `core/managers/combat_manager.py` for this change; do not relocate it to `combat_state_sync.py`.
- [x] 3.2 Preserve current startup/resume sync behavior for phase1 normalization + mirror updates + fast-lane initiative gate assumptions.
- [x] 3.3 Preserve opening marker lifecycle across all current paths: `/init` winner resolution, round-start reapplication, and post-opening-batch clear.
- [x] 3.4 Add/retain `# TABLETOP MODE:` markers at host integration points for merge clarity.

## 4. Compile Guard Convenience Mode

- [x] 4.1 Add optional convenience mode to compile changed Python files from git diff when no file args are supplied.

## 5. Verification

- [x] 5.1 Run `python3 -m py_compile core/managers/combat_manager.py core/managers/combat_state_sync.py core/generators/combat_builder.py scripts/check_builder_patch_syntax.py`.
- [x] 5.2 Run `python3 scripts/check_builder_patch_syntax.py core/managers/combat_manager.py core/managers/combat_state_sync.py core/generators/combat_builder.py`.
- [x] 5.3 Run `python3 scripts/test_multi_pc_combat.py` and confirm pass.
- [x] 5.4 Run `python3 scripts/c5_regression_combat.py` and confirm pass.
- [x] 5.5 Smoke-check one `dmGroup` opener and one `pcGroup` opener to confirm no phase desync regression.
- [x] 5.6 Validate change artifacts with `openspec validate tt-combat-manager-hardening-only`.
