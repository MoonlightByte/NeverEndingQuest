## Context

`plans/module-data-git-fix.md` identified three module-local JSON families that are mutated during play and therefore poison Git-based installs when they remain tracked:

- `modules/<module>/areas/*.json`
- `modules/<module>/module_plot.json`
- `modules/<module>/player_quests_<module>.json`

A related fresh-install bug showed the same architectural truth at the repo root: `party_tracker.json` is intentionally local runtime state, but a newer startup preflight gate briefly treated its absence as a fatal install error. That bug is now patched, and this design treats the fix as a prerequisite signal: Git installs must assume runtime state may be absent on fresh clone, and startup/reset code must create or hydrate it.

This change is cross-cutting because it touches shipped module content, runtime hydration, gameplay write paths, startup/reset ordering, and Git cleanliness verification.

## Goals / Non-Goals

**Goals:**
- MUST define a durable boundary between canonical shipped content and mutable runtime state.
- MUST guarantee that every untracked live module file has a canonical hydration source before tracking is cleaned up.
- MUST preserve current runtime filenames where feasible so existing call sites continue to work.
- MUST keep fresh clone, reset, and normal gameplay playable in both single-player and TABLETOP MODE.
- MUST make Git-based installs update-safe after ordinary gameplay when no code files were edited.
- SHOULD reuse existing `_BU` conventions and existing startup/reset flows.
- SHOULD keep rollout incremental so each phase can be validated before untracking more files.

**Non-Goals:**
- This design does NOT move the project to a database-backed module state system.
- This design does NOT require wholesale relocation of runtime files into a new directory tree if existing paths can be hydrated safely.
- This design does NOT change gameplay semantics, prompt rules, or combat/narration logic outside startup/runtime-state handling.

## Decisions

### Decision 1: Preserve live runtime filenames; change canonical source ownership instead

MUST: Existing readers and writers may keep using live runtime filenames such as `areas/*.json` and `module_plot.json`.

Rationale:
- This minimizes call-site churn across gameplay systems.
- The real problem is not the runtime filename; it is that the live file is still treated as shipped canonical content.

Chosen approach:
- Canonical shipped content for mutable module files SHALL live in tracked `_BU` backups.
- Live mutable files SHALL be hydrated from those backups during startup/reset/bootstrap.
- Derived quest projections SHALL be regenerated rather than tracked.

Alternative considered:
- Move all runtime files into a new `runtime/` subtree immediately.
- Rejected for this phase because it would require broad path rewrites across gameplay code and increase merge risk.

### Decision 2: Treat root bootstrap state and module live state as the same architectural class

MUST: Root files like `party_tracker.json` and module-local live files like `areas/*.json` SHALL both be treated as mutable runtime state, not canonical shipped content.

Rationale:
- The Windows fresh-install failure proved that bootstrap code must not assume gitignored runtime state exists.
- Using one architectural rule avoids repeating the same mistake at different path levels.

Chosen approach:
- Startup/preflight SHALL tolerate missing runtime state when bootstrap/setup is expected.
- Strict validation SHALL apply after campaign state and canonical hydration sources are present.

Alternative considered:
- Handle `party_tracker.json` as a special one-off exception.
- Rejected because it hides the broader canonical-vs-runtime boundary and invites future regressions.

### Decision 3: Complete canonical backup coverage before untracking live files

MUST: No live gameplay-mutated file family may be untracked until every shipped module has a canonical source for hydration.

Rationale:
- Untracking before coverage completion can leave fresh installs without a recoverable live state source.
- `Night_of_the_Restless_Dead` currently needs backup completion for at least one area file and `module_plot.json`.

Chosen approach:
- Audit all shipped modules for `_BU` coverage.
- Add missing canonical backups first.
- Only then remove live file families from tracking.

Alternative considered:
- Untrack first and rely on manual reconstruction later.
- Rejected because it is brittle, operator-hostile, and unsafe for tester installs.

### Decision 4: Roll out in four ordered phases with explicit stop points

MUST: Migration sequencing SHALL be:
1. canonical coverage audit/completion
2. hydration hardening
3. Git tracking cleanup
4. gameplay/update-path verification

Rationale:
- Each phase reduces a distinct failure mode.
- Verification after each phase allows rollback before more destructive repo hygiene changes land.

SHOULD:
- Keep phase boundaries mirrored in `tasks.md` and `executor_prompts.md` so builder execution remains deterministic.

### Decision 5: Verification must measure repo cleanliness, not just unit logic

MUST: This change SHALL include verification that tracked-tree cleanliness is preserved after representative gameplay mutations.

Rationale:
- The bug is operational, not purely functional.
- Compile-only or schema-only checks cannot prove update-safe gameplay for Git installs.

Chosen approach:
- Add targeted verification for fresh clone bootstrap, plot advancement, area mutation/reconciliation, and update readiness.
- Treat tracked-file dirtiness from gameplay as a release blocker for this change.

## Risks / Trade-offs

- [Missing `_BU` coverage] -> Mitigation: perform a per-module coverage audit first and block untracking until every required canonical backup exists.
- [Hidden runtime write path still targets tracked files] -> Mitigation: verify representative gameplay flows and inspect all known write paths named in the source plan.
- [Hydration order races startup validation] -> Mitigation: keep bootstrap/hydration checks before strict gameplay validation paths and preserve fail-open bootstrap detection.
- [Developer confusion over canonical vs runtime files] -> Mitigation: document file-family ownership clearly in specs and keep path names stable while ownership changes.
- [Rollback complexity after untracking] -> Mitigation: stage rollout so Git tracking cleanup happens only after hydration hardening and verification are green.

## Migration Plan

1. Audit shipped modules for canonical backup coverage of live area and plot files.
2. Add missing `_BU` files for any uncovered shipped modules.
3. Harden startup/reset/runtime regeneration so fresh clones and resets can recreate live state deterministically.
4. Update Git tracking boundaries for live module files and remove stray tracked runtime cruft.
5. Run clean-install and gameplay dirtiness verification before considering the change implementation-ready.

Rollback strategy:
- If hydration gaps or update-path regressions appear, stop before or revert the tracking cleanup phase.
- Canonical `_BU` additions are safe to keep even if later phases pause.
- The fallback state is the current tracked-live-file model, but only if necessary to restore install reliability while remaining gaps are fixed.

## Open Questions

- Should the repo eventually ship a tracked template for `party_tracker.json`, or is the current fully runtime-created approach preferred long term?
- Do any toolkit or validation flows still rely on tracked live module files instead of canonical `_BU` inputs?
- Should `player_quests_<module>.json` remain module-local derived state, or eventually move to a separate runtime-only location once the boundary cleanup is complete?
