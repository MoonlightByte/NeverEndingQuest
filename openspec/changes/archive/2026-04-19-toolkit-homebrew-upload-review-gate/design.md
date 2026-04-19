## Context

The previous uploader change established a contract-first substrate for public Homebrew markdown uploads: readable sources can now be preserved in a dedicated workspace, preflight emits routing-aware outcomes, and a normalized packet placeholder can be persisted without forcing deterministic ingest to succeed first. The toolkit still lacks the mandatory human approval boundary described in `plans/module-uploader.md`, which means packet-backed upload jobs can stop at an internal state but cannot yet become a reviewed, operator-controlled workflow.

This design adds that review boundary without coupling it to build execution. The change crosses the toolkit route layer, toolkit UI, upload job state model, and workspace artifact persistence, so a design document is warranted before implementation.

## Goals / Non-Goals

**Goals:**
- MUST add a review gate that reads normalized packet data from the upload workspace and surfaces a curated review summary in the toolkit UI.
- MUST add explicit `approve` and `reject` job actions that update authoritative job state and persist a review snapshot artifact.
- MUST prevent unreviewed jobs from advancing to later build-start or registry-facing stages.
- MUST preserve the current concept-builder workflow and existing upload artifact workspace ownership.
- SHOULD keep first-release scope narrow: review, approve, reject, and snapshot persistence only.

**Non-Goals:**
- NOT implementing the LLM normalization backend in this change.
- NOT building modules from normalized packets in this change.
- NOT adding inline editing, packet patching, or rich review annotation tools in this first review slice.
- NOT merging the uploader lane with the source-anonymous world-narrative ingestion lane.

## Decisions

### Decision: The upload workspace remains the truth source for reviewable packet state
- Rationale: the prior change already established `user_uploads/toolkit/homebrew_md/<job_id>/` as the authoritative artifact workspace. Reusing that workspace avoids duplicate packet storage and makes review decisions auditable against the exact packet on disk.
- MUST read `normalized_packet.json` and write `ui_review_snapshot.json` inside the same workspace.
- SHOULD treat missing or invalid packet artifacts as review-blocking errors rather than silently fabricating UI defaults.
- Alternative considered: copy packet data into in-memory job state and review from memory.
- Rejected because it weakens resumability, complicates debugging, and makes packet/review drift more likely.

### Decision: Review actions use dedicated route handlers, not ad hoc client-side state transitions
- Rationale: approval and rejection are policy decisions, not cosmetic UI state. They need a server-side authority path that can validate current job state, persist the snapshot, and reject invalid transitions.
- MUST require the server to validate that the job is in a reviewable state before accepting `approve` or `reject`.
- SHOULD keep the route surface additive to `web/routes/toolkit_homebrew_routes.py` with minimal host-file impact.
- Alternative considered: let the UI set a client-side approved flag and continue later.
- Rejected because client-only state would not be auditable or safe.

### Decision: Job reporting adds review states but preserves authoritative stage identity
- Rationale: current toolkit upload reporting already distinguishes routing and pipeline status. The review gate should extend that model rather than invent a parallel status language.
- MUST support explicit states such as `awaiting_review`, `approved_for_build`, and `rejected`.
- MUST preserve the job's authoritative `stage`, `pipeline_status`, and `routing_outcome` fields when present.
- SHOULD keep stage wording clear enough that operators understand approval is not the same as build completion.
- Alternative considered: collapse review into a generic `completed` status with a boolean flag.
- Rejected because it hides the gating boundary and creates ambiguous downstream behavior.

### Decision: Review snapshot persistence is fail-closed for approval progression and fail-open for artifact inspection
- Rationale: review approval is the explicit human-release boundary for this lane. If snapshot persistence fails, the system must not advance as though approval succeeded. At the same time, the workspace should remain available for inspection and retry.
- MUST block transition to `approved_for_build` or `rejected` if snapshot persistence fails.
- MUST leave the job and workspace inspectable after a failed review write.
- SHOULD include packet identity fields such as source hash or packet hash in the snapshot so later build changes can verify continuity.
- Alternative considered: allow state change first, then best-effort snapshot write.
- Rejected because it would make approval non-auditable under failure conditions.

### Decision: First-release review UI is curated summary only
- Rationale: the roadmap already prefers approve/reject-only as the first release. That keeps the slice small and avoids entangling review with packet editing before build-from-packet exists.
- MUST display key fields needed for operator judgment: title, author, description, level range, scene/location summary, NPCs, monster refs, warnings, and assumptions.
- SHOULD omit deep inline editing in this slice.
- Alternative considered: add editable metadata and patch-write support now.
- Rejected because it broadens scope into packet-editing and validation work better handled in a later change.

## Risks / Trade-offs

- [Review UI arrives before full normalizer] -> Mitigation: the UI MUST tolerate placeholder packet content and show warnings/assumptions explicitly so review remains meaningful during staged rollout.
- [Operators misread approval as build completion] -> Mitigation: toolkit messaging MUST distinguish `approved_for_build` from any later build state.
- [Snapshot/write failure traps jobs in ambiguous state] -> Mitigation: server-side transitions MUST fail closed and return actionable error payloads while leaving the workspace intact.
- [Concurrent job mutation causes stale approvals] -> Mitigation: review routes MUST validate current job status under the existing job-state lock before applying transitions.
- [Future build change needs more review metadata] -> Mitigation: snapshot contract SHOULD include stable job, packet, and decision fields so later changes can extend it additively.

## Migration Plan

1. Add review-state helpers and snapshot persistence to the upload contract layer.
2. Add route handlers for fetching review payload and posting `approve` / `reject` decisions.
3. Extend toolkit upload polling/UI to surface `awaiting_review` and to render the review summary panel.
4. Add regression tests for state transitions, snapshot persistence, and no-regression builder behavior.
5. Stop after apply-ready review flow; defer actual build-from-packet execution to the next uploader change.

Rollback strategy:

1. Remove review route handlers and UI wiring.
2. Revert job states to the prior upload-routing terminal state model.
3. Preserve existing artifact workspace files; `ui_review_snapshot.json` may remain as inert additive data.

## Open Questions

- Should the review panel fetch the normalized packet through the job-status route payload, or through a dedicated review-detail route that reads workspace artifacts on demand?
- Should `approved_for_build` be a terminal state in this change, or a resumable pre-build state that the next change consumes directly?
- Should review snapshots record only approve/reject decisions in v1, or also reserve a free-text reviewer note field for later use?
