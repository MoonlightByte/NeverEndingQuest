## Context

The structural uploader slice did the work it was supposed to do. Numillian stopped failing for monster materialization drift, schema breakage, area/map parity drift, and hidden-NPC false positives. The new post-reingest result is narrower: the module is structurally real enough to validate, but the finisher/reporting layers still collapse two different kinds of remaining debt into misleading failure language.

The monster media result is the clearest example. The toolkit route currently invokes the ingest pipeline with `allow_provider=False`. The monster-media prewarm contract already says provider fallback is opt-in. The finisher then evaluates gameplay/media expectations against module-local monster assets. When those assets do not exist, the current report says `Missing base media for: <slug>` without clearly saying that no provider-backed monster generation was attempted in that toolkit run and that the intended remediation is the existing manual toolkit image-generation workflow.

The `paradox sanctuary` phrase is the semantic analogue. The semantic-authority layer already reduced broad prose mining, and the module still resolves canonical `Veiled Paradox Sanctuary -> H01`. The residual phrase is not proof that the deterministic structural layer is broken. It is evidence that one remaining player-facing contraction should be handled by the later intelligent ambiguity layer.

This change does not start Phase 2. It formalizes how the deterministic system should report these two residual classes.

## Goals / Non-Goals

**Goals:**
- MUST make toolkit finisher/reporting explicitly state whether monster media was reused, generated, skipped because provider generation was disabled, or remains missing after an allowed generation attempt.
- MUST surface the existing toolkit monster-image generation flow as the manual remediation path when media is still missing.
- MUST preserve the existing provider opt-in contract for monster media generation.
- MUST keep combat-valid monster media debt visible and strict at publishability time.
- MUST classify `paradox sanctuary`-style residuals as explicit Phase 2 ambiguity debt when deterministic resolution is intentionally deferred.
- MUST preserve the distinction between structural readiness and publishability.
- MUST add verification/reporting coverage that proves the Numillian canary now fails, degrades, or passes for the right stated reasons.

**Non-Goals:**
- NOT enabling broad provider generation automatically for all toolkit runs.
- NOT duplicating the existing toolkit monster-image generation surfaces inside finisher automation.
- NOT starting LLM-assisted semantic reconciliation in this change.
- NOT broadening destination extraction heuristics to absorb informal contractions.
- NOT weakening gameplay/media requirements for combat-valid structural monsters.
- NOT changing runtime combat, narration, or SP/MP gameplay behavior.

## Decisions

### Decision: Toolkit monster-media outcome must be explicit about policy, attempt state, and manual remediation path
- Rationale: the current report makes it easy to read missing media as if earlier image-generation work disappeared. The actual state is that the toolkit path did not run provider-backed monster generation and did not produce module-local monster assets.
- MUST surface one explicit monster-media outcome contract for toolkit-facing reporting, with states such as:
  1. reusable media satisfied,
  2. provider generation executed and succeeded,
  3. provider generation disabled and media remains missing,
  4. provider generation allowed but media still unresolved.
- MUST preserve module-local monster media as the audited base for gameplay/publishability.
- MUST, for unresolved toolkit outcomes, point to the existing manual toolkit monster-image workflow as the operator remediation path.
- SHOULD reuse the existing prewarm result shape instead of inventing a separate incompatible reporting vocabulary.

### Decision: Provider-disabled monster media debt may be non-structural while remaining release-blocking
- Rationale: a toolkit-built module can be structurally valid and still lack release-ready monster media. That should not be conflated with hydration/schema failure.
- MUST keep readiness/publishability semantics distinct.
- SHOULD allow toolkit reporting to describe provider-disabled missing monster media as explicit media debt rather than structural corruption.
- MUST preserve publishability failure when required base monster media is still absent for combat-valid monsters.
- SHOULD leave the exact readiness severity open to this slice's implementation, but it MUST be reported explicitly and consistently.

