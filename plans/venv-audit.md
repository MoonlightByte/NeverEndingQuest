# Venv Audit Plan

Status: Proposed
Owner: OpenCode
Purpose: Audit interpreter usage and silent dependency-fallback behavior so repository maintenance commands reliably use the same runtime environment as the application.

---

## 1. Problem Statement

Recent Diary rebuild work exposed an operational failure mode:

- `ENABLE_SESSION_DIARY_LLM` was enabled
- the rebuild was run with system `python3`
- that interpreter did not have `openai` installed
- the Diary pipeline silently degraded to deterministic fallback output

This indicates a repo-wide risk:

1. documentation and task notes may still suggest `python` / `python3` for dependency-sensitive commands
2. some maintenance/runtime paths may fail open too quietly when third-party dependencies are missing
3. command examples may not reliably reflect the real application runtime

---

## 2. Audit Goal

Produce a concrete map of where NeverEndingQuest must use `.venv/bin/python`, where existing docs still encourage the wrong interpreter, and where code silently hides interpreter mismatch.

The goal is not a broad architecture rewrite.

The goal is to make runtime, rebuild, migration, validation, and diary/story workflows consistently use the correct interpreter and surface mistakes clearly.

---

## 3. Audit Questions

### 3.1 Command Guidance

1. Where do repo docs, plans, and OpenSpec tasks still tell users or builders to run `python` or `python3` for dependency-sensitive commands?
2. Which of those commands should explicitly become `.venv/bin/python`?

### 3.2 Runtime/Script Risk

1. Which scripts or maintenance entrypoints import third-party runtime dependencies?
2. Which of those are likely to degrade silently or behave differently under the wrong interpreter?

### 3.3 Silent Fallback Risk

1. Where do `ImportError` or missing-dependency handlers silently disable important behavior?
2. Which of those should warn loudly?
3. Which of those should fail closed for maintenance/rebuild commands?

### 3.4 Operational Priority

1. Which workflows are highest risk if run under the wrong interpreter?
2. Which should be corrected first in docs and code?

---

## 4. Scope

### In Scope

1. `AGENTS.md`
2. `README.md`
3. active plans under `plans/`
4. active OpenSpec changes under `openspec/changes/`
5. scripts under `scripts/`
6. runtime/service modules that are invoked by maintenance workflows
7. dependency-sensitive diary/story/rebuild/remediation/validation commands

### Out of Scope

1. unrelated game-mechanics refactors
2. large-scale packaging changes
3. replacing the venv workflow with another environment manager
4. changing every historical archived note unless it is still likely to be copied into active work

---

## 5. Audit Categories

### Category A: Documentation Command Audit

Review command examples in:

1. `AGENTS.md`
2. `README.md`
3. `plans/**/*.md`
4. `openspec/changes/**/tasks.md`
5. `openspec/changes/**/design.md` where runtime verification commands are mentioned

Classify each Python command as:

1. `venv-required`
2. `venv-preferred`
3. `interpreter-agnostic`

Priority examples to inspect first:

1. Diary rebuild/remediation
2. Story So Far generation/PDF
3. schema validation
4. startup/runtime verification
5. web route or Flask-adjacent scripts
6. any command importing `openai`

### Category B: Script Dependency Audit

Inspect scripts and helpers for imports of:

1. `openai`
2. Flask/web dependencies
3. schema/validation tooling
4. provider clients
5. other third-party packages only present in the project venv

For each script, record:

1. path
2. dependency-sensitive imports
3. current documented command style
4. required interpreter classification

### Category C: Silent Fallback Audit

Search for patterns like:

1. `except ImportError:`
2. `ModuleNotFoundError`
3. dependency booleans such as `*_AVAILABLE = False`
4. feature-disable fallbacks caused by missing imports

For each case, classify whether current behavior should be:

1. keep as-is
2. warn loudly
3. fail closed in maintenance commands

Priority targets:

1. Diary rebuild/generation
2. Story So Far generation
3. any migration or rebuild paths that mutate runtime data

### Category D: Operational Risk Audit

Rank workflows by user impact if run under the wrong interpreter.

Expected top tier:

1. Diary rebuild/remediation
2. Story So Far generation/PDF
3. schema validation before release
4. startup verification or campaign-state repair scripts

---

## 6. Deliverables

The audit should produce:

### Deliverable 1: Command Matrix

A table or structured list containing:

1. command or script path
2. current documented interpreter
3. required interpreter classification
4. recommended replacement command

### Deliverable 2: Silent Fallback Register

A list of code locations where dependency loss currently hides interpreter mismatch, with:

1. file path
2. fallback behavior
3. operational risk
4. recommended fix type

### Deliverable 3: Priority Remediation List

A short implementation queue ordered by risk:

1. docs fixes
2. warning/fail-closed behavior additions
3. targeted script command updates

---

## 7. Success Criteria

This audit is successful when:

1. all dependency-sensitive Diary/Story/runtime commands are clearly identified as `.venv/bin/python`
2. the repo no longer relies on implied interpreter knowledge for important maintenance workflows
3. silent dependency fallback sites are cataloged and triaged
4. a reviewer can see exactly where command guidance and code behavior still need correction

---

## 8. Recommended Follow-up After Audit

After review, implementation should proceed in this order:

1. update active docs/plans/OpenSpec task commands to `.venv/bin/python`
2. add loud warnings or fail-closed behavior for critical maintenance paths
3. keep historical/archive cleanup selective, not exhaustive
4. re-run the highest-risk workflows using `.venv/bin/python` to confirm parity with real runtime

---

## 9. Notes

This audit is intentionally operational, not theoretical.

The main question is not whether the app can run in a venv.

The main question is whether the repo consistently makes the correct interpreter obvious for all workflows that can silently degrade if run under the wrong Python.
