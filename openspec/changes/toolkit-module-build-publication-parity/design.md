## Context

The toolkit builder and the Homebrew ingest path both produce NEQ module directories, but only the ingest side runs a richer post-generation finishing sequence. Today, a successful toolkit build emits a generic `module_complete` event immediately after `builder.build_module(...)` returns. That means generated modules can miss continuity normalization, registry verification semantics, monster seed materialization, and richer reporting already present in the ingest workflow.

This change is intentionally narrower than the full publication plan. The goal is parity with the existing ingest finishing stages, not the full semantic publishability contract from `plans/module-publication.md`.

## Goals / Non-Goals

**Goals:**
- Add a shared finishing stage after toolkit builds complete.
- Reuse existing ingest-oriented normalization and verification helpers where possible.
- Return structured toolkit build results that distinguish raw-generation success from post-build finishing success.
- Keep the concept-builder prompt-driven UX intact.

**Non-Goals:**
- Replacing `ModuleBuilder` with the deterministic importer.
- Implementing full publication semantics such as probe suites, tactical grids, or spatial cartography.
- Changing the watcher or CLI ingest paths.
- Forcing strict failure on every degraded finishing outcome if the underlying module remains usable.

## Decisions

### Decision: Builder parity SHOULD use a shared finishing helper, not inline copied stages
- Rationale: the builder path should call a dedicated helper/service that wraps continuity normalization, verification, materialization, and reporting. This reduces drift and makes later publication-hardening reusable by both builder and ingest flows.
- Alternative considered: add finishing logic directly inside `simulate_build_process(...)`.
- Rejected because that would entangle web transport code with module finishing behavior and make reuse harder.

### Decision: Raw generation success and finishing success MUST be reported separately
- Rationale: `builder.build_module(...)` can succeed while a parity stage degrades or fails later. The toolkit should distinguish these outcomes instead of collapsing them into a single generic success banner.
- Alternative considered: keep existing `module_complete` semantics and log any finishing issues server-side only.
- Rejected because it hides publication-readiness drift from the operator.

### Decision: The first parity slice MUST target existing ingest-ready finishing stages only
- Rationale: continuity normalization, registry verification, and monster materialization already exist and are directly useful. Full semantic publication probes belong in later changes.
- Alternative considered: attach the entire `plans/module-publication.md` scope immediately.
- Rejected because it would mix near-term parity work with larger semantic-authoring research.

### Decision: Degraded outcomes SHOULD preserve generated modules unless an existing strict gate already requires quarantine
- Rationale: some finishing stages are advisory or recoverable. Toolkit users benefit from seeing a degraded result instead of losing all output when the base module generation succeeded.
- Alternative considered: fail closed on any finishing warning.
- Rejected because it would be harsher than the current toolkit UX and would overstate parity with the still-evolving publication plan.

## Risks / Trade-offs

- [Shared helper imports ingest-only assumptions into toolkit flow] -> Mitigation: keep the helper focused on post-build module directories and avoid watcher/CLI-only concerns.
- [Finishing stage runtime makes builder feel slower] -> Mitigation: surface explicit progress and stage names so the user can see why the build is still running.
- [Builder result semantics become more complex] -> Mitigation: preserve a simple top-level status while exposing nested finishing details for advanced review.
- [Parity work is mistaken for full publication compliance] -> Mitigation: explicitly mark semantic publication probes, spatial grounding, and tactical grids as out of scope in both UI copy and change docs.

## Migration Plan

1. Introduce a shared builder post-build finishing helper around an existing generated module directory.
2. Wire the toolkit build thread to call the helper after `builder.build_module(...)` returns.
3. Update toolkit progress/result reporting to distinguish generation completion from finishing completion.
4. Add regression coverage for success, degraded, and failure mappings.
5. Rollback path: disable the finishing helper call and restore the prior immediate-complete behavior.

## Open Questions

- Should builder parity persist a toolkit-specific build report only, or should it adopt the ingest sidecar pattern directly?
- Which finishing outcomes should count as hard failure versus degraded success for toolkit-driven builds?
