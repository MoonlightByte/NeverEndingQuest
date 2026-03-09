# ADR-0005: Canonical State Ownership by Persistence Domain

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Multi-source state updates can create subtle desynchronization in tabletop sessions.

## Decision
Assign single ownership domains:
- Party state -> `party_tracker.json`
- Character state -> character JSON files
- Combat state -> encounter files
- Managers -> runtime coordinators/cache, not primary truth

## Consequences
- Recovery and debugging are deterministic.
- Cross-system updates are easier to reason about.
- Runtime caches must always reconcile with persisted state.

## Sources
- `AGENTS.md`
- `memory-bank/systemPatterns.md`
