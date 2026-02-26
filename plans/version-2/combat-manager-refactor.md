# Combat Manager Refactor Plan (Builder Reliability + Merge Safety)

Status: V2 backlog (deferred from current test build)
Priority: High
Date: 2026-02-26
Owner: Combat systems + tabletop mode
Target: `plans/version-2/combat-manager-refactor.md`

---

## 1) Objective

Execute a broad structural refactor of `core/managers/combat_manager.py` in v2 after current test-build stabilization, so long-term upstream-facing maintainability improves without rushing risky monolith surgery into the live test cycle.

Primary goals:
1. Reduce editing fragility in `run_combat_simulation()` by splitting deep nested blocks into focused helper functions.
2. Isolate initiative gate logic (`/init` two-group phase handling) into a dedicated handler.
3. Add a small builder regression utility that enforces per-file `py_compile` checks after each patch step.
4. Preserve merge-safe TABLETOP MODE hooks and avoid upstream behavior regressions.

## 1.1 Version Split (MUST)

- **Current test build (NOW):** TT-only hardening is executed under OpenSpec change `tt-combat-manager-hardening-only`.
- **Version 2 (THIS PLAN):** Upstream-wide structural decomposition of `combat_manager.py`, including non-TT sections, proceeds only after test-build validation gates pass.
- **Conflict rule:** If a change can be scoped to TT-only safely, it SHOULD stay in the TT-only change and MUST NOT expand this v2 scope early.

---

## 2) Problem Statement

`combat_manager.py` is large and indentation-sensitive, with deeply nested control flow around encounter load, phase sync, `/init` gate routing, and turn progression. This causes:
- frequent patch failures from tiny indentation drift,
- harder verification of behavior equivalence,
- slow builder iteration due to broad edit scope.

Recent fixes for phase marker and roster coherence are correct, but they increased pressure on an already monolithic function surface.

---

## 3) Scope and Non-Goals

### 3.1 In scope (MUST)
- Refactor `run_combat_simulation()` into helper functions with clear contracts across TT and non-TT regions.
- Extract `/init` gate logic into one function and align with broader phase-routing structure.
- Add or extend compile-check automation for touched Python files.
- Keep behavior equivalent for existing single-player and multi-player combat flows.

### 3.2 Out of scope (MUST NOT)
- No combat rules redesign.
- No schema migrations.
- No prompt grammar redesign.
- No frontend/UI redesign.
- No OpenRouter/router architecture changes.
- No TT-only emergency fixes that belong to `tt-combat-manager-hardening-only`.

### 3.3 Prerequisite (MUST)
- TT-only hardening change `tt-combat-manager-hardening-only` MUST be merged and validated before this v2 refactor begins.

---

## 4) Design Direction

### 4.1 Refactor principles
- Keep host file edits minimal and marked with `# TABLETOP MODE:` where relevant.
- Extract logic; do not change business rules unless bug fix is explicitly required.
- New helpers should have narrow input/output contracts and no hidden global side effects.
- Preserve existing fail-open behavior and logging categories.

### 4.2 Proposed helper boundaries

#### A) Encounter and phase preflight
- `_load_encounter_state(encounter_id, path_manager) -> Tuple[encounter_data, json_file_path]`
- `_apply_phase_and_roster_sync(encounter_data, party_tracker, party_tracker_data, json_file_path, path_manager) -> encounter_data`
  - Calls existing `normalize_phase1_initiative(...)`
  - Calls `normalize_multi_pc_roster(...)` from `core/managers/combat_state_sync.py`

#### B) Multi-PC manager setup
- `_init_multi_pc_manager(encounter_data, party_tracker_data) -> Optional[MultiPCCombatManager]`
  - retrieves or creates manager,
  - initializes turn queue,
  - syncs round state.

