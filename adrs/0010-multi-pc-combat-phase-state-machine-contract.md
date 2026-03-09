# ADR-0010: Multi-PC Combat Phase State Machine Contract

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Combat regressions were caused by phase desync, initiative ambiguity, and incomplete roster/marker synchronization.

## Decision
Treat multi-PC combat as a deterministic state machine:
- Two-group initiative startup with `/init <1-20>` gate.
- Explicit opening-batch marker behavior for DM-start rounds.
- Deterministic PC-phase and enemy-phase transitions.
- Roster normalization ensures all party PCs are represented consistently.
- Out-of-context combat commands are blocked with deterministic system guidance.

## Consequences
- Combat flow is predictable and testable.
- Fewer retry loops and phase-lock failures.
- Requires stricter validation and state sync at boundaries.

## Sources
- `AGENTS.md`
- `openspec/changes/archive/2026-02-27-multipc-initiative-phase-sync-and-roster-integrity/`
- `openspec/changes/archive/2026-02-15-combat-state-init-and-batching-hardening/`
