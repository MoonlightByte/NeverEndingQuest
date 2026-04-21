## Context

`modules/<module>/media/{npcs,monsters}` is the self-contained media source a module should ship with, but `web/static/media/{npcs,monsters}` has accumulated older activated-pack assets, generated fallback files, and prior test outputs. The current runtime fallback behavior is convenient, but because the shared static folders are long-lived and additive, stale portraits can leak across module boundaries and the fallback surface keeps growing without a clear maintenance contract.

This change does not redesign media lookup. It defines how the shared static layer should be maintained so the fallback pool is bounded, intentional, and auditable.

## Goals / Non-Goals

**Goals:**
- MUST define `web/static/media/npcs` and `web/static/media/monsters` as rebuildable runtime cache only.
- MUST keep `modules/<module>/media/*` as the authoritative, publishable media location.
- MUST provide a dry-run audit/report before cleanup so operators can see active-pack inputs, orphaned files, and collisions.
- MUST provide a backup/rollback path before destructive rebuild.
- MUST rebuild live static NPC/monster fallback from active packs only instead of preserving long-lived additive drift.
- MUST preserve current runtime lookup order in this slice.
- MUST preserve module publication rules that require module-local media regardless of shared fallback contents.
- SHOULD leave unrelated static sibling folders such as `videos`, `environment`, and `class_portraits` out of scope unless explicitly added later.

**Non-Goals:**
- NOT changing module-first runtime media lookup semantics.
- NOT making shared static fallback authoritative for publication or readiness.
- NOT cleaning every `web/static/media/*` subtree in this slice.
- NOT solving every possible cross-pack naming collision automatically.
- NOT changing graphic pack authoring/export format beyond what is required for deterministic rebuild.

## Decisions

### Decision: Module-local media remains authoritative; shared static media is disposable fallback
- Rationale: the repository already treats module-local media as the self-contained shipped form, while shared static media is a convenience layer fed by pack activation and generation flows.
- MUST treat `modules/<module>/media/{npcs,monsters}` as authoritative.
- MUST treat `web/static/media/{npcs,monsters}` as runtime cache/fallback only.
- MUST keep publishability and readiness grounded in module-local media.
- Alternative considered: keep today’s additive shared folders and rely on occasional manual cleanup.
- Rejected because it preserves stale fallback leakage and unbounded growth.

### Decision: Strict-cache rebuild scope is limited to static NPC and monster folders
- Rationale: those two folders are the current growth/collision risk, while sibling folders have different usage patterns and can be addressed separately.
- MUST scope destructive rebuild behavior to:
  1. `web/static/media/npcs`
  2. `web/static/media/monsters`
- SHOULD leave `videos`, `environment`, `class_portraits`, and other sibling folders unchanged in this slice.

### Decision: Rebuild must be deliberate, auditable, and reversible
- Rationale: static fallback may currently be masking missing module-local assets or stale assumptions, so operators need visibility before cleanup.
- MUST provide a dry-run mode that reports:
  1. files currently present in live static fallback,
  2. files sourced from active packs,
  3. files that would be removed as orphans,
  4. filename collisions or overwrite candidates between active packs.
- MUST provide a backup/snapshot path before any destructive clear-and-rebuild operation.
- SHOULD make the rebuild workflow easy to repeat after pack activation changes.

### Decision: Live static rebuild is clear-then-populate, not additive copy
- Rationale: additive copy is the direct cause of fallback drift.
- MUST clear `web/static/media/npcs` and `web/static/media/monsters` before repopulating them from the currently active packs.
- MUST repopulate only from active-pack assets in this slice.
- SHOULD keep any direct-generation flows aligned with the same strict-cache contract so those folders do not silently revert to archive behavior.
- Alternative considered: only delete obvious stale files during rebuild.
- Rejected because it requires provenance certainty the current tree does not have and would preserve drift.

### Decision: Publishability remains independent of shared static fallback
- Rationale: gameplay may still resolve via fallback, but publication must reflect whether the module is self-contained.
- MUST preserve the rule that module-local media debt remains real even if shared static fallback happens to contain a matching asset.
- SHOULD expose this contract clearly in audit/reporting and operator workflow text so fallback convenience is not confused with publication readiness.

### Decision: Lookup order remains unchanged in this slice
- Rationale: the current problem is stale shared fallback accumulation, not the entire runtime media routing design.
- MUST keep current runtime lookup behavior unchanged for now.
- SHOULD treat deeper routing questions such as cross-module fallback search order as a separate slice if they remain problematic after strict-cache cleanup.

## Architecture

### Before

1. packs are activated and copied into shared static media,
2. generation flows may also write additional files into shared static media,
3. shared fallback folders continue growing,
4. runtime falls through to those folders when module-local resolution misses.

### After

1. operator runs audit/dry-run for static NPC/monster cache,
2. workflow reports active-pack inputs, orphaned files, and collisions,
3. operator creates backup snapshot,
4. workflow clears live static NPC/monster folders,
5. workflow repopulates them from active packs only,
6. runtime continues using the same lookup order, but fallback surface is reduced to intentional pack-backed assets.

## Risks / Trade-offs

- [Fallback cleanup exposes hidden module-local media debt] -> Mitigation: dry-run report and backup path before rebuild.
- [Active packs still contain stale or colliding assets] -> Mitigation: collision/orphan reporting MUST surface this explicitly even if automatic deconfliction is deferred.
- [Operators mistake runtime fallback success for publishability] -> Mitigation: keep module-publishable contract explicit and unchanged.
- [Generation flows re-pollute static cache after rebuild] -> Mitigation: align post-rebuild writes with the strict-cache contract or make those writes explicit and auditable.

## Migration Plan

1. Define strict-cache contract in OpenSpec artifacts.
2. Add static media audit/dry-run reporting for NPC and monster fallback folders.
3. Add backup/snapshot and rebuild workflow.
4. Update active-pack population path to clear-and-rebuild rather than preserve additive drift.
5. Lock publishability expectations to module-local media in spec/tests.
6. Smoke-test with representative active modules after rebuild.

Rollback strategy:

1. Restore pre-rebuild backup snapshot.
2. Disable or bypass strict-cache rebuild path temporarily if rebuild logic is unsafe.
3. Keep audit/reporting artifacts even if destructive rebuild is rolled back.

## Verification Plan

Minimum verification for this change should include:

1. dry-run report for current static NPC/monster fallback contents,
2. successful backup creation before destructive rebuild,
3. rebuild that leaves only active-pack NPC/monster assets in `web/static/media/{npcs,monsters}`,
4. regression proving runtime lookup order is unchanged,
5. regression proving publishability still treats missing module-local media as real debt,
6. smoke test on one or two representative modules after rebuild.

## Open Questions

- Should direct portrait-generation flows stop writing into shared static media entirely, or should they continue writing there but be followed by strict-cache rebuild maintenance?
- Should collision reporting be warning-only in this slice, or should active-pack filename collisions hard-fail rebuild?
- Which modules should be mandatory smoke-test canaries after the first strict-cache rebuild?
