# ADR-0006: Character Data Access Abstraction Layer

- Date: 2026-03-10
- Status: Accepted
- Supersedes: None
- Superseded by: None

## Context
Character reads/writes occurred across multiple call sites with differing assumptions, making migration and consistency hard.

## Decision
Use `utils/pc_manager.py` as the primary abstraction for character state access and updates, with graceful fallback behavior and shared validation.

## Consequences
- Unified access patterns across combat, action handling, and UI paths.
- Easier future backend migration for character storage.
- Slight overhead from abstraction, negligible relative to LLM latency.

## Sources
- `AGENTS.md`
- `memory-bank/systemPatterns.md`
