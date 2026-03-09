# ADR-0008: Head-Body-Tail Prompt Architecture for Multi-PC

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Long-running multi-PC sessions need both strict authoritative state and narrative continuity without runaway token growth.

## Decision
Structure prompts as:
- Head: immutable authoritative state and rules
- Body: compressible historical narrative
- Tail: freshest interactions in raw form

## Consequences
- Mechanical instructions remain stable under long sessions.
- Compression savings are achieved without losing immediate narrative flow.
- Requires discipline to keep head authoritative and body compressible.

## Sources
- `AGENTS.md`
- `memory-bank/systemPatterns.md`
