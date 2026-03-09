# ADR-0023: Canonical-World Continuous Module Import Pipeline

- Date: 2026-03-10
- Status: Planned
- Supersedes: ADR-0028
- Superseded by: None

## Context
The v2 direction requires sustained ingestion of community adventures into a long-lived canonical campaign world.

## Decision
Plan a continuous import pipeline:
- Intake -> Extract -> Normalize -> Canonical Rewrite -> Emit -> Validate -> Stitch.
- Strict pass-only publication and quarantine for degraded imports.
- Canonical world default, with optional future world-fork overlays.

## Consequences
- Supports scalable module expansion.
- Enforces quality before publication.
- Significant implementation effort remains across extract/normalize/rewrite stages.

## Sources
- `plans/version-2/module-import.md`
- `AGENTS.md`
