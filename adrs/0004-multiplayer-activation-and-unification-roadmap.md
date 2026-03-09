# ADR-0004: Multiplayer Activation and SP/MP Unification Roadmap

- Date: 2026-03-10
- Status: Planned
- Supersedes: None
- Superseded by: None

## Context
Current tabletop behavior uses a dual-check activation model (`MULTIPLAYER_MODE` plus runtime party size). Long-term maintenance benefits from converging SP and MP code paths.

## Decision
Follow a phased activation roadmap:
- Phase 1: dual-check activation (current).
- Phase 2: runtime detection only (`partyMembers > 1`).
- Phase 3: full SP/MP unification with MP-default behavior.

## Consequences
- Migration can happen incrementally without breaking active flows.
- Compatibility remains during transition.
- Some temporary branching remains until phase completion.

## Sources
- `AGENTS.md`
- `memory-bank/systemPatterns.md`
