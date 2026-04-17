## Context

The uploader now has two implemented slices: a contract-first routing/workspace substrate and a review gate. The sequencing gap is that review can currently operate on a placeholder normalized packet instead of a true source interpretation. That conflicts with `plans/module-uploader.md`, which expects Phase 2 normalization and Phase 3 normalization job orchestration to happen before Phase 4 review.

This change restores that ordering by adding the actual normalization backend and aligning toolkit job states so `awaiting_review` means "real normalized packet ready" rather than "routing placeholder available." The work spans prompt design, provider-backed normalization execution, packet/report persistence, and toolkit upload job transitions, so a technical design is needed.

## Goals / Non-Goals

**Goals:**
- MUST add a dedicated normalization service that converts uploaded markdown into a source-faithful normalized packet.
- MUST persist `normalized_packet.json`, `normalization_report.json`, and `builder_narrative.txt` as outputs of successful normalization.
- MUST update toolkit job orchestration so normalization-required uploads move through `normalizing` before `awaiting_review`.
- MUST fail closed on provider, parsing, or persistence failures by preventing review handoff.
- SHOULD preserve the current review-gate and concept-builder architecture with minimal host-file changes.

**Non-Goals:**
- NOT implementing build-from-packet execution in this change.
- NOT adding inline packet editing or review-note authoring.
- NOT reworking deterministic-ready direct ingest into the builder path.
- NOT merging uploader packet semantics with the separate world-narrative ingestion lane.

## Decisions

### Decision: Add a dedicated normalization service module instead of embedding prompt logic in routes
- Rationale: normalization is now a first-class stage with its own provider calls, persistence outputs, and failure modes. A dedicated service keeps route logic thin and makes the normalizer testable in isolation.
- MUST keep route handlers focused on job orchestration and delegate prompt execution plus packet assembly to a helper module.
- SHOULD place the service under `web/extensions/` or `utils/` rather than folding it into `toolkit_homebrew_routes.py`.
- Alternative considered: perform normalization inline inside the upload job worker.
- Rejected because it would entangle orchestration, provider error handling, and packet formatting in one layer.

### Decision: Normalization output must distinguish grounded facts from assumptions explicitly
- Rationale: the uploader plan calls for a source-faithful interpretation layer, not freeform worldbuilding. Review and later build phases depend on knowing what came from the source versus what was inferred.
- MUST require the normalizer prompt and packet assembly to separate grounded fields from assumptions or warnings.
- SHOULD keep inferred content bounded and auditable through the normalization report.
- Alternative considered: allow the normalizer to fill empty fields freely as long as the packet validates.
- Rejected because it would weaken source fidelity and make review less trustworthy.

### Decision: Review handoff only occurs after successful normalization persistence
- Rationale: the current sequencing issue exists because placeholder packet presence is being treated as review readiness. The corrected boundary is persistence of a real normalized packet and report.
- MUST move a normalization-required upload job into `awaiting_review` only after packet, report, and builder narrative writes succeed.
- MUST leave failed normalization jobs in `failed` or equivalent non-review state with artifacts preserved.
- Alternative considered: continue allowing placeholder packet review and add a later background upgrade step.
- Rejected because it preserves the incorrect approval order and lets users approve non-interpreted sources.

### Decision: Deterministic-ready uploads keep their current fast path
- Rationale: this change fills the missing normalization lane; it does not need to re-architect already deterministic-ready sources.
- MUST preserve deterministic-ready behavior for existing room-based or transformable sources.
- SHOULD leave room for later parity if deterministic-ready uploads also want normalization-backed packet generation.
- Alternative considered: force every upload through the normalizer.
- Rejected because it expands scope and risks regressions for already-working deterministic paths.

### Decision: Provider failure must be surfaced as actionable job error, not silent fallback to placeholder review
- Rationale: a provider-backed normalization stage introduces quota, timeout, and output-shape risks. The safe behavior is to fail closed for review progression while preserving the workspace for retry/debug.
- MUST record provider or parsing failure in the normalization report or job payload.
- MUST NOT replace failed normalization with a placeholder packet that can still be approved.
- SHOULD keep provider handling profile-based and factory-driven to avoid model lock-in.
- Alternative considered: on normalizer failure, fall back to the existing placeholder packet so the user can still review something.
- Rejected because it reintroduces the current sequencing bug under failure.

## Risks / Trade-offs

- [Normalization prompt over-infers content] -> Mitigation: require explicit assumptions separation and bounded source-faithful prompt wording.
- [Provider outages block reviewable uploads] -> Mitigation: preserve workspace artifacts and actionable job error payloads so retries are possible without re-uploading.
- [Packet/report persistence partially succeeds] -> Mitigation: review handoff MUST require all core normalization artifacts to persist successfully.
- [Job-state complexity increases] -> Mitigation: keep the state machine explicit and additive (`normalizing` -> `awaiting_review`) and avoid changing concept-builder states.
- [Deterministic-ready and normalization-required paths drift] -> Mitigation: keep preflight as the routing authority and keep artifact helpers shared.

## Migration Plan

1. Add the normalization prompt and normalization service module.
2. Wire upload job orchestration to call the normalizer for normalization-required uploads and persist packet/report/narrative artifacts.
3. Update job reporting to surface `normalizing` and only enter `awaiting_review` on successful persistence.
4. Extend regression tests for service output, job transitions, and fail-closed provider/persistence behavior.
5. Leave review UI in place but make it consume only true normalized packet handoff states.

Rollback strategy:

1. Remove the normalizer service integration from toolkit upload jobs.
2. Revert upload jobs to the prior routing-only placeholder behavior if needed.
3. Keep additive prompt and artifact files inert if rollback is required quickly.

## Open Questions

- Should `builder_narrative.txt` be produced directly by the normalizer prompt or by a second bounded derivation step from the packet?
- Which provider/model profile should be the default normalizer path, and should normalization support explicit fallback behavior on retryable provider errors?
- Should ACT/LOCATION transformable sources bypass the normalizer entirely, or optionally emit normalized packets for parity later?
