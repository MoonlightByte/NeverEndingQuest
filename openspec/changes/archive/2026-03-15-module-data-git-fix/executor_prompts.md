# Builder Prompts - module-data-git-fix

## Execution Contract
- MUST preserve current gameplay behavior while separating canonical shipped content from runtime-local state.
- MUST stop before Git untracking if any shipped module still lacks required `_BU` backup coverage.
- MUST keep runtime filenames stable unless a task explicitly requires otherwise.
- MUST treat missing gitignored runtime files as bootstrap-required local state, not as proof of a broken install.
- MUST prefer additive hooks and minimal host-file edits with `# TABLETOP MODE:` markers where host changes are required.
- MUST run `python3 -m py_compile <file>` immediately after each touched Python file.
- SHOULD apply one anchored patch at a time, then re-run `py_compile` before the next patch.
- SHOULD keep Git-boundary changes late in the sequence, after hydration and verification work is green.

## Prompt 1 - Coverage Audit and Guardrails
**Step ID:** 1
**Tier:** MUST

Implement OpenSpec `module-data-git-fix` Section 1 only.

### Required scope
- Audit shipped modules for live mutable file families and canonical `_BU` coverage.
- Confirm which runtime bootstrap files are intentionally gitignored.
- Identify any remaining startup/preflight assumptions that still expect missing runtime files to exist on fresh clone.
- Add or outline focused regression coverage needed before Git tracking cleanup begins.

### Allowed files
- `plans/module-data-git-fix.md`
- `scripts/test_*`
- lightweight audit/report files if needed

### Forbidden
- No Git tracking cleanup yet.
- No destructive repo changes.

### Verification gate
- Any new Python files: `python3 -m py_compile <file>`
- Report the module coverage matrix and unresolved blockers.

### Next step
Proceed to Prompt 2 only after backup-coverage blockers are explicitly listed.

---

## Prompt 2 - Canonical Backup Completion
**Step ID:** 2
**Tier:** MUST

Implement OpenSpec `module-data-git-fix` Section 2 only.

### Required scope
- Add missing tracked `_BU` backups for shipped modules that still lack canonical coverage.
- Explicitly close the known `Night_of_the_Restless_Dead` gaps for live area and plot backups.
- Keep canonical backup files content-equivalent to the live source being canonicalized.

### Allowed files
- `modules/*/areas/*_BU.json`
- `modules/*/module_plot_BU.json`
- focused verification scripts if needed

### Forbidden
- Do not untrack live files yet.
- Do not rewrite runtime path conventions.

### Verification gate
- Run targeted validation or presence checks for every newly added `_BU` file.
- If helper scripts are added, run `python3 -m py_compile <file>`.

### Next step
Proceed to Prompt 3 only after every shipped module has canonical backup coverage for targeted live file families.

---

## Prompt 3 - Runtime Hydration Hardening
**Step ID:** 3
**Tier:** MUST

Implement OpenSpec `module-data-git-fix` Section 3 only.

### Required scope
- Harden startup hydration for missing live `areas/*.json` and `module_plot.json` files using tracked `_BU` sources.
- Ensure missing `player_quests_<module>.json` regenerates as a derived runtime output.
- Preserve fresh-install bootstrap behavior when gitignored root/runtime files are absent.

### Allowed files
- `utils/startup_wizard.py`
- `utils/reset_campaign.py`
- `utils/quest_player_formatter.py`
- other narrow hydration helpers required by existing architecture
- focused regression tests

### Forbidden
- No Git tracking cleanup yet.
- No broad runtime path rewrites.

### Verification gate
- `python3 -m py_compile` for every touched Python file
- Run focused startup/reset/runtime regeneration tests added or updated in this step
- Report positive and negative hydration behavior

### Next step
Proceed to Prompt 4 only after fresh-install and reset flows can recreate live runtime state without tracked live module JSON files.

---

## Prompt 4 - Git Tracking Cleanup
**Step ID:** 4
**Tier:** MUST

Implement OpenSpec `module-data-git-fix` Section 4 only.

### Required scope
- Update `.gitignore` and tracked-file boundaries so targeted live module files are runtime-local rather than canonical tracked content.
- Remove targeted live runtime JSON families from Git tracking while preserving `_BU` backups and other canonical assets.
- Remove obvious tracked runtime cruft from the repo root.

### Allowed files
- `.gitignore`
- targeted module file tracking state
- documentation notes tied directly to the cleanup

### Forbidden
- Do not remove canonical authored assets.
- Do not proceed if backup coverage or hydration verification is incomplete.

### Verification gate
- `git status --short`
- targeted file-tracking checks for removed live files vs preserved `_BU` backups
- report exact tracked/untracked state after cleanup

### Next step
Proceed to Prompt 5 only after tracked gameplay-mutated file families are cleanly separated from canonical content.

---

## Prompt 5 - Update-Safe Verification Bundle
**Step ID:** 5
**Tier:** MUST

Implement OpenSpec `module-data-git-fix` Section 5 only.

### Required scope
- Run compile checks for touched Python files.
- Run targeted regressions for startup bootstrap, hydration, and derived output regeneration.
- Perform a gameplay smoke pass covering startup, plot advancement, area reconciliation, and quest regeneration.
- Confirm tracked repo content remains clean after ordinary play and that update workflows remain available.
- Run OpenSpec validation for this change.

### Verification gate
- `python3 -m py_compile <touched-python-files>`
- targeted test commands added during implementation
- `git status --short`
- `openspec validate module-data-git-fix`

### Completion criteria
- Fresh clone remains bootstrappable.
- Live gameplay no longer dirties tracked canonical module content.
- Update path remains available when no code edits exist.
- OpenSpec validation returns valid.
