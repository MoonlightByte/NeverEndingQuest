## Context

Watcher ingest is currently a lightweight deterministic importer path with archive + sidecar writing. The dev CLI skill path is a full orchestrated pipeline with strict validation, duplicate guardrails, media stages, and richer reporting.

This mismatch causes operational confusion:
- A file can succeed in CLI flow but fail watcher flow (or vice versa).
- Sidecar audit behavior differs by ingest path.
- Raw Homebrew markdown in `modules/ingest/` is often not deterministic-ready.

## Goals

- Enforce strict watcher behavior: only ingest-ready markdown is accepted.
- Ensure watcher uses the same pipeline stages as CLI for validated inputs.
- Preserve sidecar evidence contract for watcher-processed files.
- Keep provider generation opt-in only.

## Non-Goals

- Do not add LLM rewrite/normalization inside watcher.
- Do not weaken strict gate to auto-transform unknown structures.
- Do not alter game runtime media fallback semantics.

## Decisions

### 1) Strict readiness gate before ingest

Watcher will preflight each candidate and continue only when:
- `ready == true`
- `structure_type` is deterministic-ready (room-based path)
- required metadata is present (title, author, description)

If any gate fails, watcher quarantines/archives with explicit reason and writes sidecar result status indicating non-ready rejection.

### 2) Shared pipeline entrypoint for parity

Refactor CLI pipeline logic into a shared callable entrypoint (or equivalent shared function) that returns stage-level status payload.

- CLI and watcher both call the same core pipeline implementation.
- Watcher supplies strict mode defaults and source/archive context.
- Core stages remain deterministic and ordered.

### 3) Watcher remains archive + sidecar owner

Watcher continues to own:
- source-file archival naming
- sidecar file creation in `modules/ingest/archive/*.result.json`

Pipeline stage details are embedded under `result` in sidecar payload using canonical keys (`media_extraction`, `media_handles`, `portrait_prewarm`).

### 4) Provider generation remains explicit

Watcher parity must preserve opt-in provider behavior. Default watcher execution must not trigger paid provider generation unless explicit config/flag enables it.

### 5) Failure model

- Core strict failures -> quarantine result; no module write.
- Media/post stages may remain degraded/fail-open as already defined by pipeline contract, but statuses must be surfaced in sidecar.

## Risks / Trade-offs

- Stricter gate may increase rejected files for staff.
  - Mitigation: clear rejection reasons and simple guidance: "prepare via skill first".
- Shared pipeline refactor can introduce regressions.
  - Mitigation: parity tests with same validated fixture through both CLI and watcher.

## Migration Plan

1. Extract/centralize shared ingest pipeline callable from CLI script internals.
2. Update watcher to run strict preflight gate + shared pipeline invocation.
3. Keep watcher archive + sidecar write path intact; enrich sidecar fields from pipeline output.
4. Add/extend regression tests for strict gate and parity.
5. Validate with local ingest-ready fixture in `modules/ingest/`.

## Verification Strategy

- Unit/regression tests for watcher strict gate and sidecar contents.
- Parity test: same validated markdown via CLI and watcher yields equivalent module slug + core stage success statuses.
- Manual smoke: drop validated file into `modules/ingest/`, start server, confirm module appears and sidecar audit passes.
