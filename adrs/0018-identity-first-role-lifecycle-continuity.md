# ADR-0018: Identity-First Role Lifecycle Continuity (NPC/PC/Retired)

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Character role changes (NPC to PC, retire, return) can fragment identity and memory continuity if represented as clones.

## Decision
Use in-place role transitions with stable identity:
- Preserve `character_id`.
- Append transition events to `_tabletop_role_history`.
- Persist leave/return transition memory with actor/witness links.

## Consequences
- Better continuity across campaign arcs.
- Cleaner auditing of role evolution.
- Requires strict normalization across role fields and party membership state.

## Sources
- `AGENTS.md`
- `memory-bank/systemPatterns.md`
- `openspec/changes/archive/2026-02-17-pc-leave-return-world-memory/`
