# ADR-0021: Ingest Watcher Strict Gate and CLI Parity Contract

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Watcher and CLI ingest flows drifted in behavior and validation strictness, creating inconsistent outcomes.

## Decision
Route watcher through the same strict shared ingest pipeline used by CLI:
- Preflight readiness gate with quarantine for non-ready inputs.
- Shared strict pipeline invocation.
- Canonical sidecar result shape for parity and audits.

## Consequences
- Operational behavior is consistent regardless of entrypoint.
- Quarantine outcomes become deterministic and auditable.
- Requires maintaining parity tests across watcher and CLI paths.

## Sources
- `AGENTS.md`
- `web/extensions/module_ingest_watch.py`
- `openspec/changes/archive/2026-03-05-homebrew-watcher-strict-cli-parity/`
