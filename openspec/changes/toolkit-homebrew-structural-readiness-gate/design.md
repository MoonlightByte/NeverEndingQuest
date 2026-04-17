## Context

The uploader roadmap now has routing, normalization, review, and packet-driven raw build slices in place. What is still missing is the structural boundary between "the builder emitted files" and "the module is safe to hand to the finisher/publication stack." The current plan originally assumed Phase 6 could attach directly after Phase 5, but real smoke output from `The_Ancients_Lab` showed that raw builder success can coexist with unresolved validator failures and generator defects.

This design introduces a dedicated readiness gate and bounded remediation loop. It must preserve the repo's existing authority model: Python validation and readiness audit remain authoritative; LLM repair is narrow, targeted, and only used when Python lacks enough semantic information to correct the failing content safely.

## Goals / Non-Goals

**Goals:**
- MUST add a structural readiness stage between packet-driven raw build and finisher/publication.
- MUST use `core/validation/validate_module_files.py` and `scripts/audit_module_readiness.py` as the authoritative post-build readiness gates.
- MUST distinguish builder/runtime defects from content defects and stop immediately on system failures.
- MUST attempt deterministic repair before any semantic repair.
- MUST bound all repair loops and preserve artifacts/reporting for manual inspection.
- SHOULD expose stage-aware reporting in the toolkit UI so users can distinguish build completion from readiness success.

**Non-Goals:**
- NOT attaching finisher/publication stages in this change.
- NOT creating a full inline repair editor for toolkit users.
- NOT replacing `ModuleBuilder` with a deterministic-only emitter.
- NOT introducing broad unconstrained full-module re-generation as a repair mechanism.

## Decisions

### Decision: Raw build completion is a distinct state from readiness success
- Rationale: packet build success only proves raw artifacts were created. It does not prove monster files exist, spatial contracts pass, or generator bugs did not leave broken derived artifacts.
- MUST keep `build_completed` as a pre-readiness state.
- MUST add `ready_for_finishing` as the first state that means the module may enter the finisher.
- Alternative considered: fold validation into `build_completed` and report one success state.
- Rejected because it hides the critical structural boundary and makes debugging much harder.

### Decision: Canonical validator and readiness audit remain authoritative
- Rationale: the repository already has a strict validator plus a readiness aggregator. Reusing those tools preserves existing standards and avoids a second upload-only correctness model.
- MUST run `core/validation/validate_module_files.py --module <slug>` after raw build.
- MUST run `scripts/audit_module_readiness.py --module <slug>` before entering finisher.
- SHOULD persist validation/readiness payloads into the upload workspace for review and retry.
- Alternative considered: build a lighter uploader-only validator.
- Rejected because it would drift from the repo's publication authority.

### Decision: Failure triage is split into builder defects, deterministic output defects, and semantic defects
- Rationale: not all failures should enter the same repair loop. Some indicate broken Python code, others are purely structural and mechanically repairable, and others need semantic judgment.
- MUST stop immediately on builder/runtime defects such as undefined helpers, broken persistence calls, or uncaught generator exceptions.
- MUST run deterministic repair domains first when the failure class is structurally repairable.
- MAY run targeted semantic repair only when deterministic repair cannot resolve the remaining issues safely.
- Alternative considered: route all failures through a generic LLM repair loop.
- Rejected because that would mask generator bugs and create non-converging retries.

### Decision: Deterministic repair happens in domain batches, not one-error-at-a-time
- Rationale: the validator often emits multiple related failures from the same root cause. Grouped repair domains reduce redundant reruns and give clearer progress reporting.
- Initial deterministic domains SHOULD include:
  1. party/world enum normalization,
  2. monster reference materialization,
  3. spatial contract repair,
  4. derived context/summary regeneration.
- MUST rerun validation after each deterministic batch.
- Alternative considered: fix one validator line item at a time.
- Rejected because it increases latency and obscures root-cause convergence.

### Decision: Semantic repair is targeted and patch-oriented
- Rationale: some issues like missing NPC placement or plot-hook coherence cannot be derived mechanically from structure alone, but still do not justify a full rebuild.
- Initial semantic domains SHOULD include:
  1. missing NPC placement into existing locations only,
  2. plot hook repair/enrichment,
  3. summary alignment for narrative report surfaces.
- MUST scope semantic prompts to failing files only.
- MUST apply minimal patch payloads rather than regenerate the whole module.
- Alternative considered: rerun `ModuleBuilder` from scratch with failure notes.
- Rejected because it broadens blast radius and weakens artifact traceability.

### Decision: Repair budgets are strict and fail-closed
- Rationale: uploader latency and convergence both matter. Unbounded retries will hide bad builders and create unclear UX.
- SHOULD start with:
  1. max 2 deterministic passes,
  2. max 2 semantic passes per repair domain,
  3. max 4 total repair cycles.
- MUST stop when the validation signature repeats without improvement.
- MUST surface `repair_budget_exhausted` with grouped fix guidance when convergence does not happen.

### Decision: Toolkit reporting must expose the structural pipeline explicitly
- Rationale: the uploader is becoming a multi-stage asynchronous workflow. Users need to see progress and to understand why a module is not yet ready for finishing.
- MUST surface explicit states such as `validating`, `repairing_deterministic`, `repairing_semantic`, `ready_for_finishing`, `build_system_failed`, and `repair_budget_exhausted`.
- SHOULD add a stage-aware progress bar or equivalent progress indicator.
- SHOULD update the review panel title/state after approval so it no longer lingers as `Review Required` once build or repair stages begin.

## Risks / Trade-offs

- [Validator is too strict for first readiness pass] -> Mitigation: deterministic repair domains should target the most frequent structural failures first, reducing false impressions that the builder is unusable.
- [Repair loops hide builder bugs] -> Mitigation: Class A builder/runtime defect classification fails closed and bypasses all content repair.
- [Repair stages increase perceived latency] -> Mitigation: show stage-aware progress and preserve artifacts so retries can resume without re-normalization.
- [Semantic repair patches drift from source intent] -> Mitigation: semantic prompts must preserve packet identity, use existing locations only where required, and remain patch-oriented.
- [Uploader and developer finisher drift] -> Mitigation: this change still ends before finisher; the next change will consume only `ready_for_finishing` outputs using the same finisher/reporting stack.

## Migration Plan

1. Add post-build job states and reporting fields for validation/repair/readiness outcomes.
2. Add a readiness-gate orchestrator that runs validator + readiness audit and persists their reports.
3. Add deterministic repair domain helpers for initial high-confidence failure classes.
4. Add targeted semantic repair scaffolding for the first narrow repair domains.
5. Extend toolkit reporting/UI for stage-aware progress and grouped failure reporting.
6. Add regression coverage for raw build success vs readiness success and for stop conditions on builder defects.
7. Stop when upload jobs can reliably land in `ready_for_finishing` or a bounded failure state.

Rollback strategy:

1. Remove the readiness-gate orchestration and state transitions.
2. Revert upload jobs to the existing `build_completed|failed` post-build model.
3. Preserve validation/repair artifacts as inert additive files in upload workspaces if already written.

## Open Questions

- Should readiness artifacts live only in the upload workspace, or also mirror into the module directory as upload-owned reports?
- Which deterministic repair domains should be mandatory in v1 of this change, and which should be deferred to follow-up slices if they require too much shared extraction?
- Should semantic repair support multiple domains in the first implementation, or start only with missing NPC placement to keep scope tighter?
