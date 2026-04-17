## Context

The current Homebrew toolkit path has four different monster-resolution behaviors that do not converge:

1. packet-driven build can emit authored monster references without `monsters_seed.json`,
2. readiness repair uses `ModuleGenerator._ensure_monster_reference_closure()` and retries AI generation opaquely,
3. finisher uses `scripts/homebrew_materialize_monsters.py`, which currently assumes seed artifacts exist and only maps against the shipped compendium,
4. runtime encounter startup uses module-authorized hydration logic with reuse-first behavior.

This split violates the repository's Python-first authority model. The validator correctly treats missing `monsters/<slug>.json` files as blocking, but the workflows that should resolve those files do not share one authoritative source of truth, one precedence order, or one failure model. Packet-built modules are therefore more fragile than ingest-built modules, and authored non-bestiary monsters are not treated as a first-class module-builder use case even though they are central to adventure design.

Stakeholders:
- toolkit users who expect Module Builder to produce playable modules,
- developers maintaining merge-safe uploader/readiness/finisher extensions,
- runtime combat flows that depend on schema-valid local monster files,
- future publication workflows that assume readiness convergence is trustworthy.

## Goals / Non-Goals

**Goals:**
- MUST define one shared monster hydration contract used by readiness, finisher, and runtime-authorized hydration.
- MUST allow packet-built modules to hydrate monsters from authored module content even when `monsters_seed.json` is absent.
- MUST preserve authored-content-only authorization boundaries.
- MUST support authored non-bestiary monsters through controlled AI generation that writes schema-valid module-local monster files.
- MUST keep unresolved references blocking and inspectable instead of degrading into false success.
- SHOULD improve toolkit reporting so operators can see why hydration converged or failed.

**Non-Goals:**
- NOT relaxing validator `reference_integrity` rules.
- NOT authorizing monsters from freeform narration, review notes, or chat history.
- NOT turning monster generation into an unrestricted open-ended creative rebuild of the module.
- NOT broadening this slice into semantic publication probes or full finisher redesign.
- NOT replacing existing runtime encounter authorization rules with uploader-only logic.

## Decisions

### Decision: Introduce a shared authoritative monster hydration service
- Rationale: the same authored monster reference should resolve the same way regardless of whether it appears during packet-build readiness, post-build finishing, or runtime encounter startup.
- MUST centralize hydration precedence and structured outcomes in one shared helper surface.
- SHOULD extend the existing monster-authorization layer rather than add another parallel toolkit-only resolver.
- Alternative considered: keep readiness, finisher, and runtime on separate helpers and only patch the readiness gate.
- Rejected because it preserves drift and guarantees the next edge case will reappear in a different workflow.

### Decision: Authorization remains authored-content-only
- Rationale: the builder must be able to invent stats for module-authored monsters, but it must not invent new monster identities from transient narration or repair prompts.
- MUST derive authorized monster identities from module area data, emitted seed artifacts, module context, and other builder-owned authored assets only.
- MUST treat missing seed artifacts as an input-shape problem, not as lack of authorization, when area/module files clearly authorize the monster.
- Alternative considered: allow readiness repair prompts to authorize additional monsters implicitly.
- Rejected because that would weaken reference integrity and make publication state non-deterministic.

### Decision: Hydration precedence is deterministic-first, AI-last
- Rationale: deterministic sources are cheaper, more reproducible, and easier to audit.
- MUST apply this precedence order:
  1. existing module-local monster file,
  2. reusable trusted monster file from another module or canonical source,
  3. bestiary-backed materialization,
  4. controlled AI generation for an authorized monster,
  5. structured blocking failure.
- SHOULD emit the winning hydration mode in all structured reports.
- Alternative considered: prefer AI generation once a bestiary miss occurs.
- Rejected because it discards reusable deterministic content and increases provider dependence.

### Decision: Packet-builder parity comes from authored reference discovery, not mandatory seed duplication
- Rationale: packet-built modules already contain authored monster references in area files even when the ingest seed artifacts were never emitted.
- MUST allow hydration input discovery from live module assets when seed artifacts are absent.
- SHOULD still preserve or emit seed artifacts where convenient, but readiness and finisher MUST NOT depend exclusively on their presence.
- Alternative considered: force packet-builder to emit `monsters_seed.json` before any later stage can hydrate monsters.
- Rejected as the only fix because it still leaves runtime and finisher logic bifurcated and does not solve already-built modules.

