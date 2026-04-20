## Context

The previous change fixed the structural builder issues that were blending unrelated failures together. The resulting 6.2 baseline and 6.3 Numillian re-ingest prove the pipeline is now exposing the right classes of problems, but not yet handling them in an operationally clean way.

The two most important new facts are:

1. toolkit provenance is now a real contract, but the finisher currently validates that contract before it writes the toolkit report for the same run;
2. semantic systems can now degrade with warning-only/tooling-debt findings after the false destination and hidden-NPC blockers were removed, yet publishability still collapses those cases into full failure.

This slice defines the rollout/remediation workflow that sits between structural stabilization and any later LLM-assisted classification work.

## Goals / Non-Goals

**Goals:**
- MUST fix same-run toolkit provenance ordering so toolkit-source audits can validate the current run safely.
- MUST preserve strict watcher-source sidecar behavior.
- MUST distinguish semantic blocking findings from warning-only or tooling-debt degradation in publication policy.
- MUST expose remediation categories clearly in toolkit/CLI reporting.
- MUST define rerun expectations for legacy watcher modules versus toolkit-built modules.
- MUST use `The_Hidden_City_of_Numillian` as the primary toolkit remediation canary.

**Non-Goals:**
- NOT adding Phase 2 LLM classification.
- NOT weakening real monster media requirements for structured combatants.
- NOT making legacy watcher modules automatically pass toolkit provenance.
- NOT changing runtime combat/gameplay authority.

## Decisions

### Decision: Toolkit provenance must be satisfiable during the same finisher run
- MUST either persist a preliminary toolkit report before publishability/readiness runs or pass an equivalent in-memory provenance contract into readiness.
- MUST NOT require a toolkit finisher run to fail merely because it has not yet written the report artifact that the same run is about to write.
- SHOULD prefer a persisted preliminary artifact because it keeps CLI/tooling visibility simple and auditable.

### Decision: Source contracts remain strict and asymmetric by design
- `watcher` MUST continue requiring ingest-sidecar provenance.
- `toolkit` MUST continue requiring toolkit provenance.
- Legacy modules without toolkit reports SHOULD continue failing toolkit-source audits unless explicitly rebuilt or migrated.
- This asymmetry is correct and should be documented as expected behavior, not treated as residual breakage.

### Decision: Semantic warning/tooling debt must not equal semantic contradiction
- Semantic publication policy MUST distinguish:
  1. blocking semantic contradictions,
  2. warning-only authored ambiguity,
  3. tooling/fixture debt.
- Only category 1 MUST fail publishability automatically.
- Categories 2 and 3 SHOULD remain visible in reporting and remediation output.

### Decision: Remediation output should classify blockers by action path
- Reporting SHOULD emit remediation classes such as:
  - `provenance_ordering_bug`
  - `legacy_provenance_gap`
  - `structured_monster_media_missing`
  - `semantic_warning_only`
  - `semantic_tooling_debt`
  - `scene_entity_modeling_candidate`
- This keeps follow-up work deterministic and prepares a future review layer without requiring LLM classification in this slice.

### Decision: Numillian is the first toolkit canary
- `The_Hidden_City_of_Numillian` MUST be the first end-to-end canary because:
  - its toolkit provenance already exists,
  - the original structural materialization failure is fixed,
  - remaining failures are now attributable to ordering, media debt, and semantic policy.

## Architecture

### Finisher provenance flow

Recommended same-run order:

1. run finishing stages that produce deterministic artifacts
2. write preliminary toolkit provenance/report payload
3. run toolkit-source readiness/publishability against that provenance
4. finalize toolkit report with all stage and audit outcomes

This preserves a file-backed audit trail while removing the self-referential failure case.

### Publishability policy model

Recommended semantic outcome mapping:

1. **blocking semantic contradictions present**
   - `publishable_status=fail`
2. **no blocking semantic contradictions, warnings/tooling debt only**
   - readiness unchanged
   - publishability may remain pass or degraded-reporting-only depending on final gate policy
   - MUST NOT be reported as the same class of failure as blocking contradictions

This slice should prefer explicit reporting over silent success, but should stop treating warning-only degradation as a hard contradiction.

### Remediation workflow model

Recommended remediation sequence:

1. run toolkit or watcher audit with explicit source
2. classify outcomes into remediation buckets
3. surface exact operator action per bucket
4. rerun only the affected path when possible
5. record outcome in baseline/canary report artifacts

## Risks / Trade-offs

- [Preliminary toolkit report is mistaken for final success] -> Mitigation: include explicit `status`/`phase` markers so report consumers can tell pre-audit from final audit states.
- [Semantic policy becomes too permissive] -> Mitigation: keep blocking contradictions fail-closed and only relax warning/tooling-debt treatment.
- [Legacy module matrix becomes confusing] -> Mitigation: document watcher-vs-toolkit expectations in a formal rerun matrix.
- [Media remediation pressure gets deferred indefinitely] -> Mitigation: keep structured-monster media failures as first-class blocker categories in reporting.

## Verification Plan

1. regression test same-run toolkit provenance success path
2. regression test watcher-source strictness unchanged
3. regression test warning-only semantic degradation does not masquerade as blocking contradiction
4. regression test probe tooling debt is reported distinctly
5. rerun baseline matrix across representative modules
6. rerun Numillian as toolkit canary and confirm ordering bug is gone
