## Context

The public uploader has now reached a correct pre-build boundary: readable markdown can be normalized into a true packet, the packet is reviewable, and operator approval persists a release-boundary snapshot. The next missing slice from `plans/module-uploader.md` is Phase 5: build from normalized packet.

Today the only rich builder entrypoint is the concept-builder socket flow in `web/web_interface.py`, which expects raw narrative, area counts, and location counts, and then immediately continues into post-build finishing. That is the wrong contract for approved upload jobs because:

1. approval must remain a resumable state rather than auto-starting the build,
2. upload jobs need persisted `builder_input.json` and `build_result.json`,
3. build completion must remain distinct from later finishing/publication stages,
4. the upload lane should be able to rebuild from packet without rerunning normalization.

This change fills that gap by adding a packet-aware builder facade and a dedicated build-start transition for approved upload jobs.

## Goals / Non-Goals

**Goals:**
- MUST add a dedicated packet-driven build facade for approved upload workspaces.
- MUST persist `builder_input.json` before builder execution starts.
- MUST keep approval and build start as separate actions and states.
- MUST reuse the upstream `ModuleBuilder` path internally wherever practical.
- MUST persist `build_result.json` with authoritative packet identity and build outcome details.
- SHOULD expose `approved_for_build`, `building`, and `build_completed` clearly in toolkit reporting.

**Non-Goals:**
- NOT reattaching post-build finishing, semantic audits, or registry integration in this change.
- NOT collapsing upload builds into the concept-builder socket contract.
- NOT adding inline packet editing or approval-note authoring.
- NOT replacing deterministic-ready direct ingest behavior.

## Decisions

### Decision: Add a dedicated upload-aware builder facade instead of reusing `start_build` directly
- Rationale: the current `start_build` socket path is shaped around freeform concept input and currently continues into post-build finishing. Upload jobs need workspace-aware packet validation, artifact persistence, and upload-job state transitions.
- MUST introduce a dedicated helper module that reads `normalized_packet.json` and the review snapshot from the upload workspace.
- SHOULD share internal builder invocation helpers with the concept-builder flow if extraction is small and safe.
- Alternative considered: call the existing socket path with synthesized narrative text only.
- Rejected because it would hide packet identity, bypass upload-job ownership, and make build artifact persistence ad hoc.

### Decision: Approval remains resumable and does not auto-start the build
- Rationale: the review gate is the human release boundary; it should not be overloaded as a build execution trigger. Keeping approval separate preserves retryability and clearer operator control.
- MUST keep `approved_for_build` as a stable pre-build state.
- MUST add an explicit build-start action for approved jobs.
- Alternative considered: change approve to `Approve and Build` and start immediately.
- Rejected because it would weaken resumability and conflate policy approval with compute execution.

### Decision: Packet-to-builder transformation is persisted and auditable
- Rationale: `plans/module-uploader.md` treats `builder_input.json` as a canonical artifact. The build handoff should therefore persist the transformed builder input before invoking the builder.
- MUST write `builder_input.json` with packet identity, build mode, derived builder parameters, and builder narrative inputs.
- SHOULD preserve enough packet provenance in the transformed input so later rebuilds do not require the original normalization call.
- Alternative considered: compute builder arguments in memory only.
- Rejected because it would undermine auditability and packet-based rebuild semantics.

### Decision: Build completion stops at a pre-finishing state
- Rationale: post-build finishing and publication parity are intentionally deferred to the next uploader slice. This change must not imply that a built module is already publication-safe.
- MUST end successful packet builds in a distinct state such as `build_completed`.
- MUST reserve final `completed` semantics for the later finisher-integrated flow.
- Alternative considered: mark the upload job `completed` after raw builder success.
- Rejected because it would blur the line between raw generation and validated/publishable output.

### Decision: Reuse `ModuleBuilder` as the default rich-generation engine
- Rationale: the plan explicitly calls for the upstream builder strengths to be reused. Packet-driven uploads should benefit from the richer generation path instead of falling back to deterministic import alone.
- MUST use the upstream builder as the default mode for approved upload builds.
- SHOULD preserve room for a future deterministic-emitter fallback, but that fallback is not required in this slice.
- Alternative considered: build packet-driven uploads entirely through deterministic emit now.
- Rejected because it would undercut the stated goal of richer public upload output quality.

### Decision: Build reporting stays on the upload job contract rather than builder-only socket messages
- Rationale: upload users already have job polling and artifact workspaces. Packet-driven build progress should remain attributable to the authoritative upload job.
- MUST update upload job state transitions directly during packet-driven build execution.
- SHOULD translate major builder progress milestones into job `stage` / `pipeline_status` updates without inventing a second source of truth.
- Alternative considered: surface only socket progress events for upload builds.
- Rejected because it would fragment state and make resume/retry flows harder.

## Risks / Trade-offs

- [Packet transformation under-specifies builder input] -> Mitigation: persist `builder_input.json` explicitly and test representative packet transformations.
- [Concept-builder refactor causes regressions] -> Mitigation: keep concept-builder entrypoints intact and share only small internal helpers when beneficial.
- [Upload builds look final before finisher exists] -> Mitigation: use `build_completed` rather than `completed`, and message clearly that finishing/publication is not yet attached.
- [Builder failures leave ambiguous artifacts] -> Mitigation: persist `build_result.json` with explicit failure payloads and preserve the approved packet workspace.
- [Approved job can be built multiple times inconsistently] -> Mitigation: define explicit allowed transitions and overwrite or version `build_result.json` deterministically in v1.

## Migration Plan

1. Add the upload-aware packet-to-builder facade and the `builder_input.json` transform contract.
2. Add explicit build-start orchestration for `approved_for_build` upload jobs.
3. Update toolkit reporting/UI to expose pre-build, building, and build-completed states distinctly.
4. Add regression tests for transform shape, job transitions, and concept-builder non-regression.
5. Stop at `build_completed`; defer finishing/publication wiring to the next uploader change.

Rollback strategy:

1. Remove the packet-driven build facade and build-start route/action.
2. Leave existing approved review snapshots and normalized packets intact.
3. Preserve additive builder artifact files as inert data if rollback is needed quickly.

## Open Questions

- Should packet-driven build execution extract a shared helper from `simulate_build_process(...)`, or keep the concept-builder socket flow untouched and duplicate only a very small invocation wrapper?
- What is the smallest stable `builder_input.json` contract that still supports rebuild-from-packet in the next phase?
- Should the first packet-driven build UI expose a dedicated `Start Build` button only for `approved_for_build`, or also surface a limited retry action after `build_completed` / `failed` in the same slice?
