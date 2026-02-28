## 1. TT `/init` Gate Isolation

- [ ] 1.1 Add dedicated helper for TT `/init` initiative gate handling in `core/managers/combat_manager.py` with explicit input/output contract.
- [ ] 1.2 Replace inline `/init` gate branch in `run_combat_simulation()` with thin helper invocation and structured result handling.
- [ ] 1.3 Ensure helper path preserves existing writes for initiative fields and mirror payload, including `openingEnemyBatchPending` handling via `apply_opening_batch_marker(...)`.
- [ ] 1.4 Keep single-player flow unchanged and guard TT path behind existing multi-PC activation checks.

## 2. TT State Ownership and Marker Lifecycle Hardening

- [ ] 2.1 Preserve ownership boundary: keep `normalize_phase1_initiative(...)` in `core/managers/combat_manager.py` for this change; do not relocate it to `combat_state_sync.py`.
- [ ] 2.2 Preserve current startup/resume sync behavior for phase1 normalization + mirror updates + fast-lane initiative gate assumptions.
- [ ] 2.3 Preserve opening marker lifecycle across all current paths: `/init` winner resolution, round-start reapplication, and post-opening-batch clear.
- [ ] 2.4 Add/retain `# TABLETOP MODE:` markers at host integration points for merge clarity.

## 3. Builder Compile Guard Script

- [ ] 3.1 Create `scripts/check_builder_patch_syntax.py` to compile explicit Python file arguments and return non-zero on failure.
- [ ] 3.2 Add optional convenience mode to compile changed Python files from git diff when no file args are supplied.
- [ ] 3.3 Provide script usage examples in header docstring.

## 4. Verification

- [ ] 4.1 Run `python3 -m py_compile core/managers/combat_manager.py core/managers/combat_state_sync.py core/generators/combat_builder.py scripts/check_builder_patch_syntax.py`.
- [ ] 4.2 Run `python3 scripts/test_multi_pc_combat.py` and confirm pass.
- [ ] 4.3 Run `python3 scripts/c5_regression_combat.py` and confirm pass.
- [ ] 4.4 Smoke-check one `dmGroup` opener and one `pcGroup` opener to confirm no phase desync regression.
- [ ] 4.5 Validate change artifacts with `openspec validate tt-combat-manager-hardening-only`.