#### C) `/init` phase gate handler
- `_handle_group_initiative_gate(clean_input, encounter_data, party_tracker_data, multi_pc_manager, json_file_path) -> Dict[str, Any]`
  - Handles parse/validation of `/init <1-20>`
  - Applies `apply_opening_batch_marker(...)`
  - Persists encounter + mirror updates
  - Returns structured result (`handled`, `error_message`, `phase_label`, `winner`).

#### D) History resume decision
- `_resolve_combat_history_resume(encounter_id, conversation_history_file) -> Tuple[is_resuming, conversation_history]`

### 4.3 Builder compile utility
Create `scripts/check_builder_patch_syntax.py`:
- Input: list of Python file paths
- Behavior:
  - compile each with `py_compile`,
  - print pass/fail per file,
  - exit non-zero if any fail.
- Optional convenience mode:
  - read changed Python files from `git diff --name-only` and compile only those.

---

## 5) Implementation Phases

## 5.1 Phase 1 - Safe extraction scaffold (MUST)
- Add helper signatures and move code in small chunks from `run_combat_simulation()`.
- Keep old variable names and logging lines where possible.
- Add no new behavior.

Deliverables:
- helper functions present,
- `run_combat_simulation()` reduced by at least one major nested block.

## 5.2 Phase 2 - `/init` gate isolation (MUST)
- Move `/init` parsing + winner/phase routing into `_handle_group_initiative_gate(...)`.
- Keep exact functional outputs and side effects.
- Preserve marker semantics and mirror updates.

Deliverables:
- `/init` branch in main loop becomes a thin call + response handling.

## 5.3 Phase 3 - Builder syntax checker (MUST)
- Add `scripts/check_builder_patch_syntax.py`.
- Add usage examples in script header.

Deliverables:
- script compiles and returns correct exit codes.

## 5.4 Phase 4 - Regression and smoke validation (MUST)
- Run compile and combat tests.
- Execute one dmGroup-start and one pcGroup-start smoke flow.

Deliverables:
- test report notes and pass/fail evidence.

---

## 6) Verification Commands

Required gates:

```bash
python3 -m py_compile core/managers/combat_manager.py core/managers/combat_state_sync.py core/generators/combat_builder.py
python3 scripts/test_multi_pc_combat.py
```

When script lands:

```bash
python3 scripts/check_builder_patch_syntax.py core/managers/combat_manager.py
```

Optional targeted checks:

```bash
python3 -m py_compile scripts/check_builder_patch_syntax.py
```

---

## 7) Acceptance Criteria

1. `run_combat_simulation()` is structurally simpler, with key preflight and gate logic extracted.
2. `/init` initiative gate behavior is unchanged from current intended behavior.
3. dmGroup marker and roster normalization continue to function.
4. Single-player compatibility remains intact.
5. `scripts/test_multi_pc_combat.py` passes.
6. Builder syntax checker script works and is documented.

---

## 8) Risks and Mitigations

### Risk: behavior drift during extraction
- Mitigation: extraction in tiny slices, compile after each patch, keep logs stable for diff-based comparison.

### Risk: hidden dependencies on local variables
- Mitigation: explicit helper parameters and return structs instead of closure reliance.

### Risk: merge friction with upstream
- Mitigation: additive helper extraction and minimal host-flow edits with `# TABLETOP MODE:` markers.

---

## 9) Rollback Strategy

- Keep refactor commits small and phase-scoped.
- If a phase regresses behavior, revert only that phase commit.
- Maintain known-good baseline in `combat_state_sync.py` and call sites.

---

## 10) OpenSpec Follow-up

If promoted to execution track, create an OpenSpec change such as:
- `combat-manager-structure-hardening-v2`

Current separation:
- NOW track: `tt-combat-manager-hardening-only` (TT scope only)
- V2 track: broader upstream-facing structural decomposition

Suggested task groups:
1. helper extraction,
2. `/init` gate isolation,
3. syntax checker script,
4. regression + smoke verification.

This keeps refactor work explicit and separable from gameplay feature changes.
