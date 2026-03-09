# ADR-0022: Ingest Success Requires Registration and Strict Bulk Validation

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Generated artifacts alone were insufficient when modules were not registered or validator dependencies degraded silently.

## Decision
Define ingest success as:
- Strict validation passes.
- Module is registered and discoverable in world registry.
- Bulk validation defaults to deterministic target discovery and fails closed on strict dependency problems.

## Consequences
- Better playability guarantees after ingest.
- Fewer "looks valid but not usable" outcomes.
- Stricter gates can increase quarantine frequency until content quality improves.

## Sources
- `AGENTS.md`
- `openspec/changes/archive/2026-03-02-module-ingest-playable-registration/`
- `openspec/changes/archive/2026-03-05-module-validation-bulk-default-targeting/`
