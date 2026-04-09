## Context

The prior spatial-contract change completed field-shape parity across builder, ingest, remediation, and validation. The remaining gap is qualitative rather than structural:

- ingest still constructs room connectivity from sequential source order before calling the shared planner
- strict spatial validation checks field presence, map/area parity, and direction membership, but not whether the emitted geometry actually makes sense

This change is intentionally the last `module-maps` slice before `plans/module-publication.md`. It should finish spatial authoring quality without mixing in the broader publication semantics work.

## Goals / Non-Goals

**Goals:**
- Make ingest use deterministic authored adjacency extraction when source text contains stronger relationship cues than source order.
- Keep the shared spatial helper as the single planning surface for ingest, builder, and remediation callers.
- Add explicit geometric coherence rules for strict spatial-contract outputs.
- Preserve legacy warn-first behavior and fail-open generation fallbacks when semantics are incomplete.

**Non-Goals:**
- Adding publication-time destination/NPC semantic audits.
- Introducing a `publishable` result tier.
- Reworking builder spatial generation beyond keeping helper parity.
- Adding runtime map services or movement-graph behavior.

## Decisions

### Decision: Ingest adjacency extraction MUST be deterministic and bounded before spatial planning
- Rationale: the missing gap is not coordinate formatting but source-order topology. The importer should build a better graph first, then reuse the existing planner.
- Approach: add a deterministic authored-adjacency extraction helper that inspects room names/descriptions and explicit references such as exits, stairs, wings, halls, chambers, and named destinations already present in the imported room set.
- Alternative considered: move all semantic graph inference into an LLM call.
- Rejected because this slice needs reproducible ingest behavior and should not widen provider dependency for baseline module generation.

### Decision: The shared spatial helper SHOULD remain the single coordinate/direction authority
- Rationale: builder, ingest, and remediation already converge on `resolve_semantic_spatial_plan(...)`. Strengthening ingest should improve inputs to that helper, not fork a second planner.
- Alternative considered: implement ingest-only layout logic inside the importer.
- Rejected because it would recreate parity drift the previous change just removed.

### Decision: Strict spatial coherence MUST fail only on explicit geometric contradictions
- Rationale: the validator should catch obviously broken new outputs without inventing narrative constraints that modules never authored.
- Strict checks should cover:
  - connected rooms whose coordinates are not cardinally adjacent unless a bounded exception contract exists
  - direction entries whose target coordinate delta does not match the cardinal label
  - strict map/area layouts whose local geometry cannot support the declared room graph
- Alternative considered: broad heuristic scoring of "good" layouts.
- Rejected because it would be hard to audit and unstable across modules.

### Decision: Legacy modules MUST remain warnings-only for these stronger checks
- Rationale: this change is about finishing current authoring output quality, not invalidating older content already in play.
- Alternative considered: fail all modules on new coherence rules immediately.
- Rejected because it would convert a data-prep improvement into a repo-wide remediation event.

## Risks / Trade-offs

- [Weak prose yields under-connected extracted graphs] -> Mitigation: if authored evidence is insufficient, extraction falls back to the current safe sequential scaffold rather than deleting connectivity.
- [Strong validator rules block active ingest experimentation] -> Mitigation: apply the new coherence failures only to strict spatial-contract-marked outputs and add focused regression fixtures before rollout.
- [Importer and validator logic drift apart] -> Mitigation: centralize coordinate/direction semantics in `utils/spatial_contract.py` and keep validator delta rules based on the same coordinate parsing helpers.
- [Future publication work wants richer exceptions such as teleport links] -> Mitigation: keep this slice narrow and allow later publication changes to extend the exception contract explicitly instead of baking speculative behavior in now.

## Migration Plan

1. Add deterministic authored-adjacency extraction helpers in the shared spatial layer or a tightly scoped ingest helper.
2. Update `core/importers/homebrewery_importer.py` to build room records from extracted authored adjacency before calling `resolve_semantic_spatial_plan(...)`.
3. Extend `core/validation/validate_module_files.py` with strict geometric coherence checks while preserving warning-only legacy behavior.
4. Add targeted regressions for non-linear ingest source structure and strict validator failure cases.
5. Validate at least one real ingested module path and keep rollback simple by reverting the importer to sequential adjacency plus removing the new validator checks.

## Open Questions

- Which explicit exception marker, if any, should allow non-adjacent connected rooms in strict outputs without failing coherence validation?
- Should ingest adjacency extraction recognize only room-to-room textual references within the same imported area, or also infer cross-room adjacency from repeated landmark nouns when no explicit destination phrase appears?
