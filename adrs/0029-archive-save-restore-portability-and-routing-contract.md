# ADR-0029: Archive Save/Restore Portability and Routing Contract

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Campaign operations needed portable archives and deterministic restore routing across save folders and archive zips.

## Decision
Use an archive portability contract:
- Full saves can produce explicit zip artifacts with metadata.
- Restore validates archive preflight, stages canonical save paths, then delegates to core restore flow.
- Load UI presents unified timeline while preserving action compatibility and safety restrictions.

## Consequences
- Better operational portability (including USB workflows).
- Safer restores with fail-closed preflight checks.
- Added complexity in save/restore orchestration and test coverage.

## Sources
- `AGENTS.md`
- `openspec/changes/archive/2026-02-17-archive-root-export-and-zip-import-restore/`
- `openspec/changes/archive/2026-02-17-archive-zip-portability-and-memory-backup-parity/`
