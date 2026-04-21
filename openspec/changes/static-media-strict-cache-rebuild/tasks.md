## 1. Contract and Scope

- [x] 1.1 Finalize the strict-cache authority contract for module-local media vs shared static fallback.
- [x] 1.2 Confirm scope boundaries for `web/static/media/npcs` and `web/static/media/monsters`, leaving unrelated sibling folders out of scope.

## 2. Audit and Reporting

- [x] 2.1 Add a dry-run audit/report path that classifies current live static files, active-pack sources, orphaned files, and filename collisions.
- [x] 2.2 Document operator-facing output so rebuild decisions are reviewable before deletion.

## 3. Backup and Rebuild Workflow

- [x] 3.1 Add a backup/snapshot path for live static NPC/monster folders before destructive cleanup.
- [x] 3.2 Implement a clear-and-rebuild workflow that repopulates static NPC/monster fallback from active packs only.
- [x] 3.3 Verify post-rebuild behavior does not repopulate stale additive leftovers during the same workflow.

## 4. Publishability and Runtime Guardrails

- [x] 4.1 Preserve current runtime media lookup order while adopting strict-cache rebuild behavior.
- [x] 4.2 Add or update tests so shared static fallback never counts as satisfying module-local publication debt.

## 5. Verification

- [x] 5.1 Run dry-run audit on the current tree and review orphan/collision output.
- [x] 5.2 Execute backup + rebuild on the strict-cache target folders.
- [x] 5.3 Smoke-test representative modules after rebuild and record any remaining fallback anomalies.
