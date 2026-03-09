# ADR-0027: V2 Prime Directive and Approval-Gated Canon Apply

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
V2 architecture requires creative runtime adaptation while protecting canonical world integrity.

## Decision
Adopt the prime directive and Ralph loop:
- Runtime LLM may propose adaptive narrative outputs.
- Python validates deterministic/mechanical constraints.
- Human facilitator approval is required before canon apply.

## Consequences
- Strong governance against accidental canon drift.
- Preserves creativity without sacrificing deterministic safety.
- Adds explicit review workflow for canonization steps.

## Sources
- `plans/version-2/v2-narrative-track.md`
- `AGENTS.md`
