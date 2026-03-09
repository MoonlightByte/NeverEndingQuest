# ADR-0011: NPC Arrival Narration-State Synchronization Contract

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Narrative references to off-location NPCs could diverge from persisted world state, causing retry loops and continuity errors.

## Decision
Require same-response state action when off-location NPC arrival is narrated:
- Accept `moveBackgroundNPC` or explicit party-add actions.
- Fail validation when arrival narration lacks a matching state update.
- Exempt already-present NPCs and party members from false positives.

## Consequences
- Narration/state consistency is enforceable.
- Reduced silent drift in long sessions.
- Validation prompts and runtime rules must stay aligned.

## Sources
- `AGENTS.md`
- `openspec/changes/archive/2025-02-27-tt-npc-arrival-state-sync/`