### Decision: `paradox sanctuary` is a bounded Phase 2 ambiguity case
- Rationale: canonical destination authority is already present for `Veiled Paradox Sanctuary`, and the remaining contraction does not justify reopening broad deterministic prose mining.
- MUST allow semantic publication reporting to classify this exact class of residual as `phase2_ambiguity_debt` or equivalent explicit label when deterministic closure is intentionally deferred.
- MUST keep the phrase out of misleading structural-failure messaging.
- MUST NOT silently auto-resolve the phrase by widening generic extraction heuristics.
- SHOULD preserve the phrase and provenance in diagnostics so the later LLM-assisted layer has explicit input.

### Decision: Publishability reporting must preserve debt class boundaries
- Rationale: the repo already distinguishes readiness from publishability. This slice needs that distinction to remain legible when the remaining issues are release debt and Phase 2 ambiguity debt rather than broken structure.
- MUST preserve `ready_status` and `publishable_status` as separate outputs.
- MUST report monster-media debt distinctly from semantic Phase 2 ambiguity debt.
- SHOULD update canary/report artifacts so post-reingest Numillian results show structural green plus residual debt classes clearly.

## Architecture

### Toolkit media reporting path
Recommended shape:

1. toolkit build/finisher declares source=`toolkit`
2. shared prewarm/media helper contract is consulted or replayed for monster-media outcome
3. gameplay audit/reporting evaluates module-local monster media
4. report classifies missing media according to provider policy and attempt state, and names the existing manual toolkit generation flow as the next remediation step when appropriate
5. publishability preserves strict release decision while exposing the exact debt class

The important rule is that report consumers can tell the difference between:
- no generation attempted because provider path was disabled,
- generation attempted and failed,
- reused media satisfied,
- missing assets remain true release debt.

The equally important rule is that the deterministic system does not recreate the toolkit's existing manual media-generation surfaces inside the finisher. This slice clarifies and routes; it does not automate operator media creation.

### Semantic ambiguity reporting path
Recommended shape:

1. semantic authority still emits canonical destination authority from canonical fields only
2. semantic publication audit/probes inspect unresolved phrases
3. when a phrase is recognized as a bounded contraction/ambiguity intentionally deferred to Phase 2, the result is labeled as Phase 2 ambiguity debt rather than structural contradiction
4. publishability remains free to fail on that semantic debt if policy requires, but the failure message must name the right class

This keeps deterministic authority narrow while avoiding false suggestions that structural extraction regressed.

## Risks / Trade-offs

- [Media reporting becomes too soft] -> Mitigation: keep publishability strict for missing base monster media even when the report clarifies provider-disabled attempt state.
- [Readiness semantics become inconsistent across sources] -> Mitigation: tie toolkit reporting to explicit source=`toolkit` policy and keep watcher-sidecar behavior unchanged.
- [Phase 2 ambiguity label is overused] -> Mitigation: scope the label to explicitly bounded unresolved phrases with preserved provenance, not broad semantic misses.
- [Developers infer that provider generation should auto-run by default] -> Mitigation: restate opt-in provider contract in the change and require reporting to say when generation was disabled.

## Migration Plan

1. Define the toolkit monster-media outcome contract and align it with existing prewarm/provider fallback semantics plus manual toolkit remediation guidance.
2. Update gameplay/readiness/publishability reporting to surface explicit monster-media debt classes.
3. Update semantic publication reporting to classify `paradox sanctuary`-style residuals as Phase 2 ambiguity debt when explicitly deferred.
4. Refresh targeted tests for monster-media reporting and semantic ambiguity classification.
5. Re-run the Numillian post-reingest finisher/readiness/publishability canary and persist a current artifact.

Rollback strategy:

1. Restore prior reporting text if the new debt-class taxonomy causes regressions.
2. Keep any new canary artifacts and tests as historical evidence even if code rollback is needed.

## Verification Plan

Minimum verification for this change should include:

1. targeted tests covering toolkit monster-media reporting under provider-disabled and provider-enabled states,
2. tests proving publishability still fails when combat-valid monster base media is missing,
3. semantic audit/probe tests proving a bounded deferred ambiguity is labeled explicitly instead of reported as generic structural contradiction,
4. a fresh Numillian finisher/readiness/publishability run with updated canary artifact,
5. `openspec validate gui-builder-numillian-postreingest-gate-reconciliation`.
