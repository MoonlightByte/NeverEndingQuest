# ADR-0016: Two-Plane Memory Architecture (Historical Store vs Prompt Lens)

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Gameplay needs durable long-term memory without flooding prompt context windows.

## Decision
Split memory into two planes:
- Historical plane: additive SQLite store (`data/memory.db`).
- Retrieval plane: bounded deterministic query packs for runtime prompts.

## Consequences
- Long-horizon continuity is preserved.
- Prompt token use remains bounded.
- Retrieval quality depends on ranking policies and ingest fidelity.

## Sources
- `AGENTS.md`
- `memory-bank/systemPatterns.md`
- `openspec/changes/archive/2026-02-13-memory-schema-retrieval-foundation/`
