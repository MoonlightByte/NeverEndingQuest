## Why

Packet-built Homebrew modules can currently fail structural readiness on authored monster references even when the builder otherwise succeeds, because the upload pipeline does not share one authoritative monster-hydration path across packet build, readiness repair, finisher, and runtime encounter startup. `The_Ancients_Lab` exposed the gap clearly: the module referenced an authored monster, the readiness gate retried an opaque builder-only closure path, the deterministic materializer could not help packet-built modules without seed parity, and the job stopped at `repair_budget_exhausted` instead of converging on a playable module.

This change is needed now because module builder must be trusted to build modules end-to-end. Author-authored monsters that are not already in the shipped bestiary MUST still become valid module-local monster files, using deterministic reuse and bestiary lookup first, and controlled AI generation only when the monster is explicitly authorized by authored module content and no deterministic source exists.

## What Changes

- Add one shared post-build monster hydration contract for packet-built modules, readiness repair, finisher flows, and runtime-authorized hydration.
- Make packet-built modules expose authoritative monster hydration inputs even when `monsters_seed.json` is absent, using authored area/module references as a canonical fallback source.
- Replace readiness-gate use of the legacy module-builder closure path with the shared monster hydration path used by finishing and runtime hydration.
- Add explicit support for authored non-bestiary monsters so the system MAY generate 5e SRD-compatible local monster JSON when the monster is authorized by module content and deterministic reuse/bestiary lookup cannot satisfy it.
- Require structured hydration outcomes that distinguish:
  - deterministic reuse success,
  - bestiary materialization success,
  - controlled AI generation success,
  - unresolved authorized hydration failure,
  - unauthorized monster reference rejection.
- Preserve fail-closed validation semantics: unresolved monster references MUST still block readiness and finishing until hydration succeeds.
- Improve toolkit reporting so operators can see whether failure came from missing hydration inputs, unauthorized references, provider/builder failure, or an unchanged validation signature.
- **MUST NOT** silently widen authorization from freeform narration or ad hoc repair prompts.
- **MUST NOT** replace validator/reference-integrity rules with a warn-only model.
- **SHOULD** keep all host-file changes additive and route new behavior through shared helpers instead of duplicating monster resolution logic in each workflow.

## Capabilities

### New Capabilities
- `toolkit-homebrew-monster-hydration-convergence`: packet-built toolkit modules use a single authoritative monster hydration pipeline that can converge authored bestiary and non-bestiary monster references into valid module-local monster files before finishing.

### Modified Capabilities
- `homebrew-ingest-monster-materialization`: monster materialization requirements expand from seed-only bestiary mapping to authored-reference fallback discovery plus controlled AI generation for authorized non-bestiary monsters.
- `tt-module-authorized-monster-hydration`: runtime-authorized hydration requirements expand into a shared convergence contract so builder, readiness, finisher, and runtime all resolve authorized monsters through the same precedence order and failure semantics.
- `toolkit-module-postbuild-finishing`: post-build finishing requirements change so toolkit finishing reuses the shared monster hydration contract rather than a parallel packet-builder-only or finisher-only materialization path.
- `toolkit-homebrew-ingest-job-reporting`: toolkit job reporting requirements change to surface hydration-mode outcomes and convergence blockers distinctly.

## Impact

- Affected upload readiness surface: `web/extensions/toolkit_homebrew_readiness_gate.py`
- Affected finisher surface: `web/extensions/toolkit_module_finisher.py`
- Affected packet-builder/build artifact surface: `web/extensions/toolkit_homebrew_packet_builder.py`
- Affected deterministic materialization surface: `scripts/homebrew_materialize_monsters.py`
- Affected shared authority surface: `utils/module_monster_authority.py`
- Likely affected builder fallback surface: `core/generators/monster_builder.py` and/or a new shared helper under `utils/` or `scripts/`
- Affected validation/reporting surfaces: `core/validation/validate_module_files.py`, toolkit workspace artifacts, and `web/templates/module_toolkit.html`
- Dependency impact: provider-aware AI generation paths MUST define outage/quota behavior explicitly; deterministic reuse and bestiary-backed hydration remain preferred and MUST run before AI generation.
- Merge safety impact: SHOULD remain additive by centralizing shared hydration helpers instead of rewriting builder or validator contracts in place.
- SP/MP compatibility impact: gameplay rules do not change; this change is scoped to module asset generation/hydration and runtime monster file availability.
- Rollout risk: broader hydration support could mask authorization drift if scoped poorly, so authorization MUST remain authored-content-only and unresolved results MUST stay visible and blocking.
- Fallback strategy: if AI hydration is unavailable due to provider outage, quota exhaustion, or builder failure, the pipeline MUST preserve a structured blocking result and actionable diagnostics rather than looping blindly or degrading into a false success.
