# ADR-0020: Continuity Contract v1 for Any-Order Module Play

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Modules need coherent continuity metadata to support any-order play and strict readiness checks.

## Decision
Require continuity contract v1 fields across ingest and validation gates:
- `continuity_version`
- `entry_state_variants`
- `cross_module_refs`
- `standalone_fallback`

## Consequences
- Shared baseline for readiness and bulk validation.
- Better interoperability between imported and hand-authored modules.
- Requires remediation/enrichment for legacy module sets.

## Sources
- `AGENTS.md`
- `plans/archive/ingest-module.md`
- `openspec/changes/archive/2026-03-09-any-order-module-continuity-normalization/`
