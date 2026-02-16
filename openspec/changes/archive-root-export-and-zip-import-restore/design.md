## Context

PR2 established archive zip generation and fail-closed behavior for full saves, plus reset memory parity. Operational testing shows staff need a simple, obvious archive location for USB copy and a direct zip restore path. The current folder-based restore is robust and should remain the source of truth for final restore semantics.

## Goals / Non-Goals

Goals:
- Write full-save archive zips to repo-root `archive_exports/`.
- Add restore-from-zip that uses strict preflight validation and safe staging.
- Reuse existing restore pipeline after staging extracted save folder.
- Keep existing folder restore path and essential save unchanged.

Non-Goals:
- No cloud sync.
- No changes to save lineage/worldline semantics.
- No broad UI redesign.

## Decisions

### 1) Canonical export location is repo-root `archive_exports/`
Decision:
- Full-save zip artifacts are generated to `archive_exports/` at repo root.

Rationale:
- Immediate discoverability for staff and USB workflows.

### 2) Deterministic archive naming
Decision:
- Name format: `archive_<module>_<timestamp>_<save_folder>.zip`.

Rationale:
- Human-readable, sortable, and unique for operational triage.

### 3) Zip restore is staged then delegated
Decision:
- Restore-from-zip pipeline performs:
  1. Preflight zip validation
  2. Secure extraction to temp staging
  3. Staging save folder into canonical module save dir
  4. Delegate to existing restore function

Rationale:
- Minimizes new restore logic and preserves proven semantics.

### 4) Security checks are mandatory
Decision:
- Reject archives containing traversal/absolute paths.
- Reject missing `save_metadata.json` or invalid module mapping.
- Fail restore explicitly with operator-readable error.

Rationale:
- Prevent unsafe extraction and silent corruption.

## Data Flow

### Full save path
1. User triggers save with `save_mode=full`.
2. Save folder created as today.
3. Zip generated in `archive_exports/`.
4. Success payload includes root export path.

### Zip restore path
1. User selects zip archive from load dialog archive section.
2. Backend preflight validates archive and metadata.
3. Backend stages extracted save folder under canonical module save path.
4. Backend invokes existing folder restore path.
5. Existing restore-complete/restart behavior emitted.

## Risks / Mitigations

- Risk: malformed zip contents -> Mitigation: strict preflight + fail-closed.
- Risk: duplicate save folder naming -> Mitigation: deterministic collision handling (suffix or reject with explicit message).
- Risk: behavioral divergence from folder restore -> Mitigation: delegate to existing restore core after staging.

## Migration Plan

1. Add root export constants/helpers.
2. Wire full-save archive output path update.
3. Add archive zip catalog listing.
4. Add zip preflight + secure extract + staging helpers.
5. Add zip restore action route.
6. Add load dialog archive list wiring.
7. Validate compile/smoke/negative/regression.
