## 1. Coverage Audit and Safety Gate

- [x] 1.1 Audit all shipped modules for live mutable file families (`areas/*.json`, `module_plot.json`, `player_quests_<module>.json`) and record which canonical `_BU` sources already exist.
- [x] 1.2 Confirm which root/runtime bootstrap files are intentionally gitignored and document any startup/preflight paths that still assume those files already exist.
- [x] 1.3 Add or extend focused regression coverage for fresh-clone bootstrap assumptions and runtime-state hydration entry points before changing Git tracking.

## 2. Canonical Backup Completion

- [x] 2.1 Add missing tracked `_BU` coverage for every shipped module that still lacks canonical backups for live mutable area or plot files.
- [x] 2.2 Verify the known `Night_of_the_Restless_Dead` gaps are closed for `NIG001` and `module_plot` canonical backup coverage.
- [x] 2.3 Run module validation or equivalent file-presence verification to confirm backup completion before untracking any live files.

## 3. Runtime Hydration Hardening

- [x] 3.1 Harden startup hydration so missing live `areas/*.json` files are recreated from tracked `*_BU.json` sources.
- [x] 3.2 Harden startup/reset hydration so missing live `module_plot.json` files are recreated from tracked `module_plot_BU.json` sources.
- [x] 3.3 Ensure missing `player_quests_<module>.json` files regenerate cleanly as derived runtime outputs rather than blocking gameplay.
- [x] 3.4 Verify fresh install and reset flows still reach a playable state without tracked live module JSON files.

## 4. Git Tracking Cleanup

- [x] 4.1 Update `.gitignore` and tracked-file boundaries so live runtime module files are not versioned as canonical shipped content.
- [x] 4.2 Remove the targeted live runtime JSON families from Git tracking while preserving tracked `_BU` backups and other canonical authored assets.
- [x] 4.3 Remove obvious tracked runtime cruft in the repo root that is not legitimate canonical content.

## 5. Update-Safe Verification

- [x] 5.1 Run compile and targeted regression checks for any touched Python startup/reset/runtime-state files.
- [x] 5.2 Run a fresh-clone gameplay smoke pass that includes startup, plot advancement, area reconciliation, and quest projection regeneration, then confirm gameplay does not dirty tracked repo content.
- [x] 5.3 Verify Git-based update workflows remain available after ordinary gameplay when no code edits exist.
- [x] 5.4 Run `openspec validate module-data-git-fix` and capture the verification summary.

SHOULD: Keep `openspec/changes/module-data-git-fix/executor_prompts.md` aligned with task ordering and verification gates so builder execution can proceed in small bounded steps.
