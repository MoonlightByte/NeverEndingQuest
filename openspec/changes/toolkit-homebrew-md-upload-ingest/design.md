## Context

The repository already has a capable Homebrew ingest pipeline, but it is operator-oriented. `scripts/homebrew_ingest_dev.py` orchestrates preflight, transform, dry-run, strict ingest, continuity normalization, registry verification, monster materialization, and media stages. The toolkit, by contrast, only sends `start_build` events for AI-first concept generation and has no direct source-import surface.

The watcher at `web/extensions/module_ingest_watch.py` proves that the shared ingest pipeline is safe to call from the web process, but the watcher is file-system driven and intentionally strict. The toolkit upload flow should reuse the same pipeline contract without forcing the user to interact with `modules/ingest/` or understand archive-sidecar conventions.

## Goals / Non-Goals

**Goals:**
- Add a first-class toolkit upload path for `.md` Homebrewery exports.
- Reuse the existing `run_ingest_pipeline(...)` orchestration as the single source of ingest truth.
- Surface pipeline stages and outcomes in the toolkit UI with a stable result contract.
- Keep the upload path isolated from the existing concept-based Module Builder flow.

**Non-Goals:**
- PDF upload or PDF-to-markdown normalization.
- Replacing the existing watcher or CLI ingest workflows.
- Implementing full publication semantics from `plans/module-publication.md`.
- Refactoring the deterministic importer structure beyond what is needed for direct toolkit invocation.

## Decisions

### Decision: The toolkit MUST call the shared ingest orchestrator directly
- Rationale: `run_ingest_pipeline(...)` already encodes the strict stage order, guard behavior, continuity normalization, verification, and media handling. Reusing it avoids another drift-prone copy of the ingest rules.
- Alternative considered: a toolkit-specific ingest path inside `web/web_interface.py`.
- Rejected because it would immediately diverge from CLI/watcher behavior and duplicate strict-stage logic.

### Decision: The first slice MUST be markdown-only
- Rationale: the user explicitly approved `.md` only. Markdown upload can ride the existing pipeline immediately, while PDF support needs extraction, normalization, and more failure classes.
- Alternative considered: `.md` + `.pdf` in one change.
- Rejected because it would mix transport/UI work with document-extraction design and slow review.

### Decision: The toolkit SHOULD use a job/result contract instead of raw log streaming
- Rationale: the ingest pipeline already returns structured `status`, `stage`, `exit_code`, and nested stage payloads. The toolkit should present those results directly instead of inventing another free-form progress language.
- Alternative considered: stream plain text logs to the toolkit.
- Rejected because text logs are harder to test, harder to map to GUI states, and easier to drift from pipeline semantics.

### Decision: Uploaded sources MUST remain isolated from watcher-managed ingest paths
- Rationale: toolkit uploads should not silently drop files into `modules/ingest/` and wait for the watcher. Direct invocation is simpler for users and avoids race conditions between upload jobs and the watcher thread.
- Alternative considered: reuse watcher directories as the toolkit upload buffer.
- Rejected because it would create ambiguous ownership, duplicate archive traces, and non-deterministic timing.

### Decision: Host changes SHOULD stay minimal and extension-friendly
- Rationale: toolkit upload behavior is a good fit for a dedicated route/helper module with thin wiring from `web/web_interface.py` or existing toolkit route surfaces.
- Alternative considered: large inline route/handler additions directly in `web/web_interface.py`.
- Rejected because the toolkit already has enough host-file density.

## Risks / Trade-offs

- [Upload job blocks too long in the web process] -> Mitigation: run ingest in a background thread or job wrapper similar to existing builder flows and surface staged completion asynchronously.
- [Toolkit job contract diverges from pipeline result shape] -> Mitigation: preserve pipeline `status` and `stage` fields as the authoritative job truth and only add GUI wrapper metadata around them.
- [Users assume any markdown will work] -> Mitigation: expose strict preflight rejection and show the pipeline's quarantine reason and remediation guidance.
- [Watcher and toolkit import the same helper differently over time] -> Mitigation: keep `run_ingest_pipeline(...)` as the single shared entrypoint and avoid introducing a second orchestration function.
- [Media stages add latency or cost surprise] -> Mitigation: the job result SHOULD make provider/media stage behavior explicit, and the first UI copy SHOULD frame the flow as full ingest rather than instant parse-only import.

## Migration Plan

1. Add toolkit upload/job backend that stages a markdown file outside watcher-owned directories and calls `run_ingest_pipeline(...)`.
2. Add toolkit UI controls and job status/result rendering.
3. Add regression coverage for extension filtering, duplicate job guarding, success/quarantine/degraded result mapping, and watcher independence.
4. Roll out with markdown-only support and preserve existing concept-builder tab behavior.
5. Rollback path: remove the toolkit upload entrypoints and UI while leaving CLI/watcher ingest unchanged.

## Open Questions

- Should toolkit uploads be persisted under a dedicated temporary directory for later operator inspection, or deleted after the job completes successfully?
- Should the first UI slice expose dry-run details in a collapsible report, or only final stage summaries plus quarantine reasons?