### Decision: Controlled AI generation is an explicit authored-monster feature, not an opaque fallback
- Rationale: the user expectation is correct: module builder should be able to create a new monster from story context with SRD-compatible stats when no canonical bestiary record exists.
- MUST scope AI generation to monsters already authorized by authored module content.
- MUST require schema-valid local output before hydration is considered successful.
- MUST classify provider outage, quota, or builder exceptions distinctly from unauthorized reference failures.
- SHOULD include authored context such as location description, monster prose, danger level, and recommended level when generating non-bestiary monsters.
- Alternative considered: require every missing monster to be added to the global compendium first.
- Rejected because it blocks bespoke module monsters and makes the toolkit dependent on manual global data maintenance.

### Decision: Readiness remains fail-closed but stops retrying unchanged opaque failures
- Rationale: the current `repair_budget_exhausted` path is useful only if retries represent real alternative repair work.
- MUST route readiness monster repair through the shared hydration service instead of `ModuleGenerator._ensure_monster_reference_closure()`.
- MUST stop on unchanged validation signatures or repeated hydration failure for the same authorized monster.
- SHOULD surface blocker classes such as `missing_hydration_inputs`, `unauthorized_monster_reference`, `authorized_monster_hydration_failed`, and `provider_unavailable`.
- Alternative considered: keep the existing readiness retry loop and add more passes.
- Rejected because the current failure is architectural, not budget-related.

### Decision: Shared hydration writes must be atomic and concurrency-safe enough for web workflows
- Rationale: readiness, finisher, and runtime may all attempt to create the same local monster file in adjacent workflows.
- MUST treat the existence of a valid target file as idempotent success.
- MUST use atomic JSON write patterns for new monster files.
- SHOULD avoid global mutable caches so separate web requests and subprocesses can converge safely on filesystem truth.
- Alternative considered: maintain a process-global in-memory hydration registry.
- Rejected because web reloads, subprocess materialization, and multiprocess startup paths would drift from that state.

### Decision: Observability is part of the contract
- Rationale: monster hydration now becomes a core convergence layer, so developers and operators need high-signal diagnostics.
- MUST emit structured result payloads with requested name, canonical slug, authorization mode, hydration mode, and blocking reason.
- SHOULD persist stage reports into toolkit workspace artifacts and finisher/build reports without changing validator truth.
- Alternative considered: rely on freeform stderr from `monster_builder.py`.
- Rejected because that is exactly what produced the current unhelpful `Unknown error` failure.

## Risks / Trade-offs

- [AI generation creates weak or thematically poor monsters] -> Mitigation: deterministic sources remain preferred, generation is scoped to authored context, and output must still pass schema validation.
- [Shared hydration broadens blast radius of future bugs] -> Mitigation: centralize only the resolution contract, keep validator authority unchanged, and require structured failure classes.
- [Packet-built modules still miss enough context for good bespoke monster generation] -> Mitigation: pull context from area/location description, danger level, recommended level, and authored monster prose before declaring the feature complete.
- [Provider outage blocks playable module output for bespoke monsters] -> Mitigation: fail closed with explicit `provider_unavailable` or equivalent blocker class instead of silent retries; keep reusable and bestiary hydration ahead of provider dependence.
- [Duplicate implementations linger during migration] -> Mitigation: route readiness and finisher through the shared helper first, then reduce legacy helper usage to compatibility wrappers.

## Migration Plan

1. Introduce the shared hydration helper and structured result contract.
2. Teach the helper to discover authorized monster refs from live module assets when seed artifacts are absent.
3. Route `scripts/homebrew_materialize_monsters.py` through the shared helper so finisher and ingest use the same precedence order.
4. Route `web/extensions/toolkit_homebrew_readiness_gate.py` through the same helper for deterministic monster repair.
5. Align runtime-authorized hydration to the same precedence/result contract, preserving encounter-time authorization semantics.
6. Extend toolkit reports and build/finisher artifacts with hydration-mode diagnostics.
7. Retire or narrow the legacy closure path once parity tests pass.

Rollback strategy:

1. Repoint readiness and finisher to their previous helper paths.
2. Keep the shared helper inert as an additive utility.
3. Preserve newly written module-local monster files as valid artifacts; rollback only changes future hydration routing, not already-created content.

## Open Questions

- Should reusable deterministic sources include only other module-local monster files, or also curated standalone canonical monster JSON beyond the compendium?
- Should controlled AI generation write provenance metadata into module-local monster files, or keep files schema-pure and store provenance only in sidecar/build reports?
- Do we want an optional strict mode that forbids AI generation for bespoke monsters during publication-oriented workflows while still allowing it in toolkit builder workflows?
